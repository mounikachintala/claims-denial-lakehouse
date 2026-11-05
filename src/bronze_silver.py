"""Bronze -> Silver with PySpark + Delta Lake. Run on Databricks.

Bronze: raw as-is + ingestion metadata. No business logic.
Silver: dedupe, type casting, valid dates/amounts, standardised codes,
        plus data-quality checks that FAIL the job when thresholds breach
        (never silently load bad data into Gold).

On Databricks, run as a Workflow task / notebook with:
    spark = SparkSession.builder.getOrCreate()
    run_pipeline(spark, raw_path="/Volumes/<catalog>/<schema>/landing/claims.csv")
"""
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

def load_bronze(spark: SparkSession, raw_path: str, bronze_table: str) -> DataFrame:
    df = (
        spark.read.option("header", "true").option("inferSchema", "true")
        .csv(raw_path)
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.input_file_name())
    )
    df.write.format("delta").mode("overwrite").saveAsTable(bronze_table)
    return df


def clean_silver(spark: SparkSession, bronze_table: str, silver_table: str) -> DataFrame:
    df = spark.table(bronze_table)
    clean = (
        df.dropDuplicates(["claim_id"])
        .withColumn("service_date", F.to_date("service_date"))
        .withColumn("billed_amount", F.col("billed_amount").cast("double"))
        .withColumn("payer", F.upper(F.trim("payer")))
        # Spark reads an empty CSV field as NULL, not "". Normalise it so
        # the Gold missing-diagnosis check (diagnosis_code = '') works.
        .withColumn("diagnosis_code",
                    F.coalesce(F.upper(F.trim("diagnosis_code")), F.lit("")))
        .filter(F.col("service_date").isNotNull())
        .filter(F.col("billed_amount") > 0)
        .filter(F.col("claim_id").isNotNull())
    )
    # Data-quality gates: raise, don't silently continue.
    total = clean.count()
    missing_dx_rate = clean.filter(
        (F.col("diagnosis_code").isNull()) | (F.col("diagnosis_code") == "")
    ).count() / max(total, 1)
    if missing_dx_rate > 0.25:
        raise ValueError(f"Missing-diagnosis rate {missing_dx_rate:.1%} exceeds 25% gate")
    clean.write.format("delta").mode("overwrite").partitionBy("service_date").saveAsTable(silver_table)
    return clean


def run_pipeline(spark: SparkSession, raw_path: str,
                 bronze_table: str = "bronze.claims_raw",
                 silver_table: str = "silver.claims_clean") -> None:
    load_bronze(spark, raw_path, bronze_table)
    clean_silver(spark, bronze_table, silver_table)
    print("Bronze -> Silver complete.")


def main() -> None:
    """Entry point for a Databricks Workflow spark_python_task.

    Without this, importing the file as a job task runs nothing.
    Pass the Volume path of the uploaded claims.csv, e.g.:
        --raw-path /Volumes/<catalog>/<schema>/landing/claims.csv
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-path", required=True,
                    help="Path to claims.csv (Volume path on Databricks).")
    ap.add_argument("--bronze-table", default="bronze.claims_raw")
    ap.add_argument("--silver-table", default="silver.claims_clean")
    args = ap.parse_args()
    spark = SparkSession.builder.getOrCreate()
    run_pipeline(spark, args.raw_path, args.bronze_table, args.silver_table)


if __name__ == "__main__":
    main()
