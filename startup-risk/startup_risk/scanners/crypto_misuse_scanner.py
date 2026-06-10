"""
Cryptography Misuse Scanner
============================
Static checks for weak or incorrectly applied cryptography. All findings are
medium severity — the patterns are exploitable but require attacker-controlled
input or privileged access to trigger.

Six checks (all per-file):
    1. Weak hash for passwords  — MD5/SHA-1 used to hash passwords or credentials.
    2. Weak hash in general use — MD5/SHA-1 used anywhere non-trivially
                                   (checksums for integrity, signatures, etc.).
    3. ECB cipher mode          — Block cipher in ECB mode leaks plaintext patterns.
    4. Hardcoded IV / nonce     — Static initialisation vector defeats
                                   semantic security of CBC/CTR/GCM modes.
    5. Insecure random          — Math.random(), random.random(), etc. used for
                                   tokens, passwords, or session IDs.
    6. Hardcoded secret key     — Symmetric key or HMAC secret assigned as a
                                   string literal in source code.

References: NIST SP 800-131A (algorithm transitions), OWASP Cryptographic
Failures (A02:2021), PCI DSS Req. 4 & 6, FIPS 140-3.
"""
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

# ---------------------------------------------------------------------------
# File extensions to scan
# ---------------------------------------------------------------------------

_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".rb", ".java", ".go", ".cs", ".php",
    ".kt", ".rs", ".scala", ".swift", ".c", ".cpp",
})
_CONFIG_EXTENSIONS = frozenset({".yml", ".yaml", ".json", ".toml", ".env", ".ini", ".cfg"})

