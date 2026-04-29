import json
import sqlite3
from pathlib import Path
from typing import Optional

import requests as _requests

from .models import Bill, BillSummary, ComplianceQuestion


class _TursoRow:
    def __init__(self, cols, cells):
        self._d = dict(zip(cols, cells))

    def __getitem__(self, k):
        return self._d[k]

    def keys(self):
        return self._d.keys()


class _TursoCursor:
    def __init__(self, cols, rows):
        self._rows = [_TursoRow(cols, r) for r in rows]
        self._i = 0

    def fetchone(self):
        if self._i < len(self._rows):
            r = self._rows[self._i]; self._i += 1; return r
        return None

    def fetchall(self):
        return self._rows


class _TursoConn:
    """Thin sqlite3-compatible wrapper around the Turso HTTP pipeline API."""

    def __init__(self, url: str, auth_token: str):
        self._url = url.replace("libsql://", "https://") + "/v2/pipeline"
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        self.row_factory = None  # accepted but unused; rows always use _TursoRow

    @staticmethod
    def _arg(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": str(v)}
        return {"type": "text", "value": str(v)}

    @staticmethod
    def _cell(c):
        t = c["type"]
        if t == "null":
            return None
        if t == "integer":
            return int(c["value"])
        if t == "float":
            return float(c["value"])
        return c["value"]

    def _pipeline(self, stmts):
        body = [
            {"type": "execute", "stmt": {"sql": s, "args": [self._arg(a) for a in p]}}
            for s, p in stmts
        ]
        body.append({"type": "close"})
        resp = _requests.post(self._url, headers=self._headers, json={"requests": body}, timeout=30)
        resp.raise_for_status()
        return resp.json()["results"]

    def execute(self, sql: str, params=()):
        results = self._pipeline([(sql, list(params or []))])
        res = results[0]
        if res.get("type") == "error":
            raise Exception(res["error"]["message"])
        data = res["response"]["result"]
        cols = [c["name"] for c in data.get("cols", [])]
        rows = [[self._cell(c) for c in row] for row in data.get("rows", [])]
        return _TursoCursor(cols, rows)

    def executemany(self, sql: str, param_list):
        stmts = [(sql, list(p)) for p in param_list]
        if stmts:
            self._pipeline(stmts)

    def commit(self):
        pass  # Turso auto-commits each statement

    def close(self):
        pass

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


def init_db(db_path: str, turso_url: str = None, turso_token: str = None):
    if turso_url and turso_token:
        conn = _TursoConn(turso_url, turso_token)
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

    for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    conn.commit()

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
