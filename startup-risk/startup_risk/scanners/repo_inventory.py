from __future__ import annotations

from collections import Counter

from startup_risk.core.models import (
    InventoryCategory,
    RepositoryInventory,
    RepositorySnapshot,
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

INFRA_FILENAMES = {
    ".dockerignore",
    "docker-compose.yml",
    "docker-compose.yaml",
    "dockerfile",
}

INFRA_EXTENSIONS = {
    ".tf",
    ".tfvars",
}

CONFIG_FILENAMES = {
    ".editorconfig",
    ".env.example",
    ".gitignore",
    "netlify.toml",
    "vercel.json",
}

CONFIG_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".ini",
    ".toml",
    ".yaml",
    ".yml",
}

DOC_EXTENSIONS = {
    ".adoc",
    ".md",
    ".rst",
    ".txt",
}


class RepoInventoryScanner:
    """Builds static repository inventory metadata for downstream scanners."""

    id = "repo_inventory"
    name = "Repository Inventory"
    version = "1.1.0"

    def __init__(self, *, example_limit: int = 10, include_full_paths: bool = False) -> None:
        self.example_limit = example_limit
        self.include_full_paths = include_full_paths

    def scan(self, snapshot: RepositorySnapshot) -> RepositoryInventory:
        return RepositoryInventory(
            languages=self._language_inventory(snapshot),
            docs_files=self._path_inventory(_matching_paths(snapshot, extensions=DOC_EXTENSIONS)),
            manifest_files=self._path_inventory(
                _matching_paths(snapshot, filenames=MANIFEST_FILENAMES | LOCKFILE_FILENAMES)
            ),
            schema_files=self._path_inventory(
                _matching_paths(
                    snapshot,
                    filenames=SCHEMA_FILENAMES,
                    extensions=SCHEMA_EXTENSIONS,
                )
            ),
            infra_files=self._path_inventory(
                _matching_paths(
                    snapshot,
                    filenames=INFRA_FILENAMES,
                    extensions=INFRA_EXTENSIONS,
                    roles={"infra"},
                )
            ),
            config_files=self._path_inventory(
                _matching_paths(
                    snapshot,
                    filenames=CONFIG_FILENAMES,
                    extensions=CONFIG_EXTENSIONS,
                    roles={"config"},
                )
            ),
        )

    def _language_inventory(self, snapshot: RepositorySnapshot) -> InventoryCategory:
        counts: Counter[str] = Counter()
        for file in snapshot.files:
            language = LANGUAGE_EXTENSIONS.get(file.extension)
            if language is not None:
                counts[language] += 1

        examples = [
            f"{language}: {count} file(s)" for language, count in sorted(counts.items())
        ]
        return InventoryCategory(
            count=len(counts),
            examples=examples[: self.example_limit],
            full_paths=None,
        )

    def _path_inventory(self, paths: list[str]) -> InventoryCategory:
        sorted_paths = sorted(paths)
        return InventoryCategory(
            count=len(sorted_paths),
            examples=sorted_paths[: self.example_limit],
            full_paths=sorted_paths if self.include_full_paths else None,
        )


def _matching_paths(
    snapshot: RepositorySnapshot,
    *,
    filenames: set[str] | None = None,
    extensions: set[str] | None = None,
    roles: set[str] | None = None,
) -> list[str]:
    filenames = filenames or set()
    extensions = extensions or set()
    roles = roles or set()
    paths: list[str] = []

    for file in snapshot.files:
        filename = file.path.lower().rsplit("/", maxsplit=1)[-1]
        if (
            filename in filenames
            or file.extension in extensions
            or file.path_role in roles
        ):
            paths.append(file.path)

    return sorted(set(paths))
