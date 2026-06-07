from __future__ import annotations

import json
from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.license_scanner.licenses import classify_license
from startup_risk.scanners.license_scanner.models import LLMBatchResponse
from startup_risk.scanners.license_scanner.parsers import npm, python, rust
from startup_risk.scanners.license_scanner.scanner import LicenseRiskScanner


class MockBatchProvider:
    name = "mock"

    def __init__(self, payload_by_task: dict[str, str] | None = None, error: str | None = None) -> None:
        self.payload_by_task = payload_by_task or {}
        self.error = error
        self.calls = []

    def submit_and_wait(self, tasks, *, timeout_seconds: int, poll_interval_seconds: int):
        self.calls.append(
            {
                "tasks": tasks,
                "timeout_seconds": timeout_seconds,
                "poll_interval_seconds": poll_interval_seconds,
            }
        )
        responses = []
        for task in tasks:
            if self.error:
                responses.append(LLMBatchResponse(task.task_id, None, self.error))
            else:
                responses.append(LLMBatchResponse(task.task_id, self.payload_by_task.get(task.task_id, _payload_for_task(task))))
        return responses


def snapshot(files: dict[str, str], *, skipped: dict[str, str] | None = None) -> RepositorySnapshot:
    snapshots = [
        FileSnapshot(
            path=path,
            size_bytes=len(text.encode("utf-8")),
            extension=Path(path).suffix.lower(),
            text=text,
        )
        for path, text in files.items()
    ]
    for path, reason in (skipped or {}).items():
        snapshots.append(
            FileSnapshot(
                path=path,
                size_bytes=999999,
                extension=Path(path).suffix.lower(),
                skipped_reason=reason,
            )
        )
    return RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=snapshots,
    )


def test_npm_parser_extracts_dependencies_license_and_lifecycle_script():
    file = FileSnapshot(
        path="package.json",
        size_bytes=1,
        extension=".json",
        text=json.dumps(
            {
                "name": "demo",
                "version": "1.0.0",
                "scripts": {"postinstall": "node evil.js"},
                "dependencies": {"left-pad": "1.3.0"},
            },
            indent=2,
        ),
    )

    deps = npm.parse(file)

    assert any(dep.name == "left-pad" and dep.relationship == "direct" for dep in deps)
    assert any("npm_lifecycle_script:postinstall" in dep.flags for dep in deps)


def test_python_and_rust_parsers_extract_dependencies_and_local_project_license():
    req = FileSnapshot(path="requirements.txt", size_bytes=1, extension=".txt", text="requests==2.31.0\n")
    cargo = FileSnapshot(
        path="Cargo.toml",
        size_bytes=1,
        extension=".toml",
        text='[package]\nname = "demo"\nversion = "0.1.0"\nlicense = "MIT OR Apache-2.0"\n\n[dependencies]\nserde = "1"\n',
    )

    py_deps = python.parse(req)
    rust_deps = rust.parse(cargo)

    assert py_deps[0].name == "requests"
    assert py_deps[0].version == "2.31.0"
    assert any(dep.name == "serde" for dep in rust_deps)
    assert any(dep.declared_license == "MIT OR Apache-2.0" and "local_project" in dep.flags for dep in rust_deps)


def test_license_classifier_buckets_common_risks():
    assert classify_license("MIT", has_notice=True).priority == "low"
    assert classify_license("Apache-2.0", has_notice=False).priority == "medium"
    assert classify_license("LGPL-3.0").priority == "medium"
    assert classify_license("AGPL-3.0").priority == "high"


def test_scanner_uses_batch_provider_and_allows_llm_to_clarify_unknown():
    snap = snapshot({"package-lock.json": '{"packages":{"node_modules/left-pad":{"version":"1.3.0"}}}'})
    provider = MockBatchProvider()

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    assert provider.calls
    assert not [finding for finding in findings if "unknown license" in finding.title.lower()]


def test_scanner_preserves_deterministic_high_risk_even_if_llm_disagrees():
    snap = snapshot(
        {
            "package-lock.json": json.dumps(
                {"packages": {"node_modules/copyleft": {"version": "1.0.0", "license": "AGPL-3.0"}}}
            )
        }
    )
    provider = MockBatchProvider()

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    assert any("AGPL-3.0" in finding.title and finding.severity == "high" for finding in findings)


def test_malformed_batch_output_becomes_review_required_finding():
    snap = snapshot({"requirements.txt": "mystery==1.0\n"})
    provider = MockBatchProvider(payload_by_task={"license-scan-0001": "not-json"})

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    assert any("LLM batch" in finding.title and finding.severity == "high" for finding in findings)


