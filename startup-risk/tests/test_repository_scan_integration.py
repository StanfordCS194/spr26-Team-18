from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.scanners.license_scanner import LicenseRiskScanner
from startup_risk.scanners.repository_catalog import repositories_by_slug_list


REPO_ENV = "LICENSE_SCANNER_TEST_REPO"
LLM_ENV = "LICENSE_SCANNER_TEST_LLM"
OUTPUT_ENV = "LICENSE_SCANNER_TEST_OUTPUT"


@pytest.mark.integration
def test_license_scanner_catalog_repositories_selected_by_env():
    """Opt-in live GitHub smoke test for one or more catalog repositories.

    Usage:
        LICENSE_SCANNER_TEST_REPO=django/django pytest tests/test_repository_scan_integration.py -s
        LICENSE_SCANNER_TEST_REPO=django/django,BurntSushi/ripgrep pytest tests/test_repository_scan_integration.py -s
        LICENSE_SCANNER_TEST_REPO=django/django LICENSE_SCANNER_TEST_OUTPUT=/tmp/findings.json pytest tests/test_repository_scan_integration.py -s

    The test defaults to deterministic-only mode. Set LICENSE_SCANNER_TEST_LLM=1 to
    exercise the blocking batch-LLM path, which may take hours and consume API credits.
    """
    selector = os.getenv(REPO_ENV)
    if not selector:
        pytest.skip(f"Set {REPO_ENV}=owner/repo to run a live catalog repository scan.")

    use_llm = os.getenv(LLM_ENV) == "1"
    output_path = os.getenv(OUTPUT_ENV)
    ingestor = RepositoryIngestor(max_file_bytes=2_000_000)
    scanner = LicenseRiskScanner(deterministic_only=not use_llm)
    results = []
    output_payload = []

    for repo in repositories_by_slug_list(selector):
        snapshot = ingestor.ingest(repo.url)
        findings = scanner.scan(snapshot)
        by_severity = Counter(finding.severity for finding in findings)
        result = {
            "slug": repo.slug,
            "suite": repo.suite,
            "files": len(snapshot.files),
            "findings": len(findings),
            "high": by_severity["high"],
            "medium": by_severity["medium"],
            "low": by_severity["low"],
            "expected_dependency_files": repo.expected_dependency_files,
            "deterministic_only": not use_llm,
        }
        print(json.dumps(result, sort_keys=True))
        results.append(result)
        output_payload.append(
            {
                "repository": result,
                "findings": [finding.model_dump(mode="json") for finding in findings],
            }
        )

    assert results
    assert all(result["files"] > 0 for result in results)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output_payload, indent=2, sort_keys=True), encoding="utf-8")
