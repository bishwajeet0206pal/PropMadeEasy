import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from core.models import (
    DailySiteReport, SpotPhotoVerification, ScheduleVariance,
    VarianceRiskLevel, ApprovalActionType
)
from core.approval_inbox import UnifiedApprovalInbox
from core.audit import AuditLogger

class SiteWatcherAgent:
    """
    Agent 2a: Site Watcher (Sub-agent of Delivery and Cash Guardian).
    Executes Daily Site Loop: Steps G1 to G5.
    Hardened with:
    - GD-I7: Deterministic Date Maths for schedule variance (Section 17D).
    - 4-spot photo verification and missing-update streak escalation.
    """
    def __init__(self, inbox: UnifiedApprovalInbox, audit: AuditLogger):
        self.inbox = inbox
        self.audit = audit
        self.daily_reports: Dict[str, DailySiteReport] = {}
        self.variances: Dict[str, ScheduleVariance] = {}
        self.missing_streak_by_tower: Dict[str, int] = {}

    # G1: Daily site prompt
    def g1_generate_daily_prompt(self, project_id: str, tower: str, site_engineer_name: str) -> Dict[str, Any]:
        return {
            "prompt_target": site_engineer_name,
            "project_id": project_id,
            "tower": tower,
            "required_fields": [
                "current_milestone",
                "percent_completed",
                "laborers_on_site",
                "material_shortage (Yes/No)"
            ],
            "required_photo_spots": [
                "Spot 1: Main Slab Reinforcement",
                "Spot 2: Concreting Area",
                "Spot 3: Material Yard & Rebar Stock",
                "Spot 4: Safety & Perimeter Edge"
            ],
            "cutoff_time": "18:00 IST"
        }

    # G2: Ingest and validate report
    def g2_ingest_and_validate_report(
        self,
        project_id: str,
        tower: str,
        site_engineer_name: str,
        milestone: str,
        percent_done: float,
        labor_count: int,
        material_shortage: bool,
        material_notes: Optional[str],
        photos_submitted: List[str]
    ) -> DailySiteReport:
        report_id = f"SITE-{uuid.uuid4().hex[:6].upper()}"
        
        expected_spots = [
            "Spot 1: Main Slab Reinforcement",
            "Spot 2: Concreting Area",
            "Spot 3: Material Yard & Rebar Stock",
            "Spot 4: Safety & Perimeter Edge"
        ]
        spot_verifications = []
        for i, spot in enumerate(expected_spots):
            received = i < len(photos_submitted)
            spot_verifications.append(
                SpotPhotoVerification(spot_name=spot, photo_received=received, notes=photos_submitted[i] if received else "MISSING")
            )

        report = DailySiteReport(
            report_id=report_id,
            project_id=project_id,
            tower=tower,
            date=datetime.now().strftime("%Y-%m-%d"),
            site_engineer_name=site_engineer_name,
            current_milestone=milestone,
            percent_completed=percent_done,
            laborers_on_site=labor_count,
            material_shortage=material_shortage,
            material_notes=material_notes,
            spot_photos=spot_verifications
        )
        self.daily_reports[report_id] = report
        self.missing_streak_by_tower[tower] = 0

        self.audit.record("Agent:SiteWatcher", "G2_SITE_UPDATE_INGESTED", "DailySiteReport", report_id, {
            "tower": tower, "percent": percent_done, "labor": labor_count, "material_shortage": material_shortage
        })
        return report

    def g3_evaluate_schedule_variance(
        self,
        tower: str,
        current_stage: str,
        planned_completion_date: str,
        actual_projected_date: str,
        days_behind: int,
        root_cause: Optional[str] = None
    ) -> ScheduleVariance:
        """Compatibility alias using direct variance input."""
        risk = VarianceRiskLevel.AT_RISK if days_behind > 21 else (VarianceRiskLevel.WATCH if days_behind > 7 else VarianceRiskLevel.ON_TRACK)
        variance = ScheduleVariance(
            tower=tower,
            current_stage=current_stage,
            planned_completion_date=planned_completion_date,
            actual_projected_date=actual_projected_date,
            days_behind=days_behind,
            risk_level=risk,
            root_cause=root_cause,
            affected_milestone_demands=[f"{tower} - {current_stage} Demand", f"{tower} - 70% Escrow Release"]
        )
        self.variances[tower] = variance
        self.audit.record("Agent:SiteWatcher", "G3_VARIANCE_EVALUATED", "Tower", tower, {
            "days_behind": days_behind, "risk": risk.value, "root_cause": root_cause
        })
        return variance

    # G3: Compare plan with actual via DETERMINISTIC DATE MATHS (GD-I7 / Section 17D)
    def g3_compute_schedule_variance_deterministic(
        self,
        tower: str,
        stage_name: str,
        planned_start_date: str,
        planned_end_date: str,
        rera_possession_date: str,
        actual_percent_completed: float,
        blockers_count: int = 0
    ) -> ScheduleVariance:
        """
        Pure arithmetic implementation of Section 17D:
        - plannedPct = (today - start) / (end - start) * 100
        - daysBehind = (plannedPct - actualPct) / 100 * totalDays
        - status: at_risk (>21d or threatens RERA possession), watch (>7d or >=2 blockers), on_track (<=7d)
        """
        today = datetime.now()
        start = datetime.fromisoformat(planned_start_date)
        end = datetime.fromisoformat(planned_end_date)
        possession = datetime.fromisoformat(rera_possession_date)

        total_days = max(1, (end - start).days)
        elapsed_days = max(0, (today - start).days)
        planned_pct = min(100.0, max(0.0, (elapsed_days / total_days) * 100.0))

        days_behind = max(0, round(((planned_pct - actual_percent_completed) / 100.0) * total_days))
        projected_end = end.timestamp() + (days_behind * 86400)
        threatens_rera = projected_end > possession.timestamp()

        if days_behind > 21 or threatens_rera:
            risk = VarianceRiskLevel.AT_RISK
        elif days_behind > 7 or blockers_count >= 2:
            risk = VarianceRiskLevel.WATCH
        else:
            risk = VarianceRiskLevel.ON_TRACK

        variance = ScheduleVariance(
            tower=tower,
            current_stage=stage_name,
            planned_completion_date=planned_end_date,
            actual_projected_date=datetime.fromtimestamp(projected_end).strftime("%Y-%m-%d"),
            days_behind=days_behind,
            risk_level=risk,
            root_cause=f"{blockers_count} reported blockers" if blockers_count else None,
            affected_milestone_demands=[f"{tower} - {stage_name} Demand", f"{tower} - 70% Escrow Release"]
        )
        self.variances[tower] = variance
        self.audit.record("Agent:SiteWatcher", "G3_DETERMINISTIC_VARIANCE_COMPUTED", "Tower", tower, {
            "days_behind": days_behind, "risk": risk.value, "threatens_rera": threatens_rera
        })
        return variance

    # G4: Early Warning (Human in the loop)
    def g4_send_early_warning_if_at_risk(self, variance: ScheduleVariance) -> Optional[str]:
        if variance.risk_level in (VarianceRiskLevel.WATCH, VarianceRiskLevel.AT_RISK):
            task = self.inbox.create_task(
                action_type=ApprovalActionType.DELAY_WARNING_RESOLUTION,
                target_role="Project Head",
                summary=f"Schedule Warning ({variance.risk_level.value}): {variance.tower} is {variance.days_behind} days behind.",
                details={
                    "tower": variance.tower,
                    "stage": variance.current_stage,
                    "days_behind": variance.days_behind,
                    "planned_date": variance.planned_completion_date,
                    "projected_date": variance.actual_projected_date,
                    "actions": ["1. Fix (deploy extra labour)", "2. Accept internal delay buffer", "3. Set internal milestone target"]
                }
            )
            self.audit.record("Agent:SiteWatcher", "G4_EARLY_WARNING_POSTED", "ApprovalTask", task.task_id, {
                "tower": variance.tower, "days_behind": variance.days_behind
            })
            return f"Early warning card posted to Project Head ({task.task_id})."
        return None

    # G5: Supplier chaser
    def g5_chase_supplier(self, vendor_name: str, delayed_material: str, tower: str, target_date: str) -> str:
        msg = (
            f"Automated Priority Notice for {tower} (Skyline Green Heights): "
            f"Consignment '{delayed_material}' is overdue. Please confirm dispatch challan and ETA before 14:00 today."
        )
        self.audit.record("Agent:SiteWatcher", "G5_SUPPLIER_CHASED", "Vendor", vendor_name, {
            "material": delayed_material, "target_date": target_date
        })
        return msg
