from __future__ import annotations

import tarfile
import tempfile
import zipfile
import base64
import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path


LIKELY_LICENSE_FILES = (
    "package.json",
    "cargo.toml",
    "metadata",
    "pkg-info",
    "pom.xml",
    "license",
    "copying",
    "notice",
    "readme",
)


@dataclass(frozen=True)
class ArtifactLimits:
    max_archive_size: int = 50_000_000
    max_extracted_size: int = 200_000_000
    max_file_count: int = 10_000
    max_single_text_file: int = 1_000_000


class UnsafeArtifactError(ValueError):
    """Raised when an archive violates safe data-only inspection limits."""


def download_artifact(url: str, *, integrity: str | None = None, limits: ArtifactLimits | None = None, timeout: int = 60) -> Path:
    limits = limits or ArtifactLimits()
    parsed_name = Path(url.split("?", maxsplit=1)[0]).name or "artifact"
    target = Path(tempfile.mkdtemp(prefix="license-download-")) / parsed_name
    request = urllib.request.Request(url, headers={"User-Agent": "startup-risk-license-scanner/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(limits.max_archive_size + 1)
    if len(data) > limits.max_archive_size:
        raise UnsafeArtifactError("downloaded artifact exceeds max_archive_size")
    _verify_integrity(data, integrity)
    target.write_bytes(data)
    return target


def safe_extract_archive(archive_path: str | Path, *, limits: ArtifactLimits | None = None) -> Path:
    """Extract an archive as data only, rejecting traversal, absolute paths, and links."""
    limits = limits or ArtifactLimits()
    archive = Path(archive_path)
    if archive.stat().st_size > limits.max_archive_size:
        raise UnsafeArtifactError("archive exceeds max_archive_size")
    temp_dir = Path(tempfile.mkdtemp(prefix="license-artifact-"))
    if zipfile.is_zipfile(archive):
        _extract_zip(archive, temp_dir, limits)
        return temp_dir
    if tarfile.is_tarfile(archive):
        _extract_tar(archive, temp_dir, limits)
        return temp_dir
    raise UnsafeArtifactError("unsupported archive format")


def iter_likely_license_texts(root: str | Path, *, limits: ArtifactLimits | None = None) -> list[tuple[str, str]]:
    limits = limits or ArtifactLimits()
    output: list[tuple[str, str]] = []
    for path in Path(root).rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        lower = path.name.lower()
        if not any(lower == name or lower.startswith(name + ".") for name in LIKELY_LICENSE_FILES):
            continue
        if path.stat().st_size > limits.max_single_text_file:
            continue
        try:
            output.append((path.as_posix(), path.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return output


def _verify_integrity(data: bytes, integrity: str | None) -> None:
    if not integrity:
        return
    for token in integrity.split():
        if "-" not in token:
            continue
        algorithm, expected = token.split("-", maxsplit=1)
        algorithm = algorithm.lower()
        if algorithm not in {"sha1", "sha256", "sha384", "sha512"}:
            continue
        digest = hashlib.new(algorithm, data).digest()
        try:
            expected_bytes = base64.b64decode(expected)
        except Exception:
            expected_bytes = bytes.fromhex(expected)
        if digest == expected_bytes:
            return
    raise UnsafeArtifactError("artifact integrity verification failed")


def _extract_zip(archive: Path, target: Path, limits: ArtifactLimits) -> None:
    total_size = 0
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > limits.max_file_count:
            raise UnsafeArtifactError("archive exceeds max_file_count")
        for info in infos:
            destination = _safe_destination(target, info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode in {0o120000, 0o10000, 0o20000, 0o60000}:
                raise UnsafeArtifactError("archive contains link or special file")
            total_size += info.file_size
            if total_size > limits.max_extracted_size:
                raise UnsafeArtifactError("archive exceeds max_extracted_size")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, destination.open("wb") as dst:
                dst.write(src.read())


def _extract_tar(archive: Path, target: Path, limits: ArtifactLimits) -> None:
    total_size = 0
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        if len(members) > limits.max_file_count:
            raise UnsafeArtifactError("archive exceeds max_file_count")
        for member in members:
            destination = _safe_destination(target, member.name)
            if member.issym() or member.islnk() or member.isdev():
                raise UnsafeArtifactError("archive contains link or special file")
            total_size += member.size
            if total_size > limits.max_extracted_size:
                raise UnsafeArtifactError("archive exceeds max_extracted_size")
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(member)
            if src is None:
                continue
            with src, destination.open("wb") as dst:
                dst.write(src.read())


def _safe_destination(root: Path, member_name: str) -> Path:
    member_path = Path(member_name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise UnsafeArtifactError("archive contains unsafe path")
    destination = (root / member_path).resolve()
    root_resolved = root.resolve()
    if root_resolved not in destination.parents and destination != root_resolved:
        raise UnsafeArtifactError("archive path escapes extraction root")
    return destination
