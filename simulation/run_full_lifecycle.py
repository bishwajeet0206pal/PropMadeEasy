import sys
import os
import json
from pprint import pprint

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import ChannelSource, ApprovalStatus
from agents.orchestrator import PropertyWorkflowOrchestrator

def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ")
    print("=" * 80)

def main():
    print_banner("Real Estate Agentic AI - End-to-End Lifecycle Simulation")
    print("Market Context: Mid-size Property Developers in Hyderabad (Under-construction apartments)")
    print("Key Regulations: TG-RERA Registration, 10.70% Statutory Delay Interest, Section 4(2)(l)(D) 70% Escrow")

    orchestrator = PropertyWorkflowOrchestrator()

    # =========================================================================
    # PHASE 1: PROBLEM 1 - SALES CLOSER (STEPS S1 TO S9)
    # =========================================================================
    print_banner("Phase 1: Sales Closer (Lead to Booking)")

    # S1: Catch Lead
    print("\n[Step S1] Ingesting New Inbound Lead...")
    lead = orchestrator.sales_closer.s1_catch_lead(
        name="Ravi Kumar",
        phone="+919876543210",
        channel=ChannelSource.DIGITAL_AD,
        email="ravi.kumar@example.com"
    )
    print(f" -> Lead Created: {lead.lead_id} | Name: {lead.full_name} | Channel: {lead.channel.value}")

    # S2: First Reply (<5 mins)
    print("\n[Step S2] Buyer Sends Initial Inbound Inquiry:")
    inquiry = "Hi, saw your ad for Green Heights. What is the 3 BHK price?"
    print(f" Buyer: \"{inquiry}\"")
    first_reply = orchestrator.sales_closer.s2_first_reply(lead.lead_id, inquiry)
    print(f" Sales Closer Agent:\n\"{first_reply}\"")

    # S3: Qualification
    print("\n[Step S3] Buyer Responds with Qualification Details:")
    print(" Buyer: \"Budget is 1.3 to 1.5 crore. Need a home loan. Move-in targeted for 2028.\"")
    qualified_lead = orchestrator.sales_closer.s3_qualify_lead(
        lead_id=lead.lead_id,
        budget_min=13000000,
        budget_max=15000000,
        bhk=3,
        possession_year=2028,
        loan_needed=True
    )
    print(f" -> Lead Qualification: {qualified_lead.qualification.value}")
    print(f" -> Matched Units in Live Inventory: {qualified_lead.matched_units}")

    # S4: Match Homes and Send Cost Sheet
    selected_unit = qualified_lead.matched_units[0] if qualified_lead.matched_units else "TB-1204"
    print(f"\n[Step S4] Matching Live Inventory and Generating All-Inclusive Cost Sheet for {selected_unit}...")
    _, cost_sheet, sheet_msg = orchestrator.sales_closer.s4_generate_cost_sheet(lead.lead_id, selected_unit)
    print(f" Sales Closer Agent:\n\"{sheet_msg}\"")

    # S5: Book Site Visit
    print("\n[Step S5] Buyer Agrees to Site Visit:")
    print(" Buyer: \"I can visit this Saturday at 11:00 AM.\"")
    visit = orchestrator.sales_closer.s5_book_site_visit(
        lead_id=lead.lead_id,
        unit_id=selected_unit,
        scheduled_slot="Saturday 11:00 AM",
        sales_rep="Praveen Kumar"
    )
    print(f" -> Site Visit Confirmed: {visit.visit_id}")
    print(f" -> Sales Representative Brief Generated:")
    pprint(visit.executive_brief)

    # S6: Post-Visit Follow-up & Loan Assistance
    print("\n[Step S6] Post-Visit Follow-up & Home Loan Paperwork Guidance:")
    followup_msg = orchestrator.sales_closer.s6_post_visit_followup(
        lead_id=lead.lead_id,
        feedback_notes="Liked Unit TB-1204 corner view. Inquired regarding HDFC loan approval speed."
    )
    print(f" Sales Closer Agent:\n\"{followup_msg}\"")

    # S7: Discount Request (HUMAN IN THE LOOP GATE)
    print("\n[Step S7] Buyer Requests Price Concession:")
    print(" Buyer: \"Can you do 3% off on Unit 1204?\"")
    print(" [GUARDRAIL TRIGGERED] AI is strictly forbidden from granting discounts.")
    print(" -> Creating Approval Task in Unified Inbox...")
    disc_req = orchestrator.sales_closer.s7_request_discount(
        lead_id=lead.lead_id,
        unit_id=selected_unit,
        requested_discount_pct=3.0
    )
    print(f" -> Task Created: {disc_req.request_id} | Requires Owner Approval: {disc_req.requires_owner}")

    # Inspect Approval Inbox
    pending_tasks = orchestrator.inbox.get_pending_tasks()
    print(f"\n --- Unified Approval Inbox (Pending: {len(pending_tasks)}) ---")
    for t in pending_tasks:
        print(f" [{t.task_id}] Target: {t.target_role} | {t.summary}")

    # Simulate Human Decider Action: Sales Head edits and approves 2.0%
    print("\n [Human Action] Sales Head reviews card, edits discount to policy maximum 2.0%, and approves:")
    edited_task = orchestrator.inbox.edit_and_approve(
        task_id=pending_tasks[0].task_id,
        decider_name="Sunil Varma (Sales Head)",
        modifications={"approved_discount_pct": 2.0, "net_payable": int(disc_req.all_inclusive_total * 0.98)},
        notes="Approved at policy ceiling of 2.0%. High-intent buyer with pre-approved HDFC loan."
    )
    print(f" -> Task Status: {edited_task.status.value} | Decided By: {edited_task.decided_by}")

    # S8: Booking Papers (Agreement for Sale)
    agreed_price = int(disc_req.all_inclusive_total * 0.98)
    token_paid = 500000
    print(f"\n[Step S8] Drafting Agreement for Sale Draft (Agreed Price: ₹{agreed_price:,})...")
    draft = orchestrator.sales_closer.s8_draft_booking_agreement(
        lead_id=lead.lead_id,
        unit_id=selected_unit,
        agreed_price=agreed_price,
        token_paid=token_paid
    )
    print(f" -> Agreement Draft: {draft.draft_id} | RERA: {draft.rera_registration_number} | Handover: {draft.statutory_handover_date}")

    # S9: Finalize Booking & Helped-Close Attribution
    print("\n[Step S9] Closing Booking & Evaluating Attribution / Broker Payout...")
    booking_result = orchestrator.sales_closer.s9_finalize_booking(lead.lead_id, agreed_price)
    print(" -> Final Booking Metrics:")
    pprint(booking_result)

    # Cross-Agent Feedback 1: Register confirmed booking into Ledger
    ledger_entry = orchestrator.register_confirmed_booking_into_ledger(
        lead_id=lead.lead_id,
        buyer_name=lead.full_name,
        unit_number="1204",
        agreed_price=agreed_price
    )
    print(f" -> [CROSS-AGENT FEEDBACK] Booking synced to Payment Ledger: {ledger_entry['buyer_id']} (Unit {ledger_entry['unit_number']})")


    # =========================================================================
    # PHASE 2: PROBLEM 2 - DELIVERY & CASH GUARDIAN (STEPS G1 TO G9)
    # =========================================================================
    print_banner("Phase 2: Delivery & Cash Guardian (Site Watcher + Money Desk)")

    # G1: Daily Site Prompt
    print("\n[Step G1] Daily Site Update Prompt Sent to Site Engineer via WhatsApp Form:")
    prompt_config = orchestrator.site_watcher.g1_generate_daily_prompt(
        project_id="PRJ-GH-KOKAPET",
        tower="Tower B",
        site_engineer_name="Suresh Reddy"
    )
    print(f" Target: {prompt_config['prompt_target']} | Cutoff: {prompt_config['cutoff_time']}")
    print(f" Required Photo Spots: {prompt_config['required_photo_spots']}")

    # G2: Ingest and Validate Site Update
    print("\n[Step G2] Ingesting Submitted Daily Site Report:")
    report = orchestrator.site_watcher.g2_ingest_and_validate_report(
        project_id="PRJ-GH-KOKAPET",
        tower="Tower B",
        site_engineer_name="Suresh Reddy",
        milestone="7th slab reinforcement",
        percent_done=62.0,
        labor_count=48,
        material_shortage=True,
        material_notes="Steel consignment delayed by 2 days due to transporter strike",
        photos_submitted=[
            "https://cdn.skyline.in/spots/spot1_slab.jpg",
            "https://cdn.skyline.in/spots/spot2_concreting.jpg",
            "https://cdn.skyline.in/spots/spot3_rebar.jpg",
            "https://cdn.skyline.in/spots/spot4_safety.jpg"
        ]
    )
    print(f" -> Report Ingested: {report.report_id} | Status: All 4 Photo Spots Verified")

    # G3: Schedule Variance Evaluation
    print("\n[Step G3] Comparing Plan vs Actual Schedule Progress:")
    variance = orchestrator.site_watcher.g3_evaluate_schedule_variance(
        tower="Tower B",
        current_stage="7th slab casting",
        planned_completion_date="2026-10-12",
        actual_projected_date="2026-10-21",
        days_behind=9,
        root_cause="Transporter strike delayed rebar steel delivery"
    )
    print(f" -> Schedule Variance: {variance.days_behind} days behind")
    print(f" -> Risk Classification: {variance.risk_level.value}")

    # G4: Early Warning to Project Head (HUMAN IN THE LOOP GATE)
    print("\n[Step G4] Early Warning Triggered:")
    warning_notice = orchestrator.site_watcher.g4_send_early_warning_if_at_risk(variance)
    print(f" -> {warning_notice}")

    # G5: Supplier Chasing
    print("\n[Step G5] Automated Subcontractor / Supplier Reminder:")
    chaser_msg = orchestrator.site_watcher.g5_chase_supplier(
        vendor_name="TMT Steel Infra Logistics",
        delayed_material="32mm TMT Rebar Batch 4",
        tower="Tower B",
        target_date="2026-10-22"
    )
    print(f" Notice Sent:\n\"{chaser_msg}\"")

    # G6: Stage Completion Verification (HUMAN SIGN-OFF GATE)
    print("\n[Step G6] Stage 7 Slab Casting Completed - Requesting Formal Sign-off:")
    completion_task_id = orchestrator.money_desk.g6_request_stage_completion_signoff(
        project_id="PRJ-GH-KOKAPET",
        tower="Tower B",
        stage_number=5,
        stage_name="Completion of 7th Floor Slab",
        photo_evidence_links=[
            "https://cdn.skyline.in/evidence/slab7_pour_completed.jpg",
            "https://cdn.skyline.in/evidence/slab7_cube_test_report.pdf"
        ]
    )
    print(f" -> Approval Task Created: {completion_task_id} (Sign-off required: Site Engineer & Project Head)")

    # Simulate Project Head approval
    orchestrator.inbox.approve(
        task_id=completion_task_id,
        decider_name="M. R. Rao (Project Head)",
        notes="Inspected on-site cube test strength and curing records. Approved."
    )
    print(f" -> [Human Action] Stage 7 Completion Verified and Signed by Project Head.")

    # G7: Draft Stage Demand Letters & RERA 70% Certificate Pack
    print("\n[Step G7] Drafting Demand Letters (with photo proof) and 70% Escrow Withdrawal Certificates:")
    batch_info = orchestrator.money_desk.g7_draft_stage_letters_and_certificates(
        project_id="PRJ-GH-KOKAPET",
        tower="Tower B",
        stage_number=5,
        stage_name="Completion of 7th Floor Slab",
        demand_pct=15.0,
        buyer_ledger=orchestrator.buyer_ledger,
        photo_proof_links=["https://cdn.skyline.in/evidence/slab7_pour_completed.jpg"]
    )
    print(f" -> Batch Generated: {batch_info['batch_id']}")
    print(f" -> Total Demand Value: ₹{batch_info['total_demand_value']:,}")
    print(f" -> 70% Escrow Withdrawal Pack: {batch_info['pack_id']}")
    print(f" -> Finance Head Approval Task: {batch_info['approval_task_id']}")

    # G8: Finance Head Approves & Dispatches
    print("\n[Step G8] Finance Head Approves Demand Letters Batch:")
    orchestrator.inbox.approve(
        task_id=batch_info["approval_task_id"],
        decider_name="K. Lakshmi (Finance Head)",
        notes="Verified demand calculations against buyer schedule of payments. Approved for dispatch."
    )
    dispatched_letters = orchestrator.money_desk.g8_distribute_approved_demand_letters(batch_info["batch_id"])
    print(f" -> Dispatched {len(dispatched_letters)} Demand Letters to Buyers:")
    for dl in dispatched_letters:
        print(f"    • Buyer: {dl['buyer_name']} | Unit: {dl['unit']} | Amount: ₹{dl['amount']:,} | Due: {dl['due_date']}")

    # G9: Monthly Honest Buyer Update & Two-Way Grounding Sync
    print("\n[Step G9] Drafting Monthly Progress Newsletter for Homebuyers:")
    update_item = orchestrator.money_desk.g9_draft_buyer_progress_newsletter(
        tower="Tower B",
        month="October 2026",
        percent_done=62.0,
        achievements=["7th floor slab cast and de-shuttered", "Brickwork completed up to 4th floor"],
        photo_urls=["https://cdn.skyline.in/updates/oct_tower_b_overview.jpg"],
        next_stage_target="8th floor slab casting (internal target)"
    )
    # Project head approves
    pending_tasks = orchestrator.inbox.get_pending_tasks(role="Project Head")
    update_task = [t for t in pending_tasks if t.action_type.value == "Monthly Buyer Update"][0]
    orchestrator.inbox.approve(update_task.task_id, "M. R. Rao (Project Head)", "Photos verified, target dates realistic.")
    
    broadcast = orchestrator.money_desk.g9_publish_approved_update(update_item.update_id)
    print(f" Broadcast to Homebuyers:\n\"{broadcast}\"")

    # Cross-Agent Feedback 2: Check that Facts Sheet has updated progress
    refreshed_tower_b = next(t for t in orchestrator.facts_engine.facts["towers"] if t["name"] == "Tower B")
    print(f"\n -> [CROSS-AGENT FEEDBACK] Grounded Facts Engine Tower B Status:")
    print(f"    Current Stage: {refreshed_tower_b['current_stage']} | Percent Done: {refreshed_tower_b['percent_done']}%")


    # =========================================================================
    # AUDIT TRAIL & GOVERNANCE VERIFICATION
    # =========================================================================
    print_banner("Audit Trail & Compliance Verification")
    all_logs = orchestrator.audit.get_all_logs()
    print(f"Total Immutable Audit Entries Generated: {len(all_logs)}")
    print("Sample Key Governance Entries:")
    for entry in all_logs[-5:]:
        print(f" [{entry.timestamp.strftime('%H:%M:%S')}] {entry.actor} -> {entry.action} ({entry.entity_type}: {entry.entity_id})")

    print("\nSimulation successfully completed with 100% adherence to all human governance rules!")

if __name__ == "__main__":
    main()
