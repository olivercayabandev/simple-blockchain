from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import jwt
import os
import secrets
import time
from collections import defaultdict

from database import (
    register_voter,
    authenticate_voter,
    get_voter_by_id_hash,
    mark_voter_as_voted,
    get_candidates,
    add_candidate,
    remove_candidate,
    get_election_status,
    start_election,
    stop_election,
    get_voting_stats,
    get_all_voters,
    authenticate_admin,
)
from blockchain import (
    Blockchain,
    load_blockchain,
    save_blockchain,
    blockchain_instance,
    GAS_COST_PER_VOTE,
)

# Security: Generate random JWT secret if not provided
SECRET_KEY = os.environ.get("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"

# Rate limiting storage
rate_limit_store: Dict[str, List[float]] = defaultdict(list)
RATE_LIMIT = 10  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# CORS: Allow specific origins (configure via environment variable)
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="Blockchain Voting System API")

# CORS: Allow specific origins - hardcoded for development
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    current_time = time.time()
    # Remove old requests outside the window
    rate_limit_store[client_ip] = [
        req_time
        for req_time in rate_limit_store[client_ip]
        if current_time - req_time < RATE_LIMIT_WINDOW
    ]

    if len(rate_limit_store[client_ip]) >= RATE_LIMIT:
        return False

    rate_limit_store[client_ip].append(current_time)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all requests"""
    client_ip = request.client.host if request.client else "unknown"

    # Skip rate limit for health checks
    if "/health" not in str(request.url):
        if not check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

    response = await call_next(request)
    return response


class VoterRegistration(BaseModel):
    resident_id: str
    pin: str
    full_name: str

    @field_validator("resident_id", "pin", "full_name")
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("pin")
    @classmethod
    def validate_pin_length(cls, v):
        if len(v) < 4:
            raise ValueError("PIN must be at least 4 characters")
        return v


class VoterLogin(BaseModel):
    resident_id: str
    pin: str

    @field_validator("resident_id", "pin")
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class VoteRequest(BaseModel):
    candidate: str

    @field_validator("candidate")
    @classmethod
    def validate_candidate(cls, v):
        if not v or not v.strip():
            raise ValueError("Candidate cannot be empty")
        return v.strip()


class AdminLogin(BaseModel):
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class CandidateRequest(BaseModel):
    name: str
    description: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name too long")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v and len(v) > 500:
            raise ValueError("Description too long")
        return v.strip() if v else ""


def create_token(
    data: Dict[str, Any], expires_delta: timedelta = timedelta(hours=24)
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_voter(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    payload = verify_token(authorization)
    voter = get_voter_by_id_hash(payload.get("resident_id_hash"))
    if not voter:
        raise HTTPException(status_code=401, detail="Voter not found")
    return voter


def get_current_admin(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    payload = verify_token(authorization)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


@app.get("/")
def root():
    return {"message": "Blockchain Voting System API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "blockchain_blocks": len(blockchain_instance.chain),
        "pending_transactions": blockchain_instance.get_pending_count(),
    }


@app.post("/api/register")
def register(voter_data: VoterRegistration):
    result = register_voter(
        voter_data.resident_id, voter_data.pin, voter_data.full_name
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    token = create_token(
        {
            "resident_id_hash": result["voter_id_hash"],
            "full_name": voter_data.full_name,
            "role": "voter",
        }
    )

    return {
        "success": True,
        "token": token,
        "voter": {
            "resident_id_hash": result["voter_id_hash"],
            "full_name": voter_data.full_name,
            "gas_balance": result["gas_balance"],
        },
    }


@app.post("/api/login")
def login(login_data: VoterLogin):
    voter = authenticate_voter(login_data.resident_id, login_data.pin)

    if not voter:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    election_status = get_election_status()

    token = create_token(
        {
            "resident_id_hash": voter["resident_id_hash"],
            "full_name": voter["full_name"],
            "role": "voter",
        }
    )

    return {
        "success": True,
        "token": token,
        "voter": {
            "resident_id_hash": voter["resident_id_hash"],
            "full_name": voter["full_name"],
            "gas_balance": voter["gas_balance"],
            "has_voted": voter["has_voted"],
            "election_started": election_status["election_started"],
        },
    }


@app.post("/api/admin/login")
def admin_login(login_data: AdminLogin):
    admin = authenticate_admin(login_data.username, login_data.password)

    if not admin:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    token = create_token({"username": admin["username"], "role": "admin"})

    return {"success": True, "token": token, "admin": {"username": admin["username"]}}


@app.get("/api/voter/me")
def get_current_voter_info(current_voter: Dict[str, Any] = Depends(get_current_voter)):
    election_status = get_election_status()
    return {
        "resident_id_hash": current_voter["resident_id_hash"],
        "full_name": current_voter["full_name"],
        "gas_balance": current_voter["gas_balance"],
        "has_voted": current_voter["has_voted"],
        "election_started": election_status["election_started"],
    }


@app.get("/api/candidates")
def list_candidates():
    candidates = get_candidates()
    election_status = get_election_status()
    return {
        "candidates": candidates,
        "election_started": election_status["election_started"],
    }


@app.post("/api/vote")
def cast_vote(
    vote_data: VoteRequest, current_voter: Dict[str, Any] = Depends(get_current_voter)
):
    election_status = get_election_status()

    if not election_status["election_started"]:
        raise HTTPException(status_code=400, detail="Election has not started")

    if current_voter["has_voted"]:
        raise HTTPException(status_code=400, detail="You have already voted")

    if current_voter["gas_balance"] < GAS_COST_PER_VOTE:
        raise HTTPException(status_code=400, detail="Insufficient gas balance")

    candidates = get_candidates()
    candidate_names = [c["name"] for c in candidates]

    if vote_data.candidate not in candidate_names:
        raise HTTPException(status_code=400, detail="Invalid candidate")

    transaction = blockchain_instance.add_transaction(
        current_voter["resident_id_hash"], vote_data.candidate
    )

    mark_voter_as_voted(current_voter["resident_id_hash"], GAS_COST_PER_VOTE)

    pending_count = blockchain_instance.get_pending_count()
    auto_mine = pending_count >= blockchain_instance.votes_per_block

    if auto_mine:
        blockchain_instance.mine_pending_transactions()

    return {
        "success": True,
        "transaction": transaction.to_dict(),
        "gas_used": GAS_COST_PER_VOTE,
        "gas_remaining": current_voter["gas_balance"] - GAS_COST_PER_VOTE,
        "pending_count": pending_count,
        "auto_mined": auto_mine,
        "votes_until_next_block": blockchain_instance.votes_per_block - pending_count,
    }


@app.get("/api/ledger")
def get_ledger(
    current_voter: Dict[str, Any] = Depends(get_current_voter),
    admin: Dict[str, Any] = Depends(get_current_admin),
):
    chain = blockchain_instance.get_chain_json()
    pending = blockchain_instance.get_pending_count()
    total_votes = blockchain_instance.get_total_votes()
    is_valid = blockchain_instance.validate_chain()

    return {
        "chain": chain,
        "pending_transactions": pending,
        "total_votes": total_votes,
        "is_valid": is_valid,
        "votes_per_block": blockchain_instance.votes_per_block,
    }


@app.get("/api/chain")
def get_chain():
    chain = blockchain_instance.get_chain_json()
    pending = blockchain_instance.get_pending_count()
    total_votes = blockchain_instance.get_total_votes()
    is_valid = blockchain_instance.validate_chain()

    return {
        "chain": chain,
        "pending_transactions": pending,
        "total_votes": total_votes,
        "is_valid": is_valid,
        "votes_per_block": blockchain_instance.votes_per_block,
    }


@app.post("/api/admin/mine")
def mine_block(admin: Dict[str, Any] = Depends(get_current_admin)):
    try:
        block = blockchain_instance.mine_manual()
        return {"success": True, "block": block.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/stats")
def get_stats(admin: Dict[str, Any] = Depends(get_current_admin)):
    voting_stats = get_voting_stats()
    chain_info = {
        "total_blocks": len(blockchain_instance.chain),
        "pending_transactions": blockchain_instance.get_pending_count(),
        "total_votes": blockchain_instance.get_total_votes(),
        "is_valid": blockchain_instance.validate_chain(),
    }

    return {**voting_stats, **chain_info}


@app.get("/api/election/status")
def get_election():
    return get_election_status()


@app.post("/api/admin/election/start")
def start_voting(admin: Dict[str, Any] = Depends(get_current_admin)):
    return start_election()


@app.post("/api/admin/election/stop")
def stop_voting(admin: Dict[str, Any] = Depends(get_current_admin)):
    return stop_election()


@app.post("/api/admin/candidates")
def create_candidate(
    candidate_data: CandidateRequest, admin: Dict[str, Any] = Depends(get_current_admin)
):
    return add_candidate(candidate_data.name, candidate_data.description)


@app.delete("/api/admin/candidates/{candidate_id}")
def delete_candidate(
    candidate_id: int, admin: Dict[str, Any] = Depends(get_current_admin)
):
    return remove_candidate(candidate_id)


@app.get("/api/admin/voters")
def list_voters(admin: Dict[str, Any] = Depends(get_current_admin)):
    voters = get_all_voters()
    return {"voters": voters}


@app.get("/api/verify/{tx_hash}")
def verify_vote(tx_hash: str):
    result = blockchain_instance.verify_vote(tx_hash)
    if result["valid"]:
        tx = result["transaction"]
        return {
            "valid": True,
            "message": "Vote is recorded on the blockchain",
            "recorded_at": tx["timestamp"],
            "tx_hash": tx["tx_hash"],
        }
    return {"valid": False, "message": "Transaction not found"}


@app.get("/api/blockchain/status")
def blockchain_status():
    return {
        "chain_length": len(blockchain_instance.chain),
        "pending_transactions": blockchain_instance.get_pending_count(),
        "total_votes": blockchain_instance.get_total_votes(),
        "is_valid": blockchain_instance.validate_chain(),
        "votes_per_block": blockchain_instance.votes_per_block,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
