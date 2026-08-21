#!/usr/bin/env bash
# One-command benchmark run: loads data + runs workloads for every platform,
# then builds the results matrix and charts.
#
# Prereqs before running:
#   1. cp .env.example .env  and fill in real credentials
#   2. pip install -r requirements.txt
#   3. docker compose up -d          (starts memgraph, arangodb, janusgraph)
#   4. python scripts/prepare_dataset.py --target-edges 200000
#
# Usage: ./scripts/run_all.sh

set -euo pipefail

PLATFORMS=("cognodb" "neo4j" "memgraph" "arangodb" "janusgraph")

echo "=== Loading dataset into every platform ==="
for p in "${PLATFORMS[@]}"; do
    echo "--- load: $p ---"
    python loaders/load_dataset.py --platform "$p"
done

echo "=== Running workloads against every platform ==="
for p in "${PLATFORMS[@]}"; do
    echo "--- workloads: $p ---"
    python workloads/run_workloads.py --platform "$p"
done

echo "=== Building results matrix + charts ==="
python scripts/build_report.py

echo "=== Done. See results/results_matrix.csv and results/chart_*.png ==="
