import json as _json
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from pypdf import PdfReader

from app.ranking import rank_bills
from .config import OPENAI_MODEL, load_config
from .grader import grade_company
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
        _conn = init_db(cfg["db_path"], cfg.get("turso_url"), cfg.get("turso_token"))
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
            "category": b.category,
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
            "category": b.category,
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


@app.post("/api/startup/prd/extract")
def extract_startup_prd(file: UploadFile = File(...)):
    """Extract PRD text for the startup health grader.

    Text/Markdown can be parsed in the browser, but PDFs need backend parsing
    via pypdf. The frontend still runs the deterministic PRD rubric locally
    after receiving this text.
    """
    if not file.filename:
        raise HTTPException(400, "Upload a PRD file.")
    try:
        text = _extract_text(file)
    except Exception as e:
        raise HTTPException(400, f"Could not read PRD: {e}")
    if not text.strip():
        raise HTTPException(400, "No readable text found in PRD.")
    return {
        "filename": file.filename,
        "text": text,
        "length": len(text),
    }


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


def _rank_for_description(description: str) -> list:
    conn = get_conn()
    bills = get_all_bills(conn)
    enriched = []
    for b in bills:
        rec = get_bill_with_summary_and_questions(conn, b.bill_number)
        summary_text = rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
        enriched.append((b, summary_text))
    ranked = rank_bills(description, enriched)
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


CHAT_SYSTEM_PROMPT = """You are a helpful assistant helping a mid-market company find California environmental legislation that affects them.

Goal: gather just enough information to identify the most relevant CA environmental bills, then call the run_match tool. Don't ask for things you don't need.

What you need (gather concisely, not as a checklist):
- What the company makes or does (industry / products)
- Where they operate (especially CA presence)
- Rough size (employees or revenue)
- Any environmentally-relevant operations (water, energy, emissions, waste, hazardous materials, transportation, packaging)

If the first turn already includes a 10-K excerpt or a substantive description, you may have enough to call run_match immediately — skip the questions and call the tool.

Otherwise ask 1–3 short follow-up questions across one or two turns. Don't number questions. Don't restate what the user said. Stay conversational.

After run_match returns, write one short paragraph (2–4 sentences) explaining why the top 1–3 bills matter for this specific company. Cite their actual processes or scale; avoid generic statements. The UI will render the ranked bill list separately, so don't list bill titles.

When the user asks about a specific bill (e.g. "tell me more about SB1237"), call get_bill_details to pull its summary and compliance questions, then answer in 3–6 sentences: what the bill does, who it applies to, and what this specific company would need to do. Be concrete."""

CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_match",
            "description": "Rank California environmental bills against a company description. Call this once you have enough information about the company. Returns the top 10 most relevant bills.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "A consolidated description of the company suitable for keyword matching against bill text. Include industry, location (especially CA presence), size, and any environmentally-relevant processes/products. 100-400 words.",
                    }
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bill_details",
            "description": "Look up full details for a specific California bill: title, description, plain-language summary, compliance questions, status, URL. Call this when the user asks about a specific bill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_number": {
                        "type": "string",
                        "description": "The bill identifier exactly as shown in the matches list, e.g. 'SB1237' or 'AB1279'.",
                    }
                },
                "required": ["bill_number"],
            },
        },
    },
]


def _bill_details_payload(bill_number: str) -> dict:
    rec = get_bill_with_summary_and_questions(get_conn(), bill_number)
    if not rec:
        return {"error": f"Bill {bill_number} not found"}
    b = rec["bill"]
    return {
        "bill_number": b.bill_number,
        "title": b.title,
        "description": b.description,
        "status": b.status,
        "session_year": b.session_year,
        "subjects": b.subjects,
        "url": b.url,
        "summary": rec["summary"]["summary_text"] if rec["summary"] else None,
        "compliance_questions": [q["question_text"] for q in rec["questions"]],
    }


@app.post("/api/match/chat")
def match_chat(
    messages: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    try:
        history = _json.loads(messages)
        assert isinstance(history, list)
    except Exception:
        raise HTTPException(400, "messages must be a JSON-encoded array")

    if file is not None and file.filename:
        try:
            file_text = _extract_text(file)[:6000]
        except Exception as e:
            raise HTTPException(400, f"Could not read file: {e}")
        for i in range(len(history) - 1, -1, -1):
            if history[i].get("role") == "user":
                original = history[i].get("content", "")
                history[i] = {
                    "role": "user",
                    "content": (
                        f"[Attached document — first 6000 chars of {file.filename}]\n"
                        f"{file_text}\n[end of document]\n\n{original}"
                    ).strip(),
                }
                break

    cfg = load_config()
    api_key = cfg.get("openai_api_key", "")
    if not api_key or api_key.startswith("stub"):
        raise HTTPException(
            503,
            "OPENAI_API_KEY is not configured. Set a real key in .env to enable chat.",
        )

    client = OpenAI(api_key=api_key)
    full = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *history]
    matches: Optional[list] = None

    for _ in range(3):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=full,
                tools=CHAT_TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            raise HTTPException(502, f"OpenAI API error: {e}")

        msg = response.choices[0].message

        if msg.tool_calls:
            full.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                args = _json.loads(tc.function.arguments or "{}")
                if tc.function.name == "run_match":
                    matches = _rank_for_description(args.get("description", ""))
                    tool_result = {
                        "matches_returned": len(matches),
                        "top_bills": [
                            {"bill_number": m["bill_number"], "title": m["title"], "tier": m["tier"]}
                            for m in matches[:5]
                        ],
                    }
                elif tc.function.name == "get_bill_details":
                    tool_result = _bill_details_payload(args.get("bill_number", ""))
                else:
                    tool_result = {"error": f"unknown tool {tc.function.name}"}
                full.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _json.dumps(tool_result),
                })
            continue

        return {"message": msg.content or "", "matches": matches}

    raise HTTPException(500, "Chat tool-call loop did not converge")


