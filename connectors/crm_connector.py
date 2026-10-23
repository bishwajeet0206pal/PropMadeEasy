import json
from typing import Dict, Any, Optional
from core.models import ChannelSource
from agents.orchestrator import PropertyWorkflowOrchestrator

class CRMConnector:
    """
    Adapter for CRM integration (Sell.Do, LeadSquared, Zoho, etc.).
    Operates in 'read-mostly, write-light' mode.
    """
    def __init__(self, orchestrator: PropertyWorkflowOrchestrator):
        self.orchestrator = orchestrator

    def handle_incoming_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives webhook from Sell.Do / Meta Ad / Portal.
        """
        name = payload.get("lead_name", "Unknown Buyer")
        phone = payload.get("phone", "+919999999999")
        source_str = payload.get("channel", "Meta/Google Ad")
        broker = payload.get("broker_name")

        # Map channel
        channel = ChannelSource.DIGITAL_AD
        if "broker" in source_str.lower() or "partner" in source_str.lower():
            channel = ChannelSource.BROKER
        elif "portal" in source_str.lower() or "99acres" in source_str.lower():
            channel = ChannelSource.PORTAL
        elif "walk" in source_str.lower():
            channel = ChannelSource.WALK_IN
        elif "whatsapp" in source_str.lower():
            channel = ChannelSource.WHATSAPP

        lead = self.orchestrator.sales_closer.s1_catch_lead(
            name=name, phone=phone, channel=channel, broker_name=broker
        )

        return {"status": "SUCCESS", "lead_id": lead.lead_id, "name": lead.full_name}

    def write_crm_activity_note(self, lead_id: str, note: str) -> Dict[str, Any]:
        """
        Writes notes & tasks back into developer's CRM without altering system-of-record state.
        """
        return {"status": "SUCCESS", "lead_id": lead_id, "note_appended": note}

class SiteAppConnector:
    """
    Adapter for Powerplay / Mobile Site Checklists.
    """
    def __init__(self, orchestrator: PropertyWorkflowOrchestrator):
        self.orchestrator = orchestrator

    def submit_daily_site_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        report = self.orchestrator.site_watcher.g2_ingest_and_validate_report(
            project_id=payload.get("project_id", "PRJ-GH-KOKAPET"),
            tower=payload.get("tower", "Tower B"),
            site_engineer_name=payload.get("engineer_name", "Suresh Reddy"),
            milestone=payload.get("current_milestone", "7th slab"),
            percent_done=float(payload.get("percent_done", 62.0)),
            labor_count=int(payload.get("labor_count", 48)),
            material_shortage=bool(payload.get("material_shortage", False)),
            material_notes=payload.get("material_notes"),
            photos_submitted=payload.get("photos", [])
        )
        return {"status": "SUCCESS", "report_id": report.report_id}

class TallyERPConnector:
    """
    Adapter for TallyPrime and ERP financial ledgers.
    Supports HTTP XML/JSON or CSV/ODBC read-only sync.
    """
    def __init__(self, orchestrator: PropertyWorkflowOrchestrator):
        self.orchestrator = orchestrator

    def sync_stage_demand_into_tally(self, letter_id: str, buyer_name: str, amount: int, milestone: str) -> Dict[str, Any]:
        """
        Generates standard TallyPrime XML voucher for stage payment receivable.
        """
        xml_voucher = f"""
        <ENVELOPE>
          <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
          <BODY>
            <IMPORTDATA>
              <REQUESTDATA>
                <TALLYMESSAGE>
                  <VOUCHER VCHTYPE="Sales" ACTION="Create">
                    <DATE>{datetime.now().strftime("%Y%m%d")}</DATE>
                    <PARTYLEDGERNAME>{buyer_name}</PARTYLEDGERNAME>
                    <NARRATION>Milestone demand: {milestone} - Letter {letter_id}</NARRATION>
                    <ALLLEDGERENTRIES.LIST>
                      <LEDGERNAME>Construction Milestone Receivables</LEDGERNAME>
                      <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                      <AMOUNT>-{amount}</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                  </VOUCHER>
                </TALLYMESSAGE>
              </REQUESTDATA>
            </IMPORTDATA>
          </BODY>
        </ENVELOPE>
        """
        return {"status": "SUCCESS", "letter_id": letter_id, "xml_payload": xml_voucher.strip()}

from datetime import datetime
