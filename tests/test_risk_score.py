from src.explain import load_claim, template_explanation
from src.risk_score import risk_band, risk_score


def test_missing_diagnosis_is_high_risk():
    score, reasons = risk_score({"diagnosis_code": "", "is_duplicate": 0,
                                 "days_to_submit": 5, "billed_amount": 100})
    assert score >= 0.45 and risk_band(score) == "HIGH"
    assert "Missing diagnosis code" in reasons


def test_clean_claim_is_low_risk():
    score, _ = risk_score({"diagnosis_code": "E11.9", "is_duplicate": 0,
                           "days_to_submit": 5, "billed_amount": 100})
    assert score == 0.0 and risk_band(score) == "LOW"


def test_csv_string_values_do_not_inflate_score():
    # Rows read from CSV carry strings; "0" is truthy, so is_duplicate
    # must be coerced, not tested for truthiness (C-000123: 0.10 only).
    score, reasons = risk_score({"diagnosis_code": "J06.9", "is_duplicate": "0",
                                 "days_to_submit": "2", "billed_amount": "1238.64"})
    assert score == 0.10 and risk_band(score) == "LOW"
    assert reasons == ["High billed amount — check coding"]


def test_load_claim_reads_the_requested_row(tmp_path):
    csv_path = tmp_path / "claims.csv"
    csv_path.write_text(
        "claim_id,payer,procedure_code,diagnosis_code,billed_amount,"
        "service_date,days_to_submit,is_duplicate,denied,denial_code\n"
        "C-000123,Cigna,99213,J06.9,1238.64,2025-10-13,2,0,1,CO-97\n")
    claim = load_claim("C-000123", csv_path)
    assert claim["payer"] == "Cigna" and claim["diagnosis_code"] == "J06.9"
    assert claim["billed_amount"] == 1238.64 and claim["is_duplicate"] == 0
    assert load_claim("C-999999", csv_path) is None
    assert load_claim("C-000123", tmp_path / "missing.csv") is None


def test_explanation_names_the_reason_and_fix():
    claim = {"claim_id": "C-000001", "payer": "BCBS", "diagnosis_code": "",
             "billed_amount": 250, "days_to_submit": 5, "is_duplicate": 0}
    score, reasons = risk_score(claim)
    text = template_explanation(claim, score, reasons)
    assert "Missing diagnosis code" in text
    assert "C-000001" in text