@app.post("/api/grade")
def grade(
    company_text: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Score a company across the 5 regulatory exposure axes with evidence.

    Accepts either a 10-K file (PDF or text) or a free-text company description.
    Returns axis scores, per-axis evidence (which bills, rationale, quoted
    snippets), composite score, letter grade, and top-3 bills overall.
    """
    text = ""
    fname = None
    if file is not None and file.filename:
        try:
            text = _extract_text(file)
            fname = file.filename
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    elif company_text:
        text = company_text

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Provide a non-empty file or company_text.",
        )

    cfg = load_config()
    api_key = cfg.get("openai_api_key", "")
    if not api_key or api_key.startswith("stub"):
        raise HTTPException(
            503,
            "OPENAI_API_KEY is not configured. Set a real key in .env to enable grading.",
        )

    # Use the same enrichment pattern as /api/match — bills + their summary text
    # if available — so the ranker has the richest possible corpus to match against.
    conn = get_conn()
    bills = get_all_bills(conn)
    enriched = []
    for b in bills:
        rec = get_bill_with_summary_and_questions(conn, b.bill_number)
        summary_text = rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
        enriched.append((b, summary_text))

    name = company_name or (fname.rsplit(".", 1)[0] if fname else None)

    try:
        client = OpenAI(api_key=api_key)
        result = grade_company(client, enriched, text, company_name=name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Grading failed: {e}")

    return result


@app.get("/api/grade/featured")
def list_featured():
    """Return all baked featured-company grades (cached on disk)."""
    cache_path = Path(__file__).parent / "data" / "featured_grades.json"
    if not cache_path.exists():
        raise HTTPException(404, "No featured grades baked yet. Run `python -m legi_bill.bake_featured`.")
    with open(cache_path) as f:
        data = _json.load(f)
    # Return as a list, ordered by ticker for stable display.
    return [data[ticker] for ticker in sorted(data.keys())]


@app.get("/api/grade/featured/{ticker}")
def get_featured(ticker: str):
    """Return one baked featured grade by ticker."""
    cache_path = Path(__file__).parent / "data" / "featured_grades.json"
    if not cache_path.exists():
        raise HTTPException(404, "No featured grades baked.")
    with open(cache_path) as f:
        data = _json.load(f)
    payload = data.get(ticker.upper())
    if not payload:
        raise HTTPException(404, f"Featured ticker {ticker} not in cache.")
    return payload


class StartupSummaryRequest(BaseModel):
    name: str
    grade: str
    composite: int
    axes: dict
    top_actions: list


@app.post("/api/startup/summary")
def startup_summary(req: StartupSummaryRequest):
    """Synthesize a short verdict over the deterministic startup-health grade."""
    cfg = load_config()
    api_key = cfg.get("openai_api_key", "")
    if not api_key or api_key.startswith("stub"):
        raise HTTPException(503, "OPENAI_API_KEY not configured.")

    lines = [
        f"Startup: {req.name}",
        f"Composite grade: {req.grade} ({req.composite}/100)",
        "",
        "Per-axis sub-scores:",
    ]
    for axis_key, axis_data in req.axes.items():
        lines.append(f"  - {axis_key}: {axis_data.get('score', 0)}/100")

    lines.append("")
    lines.append("Failed rules:")
    seen = 0
    for axis_key, axis_data in req.axes.items():
        for r in axis_data.get("results", []):
            if r.get("passed") is False:
                lines.append(f"  - [{axis_key}] {r.get('title')} — {r.get('observed')}")
                seen += 1
                if seen >= 12:
                    break
        if seen >= 12:
            break

    system = (
        "You are a no-nonsense startup advisor. You will be shown a structured grade "
        "produced by a deterministic rubric. Do not re-grade. Write a 2-3 sentence "
        "verdict that synthesizes what's strong, the single biggest risk, and one "
        "concrete next step. Do not invent facts. No bullets or headers."
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=cfg.get("openai_model", OPENAI_MODEL) or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.4,
            max_tokens=180,
        )
        verdict = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        raise HTTPException(502, f"Summary generation failed: {e}")

    return {"verdict": verdict, "model": cfg.get("openai_model", OPENAI_MODEL)}


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
        "history": b.history,
        "summary": result["summary"]["summary_text"] if result["summary"] else None,
        "metadata": result["summary"]["metadata"] if result["summary"] else {},
        "compliance_questions": [q["question_text"] for q in result["questions"]],
    }
