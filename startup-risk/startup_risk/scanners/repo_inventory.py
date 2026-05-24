from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    SourceLocation,
)


LANGUAGE_EXTENSIONS = {
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}

MANIFEST_FILENAMES = {
    "cargo.toml",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
}

LOCKFILE_FILENAMES = {
    "cargo.lock",
    "go.sum",
    "package-lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "yarn.lock",
}

SCHEMA_EXTENSIONS = {
    ".graphql",
    ".jsonschema",
    ".proto",
    ".sql",
}

SCHEMA_FILENAMES = {
    "schema.json",
    "schema.prisma",
}

INFRA_CONFIG_FILENAMES = {
    ".dockerignore",
    "docker-compose.yml",
    "dockerfile",
    "netlify.toml",
    "vercel.json",
}

INFRA_CONFIG_EXTENSIONS = {
    ".tf",
}

DOC_EXTENSIONS = {
    ".adoc",
    ".md",
    ".rst",
    ".txt",
}


@dataclass(frozen=True)
class InventoryBucket:
    id_suffix: str
    title: str
    description: str
    paths: list[str]


class RepoInventoryScanner:
    """Reports static repository inventory signals for downstream scanners."""

    id = "repo_inventory"
    name = "Repository Inventory"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        language_counts = _language_counts(snapshot)
        buckets = [
            InventoryBucket(
                id_suffix="languages",
                title="Detected languages",
                description=_language_description(language_counts),
                paths=[],
            ),
            InventoryBucket(
                id_suffix="manifests",
                title="Detected dependency manifests",
                description="Repository contains dependency or package manifest files.",
                paths=_matching_paths(snapshot, filenames=MANIFEST_FILENAMES),
            ),
            InventoryBucket(
                id_suffix="lockfiles",
                title="Detected dependency lockfiles",
                description="Repository contains dependency lockfiles.",
                paths=_matching_paths(snapshot, filenames=LOCKFILE_FILENAMES),
            ),
            InventoryBucket(
                id_suffix="schemas",
                title="Detected schema files",
                description="Repository contains files that appear to define data or API schemas.",
                paths=_matching_paths(
                    snapshot,
                    filenames=SCHEMA_FILENAMES,
                    extensions=SCHEMA_EXTENSIONS,
                ),
            ),
            InventoryBucket(
                id_suffix="infra_config",
                title="Detected infrastructure or config files",
                description="Repository contains deployment, infrastructure, or service config files.",
                paths=_matching_paths(
                    snapshot,
                    filenames=INFRA_CONFIG_FILENAMES,
                    extensions=INFRA_CONFIG_EXTENSIONS,
                ),
            ),
            InventoryBucket(
                id_suffix="docs",
                title="Detected documentation files",
                description="Repository contains documentation-like files.",
                paths=_matching_paths(snapshot, extensions=DOC_EXTENSIONS),
            ),
        ]

        findings: list[Finding] = []
        if language_counts:
            findings.append(
                self._finding(
                    buckets[0],
                    evidence=[
                        FindingEvidence(
                            description=(
                                f"{language}: {count} file(s) detected by extension."
                            )
                        )
                        for language, count in sorted(language_counts.items())
                    ],
                )
            )

        for bucket in buckets[1:]:
            if not bucket.paths:
                continue
            findings.append(
                self._finding(
                    bucket,
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(path=path),
                            description="File matched this inventory category.",
                        )
                        for path in bucket.paths
                    ],
                )
            )

        return findings

    def _finding(
        self,
        bucket: InventoryBucket,
        *,
        evidence: list[FindingEvidence],
    ) -> Finding:
        return Finding(
            id=f"{self.id}.{bucket.id_suffix}",
            title=bucket.title,
            description=bucket.description,
            category="repository_inventory",
            severity="info",
            confidence="high",
            evidence=evidence,
            recommendation="Use this inventory signal to decide which deeper scanners should run.",
            scanner_id=self.id,
            scanner_version=self.version,
        )


def _language_counts(snapshot: RepositorySnapshot) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for file in snapshot.files:
        language = LANGUAGE_EXTENSIONS.get(file.extension)
        if language is not None:
            counts[language] += 1
    return dict(counts)


def _language_description(language_counts: dict[str, int]) -> str:
    languages = ", ".join(
        f"{language} ({count})" for language, count in sorted(language_counts.items())
    )
    return f"Repository contains source files for: {languages}."


def _matching_paths(
    snapshot: RepositorySnapshot,
    *,
    filenames: set[str] | None = None,
    extensions: set[str] | None = None,
) -> list[str]:
    filenames = filenames or set()
    extensions = extensions or set()
    paths: list[str] = []

    for file in snapshot.files:
        filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
        if filename in filenames or file.extension in extensions:
            paths.append(file.path)

    return sorted(paths)
