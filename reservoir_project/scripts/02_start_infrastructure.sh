#!/bin/bash

set -e

HOME_DIR="/home/talentum"

echo "======================================"
echo "Starting Hadoop"
echo "======================================"

jps | grep -q NameNode || "$HOME_DIR/run-hdfs.sh" -s start
sleep 3

jps | grep -q ResourceManager || "$HOME_DIR/run-yarn.sh" -s start
sleep 3

echo
echo "Creating HDFS directories..."

#hdfs dfs -mkdir -p /user/talentum
#hdfs dfs -mkdir -p /user/hive/warehouse
hdfs dfs -mkdir -p /user/talentum/reservoir_project

echo
echo "======================================"
echo "Starting Hive Metastore"
echo "======================================"

if ! jps | grep -q RunJar; then
    nohup "$HOME_DIR/run-hivemetastore.sh" -s start \
        > "$HOME_DIR/reservoir_project/logs/hive-metastore.log" 2>&1 &
    sleep 5
else
    echo "A RunJar process already exists; not starting another."
fi

echo
echo "======================================"
echo "Starting HiveServer2"
echo "======================================"

if ! pgrep -f "org.apache.hive.service.server.HiveServer2" > /dev/null; then
    nohup "$HOME_DIR/run-hiveserver2.sh" -s start \
        > "$HOME_DIR/reservoir_project/logs/hiveserver2.log" 2>&1 &
    sleep 10
else
    echo "HiveServer2 already running."
fi


echo
echo "======================================"
echo "Starting ZooKeeper"
echo "======================================"

if ! pgrep -f "QuorumPeerMain" > /dev/null; then
    nohup "$HOME_DIR/run-kafka_zookeeper_server.sh" -s start \
        > "$HOME_DIR/reservoir_project/logs/zookeeper.log" 2>&1 &
    sleep 5
else
    echo "ZooKeeper already running."
fi

echo
echo "======================================"
echo "Starting Kafka"
echo "======================================"

if ! pgrep -f "kafka.Kafka" > /dev/null; then
    nohup "$HOME_DIR/run-kafka_server.sh" -s start \
        > "$HOME_DIR/reservoir_project/logs/kafka.log" 2>&1 &
    sleep 8
else
    echo "Kafka already running."
fi

echo
echo "======================================"
echo "Services"
echo "======================================"

jps

echo
echo "HDFS:"
hdfs dfs -ls /user/talentum

echo
echo "Infrastructure startup complete."
