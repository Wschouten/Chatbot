"""Admin Portal SQLite Database Module.

Provides schema, initialization, and CRUD operations for conversation metadata,
labels, notes, ratings, and status tracking. Uses Python's built-in sqlite3.

Feature 30a: Admin DB Schema & Core Module
"""

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import g

logger = logging.getLogger(__name__)

# Default DB path (configurable via PORTAL_DB_PATH env var)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "portal.db")

# ---------------------------------------------------------------------------
# Predefined label definitions (seeded on first run)
# ---------------------------------------------------------------------------
PREDEFINED_LABELS = [
    ("shipping-inquiry", "#3B82F6", "Questions about shipping"),
    ("order-tracking", "#10B981", "Track order status"),
    ("product-question", "#8B5CF6", "Product information requests"),
    ("complaint", "#EF4444", "Customer complaints"),
    ("positive-feedback", "#22C55E", "Happy customer feedback"),
    ("needs-escalation", "#F97316", "Requires human attention"),
    ("return-request", "#F59E0B", "Return or exchange request"),
    ("refund-inquiry", "#EC4899", "Questions about refunds"),
    ("pricing-question", "#6366F1", "Pricing and discount inquiries"),
    ("availability", "#14B8A6", "Stock and availability questions"),
    ("installation-help", "#0EA5E9", "Installation and setup help"),
    ("warranty-claim", "#D946EF", "Warranty claims"),
    ("bulk-order", "#84CC16", "Bulk or wholesale inquiries"),
    ("delivery-issue", "#F43F5E", "Delivery problems"),
    ("payment-issue", "#FB923C", "Payment or billing issues"),
    ("general-inquiry", "#94A3B8", "General questions"),
    ("follow-up", "#A78BFA", "Requires follow-up"),
    ("resolved", "#22D3EE", "Issue resolved"),
    ("duplicate", "#78716C", "Duplicate conversation"),
    ("spam", "#6B7280", "Spam or irrelevant"),
    ("language-nl", "#FF6B35", "Dutch language conversation"),
    ("language-en", "#1E40AF", "English language conversation"),
    ("high-priority", "#DC2626", "High priority issue"),
    ("vip-customer", "#FBBF24", "VIP or repeat customer"),
]

# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_metadata (
    session_id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'open',
    rating INTEGER CHECK(rating IS NULL OR (rating >= 1 AND rating <= 5)),
    language TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    label_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES conversation_metadata(session_id),
    UNIQUE(session_id, label_name)
);

CREATE TABLE IF NOT EXISTS conversation_notes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    text TEXT NOT NULL,
    author TEXT DEFAULT 'admin',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES conversation_metadata(session_id)
);

CREATE TABLE IF NOT EXISTS message_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    label_name TEXT,
    rating INTEGER CHECK(rating IS NULL OR (rating >= 1 AND rating <= 5)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES conversation_metadata(session_id)
);

CREATE TABLE IF NOT EXISTS label_definitions (
    name TEXT PRIMARY KEY,
    color TEXT NOT NULL DEFAULT '#94A3B8',
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_labels_session ON conversation_labels(session_id);
CREATE INDEX IF NOT EXISTS idx_notes_session ON conversation_notes(session_id);
CREATE INDEX IF NOT EXISTS idx_msgmeta_session ON message_metadata(session_id);
CREATE INDEX IF NOT EXISTS idx_msgmeta_message ON message_metadata(message_id);
"""


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _db_path() -> str:
    return os.environ.get("PORTAL_DB_PATH", DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Connection lifecycle (Flask integration)
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
    """Get or create a DB connection stored on Flask's ``g`` object."""
    if "portal_db" not in g:
        db_path = _db_path()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        g.portal_db = conn
    return g.portal_db


def close_db(e=None) -> None:
    """Close the DB connection at end of request (Flask teardown handler)."""
    conn = g.pop("portal_db", None)
    if conn is not None:
        conn.close()


def init_db(app=None) -> None:
    """Create tables, set schema version, and seed default labels.

    Call once during app startup. If *app* is provided, registers the
    ``close_db`` teardown handler on it.
    """
    db_path = _db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)

        # Check if schema version already recorded
        cur = conn.execute("SELECT version FROM schema_version ORDER BY rowid DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                ("1.0.0", _now()),
            )

        # Seed default labels (skip duplicates)
        for name, color, desc in PREDEFINED_LABELS:
            conn.execute(
                "INSERT OR IGNORE INTO label_definitions (name, color, description, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, color, desc, _now()),
            )

        conn.commit()
        logger.info("Portal DB initialized at %s", db_path)
    except Exception:
        logger.exception("Failed to initialize portal DB")
        raise
    finally:
        conn.close()

    if app is not None:
        app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# Internal helper: ensure conversation_metadata row exists
