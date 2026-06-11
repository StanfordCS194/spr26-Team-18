from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Confidence,
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    ScanContext,
    Severity,
    SourceLocation,
)

# An injectable LLM completion function: (system_prompt, user_prompt) -> raw text.
# The default implementation calls OpenAI; tests inject a fake to stay offline.
LLMComplete = Callable[[str, str], str]

_DEFAULT_MODEL = "gpt-4o-mini"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Ported from the legacy /api/startup/custom-rules endpoint.
_RULES_SYSTEM = (
    "You are a startup diligence expert. Given a founder's questionnaire and PRD, "
    "write a CUSTOM ruleset of 5-8 specific, checkable rules that matter for THIS "
    "product (not generic best practices already covered by stock scanners: secrets, "
    "dependency vulnerabilities, licenses, outdated deps, GDPR/CCPA/COPPA code "
    "patterns). Focus on what is unique to their stage, customer, industry, data, and "
    "go-to-market. Each rule must be verifiable from the repository facts and source "
    "excerpts a grader will be shown. "
    "Return ONLY a JSON object: "
    '{"rules": [{"id": "snake_case_id", "title": "short rule title", '
    '"weight": 5-20, "what_to_check": "explicit criteria the grader will use", '
    '"fix": "one-line concrete remediation"}]}. No prose, no markdown fences.'
)

# Ported from the legacy /api/startup/custom-grade endpoint, extended to ask the
# model to cite a repo-relative file path so we can attach Finding evidence.
_GRADE_SYSTEM = (
    "You are evaluating a startup repository against a CUSTOM ruleset. For each rule, "
    "decide passed=true/false STRICTLY from the evidence shown. If evidence is "
    "missing, passed=false and say so in observed. Never invent facts. When a rule "
    "fails because of something visible in a specific file, set evidence_path to that "
    "repo-relative path (exactly as listed); otherwise set evidence_path to null. "
    "Return ONLY JSON: "
    '{"results": [{"id": "<rule id>", "passed": bool, '
    '"observed": "<1 short sentence of evidence>", "evidence_path": "<path or null>"}]}. '
    "Include every rule id exactly once. No markdown fences."
)


def _weight_to_severity(weight: int) -> Severity:
    if weight >= 18:
        return "high"
    if weight >= 12:
        return "medium"
    if weight >= 6:
        return "low"
    return "info"


