"""Train denial-risk model, log to MLflow. Run on Databricks.

Default source is the Gold table ``gold.claim_features`` built by
``sql/gold_models.sql`` — this task runs after the Gold task in the
Databricks Workflow, so training on the local landing CSV would bypass
Silver deduping/cleaning and the Gold feature definitions. The CSV path
is kept only as a fallback for running outside Databricks
(``--csv-path``); it derives the same four features with the same
thresholds as the Gold SQL (missing diagnosis, duplicate, submitted
after 30 days, billed amount over $1,000), matching ``src/risk_score.py``.

Reports metrics on SYNTHETIC data only. If sklearn/MLflow/pandas are
unavailable, the script exits with a clear message instead of
pretending to train. Spark/ML steps have not been run locally
(no Spark/workspace here); they run on Databricks.
"""

FEATURES = ["missing_dx", "is_duplicate", "late_submission", "high_amount"]
TARGET = "denied"


def build_features_from_csv(df):
    """Derive Gold-equivalent features from raw CSV columns.

    Mirrors gold.claim_features exactly: an empty/missing diagnosis is
    missing_dx, days_to_submit > 30 is late, billed_amount > 1000 is
    high_amount. CSV string values (e.g. "0") are coerced to numbers
    first, so "0" does not count as truthy.
    """
    df = df.copy()
    df["missing_dx"] = (df["diagnosis_code"].fillna("").astype(str).str.strip() == "").astype(int)
    df["is_duplicate"] = df["is_duplicate"].astype(int)
    df["late_submission"] = (df["days_to_submit"].astype(float) > 30).astype(int)
    df["high_amount"] = (df["billed_amount"].astype(float) > 1000).astype(int)
    return df


def load_from_csv(csv_path: str):
    import pandas as pd

    df = build_features_from_csv(pd.read_csv(csv_path))
    return df[FEATURES + [TARGET]]


def load_from_table(table: str = "gold.claim_features"):
    """Read the Gold features table via Spark and return a pandas frame."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    pdf = spark.table(table).select(FEATURES + [TARGET]).toPandas()
    for col in FEATURES + [TARGET]:
        pdf[col] = pdf[col].astype(int)
    return pdf


def train_dataframe(df, experiment: str = "claims-denial-risk") -> None:
    try:
        import mlflow
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError as e:  # pragma: no cover
        raise SystemExit(f"Install requirements first (sklearn, mlflow, pandas): {e}")

    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURES], df[TARGET], test_size=0.25, random_state=42
    )
    mlflow.set_experiment(experiment)
    with mlflow.start_run():
        model = LogisticRegression(max_iter=500).fit(X_train, y_train)
        auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
        mlflow.log_params({"model": "LogisticRegression", "features": ",".join(FEATURES)})
        mlflow.log_metric("roc_auc_synthetic_test", float(auc))
        mlflow.sklearn.log_model(model, "model")
        print(f"ROC-AUC on synthetic test set: {auc:.3f} (synthetic data only)")
        print("Features:", FEATURES)


def train(csv_path: str, experiment: str = "claims-denial-risk") -> None:
    """Backwards-compatible CSV entry point: train from a raw claims CSV."""
    train_dataframe(load_from_csv(csv_path), experiment)


def main() -> None:
    """Entry point for a Databricks Workflow spark_python_task.

    No arguments on Databricks: reads gold.claim_features. Use
    --csv-path to train from a local CSV instead (needs the
    requirements installed locally).
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="gold.claim_features",
                    help="Gold features table to train from (Databricks).")
    ap.add_argument("--csv-path", default=None,
                    help="Train from a raw claims CSV instead of the Gold table.")
    ap.add_argument("--experiment", default="claims-denial-risk")
    args = ap.parse_args()
    if args.csv_path:
        print(f"Training from CSV (fallback): {args.csv_path}")
        train_dataframe(load_from_csv(args.csv_path), args.experiment)
    else:
        print(f"Training from Gold table: {args.table}")
        train_dataframe(load_from_table(args.table), args.experiment)


if __name__ == "__main__":
    main()
