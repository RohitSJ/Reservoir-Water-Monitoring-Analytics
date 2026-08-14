from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    trim,
    to_date,
    year,
    month,
    when,
    from_json
)

from pyspark.sql.types import (
    StructType,
    StructField,
    StringType
)


DATE_FORMAT = "yyyy-MM-dd"  
NA_TOKEN = "NA"


def null_if_na(column):
    
    return when(col(column) == NA_TOKEN, None).otherwise(col(column))


KAFKA_SERVER = "localhost:9092"
TOPIC = "reservoir_data"

HDFS_NAMENODE = "hdfs://localhost:9000"
CHECKPOINT = HDFS_NAMENODE + "/user/talentum/reservoir_project/checkpoint"

OUTPUT = HDFS_NAMENODE + "/user/talentum/reservoir_project/cleaned"

spark = (
    SparkSession.builder
    .appName("ReservoirStructuredStreaming")
    .enableHiveSupport()
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


schema = StructType([
    StructField("Reservoir_name", StringType(), True),
    StructField("Basin", StringType(), True),
    StructField("subbasin", StringType(), True),
    StructField("Agency_name", StringType(), True),
    StructField("Lat", StringType(), True),
    StructField("Long", StringType(), True),
    StructField("Date", StringType(), True),
    StructField("Year", StringType(), True),
    StructField("Month", StringType(), True),
    StructField("Full_reservoir_level", StringType(), True),
    StructField("Live_capacity_FRL", StringType(), True),
    StructField("Storage", StringType(), True),
    StructField("Level", StringType(), True),
    StructField("source_file", StringType(), True)
])


# ------------------------------------------------
# Kafka source
# ------------------------------------------------

raw_stream = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_SERVER)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "earliest")
    .option("failOnDataLoss", "false")
    .load()
)

# ------------------------------------------------
# Kafka JSON -> columns
# ------------------------------------------------

json_stream = (
    raw_stream
    .selectExpr(
        "CAST(value AS STRING) AS json_value"
    )
    .select(
        from_json(
            col("json_value"),
            schema
        ).alias("data")
    )
    .select("data.*")
)


# ------------------------------------------------
# Cleaning
# ------------------------------------------------

cleaned = (
    json_stream

    .drop("subbasin")

    .withColumn("Reservoir_name", trim(col("Reservoir_name")))
    .withColumn("Basin", trim(col("Basin")))
    .withColumn("Agency_name", trim(col("Agency_name")))

    .withColumn("Lat", null_if_na("Lat").cast("double"))
    .withColumn("Long", null_if_na("Long").cast("double"))

    .withColumn(
        "Full_reservoir_level",
        null_if_na("Full_reservoir_level").cast("double")
    )

    .withColumn(
        "Live_capacity_FRL",
        null_if_na("Live_capacity_FRL").cast("double")
    )

    .withColumn(
        "Storage",
        null_if_na("Storage").cast("double")
    )

    .withColumn(
        "Level",
        null_if_na("Level").cast("double")
    )

    .withColumn(
        "Date",
        to_date(col("Date"), DATE_FORMAT)
    )

    .filter(col("Reservoir_name").isNotNull())
    .filter(col("Date").isNotNull())

    .withColumn("Year", year(col("Date")))
    .withColumn("Month", month(col("Date")))
)


# ------------------------------------------------
# Write cleaned data to HDFS
# ------------------------------------------------

query = (
    cleaned
    .writeStream
    .format("parquet")
    .option("path", OUTPUT)
    .option("checkpointLocation", CHECKPOINT)
    .outputMode("append")
    .trigger(once=True)
    .start()
)

print("Spark Structured Streaming started")
query.awaitTermination()
print("Spark Structured Streaming completed")

