import unittest

from scripts import verify_server_global_repair as verifier


class VerifyServerGlobalRepairTests(unittest.TestCase):
    def test_flags_nodes_and_relationships_outside_kgnode_contract(self):
        self.assertIn("non_kgnode_node_count", verifier.QUERIES)
        self.assertIn("relation_touching_non_kgnode_count", verifier.QUERIES)
        self.assertIn("WHERE NOT n:KGNode", verifier.QUERIES["non_kgnode_node_count"])
        self.assertIn("WHERE NOT a:KGNode OR NOT b:KGNode", verifier.QUERIES["relation_touching_non_kgnode_count"])


if __name__ == "__main__":
    unittest.main()
