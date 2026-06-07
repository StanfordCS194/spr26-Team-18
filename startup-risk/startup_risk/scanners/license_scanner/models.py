from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Relationship = Literal["direct", "transitive", "vendored", "unknown"]
SourceType = Literal["manifest", "lockfile", "metadata", "vendored_code"]
EvidenceSource = Literal[
    "local_manifest",
    "local_license_file",
    "lockfile",
    "registry_metadata",
    "package_artifact",
    "source_repo",
    "llm",
]
Confidence = Literal["none", "low", "medium", "high"]
Priority = Literal["low", "medium", "high"]


@dataclass
class LicenseEvidence:
    source: EvidenceSource
    file: str | None
    line: int | None
    text: str | None
    detected_license: str | None
    confidence: Confidence


@dataclass
class Dependency:
    name: str
    version: str | None
    ecosystem: str
    relationship: Relationship
    source_type: SourceType
    source_file: str
    source_line: int | None
    declared_license: str | None = None
    normalized_license: str | None = None
    license_confidence: Confidence = "none"
    evidence: list[LicenseEvidence] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.ecosystem}:{self.name}:{self.version or '?'}:{self.source_file}:{self.source_line or 0}"


@dataclass(frozen=True)
class LicenseClassification:
    normalized_license: str | None
    priority: Priority
    confidence: Literal["low", "medium", "high"]
    explanation: str
    recommendation: str
    source: Literal["deterministic", "llm"]


@dataclass(frozen=True)
class LLMTaskItem:
    item_id: str
    dependency_key: str
    dependency_name: str
    ecosystem: str
    declared_license: str | None
    evidence: list[LicenseEvidence]


@dataclass(frozen=True)
class LLMTask:
    task_id: str
    items: list[LLMTaskItem]
    prompt: str
    estimated_prompt_tokens: int = 0
    estimated_request_bytes: int = 0


@dataclass(frozen=True)
class LLMBatchResponse:
    task_id: str
    output_text: str | None
    error: str | None = None


@dataclass(frozen=True)
class LLMItemResult:
    item_id: str
    detected_license: str | None
    confidence: Literal["low", "medium", "high"]
    evidence: list[str]
    is_custom_or_modified: bool
    needs_review: bool
    reason: str
