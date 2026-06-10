from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

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
_VALID_SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})

# Application source files most agents reason over.
SOURCE_EXTENSIONS = frozenset({
    ".js", ".jsx", ".ts", ".tsx",
    ".py", ".go", ".rb", ".java", ".kt", ".cs",
    ".swift", ".php", ".c", ".cpp", ".rs", ".scala",
})
SKIP_PATH_ROLES = frozenset({"docs", "tests"})

_FINDING_SCHEMA = (
    'Return ONLY JSON: {"findings": [{"rule": "snake_case_category", "title": "...", '
    '"description": "why it is a risk", "severity": "info|low|medium|high|critical", '
    '"recommendation": "concrete fix", "file": "exact path as given", "line": 0, '
    '"excerpt": "the offending line, trimmed"}]}. If there are no issues return '
    '{"findings": []}. No prose, no markdown fences.'
)


def safe_json(raw: str) -> dict:
    try:
        value = json.loads((raw or "").strip())
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def clean_path(value: object) -> str | None:
    if not value or not isinstance(value, str):
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


class LLMAgent:
    """Base class for LLM-driven scanner agents.

    A subclass sets ``id``/``name``/``version``/``category`` and a ``system``
    prompt describing what to look for. The base reads line-numbered source
    (batched under a char budget across calls so large repos are covered, not
    truncated), calls the LLM, and maps the returned items to validated
    ``Finding`` objects whose evidence is tied to a real file+line.

    Opt-in & no-op safe: with no injected ``llm`` and no API key, ``scan``
    returns an empty list so the agent never blocks a default scan.
    """

    id: str = ""
    name: str = ""
    version: str = "0.1.0"
    category: str = ""
    # The instruction prompt — subclasses provide the task; the schema is appended.
    system: str = ""
    # Files the agent reasons over. Subclasses may widen this (e.g. infra configs).
    extensions: frozenset[str] = SOURCE_EXTENSIONS

    def __init__(
        self,
        *,
        llm: LLMComplete | None = None,
        model: str | None = None,
        api_key: str | None = None,
        max_chunk_chars: int = 12_000,
        max_file_chars: int = 8_000,
    ) -> None:
        self._llm = llm
        self._model = model or _DEFAULT_MODEL
        self._api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._max_chunk_chars = max_chunk_chars
        self._max_file_chars = min(max_file_chars, max_chunk_chars)

    @property
    def enabled(self) -> bool:
        return self._llm is not None or bool(self._api_key)

    @property
    def system_prompt(self) -> str:
        return f"{self.system}\n{_FINDING_SCHEMA}"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        if not self.enabled:
            return []
        complete = self._llm or self._default_llm
        valid_paths = {f.path for f in snapshot.files}

        findings: list[Finding] = []
        seen: set[str] = set()
        for chunk in self._chunks(snapshot):
            for item in self._parse(complete(self.system_prompt, chunk)):
                finding = self._to_finding(item, valid_paths)
                if finding is not None and finding.id not in seen:
                    seen.add(finding.id)
                    findings.append(finding)
        return findings

    # ── file selection / prompt building ───────────────────────────────────────

    def _is_eligible(self, file) -> bool:
        if file.text is None or file.path_role in SKIP_PATH_ROLES:
            return False
        return file.extension in self.extensions

    def _eligible_files(self, snapshot: RepositorySnapshot) -> Iterator:
        for file in snapshot.files:
            if self._is_eligible(file):
                yield file

    def _chunks(self, snapshot: RepositorySnapshot) -> Iterator[str]:
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
        lines = file.text[: self._max_file_chars].splitlines()
        numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        return f"=== FILE: {file.path} ===\n{numbered}"

    # ── parsing / finding assembly ─────────────────────────────────────────────

    def _parse(self, raw: str) -> list[dict]:
        parsed = safe_json(raw)
        items = parsed.get("findings")
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []

    def _to_finding(self, item: dict, valid_paths: set[str]) -> Finding | None:
        path = item.get("file")
        if not path or path not in valid_paths:
            return None

        rule = str(item.get("rule") or self.category or "risk")[:64]
        severity = str(item.get("severity") or "medium").lower()
        if severity not in _VALID_SEVERITIES:
            severity = "medium"
        line = item.get("line")
        line = line if isinstance(line, int) and line >= 1 else None
        title = str(item.get("title") or self.name)[:140]
        excerpt = str(item.get("excerpt") or "")[:200] or None

        return Finding(
            id=stable_finding_id(self.id, rule, f"{path}:{line}"),
            title=title,
            description=str(item.get("description") or title)[:600],
            category=self.category,
            severity=severity,
            confidence="medium",
            evidence=[
                FindingEvidence(
                    location=SourceLocation(path=path, line_start=line),
                    description=f"Identified by the {self.name}.",
                    excerpt=excerpt,
                )
            ],
            recommendation=str(item.get("recommendation") or "Address the risk above.")[:240],
            scanner_id=self.id,
            scanner_version=self.version,
        )

    # ── default LLM (OpenAI over urllib; tests inject a fake instead) ────────────

    def _default_llm(self, system: str, user: str) -> str:
        if not self._api_key:
            raise RuntimeError(f"OPENAI_API_KEY not configured for {self.id}")
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
            raise RuntimeError(f"{self.id} LLM request failed: {exc}") from exc
        return payload["choices"][0]["message"]["content"] or ""
