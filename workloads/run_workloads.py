"""Runs the full required workload suite (section 5.2 of the assignment)
against one platform and saves per-workload JSON results.

Usage:
    python workloads/run_workloads.py --platform cognodb
"""
import argparse
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
from common.db_clients import get_client
from common.latency import run_n_times, summarize, save_result
from gremlin_python.process.traversal import TextP

load_dotenv()

SAMPLE_START_NODES = int(os.environ.get("SAMPLE_START_NODES", 200))
READ_ITERATIONS = int(os.environ.get("READ_ITERATIONS", 100))
CONCURRENCY_LEVELS = [int(x) for x in os.environ.get("CONCURRENCY_LEVELS", "10,40").split(",")]
MIXED_DURATION_SEC = int(os.environ.get("MIXED_WORKLOAD_DURATION_SEC", 30))


def sample_start_ids_bolt(client, n=SAMPLE_START_NODES):
    rows = client.run_cypher(
        "MATCH (n:Node) RETURN n.id AS id ORDER BY rand() LIMIT $n", {"n": n}
    )
    return [r["id"] for r in rows]


def traversals_bolt(client, platform):
    start_ids = sample_start_ids_bolt(client)
    for hops in (1, 2, 3):
        pattern = "-[:REL]->()" * hops
        query = f"MATCH (a:Node {{id: $id}}){pattern} RETURN count(*) AS c"

        def op(qid=None):
            qid = qid or random.choice(start_ids)
            client.run_cypher(query, {"id": qid})

        latencies = run_n_times(lambda: op(), READ_ITERATIONS, warmup=10)
        save_result(platform, f"traversal_{hops}hop", summarize(latencies))


def lookups_bolt(client, platform):
    start_ids = sample_start_ids_bolt(client)

    def point_lookup():
        client.run_cypher("MATCH (n:Node {id: $id}) RETURN n", {"id": random.choice(start_ids)})

    latencies = run_n_times(point_lookup, READ_ITERATIONS, warmup=10)
    save_result(platform, "point_lookup", {
        **summarize(latencies),
        "indexed_properties": ["Node.id"],
    })

    # Indexed/filtered lookup -- filters on the same indexed property with a range-ish predicate
    def filtered_lookup():
        client.run_cypher(
            "MATCH (n:Node) WHERE n.id STARTS WITH $prefix RETURN n LIMIT 20",
            {"prefix": str(random.choice(start_ids))[:2]},
        )

    latencies = run_n_times(filtered_lookup, READ_ITERATIONS, warmup=10)
    save_result(platform, "filtered_lookup", {
        **summarize(latencies),
        "indexed_properties": ["Node.id"],
    })


def aggregation_bolt(client, platform):
    def agg():
        client.run_cypher(
            "MATCH (n:Node)-[r:REL]->() RETURN count(r) AS out_degree_total"
        )

    latencies = run_n_times(agg, READ_ITERATIONS, warmup=10)
    save_result(platform, "aggregation", summarize(latencies))


def mixed_workload_bolt(client_factory, platform, concurrency):
    """Sustained read/write mix (80/20) for MIXED_DURATION_SEC seconds at
    the given client concurrency. Each thread gets its own client/session
    since Bolt sessions aren't meant to be shared across threads.
    """
    start_ids_client = client_factory()
    start_ids = sample_start_ids_bolt(start_ids_client)
    start_ids_client.close()

    stop_at = time.perf_counter() + MIXED_DURATION_SEC
    counters = {"ops": 0, "errors": 0}

    def worker():
        client = client_factory()
        local_ops = 0
        while time.perf_counter() < stop_at:
            try:
                if random.random() < 0.8:  # 80% reads
                    client.run_cypher(
                        "MATCH (n:Node {id: $id})-[:REL]->(m) RETURN m LIMIT 10",
                        {"id": random.choice(start_ids)},
                    )
                else:  # 20% writes
                    client.run_cypher(
                        "MERGE (n:Node {id: $id}) SET n.touched = timestamp()",
                        {"id": f"synthetic_{random.randint(0, 10_000_000)}"},
                    )
                local_ops += 1
            except Exception:
                counters["errors"] += 1
        client.close()
        return local_ops

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for f in as_completed(futures):
            counters["ops"] += f.result()

    qps = counters["ops"] / MIXED_DURATION_SEC
    save_result(platform, f"mixed_c{concurrency}", {
        "concurrency": concurrency,
        "duration_sec": MIXED_DURATION_SEC,
        "total_ops": counters["ops"],
        "errors": counters["errors"],
        "queries_per_sec": round(qps, 2),
        "read_write_mix": "80/20",
    })


