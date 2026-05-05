import os
import json
import hashlib
import re
import threading
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
    """Simple append-only blockchain for integrity entries.

    - Each block contains a small list of transactions (dicts).
    - Blocks are signed with an Ed25519 keypair persisted under the provided directory.
    - Chain is stored as JSON at `<dir>/chain.json` and key at `<dir>/key.pem`.
    """

    def __init__(self, path_dir):
        self.path_dir = path_dir
        os.makedirs(self.path_dir, exist_ok=True)
        self.chain_file = os.path.join(self.path_dir, "chain.json")
        self.key_file = os.path.join(self.path_dir, "key.pem")
        self._chain_lock = threading.Lock()  # Serialize all blockchain modifications

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

    def _refresh_chain_from_disk(self):
        self.chain = self._load_chain()

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
        """Add a block to the chain in a thread-safe manner."""
        with self._chain_lock:
            self._refresh_chain_from_disk()
            prev_hash = self.chain[-1].hash if self.chain else "0" * 64
            block = self._create_block(transactions, prev_hash)
            self.chain.append(block)
            # persist
            self._save_chain([b.to_dict() for b in self.chain])
            return block.to_dict()

    @staticmethod
    def _normalize_evidence_id(evidence_id):
        if isinstance(evidence_id, bool):
            raise ValueError("evidence_id must be an integer")
        try:
            normalized = int(evidence_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("evidence_id must be an integer") from exc
        if normalized <= 0:
            raise ValueError("evidence_id must be greater than zero")
        return normalized

    @staticmethod
    def _normalize_sha256_hex(sha256_hash):
        if not isinstance(sha256_hash, str):
            raise ValueError("sha256 hash must be a string")
        normalized = sha256_hash.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("sha256 hash must be a 64-character hex string")
        return normalized

    def _get_evidence_hash_unlocked(self, normalized_evidence_id):
        for block in reversed(self.chain):
            for tx in reversed(block.transactions):
                if tx.get("type") == "evidence_hash_store" and tx.get("evidence_id") == normalized_evidence_id:
                    return tx.get("sha256")
        return None

    def store_evidence_hash(self, evidence_id, sha256_hash):
        """
        Store a SHA-256 hash for a specific evidence ID on the local blockchain.

        Mirrors smart-contract behavior:
        - evidence_id can be stored only once
        - hash must be a canonical 64-character hex string
        """
        normalized_evidence_id = self._normalize_evidence_id(evidence_id)
        normalized_hash = self._normalize_sha256_hex(sha256_hash)

        with self._chain_lock:
            self._refresh_chain_from_disk()
            if self._get_evidence_hash_unlocked(normalized_evidence_id) is not None:
                raise ValueError(f"evidence_id {normalized_evidence_id} is already anchored")

            tx = {
                "type": "evidence_hash_store",
                "evidence_id": normalized_evidence_id,
                "sha256": normalized_hash,
            }
            prev_hash = self.chain[-1].hash if self.chain else "0" * 64
            block = self._create_block([tx], prev_hash)
            self.chain.append(block)
            self._save_chain([b.to_dict() for b in self.chain])
            return {
                "block_index": block.index,
                "block_hash": block.hash,
                "evidence_id": normalized_evidence_id,
                "sha256": normalized_hash,
            }

    def get_evidence_hash(self, evidence_id):
        normalized_evidence_id = self._normalize_evidence_id(evidence_id)
        with self._chain_lock:
            self._refresh_chain_from_disk()
            return self._get_evidence_hash_unlocked(normalized_evidence_id)

    def has_evidence_hash(self, evidence_id):
        return self.get_evidence_hash(evidence_id) is not None

    def verify_evidence_hash(self, evidence_id, sha256_hash):
        normalized_evidence_id = self._normalize_evidence_id(evidence_id)
        normalized_hash = self._normalize_sha256_hex(sha256_hash)
        with self._chain_lock:
            self._refresh_chain_from_disk()
            stored_hash = self._get_evidence_hash_unlocked(normalized_evidence_id)
        if stored_hash is None:
            return False
        return stored_hash == normalized_hash

    def validate(self):
        """Validate chain integrity and signatures. Returns (valid:bool, message:str)."""
        with self._chain_lock:
            try:
                self._refresh_chain_from_disk()
            except Exception as exc:
                return False, f"Unable to load chain: {exc}"

            chain_snapshot = list(self.chain)

        if not chain_snapshot:
            return False, "Chain is empty"

        genesis = chain_snapshot[0]
        if genesis.index != 0:
            return False, "Invalid genesis index"
        if genesis.prev_hash != "0" * 64:
            return False, "Invalid genesis prev_hash"

        tx_hash = self._transactions_hash(genesis.transactions)
        expected = self._block_hash(genesis.index, genesis.timestamp, genesis.prev_hash, tx_hash)
        if expected != genesis.hash:
            return False, "Hash mismatch at index 0"

        pub_bytes = bytes.fromhex(genesis.signer_pub)
        sig = bytes.fromhex(genesis.signature)
        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        try:
            pub.verify(sig, genesis.hash.encode("utf-8"))
        except Exception:
            return False, "Invalid signature at index 0"

        for i in range(1, len(chain_snapshot)):
            cur = chain_snapshot[i]
            prev = chain_snapshot[i - 1]
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
