import json as _json
import sys
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.ranking import rank_bills
from .config import load_config
from .grader import grade_company
from .legal_intelligence import detect_industry, calculate_savings
from .llm import LLMConfigError, LLMProviderCapabilityError, get_chat_client
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
    llm_provider: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
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

    try:
        client = get_chat_client(provider=llm_provider, model=llm_model)
    except LLMConfigError as e:
        raise HTTPException(503, str(e)) from e
    full = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *history]
    matches: Optional[list] = None

    for _ in range(3):
        try:
            response = client.complete(
                messages=full,
                tools=CHAT_TOOLS,
                tool_choice="auto",
            )
        except LLMProviderCapabilityError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            raise HTTPException(502, f"LLM API error: {e}")

        tool_calls = response.tool_calls or []

        if tool_calls:
            full.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                function = tc.get("function", {}) if isinstance(tc, dict) else {}
                args = _json.loads(function.get("arguments") or "{}")
                function_name = function.get("name")
                if function_name == "run_match":
                    matches = _rank_for_description(args.get("description", ""))
                    tool_result = {
                        "matches_returned": len(matches),
                        "top_bills": [
                            {"bill_number": m["bill_number"], "title": m["title"], "tier": m["tier"]}
                            for m in matches[:5]
                        ],
                    }
                elif function_name == "get_bill_details":
                    tool_result = _bill_details_payload(args.get("bill_number", ""))
                else:
                    tool_result = {"error": f"unknown tool {function_name}"}
                full.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", "") if isinstance(tc, dict) else "",
                    "content": _json.dumps(tool_result),
                })
            continue

        return {"message": response.content or "", "matches": matches}

    raise HTTPException(500, "Chat tool-call loop did not converge")


@app.post("/api/grade")
def grade(
    company_text: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
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
        client = get_chat_client(provider=llm_provider, model=llm_model)
        result = grade_company(client, enriched, text, company_name=name)
    except LLMConfigError as e:
        raise HTTPException(503, str(e))
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
    llm_provider: str | None = None
    llm_model: str | None = None


class LicenseScanOptions(BaseModel):
    deterministic_only: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
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
        model_name=req.options.llm_model,
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
        client = _get_llm_client(provider=req.llm_provider, model=req.llm_model)
        resp = client.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.4,
            max_tokens=180,
        )
        verdict = (resp.content or "").strip()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Summary generation failed: {e}")

    return {"verdict": verdict, "model": resp.model, "provider": resp.provider}


class StartupCustomRulesRequest(BaseModel):
    questionnaire: dict  # { stage, customers, sensitive_data, regulated_industry, gtm, ... }
    prd_text: Optional[str] = None
    github_summary: Optional[dict] = None  # passed through so rules can reference repo facts
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class StartupCustomGradeRequest(BaseModel):
    rules: list  # [{id, title, weight, what_to_check, fix}]
    prd_text: Optional[str] = None
    github_summary: Optional[dict] = None
    spreadsheet_summary: Optional[dict] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


def _get_llm_client(provider: str | None = None, model: str | None = None):
    try:
        return get_chat_client(provider=provider, model=model)
    except LLMConfigError as e:
        raise HTTPException(503, str(e)) from e


@app.post("/api/startup/custom-rules")
def startup_custom_rules(req: StartupCustomRulesRequest):
    """LLM writes a tailored ruleset for this specific startup.

    Inputs: a short questionnaire + (optionally) the PRD. Output: a JSON list
    of 5-8 rules with id, title, weight, what_to_check (criteria the grader will
    use), and a fix. These rules form the "custom" axis in the rubric.
    """
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
        client = _get_llm_client(provider=req.llm_provider, model=req.llm_model)
        resp = client.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        raw = (resp.content or "").strip()
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Rule generation failed: {e}")

    return {"rules": cleaned, "model": resp.model, "provider": resp.provider}


@app.post("/api/startup/custom-grade")
def startup_custom_grade(req: StartupCustomGradeRequest):
    """LLM grades the repo + PRD against the custom rules. Returns pass/fail
    per rule with evidence ('observed') the user will see in the drilldown.
    """
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
        client = _get_llm_client(provider=req.llm_provider, model=req.llm_model)
        resp = client.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        raw = (resp.content or "").strip()
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Custom grading failed: {e}")

    return {"results": cleaned, "model": resp.model, "provider": resp.provider}


