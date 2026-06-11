from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


SourceKind = Literal["local", "github"]
Severity = Literal["info", "low", "medium", "high", "critical"]
Confidence = Literal["low", "medium", "high"]
PathRole = Literal[
    "root",
    "src",
    "tests",
    "examples",
    "docs",
    "config",
    "infra",
    "unknown",
]

PATH_ROLE_DIRS: dict[str, PathRole] = {
    ".github": "config",
    "config": "config",
    "configs": "config",
    "doc": "docs",
    "docs": "docs",
    "example": "examples",
    "examples": "examples",
    "infra": "infra",
    "infrastructure": "infra",
    "k8s": "infra",
    "kubernetes": "infra",
    "src": "src",
    "test": "tests",
    "tests": "tests",
}

INFRA_ROOT_FILES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

CONFIG_ROOT_FILES = {
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitignore",
    "netlify.toml",
    "vercel.json",
}


def _validate_repo_relative_path(value: str) -> str:
    if not value:
        raise ValueError("path must not be empty")
    path = Path(value)
    if path.is_absolute():
        raise ValueError("path must be repo-relative")
    if ".." in path.parts:
        raise ValueError("path must not traverse outside the repo")
    return path.as_posix()


class RepositorySource(BaseModel):
    kind: SourceKind
    location: str
    requested_ref: str | None = None
    resolved_ref: str | None = None
    commit_sha: str | None = None


class FileSnapshot(BaseModel):
    path: str
    size_bytes: int
    extension: str
    path_role: PathRole = "unknown"
    text: str | None = None
    is_binary: bool = False
    skipped_reason: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_repo_relative_path(value)

    @model_validator(mode="after")
    def validate_skipped_file_metadata(self) -> "FileSnapshot":
        self.path_role = classify_path_role(self.path)
        if self.text is not None and self.skipped_reason is not None:
            raise ValueError("text files cannot also have a skipped_reason")
        if self.is_binary and self.text is not None:
            raise ValueError("binary files cannot include decoded text")
        return self

    @property
    def is_text(self) -> bool:
        return self.text is not None


class RepositorySnapshot(BaseModel):
    source: RepositorySource
    root: Path = Field(exclude=True)
    files: list[FileSnapshot]
    _temp_dir: object | None = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="after")
    def sort_files(self) -> "RepositorySnapshot":
        self.files = sorted(self.files, key=lambda file: file.path)
        return self


class SourceLocation(BaseModel):
    path: str
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_repo_relative_path(value)

    @model_validator(mode="after")
    def validate_line_range(self) -> "SourceLocation":
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class FindingEvidence(BaseModel):
    location: SourceLocation | None = None
    description: str
    excerpt: str | None = None


class LegalCitation(BaseModel):
    title: str
    citation: str | None = None
    url: str | None = None
    authority_type: str = "other"
    jurisdiction: str | None = None


class LegalFindingContext(BaseModel):
    rule_id: str
    legal_basis: str
    why_it_matters: str
    citations: list[LegalCitation] = Field(default_factory=list)
    confidence: Confidence = "low"
    source_interpretation: bool = True


class ScannerLegalGuidance(BaseModel):
    """Bounded legal guidance supplied to scanners before findings are created."""

    rule_id: str
    category: str
    title: str
    legal_basis: str
    risk_signal: str
    detection_hints: list[str] = Field(default_factory=list)
    recommendation: str
    citations: list[LegalCitation] = Field(default_factory=list)
    confidence: Confidence = "low"
    source_interpretation: bool = True


class ScanContext(BaseModel):
    """Optional execution context for scanners that can use profile/legal guidance."""

    profile: dict[str, Any] = Field(default_factory=dict)
    legal_guidance: list[ScannerLegalGuidance] = Field(default_factory=list)


class Finding(BaseModel):
    id: str
    title: str
    description: str
    category: str
    severity: Severity
    confidence: Confidence
    evidence: list[FindingEvidence] = Field(default_factory=list)
    legal_context: list[LegalFindingContext] = Field(default_factory=list)
    recommendation: str
    scanner_id: str
    scanner_version: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value:
            raise ValueError("finding id must not be empty")
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if any(char not in allowed for char in value):
            raise ValueError("finding id must be lowercase and URL-safe")
        return value


class InventoryCategory(BaseModel):
    count: int = Field(ge=0)
    examples: list[str] = Field(default_factory=list)
    full_paths: list[str] | None = None


class RepositoryInventory(BaseModel):
    languages: InventoryCategory = Field(default_factory=lambda: InventoryCategory(count=0))
    docs_files: InventoryCategory = Field(default_factory=lambda: InventoryCategory(count=0))
    manifest_files: InventoryCategory = Field(default_factory=lambda: InventoryCategory(count=0))
    schema_files: InventoryCategory = Field(default_factory=lambda: InventoryCategory(count=0))
    infra_files: InventoryCategory = Field(default_factory=lambda: InventoryCategory(count=0))
    config_files: InventoryCategory = Field(default_factory=lambda: InventoryCategory(count=0))

    def signal_count(self) -> int:
        categories = (
            self.languages,
            self.docs_files,
            self.manifest_files,
            self.schema_files,
            self.infra_files,
            self.config_files,
        )
        return sum(1 for category in categories if category.count > 0)


class ScanSummary(BaseModel):
    actionable_findings: int
    informational_inventory_signals: int
    by_severity: dict[Severity, int]


class ScanResult(BaseModel):
    source: RepositorySource
    scanned_at: datetime
    inventory: RepositoryInventory
    findings: list[Finding]
    summary: ScanSummary

    @model_validator(mode="after")
    def sort_findings(self) -> "ScanResult":
        self.findings = sorted(self.findings, key=_finding_sort_key)
        return self

    @classmethod
    def from_findings(
        cls,
        *,
        source: RepositorySource,
        inventory: RepositoryInventory,
        findings: list[Finding],
    ) -> "ScanResult":
        severity_counts: dict[Severity, int] = {
            "info": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }
        for finding in findings:
            severity_counts[finding.severity] += 1

        return cls(
            source=source,
            scanned_at=datetime.now(timezone.utc),
            inventory=inventory,
            findings=sorted(findings, key=_finding_sort_key),
            summary=ScanSummary(
                actionable_findings=len(findings),
                informational_inventory_signals=inventory.signal_count(),
                by_severity=severity_counts,
            ),
        )


def _finding_sort_key(finding: Finding) -> tuple[int, int, str, str]:
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    title = finding.title.lower()
    is_unknown = "unknown license" in title or finding.id.startswith("license_risk.unknown_license")
    return (severity_rank[finding.severity], 1 if is_unknown else 0, finding.title, finding.id)


def classify_path_role(path: str) -> PathRole:
    parts = Path(path).as_posix().lower().split("/")
    filename = parts[-1]

    if filename in INFRA_ROOT_FILES or filename.endswith((".tf", ".tfvars")):
        return "infra"
    if filename in CONFIG_ROOT_FILES:
        return "config"
    if len(parts) == 1:
        return "root"
    for part in parts[:-1]:
        role = PATH_ROLE_DIRS.get(part)
        if role is not None:
            return role
    return "unknown"