class CustomScanner:
    """AI-tailored compliance scanner.

    Generates a startup-specific ruleset from a founder questionnaire (and optional
    PRD), grades the repository snapshot against those rules with an LLM, and emits a
    Finding for every rule the repository fails.

    Opt-in by design: with no questionnaire/PRD or no available LLM, ``scan`` returns
    an empty list so the scanner never disrupts a default scan.
    """

    id = "custom_compliance"
    name = "AI-Tailored Custom Scanner"
    version = "0.1.0"

    def __init__(
        self,
        *,
        questionnaire: dict | None = None,
        prd_text: str | None = None,
        llm: LLMComplete | None = None,
        model: str | None = None,
        api_key: str | None = None,
        max_rules: int = 8,
        max_source_chars: int = 12_000,
    ) -> None:
        self._questionnaire = questionnaire or {}
        self._prd_text = prd_text
        self._model = model or _DEFAULT_MODEL
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._llm = llm
        self._max_rules = max_rules
        self._max_source_chars = max_source_chars

    @property
    def enabled(self) -> bool:
        """True only when we have tailoring input AND a way to call an LLM."""
        has_input = bool(self._questionnaire) or bool(self._prd_text)
        has_llm = self._llm is not None or bool(self._api_key)
        return has_input and has_llm

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        return self._scan(snapshot, context=None)

    def scan_with_context(self, snapshot: RepositorySnapshot, context: ScanContext) -> list[Finding]:
        return self._scan(snapshot, context=context)

    def _scan(self, snapshot: RepositorySnapshot, *, context: ScanContext | None) -> list[Finding]:
        if not self.enabled:
            return []

        complete = self._llm or self._default_llm
        repo_facts = self._summarize_repo(snapshot)
        legal_context = self._legal_context_prompt(context)

        rules = self._generate_rules(complete, repo_facts, legal_context)
        if not rules:
            return []

        graded = self._grade(complete, rules, snapshot, repo_facts, legal_context)
        return self._to_findings(graded, snapshot)

    # ── prompt building ─────────────────────────────────────────────────────

    def _summarize_repo(self, snapshot: RepositorySnapshot) -> str:
        text_files = [f for f in snapshot.files if f.is_text]
        extensions: dict[str, int] = {}
        for f in snapshot.files:
            if f.extension:
                extensions[f.extension] = extensions.get(f.extension, 0) + 1
        top_ext = sorted(extensions.items(), key=lambda kv: (-kv[1], kv[0]))[:8]

        readme = next(
            (f for f in text_files if f.path.lower().split("/")[-1].startswith("readme")),
            None,
        )
        filenames = [f.path for f in snapshot.files][:40]

        lines = [
            f"source: {snapshot.source.kind}:{snapshot.source.location}",
            f"file_count: {len(snapshot.files)}",
            "top_extensions: " + ", ".join(f"{ext}({n})" for ext, n in top_ext),
            "files: " + ", ".join(filenames),
        ]
        if readme and readme.text:
            lines += ["", "README excerpt:", readme.text[:1200]]
        return "\n".join(lines)

    def _rules_user_prompt(self, repo_facts: str, legal_context: str = "") -> str:
        lines = ["Founder questionnaire:"]
        for key, value in self._questionnaire.items():
            if value:
                lines.append(f"  - {key}: {value}")
        if self._prd_text:
            lines += ["", "PRD excerpt:", self._prd_text[:4000]]
        if legal_context:
            lines += ["", legal_context]
        lines += ["", "Repository facts:", repo_facts]
        return "\n".join(lines)

    def _grade_user_prompt(
        self,
        rules: list[dict],
        snapshot: RepositorySnapshot,
        repo_facts: str,
        legal_context: str = "",
    ) -> str:
        lines = ["Rules to evaluate:"]
        for rule in rules:
            lines.append(
                f"  - id={rule['id']} | title={rule['title']} | check: {rule['what_to_check']}"
            )
        lines += ["", "Repository facts:", repo_facts]
        if self._prd_text:
            lines += ["", "PRD excerpt:", self._prd_text[:4000]]
        if legal_context:
            lines += ["", legal_context]

        # Provide a bounded slice of source so the grader can cite files.
        lines += ["", "Source excerpts:"]
        budget = self._max_source_chars
        for f in snapshot.files:
            if not f.is_text or f.path_role in ("tests", "docs") or not f.text:
                continue
            if budget <= 0:
                break
            excerpt = f.text[: min(800, budget)]
            budget -= len(excerpt)
            lines += [f"--- {f.path} ---", excerpt]
        return "\n".join(lines)

    def _legal_context_prompt(self, context: ScanContext | None) -> str:
        if not context or not context.legal_guidance:
            return ""
        lines = [
            "Legal guidance context:",
            "Use this source-backed legal context only to focus the custom rules and grading.",
            "Do not invent repository facts, citations, obligations, files, or line numbers.",
            "A failed rule still needs support from the questionnaire, PRD, repository facts, or source excerpts.",
        ]
        for index, guidance in enumerate(context.legal_guidance[:5], start=1):
            citations = "; ".join(
                citation.citation or citation.title
                for citation in guidance.citations[:2]
                if citation.citation or citation.title
            )
            citation_text = f" | citations: {citations}" if citations else ""
            hints = ", ".join(guidance.detection_hints[:4])
            hint_text = f" | hints: {hints}" if hints else ""
            lines.append(
                f"{index}. [{guidance.category}] {guidance.title} "
                f"(confidence: {guidance.confidence}) | legal basis: {guidance.legal_basis} "
                f"| risk signal: {guidance.risk_signal}{hint_text}{citation_text}"
            )
        return "\n".join(lines)

    # ── LLM steps ───────────────────────────────────────────────────────────

    def _generate_rules(self, complete: LLMComplete, repo_facts: str, legal_context: str = "") -> list[dict]:
        raw = complete(_RULES_SYSTEM, self._rules_user_prompt(repo_facts, legal_context))
        parsed = _safe_json(raw)
        rules = parsed.get("rules") if isinstance(parsed, dict) else None
        if not isinstance(rules, list):
            return []

        cleaned: list[dict] = []
        for i, r in enumerate(rules[: self._max_rules]):
            if not isinstance(r, dict):
                continue
            cleaned.append(
                {
                    "id": str(r.get("id") or f"custom_{i}")[:64],
                    "title": str(r.get("title") or "")[:140],
                    "weight": _clamp_int(r.get("weight"), default=8, lo=1, hi=25),
                    "what_to_check": str(r.get("what_to_check") or "")[:600],
                    "fix": str(r.get("fix") or "")[:240],
                }
            )
        return cleaned

    def _grade(
        self,
        complete: LLMComplete,
        rules: list[dict],
        snapshot: RepositorySnapshot,
        repo_facts: str,
        legal_context: str = "",
    ) -> list[dict]:
        raw = complete(_GRADE_SYSTEM, self._grade_user_prompt(rules, snapshot, repo_facts, legal_context))
        parsed = _safe_json(raw)
        results = parsed.get("results") if isinstance(parsed, dict) else None
        by_id = {
            str(r.get("id")): r
            for r in (results or [])
            if isinstance(r, dict)
        }

        graded: list[dict] = []
        for rule in rules:
            hit = by_id.get(rule["id"]) or {}
            graded.append(
                {
                    **rule,
                    "passed": bool(hit.get("passed", False)),
                    "observed": str(hit.get("observed") or "no evidence found")[:240],
                    "evidence_path": _clean_path(hit.get("evidence_path")),
                }
            )
        return graded

    # ── Finding assembly ──────────────────────────────────────────────────────

    def _to_findings(self, graded: list[dict], snapshot: RepositorySnapshot) -> list[Finding]:
        valid_paths = {f.path for f in snapshot.files}
        findings: list[Finding] = []
        for rule in graded:
            if rule["passed"]:
                continue

            evidence_path = rule["evidence_path"] if rule["evidence_path"] in valid_paths else None
            location = SourceLocation(path=evidence_path) if evidence_path else None
            findings.append(
                Finding(
                    id=stable_finding_id(self.id, rule["id"], rule["id"]),
                    title=rule["title"] or f"Custom rule: {rule['id']}",
                    description=(
                        f"Tailored compliance rule for this startup. "
                        f"Criteria: {rule['what_to_check']}"
                    ),
                    category="custom_compliance",
                    severity=_weight_to_severity(rule["weight"]),
                    confidence="low",  # LLM-judged against a tailored rubric
                    evidence=[
                        FindingEvidence(
                            location=location,
                            description=rule["observed"],
                        )
                    ],
                    recommendation=rule["fix"] or "Address the failing custom rule above.",
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )
        return findings

    # ── default LLM (OpenAI over urllib; tests inject a fake instead) ────────────

    def _default_llm(self, system: str, user: str) -> str:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY not configured for CustomScanner")
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            _OPENAI_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"CustomScanner LLM request failed: {exc}") from exc
        return payload["choices"][0]["message"]["content"] or ""


def _safe_json(raw: str) -> dict:
    try:
        value = json.loads((raw or "").strip())
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _clamp_int(value: object, *, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _clean_path(value: object) -> str | None:
    if not value or not isinstance(value, str):
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()
