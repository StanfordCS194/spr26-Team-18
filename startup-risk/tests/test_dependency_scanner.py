from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from startup_risk.cli import app
from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.dependency_scanner import DependencyRiskScanner


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


def test_dependency_scanner_reuses_npm_python_and_rust_parsers():
    snap = snapshot(
        {
            "package.json": '{"dependencies":{"left-pad":"1.3.0"}}\n',
            "requirements.txt": "requests==2.31.0\n",
            "Cargo.toml": '[package]\nname = "demo"\n[dependencies]\nserde = "1"\n',
        }
    )

    findings = DependencyRiskScanner().scan(snap)
    text = " ".join(finding.title + " " + finding.description for finding in findings)

    assert "left-pad" in text
    assert "requests" in text
    assert "serde" in text


def test_runtime_manifest_without_lockfile_is_medium_and_dev_is_low():
    snap = snapshot(
        {
            "package.json": json.dumps(
                {
                    "dependencies": {"runtime-lib": "1.0.0"},
                    "devDependencies": {"dev-lib": "1.0.0"},
                }
            )
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    finding = [finding for finding in findings if "matching lockfile" in finding.title][0]
    assert finding.severity == "medium"
    assert "1 runtime and 1 dev/test" in finding.description
    assert "runtime-lib" in finding.description
    assert "dev-lib" in finding.description


def test_unpinned_specs_are_flagged_unless_lockfile_resolves_dependency():
    unlocked = snapshot({"package.json": '{"dependencies":{"react":"*"}}\n'})
    locked = snapshot(
        {
            "package.json": '{"dependencies":{"react":"*"}}\n',
            "package-lock.json": json.dumps(
                {
                    "packages": {
                        "node_modules/react": {
                            "version": "18.2.0",
                            "resolved": "https://registry.npmjs.org/react/-/react-18.2.0.tgz",
                            "integrity": "sha512-demo",
                        }
                    }
                }
            ),
        }
    )

    unlocked_findings = DependencyRiskScanner().scan(unlocked)
    locked_findings = DependencyRiskScanner().scan(locked)

    assert any("not pinned" in finding.title for finding in unlocked_findings)
    assert not any("not pinned" in finding.title for finding in locked_findings)


def test_python_loose_requirement_is_flagged():
    snap = snapshot({"requirements.txt": "requests>=2\n"})

    findings = DependencyRiskScanner().scan(snap)

    assert any("not pinned" in finding.title and "requests" in finding.title for finding in findings)


def test_risky_source_spec_is_high_for_runtime_and_medium_for_dev():
    snap = snapshot(
        {
            "package.json": json.dumps(
                {
                    "dependencies": {"runtime-lib": "git+https://github.com/example/runtime-lib.git"},
                    "devDependencies": {"dev-lib": "file:../dev-lib"},
                }
            )
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    runtime = [finding for finding in findings if "runtime-lib" in finding.title and "non-registry" in finding.title][0]
    dev = [finding for finding in findings if "dev-lib" in finding.title and "non-registry" in finding.title][0]
    assert runtime.severity == "high"
    assert dev.severity == "low"


def test_npm_lifecycle_script_is_reported_without_execution():
    snap = snapshot({"package.json": '{"name":"demo","scripts":{"postinstall":"node install.js"}}\n'})

    findings = DependencyRiskScanner().scan(snap)

    finding = [item for item in findings if "postinstall" in item.title][0]
    assert finding.severity == "medium"
    assert "does not execute" in finding.description


def test_npm_lockfile_metadata_gap_is_calibrated_by_scope():
    snap = snapshot(
        {
            "package.json": json.dumps(
                {
                    "dependencies": {"runtime-lib": "1.0.0"},
                    "devDependencies": {"dev-lib": "1.0.0"},
                }
            ),
            "package-lock.json": json.dumps(
                {
                    "packages": {
                        "node_modules/runtime-lib": {"version": "1.0.0"},
                        "node_modules/dev-lib": {"version": "1.0.0", "dev": True},
                        "node_modules/transitive-lib": {"version": "1.0.0"},
                    }
                }
            )
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    runtime = [finding for finding in findings if "runtime-lib" in finding.title][0]
    dev = [finding for finding in findings if "dev-lib" in finding.title][0]
    assert runtime.severity == "medium"
    assert dev.severity == "low"
    assert not any("transitive-lib" in finding.title for finding in findings)


def test_vendored_package_metadata_does_not_require_local_lockfile_or_pinned_specs():
    snap = snapshot(
        {
            "front_end/third_party/codemirror.next/package.json": json.dumps(
                {
                    "dependencies": {
                        "style-mod": "^4.0.0",
                        "lezer-tree": "~1.0.0",
                    }
                }
            )
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    assert not any("lockfile" in finding.title for finding in findings)
    assert not any("not pinned" in finding.title for finding in findings)


def test_missing_lockfile_is_grouped_and_range_specs_are_not_double_reported():
    snap = snapshot(
        {
            "package.json": json.dumps(
                {
                    "name": "library",
                    "dependencies": {"react": "^18.0.0", "debug": "~4.0.0"},
                }
            )
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    missing = [finding for finding in findings if "matching lockfile" in finding.title]
    assert len(missing) == 1
    assert missing[0].severity == "low"
    assert "react" in missing[0].description
    assert not any("not pinned" in finding.title for finding in findings)


def test_dependency_verbose_includes_dependency_level_missing_lockfile_details():
    snap = snapshot({"package.json": '{"dependencies":{"react":"^18.0.0"}}\n'})

    findings = DependencyRiskScanner(verbose=True).scan(snap)

    assert any(finding.title == "Dependency manifest has no matching lockfile: package.json" for finding in findings)
    assert any(finding.title == "Dependency manifest has no matching lockfile for react" for finding in findings)


def test_rust_workspace_uses_root_lockfile_and_suppresses_local_path_dependencies():
    snap = snapshot(
        {
            "Cargo.lock": '[[package]]\nname = "globset"\nversion = "0.4.0"\n',
            "crates/globset/Cargo.toml": (
                '[package]\nname = "globset"\nversion = "0.4.0"\n\n'
                "[dependencies]\naho-corasick = \"1.1.1\"\n"
            ),
            "fuzz/Cargo.toml": (
                '[package]\nname = "ripgrep-fuzz"\nversion = "0.1.0"\n\n'
                '[dependencies]\nglobset = { path = "../crates/globset" }\n'
            ),
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    assert not any("matching lockfile" in finding.title for finding in findings)
    assert not any("globset" in finding.title and "non-registry" in finding.title for finding in findings)


def test_npm_workspace_uses_root_lockfile_for_package_manifests():
    snap = snapshot(
        {
            "package-lock.json": json.dumps(
                {
                    "packages": {
                        "node_modules/react": {
                            "version": "18.2.0",
                            "resolved": "https://registry.npmjs.org/react/-/react-18.2.0.tgz",
                            "integrity": "sha512-demo",
                        }
                    }
                }
            ),
            "packages/web/package.json": '{"dependencies":{"react":"^18.0.0"}}\n',
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    assert not any("matching lockfile" in finding.title for finding in findings)


def test_additional_lockfile_formats_resolve_manifest_specs():
    snap = snapshot(
        {
            "package.json": '{"dependencies":{"left-pad":"^1.0.0"}}\n',
            "yarn.lock": 'left-pad@^1.0.0:\n  version "1.3.0"\n  resolved "https://registry.yarnpkg.com/left-pad/-/left-pad-1.3.0.tgz"\n  integrity sha512-demo\n',
            "pyproject.toml": '[project]\ndependencies = ["requests>=2"]\n',
            "uv.lock": '[[package]]\nname = "requests"\nversion = "2.31.0"\n',
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    assert not any("left-pad" in finding.title and "not pinned" in finding.title for finding in findings)
    assert not any("requests" in finding.title and "not pinned" in finding.title for finding in findings)
    assert not any("matching lockfile" in finding.title for finding in findings)


def test_vendored_provenance_gap_ignores_metadata_only_and_flags_substantive_code():
    snap = snapshot(
        {
            "front_end/third_party/OWNERS": "team@example.com\n",
            "vendor/no-provenance/index.js": "console.log('x')\n",
            "tests/fixtures/vendor/tool/index.js": "console.log('x')\n",
        }
    )

    findings = DependencyRiskScanner().scan(snap)

    production = [finding for finding in findings if "no-provenance" in finding.title][0]
    fixture = [finding for finding in findings if "tool" in finding.title][0]
    assert production.severity == "medium"
    assert fixture.severity == "low"
    assert not any("OWNERS" in (finding.evidence[0].excerpt or "") for finding in findings)


def test_skipped_dependency_input_is_reported():
    snap = snapshot({}, skipped={"package-lock.json": "structured dependency file exceeds structured_max_file_bytes"})

    findings = DependencyRiskScanner().scan(snap)

    assert any(finding.title == "Dependency scanner skipped an input" for finding in findings)


def test_dependency_only_cli_emits_only_dependency_findings(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("SECRET_KEY=demo\n", encoding="utf-8")
    (repo / "package.json").write_text('{"dependencies":{"left-pad":"*"}}\n', encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(repo), "--format", "json", "--dependency-only"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["findings"]
    assert {finding["scanner_id"] for finding in payload["findings"]} == {"dependency_risk"}


def test_full_deterministic_scan_includes_dependency_scanner(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"dependencies":{"left-pad":"*"}}\n', encoding="utf-8")

    result = CliRunner().invoke(app, ["scan", str(repo), "--format", "json", "--deterministic-only"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "dependency_risk" in {finding["scanner_id"] for finding in payload["findings"]}
