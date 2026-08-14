#!/bin/bash

set -e

spark-submit \
    --master local[*] \
    /home/talentum/reservoir_project/spark/create_hive_tables.py
