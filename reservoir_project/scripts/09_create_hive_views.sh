#!/bin/bash

set -e

echo "======================================"
echo "Creating Hive analytical views"
echo "======================================"

hive -f /home/talentum/reservoir_project/sql/reservoir_tables.sql

echo
echo "Done. Verify with:"
echo "  hive -e \"USE reservoir_db; SHOW TABLES;\""
