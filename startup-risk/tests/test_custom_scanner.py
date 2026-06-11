from __future__ import annotations

import json
from pathlib import Path

from startup_risk.core.models import (
    FileSnapshot,
    LegalCitation,
    RepositorySnapshot,
    RepositorySource,
    ScanContext,
    ScannerLegalGuidance,
)
from startup_risk.scanners.custom_scanner import CustomScanner, _weight_to_severity


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
    """Records prompts and returns canned JSON for the two-step flow."""

    def __init__(self, rules: dict, results: dict) -> None:
        self._rules = rules
        self._results = results
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        # First call generates rules; second grades. Distinguish by call order.
        return json.dumps(self._rules if len(self.calls) == 1 else self._results)


_RULES = {
    "rules": [
        {
            "id": "soc2_audit_logging",
            "title": "Audit logging for enterprise customers",
            "weight": 16,
            "what_to_check": "Repo writes an audit log on sensitive actions.",
            "fix": "Add structured audit logging on auth and data-access events.",
        },
        {
            "id": "data_residency",
            "title": "EU data residency configurable",
            "weight": 8,
            "what_to_check": "Storage region is configurable for EU customers.",
            "fix": "Expose a region setting and document EU hosting.",
        },
    ]
}

_QUESTIONNAIRE = {"stage": "seed", "customers": "enterprise", "sensitive_data": "PII"}


def test_no_op_without_questionnaire_or_llm():
    # No questionnaire and no api key/llm -> disabled -> empty.
    scanner = CustomScanner()
    assert scanner.enabled is False
    assert scanner.scan(_snapshot(("src/app.py", "print('hi')"))) == []


def test_no_op_with_input_but_no_llm():
    scanner = CustomScanner(questionnaire=_QUESTIONNAIRE, api_key="")
    assert scanner.enabled is False
    assert scanner.scan(_snapshot(("src/app.py", "x = 1"))) == []


def test_failed_rules_become_findings():
    results = {
        "results": [
            {"id": "soc2_audit_logging", "passed": False,
             "observed": "No audit logging found in src.", "evidence_path": "src/app.py"},
            {"id": "data_residency", "passed": True,
             "observed": "region setting present", "evidence_path": None},
        ]
    }
    fake = _FakeLLM(_RULES, results)
    scanner = CustomScanner(questionnaire=_QUESTIONNAIRE, llm=fake)
    assert scanner.enabled is True

    findings = scanner.scan(_snapshot(("src/app.py", "def handler():\n    return 1\n")))

    # Only the failed rule produces a finding.
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner_id == "custom_compliance"
    assert f.category == "custom_compliance"
    assert f.severity == "medium"  # weight 16 -> medium
    assert "audit log" in f.recommendation.lower()
    assert f.evidence[0].location is not None
    assert f.evidence[0].location.path == "src/app.py"
    # Two LLM calls: generate rules, then grade.
    assert len(fake.calls) == 2


def test_profile_and_legal_context_are_included_in_custom_scanner_prompts():
    results = {
        "results": [
            {"id": "soc2_audit_logging", "passed": False, "observed": "missing", "evidence_path": "src/app.py"},
            {"id": "data_residency", "passed": True, "observed": "ok", "evidence_path": None},
        ]
    }
    fake = _FakeLLM(_RULES, results)
    scanner = CustomScanner(questionnaire=_QUESTIONNAIRE, llm=fake)
    context = ScanContext(
        profile={"industry": "fintech", "stage": "seed", "customers": "enterprise"},
        legal_guidance=[
            ScannerLegalGuidance(
                rule_id="legal_guidance.audit",
                category="security_controls",
                title="Audit controls expected",
                legal_basis="Agency guidance expects audit controls.",
                risk_signal="missing audit trail",
                recommendation="Add audit controls.",
                citations=[LegalCitation(title="Agency guidance", citation="AG-1")],
                confidence="medium",
            )
        ],
    )

    findings = scanner.scan_with_context(_snapshot(("src/app.py", "x = 1")), context)

    assert len(findings) == 1
    assert len(fake.calls) == 2
    for _, prompt in fake.calls:
        assert "Startup profile context:" in prompt
        assert "- Industry: fintech" in prompt
        assert "Legal guidance context:" in prompt
        assert "Audit controls expected" in prompt


def test_evidence_path_outside_snapshot_is_dropped():
    results = {
        "results": [
            {"id": "soc2_audit_logging", "passed": False,
             "observed": "missing", "evidence_path": "does/not/exist.py"},
            {"id": "data_residency", "passed": True, "observed": "ok", "evidence_path": None},
        ]
    }
    scanner = CustomScanner(questionnaire=_QUESTIONNAIRE, llm=_FakeLLM(_RULES, results))
    findings = scanner.scan(_snapshot(("src/app.py", "x = 1")))
    assert len(findings) == 1
    # Path not in snapshot -> no location attached, but finding still emitted.
    assert findings[0].evidence[0].location is None


def test_all_rules_pass_yields_no_findings():
    results = {
        "results": [
            {"id": "soc2_audit_logging", "passed": True, "observed": "ok", "evidence_path": None},
            {"id": "data_residency", "passed": True, "observed": "ok", "evidence_path": None},
        ]
    }
    scanner = CustomScanner(questionnaire=_QUESTIONNAIRE, llm=_FakeLLM(_RULES, results))
    assert scanner.scan(_snapshot(("src/app.py", "x = 1"))) == []


def test_malformed_rules_json_is_safe():
    def bad_llm(system: str, user: str) -> str:
        return "not json at all"

    scanner = CustomScanner(questionnaire=_QUESTIONNAIRE, llm=bad_llm)
    assert scanner.scan(_snapshot(("src/app.py", "x = 1"))) == []


def test_weight_to_severity_mapping():
    assert _weight_to_severity(20) == "high"
    assert _weight_to_severity(18) == "high"
    assert _weight_to_severity(12) == "medium"
    assert _weight_to_severity(6) == "low"
    assert _weight_to_severity(3) == "info"
