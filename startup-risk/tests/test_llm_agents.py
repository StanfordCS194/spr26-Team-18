from __future__ import annotations

import json
from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.auth_agent import AuthAccessControlAgent
from startup_risk.scanners.infra_agent import InfraMisconfigAgent
from startup_risk.scanners.pii_agent import PIIDataFlowAgent
from startup_risk.scanners.vuln_exploitability_agent import VulnExploitabilityAgent


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
    def __init__(self, findings: list[dict]) -> None:
        self._findings = findings
        self.calls: list[tuple[str, str]] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return json.dumps({"findings": self._findings})


def _f(file: str, line: int = 1, rule: str = "risk", severity: str = "high") -> dict:
    return {
        "rule": rule, "title": "Risk", "description": "why",
        "severity": severity, "recommendation": "fix it",
        "file": file, "line": line, "excerpt": "code",
    }


# ── shared base behavior (via AuthAccessControlAgent) ───────────────────────────

def test_no_op_without_llm():
    agent = AuthAccessControlAgent(api_key="")
    assert agent.enabled is False
    assert agent.scan(_snapshot(("src/api.py", "def get(id): return db[id]"))) == []


def test_maps_findings_with_category_and_scanner_id():
    fake = _FakeLLM([_f("src/api.py", line=4)])
    agent = AuthAccessControlAgent(llm=fake)
    findings = agent.scan(_snapshot(("src/api.py", "x\n" * 10)))
    assert len(findings) == 1
    f = findings[0]
    assert f.scanner_id == "auth_access_control"
    assert f.category == "access_control"
    assert f.evidence[0].location.path == "src/api.py"
    assert f.evidence[0].location.line_start == 4


def test_drops_unknown_path_and_defaults_bad_severity():
    fake = _FakeLLM([_f("nope.py"), _f("src/api.py", severity="boom")])
    agent = AuthAccessControlAgent(llm=fake)
    findings = agent.scan(_snapshot(("src/api.py", "x = 1\n")))
    assert len(findings) == 1
    assert findings[0].severity == "medium"


def test_pii_agent_category_and_skips_tests():
    fake = _FakeLLM([])
    agent = PIIDataFlowAgent(llm=fake)
    agent.scan(_snapshot(("src/app.py", "email = req.email\n"), ("tests/t.py", "email='x'\n")))
    assert agent.category == "data_privacy"
    prompt = fake.calls[0][1]
    assert "src/app.py" in prompt and "tests/t.py" not in prompt


def test_infra_agent_matches_dockerfile_without_extension():
    fake = _FakeLLM([_f("Dockerfile", line=1)])
    agent = InfraMisconfigAgent(llm=fake)
    findings = agent.scan(_snapshot(("Dockerfile", "FROM node\nUSER root\n")))
    assert len(findings) == 1
    assert findings[0].scanner_id == "infra_misconfig"


def test_infra_agent_ignores_plain_source():
    fake = _FakeLLM([])
    agent = InfraMisconfigAgent(llm=fake)
    agent.scan(_snapshot(("src/app.py", "print('hi')\n")))
    # No infra files -> no chunks -> no LLM call.
    assert fake.calls == []


# ── vuln exploitability agent (tool-grounded) ──────────────────────────────────

def test_vuln_agent_no_op_without_facts():
    fake = _FakeLLM([_f("requirements.txt")])
    agent = VulnExploitabilityAgent(llm=fake, vuln_provider=lambda snap: [])
    assert agent.scan(_snapshot(("requirements.txt", "lodash==1.0\n"))) == []
    assert fake.calls == []  # no facts -> never calls the LLM


def test_vuln_agent_grounds_on_provided_facts():
    facts = [{
        "package": "lodash", "ecosystem": "npm", "version": "4.17.15",
        "vuln_id": "GHSA-p6mc-m468-83gw", "summary": "prototype pollution",
        "osv_severity": "high", "manifest_path": "package.json", "manifest_line": 12,
    }]
    fake = _FakeLLM([_f("src/util.js", line=3, rule="reachable_vuln")])
    agent = VulnExploitabilityAgent(llm=fake, vuln_provider=lambda snap: facts)
    findings = agent.scan(_snapshot(("src/util.js", "import _ from 'lodash'\n_.merge(a,b)\n")))
    assert len(findings) == 1
    assert findings[0].category == "dependency_vulnerability"
    assert findings[0].scanner_id == "vuln_exploitability"
    # Ground-truth CVE facts are passed into the prompt.
    assert "GHSA-p6mc-m468-83gw" in fake.calls[0][1]


def test_vuln_agent_enabled_requires_llm_and_tool():
    assert VulnExploitabilityAgent(api_key="", enable_osv=False).enabled is False
    assert VulnExploitabilityAgent(llm=_FakeLLM([]), enable_osv=True).enabled is True
