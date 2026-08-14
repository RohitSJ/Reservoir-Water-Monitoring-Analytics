#!/bin/bash

HOME_DIR="/home/talentum"

echo "Stopping HiveServer2 if running..."
"$HOME_DIR/run-hiveserver2.sh" -s stop 2>/dev/null || true

echo "Stopping Hive Metastore..."
"$HOME_DIR/run-hivemetastore.sh" -s stop 2>/dev/null || true

echo "Stopping Kafka..."
"$HOME_DIR/run-kafka_server.sh" -s stop 2>/dev/null || true

echo "Stopping ZooKeeper..."
"$HOME_DIR/run-kafka_zookeeper_server.sh" -s stop 2>/dev/null || true

echo "Stopping YARN..."
"$HOME_DIR/run-yarn.sh" -s stop 2>/dev/null || true

echo "Stopping HDFS..."
"$HOME_DIR/run-hdfs.sh" -s stop 2>/dev/null || true

echo
echo "Remaining Java processes:"
jps
