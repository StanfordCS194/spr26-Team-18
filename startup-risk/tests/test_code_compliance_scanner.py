from __future__ import annotations

import json
from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.code_compliance_scanner import CodeComplianceScanner


def _snapshot(*files: tuple[str, str]) -> RepositorySnapshot:
    return RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[
            FileSnapshot(
                path=path,
                size_bytes=len(text),
                extension=Path(path).suffix.lower(),
                text=text,
            )
            for path, text in files
        ],
    )


class _FakeLLM:
    """Returns a canned findings payload and records the prompts it receives."""

    def __init__(self, findings: list[dict]) -> None:
        self._findings = findings
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return json.dumps({"findings": self._findings})


def _f(file: str, line: int = 1, rule: str = "token_in_browser_storage",
       severity: str = "high") -> dict:
    return {
        "rule": rule,
        "title": "Auth token in browser storage",
        "description": "Token written to localStorage, readable by injected scripts.",
        "severity": severity,
        "recommendation": "Use HttpOnly Secure cookies instead.",
        "file": file,
        "line": line,
        "excerpt": "localStorage.setItem('token', t)",
    }


def test_no_op_without_llm():
    scanner = CodeComplianceScanner(api_key="")
    assert scanner.enabled is False
    assert scanner.scan(_snapshot(("src/auth.js", "localStorage.setItem('t', x)"))) == []


def test_maps_llm_findings_to_finding_objects():
    fake = _FakeLLM([_f("src/auth.js", line=12)])
    scanner = CodeComplianceScanner(llm=fake)
    assert scanner.enabled is True

    findings = scanner.scan(_snapshot(("src/auth.js", "localStorage.setItem('t', x)\n")))
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner_id == "code_compliance"
    assert f.category == "code_compliance"
    assert f.severity == "high"
    assert f.evidence[0].location.path == "src/auth.js"
    assert f.evidence[0].location.line_start == 12
    assert "cookie" in f.recommendation.lower()


def test_drops_finding_for_path_not_in_snapshot():
    fake = _FakeLLM([_f("does/not/exist.js"), _f("src/app.py")])
    scanner = CodeComplianceScanner(llm=fake)
    findings = scanner.scan(_snapshot(("src/app.py", "x = 1\n")))
    assert len(findings) == 1
    assert findings[0].evidence[0].location.path == "src/app.py"


def test_invalid_severity_defaults_to_medium():
    fake = _FakeLLM([_f("src/app.py", severity="catastrophic")])
    scanner = CodeComplianceScanner(llm=fake)
    findings = scanner.scan(_snapshot(("src/app.py", "x = 1\n")))
    assert findings[0].severity == "medium"


def test_malformed_json_is_safe():
    def bad_llm(system: str, user: str) -> str:
        return "not json"

    scanner = CodeComplianceScanner(llm=bad_llm)
    assert scanner.scan(_snapshot(("src/app.py", "x = 1\n"))) == []


def test_skips_tests_docs_and_nonsource_files():
    fake = _FakeLLM([])
    scanner = CodeComplianceScanner(llm=fake)
    scanner.scan(_snapshot(
        ("src/app.py", "x = 1\n"),
        ("tests/test_app.py", "secret = 'sk-123'\n"),
        ("docs/guide.md", "localStorage.setItem('t', x)\n"),
        ("README.md", "hello\n"),
    ))
    # Exactly one chunk, and it only contains the source file.
    assert len(fake.calls) == 1
    prompt = fake.calls[0][1]
    assert "src/app.py" in prompt
    assert "tests/test_app.py" not in prompt
    assert "docs/guide.md" not in prompt
    assert "README.md" not in prompt


def test_line_numbers_present_in_prompt():
    fake = _FakeLLM([])
    scanner = CodeComplianceScanner(llm=fake)
    scanner.scan(_snapshot(("src/app.py", "first\nsecond\n")))
    prompt = fake.calls[0][1]
    assert "1: first" in prompt and "2: second" in prompt


def test_chunks_large_input_into_multiple_calls():
    big = "x = 1\n" * 60  # ~360 chars each
    fake = _FakeLLM([])
    scanner = CodeComplianceScanner(llm=fake, max_chunk_chars=300)
    scanner.scan(_snapshot(
        ("src/a.py", big),
        ("src/b.py", big),
        ("src/c.py", big),
    ))
    assert len(fake.calls) >= 2  # batched across multiple calls, not one


def test_all_findings_have_scanner_id_and_safe_ids():
    fake = _FakeLLM([_f("src/app.py", line=3), _f("src/app.py", line=7, rule="insecure_cookie")])
    scanner = CodeComplianceScanner(llm=fake)
    findings = scanner.scan(_snapshot(("src/app.py", "a\n" * 10)))
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    for f in findings:
        assert f.scanner_id == "code_compliance"
        assert all(c in allowed for c in f.id)
