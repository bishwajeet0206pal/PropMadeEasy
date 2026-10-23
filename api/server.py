import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.models import ChannelSource, ApprovalActionType, LeadStage, LeadTemperature
from agents.orchestrator import PropertyWorkflowOrchestrator

app = FastAPI(title="Real Estate Agentic AI - Workflow Orchestrator")

# Initialize orchestrator
orchestrator = PropertyWorkflowOrchestrator()

# Pre-populate sample leads across pipeline buckets to make Atlassian Kanban board immediately rich & interactive
def _populate_initial_pipeline():
    # 1. New Lead
    l1 = orchestrator.sales_closer.s1_catch_lead(
        name="Ananya Sharma",
        phone="+919811223344",
        channel=ChannelSource.WHATSAPP,
        email="ananya.sharma@example.com"
    )
    l1.stage = LeadStage.NEW
    l1.temperature = LeadTemperature.WARM
    l1.area_preference = "Kokapet / Financial District"
    l1.bhk_preference = 2
    l1.budget_min = 8500000
    l1.budget_max = 9800000
    l1.last_buyer_message = "Hi, saw Green Heights Kokapet on Instagram. Can you share 2 BHK pricing?"
    l1.chat_history = [
        {"sender": "buyer", "text": "Hi, saw Green Heights Kokapet on Instagram. Can you share 2 BHK pricing?", "time": "10:14 AM"}
    ]

    # 2. Qualifying
    l2 = orchestrator.sales_closer.s1_catch_lead(
        name="Ravi Kumar",
        phone="+919876543210",
        channel=ChannelSource.DIGITAL_AD,
        email="ravi.kumar@example.com"
    )
    orchestrator.sales_closer.s2_process_buyer_message(l2.lead_id, "What is the 3 BHK price?")
    orchestrator.sales_closer.s3_qualify_lead(
        lead_id=l2.lead_id,
        budget_min=13000000,
        budget_max=15000000,
        bhk=3,
        possession_year=2028,
        loan_needed=True
    )
    l2.stage = LeadStage.QUALIFYING
    l2.temperature = LeadTemperature.HOT
    l2.area_preference = "Kokapet"

    # 3. Price Sent (Cost Sheet)
    l3 = orchestrator.sales_closer.s1_catch_lead(
        name="Vikram Malhotra",
        phone="+919988776655",
        channel=ChannelSource.PORTAL,
        email="vikram.m@techcorp.in"
    )
    orchestrator.sales_closer.s3_qualify_lead(l3.lead_id, 12000000, 13500000, 3, 2028, True)
    orchestrator.sales_closer.s4_generate_cost_sheet(l3.lead_id, "TA-804")
    l3.stage = LeadStage.PRICE_SENT
    l3.temperature = LeadTemperature.HOT

    # 4. Visit Booked
    l4 = orchestrator.sales_closer.s1_catch_lead(
        name="Sneha & Rajesh Patel",
        phone="+919765432190",
        channel=ChannelSource.BROKER,
        broker_name="Anarock Advisory",
        email="rajesh.patel@gmail.com"
    )
    orchestrator.sales_closer.s3_qualify_lead(l4.lead_id, 12500000, 14000000, 3, 2028, True)
    orchestrator.sales_closer.s4_generate_cost_sheet(l4.lead_id, "TA-804")
    orchestrator.sales_closer.s5_book_site_visit(l4.lead_id, "TA-804", "Saturday 11:30 AM", "Praveen Kumar")
    l4.stage = LeadStage.VISIT_BOOKED
    l4.temperature = LeadTemperature.HOT

    # 5. Visited
    l5 = orchestrator.sales_closer.s1_catch_lead(
        name="Karthik Sundaram",
        phone="+919840123456",
        channel=ChannelSource.WALK_IN,
        email="karthik.s@fintech.co"
    )
    orchestrator.sales_closer.s3_qualify_lead(l5.lead_id, 13000000, 14500000, 3, 2028, True)
    orchestrator.sales_closer.s5_book_site_visit(l5.lead_id, "TB-1204", "Yesterday 3:00 PM", "Suresh Reddy")
    orchestrator.sales_closer.s6_post_visit_followup(l5.lead_id, "Client loved Tower A corner balcony and 35,000 sq ft clubhouse. Applying for SBI loan sanction.")
    l5.stage = LeadStage.VISITED
    l5.temperature = LeadTemperature.HOT

    # 6. Negotiating / Discount Approval
    l6 = orchestrator.sales_closer.s1_catch_lead(
        name="Deepak & Sangeeta Verma",
        phone="+919822334455",
        channel=ChannelSource.DIGITAL_AD,
        email="dverma@innovate.org"
    )
    orchestrator.sales_closer.s3_qualify_lead(l6.lead_id, 12000000, 13000000, 3, 2028, False)
    orchestrator.sales_closer.s4_generate_cost_sheet(l6.lead_id, "TA-804")
    orchestrator.sales_closer.s7_request_discount(l6.lead_id, "TA-804", 3.0)
    l6.stage = LeadStage.NEGOTIATING
    l6.temperature = LeadTemperature.HOT

    # 7. Booking Docs Pending
    l7 = orchestrator.sales_closer.s1_catch_lead(
        name="Pooja Hegde",
        phone="+919845098765",
        channel=ChannelSource.PORTAL,
        email="pooja.hegde@designstudio.in"
    )
    orchestrator.sales_closer.s3_qualify_lead(l7.lead_id, 12500000, 13500000, 3, 2028, True)
    orchestrator.sales_closer.s8_draft_booking_agreement(l7.lead_id, "TA-804", 12500000, 500000)
    l7.stage = LeadStage.BOOKING_DOCS
    l7.temperature = LeadTemperature.HOT

    # 8. Booked
    l8 = orchestrator.sales_closer.s1_catch_lead(
        name="Dr. Suresh Nair",
        phone="+919810987654",
        channel=ChannelSource.BROKER,
        broker_name="Square Yards Hyderabad",
        email="dr.nair@apollo.org"
    )
    orchestrator.sales_closer.s3_qualify_lead(l8.lead_id, 13000000, 14000000, 3, 2028, False)
    orchestrator.sales_closer.s8_draft_booking_agreement(l8.lead_id, "TB-1204", 13177500, 1000000)
    orchestrator.sales_closer.s9_finalize_booking(l8.lead_id, 13177500)
    l8.stage = LeadStage.BOOKED
    l8.temperature = LeadTemperature.HOT

    # 9. Lost / Not Now
    l9 = orchestrator.sales_closer.s1_catch_lead(
        name="Alok Mittal",
        phone="+919900112233",
        channel=ChannelSource.WHATSAPP,
        email="alok.m@startup.io"
    )
    l9.stage = LeadStage.LOST
    l9.temperature = LeadTemperature.NOT_NOW
    l9.notes.append("Looking for ready-to-move-in (2024). Green Heights RERA possession is 2028. Marked lost with polite referral.")
    l9.last_buyer_message = "Need immediate possession within 3 months."
    l9.last_agent_reply = "Green Heights is currently under construction with statutory TG-RERA delivery in 2028. We have noted your preference."

