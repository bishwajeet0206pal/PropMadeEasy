from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from core.models import ApprovalTask, ApprovalStatus, ApprovalActionType
from core.audit import AuditLogger

class UnifiedApprovalInbox:
    def __init__(self, audit_logger: AuditLogger):
        self.tasks: Dict[str, ApprovalTask] = {}
        self.audit = audit_logger

    def create_task(self, action_type: ApprovalActionType, target_role: str, summary: str, details: Dict[str, Any]) -> ApprovalTask:
        task_id = f"TSK-{len(self.tasks) + 101:04d}"
        task = ApprovalTask(
            task_id=task_id,
            action_type=action_type,
            target_role=target_role,
            summary=summary,
            details=details,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now()
        )
        self.tasks[task_id] = task
        self.audit.record(
            actor="Agent:WorkflowCoordinator",
            action="APPROVAL_TASK_CREATED",
            entity_type="ApprovalTask",
            entity_id=task_id,
            details={"action_type": action_type.value, "target_role": target_role, "summary": summary}
        )
        return task

    def get_pending_tasks(self, role: Optional[str] = None) -> List[ApprovalTask]:
        pending = [t for t in self.tasks.values() if t.status in (ApprovalStatus.PENDING, ApprovalStatus.ESCALATED)]
        if role:
            pending = [t for t in pending if t.target_role == role or t.status == ApprovalStatus.ESCALATED]
        return pending

    def approve(self, task_id: str, decider_name: str, notes: Optional[str] = None) -> ApprovalTask:
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        task.status = ApprovalStatus.APPROVED
        task.decided_by = decider_name
        task.decision_notes = notes or "Approved as submitted."
        task.resolved_at = datetime.now()

        self.audit.record(
            actor=f"Human:{decider_name}",
            action="TASK_APPROVED",
            entity_type="ApprovalTask",
            entity_id=task_id,
            details={"notes": task.decision_notes, "details": task.details}
        )
        return task

    def edit_and_approve(self, task_id: str, decider_name: str, modifications: Dict[str, Any], notes: str) -> ApprovalTask:
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        task.status = ApprovalStatus.EDITED
        task.decided_by = decider_name
        task.details.update(modifications)
        task.decision_notes = f"Edited: {notes}"
        task.resolved_at = datetime.now()

        self.audit.record(
            actor=f"Human:{decider_name}",
            action="TASK_EDITED_AND_APPROVED",
            entity_type="ApprovalTask",
            entity_id=task_id,
            details={"modifications": modifications, "notes": notes}
        )
        return task

    def reject(self, task_id: str, decider_name: str, reason: str) -> ApprovalTask:
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        task.status = ApprovalStatus.REJECTED
        task.decided_by = decider_name
        task.decision_notes = f"Rejected: {reason}"
        task.resolved_at = datetime.now()

        self.audit.record(
            actor=f"Human:{decider_name}",
            action="TASK_REJECTED",
            entity_type="ApprovalTask",
            entity_id=task_id,
            details={"reason": reason}
        )
        return task

    def ask_clarification(self, task_id: str, decider_name: str, query: str) -> str:
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found.")
        msg = f"Clarification requested by {decider_name}: '{query}' on Task {task_id}"
        self.audit.record(
            actor=f"Human:{decider_name}",
            action="TASK_CLARIFICATION_REQUESTED",
            entity_type="ApprovalTask",
            entity_id=task_id,
            details={"query": query}
        )
        return msg

    def check_slas(self, current_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        now = current_time or datetime.now()
        alerts = []
        for task in self.tasks.values():
            if task.status == ApprovalStatus.PENDING:
                age_hours = (now - task.created_at).total_seconds() / 3600.0
                if age_hours >= 24 and task.status != ApprovalStatus.ESCALATED:
                    task.status = ApprovalStatus.ESCALATED
                    alerts.append({
                        "task_id": task.task_id,
                        "type": "ESCALATION_TO_OWNER",
                        "message": f"Task {task.task_id} ({task.summary}) pending >24h. Escalated to Project Owner."
                    })
                    self.audit.record(
                        actor="System:SLAChecker",
                        action="SLA_ESCALATED_TO_OWNER",
                        entity_type="ApprovalTask",
                        entity_id=task.task_id,
                        details={"age_hours": age_hours}
                    )
                elif age_hours >= 4:
                    alerts.append({
                        "task_id": task.task_id,
                        "type": "REMINDER_4H",
                        "message": f"Task {task.task_id} pending for {age_hours:.1f}h. Reminder sent to {task.target_role}."
                    })
        return alerts
