from __future__ import annotations

import json
import base64
import hashlib
import tarfile
import zipfile
from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.ingest.repository import RepositoryIngestor
from startup_risk.scanners.license_scanner.licenses import classify_license, detect_license_from_text, normalize_license
from startup_risk.scanners.license_scanner.llm.openai_batch import _jsonl_for_tasks
from startup_risk.scanners.license_scanner.models import LLMBatchResponse, LLMTask
from startup_risk.scanners.license_scanner.parsers import dotnet, go, java, npm, php, python, ruby, rust
from startup_risk.scanners.license_scanner.models import Dependency
from startup_risk.scanners.license_scanner.registry_metadata import _extract_metadata
from startup_risk.scanners.license_scanner.safe_artifacts import UnsafeArtifactError, download_artifact, safe_extract_archive
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


class UnresolvedBatchProvider(MockBatchProvider):
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
            responses.append(
                LLMBatchResponse(
                    task.task_id,
                    json.dumps(
                        {
                            "items": [
                                {
                                    "task_item_id": item.item_id,
                                    "detected_license": None,
                                    "confidence": "low",
                                    "evidence": [],
                                    "is_custom_or_modified": False,
                                    "needs_review": True,
                                    "reason": "Insufficient evidence to determine license",
                                }
                                for item in task.items
                            ]
                        }
                    ),
                )
            )
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


def test_additional_ecosystem_parsers_extract_dependencies():
    go_deps = go.parse(
        FileSnapshot(path="go.mod", size_bytes=1, extension=".mod", text="module x\nrequire github.com/pkg/errors v0.9.1\n")
    )
    java_deps = java.parse(
        FileSnapshot(
            path="pom.xml",
            size_bytes=1,
            extension=".xml",
            text="<project><dependencies><dependency><groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId><version>1.7.0</version></dependency></dependencies></project>",
        )
    )
    ruby_deps = ruby.parse(
        FileSnapshot(path="Gemfile", size_bytes=1, extension="", text='gem "rack", "3.0.0"\n')
    )
    php_deps = php.parse(
        FileSnapshot(path="composer.json", size_bytes=1, extension=".json", text='{"require":{"monolog/monolog":"^3.0"}}')
    )
    dotnet_deps = dotnet.parse(
        FileSnapshot(
            path="app.csproj",
            size_bytes=1,
            extension=".csproj",
            text='<Project><ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13.0.3" /></ItemGroup></Project>',
        )
    )

    assert go_deps[0].name == "github.com/pkg/errors"
    assert java_deps[0].name == "org.slf4j:slf4j-api"
    assert ruby_deps[0].name == "rack"
    assert php_deps[0].name == "monolog/monolog"
    assert dotnet_deps[0].name == "Newtonsoft.Json"


def test_license_classifier_buckets_common_risks():
    assert classify_license("MIT", has_notice=True).priority == "low"
    assert classify_license("Apache-2.0", has_notice=False).priority == "medium"
    assert classify_license("LGPL-3.0").priority == "medium"
    assert classify_license("AGPL-3.0").priority == "high"
    assert classify_license("BlueOak-1.0.0").priority == "low"


def test_spdx_normalization_handles_known_ids_without_rewriting_existing_ids():
    assert normalize_license("MIT-0") == "MIT-0"
    assert normalize_license("0BSD") == "0BSD"
    assert normalize_license("BlueOak-1.0.0") == "BlueOak-1.0.0"
    assert normalize_license("Python-2.0") == "Python-2.0"
    assert normalize_license("W3C") == "W3C"
    assert normalize_license("CC-BY-3.0") == "CC-BY-3.0"
    assert normalize_license("CC-BY-4.0") == "CC-BY-4.0"
    assert normalize_license("MIT OR CC0-1.0") == "MIT OR CC0-1.0"


def test_content_data_license_bucket_uses_contextual_severity():
    data = classify_license("CC-BY-4.0", content_data_context=True)
    runtime = classify_license("CC-BY-4.0", content_data_context=False)

    assert data.priority == "low"
    assert data.explanation == "Content/data license review recommended."
    assert runtime.priority == "medium"


def test_mpl_text_with_secondary_gpl_references_detects_mpl_not_gpl():
    text = """
    Mozilla Public License, version 2.0

    Exhibit A - Source Code Form License Notice
    This Source Code Form is subject to the terms of the Mozilla Public
    License, v. 2.0. This file may also be made available under the terms of
    the GNU General Public License, GNU Lesser General Public License, or GNU
    Affero General Public License as secondary licenses.
    """

    assert detect_license_from_text(text) == "MPL-2.0"


