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
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go", ".java", ".php", ".cs",
})
_CONFIG_EXTENSIONS = frozenset({".env", ".cfg", ".ini", ".conf", ".toml", ".yml", ".yaml"})

# debug = True / DEBUG=True in source or config
_DEBUG_TRUE = re.compile(
    r"""(?:^|[\s,({])DEBUG\s*[=:]\s*(?:True|true|1|"true"|'true')""",
    re.IGNORECASE | re.MULTILINE,
)
# Flask/Django: app.run(debug=True) or app.debug = True
_FLASK_DEBUG = re.compile(r"app\.(?:run\s*\([^)]*debug\s*=\s*True|debug\s*=\s*True)", re.IGNORECASE)

# Returning exception detail directly in an HTTP response
# Python: return str(e) / return repr(e) / return {"error": str(e)} / jsonify(error=str(e))
_EXCEPTION_IN_RESPONSE_PY = re.compile(
    r"\breturn\b[^;\n]*\bstr\s*\(\s*e\b|\breturn\b[^;\n]*\brepr\s*\(\s*e\b"
    r"|\b(?:jsonify|json\.dumps)\s*\([^)]*\bstr\s*\(\s*e\b",
    re.IGNORECASE,
)
# JS/TS: res.json({ error: e.message }) / res.send(e.stack) / next(err) with err.stack in body
_EXCEPTION_IN_RESPONSE_JS = re.compile(
    r"res\.(?:json|send)\s*\([^)]*\b(?:err?|error|e)\s*\.\s*(?:message|stack|toString)\b",
    re.IGNORECASE,
)
# Generic: returning full traceback text
_TRACEBACK_IN_RESPONSE = re.compile(
    r"""(?:traceback\.format_exc\s*\(\s*\)|sys\.exc_info\s*\(\s*\))""",
    re.IGNORECASE,
)

# app.set('env', 'development') — Express development mode exposes stack traces in error handler
_EXPRESS_DEV_MODE = re.compile(r"""app\.set\s*\(\s*['"]env['"]\s*,\s*['"]development['"]\s*\)""")

# show_exceptions / PROPAGATE_EXCEPTIONS enabled
_WERKZEUG_DEBUG = re.compile(r"\bWERKZEUG_DEBUG_PIN\b|\bUSE_DEBUGGER\s*=\s*True\b", re.IGNORECASE)


_COMMENT_LINE = re.compile(r"^\s*(?:#|//|/\*|\*)")


def _is_test_file(file: FileSnapshot) -> bool:
    return file.path_role in {"tests", "examples"}


def _is_comment_or_string(line: str) -> bool:
    """Skip lines that are pure comments or clearly inside a string literal."""
    stripped = line.lstrip()
    # Python / shell / Ruby comment
    if stripped.startswith("#"):
        return True
    # JS/TS/Go/Java comment
    if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
        return True
    # Lines that start with a quote are likely string literal content in a multiline string
    if stripped.startswith('"') or stripped.startswith("'"):
        return True
    return False


