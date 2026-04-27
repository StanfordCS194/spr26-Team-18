from io import BytesIO
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

from app.ranking import rank_bills
from .config import load_config
from .storage import init_db, get_all_bills, get_bill_with_summary_and_questions

app = FastAPI(title="Legi-Bill API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
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


def _extract_text(file: UploadFile) -> str:
    data = file.file.read()
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    return data.decode("utf-8", errors="replace")


@app.post("/api/match")
def match_company(
    company_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    text = ""
    if file is not None and file.filename:
        try:
            text = _extract_text(file)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    elif company_text:
        text = company_text

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide a non-empty file or company_text.",
        )

    conn = get_conn()
    bills = get_all_bills(conn)
    enriched = []
    for b in bills:
        rec = get_bill_with_summary_and_questions(conn, b.bill_number)
        summary_text = rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
        enriched.append((b, summary_text))

    ranked = rank_bills(text, enriched)
    top = [(b, s, t) for b, s, t in ranked if s > 0][:10]
    return [
        {
            "bill_number": b.bill_number,
            "title": b.title,
            "status": b.status,
            "session_year": b.session_year,
            "subjects": b.subjects,
            "url": b.url,
            "score": round(s, 4),
            "tier": tier,
        }
        for b, s, tier in top
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
