import os
import json
import hashlib
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


class Block:
    def __init__(self, index, timestamp, prev_hash, transactions, signer_pub_hex, signature_hex, block_hash):
        self.index = index
        self.timestamp = timestamp
        self.prev_hash = prev_hash
        self.transactions = transactions
        self.signer_pub = signer_pub_hex
        self.signature = signature_hex
        self.hash = block_hash

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "transactions": self.transactions,
            "signer_pub": self.signer_pub,
            "signature": self.signature,
            "hash": self.hash,
        }


class Blockchain:
    """Simple append-only blockchain for audit entries.

    - Each block contains a small list of transactions (dicts).
    - Blocks are signed with an Ed25519 keypair persisted under the provided directory.
    - Chain is stored as JSON at `<dir>/chain.json` and key at `<dir>/key.pem`.
    """

    def __init__(self, path_dir):
        self.path_dir = path_dir
        os.makedirs(self.path_dir, exist_ok=True)
        self.chain_file = os.path.join(self.path_dir, "chain.json")
        self.key_file = os.path.join(self.path_dir, "key.pem")

        self._load_or_create_key()
        self.chain = self._load_chain()

    def _load_or_create_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                data = f.read()
                self._priv = serialization.load_pem_private_key(data, password=None)
        else:
            self._priv = Ed25519PrivateKey.generate()
            pem = self._priv.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(self.key_file, "wb") as f:
                f.write(pem)

        self.pub = self._priv.public_key()

    def _load_chain(self):
        if not os.path.exists(self.chain_file):
            # genesis block
            genesis = self._create_block([], prev_hash="0" * 64, index=0)
            self._save_chain([genesis.to_dict()])
            return [genesis]

        with open(self.chain_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Block(b["index"], b["timestamp"], b["prev_hash"], b["transactions"], b["signer_pub"], b["signature"], b["hash"]) for b in raw]

    def _save_chain(self, chain_list):
        with open(self.chain_file, "w", encoding="utf-8") as f:
            json.dump(chain_list, f, indent=2)

    def _transactions_hash(self, transactions):
        j = json.dumps(transactions, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(j.encode("utf-8")).hexdigest()

    def _block_hash(self, index, timestamp, prev_hash, tx_hash):
        payload = f"{index}|{timestamp}|{prev_hash}|{tx_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _create_block(self, transactions, prev_hash, index=None):
        idx = index if index is not None else (self.chain[-1].index + 1 if self.chain else 1)
        ts = str(datetime.now(timezone.utc))
        tx_hash = self._transactions_hash(transactions)
        block_hash = self._block_hash(idx, ts, prev_hash, tx_hash)

        # sign hash
        sig = self._priv.sign(block_hash.encode("utf-8"))
        sig_hex = sig.hex()

        pub_bytes = self.pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        pub_hex = pub_bytes.hex()

        return Block(idx, ts, prev_hash, transactions, pub_hex, sig_hex, block_hash)

    def add_block(self, transactions):
        prev_hash = self.chain[-1].hash if self.chain else "0" * 64
        block = self._create_block(transactions, prev_hash)
        self.chain.append(block)
        # persist
        self._save_chain([b.to_dict() for b in self.chain])
        return block.to_dict()

    def validate(self):
        """Validate chain integrity and signatures. Returns (valid:bool, message:str)."""
        for i in range(1, len(self.chain)):
            cur = self.chain[i]
            prev = self.chain[i - 1]
            # check prev hash link
            if cur.prev_hash != prev.hash:
                return False, f"Invalid prev_hash at index {cur.index}"

            # recompute block hash
            tx_hash = self._transactions_hash(cur.transactions)
            expected = self._block_hash(cur.index, cur.timestamp, cur.prev_hash, tx_hash)
            if expected != cur.hash:
                return False, f"Hash mismatch at index {cur.index}"

            # verify signature
            pub_bytes = bytes.fromhex(cur.signer_pub)
            sig = bytes.fromhex(cur.signature)
            pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
            try:
                pub.verify(sig, cur.hash.encode("utf-8"))
            except Exception:
                return False, f"Invalid signature at index {cur.index}"

        return True, "chain valid"
