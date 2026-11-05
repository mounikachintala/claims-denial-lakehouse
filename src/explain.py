"""GenAI explanation: LLM prompt + safe template fallback.

Rules: synthetic data only, no PHI, never invent a payer rule.
The LLM only rephrases the *observed* risk factors + denial code into
plain English and a suggested fix. A human reviews the queue before
any claim is changed. If no LLM endpoint is configured, use the template.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from .risk_score import risk_band, risk_score


def load_claim(claim_id: str, csv_path: str | Path) -> dict | None:
    """Load one claim from the generated CSV, with numeric fields typed.

    Returns None when the file or claim is missing, so the caller can
    say so instead of explaining a different, hardcoded claim.
    """
    path = Path(csv_path)
    if not path.exists():
        return None
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row.get("claim_id") == claim_id:
                claim = dict(row)
                claim["billed_amount"] = float(claim["billed_amount"] or 0)
                claim["days_to_submit"] = int(float(claim["days_to_submit"] or 0))
                claim["is_duplicate"] = int(float(claim["is_duplicate"] or 0))
                return claim
    return None


def build_prompt(claim: dict, score: float, reasons: list[str]) -> str:
    return (
        "You are a billing assistant. Explain in 2 short sentences, in plain "
        "English, why this synthetic health-insurance claim may be denied, "
        "using ONLY these facts. Do not invent payer rules or amounts.\n\n"
        f"Claim {claim.get('claim_id')}, payer {claim.get('payer')}, "
        f"procedure {claim.get('procedure_code')}, "
        f"diagnosis '{claim.get('diagnosis_code') or 'missing'}', "
        f"billed ${claim.get('billed_amount')}, risk score {score:.2f} "
        f"({risk_band(score)}), risk factors: {', '.join(reasons) or 'none'}.\n"
        "End with one suggested fix, e.g. 'Add the diagnosis code and resubmit.'"
    )


def template_explanation(claim: dict, score: float, reasons: list[str]) -> str:
    reason = "; ".join(reasons) if reasons else "no risk factors found"
    fix = "Add the missing diagnosis code and check payer rules, then resubmit." \
        if not claim.get("diagnosis_code") else \
        "Review the flagged factors with the coder before submitting."
    return (f"Claim {claim.get('claim_id')} ({claim.get('payer')}) has a "
            f"{risk_band(score)} denial risk ({score:.2f}) because: {reason}. "
            f"Suggested fix: {fix}")


def explain(claim: dict) -> str:
    score, reasons = risk_score(claim)
    # Databricks Foundation Model APIs / OpenAI-compatible endpoint goes here
    # when DATABRICKS_TOKEN + LLM_ENDPOINT are set. Until then, template.
    if os.getenv("LLM_ENDPOINT"):
        return f"[LLM prompt — send to {os.getenv('LLM_ENDPOINT')}]\n{build_prompt(claim, score, reasons)}"
    return template_explanation(claim, score, reasons)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--claim-id", default="C-000001")
    ap.add_argument("--csv", default="data/raw/claims.csv",
                    help="Generated claims CSV to read the claim from "
                         "(run data/generate_data.py first).")
    args = ap.parse_args()
    claim = load_claim(args.claim_id, args.csv)
    if claim is None:
        print(f"Claim {args.claim_id} not found in {args.csv}. "
              f"Run: python3 data/generate_data.py --rows 5000 --out data/raw")
        raise SystemExit(1)
    print(explain(claim))
