"""Downloads a public graph dataset and trims it to a target relationship
count so it fits the smallest free tier (see README fairness note).

Default: SNAP soc-Pokec social network (directed friendship edges).
Source: https://snap.stanford.edu/data/soc-Pokec.html
Cite the exact source/size actually used in the README -- do not just
copy this docstring's numbers, they change depending on TARGET_EDGES.

Usage:
    python scripts/prepare_dataset.py --target-edges 200000 --out data/edges.csv
"""
import argparse
import csv
import gzip
import os
import random
import urllib.request

SOC_POKEC_URL = "https://snap.stanford.edu/data/soc-pokec-relationships.txt.gz"


def download(url, dest_path):
    if os.path.exists(dest_path):
        print(f"[skip] {dest_path} already exists")
        return dest_path
    print(f"[download] {url}")
    urllib.request.urlretrieve(url, dest_path)
    return dest_path


def trim_edgelist(raw_path, out_path, target_edges, seed=42):
    """Reads a whitespace-separated 'src dst' edge list (gzip or plain text)
    and writes a reservoir-sampled subset of `target_edges` edges as CSV,
    keeping only nodes that appear in the sampled edges.
    """
    random.seed(seed)
    opener = gzip.open if raw_path.endswith(".gz") else open
    reservoir = []
    with opener(raw_path, "rt") as f:
        for i, line in enumerate(f):
            parts = line.split()
            if len(parts) != 2:
                continue
            edge = (parts[0], parts[1])
            if len(reservoir) < target_edges:
                reservoir.append(edge)
            else:
                j = random.randint(0, i)
                if j < target_edges:
                    reservoir[j] = edge

    node_ids = set()
    for src, dst in reservoir:
        node_ids.add(src)
        node_ids.add(dst)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["src", "dst"])
        writer.writerows(reservoir)

    print(f"[done] wrote {len(reservoir)} edges, {len(node_ids)} unique nodes -> {out_path}")
    print("Record these exact numbers in the README dataset section.")
    return len(node_ids), len(reservoir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-edges", type=int, default=200_000)
    parser.add_argument("--raw", default="data/soc-pokec-relationships.txt.gz")
    parser.add_argument("--out", default="data/edges.csv")
    args = parser.parse_args()

    download(SOC_POKEC_URL, args.raw)
    trim_edgelist(args.raw, args.out, args.target_edges)
