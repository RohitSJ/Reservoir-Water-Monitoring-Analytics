# Reservoir Big-Data Pipeline

Stack (kept as-is, no upgrades): Java 8u312 - Hadoop 2.7.3 - Spark 2.4.5 (Scala 2.11.12)
- Kafka 2.2.1 - Hive 2.3.6 - Airflow 1.10.10 (conda env `airflow-tutorial`, Python 3.7.11)
- System Python 3.6.9 (used by Spark/PySpark).

See `PIPELINE_NOTES.md` for the full write-up (flow diagram, script-by-script
explanation, run order) and for the list of parts that are still drafts.

## Confirmed data format (from your sample rows)

- `Date` column is `dd-MM-yyyy`, e.g. `25-01-2023` -- handled in `spark/reservoir_streaming.py` via `to_date(col("Date"), "dd-MM-yyyy")`.
- Missing numeric values appear as the literal string `"NA"` (not blank), e.g. in `Storage`/`Level` -- handled via a `null_if_na()` helper that converts `"NA"` to a real null before casting to double, so it doesn't silently rely on Spark's cast-failure-returns-null behavior.

## Quick run order

1. `scripts/00_check_environment.sh`
2. `scripts/02_start_infrastructure.sh`
3. `scripts/03_create_kafka_topic.sh`
4. `scripts/05_run_spark_streaming.sh` (leave running/finite via trigger(once=True))
5. `python3 kafka/reservoir_producer.py`
6. `scripts/06_create_hive_tables.sh`
7. `scripts/09_create_hive_views.sh` (analytical views, untested against real data yet)
8. `scripts/07_validate_pipeline.sh`
9. `scripts/08_stop_infrastructure.sh` when done

Airflow DAG: copy `../airflow-tutorial/dags/reservoir_pipeline.py` into your
actual `$AIRFLOW_HOME/dags/` folder (this zip ships it under a sibling
`airflow-tutorial/` folder since your real Airflow home already exists at
`~/Desktop/airflow-tutorial`). The DAG now includes the `create_hive_views` task.

## Not finalized / still open

- **Raw CSVs are not included in this zip** -- put your own 4 files in `data/raw/` (I don't have direct access to your Project's CSV files from this tool environment, only the sample rows you pasted).
- Whether to drop `subbasin` or keep it for sub-basin analysis -- currently dropped in `spark/reservoir_streaming.py`. Your sample shows `subbasin` is itself often `"NA"`, so it may not be very useful anyway -- worth checking how many rows actually have a real subbasin value before deciding.
- `sql/reservoir_tables.sql` views are written and now have a runner script (`09_create_hive_views.sh`), but have **not been executed against real data** -- verify row counts/values after your first full run.
- No task/script exports data for Power BI (CSV/Parquet export or Hive ODBC) -- Power BI runs on Windows, outside this VM/repo.
- HiveServer2 startup script was discussed but never finalized in the conversation -- only Hive Metastore start is included in `02_start_infrastructure.sh`.
- `kafka-python` version pin (`2.0.2` in `requirements.txt`) hasn't been confirmed to install cleanly against your actual Python 3.6/3.7 envs -- test before relying on it.
