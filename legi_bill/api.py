import json as _json
import sys
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.ranking import rank_bills
from .config import OPENAI_MODEL, load_config
from .grader import grade_company
from .legal_intelligence import detect_industry, calculate_savings
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
    if name.endswith(".csv"):
        df = pd.read_csv(StringIO(data.decode("utf-8", errors="replace")))
        return _df_to_text(df)
    if name.endswith((".xlsx", ".xls")):
        excel = pd.ExcelFile(BytesIO(data))
        parts = []
        for sheet in excel.sheet_names:
            df = excel.parse(sheet)
            parts.append(f"Sheet: {sheet}\n{_df_to_text(df)}")
        return "\n\n".join(parts)
    return data.decode("utf-8", errors="replace")


def _df_to_text(df: pd.DataFrame) -> str:
    df = df.dropna(how="all").dropna(axis=1, how="all")
    lines = [f"Columns: {', '.join(str(c) for c in df.columns)}"]
    for _, row in df.iterrows():
        pairs = [f"{col}: {val}" for col, val in row.items() if pd.notna(val)]
        if pairs:
            lines.append(" | ".join(pairs))
    return "\n".join(lines)
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


class LicenseScanOptions(BaseModel):
    deterministic_only: bool = False
    llm_provider: str | None = None
    batch_timeout_hours: float = 24
    poll_interval_seconds: int = 60
    registry_metadata: bool = False
    artifact_inspection: bool = False
    source_repo: bool = False


class LicenseScanRequest(BaseModel):
    repo_path: str
    options: LicenseScanOptions = Field(default_factory=LicenseScanOptions)


@app.post("/api/startup/license/scan")
def startup_license_scan(req: LicenseScanRequest):
    """Run the startup-risk license scanner with path-safe local/GitHub targets."""
    startup_risk_root = Path(__file__).resolve().parents[1] / "startup-risk"
    if str(startup_risk_root) not in sys.path:
        sys.path.insert(0, str(startup_risk_root))

    from startup_risk.core.engine import ScanEngine
    from startup_risk.ingest.repository import RepositoryIngestor
    from startup_risk.outputs.json_output import result_to_json
    from startup_risk.scanners.license_scanner import LicenseRiskScanner

    target = req.repo_path.strip()
    if not target:
        raise HTTPException(400, "repo_path is required.")
    if req.options.deterministic_only is False and req.options.batch_timeout_hours <= 0:
        raise HTTPException(400, "batch_timeout_hours must be positive.")

    if target.startswith(("http://", "https://")):
        safe_target = target
    else:
        workspace_root = Path(__file__).resolve().parents[1]
        candidate = Path(target).expanduser().resolve()
        if workspace_root not in candidate.parents and candidate != workspace_root:
            raise HTTPException(400, "Local repo_path must be inside the workspace root.")
        safe_target = str(candidate)

    scanner = LicenseRiskScanner(
        deterministic_only=req.options.deterministic_only,
        provider_name=req.options.llm_provider,
        batch_timeout_seconds=int(req.options.batch_timeout_hours * 60 * 60),
        poll_interval_seconds=req.options.poll_interval_seconds,
        enable_registry_metadata=req.options.registry_metadata,
        enable_artifact_inspection=req.options.artifact_inspection,
        enable_source_repo=req.options.source_repo,
    )
    try:
        result = ScanEngine(
            ingestor=RepositoryIngestor(max_file_bytes=2_000_000),
            scanners=[scanner],
        ).scan(safe_target)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"License scan failed: {exc}") from exc

    return _json.loads(result_to_json(result))


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


class StartupCustomRulesRequest(BaseModel):
    questionnaire: dict  # { stage, customers, sensitive_data, regulated_industry, gtm, ... }
    prd_text: Optional[str] = None
    github_summary: Optional[dict] = None  # passed through so rules can reference repo facts


class StartupCustomGradeRequest(BaseModel):
    rules: list  # [{id, title, weight, what_to_check, fix}]
    prd_text: Optional[str] = None
    github_summary: Optional[dict] = None
    spreadsheet_summary: Optional[dict] = None


def _require_openai():
    cfg = load_config()
    api_key = cfg.get("openai_api_key", "")
    if not api_key or api_key.startswith("stub"):
        raise HTTPException(503, "OPENAI_API_KEY not configured.")
    return cfg, api_key