_COMPLIANCE_STAGE_REQUIREMENTS: dict[str, list[str]] = {
    "pre_seed": [
        "IRC §83(b) election — founders must file within 30 days of receiving restricted stock",
        "Form 1099-NEC — required for any contractor paid $600+ in the calendar year",
        "EIN (Form SS-4) — confirm employer identification number is established",
        "IRC §1202 QSBS — verify aggregate gross assets ≤ $50M at each stock issuance",
        "SAFE / convertible note — ASC 480/815 debt vs. equity classification; OID accrual under IRC §1273",
        "EFTPS deposit schedule — enroll and confirm monthly vs. semiweekly depositor classification",
    ],
    "seed": [
        "IRC §409A — option grants must be at FMV per an independent §409A valuation",
        "IRC §1202 QSBS eligibility tracking per share lot",
        "IRC §83(b) elections for any unvested restricted stock grants in the prior 30 days",
        "Form 1099-NEC for contractor payments ≥ $600; collect W-9 before first payment",
        "FICA / federal and state payroll withholding; Form 941 quarterly deposits via EFTPS",
        "IRC §174 — R&D expenditures must be capitalized and amortized (5-yr domestic / 15-yr foreign) — no immediate expensing on tax return",
        "State income tax nexus — each state where an employee is based requires a corporate return and payroll registration",
        "SAFE / convertible note — ASC 480/815 classification; bifurcation of embedded features; OID accrual",
    ],
    "series_a": [
        "IRC §409A — every option grant requires a current independent appraisal (refresh ≥ annually)",
        "IRC §422(d) — ISO annual $100,000 FMV limit per employee; excess auto-converts to NSO",
        "Form 3921 — file for each ISO exercise by January 31; disclose AMT exposure to employees",
        "Form 3922 — file for each ESPP stock transfer by January 31",
        "IRC §409A on severance and deferred bonus arrangements (short-term deferral exception or compliant schedule)",
        "Form 941 quarterly payroll tax deposits via EFTPS; verify depositor schedule (monthly vs. semiweekly)",
        "Form 1099-NEC for all contractors ≥ $600",
        "IRC §174 amortization — 5-year domestic / 15-year foreign; track deferred tax liability vs. ASC 730",
        "State income tax nexus — corporate returns and payroll registrations for all states with remote employees",
    ],
    "series_b": [
        "All Series A requirements, plus:",
        "Post-Wayfair sales tax nexus — economic nexus thresholds (~$100K revenue or 200 transactions) in 45 states + DC",
        "FBAR (FinCEN 114) — due April 15 if aggregate foreign account balance ever exceeded $10,000",
        "IRC §382 ownership-change study after each equity round — limits annual NOL utilization permanently",
        "IRC §41 R&D Tax Credit — contemporaneous QRE documentation; §174 mandatory 5-year amortization (post-2022)",
        "IRC §280G — §4999 excise tax analysis on change-of-control acceleration payments",
        "IRC §482 transfer pricing — arm's-length pricing and contemporaneous documentation for all related-party transactions",
        "GILTI (IRC §951A) — include foreign subsidiary income annually; Form 5471 per CFC",
        "State income tax nexus — apportionment formula analysis as employee headcount grows across states",
        "EFTPS deposit schedule — reassess semiweekly vs. monthly classification after each hiring wave",
    ],
    "series_c_plus": [
        "All Series B requirements, plus:",
        "IRC §162(m) — $1M tax deduction cap on 'covered employee' compensation (permanent post-TCJA; no performance exception)",
        "ASC 606 / IRC §451 revenue recognition — five-step model compliance; deferred revenue schedule",
        "IRC §163(j) — business interest expense limited to 30% of ATI (EBIT basis post-2021)",
        "SOX §302 / §404 — internal control readiness if pre-IPO or recently public",
        "IRC §280G pre-IPO planning for all change-of-control and acceleration provisions",
        "IRC §174 — multi-year amortization schedules and deferred tax provision for accumulated R&D spend",
    ],
}

_STAGE_DISPLAY_NAMES: dict[str, str] = {
    "pre_seed": "Pre-seed",
    "seed": "Seed",
    "series_a": "Series A",
    "series_b": "Series B",
    "series_c_plus": "Series C+",
}

_STAGE_ALIASES_API: dict[str, str] = {
    "pre-seed": "pre_seed", "preseed": "pre_seed", "pre_seed": "pre_seed",
    "seed": "seed",
    "series-a": "series_a", "series_a": "series_a", "a": "series_a",
    "series-b": "series_b", "series_b": "series_b", "b": "series_b",
    "series-c": "series_c_plus", "series_c": "series_c_plus",
    "series-c+": "series_c_plus", "series_c_plus": "series_c_plus",
    "c": "series_c_plus", "c+": "series_c_plus",
    "growth": "series_c_plus", "pre-ipo": "series_c_plus", "pre_ipo": "series_c_plus",
}

_STAGE_ORDER = ["pre_seed", "seed", "series_a", "series_b", "series_c_plus"]

