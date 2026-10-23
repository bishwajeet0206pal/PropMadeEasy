import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import ChannelSource, VarianceRiskLevel
from core.validator import ReplyValidator
from agents.orchestrator import PropertyWorkflowOrchestrator

def test_reply_validator_rera_and_price_checks():
    rera = "P02400008899"
    allowed_prices = [9817500, 12757500, 13177500]

    # Valid reply (exact all-in price matching inventory)
    valid_text = f"Unit 804 is ₹12,757,500 all-in under TG-RERA {rera}. When would you like to visit?"
    passed, reasons = ReplyValidator.validate_reply(valid_text, False, rera, allowed_prices, True)
    assert passed, f"Expected pass, got: {reasons}"

    # Planted error 1: Missing RERA with price
    bad_rera = "Unit 804 is ₹12,757,500 all-in. No hidden fees."
    passed, reasons = ReplyValidator.validate_reply(bad_rera, False, rera, allowed_prices, True)
    assert not passed
    assert any("RERA" in r for r in reasons)

    # Planted error 2: Unapproved Price
    bad_price = f"Special unit at ₹7,500,000 under TG-RERA {rera}."
    passed, reasons = ReplyValidator.validate_reply(bad_price, False, rera, allowed_prices, True)
    assert not passed
    assert any("does not match any live inventory" in r for r in reasons)

    # Planted error 3: Banned Commitment Phrase
    bad_phrase = f"100% assured possession by next Diwali under TG-RERA {rera}."
    passed, reasons = ReplyValidator.validate_reply(bad_phrase, False, rera, allowed_prices, True)
    assert not passed
    assert any("Prohibited" in r or "prohibited" in r for r in reasons)

def test_non_text_fallback_handling():
    orch = PropertyWorkflowOrchestrator()
    lead = orch.sales_closer.s1_catch_lead("Sanjay Rao", "+919876500001", ChannelSource.DIGITAL_AD)
    sent, reply = orch.sales_closer.s2_process_buyer_message(lead.lead_id, "", message_type="audio")
    assert sent is True
    assert "text messages" in reply
    assert "sales executive has been notified" in reply

def test_atomic_lead_qualification_update():
    orch = PropertyWorkflowOrchestrator()
    lead = orch.sales_closer.s1_catch_lead("Meera Reddy", "+919876500002", ChannelSource.DIGITAL_AD)
    
    # Step 1: Set budget
    orch.sales_closer.s3_qualify_lead(lead.lead_id, budget_min=10000000, budget_max=13000000)
    assert lead.budget_max == 13000000

    # Step 2: Set loan needed without re-passing budget (SC-I3 non-destructive test)
    orch.sales_closer.s3_qualify_lead(lead.lead_id, loan_needed=True)
    assert lead.budget_max == 13000000
    assert lead.requires_home_loan is True

def test_deterministic_schedule_variance_calculation():
    orch = PropertyWorkflowOrchestrator()
    var = orch.site_watcher.g3_compute_schedule_variance_deterministic(
        tower="Tower B",
        stage_name="7th Floor Slab",
        planned_start_date="2026-08-01",
        planned_end_date="2026-10-15",
        rera_possession_date="2028-03-31",
        actual_percent_completed=62.0,
        blockers_count=1
    )
    assert var.days_behind > 0
    assert var.risk_level in (VarianceRiskLevel.WATCH, VarianceRiskLevel.AT_RISK)

def test_deterministic_demand_letter_math_and_repeat_billing_protection():
    orch = PropertyWorkflowOrchestrator()
    
    # Batch 1
    batch = orch.money_desk.g7_draft_stage_letters_and_certificates(
        project_id="PRJ-GH-KOKAPET",
        tower="Tower B",
        stage_number=5,
        stage_name="Completion of 7th Floor Slab",
        demand_pct=15.0,
        buyer_ledger=orch.buyer_ledger,
        photo_proof_links=["https://cdn.skyline.in/photos/slab7.jpg"]
    )
    assert batch["total_demand_value"] > 0
    
    # Approve and distribute (marks milestone as demanded GD-I2)
    orch.inbox.approve(batch["approval_task_id"], "Finance Head")
    orch.money_desk.g8_distribute_approved_demand_letters(batch["batch_id"], milestone_key=batch["milestone_key"])
    
    # Attempt repeat billing on same milestone (must raise error)
    try:
        orch.money_desk.g7_draft_stage_letters_and_certificates(
            project_id="PRJ-GH-KOKAPET",
            tower="Tower B",
            stage_number=5,
            stage_name="Completion of 7th Floor Slab",
            demand_pct=15.0,
            buyer_ledger=orch.buyer_ledger,
            photo_proof_links=["https://cdn.skyline.in/photos/slab7.jpg"]
        )
        assert False, "Should have thrown repeat billing protection error (GD-I2)"
    except ValueError as e:
        assert "already been demanded" in str(e)

if __name__ == "__main__":
    test_reply_validator_rera_and_price_checks()
    test_non_text_fallback_handling()
    test_atomic_lead_qualification_update()
    test_deterministic_schedule_variance_calculation()
    test_deterministic_demand_letter_math_and_repeat_billing_protection()
    print("All hardened governance & validation tests PASSED cleanly!")
