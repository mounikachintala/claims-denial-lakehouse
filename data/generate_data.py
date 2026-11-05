"""Generate synthetic healthcare claims data. Stdlib only. No real PHI.

Deterministic with --seed so runs are reproducible. Denial is driven by
observable, explainable risk factors (missing diagnosis code, payer-rule
mismatch, duplicate, late submission) so the ML model and the rule-based
risk score can both learn / surface something real *in the synthetic data*.

Usage:
    python3 data/generate_data.py --rows 5000 --out data/raw
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

PAYERS = ["Aetna", "BCBS", "Cigna", "UnitedHealthcare", "Medicare"]
PROCEDURES = ["99213", "99214", "93000", "80053", "71046", "97110"]
DIAGNOSES = ["E11.9", "I10", "J06.9", "M54.5", "Z00.00", ""]
DENIAL_CODES = ["CO-16", "CO-97", "CO-29", "CO-11", ""]


def generate(rows: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    out = []
    base = date(2025, 1, 1)
    for i in range(1, rows + 1):
        payer = rng.choice(PAYERS)
        procedure = rng.choice(PROCEDURES)
        diagnosis = rng.choice(DIAGNOSES)
        missing_dx = diagnosis == ""
        # Risk factors a billing reviewer would recognise.
        late = rng.random() < 0.08
        duplicate = rng.random() < 0.05
        amount = round(rng.uniform(85, 1450), 2)
        service_date = base + timedelta(days=rng.randrange(0, 300))
        # Synthetic denial logic: transparent, not hidden.
        denied = missing_dx or (rng.random() < 0.10 if late else False) or (rng.random() < 0.12 if duplicate else False) or rng.random() < 0.03
        out.append({
            "claim_id": f"C-{i:06d}",
            "patient_id": f"P-{rng.randrange(1, 2000):05d}",
            "provider_id": f"PRV-{rng.randrange(1, 40):03d}",
            "payer": payer,
            "procedure_code": procedure,
            "diagnosis_code": diagnosis,
            "billed_amount": amount,
            "service_date": service_date.isoformat(),
            "days_to_submit": rng.randrange(1, 45) + (30 if late else 0),
            "is_duplicate": int(duplicate),
            "denied": int(denied),
            "denial_code": rng.choice(DENIAL_CODES) if denied else "",
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="data/raw")
    args = ap.parse_args()
    rows = generate(args.rows, args.seed)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "claims.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # Small reference files so joins are real, not invented.
    with (outdir / "payers.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["payer", "timely_filing_days"])
        for payer, days in zip(PAYERS, [90, 90, 180, 90, 365]):
            w.writerow([payer, days])
    print(f"Wrote {len(rows)} claims to {path} "
          f"({sum(r['denied'] for r in rows)} denied, synthetic)")


if __name__ == "__main__":
    main()
