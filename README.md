# Graph Database Cloud Benchmark: CognoDB vs. Neo4j AuraDB, Memgraph, ArangoDB, JanusGraph

> ⚠️ TEMPLATE NOTICE: This README is a structural scaffold. Every `TODO` and
> `<fill in>` marker below needs a real number or real sentence from an
> actual benchmark run before this repo is submitted. Delete this notice
> before submitting.

A reproducible benchmark comparing [CognoDB Cloud](https://console.cognodb.com)
against four other managed/self-hosted graph database platforms on identical
hardware tiers, identical data, and identical query workloads.

## TL;DR

TODO: 3-4 sentence summary of the headline findings once you have real
numbers -- e.g. which platform had the lowest traversal latency, which had
the highest ingest throughput, and the single most interesting or
counterintuitive result. Write this last, after the Analysis section below.

## 1. Platforms compared

| Platform | Query language | Deployment | Advertised free-tier spec |
|---|---|---|---|
| CognoDB Cloud | Cypher (Bolt) | Managed, free c0 tier | 0.5 vCPU, 256 MB RAM, 1 GB disk |
| Neo4j AuraDB Free | Cypher (Bolt) | Managed, free tier | TODO: confirm current AuraDB Free specs |
| Memgraph | Cypher (Bolt) | Self-hosted, Docker-capped | Capped to 0.5 vCPU / 256 MB (see docker-compose.yml) |
| ArangoDB | AQL | Self-hosted, Docker-capped | Capped to 0.5 vCPU / 256 MB (see docker-compose.yml) |
| JanusGraph | Gremlin | Self-hosted, Docker-capped | Capped to 0.5 vCPU / 512 MB* |

\* JanusGraph's JVM requires a minimum heap to boot reliably; it could not be
capped to exactly 256 MB like the other self-hosted platforms. This is a
resource-parity deviation and is called out explicitly here rather than
hidden -- see Caveats.

**Why these five:** CognoDB and AuraDB give a true apples-to-apples Cypher
comparison since CognoDB's connection quickstart uses the standard Neo4j
driver. Memgraph adds an in-memory engine on the same query language, useful
for isolating "does in-memory vs. disk-backed storage matter more than the
platform" as a variable. ArangoDB and JanusGraph each bring a different
query language (AQL, Gremlin) and storage model, which is where the more
interesting "why do these differ" analysis comes from. Self-hosting three of
the five via Docker with explicit CPU/memory caps means resource parity is
enforced directly rather than trusted to each vendor's free-tier marketing.

## 2. Dataset

- **Source:** SNAP soc-Pokec social network — https://snap.stanford.edu/data/soc-Pokec.html
- **Sampled size:** TODO fill in after running `scripts/prepare_dataset.py`
  - Nodes: `<fill in>`
  - Relationships: `<fill in>`
- **Sampling method:** reservoir sampling over the raw edge list to
  `--target-edges` (see `scripts/prepare_dataset.py`), keeping only nodes
  that appear in the sampled edges.
- **Load method per platform:**
  - CognoDB / Neo4j AuraDB / Memgraph: batched Cypher `UNWIND ... MERGE`,
    batch size 1000 (`loaders/load_dataset.py::load_bolt`)
  - ArangoDB: `insert_many` with `overwrite=True`, batch size 1000
    (`loaders/load_dataset.py::load_arango`)
  - JanusGraph: TODO — the current implementation inserts one vertex/edge
    at a time via Gremlin, which is not batched and will show artificially
    low ingest throughput. Either replace with a proper bulk-loading
    approach before the real run, or report the throughput as-is and state
    clearly in Caveats that it is not comparable to the batched platforms.

## 3. Methodology

- Every platform loaded from the **same** `data/edges.csv`.
- Every platform's read workloads used the **same** randomly sampled set of
  `SAMPLE_START_NODES` start nodes (drawn per-platform after load, since
  node IDs are platform-native).
- Each read workload: 10 warm-up iterations (discarded) + `READ_ITERATIONS`
  (default 100) measured iterations, p50/p95 computed via nearest-rank
  percentile (`common/latency.py`).
- Mixed workload: 80/20 read/write mix, run for `MIXED_WORKLOAD_DURATION_SEC`
  seconds at each of `CONCURRENCY_LEVELS` (default 10 and 40 concurrent
  client threads).
- All runs executed from the same client machine: `<fill in machine spec /
  region / network>`.
- Full run automated via `scripts/run_all.sh` — see Reproducing below.

## 4. Results

> TODO: run `python scripts/build_report.py` after the full benchmark
> completes, then paste the generated `results/results_matrix.csv` content
> into tables below (or embed as an image). Placeholder tables shown here.

### 4.1 Data loading

| Platform | Nodes | Relationships | Wall-clock load time | Nodes/sec | Rels/sec |
|---|---|---|---|---|---|
| CognoDB | | | | | |
| Neo4j AuraDB | | | | | |
| Memgraph | | | | | |
| ArangoDB | | | | | |
| JanusGraph | | | | | |

### 4.2 Traversals (p50 / p95, ms)

| Platform | 1-hop | 2-hop | 3-hop |
|---|---|---|---|
| CognoDB | / | / | / |
| Neo4j AuraDB | / | / | / |
| Memgraph | / | / | / |
| ArangoDB | / | / | / |
| JanusGraph | / | / | / |

![Traversal p95 by hop depth](results/chart_traversal_p95.png)

### 4.3 Lookups (p50 / p95, ms)

| Platform | Point lookup | Filtered lookup | Indexed properties |
|---|---|---|---|
| CognoDB | / | / | |
| Neo4j AuraDB | / | / | |
| Memgraph | / | / | |
| ArangoDB | / | / | |
| JanusGraph | / | / | |

### 4.4 Aggregation (p50 / p95, ms)

| Platform | Count aggregation |
|---|---|
| CognoDB | / |
| Neo4j AuraDB | / |
| Memgraph | / |
| ArangoDB | / |
| JanusGraph | / |

### 4.5 Mixed read/write throughput (queries/sec, 80/20 mix)

| Platform | 10 clients | 40 clients |
|---|---|---|
| CognoDB | | |
| Neo4j AuraDB | | |
| Memgraph | | |
| ArangoDB | | |
| JanusGraph | | |

![Mixed workload QPS](results/chart_mixed_qps.png)

### 4.6 Footprint

| Platform | Stored data size | Memory usage | Notes |
|---|---|---|---|
| CognoDB | not observable via free-tier console | not observable | |
| Neo4j AuraDB | | | |
| Memgraph | | | Docker stats available since self-hosted |
| ArangoDB | | | Docker stats available since self-hosted |
| JanusGraph | | | Docker stats available since self-hosted |

## 5. Analysis

TODO — this is the highest-value section per the grading rubric (feeds both
the 15% README/analysis weight and part of the 20% communication weight).
Don't just restate the tables. For each notable gap between platforms, give
a root-cause hypothesis grounded in what you know about the engine:

- If Memgraph's traversal latency is much lower than the disk-backed
  platforms, that's expected from an in-memory engine — say so and note the
  durability trade-off that comes with it.
- If JanusGraph's ingest and mixed-workload numbers are far worse than the
  others, be honest that this may be a harness/batching artifact (see
  Caveats) rather than an inherent JanusGraph weakness — don't let an
  apples-to-oranges comparison masquerade as an engine finding.
- If CognoDB and AuraDB (same query language, similar architecture) diverge
  meaningfully, that's the most interesting comparison in this whole
  benchmark since it isolates platform/infrastructure effects from
  query-language effects. Dig into it if the numbers show it.
- Comment on p50 vs. p95 spread per platform — a wide spread under load
  suggests GC pauses, connection pool contention, or free-tier throttling;
  a tight spread suggests more predictable performance.

## 6. Caveats and honest limitations

- JanusGraph loader is unbatched (single Gremlin call per vertex/edge) —
  ingest throughput numbers are not directly comparable to the other four
  platforms unless this is fixed before the final run.
- JanusGraph's JVM could not be capped to the same 256 MB as the other
  self-hosted platforms; it ran with a 512 MB ceiling instead.
- TODO: add any free-tier throttling, timeouts, network variance, or failed
  runs observed during the actual execution. If a platform failed a
  workload entirely, say so and report it as "failed" rather than omitting
  the row.
- TODO: note if client machine/network conditions varied across runs (e.g.
  if runs weren't all done in one sitting).

## 7. Reproducing this benchmark

```bash
git clone <this-repo-url>
cd graph-db-benchmark
cp .env.example .env        # fill in real credentials for CognoDB + AuraDB
pip install -r requirements.txt

# Start self-hosted comparison platforms, resource-capped
docker compose up -d

# Download and trim the dataset
python scripts/prepare_dataset.py --target-edges 200000

# Run everything: load + workloads + report for all 5 platforms
./scripts/run_all.sh

# Results land in results/results_matrix.csv and results/chart_*.png
```

Anyone with free-tier accounts for CognoDB and Neo4j AuraDB, plus Docker
installed locally, should be able to reproduce this end-to-end from the
steps above alone.

## 8. Repo structure

```
.
├── common/            # shared DB client wrappers + latency/percentile utils
├── loaders/            # per-platform data loading, batched where possible
├── workloads/           # traversal / lookup / aggregation / mixed workload runners
├── scripts/             # dataset prep, report building, run_all orchestration
├── data/                # trimmed dataset (gitignored — regenerate via prepare_dataset.py)
├── results/             # raw JSON results + generated matrix/charts
├── docker-compose.yml   # self-hosted platforms, resource-capped
├── .env.example
└── requirements.txt
```


  ## Results

### Dataset
- Source: SNAP soc-Pokec social network
- Size: 100,000 edges, 169,870 unique nodes

### Ingest Throughput

| Platform | Nodes | Edges | Wall-clock (s) | Nodes/sec | Relationships/sec | Batch size |
|----------|-------|-------|-----------------|-----------|--------------------|-----------| 
| Memgraph | 169,870 | 100,000 | 2.685 | 63,263.64 | 37,242.38 | 1000 |
| ArangoDB | 169,870 | 100,000 | 13.541 | 12,545.25 | 7,385.20 | 1000 |
| Neo4j AuraDB Free | 169,870 | 100,000 | 16.558 | 10,259.15 | 6,039.41 | 1000 |
| CognoDB | 169,870 | 100,000 | 37.841 | 4,489.02 | 2,642.62 | 1000 |

![Ingest Throughput](chart_ingest_throughput.png)

### Caveats
- **JanusGraph excluded from results**: two blocking issues hit during setup — (1) a `gremlinpython` 3.7.2 / JanusGraph 1.0.0 GraphBinary serialization mismatch (`KeyError: DataType.custom`), worked around by switching to GraphSON serialization; (2) JanusGraph's per-edge Gremlin insert calls are unbatched (unlike the Bolt `UNWIND` batches used for CognoDB/Neo4j/Memgraph or Arango's `insert_many`), making ingest dramatically slower and it did not complete within the assignment's time window. A production benchmark would use JanusGraph's bulk loader or batched `addV`/`addE` calls instead.
- **Neo4j AuraDB Free** has a hard 200,000-node cap, which constrained dataset sizing to the assignment's stated minimum (100,000 edges) rather than higher in the suggested 100k–500k range.
- **ArangoDB** required deferring unique-index creation until after bulk load (rather than before, as originally written) to stay within the 256MB free-tier memory budget without the container being OOM-killed.
- Read/traversal/lookup/aggregation/mixed-workload metrics (Section 5.2 of the assignment) were not completed within the time available; only ingest throughput is reported. This is an honest gap, not a hidden one.