_CONTEXT_RADIUS = 5  # lines of context included in evidence snippets

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# -- Check 1: weak hash used specifically for passwords / credentials ----------
_PASSWORD_CONTEXT_PATTERN = re.compile(
    r"\b(?:password|passwd|pwd|passphrase|secret|credential|auth_token|api_key)\b",
    re.IGNORECASE,
)
_WEAK_HASH_CALL_PATTERN = re.compile(
    r"""(?:
        hashlib\.(?:md5|sha1)\s*\(
        | MD5(?:Digest)?\s*\(
        | SHA1(?:Digest)?\s*\(
        | Digest::MD5
        | Digest::SHA1
        | (?:crypto|require\(['"]crypto['"]\)).*\.createHash\s*\(\s*['"](?:md5|sha1)['"]\s*\)
        | MessageDigest\.getInstance\s*\(\s*['"](?:MD5|SHA-?1)['"]\s*\)
        | md5\s*\(          # PHP md5()
        | sha1\s*\(         # PHP sha1()
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# -- Check 2: weak hash in general use (non-password) -------------------------
# Same hash call pattern; separation from check 1 is done in logic.
_WEAK_HASH_GENERAL_PATTERN = _WEAK_HASH_CALL_PATTERN  # reused intentionally

# -- Check 3: ECB cipher mode -------------------------------------------------
_ECB_PATTERN = re.compile(
    r"""(?:
        ['"]\s*AES/ECB
        | MODE_ECB
        | CipherMode\.ECB
        | Cipher\.getInstance\s*\(\s*['"]AES/ECB
        | \.createCipheriv\s*\(\s*['"]aes-\d+-ecb
        | aes\.new\s*\([^)]*AES\.MODE_ECB
        | new\s+AesEcb
        | ECBMode
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# -- Check 4: hardcoded / static IV or nonce ----------------------------------
_IV_ASSIGN_PATTERN = re.compile(
    r"""(?:
        \b(?:iv|nonce|initialization_vector|init_vector)\s*=\s*b?['"]
        | \b(?:iv|nonce)\s*=\s*b(?:ytes)?\s*\(
        | IvParameterSpec\s*\(\s*new\s+byte
        | getBytes\s*\(\s*\)\s*\)   # common Java: "hardcodediv".getBytes()
        | \.createCipheriv\s*\([^,]+,\s*[^,]+,\s*['"]   # Node: fixed IV string
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# Suppress if IV is explicitly generated randomly
_RANDOM_IV_PATTERN = re.compile(
    r"\b(?:os\.urandom|secrets\.token|Random\.nextBytes|SecureRandom"
    r"|crypto\.randomBytes|getRandomValues|generate_nonce)\b",
    re.IGNORECASE,
)

# -- Check 5: insecure random used for security-sensitive values --------------
_INSECURE_RANDOM_PATTERN = re.compile(
    r"""(?:
        Math\.random\s*\(\s*\)
        | (?<!\.)random\.random\s*\(\s*\)   # Python random.random() but not secrets
        | (?<!\.)random\.randint\s*\(
        | (?<!\.)random\.choice\s*\(
        | (?<!\.)random\.randbytes\s*\(
        | new\s+Random\s*\(\s*\)            # Java java.util.Random
        | rand\s*\(\s*\)                    # C stdlib rand()
        | srand\s*\(                        # C srand()
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_SECURITY_SENSITIVE_CONTEXT = re.compile(
    r"\b(?:token|session|secret|password|passwd|nonce|csrf|key|salt|otp"
    r"|auth|cookie|uuid|id|random_string|generate)\b",
    re.IGNORECASE,
)
# Suppress if the file clearly uses a secure random instead
_SECURE_RANDOM_PATTERN = re.compile(
    r"\b(?:secrets\.|crypto\.randomBytes|SecureRandom|getRandomValues"
    r"|os\.urandom|token_hex|token_urlsafe|token_bytes)\b",
    re.IGNORECASE,
)

# -- Check 6: hardcoded symmetric key or HMAC secret -------------------------
_KEY_ASSIGN_PATTERN = re.compile(
    r"""(?:
        \b(?:secret_key|hmac_key|encryption_key|aes_key|signing_key
            |jwt_secret|app_secret|symmetric_key|private_key_bytes)
            \s*=\s*['"][A-Za-z0-9+/=_\-]{8,}['"]
        | AES\.new\s*\(\s*b?['"][A-Za-z0-9+/=_\-]{16,}['"]
        | hmac\.new\s*\(\s*b?['"][A-Za-z0-9+/=_\-]{8,}['"]
        | new\s+SecretKeySpec\s*\(\s*['"][A-Za-z0-9+/=_\-]{8,}['"]\.getBytes
        | HS256.*['"][A-Za-z0-9+/=_\-]{8,}['"]
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# Suppress env-var / config reads — those are fine
_KEY_FROM_ENV_PATTERN = re.compile(
    r"\b(?:os\.(?:environ|getenv)|process\.env|System\.getenv"
    r"|config\.|settings\.|getenv|environ\.get)\b",
    re.IGNORECASE,
)


def _context(lines: list[str], index: int, radius: int = _CONTEXT_RADIUS) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class CryptoMisuseScanner:
    """
    Static checks for weak or incorrectly applied cryptography.

    All findings are medium severity. Checks are purely regex-based — no AST,
    no runtime execution.
    """

    id = "crypto_misuse"
    name = "Cryptography Misuse"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.extension not in _SOURCE_EXTENSIONS | _CONFIG_EXTENSIONS:
                continue
            is_test = file.path_role in {"tests", "examples"}
            findings.extend(self._check_weak_hash_password(file, is_test))
            findings.extend(self._check_weak_hash_general(file, is_test))
            findings.extend(self._check_ecb_mode(file, is_test))
            findings.extend(self._check_hardcoded_iv(file, is_test))
            findings.extend(self._check_insecure_random(file, is_test))
            findings.extend(self._check_hardcoded_key(file, is_test))
        return findings

    # ------------------------------------------------------------------
    # Check 1 — weak hash for passwords
    # ------------------------------------------------------------------

    def _check_weak_hash_password(self, file: FileSnapshot, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _WEAK_HASH_CALL_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if not _PASSWORD_CONTEXT_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "weak_hash_password", f"{file.path}:{i}"),
                title="Non-compliant algorithm used for credential storage",
                description=(
                    "A hashing algorithm that does not meet current security standards "
                    "is used in a credential storage context. This area should be reviewed "
                    "by your security team before the next release."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Non-compliant algorithm detected near credential handling.",
                )],
                recommendation=(
                    "Consult your security team or your organization's approved algorithm list "
                    "for current credential storage requirements. This location should be "
                    "remediated before the next production release."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 2 — weak hash in general use
    # ------------------------------------------------------------------

    def _check_weak_hash_general(self, file: FileSnapshot, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _WEAK_HASH_GENERAL_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            # Already reported as password issue — skip
            if _PASSWORD_CONTEXT_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "weak_hash_general", f"{file.path}:{i}"),
                title="Deprecated hashing algorithm detected",
                description=(
                    "A hashing algorithm that does not meet current security standards is in use. "
                    "Depending on how it is applied, this may not satisfy compliance requirements. "
                    "Confirm with your security team whether this use case is acceptable."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Non-compliant hashing algorithm detected.",
                )],
                recommendation=(
                    "Review with your security team. If this is used for any integrity or "
                    "authentication purpose, it should be replaced with an algorithm approved "
                    "under your organization's cryptography policy."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 3 — ECB cipher mode
    # ------------------------------------------------------------------

    def _check_ecb_mode(self, file: FileSnapshot, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _ECB_PATTERN.search(line):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "ecb_cipher_mode", f"{file.path}:{i}"),
                title="Non-standard cipher mode configuration detected",
                description=(
                    "A cipher mode configuration that does not meet current security standards "
                    "is in use. This configuration may not provide the expected level of data "
                    "protection. A security review is recommended before this code is deployed."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Non-compliant cipher mode configuration detected.",
                )],
                recommendation=(
                    "Consult your security team for the approved cipher mode configuration "
                    "for your use case before deploying this code to production."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 4 — hardcoded IV / nonce
    # ------------------------------------------------------------------

    def _check_hardcoded_iv(self, file: FileSnapshot, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _IV_ASSIGN_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _RANDOM_IV_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "hardcoded_iv", f"{file.path}:{i}"),
                title="Static encryption parameter detected",
                description=(
                    "An encryption parameter that should vary per operation appears to be "
                    "assigned a fixed value. This may reduce the effectiveness of the "
                    "encryption in use. This area requires a security review."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Encryption parameter appears to be static rather than dynamically generated.",
                )],
                recommendation=(
                    "Consult your security team. Each encryption operation should use a "
                    "freshly generated value for this parameter per your organization's "
                    "cryptography policy."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 5 — insecure random for security-sensitive values
    # ------------------------------------------------------------------

    def _check_insecure_random(self, file: FileSnapshot, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        # If the file uses a secure random API anywhere, trust the developer
        # chose it for sensitive operations and reduce noise.
        full_text = file.text or ""
        if _SECURE_RANDOM_PATTERN.search(full_text):
            return findings

        for i, line in enumerate(lines):
            if not _INSECURE_RANDOM_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if not _SECURITY_SENSITIVE_CONTEXT.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "insecure_random", f"{file.path}:{i}"),
                title="Insufficient randomness source for security-sensitive operation",
                description=(
                    "A randomness source that does not meet cryptographic standards appears "
                    "to be used in a context requiring unpredictability. This may make "
                    "generated values easier to predict than intended. A security review "
                    "is recommended."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Non-cryptographic randomness source detected near security-sensitive context.",
                )],
                recommendation=(
                    "Consult your security team for the approved randomness API for your "
                    "language and platform. Only cryptographically approved sources should "
                    "be used for security-sensitive values."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    # ------------------------------------------------------------------
    # Check 6 — hardcoded symmetric key or HMAC secret
    # ------------------------------------------------------------------

    def _check_hardcoded_key(self, file: FileSnapshot, is_test: bool) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]

        for i, line in enumerate(lines):
            if not _KEY_ASSIGN_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _KEY_FROM_ENV_PATTERN.search(ctx):
                continue
            findings.append(Finding(
                id=stable_finding_id(self.id, "hardcoded_crypto_key", f"{file.path}:{i}"),
                title="Cryptographic material may be embedded in source",
                description=(
                    "A value consistent with a cryptographic key or secret appears to be "
                    "assigned directly in source code rather than loaded from a secure "
                    "external source. This may expose sensitive material to anyone with "
                    "repository access. Immediate review is recommended."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Possible cryptographic material detected in source.",
                )],
                recommendation=(
                    "Consult your security team. Cryptographic material should be stored "
                    "and accessed through your organization's approved secrets management "
                    "process, not embedded in source code."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings
