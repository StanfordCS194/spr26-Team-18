from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import urlparse

from git import Repo

from startup_risk.core.models import FileSnapshot, RepositorySnapshot, RepositorySource


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "venv",
}


class RepositoryIngestor:
    """Builds static repository snapshots without executing scanned code."""

    def __init__(
        self,
        *,
        max_file_bytes: int = 256_000,
        ignored_dirs: set[str] | None = None,
    ) -> None:
        self.max_file_bytes = max_file_bytes
        self.ignored_dirs = ignored_dirs or DEFAULT_IGNORED_DIRS

    def ingest(self, target: str) -> RepositorySnapshot:
        if _is_github_url(target):
            return self._ingest_public_github(target)

        path = Path(target).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError("target must be an existing local directory or a public GitHub HTTPS URL")

        return self._snapshot_path(
            root=path,
            source=_source_with_git_metadata(
                kind="local",
                location=target,
                root=path,
                requested_ref=None,
            ),
        )

    def _ingest_public_github(self, url: str) -> RepositorySnapshot:
        if not _is_public_github_https_url(url):
            raise ValueError("remote targets must be public GitHub HTTPS repository URLs")

        temp_dir = tempfile.TemporaryDirectory(prefix="startup-risk-")
        root = Path(temp_dir.name) / "repo"
        repo = Repo.clone_from(url, root, multi_options=["--depth", "1"])
        snapshot = self._snapshot_path(
            root=root,
            source=_source_from_repo(
                kind="github",
                location=url,
                repo=repo,
                requested_ref=None,
            ),
        )
        snapshot._temp_dir = temp_dir
        return snapshot

    def _snapshot_path(self, *, root: Path, source: RepositorySource) -> RepositorySnapshot:
        files = [self._read_file(path, root) for path in self._iter_files(root)]
        return RepositorySnapshot(source=source, root=root, files=files)

    def _iter_files(self, root: Path) -> list[Path]:
        paths: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in self.ignored_dirs for part in path.relative_to(root).parts):
                continue
            paths.append(path)
        return sorted(paths, key=lambda path: path.relative_to(root).as_posix())

    def _read_file(self, path: Path, root: Path) -> FileSnapshot:
        relative_path = path.relative_to(root).as_posix()
        size_bytes = path.stat().st_size

        if size_bytes > self.max_file_bytes:
            return FileSnapshot(
                path=relative_path,
                size_bytes=size_bytes,
                extension=path.suffix.lower(),
                is_binary=False,
                skipped_reason="file exceeds max_file_bytes",
            )

        raw = path.read_bytes()
        if b"\x00" in raw:
            return FileSnapshot(
                path=relative_path,
                size_bytes=size_bytes,
                extension=path.suffix.lower(),
                is_binary=True,
                skipped_reason="binary file",
            )

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return FileSnapshot(
                path=relative_path,
                size_bytes=size_bytes,
                extension=path.suffix.lower(),
                is_binary=False,
                skipped_reason="non-utf8 text",
            )

        return FileSnapshot(
            path=relative_path,
            size_bytes=size_bytes,
            extension=path.suffix.lower(),
            text=text,
        )


def _is_github_url(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com"


def _is_public_github_https_url(target: str) -> bool:
    parsed = urlparse(target)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return False
    if parsed.username or parsed.password or "@" in parsed.netloc:
        return False
    parts = [part for part in parsed.path.split("/") if part]
    return len(parts) >= 2


def _source_with_git_metadata(
    *,
    kind: str,
    location: str,
    root: Path,
    requested_ref: str | None,
) -> RepositorySource:
    try:
        repo = Repo(root)
    except Exception:
        return RepositorySource(
            kind=kind,  # type: ignore[arg-type]
            location=location,
            requested_ref=requested_ref,
        )
    return _source_from_repo(
        kind=kind,
        location=location,
        repo=repo,
        requested_ref=requested_ref,
    )


def _source_from_repo(
    *,
    kind: str,
    location: str,
    repo: Repo,
    requested_ref: str | None,
) -> RepositorySource:
    commit_sha = None
    resolved_ref = None
    try:
        commit_sha = repo.head.commit.hexsha
    except Exception:
        pass
    try:
        resolved_ref = repo.active_branch.name
    except Exception:
        try:
            resolved_ref = repo.head.reference.name
        except Exception:
            pass
    return RepositorySource(
        kind=kind,  # type: ignore[arg-type]
        location=location,
        requested_ref=requested_ref,
        resolved_ref=resolved_ref,
        commit_sha=commit_sha,
    )
