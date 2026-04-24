from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json

from .config import load_config
from .storage import init_db, get_all_bills, get_bill_with_summary_and_questions

app = FastAPI(title="Legi-Bill API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_conn = None

def get_conn():
    global _conn
    if _conn is None:
        cfg = load_config()
        _conn = init_db(cfg["db_path"])
    return _conn


@app.get("/api/bills")
def list_bills(session: Optional[int] = None):
    bills = get_all_bills(get_conn(), session_year=session)
    return [
        {
            "bill_number": b.bill_number,
            "title": b.title,
            "status": b.status,
            "session_year": b.session_year,
            "subjects": b.subjects,
            "url": b.url,
        }
        for b in bills
    ]


@app.get("/api/bills/search")
def search_bills(q: str = Query(..., min_length=1)):
    bills = get_all_bills(get_conn())
    term = q.lower()
    results = [
        b for b in bills
        if term in b.title.lower() or term in (b.description or "").lower()
    ]
    return [
        {
            "bill_number": b.bill_number,
            "title": b.title,
            "status": b.status,
            "session_year": b.session_year,
            "subjects": b.subjects,
            "url": b.url,
        }
        for b in results
    ]


@app.get("/api/bills/{bill_number}")
def get_bill(bill_number: str):
    result = get_bill_with_summary_and_questions(get_conn(), bill_number)
    if not result:
        raise HTTPException(status_code=404, detail=f"Bill {bill_number} not found")
    b = result["bill"]
    return {
        "bill_number": b.bill_number,
        "title": b.title,
        "description": b.description,
        "status": b.status,
        "session_year": b.session_year,
        "subjects": b.subjects,
        "url": b.url,
        "summary": result["summary"]["summary_text"] if result["summary"] else None,
        "compliance_questions": [q["question_text"] for q in result["questions"]],
    }
