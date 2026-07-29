#!/usr/bin/env python3
"""
Reservoir Kafka Producer
Reads yearly reservoir CSV files and publishes each row as JSON to a Kafka topic.

Run:
  python producer.py \
    --input-dir ./data/raw \
    --bootstrap-server localhost:9092 \
    --topic reservoir_raw

Notes:
- This producer is designed for batch-to-stream simulation.
- Each CSV row is sent as one Kafka message.
- The Spark job consumes the same JSON schema.
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer


EXPECTED_COLUMNS = [
    "Reservoir_name",
    "Basin",
    "subbasin",
    "Agency_name",
    "Lat",
    "Long",
    "Date",
    "Year",
    "Month",
    "Full_reservoir_level",
    "Live_capacity_FRL",
    "Storage",
    "Level",
]


def infer_year_from_filename(path):
    name = path.name.lower()
    for year in (2022, 2023, 2024, 2025):
        if str(year) in name:
            return year
    return None


def normalize_row(row, source_file, source_year):
    record = row.to_dict()
    record["source_file"] = source_file
    record["source_year"] = source_year

    for k, v in list(record.items()):
        if pd.isna(v):
            record[k] = None
        elif hasattr(v, "item"):
            try:
                record[k] = v.item()
            except Exception:
                pass

    return record


def iter_csv_records(input_dir):
    files = sorted([p for p in input_dir.glob("*.csv")])
    if not files:
        raise FileNotFoundError("No CSV files found in: {}".format(input_dir))

    for csv_path in files:
        source_year = infer_year_from_filename(csv_path)
        df = pd.read_csv(csv_path)

        cols = [c for c in EXPECTED_COLUMNS if c in df.columns]
        df = df[cols].copy()

        for col in EXPECTED_COLUMNS:
            if col not in df.columns:
                df[col] = None

        df = df[EXPECTED_COLUMNS]

        for _, row in df.iterrows():
            yield normalize_row(row, csv_path.name, source_year)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, help="Folder containing raw reservoir CSV files")
    parser.add_argument("--bootstrap-server", default="localhost:9092", help="Kafka bootstrap server")
    parser.add_argument("--topic", default="reservoir_raw", help="Kafka topic name")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap_server,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if v is not None else None,
        acks="all",
        retries=5,
        linger_ms=50,
    )

    sent = 0
    for record in iter_csv_records(input_dir):
        key = str(record.get("Reservoir_name") or "unknown")
        producer.send(args.topic, key=key, value=record)
        sent += 1
        if sent % 1000 == 0:
            producer.flush()
            print("Sent {} messages...".format(sent))

    producer.flush()
    producer.close()
    print("Done. Total messages sent: {}".format(sent))


if __name__ == "__main__":
    main()