def test_large_package_lock_is_read_and_preserves_license_line_evidence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    lock_text = json.dumps(
        {
            "packages": {
                "": {"name": "demo"},
                "node_modules/copyleft": {
                    "version": "1.0.0",
                    "license": "GPL-3.0",
                    "padding": "x" * 1000,
                },
            }
        },
        indent=2,
    )
    (repo / "package-lock.json").write_text(lock_text, encoding="utf-8")

    repo_snapshot = RepositoryIngestor(max_file_bytes=50).ingest(str(repo))
    findings = LicenseRiskScanner(deterministic_only=True).scan(repo_snapshot)

    assert repo_snapshot.files[0].text is not None
    gpl = [finding for finding in findings if "GPL-3.0" in finding.title]
    assert len(gpl) == 1
    assert gpl[0].evidence[0].location.path == "package-lock.json"
    assert gpl[0].evidence[0].location.line_start is not None


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


def test_vendored_metadata_only_files_are_ignored():
    snap = snapshot(
        {
            "front_end/third_party/OWNERS": "team@example.com\n",
            "front_end/third_party/.gitignore": "*.tmp\n",
            "front_end/third_party/.clang-format": "BasedOnStyle: Chromium\n",
            "front_end/third_party/README.md": "Third-party dependencies live here.\n",
            "front_end/third_party/visibility.gni": "# metadata\n",
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert not any(finding.title == "Vendored code has no clear license file" for finding in findings)


def test_vendored_component_with_readme_chromium_is_not_missing_license_high():
    snap = snapshot(
        {
            "third_party/image_diff/README.chromium": "Name: image_diff\nLicense File: LICENSE\n",
            "third_party/image_diff/image_diff.cc": "int main() { return 0; }\n",
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert not any(finding.title == "Vendored code has no clear license file" for finding in findings)
    assert not any(finding.severity == "high" for finding in findings)


def test_apache_license_from_package_metadata_does_not_emit_notice_finding():
    snap = snapshot(
        {
            "package-lock.json": json.dumps(
                {"packages": {"node_modules/apache-lib": {"version": "1.0.0", "license": "Apache-2.0"}}}
            )
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert findings == []


def test_package_lock_dev_scope_downgrades_unknown_lockfile_dependency():
    snap = snapshot(
        {
            "package-lock.json": json.dumps(
                {"packages": {"node_modules/dev-only": {"version": "1.0.0", "dev": True}}}
            )
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    unknown = _single_unknown_finding(findings)
    assert unknown.severity == "low"


def test_npm_manifest_scope_merges_into_lockfile_dependency():
    snap = snapshot(
        {
            "package.json": json.dumps({"devDependencies": {"dev-only": "^1.0.0"}}),
            "package-lock.json": json.dumps(
                {"packages": {"node_modules/dev-only": {"version": "1.0.3", "license": "GPL-3.0"}}}
            ),
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    gpl = [finding for finding in findings if "dev-only@1.0.3" in finding.title]
    assert len(gpl) == 1
    assert not any("dev-only@^1.0.0" in finding.title for finding in findings)
    assert any(evidence.location.path == "package.json" for evidence in gpl[0].evidence)


def test_deterministic_low_risk_license_is_not_sent_to_llm():
    snap = snapshot({"package-lock.json": json.dumps({"packages": {"node_modules/mit-lib": {"version": "1.0.0", "license": "MIT"}}})})
    provider = MockBatchProvider()

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    assert provider.calls[0]["tasks"] == []
    assert findings == []


def test_long_license_evidence_excerpt_is_bounded():
    long_mpl = "Mozilla Public License, version 2.0\n" + ("x" * 5000)
    snap = snapshot({"third_party/mpllib/LICENSE": long_mpl})

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    mpl = [finding for finding in findings if "MPL-2.0" in finding.title][0]
    assert mpl.evidence[0].excerpt.endswith("...")
    assert len(mpl.evidence[0].excerpt) <= 803


def test_weak_readme_chromium_metadata_is_unknown_medium_not_missing_high():
    snap = snapshot(
        {
            "third_party/weak/README.chromium": "Imported by Chromium tooling.\n",
            "third_party/weak/source.cc": "int main() { return 0; }\n",
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    unknown = _single_unknown_finding(findings)
    assert unknown.severity == "medium"
    assert not any(finding.title == "Vendored code has no clear license file" for finding in findings)


def test_third_party_node_helper_wrappers_are_not_vendored_missing_license():
    snap = snapshot(
        {
            "third_party/node/node.py": "# local wrapper\n",
            "third_party/node/node_path.py": "# local wrapper\n",
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    assert findings == []


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


def test_llm_unresolved_unknown_uses_llm_specific_description():
    snap = snapshot({"examples/imagepipe/pyproject.toml": '[project]\ndependencies = ["pillow"]\n'})
    provider = UnresolvedBatchProvider()

    findings = LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    unknown = _single_unknown_finding(findings)
    assert unknown.description == (
        "The scanner and LLM review could not establish a license from the available local evidence."
    )
    assert unknown.severity == "low"
    assert unknown.confidence == "low"


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


def test_openai_batch_requests_force_json_object_response_format():
    task = LLMTask(
        task_id="license-scan-0001",
        items=[],
        prompt='Return JSON: {"items":[]}',
        estimated_prompt_tokens=10,
        estimated_request_bytes=0,
    )

    row = json.loads(_jsonl_for_tasks([task], "gpt-4o-mini").splitlines()[0])

    assert row["body"]["response_format"] == {"type": "json_object"}
    assert row["body"]["max_tokens"] >= 3000


def test_python_example_self_dependency_is_suppressed_but_third_party_remains():
    snap = snapshot(
        {
            "pyproject.toml": '[project]\nname = "click"\nversion = "8.3.0"\nlicense = "BSD-3-Clause"\n',
            "examples/demo/pyproject.toml": '[project]\ndependencies = ["click>=8.1", "pillow"]\n',
        }
    )

    findings = LicenseRiskScanner(deterministic_only=True).scan(snap)

    titles = [finding.title for finding in findings]
    assert not any("click" in title.lower() for title in titles)
    assert any("pillow" in title.lower() for title in titles)
    pillow = [finding for finding in findings if "pillow" in finding.title.lower()][0]
    assert pillow.severity == "low"


def test_self_dependencies_are_not_sent_to_llm_tasks():
    snap = snapshot(
        {
            "pyproject.toml": '[project]\nname = "click"\nversion = "8.3.0"\nlicense = "BSD-3-Clause"\n',
            "examples/demo/pyproject.toml": '[project]\ndependencies = ["click>=8.1", "pillow"]\n',
        }
    )
    provider = MockBatchProvider()

    LicenseRiskScanner(batch_provider=provider, poll_interval_seconds=0).scan(snap)

    queued_names = [
        item.dependency_name
        for call in provider.calls
        for task in call["tasks"]
        for item in task.items
    ]
    assert "click" not in queued_names
    assert "pillow" in queued_names


def test_safe_artifact_extraction_rejects_path_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "nope")

    try:
        safe_extract_archive(archive)
    except UnsafeArtifactError as exc:
        assert "unsafe path" in str(exc) or "escapes" in str(exc)
    else:
        raise AssertionError("expected UnsafeArtifactError")


def test_safe_artifact_extraction_rejects_tar_symlink(tmp_path):
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as tf:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/tmp/target"
        tf.addfile(info)

    try:
        safe_extract_archive(archive)
    except UnsafeArtifactError as exc:
        assert "link" in str(exc)
    else:
        raise AssertionError("expected UnsafeArtifactError")


def test_artifact_download_verifies_integrity_for_file_url(tmp_path):
    artifact = tmp_path / "artifact.tgz"
    artifact.write_bytes(b"demo")
    digest = base64.b64encode(hashlib.sha512(b"demo").digest()).decode("ascii")

    downloaded = download_artifact(artifact.as_uri(), integrity=f"sha512-{digest}")

    assert downloaded.read_bytes() == b"demo"


def test_artifact_download_rejects_integrity_mismatch(tmp_path):
    artifact = tmp_path / "artifact.tgz"
    artifact.write_bytes(b"demo")

    try:
        download_artifact(artifact.as_uri(), integrity="sha512-AAAA")
    except UnsafeArtifactError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("expected UnsafeArtifactError")


def test_registry_metadata_extracts_npm_license_artifact_and_source_url():
    dependency = Dependency(
        name="left-pad",
        version="1.3.0",
        ecosystem="npm",
        relationship="transitive",
        source_type="lockfile",
        source_file="package-lock.json",
        source_line=1,
    )
    raw = json.dumps(
        {
            "license": "MIT",
            "repository": {"url": "https://github.com/example/left-pad.git"},
            "versions": {
                "1.3.0": {
                    "license": "MIT",
                    "dist": {"tarball": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz"},
                }
            },
        }
    )

    license_value, artifact_url, source_repo_url = _extract_metadata(dependency, raw)

    assert license_value == "MIT"
    assert artifact_url.endswith("left-pad-1.3.0.tgz")
    assert source_repo_url == "https://github.com/example/left-pad.git"


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
