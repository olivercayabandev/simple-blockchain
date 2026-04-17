from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt

from blockchain_eth import blockchain_service, GAS_COST_PER_VOTE

app = FastAPI(title="Blockchain Voting System API (Ethereum)")

SECRET_KEY = "voting_system_secret_key_change_in_production"
ALGORITHM = "HS256"


class VoterRegistration(BaseModel):
    wallet_address: str
    full_name: str


class VoteRequest(BaseModel):
    candidate_id: int
    private_key: str


class AdminLogin(BaseModel):
    username: str
    password: str


class CandidateRequest(BaseModel):
    name: str
    description: str = ""


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


@app.get("/")
def root():
    return {"message": "Blockchain Voting System API (Ethereum)", "version": "2.0.0"}


@app.get("/api/health")
def health_check():
    """Check if connected to blockchain"""
    chain_info = blockchain_service.get_chain_info()
    return {
        "status": "healthy" if chain_info["connected"] else "error",
        "blockchain": chain_info,
    }


@app.post("/api/register")
def register(voter_data: VoterRegistration):
    """Register a voter on the blockchain"""
    try:
        result = blockchain_service.register_voter(
            voter_data.wallet_address, voter_data.full_name
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Registration failed")
            )

        token = create_token(
            {
                "wallet_address": voter_data.wallet_address,
                "full_name": voter_data.full_name,
                "role": "voter",
            }
        )

        voter_info = blockchain_service.get_voter_info(voter_data.wallet_address)

        return {"success": True, "token": token, "voter": voter_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/login")
def login(login_data: VoterRegistration):
    """Login using wallet address"""
    try:
        voter_info = blockchain_service.get_voter_info(login_data.wallet_address)

        if not voter_info:
            raise HTTPException(status_code=401, detail="Wallet not registered")

        election_status = blockchain_service.get_election_status()

        token = create_token(
            {
                "wallet_address": login_data.wallet_address,
                "full_name": voter_info["full_name"],
                "role": "voter",
            }
        )

        return {
            "success": True,
            "token": token,
            "voter": {
                **voter_info,
                "election_started": election_status["election_started"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/login")
def admin_login(login_data: AdminLogin):
    """Admin login"""
    if login_data.username != "admin" or login_data.password != "admin123":
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    token = create_token({"username": login_data.username, "role": "admin"})

    return {"success": True, "token": token, "admin": {"username": login_data.username}}


@app.get("/api/voter/me")
def get_current_voter_info(authorization: Optional[str] = Header(None)):
    """Get current voter info"""
    payload = verify_token(authorization)
    wallet_address = payload.get("wallet_address")

    voter_info = blockchain_service.get_voter_info(wallet_address)
    if not voter_info:
        raise HTTPException(status_code=404, detail="Voter not found")

    election_status = blockchain_service.get_election_status()

    return {**voter_info, "election_started": election_status["election_started"]}


@app.get("/api/candidates")
def list_candidates():
    """Get all candidates"""
    candidates = blockchain_service.get_candidates()
    election_status = blockchain_service.get_election_status()

    return {
        "candidates": candidates,
        "election_started": election_status["election_started"],
    }


@app.post("/api/vote")
def cast_vote(vote_data: VoteRequest, authorization: Optional[str] = Header(None)):
    """Cast a vote"""
    try:
        payload = verify_token(authorization)

        if (
            payload.get("wallet_address", "").lower()
            != vote_data.wallet_address.lower()
        ):
            raise HTTPException(status_code=403, detail="Wallet address mismatch")

        result = blockchain_service.cast_vote(
            vote_data.candidate_id, vote_data.private_key
        )

        if not result.get("success", False):
            raise HTTPException(
                status_code=400, detail=result.get("error", "Vote failed")
            )

        voter_info = blockchain_service.get_voter_info(vote_data.wallet_address)

        return {
            "success": True,
            "transaction_hash": result["transaction_hash"],
            "gas_used": result.get("gas_used", 0),
            "voter": voter_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chain")
def get_chain():
    """Get blockchain info"""
    chain_info = blockchain_service.get_chain_info()
    election_status = blockchain_service.get_election_status()
    results = blockchain_service.get_voting_results()

    return {
        "chain_info": chain_info,
        "election_status": election_status,
        "voting_results": results,
    }


@app.get("/api/election/status")
def get_election():
    """Get election status"""
    return blockchain_service.get_election_status()


@app.post("/api/admin/election/start")
def start_voting(authorization: Optional[str] = Header(None)):
    """Start the election"""
    verify_token(authorization)  # Just verify admin
    return blockchain_service.start_election()


@app.post("/api/admin/election/stop")
def stop_voting(authorization: Optional[str] = Header(None)):
    """Stop the election"""
    verify_token(authorization)  # Just verify admin
    return blockchain_service.stop_election()


@app.post("/api/admin/candidates")
def create_candidate(
    candidate_data: CandidateRequest, authorization: Optional[str] = Header(None)
):
    """Add a candidate"""
    verify_token(authorization)
    return blockchain_service.add_candidate(
        candidate_data.name, candidate_data.description
    )


@app.get("/api/admin/stats")
def get_stats(authorization: Optional[str] = Header(None)):
    """Get voting statistics"""
    verify_token(authorization)

    results = blockchain_service.get_voting_results()
    election_status = blockchain_service.get_election_status()
    chain_info = blockchain_service.get_chain_info()

    total_votes = sum(c["vote_count"] for c in results["candidates"])

    return {
        "total_votes": total_votes,
        "total_candidates": len(results["candidates"]),
        "election_started": election_status["election_started"],
        "blockchain": chain_info,
    }


@app.get("/api/verify/{wallet_address}")
def verify_vote(wallet_address: str):
    """Verify if a wallet has voted"""
    return blockchain_service.verify_vote(wallet_address)


@app.get("/api/blockchain/status")
def blockchain_status():
    """Get blockchain status"""
    return blockchain_service.get_chain_info()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
