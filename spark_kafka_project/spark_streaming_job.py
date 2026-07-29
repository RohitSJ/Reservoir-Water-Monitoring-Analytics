#!/usr/bin/env python3
"""
Reservoir Spark Structured Streaming Job
Consumes reservoir records from Kafka, cleans them, and writes Hive tables.

Run with:
  spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.apache.kafka:kafka-clients:3.7.0 \
    spark_streaming_job.py \
    --bootstrap-server localhost:9092 \
    --topic reservoir_raw \
    --checkpoint-dir hdfs:///tmp/reservoir_checkpoint \
    --hive-db reservoir_db

Important:
- Spark must be built with Hive support.
- Set spark.sql.warehouse.dir and enable Hive metastore in spark-defaults.conf if needed.
- This example writes three curated Hive tables:
    1) reservoir_master
    2) reservoir_daily_fact
    3) reservoir_cleaned_stream (optional staging table)
"""

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window


SCHEMA = T.StructType([
    T.StructField("Reservoir_name", T.StringType(), True),
    T.StructField("Basin", T.StringType(), True),
    T.StructField("subbasin", T.StringType(), True),
    T.StructField("Agency_name", T.StringType(), True),
    T.StructField("Lat", T.DoubleType(), True),
    T.StructField("Long", T.DoubleType(), True),
    T.StructField("Date", T.StringType(), True),
    T.StructField("Year", T.IntegerType(), True),
    T.StructField("Month", T.IntegerType(), True),
    T.StructField("Full_reservoir_level", T.DoubleType(), True),
    T.StructField("Live_capacity_FRL", T.DoubleType(), True),
    T.StructField("Storage", T.DoubleType(), True),
    T.StructField("Level", T.DoubleType(), True),
    T.StructField("source_file", T.StringType(), True),
    T.StructField("source_year", T.IntegerType(), True),
])


