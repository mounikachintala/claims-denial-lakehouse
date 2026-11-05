# Claims Denial Lakehouse — PySpark + Databricks + SQL + AI + CI/CD

**Personal portfolio project. Synthetic data only. No real PHI, no employer data.**

## Business problem (say this first in an interview)

A clinic / provider submits health-insurance claims to payers. Some claims are
denied — missing codes, wrong payer rules, duplicate or late submission.
A denial means delayed payment, rework by billing staff, and cash-flow risk.

**Goal:** catch risky claims *before* submission, explain *why* in plain
English, and give billing staff a prioritised review queue — so they fix the
claim once, instead of reworking a denial later.

**What success looks like (on synthetic data only):** a daily review queue
(`gold.review_queue`) with a denial-risk score, a reason, and a suggested fix,
plus a payer-level summary (`gold.denial_summary_by_payer`). No production
impact numbers are claimed — the data are synthetic, so only synthetic-data
model metrics are reported.

## Architecture — Medallion / Lakehouse

```
CSV (synthetic) ──> Bronze Delta ──> Silver Delta ──> Gold Delta ──> Review queue + summary
  landing            raw + metadata    cleaned + DQ       SQL models      ML risk score
                                                              │               │
                                                              └─ MLflow ──────┘
                                                              AI explanation (LLM, human-reviewed)
Databricks Workflow / Asset Bundle orchestrates it. GitHub Actions = CI/CD.
```

| Layer | Table | What happens |
|---|---|---|
| Landing | `data/raw/*.csv` | Synthetic claims + a payers reference file |
| Bronze | `bronze.claims_raw` | As-is load + `_ingest_ts`, `_source_file`. No business logic. |
| Silver | `silver.claims_clean` | Dedupe, valid dates/amounts, standardise codes, DQ checks fail the run if thresholds breach |
| Gold | `gold.claim_features`, `gold.review_queue`, `gold.denial_summary_by_payer` | Spark SQL: features, risk score join, payer aggregates |
| AI | MLflow model + LLM explanation | Logistic Regression risk score; LLM turns top risk factors into a plain-English reason + fix. Template fallback if no LLM endpoint. Human reviews before any action. |

## Tech used — and where each one shows up

- **Python:** data generator, risk-score logic, LLM prompt builder
- **PySpark:** Bronze → Silver transforms, Delta writes, partitioning by `service_date`
- **SQL (Spark SQL):** Gold models in `sql/gold_models.sql`
- **Databricks:** Unity Catalog schemas (bronze/silver/gold), Delta Lake, Workflows, Asset Bundles (`databricks.yml`), MLflow tracking
- **AI / ML:** scikit-learn Logistic Regression logged to MLflow + GenAI explanation via Databricks Foundation Model APIs (or any OpenAI-compatible endpoint)
- **CI/CD:** GitHub Actions — compile check, unit tests, deploy bundle on merge to `main`

## Run it

### 1. Locally (no Spark needed for the core logic)

Local checks need only `pytest` (`pip install pytest`). The full
`requirements.txt` (PySpark, MLflow, scikit-learn) is for Databricks /
local Spark — don't install it just to run the generator or tests.

```bash
# From the project root (tests import `src`, so the working directory matters)
python3 data/generate_data.py --rows 5000 --out data/raw
python3 -m pytest tests/ -q
# Reads the real generated row: C-000123 is Cigna/J06.9, LOW risk (0.10,
# high amount only). For a HIGH example, try --claim-id C-000001
# (missing diagnosis + high amount, 0.55).
python3 -m src.explain --claim-id C-000123
```

### 2. On Databricks (Free Edition / trial / Azure Databricks)

1. Create a workspace, create schemas `bronze`, `silver`, `gold` in a catalog.
2. Upload `data/raw/*.csv` to a Volume, or run `data/generate_data.py` and upload the output.
3. Run in order: `src/bronze_silver.py` with `--raw-path` set to the
   Volume path of `claims.csv` (e.g. `--raw-path /Volumes/<catalog>/<schema>/landing/claims.csv`)
   → `sql/gold_models.sql` → `src/features_train.py` → `src/explain.py`.
   Before deploying the bundle, replace the two placeholders in
   `databricks.yml` with your workspace values: the Volume path of
   `claims.csv` in the `bronze_silver` task's `parameters`
   (`/Volumes/<catalog>/<schema>/landing/claims.csv`), and your SQL
   warehouse ID in the `gold_models` task's `warehouse_id`
   (`YOUR_SQL_WAREHOUSE_ID`) — the bundle as written
   has no cluster/warehouse configured, so run
   `databricks bundle validate` first and fill in the workspace values
   it asks for. Free Edition is serverless-only, with one 2X-Small SQL
   warehouse and max 5 concurrent job tasks.
4. Or deploy the bundle: `databricks bundle deploy` then run the `claims-denial-pipeline` job (see `databricks.yml`).
5. Check the outputs: `SELECT * FROM gold.review_queue ORDER BY denial_risk_score DESC LIMIT 20;`

### 3. CI/CD

Push to GitHub. `.github/workflows/ci.yml` runs `py_compile` + `pytest` on
every PR, and deploys the Databricks bundle on merge to `main` (needs
`DATABRICKS_HOST` / `DATABRICKS_TOKEN` secrets — no secrets in code).

## Interview talking points

See `INTERVIEW_SCRIPT.md` — 2-minute story, architecture walkthrough,
trade-offs, and the 10 questions interviewers ask next (with short answers).

## Honesty notes

- Label this **personal project, synthetic data** on your resume/LinkedIn.
  Never present it as employer work.
- Never quote a real denial rate, dollar saving, or accuracy from a job.
  Report only what this synthetic run produced, and say so.
- No real patient data. The generator invents names/codes; IDs are `C-######`.
"# claims-denial-lakehouse" 
