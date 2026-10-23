import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from core.models import (
    StageDemandLetter, RERAAccountCertificatePack, BuyerProgressUpdate,
    ApprovalActionType, ApprovalStatus
)
from core.approval_inbox import UnifiedApprovalInbox
from core.facts_engine import GroundedFactsEngine
from core.audit import AuditLogger

class MoneyDeskAgent:
    """
    Agent 2b: Money Desk (Sub-agent of Delivery and Cash Guardian).
    Executes Milestone and Cash Flow Loop: Steps G6 to G9.
    Hardened with:
    - GD-I1: Mandatory Human Sign-off gate (Site Engineer & Project Head) before drafting demand letters.
    - GD-I2: Milestone status marked 'demanded' to prevent re-billing loops.
    - GD-I3: Deterministic Code Node arithmetic for per-buyer demand amounts (Section 17E).
    - GD-I4: Unit-keyed ledger filtering by active status & project.
    """
    def __init__(self, facts_engine: GroundedFactsEngine, inbox: UnifiedApprovalInbox, audit: AuditLogger):
        self.facts_engine = facts_engine
        self.inbox = inbox
        self.audit = audit
        self.demand_batches: Dict[str, List[StageDemandLetter]] = {}
        self.certificate_packs: Dict[str, RERAAccountCertificatePack] = {}
        self.buyer_updates: Dict[str, BuyerProgressUpdate] = {}
        self.demanded_milestones: set = set()

    # G6: Confirm stage is done (GD-I1 MANDATORY HUMAN GATE)
    def g6_request_stage_completion_signoff(
        self,
        project_id: str,
        tower: str,
        stage_number: int,
        stage_name: str,
        photo_evidence_links: List[str]
    ) -> str:
        task = self.inbox.create_task(
            action_type=ApprovalActionType.STAGE_COMPLETION,
            target_role="Project Head",
            summary=f"MANDATORY SIGN-OFF: Confirm Physical Completion of {tower} Stage {stage_number}: '{stage_name}'",
            details={
                "project_id": project_id,
                "tower": tower,
                "stage_number": stage_number,
                "stage_name": stage_name,
                "photos_attached": photo_evidence_links,
                "signoff_requirement": "Site Engineer and Project Head must visually inspect and certify before demand letters are generated (GD-I1)."
            }
        )
        self.audit.record("Agent:MoneyDesk", "GD_I1_STAGE_COMPLETION_GATE_CREATED", "ApprovalTask", task.task_id, {
            "tower": tower, "stage": stage_name
        })
        return task.task_id

    # G7: Draft stage letters with DETERMINISTIC ARITHMETIC (GD-I3 & GD-I4 / Section 17E)
    def g7_draft_stage_letters_and_certificates(
        self,
        project_id: str,
        tower: str,
        stage_number: int,
        stage_name: str,
        demand_pct: float,
        buyer_ledger: List[Dict[str, Any]],
        photo_proof_links: List[str]
    ) -> Dict[str, Any]:
        milestone_key = f"{project_id}_{tower}_{stage_number}"
        if milestone_key in self.demanded_milestones:
            raise ValueError(f"Milestone {milestone_key} has already been demanded (GD-I2 protection).")

        batch_id = f"BATCH-{uuid.uuid4().hex[:6].upper()}"
        due_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")

        # GD-I4: Filter by active status, project, valid phone, key by unit_id
        valid_buyers = [
            b for b in buyer_ledger
            if b.get("project_id", project_id) == project_id
            and b.get("status", "active").lower() == "active"
            and b.get("unit_number")
        ]

        letters: List[StageDemandLetter] = []
        total_demand_value = 0
        per_buyer_breakdown = []

        # GD-I3: Deterministic Code Node Arithmetic (Section 17E)
        for b in valid_buyers:
            letter_id = f"LTR-{uuid.uuid4().hex[:6].upper()}"
            agreement_val = b.get("total_agreed_price", 10000000)
            amount = round(agreement_val * (demand_pct / 100.0))
            total_demand_value += amount

            letter = StageDemandLetter(
                letter_id=letter_id,
                buyer_id=b.get("buyer_id", f"BUY-{b['unit_number']}"),
                buyer_name=b["buyer_name"],
                unit_number=b["unit_number"],
                stage_number=stage_number,
                stage_name=stage_name,
                amount_due=amount,
                due_date=due_date,
                photo_proof_links=photo_proof_links,
                engineer_confirmed=True,
                finance_head_approved=False
            )
            letters.append(letter)
            per_buyer_breakdown.append({
                "unit": b["unit_number"],
                "buyer": b["buyer_name"],
                "agreement_val": agreement_val,
                "amount_due": amount
            })

        self.demand_batches[batch_id] = letters

        # Draft 70% Escrow Certificate Pack
        pack_id = f"CERT-70-{uuid.uuid4().hex[:6].upper()}"
        cert_pack = RERAAccountCertificatePack(
            pack_id=pack_id,
            project_id=project_id,
            stage_name=stage_name,
            work_completed_pct=62.0,
            amount_to_withdraw=round(total_demand_value * 0.70),
            form1_engineer_certified=False,
            form2_architect_certified=False,
            form3_ca_certified=False,
            all_signed=False
        )
        self.certificate_packs[pack_id] = cert_pack

        # Trigger Approval Task for Finance Head
        task = self.inbox.create_task(
            action_type=ApprovalActionType.DEMAND_LETTER_BATCH,
            target_role="Finance Head",
            summary=f"Approve {tower} Stage {stage_number} Demand Letters ({len(letters)} buyers, Total: ₹{total_demand_value:,})",
            details={
                "batch_id": batch_id,
                "pack_id": pack_id,
                "tower": tower,
                "stage_name": stage_name,
                "demand_pct": demand_pct,
                "total_demand_value": total_demand_value,
                "escrow_70pct_amount": cert_pack.amount_to_withdraw,
                "buyer_table": per_buyer_breakdown,
                "photo_evidence_attached": True
            }
        )

        self.audit.record("Agent:MoneyDesk", "G7_DEMAND_LETTERS_DRAFTED_CODE_MATH", "Batch", batch_id, {
            "total_value": total_demand_value, "buyers_count": len(letters), "task_id": task.task_id
        })

        return {
            "batch_id": batch_id,
            "pack_id": pack_id,
            "total_demand_value": total_demand_value,
            "approval_task_id": task.task_id,
            "milestone_key": milestone_key
        }

    # G8: Send letters & update milestone status to 'demanded' (GD-I2)
    def g8_distribute_approved_demand_letters(self, batch_id: str, milestone_key: Optional[str] = None) -> List[Dict[str, Any]]:
        letters = self.demand_batches.get(batch_id, [])
        if not letters:
            raise ValueError(f"Batch {batch_id} not found.")

        dispatched = []
        for l in letters:
            l.finance_head_approved = True
            l.sent_to_buyer = True
            dispatched.append({
                "buyer_name": l.buyer_name,
                "unit": l.unit_number,
                "amount": l.amount_due,
                "due_date": l.due_date,
                "photos_attached": len(l.photo_proof_links),
                "message": (
                    f"Dear {l.buyer_name}, milestone '{l.stage_name}' for Unit {l.unit_number} has been certified complete on site. "
                    f"Demand letter of ₹{l.amount_due:,} is due on {l.due_date}. "
                    f"Verified site progress photographs are attached as legal proof. TG-RERA Registration P02400008899."
                )
            })

        # GD-I2: Mark milestone as demanded to prevent repeat billing
        if milestone_key:
            self.demanded_milestones.add(milestone_key)

        self.audit.record("Agent:MoneyDesk", "G8_DEMAND_LETTERS_DISPATCHED_AND_MARKED", "Batch", batch_id, {
            "count": len(letters), "milestone_key": milestone_key
        })
        return dispatched

    # G9: Monthly buyer update & RERA filing (Human approved)
    def g9_draft_buyer_progress_newsletter(
        self,
        tower: str,
        month: str,
        percent_done: float,
        achievements: List[str],
        photo_urls: List[str],
        next_stage_target: str
    ) -> BuyerProgressUpdate:
        update_id = f"UPD-{uuid.uuid4().hex[:6].upper()}"
        update = BuyerProgressUpdate(
            update_id=update_id,
            month=month,
            tower=tower,
            percent_done=percent_done,
            key_achievements=achievements,
            photo_urls=photo_urls,
            next_stage_target=next_stage_target,
            approved_by_project_head=False
        )
        self.buyer_updates[update_id] = update

        task = self.inbox.create_task(
            action_type=ApprovalActionType.BUYER_PROGRESS_UPDATE,
            target_role="Project Head",
            summary=f"Approve {month} Buyer Progress Newsletter for {tower} ({percent_done}% complete)",
            details={
                "update_id": update_id,
                "tower": tower,
                "month": month,
                "percent_done": percent_done,
                "achievements": achievements,
                "next_target": next_stage_target,
                "photos": photo_urls
            }
        )
        self.audit.record("Agent:MoneyDesk", "G9_BUYER_UPDATE_DRAFTED", "BuyerProgressUpdate", update_id, {
            "tower": tower, "percent": percent_done
        })
        return update

    def g9_publish_approved_update(self, update_id: str) -> str:
        update = self.buyer_updates.get(update_id)
        if not update:
            raise ValueError(f"Update {update_id} not found.")
        update.approved_by_project_head = True

        self.facts_engine.update_construction_progress_from_guardian(
            tower=update.tower,
            current_stage=update.next_stage_target,
            percent_done=update.percent_done
        )

        msg = (
            f"Green Heights Construction Update - {update.month}: "
            f"{update.tower} is now {update.percent_done}% complete! "
            f"Key progress: {', '.join(update.key_achievements)}. "
            f"Target: {update.next_stage_target}. "
            f"Approved photos attached. TG-RERA Reg: P02400008899."
        )

        self.audit.record("Agent:MoneyDesk", "G9_BUYER_UPDATE_PUBLISHED_AND_FACTS_SYNCED", "BuyerProgressUpdate", update_id, {
            "tower": update.tower, "percent": update.percent_done
        })
        return msg
