import unittest

from scripts.import_neo4j_delta import plan_delta_relation_actions
from scripts.import_neo4j_delta import validate_delta_nodes
from scripts.import_neo4j_delta import validate_delta_relations


class ImportNeo4jDeltaTests(unittest.TestCase):
    def test_rejects_duplicate_semantic_keys_in_delta_input(self):
        relations = [
            {"id": "REL-1", "source_code": "DIS-1", "relationType": "treated_by_medication", "target_code": "MED-1"},
            {"id": "REL-2", "source_code": "DIS-1", "relationType": "treated_by_medication", "target_code": "MED-1"},
        ]
        with self.assertRaisesRegex(ValueError, "Duplicate semantic key"):
            validate_delta_relations(relations)

    def test_rejects_delta_relation_marked_formal_cdss_ready(self):
        relations = [
            {
                "id": "REL-1",
                "source_code": "DIS-1",
                "relationType": "treated_by_medication",
                "target_code": "MED-1",
                "formal_cdss_ready": True,
            }
        ]
        with self.assertRaisesRegex(ValueError, "formal_cdss_ready"):
            validate_delta_relations(relations)

    def test_rejects_duplicate_node_codes_and_formal_ready_nodes(self):
        with self.assertRaisesRegex(ValueError, "Duplicate node code"):
            validate_delta_nodes(
                [
                    {"code": "N-1", "entityType": "Disease"},
                    {"code": "N-1", "entityType": "Disease"},
                ]
            )
        with self.assertRaisesRegex(ValueError, "formal_cdss_ready"):
            validate_delta_nodes([{"code": "N-2", "entityType": "Disease", "formal_cdss_ready": True}])

    def test_plans_create_update_and_replace_by_semantic_key(self):
        relations = [
            {"id": "REL-NEW", "source_code": "DIS-1", "relationType": "treated_by_medication", "target_code": "MED-1"},
            {"id": "REL-SAME", "source_code": "DIS-2", "relationType": "treated_by_medication", "target_code": "MED-2"},
            {"id": "REL-STANDARD", "source_code": "DIS-3", "relationType": "treated_by_medication", "target_code": "MED-3"},
        ]
        server_rows = [
            {"source_code": "DIS-1", "relationType": "treated_by_medication", "target_code": "MED-1", "existing_relation_ids": [], "existing_count": 0},
            {"source_code": "DIS-2", "relationType": "treated_by_medication", "target_code": "MED-2", "existing_relation_ids": ["REL-SAME"], "existing_count": 1},
            {"source_code": "DIS-3", "relationType": "treated_by_medication", "target_code": "MED-3", "existing_relation_ids": [None], "existing_count": 1},
        ]

        actions = plan_delta_relation_actions(relations, server_rows)

        self.assertEqual(actions[0]["action"], "create")
        self.assertEqual(actions[1]["action"], "update")
        self.assertEqual(actions[2]["action"], "replace_semantic_edge")


if __name__ == "__main__":
    unittest.main()
