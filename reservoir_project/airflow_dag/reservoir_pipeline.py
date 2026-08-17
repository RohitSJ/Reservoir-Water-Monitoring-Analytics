from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash_operator import BashOperator

PROJECT_DIR = "/home/talentum/reservoir_project"

default_args = {
    "owner": "talentum",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

dag = DAG(
    dag_id="reservoir_pipeline",
    default_args=default_args,
    description="End-to-end reservoir big-data pipeline (Kafka -> Spark -> Hive)",
    schedule_interval=None, #"@daily"
    catchup=False,
)

start_infrastructure = BashOperator(
    task_id="start_infrastructure",
    bash_command=f"bash {PROJECT_DIR}/scripts/02_start_infrastructure.sh",
    dag=dag,
)

create_kafka_topic = BashOperator(
    task_id="create_kafka_topic",
    bash_command=f"bash {PROJECT_DIR}/scripts/03_create_kafka_topic.sh",
    dag=dag,
)

produce_to_kafka = BashOperator(
    task_id="produce_to_kafka",
    bash_command=f"python3 {PROJECT_DIR}/kafka/reservoir_producer.py",
    dag=dag,
)

run_spark_streaming = BashOperator(
    task_id="run_spark_streaming",
    bash_command=f"bash {PROJECT_DIR}/scripts/05_run_spark_streaming.sh",
    dag=dag,
)

create_hive_tables = BashOperator(
    task_id="create_hive_tables",
    bash_command=f"bash {PROJECT_DIR}/scripts/06_create_hive_tables.sh",
    dag=dag,
)

create_hive_views = BashOperator(
    task_id="create_hive_views",
    bash_command=f"bash {PROJECT_DIR}/scripts/09_create_hive_views.sh",
    dag=dag,
)

validate_pipeline = BashOperator(
    task_id="validate_pipeline",
    bash_command=f"bash {PROJECT_DIR}/scripts/07_validate_pipeline.sh",
    dag=dag,
)

(
    start_infrastructure
    >> create_kafka_topic
    >> produce_to_kafka
    >> run_spark_streaming
    >> create_hive_tables
    >> create_hive_views
    >> validate_pipeline
)
