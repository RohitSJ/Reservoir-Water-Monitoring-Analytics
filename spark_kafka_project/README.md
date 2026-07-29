# Reservoir Kafka + Spark + Hive Pipeline

## What this project does
- Reads reservoir CSV data
- Publishes rows to Kafka as JSON
- Consumes them with Spark Structured Streaming
- Cleans and deduplicates records
- Writes Hive tables for analytics and dashboarding

## 1) Start Kafka
Example:
```bash
bin/zookeeper-server-start.sh config/zookeeper.properties
bin/kafka-server-start.sh config/server.properties
bin/kafka-topics.sh --create --topic reservoir_raw --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

## 2) Run Kafka producer
```bash
python producer.py --input-dir ./data/raw --bootstrap-server localhost:9092 --topic reservoir_raw
```

## 3) Run Spark Structured Streaming
```bash
spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.apache.kafka:kafka-clients:3.7.0 \
  spark_streaming_job.py \
  --bootstrap-server localhost:9092 \
  --topic reservoir_raw \
  --checkpoint-dir /tmp/reservoir_checkpoint \
  --hive-db reservoir_db
```

## 4) Hive tables created
- reservoir_cleaned_stream
- reservoir_master
- reservoir_daily_fact

## Notes
- This version is best for a simulated streaming architecture.
- For the reservoir project, use CSV files as batch inputs into Kafka.
- If you later move to real-time feeds, only the producer layer changes.