_populate_initial_pipeline()

# API Schemas
class ChatQuery(BaseModel):
    lead_id: str
    message: str
    message_type: str = "text"

class StageMoveRequest(BaseModel):
    lead_id: str
    target_stage: str
    notes: Optional[str] = None

class CreateLeadRequest(BaseModel):
    name: str
    phone: str
    channel: str = "Inbound WhatsApp"
    broker_name: Optional[str] = None
    email: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    bhk: Optional[int] = None
    area: Optional[str] = None
    temperature: Optional[str] = "warm"
    initial_message: Optional[str] = None

class QualifyRequest(BaseModel):
    lead_id: str
    budget_min: int
    budget_max: int
    bhk: int
    possession_year: int
    loan_needed: bool

class CostSheetRequest(BaseModel):
    lead_id: str
    unit_id: str

class SiteVisitRequest(BaseModel):
    lead_id: str
    unit_id: str
    slot: str
    sales_rep: Optional[str] = "Praveen Kumar"

class PostVisitRequest(BaseModel):
    lead_id: str
    feedback: str

class BookingFinalizeRequest(BaseModel):
    lead_id: str
    agreed_price: int

class DiscountSubmit(BaseModel):
    lead_id: str
    unit_id: str
    requested_pct: float

class DailySiteSubmit(BaseModel):
    tower: str
    engineer_name: str
    milestone: str
    percent_done: float
    labor_count: int
    material_shortage: bool
    material_notes: Optional[str] = None
    photos: List[str] = []

class TaskDecision(BaseModel):
    decider_name: str
    notes: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None

# --- REST Endpoints ---

