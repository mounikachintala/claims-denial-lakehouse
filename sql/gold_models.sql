-- Gold models: Spark SQL. Run after Bronze -> Silver, on Databricks.
-- All business logic lives here so analysts can read / audit it in SQL.

-- 1. Features: one row per claim, with explainable risk flags.
CREATE OR REPLACE TABLE gold.claim_features AS
SELECT
  claim_id, patient_id, provider_id, payer,
  procedure_code, diagnosis_code, billed_amount, service_date,
  days_to_submit, is_duplicate, denied, denial_code,
  CASE WHEN COALESCE(diagnosis_code, '') = '' THEN 1 ELSE 0 END AS missing_dx,
  CASE WHEN days_to_submit > 30 THEN 1 ELSE 0 END AS late_submission,
  CASE WHEN billed_amount > 1000 THEN 1 ELSE 0 END AS high_amount
FROM silver.claims_clean;

-- 2. Review queue: what billing staff work first. Highest risk first.
--    denial_risk_score here is the transparent rule score; join the
--    MLflow model score in production and compare the two.
CREATE OR REPLACE TABLE gold.review_queue AS
SELECT
  *,
  (missing_dx * 0.45 + is_duplicate * 0.30 + late_submission * 0.20 + high_amount * 0.10) AS denial_risk_score,
  CASE
    WHEN (missing_dx * 0.45 + is_duplicate * 0.30 + late_submission * 0.20 + high_amount * 0.10) >= 0.45 THEN 'HIGH'
    WHEN (missing_dx * 0.45 + is_duplicate * 0.30 + late_submission * 0.20 + high_amount * 0.10) >= 0.20 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS risk_band
FROM gold.claim_features
WHERE missing_dx = 1 OR is_duplicate = 1 OR late_submission = 1;

-- 3. Payer summary: the business KPI view for a dashboard.
CREATE OR REPLACE TABLE gold.denial_summary_by_payer AS
SELECT
  payer,
  COUNT(*) AS total_claims,
  SUM(denied) AS denied_claims,
  ROUND(100.0 * SUM(denied) / COUNT(*), 1) AS denial_rate_pct,
  ROUND(SUM(CASE WHEN denied = 1 THEN billed_amount ELSE 0 END), 2) AS denied_amount_at_risk
FROM gold.claim_features
GROUP BY payer
ORDER BY denial_rate_pct DESC;
