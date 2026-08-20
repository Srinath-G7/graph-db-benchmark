"""Reads every results/*.json file and produces:
  - results/results_matrix.csv (one row per platform x workload)
  - results/chart_*.png (a few summary charts for the README)

Run this after workloads/run_workloads.py has been run for every platform.
"""
import glob
import json
import os

import pandas as pd
import matplotlib.pyplot as plt

RESULTS_DIR = "results"


def load_all_results():
    rows = []
    for path in glob.glob(os.path.join(RESULTS_DIR, "*.json")):
        with open(path) as f:
            data = json.load(f)
        rows.append(data)
    return rows


def build_matrix(rows):
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS_DIR, "results_matrix.csv"), index=False)
    print(f"[saved] {RESULTS_DIR}/results_matrix.csv ({len(df)} rows)")
    return df


def chart_traversal_p95(df):
    hop_rows = df[df["workload"].str.startswith("traversal_", na=False)]
    if hop_rows.empty:
        return
    pivot = hop_rows.pivot(index="workload", columns="platform", values="p95_ms")
    pivot = pivot.reindex(["traversal_1hop", "traversal_2hop", "traversal_3hop"])
    ax = pivot.plot(kind="bar", figsize=(9, 5))
    ax.set_ylabel("p95 latency (ms)")
    ax.set_title("Traversal p95 latency by hop depth")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "chart_traversal_p95.png"), dpi=150)
    plt.close()
    print("[saved] chart_traversal_p95.png")


def chart_ingest_throughput(df):
    ingest_rows = df[df["workload"] == "ingest"]
    if ingest_rows.empty:
        return
    ax = ingest_rows.set_index("platform")["relationships_per_sec"].plot(kind="bar", figsize=(8, 5))
    ax.set_ylabel("relationships/sec")
    ax.set_title("Ingest throughput by platform")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "chart_ingest_throughput.png"), dpi=150)
    plt.close()
    print("[saved] chart_ingest_throughput.png")


def chart_mixed_qps(df):
    mixed_rows = df[df["workload"].str.startswith("mixed_c", na=False)]
    if mixed_rows.empty:
        return
    pivot = mixed_rows.pivot(index="concurrency", columns="platform", values="queries_per_sec")
    ax = pivot.plot(kind="bar", figsize=(9, 5))
    ax.set_ylabel("queries/sec")
    ax.set_title("Mixed workload throughput by concurrency")
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "chart_mixed_qps.png"), dpi=150)
    plt.close()
    print("[saved] chart_mixed_qps.png")


if __name__ == "__main__":
    rows = load_all_results()
    if not rows:
        print("No results found in results/. Run the loaders and workloads first.")
        raise SystemExit(1)
    df = build_matrix(rows)
    chart_traversal_p95(df)
    chart_ingest_throughput(df)
    chart_mixed_qps(df)
    print("Now pull results_matrix.csv + charts into README.md's results section.")
