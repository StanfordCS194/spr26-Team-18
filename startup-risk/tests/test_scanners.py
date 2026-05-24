from __future__ import annotations

from pathlib import Path

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource
from startup_risk.scanners.repo_inventory import RepoInventoryScanner
from startup_risk.scanners.static_hygiene import StaticHygieneScanner


def snapshot_for(paths: list[str]) -> RepositorySnapshot:
    return RepositorySnapshot(
        source=RepositorySource(kind="local", location="fixture"),
        root=Path("/tmp/unused"),
        files=[
            FileSnapshot(
                path=path,
                size_bytes=1,
                extension=Path(path).suffix.lower(),
                text="x",
            )
            for path in paths
        ],
    )


def test_static_hygiene_reports_missing_baseline_files_with_cautious_findings():
    findings = StaticHygieneScanner().scan(snapshot_for(["app.py"]))

    titles = {finding.title for finding in findings}
    assert "Missing README.md" in titles
    assert "Missing LICENSE" in titles
    assert "Missing .gitignore" in titles
    assert "Missing SECURITY.md" in titles
    assert all(finding.scanner_id == "static_hygiene" for finding in findings)
    assert all(finding.confidence in {"medium", "high"} for finding in findings)


def test_static_hygiene_flags_sensitive_filenames_cautiously():
    findings = StaticHygieneScanner().scan(
        snapshot_for(["README.md", "LICENSE", ".gitignore", "SECURITY.md", ".env"])
    )

    sensitive = [
        finding
        for finding in findings
        if finding.id.startswith("static_hygiene.suspicious_sensitive_filename")
    ]
    assert len(sensitive) == 1
    assert sensitive[0].severity == "high"
    assert "does not prove" in sensitive[0].description
    assert sensitive[0].evidence[0].location is not None
    assert sensitive[0].evidence[0].location.path == ".env"


def test_static_hygiene_lowers_severity_for_test_fixture_env_files():
    findings = StaticHygieneScanner().scan(
        snapshot_for(
            [
                "README.md",
                "LICENSE",
                ".gitignore",
                "SECURITY.md",
                ".env",
                "tests/fixtures/.env",
            ]
        )
    )

    by_path = {
        finding.evidence[0].location.path: finding
        for finding in findings
        if finding.id.startswith("static_hygiene.suspicious_sensitive_filename")
        and finding.evidence[0].location is not None
    }
    assert by_path[".env"].severity == "high"
    assert by_path["tests/fixtures/.env"].severity == "low"


def test_static_hygiene_does_not_treat_env_example_as_real_secret_file():
    findings = StaticHygieneScanner().scan(
        snapshot_for(["README.md", "LICENSE", ".gitignore", "SECURITY.md", ".env.example"])
    )

    assert not [
        finding
        for finding in findings
        if finding.id.startswith("static_hygiene.suspicious_sensitive_filename")
    ]


def test_static_hygiene_finding_ids_are_stable_and_url_safe():
    snapshot = snapshot_for(["README.md", "LICENSE", ".gitignore", "SECURITY.md", ".env"])
    first = StaticHygieneScanner().scan(snapshot)
    second = StaticHygieneScanner().scan(snapshot)

    assert [finding.id for finding in first] == [finding.id for finding in second]
    for finding in first:
        assert "/" not in finding.id
        assert finding.id == finding.id.lower()
        assert finding.id.startswith("static_hygiene.")


def test_repo_inventory_reports_detected_static_assets():
    inventory = RepoInventoryScanner().scan(
        snapshot_for(
            [
                "README.md",
                "package.json",
                "package-lock.json",
                "src/app.ts",
                "schema.graphql",
                "Dockerfile",
                "infra/main.tf",
            ]
        )
    )

    assert inventory.docs_files.count == 1
    assert inventory.infra_files.count == 2
    assert inventory.languages.examples == ["TypeScript: 1 file(s)"]
    assert inventory.manifest_files.count == 2
    assert inventory.schema_files.count == 1


def test_repo_inventory_truncates_examples():
    inventory = RepoInventoryScanner(example_limit=2).scan(
        snapshot_for(["docs/a.md", "docs/b.md", "docs/c.md"])
    )

    assert inventory.docs_files.count == 3
    assert inventory.docs_files.examples == ["docs/a.md", "docs/b.md"]
    assert inventory.docs_files.full_paths is None
