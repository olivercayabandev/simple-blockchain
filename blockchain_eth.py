import os
import json
from typing import Dict, Any, List, Optional
from web3 import Web3
from eth_account import Account
from web3.contract import ContractFunction
import time

# Sepolia Testnet RPC URL (use your own from Infura/Alchemy or public RPC)
SEPOLIA_RPC_URL = "https://rpc.sepolia.org"

# Ganache/Hardhat local URL (for local testing)
LOCAL_RPC_URL = "http://127.0.0.1:8545"

# Use local by default, change to SEPOLIA_RPC_URL for testnet
GANACHE_URL = LOCAL_RPC_URL

# Contract address file
CONTRACT_ADDRESS_FILE = os.path.join(os.path.dirname(__file__), "contract_address.txt")

# ABI - will be generated after compilation
CONTRACT_ABI = [
    {"inputs": [], "stateMutability": "nonpayable", "type": "constructor"},
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "uint256",
                "name": "id",
                "type": "uint256",
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "name",
                "type": "string",
            },
        ],
        "name": "CandidateAdded",
        "type": "event",
    },
    {"anonymous": False, "inputs": [], "name": "ElectionStarted", "type": "event"},
    {"anonymous": False, "inputs": [], "name": "ElectionStopped", "type": "event"},
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "voter",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "string",
                "name": "fullName",
                "type": "string",
            },
        ],
        "name": "VoterRegistered",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "voter",
                "type": "address",
            },
            {
                "indexed": True,
                "internalType": "uint256",
                "name": "candidateId",
                "type": "uint256",
            },
        ],
        "name": "VoteCast",
        "type": "event",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_name", "type": "string"},
            {"internalType": "string", "name": "_description", "type": "string"},
        ],
        "name": "addCandidate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "candidateAddresses",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "candidateCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "name": "candidates",
        "outputs": [
            {"internalType": "uint256", "name": "id", "type": "uint256"},
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"},
            {"internalType": "uint256", "name": "voteCount", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "electionStarted",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "_id", "type": "uint256"}],
        "name": "getCandidate",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getCandidateCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getResults",
        "outputs": [
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"},
            {"internalType": "string[]", "name": "", "type": "string[]"},
            {"internalType": "uint256[]", "name": "", "type": "uint256[]"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "_wallet", "type": "address"}],
        "name": "getVoter",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "bool", "name": "", "type": "bool"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "hasVoted",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "_wallet", "type": "address"},
            {"internalType": "string", "name": "_fullName", "type": "string"},
        ],
        "name": "registerVoter",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "registeredVoters",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "startElection",
        "outputs": [],
        "stateMutability": "nonpayability",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "stopElection",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "_candidateId", "type": "uint256"}
        ],
        "name": "vote",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "voters",
        "outputs": [
            {"internalType": "address", "name": "walletAddress", "type": "address"},
            {"internalType": "string", "name": "fullName", "type": "string"},
            {"internalType": "bool", "name": "hasVoted", "type": "bool"},
            {"internalType": "uint256", "name": "gasBalance", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "voterCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Admin account (first account from Ganache)
ADMIN_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

GAS_COST_PER_VOTE = 0.001 * 10**18  # 0.001 ETH in wei


class BlockchainService:
    def __init__(self, ganache_url: str = GANACHE_URL):
        self.w3 = Web3(Web3.HTTPProvider(ganache_url))
        self.contract = None
        self.admin_account = Account.from_key(ADMIN_PRIVATE_KEY)
        self._load_contract()

    def _load_contract(self):
        if os.path.exists(CONTRACT_ADDRESS_FILE):
            with open(CONTRACT_ADDRESS_FILE, "r") as f:
                contract_address = f.read().strip()
            if contract_address:
                self.contract = self.w3.eth.contract(
                    address=contract_address, abi=CONTRACT_ABI
                )

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_chain_info(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected(),
            "chain_id": self.w3.eth.chain_id,
            "block_number": self.w3.eth.block_number,
            "admin_address": self.admin_account.address,
        }

    def deploy_contract(self) -> str:
        """Deploy the contract to Ganache"""
        contract = self.w3.eth.contract(
            abi=CONTRACT_ABI,
            bytecode=open(
                os.path.join(
                    os.path.dirname(__file__), "contracts", "VotingSystem.bin"
                ),
                "r",
            ).read()
            if os.path.exists(
                os.path.join(os.path.dirname(__file__), "contracts", "VotingSystem.bin")
            )
            else "",
        )

        # If no bytecode, use a pre-deployed address approach
        # For simplicity, we'll use a placeholder that needs manual deployment
        raise Exception(
            "Please deploy contract manually using Remix or Truffle, then save address to contract_address.txt"
        )

    def set_contract_address(self, address: str):
        """Set the contract address after deployment"""
        with open(CONTRACT_ADDRESS_FILE, "w") as f:
            f.write(address)
        self.contract = self.w3.eth.contract(address=address, abi=CONTRACT_ABI)

    def add_candidate(self, name: str, description: str = "") -> Dict[str, Any]:
        """Add a candidate to the election"""
        if not self.contract:
            raise Exception("Contract not deployed")

        tx = self.contract.functions.addCandidate(name, description).build_transaction(
            {
                "from": self.admin_account.address,
                "nonce": self.w3.eth.get_transaction_count(self.admin_account.address),
                "gas": 100000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.admin_account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "block_number": receipt["blockNumber"],
        }

    def register_voter(self, wallet_address: str, full_name: str) -> Dict[str, Any]:
        """Register a voter"""
        if not self.contract:
            raise Exception("Contract not deployed")

        # Check if voter is already registered
        try:
            is_registered = self.contract.functions.registeredVoters(
                wallet_address
            ).call()
            if is_registered:
                return {"success": False, "error": "Voter already registered"}
        except:
            pass

        tx = self.contract.functions.registerVoter(
            wallet_address, full_name
        ).build_transaction(
            {
                "from": self.admin_account.address,
                "nonce": self.w3.eth.get_transaction_count(self.admin_account.address),
                "gas": 100000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.admin_account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "block_number": receipt["blockNumber"],
        }

    def start_election(self) -> Dict[str, Any]:
        """Start the election"""
        if not self.contract:
            raise Exception("Contract not deployed")

        tx = self.contract.functions.startElection().build_transaction(
            {
                "from": self.admin_account.address,
                "nonce": self.w3.eth.get_transaction_count(self.admin_account.address),
                "gas": 100000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.admin_account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {"success": True, "transaction_hash": tx_hash.hex()}

    def stop_election(self) -> Dict[str, Any]:
        """Stop the election"""
        if not self.contract:
            raise Exception("Contract not deployed")

        tx = self.contract.functions.stopElection().build_transaction(
            {
                "from": self.admin_account.address,
                "nonce": self.w3.eth.get_transaction_count(self.admin_account.address),
                "gas": 100000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.admin_account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {"success": True, "transaction_hash": tx_hash.hex()}

    def cast_vote(self, candidate_id: int, private_key: str) -> Dict[str, Any]:
        """Cast a vote using the voter's private key"""
        if not self.contract:
            raise Exception("Contract not deployed")

        account = Account.from_key(private_key)

        # Check if election is started
        election_started = self.contract.functions.electionStarted().call()
        if not election_started:
            return {"success": False, "error": "Election has not started"}

        # Check if already voted
        has_voted = self.contract.functions.hasVoted(account.address).call()
        if has_voted:
            return {"success": False, "error": "Already voted"}

        # Check gas balance
        try:
            voter_info = self.contract.functions.getVoter(account.address).call()
            gas_balance = voter_info[3]
            if gas_balance < GAS_COST_PER_VOTE:
                return {"success": False, "error": "Insufficient gas balance"}
        except:
            return {"success": False, "error": "Not registered as voter"}

        tx = self.contract.functions.vote(candidate_id).build_transaction(
            {
                "from": account.address,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 150000,
                "gasPrice": self.w3.eth.gas_price,
            }
        )

        signed_tx = self.w3.eth.account.sign_transaction(tx, account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "success": True,
            "transaction_hash": tx_hash.hex(),
            "block_number": receipt["blockNumber"],
            "gas_used": receipt["gasUsed"],
        }

    def get_voter_info(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get voter information"""
        if not self.contract:
            return None

        try:
            info = self.contract.functions.getVoter(wallet_address).call()
            return {
                "wallet_address": info[0],
                "full_name": info[1],
                "has_voted": info[2],
                "gas_balance": info[3],
            }
        except:
            return None

    def get_candidates(self) -> List[Dict[str, Any]]:
        """Get all candidates"""
        if not self.contract:
            return []

        count = self.contract.functions.getCandidateCount().call()
        candidates = []

        for i in range(1, count + 1):
            info = self.contract.functions.getCandidate(i).call()
            candidates.append(
                {
                    "id": info[0],
                    "name": info[1],
                    "description": info[2],
                    "vote_count": info[3],
                }
            )

        return candidates

    def get_election_status(self) -> Dict[str, Any]:
        """Get election status"""
        if not self.contract:
            return {"election_started": False}

        return {"election_started": self.contract.functions.electionStarted().call()}

    def get_voting_results(self) -> Dict[str, Any]:
        """Get voting results"""
        if not self.contract:
            return {"candidates": []}

        ids, names, votes = self.contract.functions.getResults().call()

        candidates = []
        for i in range(len(ids)):
            candidates.append({"id": ids[i], "name": names[i], "vote_count": votes[i]})

        return {"candidates": candidates}

    def verify_vote(self, wallet_address: str) -> Dict[str, Any]:
        """Verify if a wallet has voted"""
        if not self.contract:
            return {"valid": False, "error": "Contract not connected"}

        try:
            has_voted = self.contract.functions.hasVoted(wallet_address).call()
            return {
                "valid": has_voted,
                "wallet_address": wallet_address,
                "message": "Vote recorded" if has_voted else "No vote recorded",
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}


# Singleton instance
blockchain_service = BlockchainService()
