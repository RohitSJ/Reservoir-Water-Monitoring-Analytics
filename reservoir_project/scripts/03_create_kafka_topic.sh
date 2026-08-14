#!/bin/bash

set -e

KAFKA_HOME="/home/talentum/kafka"
TOPIC="reservoir_data"

echo "Checking Kafka..."

if ! pgrep -f "kafka.Kafka" > /dev/null; then
    echo "ERROR: Kafka is not running."
    exit 1
fi

echo "Creating topic: $TOPIC"

"$KAFKA_HOME/bin/kafka-topics.sh" \
    --create \
    --zookeeper localhost:2181 \
    --replication-factor 1 \
    --partitions 1 \
    --topic "$TOPIC" \
    2>/dev/null || echo "Topic may already exist."

echo
echo "Topic details:"

"$KAFKA_HOME/bin/kafka-topics.sh" \
    --describe \
    --zookeeper localhost:2181 \
    --topic "$TOPIC"
