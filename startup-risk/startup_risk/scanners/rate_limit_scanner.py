from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    FileSnapshot,
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    SourceLocation,
)

_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go", ".java", ".php",
})
_DEP_FILES = frozenset({
    "package.json", "requirements.txt", "pipfile", "pyproject.toml",
    "gemfile", "go.mod", "pom.xml", "build.gradle",
})

# Path patterns that strongly suggest an auth route handler file
_AUTH_FILE_PATTERN = re.compile(
    r"\b(?:auth|login|signin|sign[-_]in|register|signup|sign[-_]up|"
    r"password[-_]?reset|forgot[-_]?password|reset[-_]?password|oauth|token)\b",
    re.IGNORECASE,
)

# Rate-limiting library imports / references across major frameworks
_RATE_LIMIT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Python
    (re.compile(r"\bslowapi\b", re.IGNORECASE), "slowapi"),
    (re.compile(r"\bflask[_-]limiter\b", re.IGNORECASE), "Flask-Limiter"),
    (re.compile(r"\bdjango[_-]ratelimit\b", re.IGNORECASE), "django-ratelimit"),
    (re.compile(r"\bratelimit\b", re.IGNORECASE), "ratelimit"),
    (re.compile(r"from\s+limits\b", re.IGNORECASE), "limits"),
    # Node / JS / TS
    (re.compile(r"\bexpress-rate-limit\b", re.IGNORECASE), "express-rate-limit"),
    (re.compile(r"\brate-limiter-flexible\b", re.IGNORECASE), "rate-limiter-flexible"),
    (re.compile(r"\bexpress-slow-down\b", re.IGNORECASE), "express-slow-down"),
    (re.compile(r"\bbottleneck\b", re.IGNORECASE), "bottleneck"),
    (re.compile(r"\b@upstash/ratelimit\b", re.IGNORECASE), "@upstash/ratelimit"),
    # Ruby
    (re.compile(r"\brack-attack\b", re.IGNORECASE), "rack-attack"),
    (re.compile(r"\brack-throttle\b", re.IGNORECASE), "rack-throttle"),
    # Go
    (re.compile(r"golang\.org/x/time/rate", re.IGNORECASE), "golang.org/x/time/rate"),
    (re.compile(r"github\.com/ulule/limiter", re.IGNORECASE), "ulule/limiter"),
    # Java
    (re.compile(r"\bbucket4j\b", re.IGNORECASE), "Bucket4j"),
    (re.compile(r"\bresilience4j\b", re.IGNORECASE), "Resilience4j"),
    # Generic framework decorators / middleware references
    (re.compile(r"@RateLimit|@Throttle|RateLimiter"), "rate-limit decorator"),
    (re.compile(r"\brateLimit\s*\(|\bthrottle\s*\(", re.IGNORECASE), "rate-limit middleware"),
    (re.compile(r"\bnginx\s+limit_req\b|\bnginx.*rate.*limit\b", re.IGNORECASE), "nginx rate limiting"),
]

# Within an auth file: route-handler patterns to confirm this file actually defines endpoints
_ROUTE_PATTERN = re.compile(
    r"""(?:@app\.(?:post|get|route)|@router\.|router\.(?:post|get)|"""
    r"""app\.(?:post|get)\s*\(['"]|Route\s*\[|@PostMapping|@GetMapping|"""
    r"""func\s+\w+Handler|http\.HandleFunc|def\s+(?:post|get|login|register|signup)\b)""",
    re.IGNORECASE,
)


def _is_auth_file(file: FileSnapshot) -> bool:
    return bool(_AUTH_FILE_PATTERN.search(file.path))


def _repo_has_rate_limiting(snapshot: RepositorySnapshot) -> tuple[bool, str]:
    """Return (found, library_name). Checks source files and dependency manifests."""
    for file in snapshot.files:
        if file.text is None:
            continue
        filename_lower = file.path.lower().rsplit("/", 1)[-1]
        # Check dependency files first (fast path)
        if filename_lower in _DEP_FILES or file.extension in {".txt", ".toml", ".json", ".mod"}:
            for pattern, lib in _RATE_LIMIT_PATTERNS:
                if pattern.search(file.text):
                    return True, lib
        # Check source files
        if file.extension in _SOURCE_EXTENSIONS:
            for pattern, lib in _RATE_LIMIT_PATTERNS:
                if pattern.search(file.text):
                    return True, lib
    return False, ""


def _auth_files_with_routes(snapshot: RepositorySnapshot) -> list[FileSnapshot]:
    """Return auth-named files that also contain route-handler code."""
    results = []
    for file in snapshot.files:
        if not _is_auth_file(file):
            continue
        if file.extension not in _SOURCE_EXTENSIONS:
            continue
        if file.text is None:
            continue
        if _ROUTE_PATTERN.search(file.text):
            results.append(file)
    return results


class RateLimitScanner:
    """Checks that auth endpoints are protected by a rate-limiting mechanism."""

    id = "rate_limiting"
    name = "Rate Limiting on Auth Endpoints"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        auth_files = _auth_files_with_routes(snapshot)
        if not auth_files:
            # No detectable auth endpoints — nothing to flag
            return []

        has_rate_limit, lib_name = _repo_has_rate_limiting(snapshot)
        if has_rate_limit:
            return []

        # Auth routes exist but no rate-limiting library found anywhere
        evidence = [
            FindingEvidence(
                location=SourceLocation(path=f.path, line_start=1, line_end=1),
                description=f"Auth route file with no rate-limiting reference: {f.path}",
            )
            for f in auth_files[:4]
        ]
        seed = "|".join(sorted(f.path for f in auth_files))

        return [
            Finding(
                id=stable_finding_id(self.id, "no_rate_limiting_on_auth", seed),
                title="Auth endpoints detected with no rate-limiting library in the codebase",
                description=(
                    "Authentication endpoints (login, registration, password reset) were detected "
                    "but no rate-limiting library was found anywhere in the codebase. Without "
                    "rate limiting, these endpoints are vulnerable to credential-stuffing, "
                    "brute-force, and account-enumeration attacks. A single targeted account "
                    "can be hammered with thousands of password guesses per minute."
                ),
                category="access_control",
                severity="high",
                confidence="medium",
                evidence=evidence,
                recommendation=(
                    "Add a rate-limiting library appropriate for your stack:\n"
                    "  • Python/FastAPI: slowapi\n"
                    "  • Python/Flask: Flask-Limiter\n"
                    "  • Node/Express: express-rate-limit\n"
                    "  • Ruby/Rails: rack-attack\n"
                    "At minimum, limit login and password-reset endpoints to 5–10 attempts per "
                    "IP per minute. Consider adding CAPTCHA for registration flows. "
                    "Infra-level rate limiting (nginx, Cloudflare, AWS WAF) also satisfies this "
                    "check but won't be detected here."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]
