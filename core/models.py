from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ChannelSource(str, Enum):
    PORTAL = "99acres/MagicBricks"
    DIGITAL_AD = "Meta/Google Ad"
    BROKER = "Channel Partner"
    WALK_IN = "Site Walk-in"
    WHATSAPP = "Inbound WhatsApp"

class LeadQualification(str, Enum):
    HOT = "Hot"
    WARM = "Warm"
    NOT_NOW = "Not Now"
    DISQUALIFIED = "Disqualified"

class VarianceRiskLevel(str, Enum):
    ON_TRACK = "On Track"
    WATCH = "Watch"
    AT_RISK = "At Risk"

class ApprovalStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    EDITED = "Edited & Approved"
    REJECTED = "Rejected"
    ESCALATED = "Escalated to Owner"

class ApprovalActionType(str, Enum):
    DISCOUNT = "Discount Request"
    BOOKING_PAPERS = "Booking Papers"
    BROKER_PAYOUT = "Broker Payout"
    DELAY_WARNING_RESOLUTION = "Delay Warning Resolution"
    STAGE_COMPLETION = "Stage Completion Sign-off"
    DEMAND_LETTER_BATCH = "Stage Demand Letters Batch"
    BUYER_PROGRESS_UPDATE = "Monthly Buyer Update"
    RERA_FILING = "Quarterly RERA Update"

class LeadStage(str, Enum):
    NEW = "new"
    QUALIFYING = "qualifying"
    PRICE_SENT = "price_sent"
    VISIT_BOOKED = "visit_booked"
    VISITED = "visited"
    NEGOTIATING = "negotiating"
    BOOKING_DOCS = "booking_docs"
    BOOKED = "booked"
    LOST = "lost"

class LeadTemperature(str, Enum):
    HOT = "hot"
    WARM = "warm"
    NOT_NOW = "not_now"

# --- Problem 1: Sales Closer Models ---

class Lead(BaseModel):
    lead_id: str
    full_name: str
    phone: str
    email: Optional[str] = None
    channel: ChannelSource
    broker_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    bhk_preference: Optional[int] = None
    area_preference: Optional[str] = None
    possession_year: Optional[int] = None
    requires_home_loan: Optional[bool] = None
    qualification: LeadQualification = LeadQualification.WARM
    stage: LeadStage = LeadStage.NEW
    temperature: LeadTemperature = LeadTemperature.WARM
    matched_units: List[str] = Field(default_factory=list)
    agent_touchpoints: int = 0
    qualifying_actions: List[str] = Field(default_factory=list)
    opted_out: bool = False
    visit_slot: Optional[str] = None
    next_followup_date: Optional[str] = None
    handover_required: bool = False
    handover_reason: Optional[str] = None
    last_buyer_message: Optional[str] = None
    last_agent_reply: Optional[str] = None
    last_contact: Optional[str] = None
    chat_history: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

class CostSheet(BaseModel):
    sheet_id: str
    unit_id: str
    unit_number: str
    tower: str
    bhk: int
    super_builtup_sqft: int
    carpet_sqft: int
    base_price: int
    amenities_charges: int
    gst_amount: int
    car_parking_charge: int
    all_inclusive_total: int
    dated: str
    rera_number: str

class SiteVisitBooking(BaseModel):
    visit_id: str
    lead_id: str
    buyer_name: str
    unit_interested: str
    scheduled_slot: str
    sales_rep_assigned: str
    confirmed: bool = True
    executive_brief: Dict[str, Any]

class DiscountRequest(BaseModel):
    request_id: str
    lead_id: str
    buyer_name: str
    unit_id: str
    all_inclusive_total: int
    requested_discount_pct: float
    discount_amount: int
    net_payable: int
    sales_head_limit_pct: float = 2.0
    requires_owner: bool = False
    buyer_brief: Dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None

class BookingAgreementDraft(BaseModel):
    draft_id: str
    lead_id: str
    buyer_name: str
    unit_id: str
    agreed_price: int
    booking_token_paid: int
    rera_registration_number: str
    statutory_handover_date: str
    clauses_verified: bool = True
    status: ApprovalStatus = ApprovalStatus.PENDING

class BrokerCommissionRecord(BaseModel):
    record_id: str
    broker_name: str
    booking_id: str
    unit_id: str
    sale_value: int
    commission_pct: float = 2.0
    commission_amount: int
    helped_close_verified: bool
    status: ApprovalStatus = ApprovalStatus.PENDING

# --- Problem 2: Delivery & Cash Guardian Models ---

class SpotPhotoVerification(BaseModel):
    spot_name: str
    photo_received: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = None

class DailySiteReport(BaseModel):
    report_id: str
    project_id: str
    tower: str
    date: str
    site_engineer_name: str
    current_milestone: str
    percent_completed: float
    laborers_on_site: int
    material_shortage: bool = False
    material_notes: Optional[str] = None
    spot_photos: List[SpotPhotoVerification] = Field(default_factory=list)
    submitted_at: datetime = Field(default_factory=datetime.now)

class ScheduleVariance(BaseModel):
    tower: str
    current_stage: str
    planned_completion_date: str
    actual_projected_date: str
    days_behind: int
    risk_level: VarianceRiskLevel
    root_cause: Optional[str] = None
    affected_milestone_demands: List[str] = Field(default_factory=list)

class StageDemandLetter(BaseModel):
    letter_id: str
    buyer_id: str
    buyer_name: str
    unit_number: str
    stage_number: int
    stage_name: str
    amount_due: int
    due_date: str
    photo_proof_links: List[str]
    engineer_confirmed: bool = True
    finance_head_approved: bool = False
    sent_to_buyer: bool = False
    paid_status: bool = False

class RERAAccountCertificatePack(BaseModel):
    pack_id: str
    project_id: str
    stage_name: str
    work_completed_pct: float
    amount_to_withdraw: int
    form1_engineer_certified: bool = False
    form2_architect_certified: bool = False
    form3_ca_certified: bool = False
    all_signed: bool = False

class BuyerProgressUpdate(BaseModel):
    update_id: str
    month: str
    tower: str
    percent_done: float
    key_achievements: List[str]
    photo_urls: List[str]
    next_stage_target: str
    approved_by_project_head: bool = False

# --- Governance & Approvals ---

class ApprovalTask(BaseModel):
    task_id: str
    action_type: ApprovalActionType
    target_role: str  # Sales Head, Finance Head, Project Head, Owner
    summary: str
    details: Dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision_notes: Optional[str] = None
    decided_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None

class AuditLogEntry(BaseModel):
    log_id: str
    actor: str  # e.g., "Agent:SalesCloser", "Agent:Guardian", "User:SalesHead"
    action: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
