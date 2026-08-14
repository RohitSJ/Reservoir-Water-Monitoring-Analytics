from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    row_number,
    lag,
    when,
    date_format,
    round as spark_round
)
from pyspark.sql.window import Window


spark = (
    SparkSession.builder
    .appName("CreateReservoirHiveTables")
    .enableHiveSupport()
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

INPUT = "hdfs://localhost:9000/user/talentum/reservoir_project/cleaned"


print("Reading cleaned Parquet...")

df = spark.read.parquet(INPUT)

print("Rows before de-duplication:", df.count())



dedup_window = Window.partitionBy("Reservoir_name", "Date").orderBy(
    col("Storage").isNull().asc(),
    col("source_file").desc()
)

df = (
    df
    .withColumn("_rn", row_number().over(dedup_window))
    .filter(col("_rn") == 1)
    .drop("_rn")
)

print("Rows after de-duplication:", df.count())

df.printSchema()


# ---------------------------------------------
# Derived columns
# ---------------------------------------------

df = df.withColumn("Month_Name", date_format(col("Date"), "MMMM"))


df = df.withColumn(
    "Storage_Percentage",
    when(
        col("Storage").isNotNull()
        & col("Live_capacity_FRL").isNotNull()
        & (col("Live_capacity_FRL") != 0),
        spark_round((col("Storage") / col("Live_capacity_FRL")) * 100, 2)
    ).otherwise(None)
)


trend_window = Window.partitionBy("Reservoir_name").orderBy("Date")

df = df.withColumn("Previous_Storage", lag("Storage").over(trend_window))

df = df.withColumn(
    "Storage_Change",
    when(
        col("Storage").isNotNull() & col("Previous_Storage").isNotNull(),
        spark_round(col("Storage") - col("Previous_Storage"), 2)
    ).otherwise(None)
)

df = df.withColumn(
    "Storage_Change_Percentage",
    when(
        col("Storage").isNotNull()
        & col("Previous_Storage").isNotNull()
        & (col("Previous_Storage") != 0),
        spark_round((col("Storage_Change") / col("Previous_Storage")) * 100, 2)
    ).otherwise(None)
)


# ---------------------------------------------
# Database
# ---------------------------------------------

spark.sql("CREATE DATABASE IF NOT EXISTS reservoir_db")


# ---------------------------------------------
# Fact table
# ---------------------------------------------

fact_df = df.select(
    "Reservoir_name",
    "Basin",
    "Agency_name",
    "Lat",
    "Long",
    "Date",
    "Year",
    "Month",
    "Month_Name",
    "Full_reservoir_level",
    "Live_capacity_FRL",
    "Storage",
    "Level",
    "Storage_Percentage",
    "Previous_Storage",
    "Storage_Change",
    "Storage_Change_Percentage",
    "source_file"
)

fact_df.write \
    .mode("overwrite") \
    .format("parquet") \
    .saveAsTable("reservoir_db.fact_reservoir_level")


# ---------------------------------------------
# Dimension table
# ---------------------------------------------

dim_window = Window.partitionBy("Reservoir_name").orderBy("Date")

dim_df = (
    df
    .withColumn("rn", row_number().over(dim_window))
    .filter("rn = 1")
    .select(
        "Reservoir_name",
        "Basin",
        "Agency_name",
        "Lat",
        "Long"
    )
)

dim_df.write \
    .mode("overwrite") \
    .format("parquet") \
    .saveAsTable("reservoir_db.dim_reservoir")


print("Hive tables created.")

spark.sql("SHOW TABLES IN reservoir_db").show()


spark.stop()