# ---------------------------------------------------------------------------
# ArangoDB (AQL). Schema mirrors the loader: nodes collection with `node_id`
# (hash-indexed), edges collection named `edges`.
# ---------------------------------------------------------------------------

def sample_start_ids_aql(client, n=SAMPLE_START_NODES):
    rows = client.run_aql(
        "FOR n IN nodes SORT RAND() LIMIT @n RETURN n.node_id", {"n": n}
    )
    return list(rows)


def traversals_aql(client, platform):
    start_ids = sample_start_ids_aql(client)
    for hops in (1, 2, 3):
        query = f"""
        FOR v IN {hops}..{hops} OUTBOUND @start_vertex edges
            COLLECT WITH COUNT INTO c
            RETURN c
        """

        def op():
            start_id = random.choice(start_ids)
            client.run_aql(query, {"start_vertex": f"nodes/{start_id}"})

        latencies = run_n_times(op, READ_ITERATIONS, warmup=10)
        save_result(platform, f"traversal_{hops}hop", summarize(latencies))


def lookups_aql(client, platform):
    start_ids = sample_start_ids_aql(client)

    def point_lookup():
        client.run_aql(
            "FOR n IN nodes FILTER n.node_id == @id RETURN n", {"id": random.choice(start_ids)}
        )

    latencies = run_n_times(point_lookup, READ_ITERATIONS, warmup=10)
    save_result(platform, "point_lookup", {**summarize(latencies), "indexed_properties": ["nodes.node_id"]})

    def filtered_lookup():
        prefix = str(random.choice(start_ids))[:2]
        client.run_aql(
            "FOR n IN nodes FILTER STARTS_WITH(n.node_id, @prefix) LIMIT 20 RETURN n",
            {"prefix": prefix},
        )

    latencies = run_n_times(filtered_lookup, READ_ITERATIONS, warmup=10)
    save_result(platform, "filtered_lookup", {**summarize(latencies), "indexed_properties": ["nodes.node_id"]})


def aggregation_aql(client, platform):
    def agg():
        client.run_aql("FOR e IN edges COLLECT WITH COUNT INTO c RETURN c")

    latencies = run_n_times(agg, READ_ITERATIONS, warmup=10)
    save_result(platform, "aggregation", summarize(latencies))


def mixed_workload_aql(client_factory, platform, concurrency):
    seed_client = client_factory()
    start_ids = sample_start_ids_aql(seed_client)
    seed_client.close()

    stop_at = time.perf_counter() + MIXED_DURATION_SEC
    counters = {"ops": 0, "errors": 0}

    def worker():
        client = client_factory()
        local_ops = 0
        while time.perf_counter() < stop_at:
            try:
                if random.random() < 0.8:
                    client.run_aql(
                        "FOR v IN 1..1 OUTBOUND @start_vertex edges LIMIT 10 RETURN v",
                        {"start_vertex": f"nodes/{random.choice(start_ids)}"},
                    )
                else:
                    doc_id = f"synthetic_{random.randint(0, 10_000_000)}"
                    client.run_aql(
                        "UPSERT { node_id: @id } INSERT { node_id: @id, touched: DATE_NOW() } "
                        "UPDATE { touched: DATE_NOW() } IN nodes",
                        {"id": doc_id},
                    )
                local_ops += 1
            except Exception:
                counters["errors"] += 1
        client.close()
        return local_ops

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for f in as_completed(futures):
            counters["ops"] += f.result()

    qps = counters["ops"] / MIXED_DURATION_SEC
    save_result(platform, f"mixed_c{concurrency}", {
        "concurrency": concurrency, "duration_sec": MIXED_DURATION_SEC,
        "total_ops": counters["ops"], "errors": counters["errors"],
        "queries_per_sec": round(qps, 2), "read_write_mix": "80/20",
    })


# ---------------------------------------------------------------------------
# JanusGraph (Gremlin). Schema mirrors the loader: vertices labeled "Node"
# with property `node_id`, edges labeled "REL".
# ---------------------------------------------------------------------------

def sample_start_ids_gremlin(client, n=SAMPLE_START_NODES):
    ids = client.run_gremlin(lambda g: g.V().hasLabel("Node").values("node_id").limit(n).toList())
    return ids


