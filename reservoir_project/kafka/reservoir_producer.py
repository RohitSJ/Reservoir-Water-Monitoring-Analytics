#!/usr/bin/env python3

import csv
import json
import os

from kafka import KafkaProducer

KAFKA_SERVER = "localhost:9092"
TOPIC = "reservoir_data"

BASE_DIR = "/home/talentum/reservoir_project"
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

FILES = [
    "2022_Reservoir_Data.csv",
    "2023_Reservoir_Data.csv",
    "2024_Reservoir_Data.csv",
    "2025_Reservoir_Data.csv"
]


def create_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        value_serializer=lambda value:
            json.dumps(value).encode("utf-8"),
        acks="all",
        retries=3
    )


def produce_file(producer, filepath):
    print("\nProcessing:", filepath)

    count = 0

    with open(filepath, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:

            # Add source information
            row["source_file"] = os.path.basename(filepath)

            producer.send(TOPIC, value=row)

            count += 1

            if count % 1000 == 0:
                producer.flush()
                print("Sent:", count)

    producer.flush()

    print("Completed:", count, "records")


def main():

    print("======================================")
    print("Reservoir Kafka Producer")
    print("======================================")

    producer = create_producer()

    for filename in FILES:

        filepath = os.path.join(RAW_DIR, filename)

        if not os.path.exists(filepath):
            print("WARNING: File not found:", filepath)
            continue

        produce_file(producer, filepath)

    producer.flush()
    producer.close()

    print("\nProducer completed.")


if __name__ == "__main__":
    main()
