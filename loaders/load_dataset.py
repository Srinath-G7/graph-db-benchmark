"""Loads data/edges.csv into a target platform and measures ingest throughput.

Usage:
    python loaders/load_dataset.py --platform cognodb
    python loaders/load_dataset.py --platform neo4j
    python loaders/load_dataset.py --platform memgraph
    python loaders/load_dataset.py --platform arangodb
    python loaders/load_dataset.py --platform janusgraph

Keep batch size identical across platforms (BATCH_SIZE below) -- differences
in load time should come from the database, not from your batching choices.
"""
import argparse
import csv
import os
import time
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from common.db_clients import get_client
from common.latency import save_result

load_dotenv()

BATCH_SIZE = 1000


def read_edges(path):
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row["src"], row["dst"]


def load_bolt(client, edges_path):
    """Cypher UNWIND batch insert -- works unchanged for CognoDB, Neo4j, Memgraph."""
    try:
        client.run_cypher("CREATE INDEX node_id_idx IF NOT EXISTS FOR (n:Node) ON (n.id)")
    except Exception:
        try:
            client.run_cypher("CREATE INDEX ON :Node(id)")
        except Exception as e:
            print(f"[warn] index creation skipped: {e}")
    batch = []
    node_count, edge_count = set(), 0
    for src, dst in read_edges(edges_path):
        batch.append({"src": src, "dst": dst})
        node_count.add(src)
        node_count.add(dst)
        if len(batch) >= BATCH_SIZE:
            _flush_bolt_batch(client, batch)
            edge_count += len(batch)
            batch = []
    if batch:
        _flush_bolt_batch(client, batch)
        edge_count += len(batch)
    return len(node_count), edge_count


def _flush_bolt_batch(client, batch):
    client.run_cypher(
        """
        UNWIND $rows AS row
        MERGE (a:Node {id: row.src})
        MERGE (b:Node {id: row.dst})
        MERGE (a)-[:REL]->(b)
        """,
        {"rows": batch},
    )


def load_arango(client, edges_path):
    if not client.db.has_collection("nodes"):
        client.db.create_collection("nodes")
    if not client.db.has_collection("edges"):
        client.db.create_collection("edges", edge=True)

    batch_nodes, batch_edges = {}, []
    node_count, edge_count = set(), 0
    for src, dst in read_edges(edges_path):
        for n in (src, dst):
            if n not in batch_nodes:
                batch_nodes[n] = {"_key": n, "node_id": n}
        batch_edges.append({"_from": f"nodes/{src}", "_to": f"nodes/{dst}"})
        node_count.update([src, dst])
        if len(batch_edges) >= BATCH_SIZE:
            _flush_arango_batch(client, batch_nodes, batch_edges)
            edge_count += len(batch_edges)
            batch_nodes, batch_edges = {}, []
    if batch_edges:
        _flush_arango_batch(client, batch_nodes, batch_edges)
        edge_count += len(batch_edges)
    client.db.collection("nodes").add_hash_index(fields=["node_id"], unique=True)
    return len(node_count), edge_count


def _flush_arango_batch(client, nodes_dict, edges_list):
    if nodes_dict:
        client.db.collection("nodes").insert_many(list(nodes_dict.values()), overwrite=True)
    if edges_list:
        client.db.collection("edges").insert_many(edges_list, overwrite=True)


def load_janusgraph(client, edges_path):
    from gremlin_python.process.graph_traversal import __
    g = client.g
    node_count, edge_count = set(), 0
    vertex_cache = {}
    for src, dst in read_edges(edges_path):
        for n in (src, dst):
            if n not in vertex_cache:
                existing = g.V().has("node_id", n).toList()
                vertex_cache[n] = existing[0] if existing else g.addV("Node").property("node_id", n).next()
                node_count.add(n)
        g.V(vertex_cache[src]).addE("REL").to(vertex_cache[dst]).next()
        edge_count += 1
    return len(node_count), edge_count


LOADERS = {
    "cognodb": load_bolt,
    "neo4j": load_bolt,
    "memgraph": load_bolt,
    "arangodb": load_arango,
    "janusgraph": load_janusgraph,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=LOADERS.keys())
    parser.add_argument("--edges-path", default=os.environ.get("DATASET_PATH", "data/edges.csv"))
    args = parser.parse_args()

    client = get_client(args.platform)
    loader_fn = LOADERS[args.platform]

    print(f"[load] platform={args.platform} file={args.edges_path}")
    start = time.perf_counter()
    node_count, edge_count = loader_fn(client, args.edges_path)
    elapsed_sec = time.perf_counter() - start
    client.close()

    result = {
        "node_count": node_count,
        "edge_count": edge_count,
        "wall_clock_sec": round(elapsed_sec, 3),
        "nodes_per_sec": round(node_count / elapsed_sec, 2) if elapsed_sec > 0 else None,
        "relationships_per_sec": round(edge_count / elapsed_sec, 2) if elapsed_sec > 0 else None,
        "batch_size": BATCH_SIZE,
    }
    print(result)
    save_result(args.platform, "ingest", result)

    print(
        "NOTE: JanusGraph's per-edge Gremlin calls above are unbatched and will be much "
        "slower than the Bolt UNWIND batches or Arango insert_many. If you keep this as-is, "
        "say so explicitly in the README caveats -- don't let it silently skew the throughput "
        "comparison. Swapping in JanusGraph's bulk loader (or larger g.addV/addE batches via "
        "Gremlin's inject/sideEffect pattern) is worth doing if time allows."
    )