def traversals_gremlin(client, platform):
    start_ids = sample_start_ids_gremlin(client)
    for hops in (1, 2, 3):
        def build_traversal(g, start_id, h=hops):
            t = g.V().has("node_id", start_id)
            for _ in range(h):
                t = t.out("REL")
            return t.count().next()

        def op():
            client.run_gremlin(lambda g: build_traversal(g, random.choice(start_ids)))

        latencies = run_n_times(op, READ_ITERATIONS, warmup=10)
        save_result(platform, f"traversal_{hops}hop", summarize(latencies))


def lookups_gremlin(client, platform):
    start_ids = sample_start_ids_gremlin(client)

    def point_lookup():
        client.run_gremlin(lambda g: g.V().has("node_id", random.choice(start_ids)).elementMap().toList())

    latencies = run_n_times(point_lookup, READ_ITERATIONS, warmup=10)
    save_result(platform, "point_lookup", {**summarize(latencies), "indexed_properties": ["Node.node_id (composite index)"]})

    def filtered_lookup():
        prefix = str(random.choice(start_ids))[:2]
        client.run_gremlin(lambda g: g.V().has("node_id", TextP.startingWith(prefix)).limit(20).toList())

    latencies = run_n_times(filtered_lookup, READ_ITERATIONS, warmup=10)
    save_result(platform, "filtered_lookup", {**summarize(latencies), "indexed_properties": ["Node.node_id (composite index)"]})


def aggregation_gremlin(client, platform):
    def agg():
        client.run_gremlin(lambda g: g.E().hasLabel("REL").count().next())

    latencies = run_n_times(agg, READ_ITERATIONS, warmup=10)
    save_result(platform, "aggregation", summarize(latencies))


def mixed_workload_gremlin(client_factory, platform, concurrency):
    seed_client = client_factory()
    start_ids = sample_start_ids_gremlin(seed_client)
    seed_client.close()

    stop_at = time.perf_counter() + MIXED_DURATION_SEC
    counters = {"ops": 0, "errors": 0}

    def worker():
        client = client_factory()
        local_ops = 0
        while time.perf_counter() < stop_at:
            try:
                if random.random() < 0.8:
                    client.run_gremlin(
                        lambda g: g.V().has("node_id", random.choice(start_ids)).out("REL").limit(10).toList()
                    )
                else:
                    new_id = f"synthetic_{random.randint(0, 10_000_000)}"
                    client.run_gremlin(lambda g: g.addV("Node").property("node_id", new_id).next())
                local_ops += 1
            except Exception:
                counters["errors"] += 1
        client.close()
        return local_ops

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for f in as_completed(futures):
            counters["ops"] += f.result()

    qps = counters["ops"] / MIXED_DURATION_SEC
    save_result(platform, f"mixed_c{concurrency}", {
        "concurrency": concurrency, "duration_sec": MIXED_DURATION_SEC,
        "total_ops": counters["ops"], "errors": counters["errors"],
        "queries_per_sec": round(qps, 2), "read_write_mix": "80/20",
    })


BOLT_PLATFORMS = {"cognodb", "neo4j", "memgraph"}
WORKLOAD_FNS = {
    "bolt": (traversals_bolt, lookups_bolt, aggregation_bolt, mixed_workload_bolt),
    "arangodb": (traversals_aql, lookups_aql, aggregation_aql, mixed_workload_aql),
    "janusgraph": (traversals_gremlin, lookups_gremlin, aggregation_gremlin, mixed_workload_gremlin),
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True)
    args = parser.parse_args()

    if args.platform in BOLT_PLATFORMS:
        traversal_fn, lookup_fn, agg_fn, mixed_fn = WORKLOAD_FNS["bolt"]
    elif args.platform in WORKLOAD_FNS:
        traversal_fn, lookup_fn, agg_fn, mixed_fn = WORKLOAD_FNS[args.platform]
    else:
        print(f"[error] unknown platform {args.platform}")
        sys.exit(1)

    client = get_client(args.platform)
    traversal_fn(client, args.platform)
    lookup_fn(client, args.platform)
    agg_fn(client, args.platform)
    client.close()

    for c in CONCURRENCY_LEVELS:
        mixed_fn(lambda: get_client(args.platform), args.platform, c)

    print(f"[done] all workloads complete for {args.platform}")
