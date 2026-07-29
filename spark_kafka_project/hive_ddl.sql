-- Hive DDL for Reservoir Project
CREATE DATABASE IF NOT EXISTS reservoir_db;
USE reservoir_db;

CREATE EXTERNAL TABLE IF NOT EXISTS reservoir_cleaned_stream (
    Reservoir_name STRING,
    Basin STRING,
    Agency_name STRING,
    Lat DOUBLE,
    Long DOUBLE,
    Date DATE,
    Full_reservoir_level DOUBLE,
    Live_capacity_FRL DOUBLE,
    Storage DOUBLE,
    Level DOUBLE,
    source_year INT,
    source_file STRING,
    ingestion_ts TIMESTAMP
)
PARTITIONED BY (Year INT, Month INT)
STORED AS PARQUET;

CREATE EXTERNAL TABLE IF NOT EXISTS reservoir_master (
    Reservoir_name STRING,
    Basin STRING,
    Agency_name STRING,
    Lat DOUBLE,
    Long DOUBLE,
    Full_reservoir_level DOUBLE,
    Live_capacity_FRL DOUBLE
)
STORED AS PARQUET;

CREATE EXTERNAL TABLE IF NOT EXISTS reservoir_daily_fact (
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
PARTITIONED BY (Year INT, Month INT)
STORED AS PARQUET;
