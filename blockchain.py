import hashlib
import json
import time
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


GAS_COST_PER_VOTE = 0.001
INITIAL_GAS_BALANCE = 1.0
CHAIN_FILE = "blockchain_data.json"


def save_blockchain(blockchain_instance):
    """Save blockchain to file for persistence"""
    data = {
        "chain": blockchain_instance.get_chain_json(),
        "pending_transactions": [
            tx.to_dict() for tx in blockchain_instance.pending_transactions
        ],
    }
    with open(CHAIN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_blockchain(blockchain_instance) -> bool:
    """Load blockchain from file if exists"""
    if not os.path.exists(CHAIN_FILE):
        return False

    try:
        with open(CHAIN_FILE, "r") as f:
            data = json.load(f)

        blockchain_instance.chain = []
        blockchain_instance.pending_transactions = []

        # Load blocks
        for block_data in data.get("chain", []):
            blockchain_instance.chain.append(
                Block(
                    index=block_data["index"],
                    timestamp=block_data["timestamp"],
                    transactions=block_data["transactions"],
                    previous_hash=block_data["previous_hash"],
                    nonce=block_data["nonce"],
                    hash=block_data["hash"],
                )
            )

        # Load pending transactions
        for tx_data in data.get("pending_transactions", []):
            blockchain_instance.pending_transactions.append(
                Transaction(
                    voter_id_hash=tx_data["voter_id_hash"],
                    candidate=tx_data["candidate"],
                    gas_used=tx_data["gas_used"],
                    timestamp=tx_data["timestamp"],
                    tx_hash=tx_data["tx_hash"],
                )
            )

        return True
    except Exception as e:
        print(f"Error loading blockchain: {e}")
        return False


@dataclass
class Transaction:
    voter_id_hash: str
    candidate: str
    gas_used: float
    timestamp: float
    tx_hash: str

    def __post_init__(self):
        if not self.tx_hash:
            self.tx_hash = self.calculate_tx_hash()

    def calculate_tx_hash(self) -> str:
        tx_data = f"{self.voter_id_hash}{self.candidate}{self.gas_used}{self.timestamp}"
        return hashlib.sha256(tx_data.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter_id_hash": self.voter_id_hash,
            "candidate": self.candidate,
            "gas_used": self.gas_used,
            "timestamp": self.timestamp,
            "tx_hash": self.tx_hash,
        }


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[Dict[str, Any]]
    previous_hash: str
    nonce: int
    hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }


class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.difficulty = 2
        self.votes_per_block = 5
        self.create_genesis_block()

    def create_genesis_block(self) -> Block:
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[],
            previous_hash="0",
            nonce=0,
            hash=self.calculate_hash(0, time.time(), [], "0", 0),
        )
        self.chain.append(genesis_block)
        return genesis_block

    @staticmethod
    def calculate_hash(
        index: int,
        timestamp: float,
        transactions: List[Dict[str, Any]],
        previous_hash: str,
        nonce: int,
    ) -> str:
        block_data = f"{index}{timestamp}{json.dumps(transactions, sort_keys=True)}{previous_hash}{nonce}"
        return hashlib.sha256(block_data.encode()).hexdigest()

    def get_last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, voter_id_hash: str, candidate: str) -> Transaction:
        gas_used = GAS_COST_PER_VOTE
        transaction = Transaction(
            voter_id_hash=voter_id_hash,
            candidate=candidate,
            gas_used=gas_used,
            timestamp=time.time(),
            tx_hash="",
        )
        self.pending_transactions.append(transaction)
        return transaction

    def mine_pending_transactions(self) -> Optional[Block]:
        if len(self.pending_transactions) < self.votes_per_block:
            return None

        transactions_to_mine = self.pending_transactions[: self.votes_per_block]
        last_block = self.get_last_block()

        new_block = self.create_block(
            transactions=[tx.to_dict() for tx in transactions_to_mine],
            previous_hash=last_block.hash,
        )

        self.pending_transactions = self.pending_transactions[self.votes_per_block :]
        self.chain.append(new_block)

        # Save to file for persistence
        save_blockchain(self)

        return new_block

    def mine_manual(self) -> Block:
        if not self.pending_transactions:
            raise ValueError("No pending transactions to mine")

        last_block = self.get_last_block()
        transactions_to_mine = self.pending_transactions[:]

        new_block = self.create_block(
            transactions=[tx.to_dict() for tx in transactions_to_mine],
            previous_hash=last_block.hash,
        )

        self.pending_transactions = []
        self.chain.append(new_block)

        # Save to file for persistence
        save_blockchain(self)

        return new_block

    def create_block(
        self, transactions: List[Dict[str, Any]], previous_hash: str
    ) -> Block:
        index = len(self.chain)
        timestamp = time.time()
        nonce = 0

        hash_val = self.calculate_hash(
            index, timestamp, transactions, previous_hash, nonce
        )

        while not self.is_valid_proof(
            index, timestamp, transactions, previous_hash, nonce, hash_val
        ):
            nonce += 1
            hash_val = self.calculate_hash(
                index, timestamp, transactions, previous_hash, nonce
            )

        return Block(
            index=index,
            timestamp=timestamp,
            transactions=transactions,
            previous_hash=previous_hash,
            nonce=nonce,
            hash=hash_val,
        )

    def is_valid_proof(
        self,
        index: int,
        timestamp: float,
        transactions: List[Dict[str, Any]],
        previous_hash: str,
        nonce: int,
        hash_val: str,
    ) -> bool:
        return hash_val[: self.difficulty] == "0" * self.difficulty

    def validate_chain(self) -> bool:
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.previous_hash != previous_block.hash:
                return False

            if current_block.hash != self.calculate_hash(
                current_block.index,
                current_block.timestamp,
                current_block.transactions,
                current_block.previous_hash,
                current_block.nonce,
            ):
                return False

        return True

    def get_chain_json(self) -> List[Dict[str, Any]]:
        return [block.to_dict() for block in self.chain]

    def get_transaction_by_hash(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("tx_hash") == tx_hash:
                    return tx

        for tx in self.pending_transactions:
            if tx.tx_hash == tx_hash:
                return tx.to_dict()

        return None

    def verify_vote(self, tx_hash: str) -> Dict[str, Any]:
        tx = self.get_transaction_by_hash(tx_hash)
        if tx:
            return {"valid": True, "transaction": tx}
        return {"valid": False, "transaction": None}

    def get_pending_count(self) -> int:
        return len(self.pending_transactions)

    def get_total_votes(self) -> int:
        return sum(len(block.transactions) for block in self.chain)


# Initialize blockchain and try to load from file
blockchain_instance = Blockchain()
if not load_blockchain(blockchain_instance):
    # If no file exists, create genesis block
    blockchain_instance.create_genesis_block()