_COMPLIANCE_SYSTEM = (
    "You are an expert IRS and startup financial compliance analyst. "
    "You will be given one or more financial documents (with their type labels) "
    "uploaded by a startup founder, along with their funding stage. "
    "Analyze the documents for IRS and tax compliance risks specific to their stage. "
    "Focus only on what the documents show or are missing — do not invent facts. "
    "If a document type is present but the content is insufficient to evaluate a "
    "compliance area, say so explicitly in the finding. "
    "Return ONLY valid JSON with this exact schema:\n"
    '{"overall_risk": "Low|Moderate|High|Unknown", "risk_score": 0-100, '
    '"summary": "1-2 sentence summary", '
    '"issues": [{"area": "string", "irc_section": "§xxx or N/A", '
    '"finding": "what the document shows or is missing", '
    '"recommendation": "specific next step", "severity": "high|medium|low"}], '
    '"notes": ["string"]}\n'
    "No prose outside the JSON. No markdown fences."
)


def _build_compliance_prompt(
    company_name: str,
    stage_key: str,
    documents: list[dict],  # [{"type": label, "text": str}]
) -> str:
    stage_name = _STAGE_DISPLAY_NAMES.get(stage_key, stage_key)
    requirements = _COMPLIANCE_STAGE_REQUIREMENTS.get(stage_key, [])

    lines = [
        f"COMPANY: {company_name}",
        f"FUNDING STAGE: {stage_name}",
        "",
        f"CRITICAL COMPLIANCE AREAS FOR {stage_name.upper()}:",
    ]
    for req in requirements:
        lines.append(f"  • {req}")

    lines += ["", "DOCUMENTS PROVIDED:"]
    for i, doc in enumerate(documents, 1):
        doc_type = doc.get("type") or "Unspecified document"
        text = doc.get("text", "").strip()
        if len(text) > 6000:
            text = text[:6000] + "\n[TRUNCATED]"
        lines += [f"\n--- Document {i}: {doc_type} ---", text or "(empty)"]

    lines += [
        "",
        "Evaluate each compliance area listed above against the documents provided. "
        "Flag any area where documentation is missing, incomplete, or shows a potential "
        "IRS/tax risk. Assign overall_risk and risk_score based on the number and severity "
        "of issues found.",
    ]
    return "\n".join(lines)


@app.post("/api/compliance/audit")
async def compliance_audit(
    company_name: Optional[str] = Form(None),
    funding_round: Optional[str] = Form(None),
    document_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    files: List[UploadFile] = File(default=[]),
    document_types: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
):
    """Stage-aware IRS/tax compliance audit of uploaded financial documents.

    Accepts one or more documents with optional document-type labels and a
    funding round, then uses an LLM to surface stage-specific compliance gaps.
    Backward-compatible with the single-file + document_text legacy interface.
    """
    stage_key = _STAGE_ALIASES_API.get((funding_round or "seed").strip().lower(), "seed")
    name = (company_name or "").strip() or "(unspecified)"

    doc_type_labels: list[str] = []
    if document_types:
        try:
            parsed = _json.loads(document_types)
            if isinstance(parsed, list):
                doc_type_labels = [str(t) for t in parsed]
        except (ValueError, TypeError):
            pass

    # Collect all document texts with type labels.
    documents: list[dict] = []

    all_files = [f for f in ([file] + list(files)) if f is not None and f.filename]
    for i, uf in enumerate(all_files):
        try:
            text = _extract_text(uf)
        except Exception as exc:
            raise HTTPException(400, f"Could not read '{uf.filename}': {exc}") from exc
        label = doc_type_labels[i] if i < len(doc_type_labels) else uf.filename
        documents.append({"type": label, "text": text})

    if document_text and document_text.strip():
        documents.append({"type": "Pasted text", "text": document_text.strip()})

    if not documents:
        raise HTTPException(400, "Provide at least one file or document_text.")

    prompt = _build_compliance_prompt(name, stage_key, documents)
    try:
        client = _get_llm_client(provider=llm_provider, model=llm_model)
        resp = client.complete(
            messages=[
                {"role": "system", "content": _COMPLIANCE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        result = _json.loads(resp.content or "{}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Compliance audit failed: {exc}") from exc

    result.setdefault("overall_risk", "Unknown")
    result.setdefault("risk_score", None)
    result.setdefault("summary", "No summary returned.")
    result.setdefault("issues", [])
    result.setdefault("notes", [])
    result["stage"] = _STAGE_DISPLAY_NAMES.get(stage_key, stage_key)
    return result


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
    # Optional founder questionnaire + PRD that drive the AI-tailored CustomScanner.
    # When omitted, the custom scanner is a no-op (returns no findings).
    questionnaire: Optional[dict] = None
    prd_text: Optional[str] = None


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
            custom_questionnaire=req.questionnaire,
            custom_prd_text=req.prd_text,
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
