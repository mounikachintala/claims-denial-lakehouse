"""Transparent, testable denial-risk logic. No Spark / no ML needed.

Used (a) as a baseline the ML model must beat, (b) as feature
definitions the ML model reuses, and (c) in unit tests. Keep the rules
explainable: a billing reviewer must be able to read a reason and act on it.
"""
from __future__ import annotations


def _to_int(value, default: int = 0) -> int:
    """Coerce CSV/string values (\"0\" is truthy in Python) to int safely."""
    try:
        return int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def risk_score(claim: dict) -> tuple[float, list[str]]:
    """Return (score 0..1, reasons). Pure function — easy to test."""
    score, reasons = 0.0, []
    if not claim.get("diagnosis_code"):
        score += 0.45
        reasons.append("Missing diagnosis code")
    if _to_int(claim.get("is_duplicate")):
        score += 0.30
        reasons.append("Possible duplicate claim")
    if _to_int(claim.get("days_to_submit")) > 30:
        score += 0.20
        reasons.append("Submitted late (>30 days)")
    if _to_float(claim.get("billed_amount")) > 1000:
        score += 0.10
        reasons.append("High billed amount — check coding")
    return min(score, 1.0), reasons


def risk_band(score: float) -> str:
    if score >= 0.45:
        return "HIGH"
    if score >= 0.20:
        return "MEDIUM"
    return "LOW"
