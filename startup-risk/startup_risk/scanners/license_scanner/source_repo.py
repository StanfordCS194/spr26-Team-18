from __future__ import annotations

import re
import urllib.parse
import urllib.request

from startup_risk.scanners.license_scanner.licenses import detect_license_from_text
from startup_risk.scanners.license_scanner.models import LicenseEvidence


SOURCE_LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "NOTICE")


class SourceRepoError(ValueError):
    """Raised when source repository license evidence cannot be fetched."""


def fetch_source_repo_license_evidence(repo_url: str, *, timeout: int = 20) -> LicenseEvidence | None:
    github = _github_owner_repo(repo_url)
    if github is None:
        return None
    owner, repo = github
    for branch in ("main", "master"):
        for filename in SOURCE_LICENSE_NAMES:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}"
            try:
                request = urllib.request.Request(raw_url, headers={"User-Agent": "startup-risk-license-scanner/1.0"})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    text = response.read(1_000_000).decode("utf-8", errors="replace")
            except Exception:
                continue
            detected = detect_license_from_text(text)
            if detected or text.strip():
                return LicenseEvidence(
                    source="source_repo",
                    file=raw_url,
                    line=1,
                    text=text[:8000],
                    detected_license=detected,
                    confidence="medium" if detected else "low",
                )
    return None


def _github_owner_repo(url: str) -> tuple[str, str] | None:
    cleaned = url.strip()
    cleaned = re.sub(r"^(git\+|git://)", "", cleaned)
    cleaned = cleaned.removesuffix(".git")
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return urllib.parse.quote(parts[0], safe=""), urllib.parse.quote(parts[1], safe="")