@app.post("/api/startup/custom-rules")
def startup_custom_rules(req: StartupCustomRulesRequest):
    """LLM writes a tailored ruleset for this specific startup.

    Inputs: a short questionnaire + (optionally) the PRD. Output: a JSON list
    of 5-8 rules with id, title, weight, what_to_check (criteria the grader will
    use), and a fix. These rules form the "custom" axis in the rubric.
    """
    cfg, api_key = _require_openai()

    q = req.questionnaire or {}
    lines = ["Founder questionnaire:"]
    for k, v in q.items():
        if v:
            lines.append(f"  - {k}: {v}")
    if req.prd_text:
        excerpt = req.prd_text[:4000]
        lines += ["", "PRD excerpt:", excerpt]
    if req.github_summary:
        gh = req.github_summary
        lines += [
            "",
            "Repo facts:",
            f"  - name: {gh.get('fullName')}",
            f"  - language: {gh.get('language')}",
            f"  - license: {gh.get('license')}",
            f"  - files: {', '.join((gh.get('filenames') or [])[:20])}",
        ]
    user_msg = "\n".join(lines)

    system = (
        "You are a startup diligence expert. Given a founder's questionnaire and PRD, "
        "write a CUSTOM ruleset of 5-8 specific, checkable rules that matter for THIS "
        "product (not generic best practices already covered by a stock rubric: license, "
        "tests, README, runway, GDPR/CCPA/COPPA, PRD completeness). Focus on what's unique "
        "to their stage, customer, industry, data, and GTM. Each rule must be verifiable "
        "from the PRD text or repo facts a grader will be shown. "
        "Return ONLY a JSON object: "
        '{"rules": [{"id": "snake_case_id", "title": "short rule title", '
        '"weight": 5-20, "what_to_check": "explicit criteria the grader will use", '
        '"fix": "one-line concrete remediation"}]}. No prose, no markdown fences.'
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=cfg.get("openai_model", OPENAI_MODEL) or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        parsed = _json.loads(raw)
        rules = parsed.get("rules") or []
        if not isinstance(rules, list) or not rules:
            raise ValueError("LLM returned no rules")
        cleaned = []
        for i, r in enumerate(rules[:8]):
            cleaned.append({
                "id": str(r.get("id") or f"custom_{i}")[:64],
                "title": str(r.get("title") or "")[:140],
                "weight": max(1, min(25, int(r.get("weight") or 8))),
                "what_to_check": str(r.get("what_to_check") or "")[:600],
                "fix": str(r.get("fix") or "")[:240],
            })
    except Exception as e:
        raise HTTPException(502, f"Rule generation failed: {e}")

    return {"rules": cleaned, "model": cfg.get("openai_model", OPENAI_MODEL)}


@app.post("/api/startup/custom-grade")
def startup_custom_grade(req: StartupCustomGradeRequest):
    """LLM grades the repo + PRD against the custom rules. Returns pass/fail
    per rule with evidence ('observed') the user will see in the drilldown.
    """
    cfg, api_key = _require_openai()

    if not req.rules:
        raise HTTPException(400, "No rules to grade against.")

    lines = ["Rules to evaluate:"]
    for r in req.rules:
        lines.append(
            f"  - id={r.get('id')} | title={r.get('title')} | check: {r.get('what_to_check')}"
        )

    lines.append("")
    lines.append("Evidence available:")
    if req.prd_text:
        lines += ["PRD:", req.prd_text[:4000]]
    if req.github_summary:
        gh = req.github_summary
        lines += [
            "",
            "Repo:",
            f"  name={gh.get('fullName')} language={gh.get('language')} license={gh.get('license')}",
            f"  files: {', '.join((gh.get('filenames') or [])[:30])}",
            f"  hasCI={gh.get('hasCI')} hasTests={gh.get('hasTests')} hasEnvFile={gh.get('hasEnvFile')}",
            f"  contributors={gh.get('contributorCount')} daysSincePush={gh.get('daysSincePush')}",
            f"  readme excerpt: {(gh.get('readmeText') or '')[:800]}",
        ]
    if req.spreadsheet_summary:
        s = req.spreadsheet_summary
        lines += [
            "",
            "Finance:",
            f"  rows={s.get('rowCount')} runway_months={s.get('runway')} "
            f"monthlyRevenue={s.get('monthlyRevenue')} hasCategories={s.get('hasCategories')}",
        ]

    user_msg = "\n".join(lines)

    system = (
        "You are evaluating a startup against a CUSTOM ruleset. For each rule, decide "
        "passed=true/false STRICTLY from the evidence shown. If evidence is missing, "
        "passed=false and say so in observed. Never invent facts. "
        "Return ONLY JSON: "
        '{"results": [{"id": "<rule id>", "passed": bool, '
        '"observed": "<1 short sentence of evidence>"}]}. '
        "Include every rule id exactly once. No markdown fences."
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=cfg.get("openai_model", OPENAI_MODEL) or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        raw = (resp.choices[0].message.content or "").strip()
        parsed = _json.loads(raw)
        results = parsed.get("results") or []
        by_id = {str(r.get("id")): r for r in results if isinstance(r, dict)}
        cleaned = []
        for r in req.rules:
            rid = str(r.get("id"))
            hit = by_id.get(rid) or {}
            cleaned.append({
                "id": rid,
                "title": r.get("title"),
                "weight": r.get("weight"),
                "passed": bool(hit.get("passed", False)),
                "observed": str(hit.get("observed") or "no evidence found")[:240],
                "fix": r.get("fix") or "",
            })
    except Exception as e:
        raise HTTPException(502, f"Custom grading failed: {e}")

    return {"results": cleaned, "model": cfg.get("openai_model", OPENAI_MODEL)}


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


@app.post("/api/legal-savings")
def legal_savings(
    company_text: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    hourly_rate: Optional[float] = Form(None),
):
    """Return an itemized legal-cost savings estimate for a company.

    Runs a keyword match against the bill DB so hours scale with how many
    bills are actually relevant to this company — making the output unique
    per company rather than a fixed number.

    Scan/screening tasks use the total DB bill count (a lawyer reads everything
    to find what applies). Analysis tasks use the matched count (deep work
    only happens on relevant bills).
    """
    industry = detect_industry(company_text or "")
    conn = get_conn()
    all_bills = get_all_bills(conn)
    total_count = len(all_bills)

    # Find bills relevant to this specific company
    matched_count = 0
    if company_text and company_text.strip():
        enriched = []
        for b in all_bills:
            rec = get_bill_with_summary_and_questions(conn, b.bill_number)
            summary_text = rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
            enriched.append((b, summary_text))
        ranked = rank_bills(company_text, enriched)
        matched_count = sum(1 for _, score, _ in ranked if score > 0)

    # Fall back to a reasonable fraction of total if nothing matched
    if matched_count == 0:
        matched_count = max(1, total_count // 10)

    return calculate_savings(
        matched_bill_count=matched_count,
        industry=industry,
        state=state,
        hourly_rate_override=hourly_rate,
    )


# ── /api/scan ─────────────────────────────────────────────────────────────────

class RepoScanRequest(BaseModel):
    repo_url: str
    industry: Optional[str] = None
    product_name: Optional[str] = None
    vuln_osv: bool = True
    outdated_registry: bool = False


@app.post("/api/scan")
def scan_repo(req: RepoScanRequest):
    """Run all startup-risk scanners on a public GitHub repository."""
    import time
    import re as _re

    startup_risk_root = Path(__file__).resolve().parents[1] / "startup-risk"
    if str(startup_risk_root) not in sys.path:
        sys.path.insert(0, str(startup_risk_root))

    try:
        from startup_risk.core.engine import ScanEngine
        from startup_risk.ingest.repository import RepositoryIngestor
        from startup_risk.scanners.registry import default_scanners
    except ImportError as exc:
        raise HTTPException(500, f"startup-risk module not available: {exc}") from exc

    # Validate: public GitHub HTTPS URL only
    if not _re.match(r"^https://github\.com/[\w.\-]+/[\w.\-]+(/?)?$", req.repo_url.strip()):
        raise HTTPException(400, "Only public GitHub HTTPS URLs are supported.")

    start = time.time()
    try:
        scanners = default_scanners(
            deterministic_license_only=True,
            vuln_osv=req.vuln_osv,
            outdated_registry=req.outdated_registry,
        )
        result = ScanEngine(
            ingestor=RepositoryIngestor(),
            scanners=scanners,
        ).scan(req.repo_url.strip())
    except Exception as exc:
        raise HTTPException(502, f"Scan failed: {exc}") from exc

    elapsed = round(time.time() - start, 1)

    # Transform Finding objects into the frontend-expected shape
    def _finding_to_dict(f) -> dict:
        evidence = []
        for ev in (f.evidence or []):
            loc = ev.location
            evidence.append({
                "file": loc.path if loc else None,
                "line": loc.line_start if loc else None,
                "excerpt": ev.excerpt or ev.description,
            })
        return {
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "category": f.category,
            "severity": f.severity,
            "confidence": f.confidence,
            "evidence": evidence,
            "recommendation": f.recommendation,
            "scanner": f.scanner_id,
        }

    findings = [_finding_to_dict(f) for f in result.findings]

    # Trivy comparison metadata — precomputed from our benchmark run
    _TRIVY_KNOWN = {
        "django/django": {
            "trivy_findings": 0,
            "trivy_vulns": 0,
            "trivy_secrets": 0,
            "trivy_note": "Trivy scanned django/django and found 0 vulnerabilities. It missed GHSA-27jp-wm6q-gp25 because its uv lockfile parser does not read optional dependencies declared in pyproject.toml.",
        },
    }
    slug = "/".join(req.repo_url.strip().rstrip("/").split("/")[-2:])
    trivy_comparison = _TRIVY_KNOWN.get(slug)

    our_vulns = sum(1 for f in findings if f["category"] == "dependency_vulnerability")
    our_secrets = sum(1 for f in findings if f["category"] == "secret_exposure")

    return {
        "repo": slug,
        "findings": findings,
        "summary": result.summary.model_dump(),
        "timing_seconds": elapsed,
        "scanners_run": list({f["scanner"] for f in findings}),
        "trivy_comparison": trivy_comparison,
        "our_vuln_count": our_vulns,
        "our_secret_count": our_secrets,
    }