@app.get("/api/state")
def get_system_state():
    return {
        "facts": orchestrator.facts_engine.facts,
        "inventory": orchestrator.facts_engine.inventory,
        "pending_tasks": [t.model_dump() for t in orchestrator.inbox.get_pending_tasks()],
        "leads": [l.model_dump() for l in orchestrator.sales_closer.leads.values()],
        "buyer_ledger": orchestrator.buyer_ledger,
        "audit_logs": [l.model_dump() for l in orchestrator.audit.get_all_logs()[-35:]]
    }

@app.get("/api/n8n/workflows")
def get_n8n_workflows():
    n8n_dir = os.path.join(os.path.dirname(__file__), "..", "n8n")
    flows = []
    flow_files = [
        ("sales_closer_agent.json", "Sales Closer Agent (Lead to Booking)", "Inbound WhatsApp, LangChain Agent, Safety Gate, Google Sheets & Slack"),
        ("delivery_cash_guardian.json", "Delivery & Cash Guardian (Site Watcher + Money Desk)", "Daily 7PM Cron, Delay Risk Engine, RERA 70% Escrow Certificates, Slack Double-Approval")
    ]
    for filename, display_name, summary in flow_files:
        path = os.path.join(n8n_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                flows.append({
                    "file": filename,
                    "name": data.get("name", display_name),
                    "summary": summary,
                    "node_count": len(data.get("nodes", [])),
                    "groups": [g.get("name") for g in data.get("nodeGroups", [])],
                    "nodes": [{"id": n.get("id"), "name": n.get("name"), "type": n.get("type")} for n in data.get("nodes", [])]
                })
    return {"workflows": flows}

@app.post("/api/leads/create")
def create_lead(payload: CreateLeadRequest):
    try:
        # Map channel
        channel_map = {
            "Inbound WhatsApp": ChannelSource.WHATSAPP,
            "Meta/Google Ad": ChannelSource.DIGITAL_AD,
            "Channel Partner": ChannelSource.BROKER,
            "99acres/MagicBricks": ChannelSource.PORTAL,
            "Site Walk-in": ChannelSource.WALK_IN
        }
        chan = channel_map.get(payload.channel, ChannelSource.WHATSAPP)
        lead = orchestrator.sales_closer.s1_catch_lead(
            name=payload.name,
            phone=payload.phone,
            channel=chan,
            broker_name=payload.broker_name,
            email=payload.email
        )
        if payload.budget_min or payload.budget_max or payload.bhk:
            orchestrator.sales_closer.s3_qualify_lead(
                lead_id=lead.lead_id,
                budget_min=payload.budget_min,
                budget_max=payload.budget_max,
                bhk=payload.bhk
            )
        if payload.area:
            lead.area_preference = payload.area
        if payload.temperature:
            temp_map = {"hot": LeadTemperature.HOT, "warm": LeadTemperature.WARM, "not_now": LeadTemperature.NOT_NOW}
            lead.temperature = temp_map.get(payload.temperature.lower(), LeadTemperature.WARM)
        if payload.initial_message:
            orchestrator.sales_closer.s2_process_buyer_message(lead.lead_id, payload.initial_message)
        return {"status": "SUCCESS", "lead": lead.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/move-stage")
def move_lead_stage(payload: StageMoveRequest):
    try:
        stage_enum = LeadStage(payload.target_stage.lower())
        lead = orchestrator.sales_closer.update_lead_stage(payload.lead_id, stage_enum, payload.notes)
        return {"status": "SUCCESS", "lead": lead.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/{lead_id}/qualify")
def qualify_lead_endpoint(lead_id: str, payload: QualifyRequest):
    try:
        lead = orchestrator.sales_closer.s3_qualify_lead(
            lead_id=lead_id,
            budget_min=payload.budget_min,
            budget_max=payload.budget_max,
            bhk=payload.bhk,
            possession_year=payload.possession_year,
            loan_needed=payload.loan_needed
        )
        return {"status": "SUCCESS", "lead": lead.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/{lead_id}/cost-sheet")
def send_cost_sheet(lead_id: str, payload: CostSheetRequest):
    try:
        sent, sheet, msg = orchestrator.sales_closer.s4_generate_cost_sheet(lead_id, payload.unit_id)
        return {
            "status": "SUCCESS" if sent else "HELD",
            "sent": sent,
            "cost_sheet": sheet.model_dump() if sheet else None,
            "message": msg
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/{lead_id}/book-visit")
def book_site_visit(lead_id: str, payload: SiteVisitRequest):
    try:
        visit = orchestrator.sales_closer.s5_book_site_visit(
            lead_id=lead_id,
            unit_id=payload.unit_id,
            scheduled_slot=payload.slot,
            sales_rep=payload.sales_rep or "Praveen Kumar"
        )
        return {"status": "SUCCESS", "visit": visit.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/{lead_id}/post-visit")
def post_visit_endpoint(lead_id: str, payload: PostVisitRequest):
    try:
        msg = orchestrator.sales_closer.s6_post_visit_followup(lead_id, payload.feedback)
        return {"status": "SUCCESS", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/leads/{lead_id}/finalize")
def finalize_booking(lead_id: str, payload: BookingFinalizeRequest):
    try:
        res = orchestrator.sales_closer.s9_finalize_booking(lead_id, payload.agreed_price)
        return {"status": "SUCCESS", "result": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/chat")
def handle_chat(query: ChatQuery):
    try:
        sent, reply = orchestrator.sales_closer.s2_process_buyer_message(
            lead_id=query.lead_id,
            buyer_message=query.message,
            message_type=query.message_type
        )
        lead = orchestrator.sales_closer.leads.get(query.lead_id)
        return {
            "status": "SENT" if sent else "DIVERTED_TO_APPROVAL",
            "reply": reply,
            "handover_required": lead.handover_required if lead else False,
            "handover_reason": lead.handover_reason if lead else None,
            "current_stage": lead.stage.value if lead else None,
            "chat_history": lead.chat_history if lead else []
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/request-discount")
def request_discount(payload: DiscountSubmit):
    try:
        req = orchestrator.sales_closer.s7_request_discount(
            lead_id=payload.lead_id,
            unit_id=payload.unit_id,
            requested_discount_pct=payload.requested_pct
        )
        return {"status": "SUCCESS", "request_id": req.request_id, "requires_owner": req.requires_owner}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/inbox/{task_id}/approve")
def approve_task(task_id: str, decision: TaskDecision):
    try:
        task = orchestrator.inbox.approve(task_id, decision.decider_name, decision.notes)
        return {"status": "APPROVED", "task": task.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/inbox/{task_id}/edit")
def edit_task(task_id: str, decision: TaskDecision):
    try:
        task = orchestrator.inbox.edit_and_approve(
            task_id, decision.decider_name, decision.modifications or {}, decision.notes or "Edited"
        )
        return {"status": "EDITED", "task": task.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/inbox/{task_id}/reject")
def reject_task(task_id: str, decision: TaskDecision):
    try:
        task = orchestrator.inbox.reject(task_id, decision.decider_name, decision.notes or "Rejected by decider.")
        return {"status": "REJECTED", "task": task.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/site-report")
def submit_site_report(report: DailySiteSubmit):
    try:
        res = orchestrator.site_watcher.g2_ingest_and_validate_report(
            project_id="PRJ-GH-KOKAPET",
            tower=report.tower,
            site_engineer_name=report.engineer_name,
            milestone=report.milestone,
            percent_done=report.percent_done,
            labor_count=report.labor_count,
            material_shortage=report.material_shortage,
            material_notes=report.material_notes,
            photos_submitted=report.photos
        )
        return {"status": "SUCCESS", "report_id": res.report_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/trigger-stage-demands")
def trigger_demands():
    try:
        res = orchestrator.money_desk.g7_draft_stage_letters_and_certificates(
            project_id="PRJ-GH-KOKAPET",
            tower="Tower B",
            stage_number=5,
            stage_name="Completion of 7th Floor Slab",
            demand_pct=15.0,
            buyer_ledger=orchestrator.buyer_ledger,
            photo_proof_links=["https://cdn.skyline.in/evidence/slab7_pour_completed.jpg"]
        )
        return {"status": "SUCCESS", "batch": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/", response_class=HTMLResponse)
def index():
    candidates = [
        os.path.join(os.path.dirname(__file__), "static", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "public", "index.html"),
        os.path.join(os.path.dirname(__file__), "..", "index.html"),
    ]
    for c in candidates:
        if os.path.exists(c):
            with open(c, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>Agentic AI Platform</h1><p>Visit /docs for API documentation.</p>"

# Mount static files with fallback to public/static
static_candidates = [
    os.path.join(os.path.dirname(__file__), "static"),
    os.path.join(os.path.dirname(__file__), "..", "public", "static"),
    os.path.join(os.path.dirname(__file__), "..", "public"),
]
for s_dir in static_candidates:
    if os.path.exists(s_dir):
        app.mount("/static", StaticFiles(directory=s_dir), name="static")
        break

