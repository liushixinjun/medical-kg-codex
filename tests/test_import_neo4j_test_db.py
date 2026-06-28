import unittest
import urllib.error
from unittest.mock import patch

from scripts import import_neo4j_test_db as importer


class FakeNeo4jClient:
    def __init__(self):
        self.calls = []
        self.delete_batches = [2, 1, 0]

    def run(self, statement, parameters=None):
        self.calls.append((statement, parameters or {}))
        if "RETURN node_count" in statement and "AS relation_count" in statement:
            return {"results": [{"data": [{"row": [3, 5]}]}]}
        if "DETACH DELETE n" in statement:
            deleted = self.delete_batches.pop(0)
            return {"results": [{"data": [{"row": [deleted]}]}]}
        return {"results": [{"data": [{"row": [1]}]}]}


class FakeLabelAuditClient:
    def __init__(self):
        self.calls = []

    def run(self, statement, parameters=None):
        self.calls.append((statement, parameters or {}))
        return {"results": [{"data": [{"row": [3, 0, 2]}]}]}


class ImportNeo4jTestDbTests(unittest.TestCase):
    def test_count_kg_subgraph_counts_only_kgnode_scope(self):
        client = FakeNeo4jClient()

        counts = importer.count_kg_subgraph(client)

        self.assertEqual(counts, {"node_count": 3, "relation_count": 5})
        statement = client.calls[0][0]
        self.assertIn("MATCH (n:KGNode)", statement)
        self.assertIn("OPTIONAL MATCH (n)-[r]-()", statement)

    def test_replace_kg_subgraph_detach_deletes_until_empty(self):
        client = FakeNeo4jClient()

        deleted = importer.replace_kg_subgraph(client, batch_size=1000)

        self.assertEqual(deleted, 3)
        delete_calls = [call for call in client.calls if "DETACH DELETE n" in call[0]]
        self.assertEqual(len(delete_calls), 3)
        self.assertEqual(delete_calls[0][1], {"batch_size": 1000})

    def test_import_nodes_uses_canonical_kgnode_first_label_contract(self):
        client = FakeNeo4jClient()
        nodes = [
            {
                "id": "N1",
                "code": "DIS-HCM",
                "name": "肥厚型心肌病",
                "entityType": "Disease",
            }
        ]

        imported = importer.import_nodes(client, nodes, batch_size=100)

        self.assertEqual(imported, 1)
        statement, parameters = client.calls[0]
        self.assertIn("MERGE (n:KGNode:`Disease` {code: row.code})", statement)
        self.assertNotIn("SET n:`Disease`", statement)
        props = parameters["rows"][0]["props"]
        self.assertEqual(props["primary_label"], "KGNode")
        self.assertEqual(props["type_label"], "Disease")
        self.assertEqual(props["canonical_labels"], ["KGNode", "Disease"])

    def test_audit_label_metadata_separates_canonical_metadata_from_raw_label_order(self):
        client = FakeLabelAuditClient()

        audit = importer.audit_label_metadata(client)

        self.assertEqual(
            audit,
            {
                "total_kg_node_count": 3,
                "canonical_label_metadata_mismatch_count": 0,
                "raw_label_order_differs_count": 2,
            },
        )
        statement = client.calls[0][0]
        self.assertIn("n.canonical_labels = ['KGNode', n.entityType]", statement)
        self.assertIn("labels(n) = ['KGNode', n.entityType]", statement)

    def test_http_client_retries_transient_url_errors(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"results":[{"data":[{"row":[1]}]}],"errors":[]}'

        client = importer.Neo4jHttpClient(
            "http://neo4j.local:7474",
            "neo4j",
            "password",
            "neo4j",
            max_retries=1,
            retry_delay_seconds=0,
        )

        with patch(
            "scripts.import_neo4j_test_db.urllib.request.urlopen",
            side_effect=[urllib.error.URLError(TimeoutError("timeout")), FakeResponse()],
        ) as urlopen:
            result = client.run("RETURN 1 AS ok")

        self.assertEqual(result["results"][0]["data"][0]["row"], [1])
        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
