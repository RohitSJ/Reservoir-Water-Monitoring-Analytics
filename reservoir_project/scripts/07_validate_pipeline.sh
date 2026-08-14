#!/bin/bash

echo "======================================"
echo "Reservoir Pipeline Validation"
echo "======================================"

echo
echo "1. Hadoop processes"
jps

echo
echo "2. Kafka process"
pgrep -af "kafka.Kafka" || echo "Kafka NOT running"

echo
echo "3. ZooKeeper process"
pgrep -af "QuorumPeerMain" || echo "ZooKeeper NOT running"

echo
echo "4. HDFS reservoir directory"
hdfs dfs -ls -R /user/talentum/reservoir_project/ 2>/dev/null

echo
echo "5. Hive tables"

hive -e "
USE reservoir_db;
SHOW TABLES;
SELECT COUNT(*) AS fact_count FROM fact_reservoir_level;
SELECT COUNT(*) AS reservoir_count FROM dim_reservoir;
"

echo
echo "6. Analytical views (row counts)"

hive -e "
USE reservoir_db;
SELECT COUNT(*) AS yearly_summary_rows FROM reservoir_yearly_summary;
SELECT COUNT(*) AS monthly_summary_rows FROM reservoir_monthly_summary;
SELECT COUNT(*) AS latest_status_rows FROM reservoir_latest_status;
SELECT COUNT(*) AS basin_summary_rows FROM reservoir_basin_summary;
"

echo
echo "7. Data quality (duplicates + missing values)"

hive -e "
USE reservoir_db;
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT Reservoir_name, \`Date\`) AS distinct_reservoir_dates,
    SUM(CASE WHEN Storage IS NULL THEN 1 ELSE 0 END) AS missing_storage,
    SUM(CASE WHEN \`Level\` IS NULL THEN 1 ELSE 0 END) AS missing_level,
    SUM(CASE WHEN Live_capacity_FRL IS NULL THEN 1 ELSE 0 END) AS missing_capacity
FROM fact_reservoir_level;
"
echo "(total_rows should equal distinct_reservoir_dates -- if not, duplicates slipped through)"

echo
echo "======================================"
echo "Validation Complete"
echo "======================================"
