# Interview script — Claims Denial Lakehouse (personal project, synthetic data)

## 2-minute story (memorise the shape, not the words)

> "Billing teams lose time and cash flow when claims get denied after
> submission — missing codes, late filing, duplicates. I built a small
> lakehouse that catches risky claims *before* submission.
>
> Synthetic claims land in Bronze as-is, Silver cleans and dedupes them
> with data-quality gates, and Gold — written in Spark SQL — produces a
> review queue ranked by denial risk and a payer-level denial summary.
> A Logistic Regression model in MLflow scores risk, and a GenAI step
> turns the risk factors into a plain-English reason and a suggested fix
> for the billing reviewer. A human reviews before anything is changed.
>
> It's orchestrated as a Databricks Workflow via Asset Bundles, and
> GitHub Actions runs tests on every PR and deploys on merge to main.
> All data are synthetic, so I only report synthetic-data metrics."

## Architecture walkthrough (30 seconds, point at the diagram in README)

Landing CSV → Bronze Delta (raw + `_ingest_ts`) → Silver Delta
(dedupe, DQ gates) → Gold SQL (features, review queue, payer summary)
→ MLflow model + LLM explanation → review queue table.

Say *why* each layer exists: Bronze = auditability, Silver = trust,
Gold = business-ready.

## Trade-offs — say these before you're asked

- **Rule score vs ML score:** I kept a transparent rule score as the
  baseline. If the ML model can't beat it clearly on synthetic data,
  ship the rules — a reviewer must be able to explain a decision.
- **Batch, not streaming:** claims arrive as daily files here. Streaming
  (Auto Loader / Structured Streaming) is the next step if submission
  becomes near-real-time — I can describe how I'd add it.
- **LLM guardrails:** the LLM only rephrases observed factors. No PHI,
  no invented payer rules, human in the loop. Template fallback if the
  endpoint is down.
- **Partitioning:** Silver/Gold partitioned by `service_date` — the
  query pattern is date-range + payer, so scans stay small.

## 10 likely follow-ups (short answers)

1. **Why Delta Lake?** ACID, time travel, schema enforcement — a failed
   Silver load doesn't corrupt Gold; you can roll back.
2. **What if a file arrives twice?** Dedupe on `claim_id` in Silver +
   `_source_file` in Bronze for lineage. Idempotent reload.
3. **How do you handle schema drift?** Bronze keeps raw; Silver casts
   explicitly and fails on unexpected nulls/rates (DQ gates).
4. **How is this tested?** Unit tests for risk logic (no Spark needed),
   DQ gates in the pipeline, CI runs both on every PR.
5. **How would you scale it?** Partitioning + incremental loads
   (only new files / MERGE into Silver), cluster sizing in the Job.
6. **Why MLflow?** Experiment tracking, model versioning, compare
   rule vs ML on the same test split.
7. **What would you do with real data?** PII/PHI handling, Unity
   Catalog access control, audit logging, payer-rule tables as
   versioned reference data — none of that is in the synthetic demo.
8. **CI/CD flow?** PR → tests → review → merge to main → bundle
   deploy → Workflow runs. Secrets in GitHub Secrets, never in code.
9. **Biggest failure mode?** Bad payer reference data silently
   mis-scoring claims — hence DQ checks on reference tables too.
10. **What next?** Streaming ingestion, model monitoring / drift on
    denial rate by payer, and a Databricks SQL dashboard on Gold.

## Resume bullet (personal project — label it as such)

> Personal Project — Claims Denial Lakehouse (PySpark, Databricks, SQL,
> MLflow, GenAI, GitHub Actions): built Bronze/Silver/Gold Delta
> lakehouse on synthetic claims data; Spark SQL Gold models produce a
> risk-ranked review queue and payer denial summary; Logistic
> Regression + LLM explanation with human review; CI/CD via Databricks
> Asset Bundles and GitHub Actions.

Do NOT add this as employer experience. Do NOT add real volumes,
savings, or accuracy figures from a job.
