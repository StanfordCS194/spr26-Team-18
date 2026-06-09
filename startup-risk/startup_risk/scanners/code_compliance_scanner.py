from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    SourceLocation,
)

# An injectable LLM completion function: (system_prompt, user_prompt) -> raw text.
# The default implementation calls OpenAI; tests inject a fake to stay offline.
LLMComplete = Callable[[str, str], str]

_DEFAULT_MODEL = "gpt-4o-mini"
_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

_SOURCE_EXTENSIONS = frozenset({
    ".js", ".jsx", ".ts", ".tsx",
    ".py", ".go", ".rb", ".java", ".kt", ".cs",
    ".swift", ".php", ".c", ".cpp", ".rs", ".scala",
})

_SKIP_PATH_ROLES = frozenset({"docs", "tests"})
_VALID_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})

# How many characters of numbered source to pack into a single LLM call. Files
# are batched up to this budget so large repos are covered across several calls
# rather than silently truncated.
_MAX_CHUNK_CHARS = 12_000
_MAX_FILE_CHARS = 8_000

_SYSTEM = (
    "You are a code-compliance agent reviewing application source for privacy, "
    "security, and regulatory risk. You are given source files with line-numbered "
    "content. Identify concrete, evidence-backed compliance risks such as: "
    "auth tokens or secrets placed in browser storage; cookies set without "
    "HttpOnly/Secure/SameSite; flows handling children/minors without consent or "
    "age gating (COPPA); health/clinical (PHI) data without safeguards; third-party "
    "tracking/analytics SDKs without disclosed consent; and personal data (PII) "
    "stored without retention/deletion/consent/encryption handling. Use judgment — "
    "do NOT flag imports, comments, test fixtures, or code that already has the "
    "appropriate control nearby. Only report issues you can tie to a specific line. "
    "For each issue return: rule (snake_case category), title, description (why it is "
    "a risk), severity (info|low|medium|high|critical), recommendation (concrete fix), "
    "file (exact path as given), line (the line number), and excerpt (the offending "
    "line, trimmed). "
    'Return ONLY JSON: {"findings": [{"rule": "...", "title": "...", "description": '
    '"...", "severity": "...", "recommendation": "...", "file": "...", "line": 0, '
    '"excerpt": "..."}]}. If there are no issues, return {"findings": []}. '
    "No prose, no markdown fences."
)


class CodeComplianceScanner:
    """Detects privacy and security compliance risks in source code via an LLM agent.

    Opt-in by design: with no available LLM (no injected callable and no API key),
    ``scan`` returns an empty list so it never blocks a default scan.
    """

    id = "code_compliance"
    name = "Code Compliance"
    version = "2.0.0"

    def __init__(
        self,
        *,
        llm: LLMComplete | None = None,
        model: str | None = None,
        api_key: str | None = None,
        max_chunk_chars: int = _MAX_CHUNK_CHARS,
    ) -> None:
        self._llm = llm
        self._model = model or _DEFAULT_MODEL
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._max_chunk_chars = max_chunk_chars

    @property
    def enabled(self) -> bool:
        return self._llm is not None or bool(self._api_key)

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        if not self.enabled:
            return []

        complete = self._llm or self._default_llm
        valid_paths = {f.path for f in snapshot.files}

        findings: list[Finding] = []
        seen: set[str] = set()
        for chunk in self._chunks(snapshot):
            raw = complete(_SYSTEM, chunk)
            for item in self._parse(raw):
                finding = self._to_finding(item, valid_paths)
                if finding is not None and finding.id not in seen:
                    seen.add(finding.id)
                    findings.append(finding)
        return findings

    # ── prompt building ──────────────────────────────────────────────────────

    def _eligible_files(self, snapshot: RepositorySnapshot):
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.path_role in _SKIP_PATH_ROLES:
                continue
            if file.extension not in _SOURCE_EXTENSIONS:
                continue
            yield file

    def _chunks(self, snapshot: RepositorySnapshot):
        """Yield batches of line-numbered source, each under the char budget."""
        buf: list[str] = []
        size = 0
        for file in self._eligible_files(snapshot):
            block = self._number_file(file)
            if not block:
                continue
            if size + len(block) > self._max_chunk_chars and buf:
                yield "\n\n".join(buf)
                buf, size = [], 0
            buf.append(block)
            size += len(block)
        if buf:
            yield "\n\n".join(buf)

    def _number_file(self, file) -> str:
        lines = file.text[: self._max_file_chars()].splitlines()
        numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        return f"=== FILE: {file.path} ===\n{numbered}"

    def _max_file_chars(self) -> int:
        return min(_MAX_FILE_CHARS, self._max_chunk_chars)

    # ── parsing & finding assembly ─────────────────────────────────────────────

    def _parse(self, raw: str) -> list[dict]:
        try:
            parsed = json.loads((raw or "").strip())
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(parsed, dict):
            return []
        items = parsed.get("findings")
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []

    def _to_finding(self, item: dict, valid_paths: set[str]) -> Finding | None:
        path = item.get("file")
        if not path or path not in valid_paths:
            return None

        rule = str(item.get("rule") or "compliance_risk")[:64]
        severity = str(item.get("severity") or "medium").lower()
        if severity not in _VALID_SEVERITIES:
            severity = "medium"

        line = item.get("line")
        line = line if isinstance(line, int) and line >= 1 else None

        title = str(item.get("title") or "Code compliance risk")[:140]
        excerpt = str(item.get("excerpt") or "")[:200] or None

        return Finding(
            id=stable_finding_id(self.id, rule, f"{path}:{line}"),
            title=title,
            description=str(item.get("description") or title)[:600],
            category="code_compliance",
            severity=severity,
            confidence="medium",
            evidence=[
                FindingEvidence(
                    location=SourceLocation(path=path, line_start=line),
                    description=f"Matched {rule} via code-compliance agent.",
                    excerpt=excerpt,
                )
            ],
            recommendation=str(item.get("recommendation") or "Address the compliance risk above.")[:240],
            scanner_id=self.id,
            scanner_version=self.version,
        )

    # ── default LLM (OpenAI over urllib; tests inject a fake instead) ────────────

    def _default_llm(self, system: str, user: str) -> str:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY not configured for CodeComplianceScanner")
        body = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "max_tokens": 1200,
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
            raise RuntimeError(f"CodeComplianceScanner LLM request failed: {exc}") from exc
        return payload["choices"][0]["message"]["content"] or ""
