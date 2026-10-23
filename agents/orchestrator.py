from typing import Dict, Any, List, Optional
from core.facts_engine import GroundedFactsEngine
from core.approval_inbox import UnifiedApprovalInbox
from core.audit import AuditLogger
from agents.sales_closer import SalesCloserAgent
from agents.site_watcher import SiteWatcherAgent
from agents.money_desk import MoneyDeskAgent

class PropertyWorkflowOrchestrator:
    """
    Master Orchestrator implementing the full agentic architecture from Section 7:
    - Problem 1: Sales Closer (S1-S9)
    - Problem 2: Delivery & Cash Guardian (Site Watcher G1-G5 + Money Desk G6-G9)
    - Unified Approval Inbox & Immutable Audit Logger
    - Two-way Data Feedback Loops (Guardian -> Facts Sheet -> Sales Closer, Sales Closer -> Ledger -> Money Desk)
    """
    def __init__(
        self,
        facts_path: str = "config/facts_sheet.json",
        pricing_path: str = "config/inventory_pricing.json",
        log_dir: str = "logs"
    ):
        self.audit = AuditLogger(log_dir=log_dir)
        self.facts_engine = GroundedFactsEngine(facts_path=facts_path, pricing_path=pricing_path)
        self.inbox = UnifiedApprovalInbox(audit_logger=self.audit)

        # Initialize the two AI teammates
        self.sales_closer = SalesCloserAgent(
            facts_engine=self.facts_engine,
            inbox=self.inbox,
            audit=self.audit
        )
        self.site_watcher = SiteWatcherAgent(
            inbox=self.inbox,
            audit=self.audit
        )
        self.money_desk = MoneyDeskAgent(
            facts_engine=self.facts_engine,
            inbox=self.inbox,
            audit=self.audit
        )

        # Buyer Payment Ledger (Cross-agent ledger fed by S8/S9 and utilized by G7/G8)
        self.buyer_ledger: List[Dict[str, Any]] = [
            {"buyer_id": "BUY-01", "buyer_name": "Ravi K.", "unit_number": "1204", "stage_amount": 740000},
            {"buyer_id": "BUY-02", "buyer_name": "Anita S.", "unit_number": "804", "stage_amount": 620000}
        ]

    def register_confirmed_booking_into_ledger(self, lead_id: str, buyer_name: str, unit_number: str, agreed_price: int):
        """
        Feedback Loop: When Sales Closer completes a booking, it registers
        the buyer into the payment ledger for milestone collections by Money Desk.
        """
        stage_amount = int(agreed_price * 0.15)  # 15% per typical slab milestone
        entry = {
            "buyer_id": f"BUY-{lead_id}",
            "buyer_name": buyer_name,
            "unit_number": unit_number,
            "stage_amount": stage_amount,
            "total_agreed_price": agreed_price
        }
        self.buyer_ledger.append(entry)
        self.audit.record("Orchestrator:LedgerSync", "LEDGER_ENTRY_CREATED_FROM_BOOKING", "BuyerLedger", entry["buyer_id"], entry)
        return entry

    def sync_guardian_progress_to_sales_closer(self, tower: str, current_stage: str, percent_done: float):
        """
        Feedback Loop: Guardian site verification feeds Grounded Facts Engine
        so Sales Closer answers buyers with 100% verified ground truth.
        """
        self.facts_engine.update_construction_progress_from_guardian(tower, current_stage, percent_done)
        self.audit.record("Orchestrator:ProgressSync", "FACTS_SHEET_UPDATED_WITH_SITE_PROGRESS", "Tower", tower, {
            "current_stage": current_stage, "percent_done": percent_done
        })
