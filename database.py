import sqlite3
import hashlib
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager


DATABASE_PATH = os.path.join(os.path.dirname(__file__), "voting_system.db")
INITIAL_GAS_BALANCE = 1.0


def hash_pin(pin: str, salt: str = "") -> str:
    return hashlib.sha256(f"{pin}{salt}".encode()).hexdigest()


def hash_resident_id(resident_id: str) -> str:
    return hashlib.sha256(resident_id.encode()).hexdigest()


@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS voters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resident_id TEXT UNIQUE NOT NULL,
                resident_id_hash TEXT UNIQUE NOT NULL,
                pin_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                gas_balance REAL DEFAULT 1.0,
                has_voted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS election_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                election_started INTEGER DEFAULT 0,
                started_at TIMESTAMP,
                ended_at TIMESTAMP
            )
        """,
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        )

        cursor.execute("""
            INSERT OR IGNORE INTO election_config (id, election_started)
            VALUES (1, 0)
        """)

        cursor.execute("SELECT COUNT(*) FROM admin_users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            admin_password_hash = hash_pin("admin123", "admin_salt")
            cursor.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                ("admin", admin_password_hash),
            )

        conn.commit()


def register_voter(resident_id: str, pin: str, full_name: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM voters WHERE resident_id = ?", (resident_id,))
        if cursor.fetchone():
            return {"success": False, "error": "Resident ID already registered"}

        resident_id_hash = hash_resident_id(resident_id)
        pin_hash = hash_pin(pin, resident_id)

        cursor.execute(
            """
            INSERT INTO voters (resident_id, resident_id_hash, pin_hash, full_name, gas_balance)
            VALUES (?, ?, ?, ?, ?)
        """,
            (resident_id, resident_id_hash, pin_hash, full_name, INITIAL_GAS_BALANCE),
        )

        conn.commit()

        return {
            "success": True,
            "voter_id_hash": resident_id_hash,
            "gas_balance": INITIAL_GAS_BALANCE,
        }


def authenticate_voter(resident_id: str, pin: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, resident_id, resident_id_hash, full_name, gas_balance, has_voted
            FROM voters WHERE resident_id = ? AND pin_hash = ?
        """,
            (resident_id, hash_pin(pin, resident_id)),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "resident_id": row["resident_id"],
            "resident_id_hash": row["resident_id_hash"],
            "full_name": row["full_name"],
            "gas_balance": row["gas_balance"],
            "has_voted": bool(row["has_voted"]),
        }


def get_voter_by_id_hash(resident_id_hash: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, resident_id, resident_id_hash, full_name, gas_balance, has_voted
            FROM voters WHERE resident_id_hash = ?
        """,
            (resident_id_hash,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "resident_id": row["resident_id"],
            "resident_id_hash": row["resident_id_hash"],
            "full_name": row["full_name"],
            "gas_balance": row["gas_balance"],
            "has_voted": bool(row["has_voted"]),
        }


def mark_voter_as_voted(resident_id_hash: str, gas_used: float):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE voters SET has_voted = 1, gas_balance = gas_balance - ?
            WHERE resident_id_hash = ?
        """,
            (gas_used, resident_id_hash),
        )

        conn.commit()


def get_all_voters() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT resident_id, full_name, gas_balance, has_voted, created_at
            FROM voters ORDER BY created_at DESC
        """)

        return [dict(row) for row in cursor.fetchall()]


def get_candidates() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, description FROM candidates ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]


def add_candidate(name: str, description: str = "") -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM candidates WHERE name = ?", (name,))
        if cursor.fetchone():
            return {"success": False, "error": "Candidate already exists"}

        cursor.execute(
            "INSERT INTO candidates (name, description) VALUES (?, ?)",
            (name, description),
        )
        conn.commit()

        return {"success": True, "candidate_id": cursor.lastrowid}


def remove_candidate(candidate_id: int) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
        conn.commit()

        return {"success": True}


def get_election_status() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT election_started, started_at, ended_at FROM election_config WHERE id = 1"
        )
        row = cursor.fetchone()

        return {
            "election_started": bool(row["election_started"]),
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
        }


def start_election() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE election_config 
            SET election_started = 1, started_at = CURRENT_TIMESTAMP, ended_at = NULL
            WHERE id = 1
        """)

        conn.commit()

        return {"success": True}


def stop_election() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE election_config 
            SET election_started = 0, ended_at = CURRENT_TIMESTAMP
            WHERE id = 1
        """)

        conn.commit()

        return {"success": True}


def get_voting_stats() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM voters")
        total_voters = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as voted FROM voters WHERE has_voted = 1")
        total_voted = cursor.fetchone()["voted"]

        cursor.execute("SELECT COUNT(*) as candidates FROM candidates")
        total_candidates = cursor.fetchone()["candidates"]

        return {
            "total_voters": total_voters,
            "total_voted": total_voted,
            "total_candidates": total_candidates,
            "voter_turnout": (total_voted / total_voters * 100)
            if total_voters > 0
            else 0,
        }


def authenticate_admin(username: str, password: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, username FROM admin_users 
            WHERE username = ? AND password_hash = ?
        """,
            (username, hash_pin(password, "admin_salt")),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {"id": row["id"], "username": row["username"]}


init_database()
