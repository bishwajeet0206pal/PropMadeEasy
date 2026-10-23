import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from core.models import (
    Lead, ChannelSource, LeadQualification, LeadStage, LeadTemperature, CostSheet, SiteVisitBooking,
    DiscountRequest, BookingAgreementDraft, BrokerCommissionRecord,
    ApprovalActionType, ApprovalStatus
)
from core.facts_engine import GroundedFactsEngine
from core.approval_inbox import UnifiedApprovalInbox
from core.audit import AuditLogger
from core.validator import ReplyValidator

class SalesCloserAgent:
    """
    Agent 1: Sales Closer (Level 2-3 AI Agent).
    Addresses Problem 1: Fill the project faster at lower cost.
    Fully hardened with:
    - SC-I1 Validator Gate: All outgoing text strictly validated before dispatch.
    - SC-I2 Non-text fallback handler for audio/images.
    - SC-I3 Non-destructive atomic field merging.
    - SC-I4 Price freshness enforcement.
    - SC-I5 Deduplication by message_id.
    - SC-I6 Human Approval SLA Inbox with reminders.
    """
    def __init__(self, facts_engine: GroundedFactsEngine, inbox: UnifiedApprovalInbox, audit: AuditLogger):
        self.facts_engine = facts_engine
        self.inbox = inbox
        self.audit = audit
        self.leads: Dict[str, Lead] = {}
        self.processed_message_ids: set = set()
        self.cost_sheets: Dict[str, CostSheet] = {}
        self.visits: Dict[str, SiteVisitBooking] = {}
        self.discount_requests: Dict[str, DiscountRequest] = {}
        self.booking_drafts: Dict[str, BookingAgreementDraft] = {}
        self.broker_commissions: Dict[str, BrokerCommissionRecord] = {}

    # S1: Catch the lead & deduplicate (SC-I5)
    def s1_catch_lead(
        self,
        name: str,
        phone: str,
        channel: ChannelSource,
        broker_name: Optional[str] = None,
        email: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Lead:
        if message_id and message_id in self.processed_message_ids:
            self.audit.record("Agent:SalesCloser", "SC_I5_DUPLICATE_MESSAGE_IGNORED", "Lead", phone, {"msg_id": message_id})
            # Return existing lead
            for existing in self.leads.values():
                if existing.phone == phone:
                    return existing

        if message_id:
            self.processed_message_ids.add(message_id)

        # Check existing lead by phone
        for existing in self.leads.values():
            if existing.phone == phone:
                # Merge channel if new (SC-I3 non-destructive)
                if channel.value not in existing.notes:
                    existing.notes.append(f"Additional touchpoint via {channel.value}")
                return existing

        lead_id = f"LD-{uuid.uuid4().hex[:6].upper()}"
        lead = Lead(
            lead_id=lead_id,
            full_name=name,
            phone=phone,
            email=email,
            channel=channel,
            broker_name=broker_name,
            notes=[f"Captured via {channel.value}"]
        )
        self.leads[lead_id] = lead
        self.audit.record("Agent:SalesCloser", "S1_LEAD_CAPTURED", "Lead", lead_id, {
            "name": name, "phone": phone, "channel": channel.value, "broker": broker_name
        })
        return lead

    def s2_first_reply(self, lead_id: str, buyer_message: str) -> str:
        """Convenience wrapper for initial text replies."""
        _, msg = self.s2_process_buyer_message(lead_id, buyer_message, message_type="text")
        return msg

    # S2: First reply with SC-I1 validation & SC-I2 non-text guard
    def s2_process_buyer_message(
        self,
        lead_id: str,
        buyer_message: str,
        message_type: str = "text",
        message_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Returns (sent_to_buyer: bool, message_content: str).
        If sent_to_buyer is False, the draft was diverted to Human Approval Inbox!
        """
        if message_id and message_id in self.processed_message_ids:
            return True, "Duplicate message ignored."
        if message_id:
            self.processed_message_ids.add(message_id)

        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        # Record inbound message
        lead.last_buyer_message = buyer_message
        lead.last_contact = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lead.chat_history.append({
            "sender": "buyer",
            "text": buyer_message,
            "time": datetime.now().strftime("%I:%M %p")
        })

        # Check opt-out
        if any(w in buyer_message.lower() for w in ["stop", "unsubscribe", "dont call", "don't call"]):
            lead.opted_out = True
            lead.qualification = LeadQualification.DISQUALIFIED
            lead.stage = LeadStage.LOST
            lead.temperature = LeadTemperature.NOT_NOW
            reply = "Thank you. We have recorded your preference and will not send further messages on this number."
            lead.last_agent_reply = reply
            lead.chat_history.append({
                "sender": "agent",
                "text": reply,
                "time": datetime.now().strftime("%I:%M %p")
            })
            self.audit.record("Agent:SalesCloser", "LEAD_OPTED_OUT", "Lead", lead_id, {"msg": buyer_message})
            return True, reply

        # SC-I2: Non-text fallback
        if message_type != "text":
            fallback_msg = (
                f"Hello {lead.full_name}, thank you for reaching out to Green Heights. "
                "I can only process text messages on this chat; our sales executive has been notified and will call you shortly."
            )
            lead.handover_required = True
            lead.handover_reason = f"non_text_{message_type}"
            lead.last_agent_reply = fallback_msg
            lead.chat_history.append({
                "sender": "agent",
                "text": fallback_msg,
                "time": datetime.now().strftime("%I:%M %p"),
                "escalated": True
            })
            self.inbox.create_task(
                action_type=ApprovalActionType.BUYER_PROGRESS_UPDATE,
                target_role="Sales Head",
                summary=f"Non-text inbound message ({message_type}) from {lead.full_name}",
                details={"lead_id": lead_id, "phone": lead.phone, "type": message_type}
            )
            self.audit.record("Agent:SalesCloser", "SC_I2_NON_TEXT_FALLBACK", "Lead", lead_id, {"type": message_type})
            return True, fallback_msg

        # Grounding safety check (discount, legal, dates)
        safe, reason = self.facts_engine.verify_query_safety(buyer_message)
        if not safe:
            lead.handover_required = True
            lead.handover_reason = reason
            if "discount" in buyer_message.lower():
                lead.stage = LeadStage.NEGOTIATING
            task = self.inbox.create_task(
                action_type=ApprovalActionType.DISCOUNT if "discount" in buyer_message.lower() else ApprovalActionType.BUYER_PROGRESS_UPDATE,
                target_role="Sales Head",
                summary=f"Buyer {lead.full_name} inquiry requires human authority: {reason}",
                details={"lead_id": lead_id, "buyer_name": lead.full_name, "message": buyer_message}
            )
            self.audit.record("Agent:SalesCloser", "SAFETY_ESCALATED_TO_HUMAN", "Lead", lead_id, {"reason": reason})
            escalated_reply = f"Thank you, {lead.full_name}. That request requires approval from our Sales Head ({task.task_id}). Our team will follow up directly today."
            lead.last_agent_reply = escalated_reply
            lead.chat_history.append({
                "sender": "agent",
                "text": escalated_reply,
                "time": datetime.now().strftime("%I:%M %p"),
                "escalated": True,
                "reason": reason
            })
            return True, escalated_reply

        # Draft candidate response
        rera = self.facts_engine.get_rera_details()
        fresh, _ = self.facts_engine.is_pricing_fresh()
        candidate_reply = (
            f"Hello {lead.full_name}, thank you for inquiring about {rera['project_name']}, {rera['location']}. "
            f"TG-RERA Registration No: {rera['rera_number']} (Possession target: {rera['statutory_possession']}). "
            f"We offer premium 2 & 3 BHK homes with GHMC permits. "
            f"What is your preferred budget range, move-in target, and do you require a home loan?"
        )

        # SC-I1 VALIDATOR GATE: Run validator before sending!
        allowed_prices = [u["all_inclusive_total"] for u in self.facts_engine.inventory.get("units", []) if u.get("status") == "Available"]
        is_first = (lead.agent_touchpoints == 0)
        
        valid, failures = ReplyValidator.validate_reply(
            reply=candidate_reply,
            is_first_reply=is_first,
            rera_number=rera["rera_number"],
            allowed_prices=allowed_prices,
            price_list_fresh=fresh
        )

        lead.agent_touchpoints += 1
        lead.qualifying_actions.append("first_reply_sent")

        if not valid:
            # Divert to Human Inbox! Never send invalid message to buyer!
            lead.handover_required = True
            lead.handover_reason = "unsure"
            task = self.inbox.create_task(
                action_type=ApprovalActionType.BUYER_PROGRESS_UPDATE,
                target_role="Sales Head",
                summary=f"BLOCKED OUTGOING MESSAGE: Failed safety validation for {lead.full_name}",
                details={"candidate_reply": candidate_reply, "failures": failures}
            )
            self.audit.record("Agent:SalesCloser", "SC_I1_VALIDATION_FAILED_DIVERTED", "Lead", lead_id, {
                "failures": failures, "task_id": task.task_id
            })
            return False, f"Message held for Sales Head review ({task.task_id}) due to validation checks: {'; '.join(failures)}"

        if lead.stage == LeadStage.NEW:
            lead.stage = LeadStage.QUALIFYING

        lead.last_agent_reply = candidate_reply
        lead.chat_history.append({
            "sender": "agent",
            "text": candidate_reply,
            "time": datetime.now().strftime("%I:%M %p")
        })

        self.audit.record("Agent:SalesCloser", "S2_REPLY_SENT_AND_VALIDATED", "Lead", lead_id, {
            "reply": candidate_reply
        })
        return True, candidate_reply

    # S3: Qualification with SC-I3 non-destructive update
    def s3_qualify_lead(
        self,
        lead_id: str,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        bhk: Optional[int] = None,
        possession_year: Optional[int] = None,
        loan_needed: Optional[bool] = None
    ) -> Lead:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        # Non-destructive atomic merging (SC-I3)
        if budget_min is not None: lead.budget_min = budget_min
        if budget_max is not None: lead.budget_max = budget_max
        if bhk is not None: lead.bhk_preference = bhk
        if possession_year is not None: lead.possession_year = possession_year
        if loan_needed is not None: lead.requires_home_loan = loan_needed

        if lead.budget_max and lead.budget_max >= 9500000:
            lead.qualification = LeadQualification.HOT
            lead.temperature = LeadTemperature.HOT
        elif lead.budget_max and lead.budget_max >= 8500000:
            lead.qualification = LeadQualification.WARM
            lead.temperature = LeadTemperature.WARM
        else:
            lead.qualification = LeadQualification.NOT_NOW
            lead.temperature = LeadTemperature.NOT_NOW

        if lead.stage == LeadStage.NEW:
            lead.stage = LeadStage.QUALIFYING

        matching = self.facts_engine.get_matching_available_units(bhk=lead.bhk_preference, max_budget=lead.budget_max)
        lead.matched_units = [u["unit_id"] for u in matching]
        lead.agent_touchpoints += 1
        lead.qualifying_actions.append("lead_qualified")

        self.audit.record("Agent:SalesCloser", "S3_LEAD_QUALIFIED", "Lead", lead_id, {
            "qualification": lead.qualification.value,
            "temperature": lead.temperature.value,
            "matched_units": lead.matched_units
        })
        return lead

    # S4: Match Homes and Send Cost Sheet with SC-I1 validation
    def s4_generate_cost_sheet(self, lead_id: str, unit_id: str) -> Tuple[bool, CostSheet, str]:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        fresh, reason = self.facts_engine.is_pricing_fresh()
        if not fresh:
            # SC-I4 Price list older than 24h stops quotes!
            task = self.inbox.create_task(
                action_type=ApprovalActionType.BUYER_PROGRESS_UPDATE,
                target_role="Sales Head",
                summary=f"Stale Price List Block: Cannot quote Unit {unit_id} for {lead.full_name}",
                details={"unit_id": unit_id, "reason": reason}
            )
            self.audit.record("Agent:SalesCloser", "SC_I4_STALE_PRICE_BLOCKED", "Lead", lead_id, {"reason": reason})
            return False, None, f"Price list is currently undergoing daily verification. Our sales desk will send the updated cost sheet shortly."

        unit = next((u for u in self.facts_engine.inventory.get("units", []) if u["unit_id"] == unit_id), None)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found.")

        sheet_id = f"CS-{uuid.uuid4().hex[:6].upper()}"
        sheet = CostSheet(
            sheet_id=sheet_id,
            unit_id=unit["unit_id"],
            unit_number=unit["unit_number"],
            tower=unit["tower"],
            bhk=unit["bhk"],
            super_builtup_sqft=unit["super_builtup_sqft"],
            carpet_sqft=unit["carpet_sqft"],
            base_price=unit["base_price"],
            amenities_charges=unit["amenities_charges"],
            gst_amount=unit["gst_amount"],
            car_parking_charge=self.facts_engine.inventory.get("car_parking_charge", 300000),
            all_inclusive_total=unit["all_inclusive_total"],
            dated=datetime.now().strftime("%Y-%m-%d"),
            rera_number=self.facts_engine.facts.get("rera_number", "")
        )
        self.cost_sheets[sheet_id] = sheet

        msg = (
            f"Here is your official All-Inclusive Cost Sheet for Unit {sheet.unit_number} ({sheet.tower}, {sheet.bhk} BHK):\n"
            f"• Super Built-up Area: {sheet.super_builtup_sqft} sq ft (Carpet: {sheet.carpet_sqft} sq ft)\n"
            f"• Base Price: ₹{sheet.base_price:,}\n"
            f"• Amenities & Car Parking: ₹{sheet.amenities_charges + sheet.car_parking_charge:,}\n"
            f"• Statutory GST (5%): ₹{sheet.gst_amount:,}\n"
            f"• Total All-Inclusive: ₹{sheet.all_inclusive_total:,}\n"
            f"All prices dated today under TG-RERA {sheet.rera_number}. Zero hidden infrastructure charges."
        )

        allowed_prices = []
        for u in self.facts_engine.inventory.get("units", []):
            if u.get("status") == "Available":
                allowed_prices.extend([
                    u.get("all_inclusive_total", 0),
                    u.get("base_price", 0),
                    u.get("amenities_charges", 0) + self.facts_engine.inventory.get("car_parking_charge", 300000),
                    u.get("gst_amount", 0)
                ])
        valid, failures = ReplyValidator.validate_reply(
            reply=msg,
            is_first_reply=False,
            rera_number=sheet.rera_number,
            allowed_prices=allowed_prices,
            price_list_fresh=fresh
        )

        if not valid:
            return False, sheet, f"Cost sheet held for verification: {'; '.join(failures)}"

        lead.stage = LeadStage.PRICE_SENT
        lead.agent_touchpoints += 1
        lead.qualifying_actions.append("sent_cost_sheet")
        self.audit.record("Agent:SalesCloser", "S4_COST_SHEET_SENT", "Lead", lead_id, {
            "sheet_id": sheet_id, "unit_id": unit_id, "total": sheet.all_inclusive_total
        })
        return True, sheet, msg

    # S5: Book Site Visit
    def s5_book_site_visit(self, lead_id: str, unit_id: str, scheduled_slot: str, sales_rep: str = "Praveen Kumar") -> SiteVisitBooking:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        visit_id = f"VISIT-{uuid.uuid4().hex[:6].upper()}"
        brief = {
            "lead_name": lead.full_name,
            "budget": f"₹{lead.budget_min:,} - ₹{lead.budget_max:,}" if lead.budget_min else "Not specified",
            "bhk": lead.bhk_preference,
            "loan_required": lead.requires_home_loan,
            "channel": lead.channel.value,
            "broker": lead.broker_name or "Direct",
            "unit_shortlisted": unit_id
        }
        visit = SiteVisitBooking(
            visit_id=visit_id,
            lead_id=lead_id,
            buyer_name=lead.full_name,
            unit_interested=unit_id,
            scheduled_slot=scheduled_slot,
            sales_rep_assigned=sales_rep,
            executive_brief=brief
        )
        self.visits[visit_id] = visit
        lead.stage = LeadStage.VISIT_BOOKED
        lead.visit_slot = scheduled_slot
        lead.agent_touchpoints += 1
        lead.qualifying_actions.append("scheduled_site_visit")
        self.audit.record("Agent:SalesCloser", "S5_VISIT_BOOKED", "Lead", lead_id, {
            "visit_id": visit_id, "slot": scheduled_slot
        })
        return visit

    # S6: Post-visit follow-up
    def s6_post_visit_followup(self, lead_id: str, feedback_notes: str) -> str:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        lead.stage = LeadStage.VISITED
        lead.notes.append(f"Post-visit: {feedback_notes}")
        lead.agent_touchpoints += 1
        lead.qualifying_actions.append("provided_loan_doc_kit")

        approved_banks = ", ".join(self.facts_engine.facts.get("approved_banks_for_loans", []))
        message = (
            f"Hi {lead.full_name}, thank you for visiting Green Heights! Glad you liked the site layout.\n"
            f"Our project is pre-approved for fast digital loan sanction with: {approved_banks}.\n"
            f"Pre-sanction checklist: 1. PAN & Aadhaar 2. 6-mo bank statement 3. 3-mo salary slips. "
            f"We have dedicated bank officers at site to assist you."
        )
        self.audit.record("Agent:SalesCloser", "S6_POST_VISIT_FOLLOWUP", "Lead", lead_id, {"notes": feedback_notes})
        return message

    # S7: Discount Hand-off (SC-I6 Human in the loop)
    def s7_request_discount(self, lead_id: str, unit_id: str, requested_discount_pct: float) -> DiscountRequest:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        unit = next((u for u in self.facts_engine.inventory.get("units", []) if u["unit_id"] == unit_id), None)
        if not unit:
            raise ValueError(f"Unit {unit_id} not found.")

        all_inc = unit["all_inclusive_total"]
        discount_amount = int(all_inc * (requested_discount_pct / 100.0))
        net_payable = all_inc - discount_amount
        requires_owner = requested_discount_pct > 2.0

        req_id = f"DISC-{uuid.uuid4().hex[:6].upper()}"
        target_role = "Owner" if requires_owner else "Sales Head"

        brief = {
            "buyer_name": lead.full_name,
            "unit": unit_id,
            "original_total": all_inc,
            "requested_pct": requested_discount_pct,
            "discount_value": discount_amount,
            "net_payable": net_payable,
            "channel": lead.channel.value,
            "broker": lead.broker_name or "Direct"
        }

        disc_req = DiscountRequest(
            request_id=req_id,
            lead_id=lead_id,
            buyer_name=lead.full_name,
            unit_id=unit_id,
            all_inclusive_total=all_inc,
            requested_discount_pct=requested_discount_pct,
            discount_amount=discount_amount,
            net_payable=net_payable,
            requires_owner=requires_owner,
            buyer_brief=brief
        )
        self.discount_requests[req_id] = disc_req
        lead.stage = LeadStage.NEGOTIATING
        lead.handover_required = True
        lead.handover_reason = "discount"

        self.inbox.create_task(
            action_type=ApprovalActionType.DISCOUNT,
            target_role=target_role,
            summary=f"Discount Request {requested_discount_pct}% for {lead.full_name} on {unit_id} (Net: ₹{net_payable:,})",
            details=brief
        )
        self.audit.record("Agent:SalesCloser", "S7_DISCOUNT_HANDOFF_TO_HUMAN", "Lead", lead_id, {
            "req_id": req_id, "pct": requested_discount_pct, "role": target_role
        })
        return disc_req

    # S8: Booking Papers Draft
    def s8_draft_booking_agreement(self, lead_id: str, unit_id: str, agreed_price: int, token_paid: int) -> BookingAgreementDraft:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        draft_id = f"AGR-{uuid.uuid4().hex[:6].upper()}"
        rera = self.facts_engine.get_rera_details()
        draft = BookingAgreementDraft(
            draft_id=draft_id,
            lead_id=lead_id,
            buyer_name=lead.full_name,
            unit_id=unit_id,
            agreed_price=agreed_price,
            booking_token_paid=token_paid,
            rera_registration_number=rera["rera_number"],
            statutory_handover_date=rera["statutory_possession"],
            clauses_verified=True
        )
        self.booking_drafts[draft_id] = draft
        lead.stage = LeadStage.BOOKING_DOCS
        lead.handover_required = True
        lead.handover_reason = "booking_papers"

        self.inbox.create_task(
            action_type=ApprovalActionType.BOOKING_PAPERS,
            target_role="Sales Head",
            summary=f"Review Agreement for Sale: {lead.full_name} ({unit_id}, Agreed: ₹{agreed_price:,})",
            details={"draft_id": draft_id, "agreed_price": agreed_price, "token_paid": token_paid}
        )
        self.audit.record("Agent:SalesCloser", "S8_BOOKING_PAPERS_DRAFTED", "Lead", lead_id, {"draft_id": draft_id})
        return draft

    # S9: Finalize Booking & Attribution
    def s9_finalize_booking(self, lead_id: str, agreed_price: int) -> Dict[str, Any]:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        helped_close = lead.agent_touchpoints >= 2 and len(lead.qualifying_actions) >= 2
        broker_record = None

        if lead.channel == ChannelSource.BROKER and lead.broker_name:
            rec_id = f"COMM-{uuid.uuid4().hex[:6].upper()}"
            comm_amount = int(agreed_price * 0.02)
            broker_record = BrokerCommissionRecord(
                record_id=rec_id,
                broker_name=lead.broker_name,
                booking_id=f"BKG-{lead.lead_id}",
                unit_id=lead.matched_units[0] if lead.matched_units else "TBD",
                sale_value=agreed_price,
                commission_pct=2.0,
                commission_amount=comm_amount,
                helped_close_verified=helped_close
            )
            self.broker_commissions[rec_id] = broker_record

            self.inbox.create_task(
                action_type=ApprovalActionType.BROKER_PAYOUT,
                target_role="Finance Head",
                summary=f"Broker Commission Payout: ₹{comm_amount:,} to {lead.broker_name} for Booking {lead.full_name}",
                details={"record_id": rec_id, "broker": lead.broker_name, "commission": comm_amount}
            )

        lead.stage = LeadStage.BOOKED
        lead.handover_required = False

        self.audit.record("Agent:SalesCloser", "S9_BOOKING_FINALIZED", "Lead", lead_id, {
            "agreed_price": agreed_price, "helped_close": helped_close
        })

        return {
            "lead_id": lead_id,
            "buyer_name": lead.full_name,
            "sale_value": agreed_price,
            "helped_close_attributed": helped_close,
            "broker_payout_scheduled": broker_record.commission_amount if broker_record else 0
        }

    def update_lead_stage(self, lead_id: str, new_stage: LeadStage, notes: Optional[str] = None) -> Lead:
        lead = self.leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")
        old_stage = lead.stage
        lead.stage = new_stage
        if notes:
            lead.notes.append(f"Bucket moved from {old_stage.value} to {new_stage.value}: {notes}")
        else:
            lead.notes.append(f"Bucket moved from {old_stage.value} to {new_stage.value}")
        self.audit.record("Agent:SalesCloser", "LEAD_STAGE_MOVED", "Lead", lead_id, {
            "from": old_stage.value, "to": new_stage.value
        })
        return lead
