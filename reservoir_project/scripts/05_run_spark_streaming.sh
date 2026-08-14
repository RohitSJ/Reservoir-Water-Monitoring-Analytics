#!/bin/bash

set -e

SPARK_HOME="/home/talentum/spark"

echo "======================================"
echo "Starting Spark Structured Streaming"
echo "======================================"

"$SPARK_HOME/bin/spark-submit" \
    --master local[*] \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.11:2.4.5 \
    --conf spark.sql.shuffle.partitions=2 \
    /home/talentum/reservoir_project/spark/reservoir_streaming.py