def build_spark(app_name):
    return (
        SparkSession.builder
        .appName(app_name)
        .enableHiveSupport()
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def dedupe_with_best_row(df):
    useful_cols = [
        "Basin", "Agency_name", "Lat", "Long",
        "Full_reservoir_level", "Live_capacity_FRL", "Storage", "Level", "Year", "Month"
    ]
    nn_expr = None
    for c in useful_cols:
        expr = F.when(F.col(c).isNotNull(), F.lit(1)).otherwise(F.lit(0))
        nn_expr = expr if nn_expr is None else (nn_expr + expr)

    w = Window.partitionBy("Reservoir_name", "Date").orderBy(F.desc(nn_expr), F.desc("source_year"))
    return (
        df.withColumn("non_null_score", nn_expr)
          .withColumn("rn", F.row_number().over(w))
          .filter(F.col("rn") == 1)
          .drop("rn", "non_null_score")
    )


def create_or_replace_hive_tables(spark, hive_db):
    spark.sql("CREATE DATABASE IF NOT EXISTS {}".format(hive_db))
    spark.sql("USE {}".format(hive_db))

    spark.sql("""
        CREATE TABLE IF NOT EXISTS reservoir_cleaned_stream (
            Reservoir_name STRING,
            Basin STRING,
            Agency_name STRING,
            Lat DOUBLE,
            Long DOUBLE,
            Date DATE,
            Year INT,
            Month INT,
            Day INT,
            Full_reservoir_level DOUBLE,
            Live_capacity_FRL DOUBLE,
            Storage DOUBLE,
            Level DOUBLE,
            source_year INT,
            source_file STRING,
            ingestion_ts TIMESTAMP
        )
        USING parquet
        PARTITIONED BY (Year, Month)
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS reservoir_master (
            Reservoir_name STRING,
            Basin STRING,
            Agency_name STRING,
            Lat DOUBLE,
            Long DOUBLE,
            Full_reservoir_level DOUBLE,
            Live_capacity_FRL DOUBLE
        )
        USING parquet
    """)

    spark.sql("""
        CREATE TABLE IF NOT EXISTS reservoir_daily_fact (
            Reservoir_name STRING,
            Basin STRING,
            Agency_name STRING,
            Lat DOUBLE,
            Long DOUBLE,
            Date DATE,
            Day INT,
            Full_reservoir_level DOUBLE,
            Live_capacity_FRL DOUBLE,
            Storage DOUBLE,
            Level DOUBLE,
            source_year INT,
            source_file STRING,
            ingestion_ts TIMESTAMP
        )
        USING parquet
        PARTITIONED BY (Year INT, Month INT)
    """)


def upsert_master_table(batch_df, batch_id, hive_db):
    if batch_df.rdd.isEmpty():
        return

    spark = batch_df.sparkSession
    spark.sql("USE {}".format(hive_db))

    meta_df = batch_df.select(
        "Reservoir_name", "Basin", "Agency_name", "Lat", "Long",
        "Full_reservoir_level", "Live_capacity_FRL"
    ).dropDuplicates(["Reservoir_name"])

    try:
        existing = spark.table("reservoir_master")
        combined = existing.unionByName(meta_df, allowMissingColumns=True)
        final_df = combined.dropDuplicates(["Reservoir_name"])
    except Exception:
        final_df = meta_df

    final_df.write.mode("overwrite").saveAsTable("reservoir_master")


def write_daily_fact(batch_df, batch_id, hive_db):
    if batch_df.rdd.isEmpty():
        return

    spark = batch_df.sparkSession
    spark.sql("USE {}".format(hive_db))

    out = (
        batch_df
        .withColumn("Year", F.year("Date"))
        .withColumn("Month", F.month("Date"))
        .withColumn("Day", F.dayofmonth("Date"))
        .withColumn("ingestion_ts", F.current_timestamp())
        .select(
            "Reservoir_name", "Basin", "Agency_name", "Lat", "Long", "Date",
            "Day", "Year", "Month", "Full_reservoir_level", "Live_capacity_FRL",
            "Storage", "Level", "source_year", "source_file", "ingestion_ts"
        )
    )

    out.write.mode("append").insertInto("reservoir_daily_fact")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-server", required=True)
    parser.add_argument("--topic", default="reservoir_raw")
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--hive-db", default="reservoir_db")
    args = parser.parse_args()

    spark = build_spark("ReservoirKafkaSparkStreaming")
    spark.sparkContext.setLogLevel("WARN")
    create_or_replace_hive_tables(spark, args.hive_db)
    spark.sql("USE {}".format(args.hive_db))

    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", args.bootstrap_server)
        .option("subscribe", args.topic)
        .option("startingOffsets", "latest")
        .load()
    )

    parsed = (
        raw_stream
        .select(F.col("value").cast("string").alias("json_str"))
        .select(F.from_json(F.col("json_str"), SCHEMA).alias("data"))
        .select("data.*")
    )

    cleaned = (
        parsed
        .withColumn("Reservoir_name", F.trim(F.col("Reservoir_name")))
        .withColumn("Basin", F.trim(F.col("Basin")))
        .withColumn("Agency_name", F.trim(F.col("Agency_name")))
        .withColumn("Date", F.to_date(F.col("Date"), "yyyy-MM-dd"))
        .filter(F.col("Reservoir_name").isNotNull() & F.col("Date").isNotNull())
    )

    deduped = dedupe_with_best_row(cleaned)

    staging = (
        deduped
        .withColumn("Year", F.year("Date"))
        .withColumn("Month", F.month("Date"))
        .withColumn("Day", F.dayofmonth("Date"))
        .withColumn("ingestion_ts", F.current_timestamp())
        .select(
            "Reservoir_name", "Basin", "Agency_name", "Lat", "Long", "Date",
            "Year", "Month", "Day", "Full_reservoir_level", "Live_capacity_FRL",
            "Storage", "Level", "source_year", "source_file", "ingestion_ts"
        )
    )

    staging_query = (
        staging.writeStream
        .outputMode("append")
        .option("checkpointLocation", "{}/staging".format(args.checkpoint_dir))
        .foreachBatch(lambda df, bid: df.write.mode("append").saveAsTable("reservoir_cleaned_stream"))
        .start()
    )

    fact_query = (
        deduped.writeStream
        .outputMode("append")
        .option("checkpointLocation", "{}/fact".format(args.checkpoint_dir))
        .foreachBatch(lambda df, bid: write_daily_fact(df, bid, args.hive_db))
        .start()
    )

    master_query = (
        deduped.writeStream
        .outputMode("append")
        .option("checkpointLocation", "{}/master".format(args.checkpoint_dir))
        .foreachBatch(lambda df, bid: upsert_master_table(df, bid, args.hive_db))
        .start()
    )

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