# ---------------------------------------------------------------------------

def _ensure_metadata(db: sqlite3.Connection, session_id: str) -> None:
    """Insert a skeleton metadata row if one doesn't exist yet."""
    db.execute(
        "INSERT OR IGNORE INTO conversation_metadata (session_id, updated_at) VALUES (?, ?)",
        (session_id, _now()),
    )


# ---------------------------------------------------------------------------
# Conversation metadata CRUD
# ---------------------------------------------------------------------------

def get_all_metadata() -> list[dict]:
    """Return all conversation metadata rows with labels and notes attached.

    Uses batch queries (3 total) instead of per-row queries to avoid N+1.
    """
    db = get_db()
    rows = db.execute(
        "SELECT session_id, status, rating, language, updated_at "
        "FROM conversation_metadata ORDER BY updated_at DESC"
    ).fetchall()

    if not rows:
        return []

    # Batch-fetch all labels and notes in two queries
    all_labels = db.execute(
        "SELECT session_id, label_name FROM conversation_labels"
    ).fetchall()
    all_notes = db.execute(
        "SELECT session_id, id, text, author, created_at "
        "FROM conversation_notes ORDER BY created_at DESC"
    ).fetchall()
    all_msg_meta = db.execute(
        "SELECT session_id, message_id, label_name, rating FROM message_metadata"
    ).fetchall()

    # Build lookup dicts
    labels_by_session: dict[str, list[str]] = {}
    for lbl in all_labels:
        labels_by_session.setdefault(lbl["session_id"], []).append(lbl["label_name"])

    notes_by_session: dict[str, list[dict]] = {}
    for n in all_notes:
        notes_by_session.setdefault(n["session_id"], []).append(
            {"id": n["id"], "text": n["text"], "author": n["author"], "created_at": n["created_at"]}
        )

    msg_meta_by_session: dict[str, dict] = {}
    for m in all_msg_meta:
        sid = m["session_id"]
        mid = m["message_id"]
        if sid not in msg_meta_by_session:
            msg_meta_by_session[sid] = {}
        if mid not in msg_meta_by_session[sid]:
            msg_meta_by_session[sid][mid] = {"labels": [], "rating": None}
        if m["label_name"]:
            msg_meta_by_session[sid][mid]["labels"].append(m["label_name"])
        if m["rating"] is not None:
            msg_meta_by_session[sid][mid]["rating"] = m["rating"]

    result = []
    for r in rows:
        sid = r["session_id"]
        result.append({
            "session_id": sid,
            "status": r["status"],
            "rating": r["rating"],
            "language": r["language"],
            "updated_at": r["updated_at"],
            "labels": labels_by_session.get(sid, []),
            "notes": notes_by_session.get(sid, []),
            "messageMetadata": msg_meta_by_session.get(sid, {}),
        })
    return result


