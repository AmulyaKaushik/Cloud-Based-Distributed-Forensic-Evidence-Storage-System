import unittest
import os
import json
import tempfile
import shutil
from blockchain import Blockchain, Block


class TestBlock(unittest.TestCase):
    def test_block_to_dict(self):
        block = Block(
            index=0,
            timestamp="2025-05-03T12:00:00",
            prev_hash="0" * 64,
            transactions=[{"action": "test"}],
            signer_pub_hex="abcd1234",
            signature_hex="sig1234",
            block_hash="hash1234"
        )
        d = block.to_dict()
        self.assertEqual(d["index"], 0)
        self.assertEqual(d["timestamp"], "2025-05-03T12:00:00")
        self.assertEqual(d["prev_hash"], "0" * 64)
        self.assertEqual(d["signer_pub"], "abcd1234")


class TestBlockchain(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_blockchain_init(self):
        bc = Blockchain(self.temp_dir)
        self.assertIsNotNone(bc)
        self.assertEqual(len(bc.chain), 1)  # genesis block
        self.assertEqual(bc.chain[0].index, 0)

    def test_blockchain_adds_block(self):
        bc = Blockchain(self.temp_dir)
        tx = {"action": "test", "value": 123}
        block_dict = bc.add_block([tx])
        self.assertEqual(block_dict["index"], 1)
        self.assertEqual(len(bc.chain), 2)
        self.assertEqual(block_dict["transactions"], [tx])

    def test_blockchain_persists_to_disk(self):
        bc = Blockchain(self.temp_dir)
        bc.add_block([{"action": "test"}])
        chain_file = os.path.join(self.temp_dir, "chain.json")
        self.assertTrue(os.path.exists(chain_file))

    def test_blockchain_loads_from_disk(self):
        bc1 = Blockchain(self.temp_dir)
        bc1.add_block([{"action": "test1"}])
        bc1.add_block([{"action": "test2"}])

        # Create a new instance from same directory
        bc2 = Blockchain(self.temp_dir)
        self.assertEqual(len(bc2.chain), 3)  # genesis + 2 added
        self.assertEqual(bc2.chain[1].transactions, [{"action": "test1"}])
        self.assertEqual(bc2.chain[2].transactions, [{"action": "test2"}])

    def test_key_persistence(self):
        bc1 = Blockchain(self.temp_dir)
        pub_hex_1 = bc1.chain[0].signer_pub

        bc2 = Blockchain(self.temp_dir)
        pub_hex_2 = bc2.chain[0].signer_pub

        # Same public key should be used
        self.assertEqual(pub_hex_1, pub_hex_2)

    def test_blockchain_validate_valid_chain(self):
        bc = Blockchain(self.temp_dir)
        bc.add_block([{"action": "test"}])
        bc.add_block([{"action": "test2"}])

        valid, msg = bc.validate()
        self.assertTrue(valid)
        self.assertIn("valid", msg.lower())

    def test_blockchain_validate_detects_tampering(self):
        bc = Blockchain(self.temp_dir)
        bc.add_block([{"action": "test"}])

        # Tamper with a block's transaction
        bc.chain[1].transactions[0]["action"] = "tampered"

        valid, msg = bc.validate()
        self.assertFalse(valid)

    def test_blockchain_signature_verification(self):
        bc = Blockchain(self.temp_dir)
        tx = {"username": "alice", "action": "UPLOAD"}
        block_dict = bc.add_block([tx])

        # Check that signature exists and is non-empty
        self.assertIn("signature", block_dict)
        self.assertTrue(len(block_dict["signature"]) > 0)

        # Validate should pass
        valid, _ = bc.validate()
        self.assertTrue(valid)

    def test_blockchain_prev_hash_link(self):
        bc = Blockchain(self.temp_dir)
        genesis = bc.chain[0]

        bc.add_block([{"action": "test"}])
        block1 = bc.chain[1]

        # Block 1's prev_hash should equal genesis's hash
        self.assertEqual(block1.prev_hash, genesis.hash)

    def test_blockchain_multiple_transactions_in_block(self):
        bc = Blockchain(self.temp_dir)
        txs = [
            {"username": "alice", "action": "UPLOAD"},
            {"username": "bob", "action": "VERIFY"},
            {"username": "charlie", "action": "DOWNLOAD"},
        ]
        block_dict = bc.add_block(txs)
        self.assertEqual(block_dict["transactions"], txs)


if __name__ == "__main__":
    unittest.main()
