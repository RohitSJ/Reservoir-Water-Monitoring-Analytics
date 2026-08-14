#!/bin/bash

echo "======================================"
echo " Reservoir Project Environment Check"
echo "======================================"

echo
echo "Java:"
java -version 2>&1 | head -n 3

echo
echo "Python:"
python3 --version

echo
echo "Hadoop:"
hdfs version 2>&1 | head -n 2

echo
echo "Spark:"
spark-submit --version 2>&1 | grep -E "version|Scala|Java" | head -n 5

echo
echo "Kafka:"
kafka-topics.sh --version

echo
echo "Hive:"
hive --version 2>&1 | head -n 3

echo
echo "Airflow:"
if [ -f "$HOME/miniconda3/envs/airflow-tutorial/bin/airflow" ]; then
    "$HOME/miniconda3/envs/airflow-tutorial/bin/airflow" version
else
    echo "Airflow executable not found"
fi

echo
echo "SPARK_HOME:"
echo "$SPARK_HOME"

echo
echo "PYSPARK_PYTHON:"
echo "$PYSPARK_PYTHON"

echo
echo "Raw data:"
ls -lh "$HOME/reservoir_project/data/raw/"

echo
echo "======================================"
echo "Checking Kafka Python"
echo "======================================"

python3 - <<'PY'
try:
    from kafka import KafkaProducer
    print("KafkaProducer: OK")
except Exception as e:
    print("KafkaProducer: FAILED")
    print(e)
PY

echo
echo "======================================"
echo "Checking HDFS"
echo "======================================"

hdfs dfs -ls /user 2>/dev/null

echo
echo "======================================"
echo "Check Complete"
echo "======================================"