def test_missing_batch_item_becomes_review_required_finding():
    snap = snapshot({"requirements.txt": "mystery==1.0\n"})
    provider = MockBatchProvider(payload_by_task={"license-scan-0001": '{"items":[]}'})

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    assert any("LLM batch" in finding.title and finding.severity == "high" for finding in findings)


def test_vendored_gpl_and_missing_license_are_flagged():
    snap = snapshot(
        {
            "third_party/gpllib/LICENSE": "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n",
            "vendor/no-license/index.js": "console.log('x')\n",
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert any("GPL" in finding.title and finding.severity == "high" for finding in findings)
    assert any("Vendored code has no clear license file" == finding.title for finding in findings)


def test_skipped_large_lockfile_is_reported():
    snap = snapshot({}, skipped={"package-lock.json": "file exceeds max_file_bytes"})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert any(finding.title == "License scanner skipped an input" for finding in findings)


def test_provider_error_becomes_review_required_finding():
    snap = snapshot({"requirements.txt": "mystery==1.0\n"})
    provider = MockBatchProvider(error="provider expired")

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    assert any("provider expired" in finding.description for finding in findings)


def test_unknown_runtime_dependency_is_medium_confidence_review_needed():
    snap = snapshot({"pyproject.toml": '[project]\ndependencies = ["asgiref"]\n'})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    unknown = _single_unknown_finding(findings)
    assert unknown.severity == "medium"
    assert unknown.confidence == "medium"
    assert "unknown_license" in unknown.id
    assert "did not establish a license" in unknown.description
    assert "Run with registry/artifact/LLM enrichment" in unknown.recommendation


def test_unknown_docs_dependency_is_low_severity():
    snap = snapshot({"docs/requirements.txt": "Sphinx==4.5.0\n"})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    unknown = _single_unknown_finding(findings)
    assert unknown.severity == "low"
    assert unknown.confidence in {"low", "medium"}


def test_unknown_npm_dev_dependency_is_low_severity():
    snap = snapshot({"package.json": '{"devDependencies":{"grunt-cli":"^1.5.0"}}\n'})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    unknown = _single_unknown_finding(findings)
    assert unknown.severity == "low"


def test_known_mit_dependency_does_not_emit_license_finding():
    snap = snapshot(
        {
            "package-lock.json": json.dumps(
                {"packages": {"node_modules/permissive": {"version": "1.0.0", "license": "MIT"}}}
            )
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert findings == []


def test_vendored_production_missing_license_emits_one_high_finding():
    snap = snapshot({"vendor/prodlib/index.js": "console.log('x')\n"})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert len(findings) == 1
    assert findings[0].title == "Vendored code has no clear license file"
    assert findings[0].severity == "high"
    assert "unknown_license" not in findings[0].id


def test_vendored_test_fixture_missing_license_emits_one_low_finding():
    snap = snapshot({"tests/fixtures/vendor/prodlib/index.js": "console.log('x')\n"})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert len(findings) == 1
    assert findings[0].title == "Vendored code has no clear license file"
    assert findings[0].severity == "low"


def test_llm_budget_limits_queued_tasks_and_marks_omitted_items_for_review():
    snap = snapshot({"requirements.txt": "one==1.0\ntwo==2.0\nthree==3.0\n"})
    provider = MockBatchProvider()

    findings = LicenseRiskScanner(
        batch_provider=provider,
        poll_interval_seconds=0,
        task_item_limit=1,
        llm_prompt_token_budget=450,
    ).scan(snap)

    queued_tasks = provider.calls[0]["tasks"]
    assert len(queued_tasks) < 3
    assert all(task.estimated_prompt_tokens > 0 for task in queued_tasks)
    assert any("LLM batch budget exceeded" in finding.description for finding in findings)


def test_llm_request_count_limit_marks_extra_items_for_review():
    snap = snapshot({"requirements.txt": "one==1.0\ntwo==2.0\n"})
    provider = MockBatchProvider()

    findings = LicenseRiskScanner(
        batch_provider=provider,
        poll_interval_seconds=0,
        task_item_limit=1,
        llm_max_batch_requests=1,
    ).scan(snap)

    assert len(provider.calls[0]["tasks"]) == 1
    assert any("LLM batch budget exceeded" in finding.description for finding in findings)


def _payload_for_task(task) -> str:
    items = []
    for item in task.items:
        detected = item.declared_license or "MIT"
        items.append(
            {
                "task_item_id": item.item_id,
                "detected_license": detected,
                "confidence": "high",
                "evidence": ["mock batch evidence"],
                "is_custom_or_modified": False,
                "needs_review": False,
                "reason": "mock provider result",
            }
        )
    return json.dumps({"items": items})


def _single_unknown_finding(findings):
    unknown = [finding for finding in findings if "unknown_license" in finding.id]
    assert len(unknown) == 1
    return unknown[0]
