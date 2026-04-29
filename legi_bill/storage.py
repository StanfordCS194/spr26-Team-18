import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import Bill, BillSummary, ComplianceQuestion

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    bill_id      INTEGER PRIMARY KEY,
    bill_number  TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    state        TEXT DEFAULT 'CA',
    status       TEXT,
    session_year INTEGER,
    url          TEXT,
    subjects     TEXT,
    text         TEXT,
    text_doc_id  INTEGER,
    category     TEXT DEFAULT 'environmental',
    history      TEXT DEFAULT '[]',
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS summaries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id       INTEGER NOT NULL REFERENCES bills(bill_id),
    summary_text  TEXT NOT NULL,
    model_used    TEXT,
    cache_hit     INTEGER,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    metadata      TEXT DEFAULT '{}',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS compliance_questions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id          INTEGER NOT NULL REFERENCES bills(bill_id),
    question_number  INTEGER,
    question_text    TEXT NOT NULL,
    created_at       TEXT DEFAULT (datetime('now'))
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # migrate existing DBs that don't have new columns
    for col, default in [("category", "'environmental'"), ("history", "'[]'")]:
        try:
            conn.execute(f"ALTER TABLE bills ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except Exception:
            pass
    try:
        conn.execute("ALTER TABLE summaries ADD COLUMN metadata TEXT DEFAULT '{}'")
        conn.commit()
    except Exception:
        pass
    return conn


def upsert_bill(conn: sqlite3.Connection, bill: Bill) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO bills
            (bill_id, bill_number, title, description, state, status,
             session_year, url, subjects, text, text_doc_id, category, history)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bill.bill_id,
            bill.bill_number,
            bill.title,
            bill.description,
            bill.state,
            bill.status,
            bill.session_year,
            bill.url,
            json.dumps(bill.subjects),
            bill.text,
            bill.text_doc_id,
            bill.category,
            json.dumps(bill.history),
        ),
    )
    conn.commit()


def upsert_summary(conn: sqlite3.Connection, summary: BillSummary) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO summaries
            (bill_id, summary_text, model_used, cache_hit, input_tokens, output_tokens, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            summary.bill_id,
            summary.summary_text,
            summary.model_used,
            int(summary.cache_hit),
            summary.input_tokens,
            summary.output_tokens,
            json.dumps(summary.metadata),
        ),
    )
    conn.commit()


def insert_compliance_questions(
    conn: sqlite3.Connection, bill_id: int, questions: list
) -> None:
    conn.execute(
        "DELETE FROM compliance_questions WHERE bill_id = ?", (bill_id,)
    )
    conn.executemany(
        """
        INSERT INTO compliance_questions (bill_id, question_number, question_text)
        VALUES (?, ?, ?)
        """,
        [(q.bill_id, q.question_number, q.question_text) for q in questions],
    )
    conn.commit()


def _row_to_bill(row: sqlite3.Row) -> Bill:
    return Bill(
        bill_id=row["bill_id"],
        bill_number=row["bill_number"],
        title=row["title"],
        description=row["description"] or "",
        state=row["state"],
        status=row["status"] or "",
        session_year=row["session_year"],
        url=row["url"] or "",
        subjects=json.loads(row["subjects"] or "[]"),
        text=row["text"],
        text_doc_id=row["text_doc_id"],
        category=row["category"] or "environmental",
        history=json.loads(row["history"] or "[]"),
    )


def get_bill_by_number(conn: sqlite3.Connection, bill_number: str) -> Optional[Bill]:
    row = conn.execute(
        "SELECT * FROM bills WHERE bill_number = ?", (bill_number,)
    ).fetchone()
    return _row_to_bill(row) if row else None


def get_bills_without_summary(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """
        SELECT b.* FROM bills b
        LEFT JOIN summaries s ON b.bill_id = s.bill_id
        WHERE s.bill_id IS NULL
        """
    ).fetchall()
    return [_row_to_bill(r) for r in rows]


def get_all_bills(conn: sqlite3.Connection, session_year: Optional[int] = None) -> list:
    if session_year:
        rows = conn.execute(
            "SELECT * FROM bills WHERE session_year = ? ORDER BY bill_number",
            (session_year,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM bills ORDER BY bill_number"
        ).fetchall()
    return [_row_to_bill(r) for r in rows]


def get_bill_with_summary_and_questions(
    conn: sqlite3.Connection, bill_number: str
) -> Optional[dict]:
    bill = get_bill_by_number(conn, bill_number)
    if not bill:
        return None

    summary_row = conn.execute(
        "SELECT * FROM summaries WHERE bill_id = ? ORDER BY created_at DESC LIMIT 1",
        (bill.bill_id,),
    ).fetchone()

    question_rows = conn.execute(
        "SELECT * FROM compliance_questions WHERE bill_id = ? ORDER BY question_number",
        (bill.bill_id,),
    ).fetchall()

    summary_dict = None
    if summary_row:
        summary_dict = dict(summary_row)
        summary_dict["metadata"] = json.loads(summary_dict.get("metadata") or "{}")

    return {
        "bill": bill,
        "summary": summary_dict,
        "questions": [dict(r) for r in question_rows],
    }
