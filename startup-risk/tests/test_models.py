from __future__ import annotations

import pytest
from pydantic import ValidationError

from startup_risk.core.models import FileSnapshot, Finding, SourceLocation


def test_file_snapshot_requires_repo_relative_path():
    with pytest.raises(ValidationError):
        FileSnapshot(path="/tmp/repo/app.py", size_bytes=10, extension=".py", text="")


def test_source_location_rejects_parent_traversal():
    with pytest.raises(ValidationError):
        SourceLocation(path="../secret.txt")


def test_source_location_validates_line_range():
    with pytest.raises(ValidationError):
        SourceLocation(path="app.py", line_start=10, line_end=9)


def test_binary_file_snapshot_cannot_include_text():
    with pytest.raises(ValidationError):
        FileSnapshot(
            path="image.bin",
            size_bytes=3,
            extension=".bin",
            text="abc",
            is_binary=True,
        )


def test_file_snapshot_classifies_path_roles():
    assert FileSnapshot(path=".env", size_bytes=1, extension="", text="x").path_role == "root"
    assert FileSnapshot(path="src/app.py", size_bytes=1, extension=".py", text="x").path_role == "src"
    assert (
        FileSnapshot(path="tests/fixtures/.env", size_bytes=1, extension="", text="x").path_role
        == "tests"
    )
    assert (
        FileSnapshot(path="Dockerfile", size_bytes=1, extension="", text="x").path_role
        == "infra"
    )


def test_finding_id_must_be_url_safe():
    with pytest.raises(ValidationError):
        Finding(
            id="bad/id",
            title="Bad",
            description="Bad id.",
            category="test",
            severity="low",
            confidence="high",
            evidence=[],
            recommendation="Review.",
            scanner_id="test",
            scanner_version="1.0.0",
        )