def get_metadata(session_id: str) -> dict | None:
    """Return metadata for a single conversation, or None."""
    db = get_db()
    row = db.execute(
        "SELECT session_id, status, rating, language, updated_at "
        "FROM conversation_metadata WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not row:
        return None

    labels = [
        lbl["label_name"]
        for lbl in db.execute(
            "SELECT label_name FROM conversation_labels WHERE session_id = ?", (session_id,)
        ).fetchall()
    ]
    notes = [
        {"id": n["id"], "text": n["text"], "author": n["author"], "created_at": n["created_at"]}
        for n in db.execute(
            "SELECT id, text, author, created_at FROM conversation_notes "
            "WHERE session_id = ? ORDER BY created_at DESC", (session_id,)
        ).fetchall()
    ]
    return {
        "session_id": row["session_id"],
        "status": row["status"],
        "rating": row["rating"],
        "language": row["language"],
        "updated_at": row["updated_at"],
        "labels": labels,
        "notes": notes,
    }


_UNSET = object()  # Sentinel to distinguish "not provided" from "set to None"


def upsert_metadata(session_id: str, *, status=_UNSET,
                     rating=_UNSET, language=_UNSET) -> dict:
    """Create or update core metadata fields for a conversation.

    Uses a sentinel default so that passing ``rating=None`` explicitly
    clears the value, while omitting it leaves it unchanged.
    """
    db = get_db()
    _ensure_metadata(db, session_id)

    updates = []
    params: list = []
    if status is not _UNSET:
        updates.append("status = ?")
        params.append(status)
    if rating is not _UNSET:
        updates.append("rating = ?")
        params.append(rating)
    if language is not _UNSET:
        updates.append("language = ?")
        params.append(language)

    if updates:
        updates.append("updated_at = ?")
        params.append(_now())
        params.append(session_id)
        db.execute(
            f"UPDATE conversation_metadata SET {', '.join(updates)} WHERE session_id = ?",
            params,
        )
        db.commit()

    return get_metadata(session_id)


# ---------------------------------------------------------------------------
# Conversation labels
# ---------------------------------------------------------------------------

def add_conversation_label(session_id: str, label_name: str) -> bool:
    """Add a label to a conversation. Returns True on success, False if duplicate."""
    db = get_db()
    _ensure_metadata(db, session_id)
    try:
        db.execute(
            "INSERT INTO conversation_labels (session_id, label_name, created_at) VALUES (?, ?, ?)",
            (session_id, label_name, _now()),
        )
        db.execute(
            "UPDATE conversation_metadata SET updated_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_conversation_label(session_id: str, label_name: str) -> bool:
    """Remove a label from a conversation. Returns True if a row was deleted."""
    db = get_db()
    cur = db.execute(
        "DELETE FROM conversation_labels WHERE session_id = ? AND label_name = ?",
        (session_id, label_name),
    )
    if cur.rowcount:
        db.execute(
            "UPDATE conversation_metadata SET updated_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
    db.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def add_note(session_id: str, text: str, author: str = "admin") -> str:
    """Add a note to a conversation. Returns the new note ID."""
    db = get_db()
    _ensure_metadata(db, session_id)
    note_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO conversation_notes (id, session_id, text, author, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (note_id, session_id, text, author, _now()),
    )
    db.execute(
        "UPDATE conversation_metadata SET updated_at = ? WHERE session_id = ?",
        (_now(), session_id),
    )
    db.commit()
    return note_id


def delete_note(note_id: str) -> bool:
    """Delete a note by ID. Returns True if a row was deleted."""
    db = get_db()
    cur = db.execute("DELETE FROM conversation_notes WHERE id = ?", (note_id,))
    db.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Message metadata
# ---------------------------------------------------------------------------

def add_message_label(session_id: str, message_id: str, label_name: str) -> int:
    """Label a specific message. Returns the new row ID."""
    db = get_db()
    _ensure_metadata(db, session_id)
    cur = db.execute(
        "INSERT INTO message_metadata (session_id, message_id, label_name, created_at) "
        "VALUES (?, ?, ?, ?)",
        (session_id, message_id, label_name, _now()),
    )
    db.commit()
    return cur.lastrowid


def remove_message_label(session_id: str, message_id: str, label_name: str) -> bool:
    """Remove a label from a message. Returns True if a row was deleted."""
    db = get_db()
    cur = db.execute(
        "DELETE FROM message_metadata "
        "WHERE session_id = ? AND message_id = ? AND label_name = ?",
        (session_id, message_id, label_name),
    )
    db.commit()
    return cur.rowcount > 0


def set_message_rating(session_id: str, message_id: str, rating: int | None) -> bool:
    """Set or clear a rating on a message. Upserts the row."""
    db = get_db()
    _ensure_metadata(db, session_id)
    # Check if a rating row already exists for this message
    existing = db.execute(
        "SELECT id FROM message_metadata "
        "WHERE session_id = ? AND message_id = ? AND label_name IS NULL",
        (session_id, message_id),
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE message_metadata SET rating = ? WHERE id = ?",
            (rating, existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO message_metadata (session_id, message_id, rating, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, message_id, rating, _now()),
        )
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Label definitions
# ---------------------------------------------------------------------------

def get_label_definitions() -> list[dict]:
    """Return all label definitions."""
    db = get_db()
    rows = db.execute(
        "SELECT name, color, description, created_at FROM label_definitions ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def add_label_definition(name: str, color: str = "#94A3B8", description: str = "") -> bool:
    """Create a new label definition. Returns True on success, False if duplicate."""
    db = get_db()
    try:
        db.execute(
            "INSERT INTO label_definitions (name, color, description, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, color, description, _now()),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def delete_label_definition(name: str) -> bool:
    """Delete a label definition. Returns True if a row was deleted."""
    db = get_db()
    cur = db.execute("DELETE FROM label_definitions WHERE name = ?", (name,))
    db.commit()
    return cur.rowcount > 0