class ErrorDisclosureScanner:
    """Checks for debug mode enabled and exception details leaked into HTTP responses."""

    id = "error_disclosure"
    name = "Error Handling & Info Disclosure"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []

        for file in snapshot.files:
            if file.text is None or _is_test_file(file):
                continue

            if file.extension in _SOURCE_EXTENSIONS:
                findings.extend(self._check_debug_true(file))
                findings.extend(self._check_exception_in_response(file))
                findings.extend(self._check_traceback_in_response(file))
                findings.extend(self._check_express_dev_mode(file))

            if file.extension in _CONFIG_EXTENSIONS or file.path.lower().endswith(".env"):
                findings.extend(self._check_debug_true(file))

        return findings

    def _check_debug_true(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if _is_comment_or_string(line):
                continue
            if _DEBUG_TRUE.search(line) or _FLASK_DEBUG.search(line) or _WERKZEUG_DEBUG.search(line):
                findings.append(
                    Finding(
                        id=stable_finding_id(self.id, "debug_mode_enabled", f"{file.path}:{line_no}"),
                        title="Debug mode appears to be enabled",
                        description=(
                            "A debug flag is set to true. In most web frameworks (Flask, Django, "
                            "Express, Rails) this causes full stack traces to be returned to the "
                            "browser or API caller on any unhandled error, leaking internal file "
                            "paths, library versions, environment variables, and source code "
                            "snippets. This should never be enabled in a production environment."
                        ),
                        category="error_disclosure",
                        severity="high",
                        confidence="medium",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(
                                    path=file.path, line_start=line_no, line_end=line_no
                                ),
                                description="Debug flag set to true.",
                                excerpt=line.strip()[:120],
                            )
                        ],
                        recommendation=(
                            "Set debug to false (or omit it) in production. Use an environment "
                            "variable to control the value: `DEBUG = os.environ.get('DEBUG', 'false') == 'true'`. "
                            "Ensure `.env` files with `DEBUG=true` are never deployed to production."
                        ),
                        scanner_id=self.id,
                        scanner_version=self.version,
                    )
                )
        return findings

    def _check_exception_in_response(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        is_py = file.extension == ".py"
        is_js = file.extension in {".js", ".ts", ".jsx", ".tsx"}

        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if _is_comment_or_string(line):
                continue
            matched = False
            if is_py and _EXCEPTION_IN_RESPONSE_PY.search(line):
                matched = True
            elif is_js and _EXCEPTION_IN_RESPONSE_JS.search(line):
                matched = True

            if matched:
                findings.append(
                    Finding(
                        id=stable_finding_id(
                            self.id, "exception_detail_in_response", f"{file.path}:{line_no}"
                        ),
                        title="Exception detail returned directly in HTTP response",
                        description=(
                            "An exception message or stack trace appears to be included verbatim "
                            "in an HTTP response body. This leaks internal implementation details "
                            "— library names, file paths, SQL query fragments — that attackers can "
                            "use to tailor further exploits. OWASP categorises this as Information "
                            "Exposure (CWE-209)."
                        ),
                        category="error_disclosure",
                        severity="medium",
                        confidence="medium",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(
                                    path=file.path, line_start=line_no, line_end=line_no
                                ),
                                description="Exception detail included in response.",
                                excerpt=line.strip()[:120],
                            )
                        ],
                        recommendation=(
                            "Return a generic error message to the caller (e.g. `{'error': 'Internal "
                            "server error'}`). Log the full exception server-side where only your "
                            "team can access it. Use a structured error format with an opaque "
                            "request-ID so support can correlate logs without exposing internals."
                        ),
                        scanner_id=self.id,
                        scanner_version=self.version,
                    )
                )
        return findings

    def _check_traceback_in_response(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if _is_comment_or_string(line):
                continue
            if _TRACEBACK_IN_RESPONSE.search(line):
                findings.append(
                    Finding(
                        id=stable_finding_id(
                            self.id, "traceback_in_response", f"{file.path}:{line_no}"
                        ),
                        title="Full traceback may be returned in HTTP response",
                        description=(
                            "A call to `traceback.format_exc()` or `sys.exc_info()` was found in "
                            "what appears to be a response path. Returning a Python traceback to an "
                            "API caller exposes internal file paths, class names, and logic flow, "
                            "significantly lowering the bar for targeted attacks."
                        ),
                        category="error_disclosure",
                        severity="high",
                        confidence="low",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(
                                    path=file.path, line_start=line_no, line_end=line_no
                                ),
                                description="Traceback captured — verify it is not forwarded to callers.",
                                excerpt=line.strip()[:120],
                            )
                        ],
                        recommendation=(
                            "Log the traceback server-side (e.g. `logger.exception(...)`) and "
                            "return only a safe error message to the caller."
                        ),
                        scanner_id=self.id,
                        scanner_version=self.version,
                    )
                )
        return findings

    def _check_express_dev_mode(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for line_no, line in enumerate(file.text.splitlines(), start=1):  # type: ignore[union-attr]
            if _is_comment_or_string(line):
                continue
            if _EXPRESS_DEV_MODE.search(line):
                findings.append(
                    Finding(
                        id=stable_finding_id(
                            self.id, "express_development_mode", f"{file.path}:{line_no}"
                        ),
                        title="Express app set to 'development' mode",
                        description=(
                            "Setting `app.set('env', 'development')` in Express enables the "
                            "development error handler, which returns full stack traces in HTTP "
                            "error responses. This setting should never be present in production "
                            "code; Express reads `NODE_ENV` automatically if this line is absent."
                        ),
                        category="error_disclosure",
                        severity="medium",
                        confidence="high",
                        evidence=[
                            FindingEvidence(
                                location=SourceLocation(
                                    path=file.path, line_start=line_no, line_end=line_no
                                ),
                                description="Express environment hard-coded to 'development'.",
                                excerpt=line.strip()[:120],
                            )
                        ],
                        recommendation=(
                            "Remove this line and set the `NODE_ENV` environment variable to "
                            "`production` in your deployment configuration instead."
                        ),
                        scanner_id=self.id,
                        scanner_version=self.version,
                    )
                )
        return findings
