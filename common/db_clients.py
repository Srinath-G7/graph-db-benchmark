"""Thin per-platform client wrappers.

Every wrapper exposes the same small surface:
    .run_cypher(query, params) -> list[dict]     (Bolt/Cypher platforms)
    .run_aql(query, bind_vars) -> list[dict]      (ArangoDB)
    .run_gremlin(traversal_fn) -> list             (JanusGraph)
    .close()

Workload/loader code is written against these, not against the raw
drivers, so swapping platforms never means rewriting query logic.
CognoDB, Neo4j AuraDB, and Memgraph are all Bolt/Cypher-compatible, so
they share the same wrapper class.
"""
import os
from neo4j import GraphDatabase


class BoltClient:
    """Covers CognoDB, Neo4j AuraDB, and Memgraph -- all speak Bolt + Cypher."""

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password) if user else None)

    def run_cypher(self, query, params=None):
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    def close(self):
        self.driver.close()


class ArangoClient:
    def __init__(self, url, db_name, user, password):
        from arango import ArangoClient as _ArangoClient
        self._client = _ArangoClient(hosts=url)
        sys_db = self._client.db("_system", username=user, password=password)
        if not sys_db.has_database(db_name):
            sys_db.create_database(db_name)
        self.db = self._client.db(db_name, username=user, password=password)

    def run_aql(self, query, bind_vars=None):
        cursor = self.db.aql.execute(query, bind_vars=bind_vars or {})
        return list(cursor)

    def close(self):
        pass  # python-arango has no persistent connection to close


class JanusGraphClient:
    def __init__(self, url):
        from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
        from gremlin_python.driver.serializer import GraphSONSerializersV3d0
        from gremlin_python.process.anonymous_traversal import traversal
        self._conn = DriverRemoteConnection(url, "g", message_serializer=GraphSONSerializersV3d0())
        self.g = traversal().withRemote(self._conn)

    def run_gremlin(self, traversal_fn):
        """traversal_fn: callable taking self.g and returning a terminated traversal, e.g.
        lambda g: g.V().has('id', 42).out('KNOWS').limit(10).toList()
        """
        return traversal_fn(self.g)

    def close(self):
        self._conn.close()


def get_client(platform: str):
    """Factory: builds the right client from env vars for a given platform name.
    platform in {"cognodb", "neo4j", "memgraph", "arangodb", "janusgraph"}
    """
    platform = platform.lower()
    if platform == "cognodb":
        return BoltClient(os.environ["COGNODB_URI"], os.environ["COGNODB_USER"], os.environ["COGNODB_PASSWORD"])
    if platform == "neo4j":
        return BoltClient(os.environ["NEO4J_URI"], os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    if platform == "memgraph":
        return BoltClient(
            os.environ["MEMGRAPH_URI"],
            os.environ.get("MEMGRAPH_USER") or None,
            os.environ.get("MEMGRAPH_PASSWORD") or None,
        )
    if platform == "arangodb":
        return ArangoClient(
            os.environ["ARANGO_URL"], os.environ["ARANGO_DB"],
            os.environ["ARANGO_USER"], os.environ["ARANGO_PASSWORD"],
        )
    if platform == "janusgraph":
        return JanusGraphClient(os.environ["JANUSGRAPH_URL"])
    raise ValueError(f"Unknown platform: {platform}")
