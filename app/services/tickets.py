import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.core.config import get_settings

settings = get_settings()

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(settings.audit_db_path)
    con.row_factory = sqlite3.Row
    return con

def init_ticket_table() -> None:
    con = get_connection()
    con.execute(
        """CREATE TABLE IF NOT EXISTS it_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            requester_email TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'agent_escalation',
            agent_trace TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    con.commit()
    con.close()

def _next_ticket_id(con: sqlite3.Connection) -> str:
    cursor = con.cursor()
    cursor.execute("SELECT id FROM it_tickets ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    next_num = 1001 if row is None else (1001 + row["id"])
    return f"INC-{next_num}"

def create_ticket(
    title: str,
    description: str,
    category: str = "General IT",
    priority: str = "Medium",
    requester_email: str = "employee@novacore.internal",
    source: str = "agent_escalation",
    agent_trace: Optional[List[str]] = None,
) -> Dict[str, Any]:
    con = get_connection()
    ticket_id = _next_ticket_id(con)
    now = datetime.now(timezone.utc).isoformat()
    trace_str = json.dumps(agent_trace) if agent_trace else "[]"

    con.execute(
        """INSERT INTO it_tickets (
            ticket_id, title, description, category, priority, status,
            requester_email, source, agent_trace, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?)""",
        (
            ticket_id,
            title.strip(),
            description.strip(),
            category,
            priority,
            requester_email.strip(),
            source,
            trace_str,
            now,
            now,
        ),
    )
    con.commit()
    con.close()

    return get_ticket(ticket_id)  # type: ignore

def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    con = get_connection()
    cursor = con.cursor()
    cursor.execute("SELECT * FROM it_tickets WHERE ticket_id = ?", (ticket_id,))
    row = cursor.fetchone()
    con.close()
    if not row:
        return None
    data = dict(row)
    try:
        data["agent_trace"] = json.loads(data["agent_trace"]) if data["agent_trace"] else []
    except Exception:
        data["agent_trace"] = []
    return data

def list_tickets(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    con = get_connection()
    cursor = con.cursor()
    if status:
        cursor.execute(
            "SELECT * FROM it_tickets WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )
    else:
        cursor.execute("SELECT * FROM it_tickets ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    con.close()
    results = []
    for row in rows:
        item = dict(row)
        try:
            item["agent_trace"] = json.loads(item["agent_trace"]) if item["agent_trace"] else []
        except Exception:
            item["agent_trace"] = []
        results.append(item)
    return results

def update_ticket_status(ticket_id: str, new_status: str) -> Optional[Dict[str, Any]]:
    con = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    cursor = con.cursor()
    cursor.execute(
        "UPDATE it_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
        (new_status, now, ticket_id),
    )
    con.commit()
    con.close()
    return get_ticket(ticket_id)
