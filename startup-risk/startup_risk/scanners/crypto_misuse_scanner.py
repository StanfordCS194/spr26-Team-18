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
                title="MD5 or SHA-1 used to hash a password or credential",
                description=(
                    "MD5 and SHA-1 are cryptographically broken and must not be used "
                    "to hash passwords or credentials. Both algorithms are fast by design, "
                    "making them trivially brute-forceable with GPU rigs. NIST SP 800-131A "
                    "disallows SHA-1 for security applications; PCI DSS Req. 8.3 requires "
                    "strong one-way hashing for stored passwords."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Weak hash algorithm applied near password/credential context.",
                )],
                recommendation=(
                    "Replace with a purpose-built password hashing function: bcrypt, scrypt, "
                    "Argon2id (recommended by OWASP), or PBKDF2-SHA256 with ≥ 310,000 iterations. "
                    "Never use a general-purpose hash (MD5, SHA-1, SHA-256) directly for passwords."
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
                title="MD5 or SHA-1 used for integrity or identification",
                description=(
                    "MD5 and SHA-1 have known collision vulnerabilities (SHAttered, Flame malware) "
                    "and are deprecated by NIST SP 800-131A for any security-relevant use. "
                    "If used for data integrity, an attacker can craft a collision to substitute "
                    "malicious content with the same hash. Acceptable only for non-security "
                    "checksums (e.g., deduplication) where collision resistance is not required."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Weak hash algorithm detected.",
                )],
                recommendation=(
                    "Replace with SHA-256 or SHA-3 for security-sensitive hashing. "
                    "For HMAC-based authentication, use HMAC-SHA256. "
                    "MD5 is acceptable only for non-security use cases such as ETag generation "
                    "or cache keys where collision resistance is not a requirement."
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
                title="Block cipher used in ECB mode",
                description=(
                    "ECB (Electronic Codebook) mode encrypts each block independently, so "
                    "identical plaintext blocks produce identical ciphertext blocks. This leaks "
                    "plaintext patterns — the 'ECB penguin' attack can reconstruct images or "
                    "structured data even without the key. ECB is explicitly prohibited by "
                    "NIST SP 800-38A and PCI DSS Req. 4."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="high",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="ECB mode cipher detected.",
                )],
                recommendation=(
                    "Replace ECB with an authenticated encryption mode. "
                    "AES-GCM is the current recommendation (provides both confidentiality and "
                    "integrity). AES-CBC with HMAC-SHA256 is acceptable if GCM is unavailable, "
                    "but requires careful IV management."
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
                title="Hardcoded or static IV / nonce used with block cipher",
                description=(
                    "An initialisation vector (IV) or nonce assigned from a string or fixed "
                    "byte array makes every encryption of the same plaintext produce the same "
                    "ciphertext — completely defeating the semantic security of CBC, CTR, and GCM "
                    "modes. For GCM specifically, IV reuse with the same key is catastrophic: "
                    "it allows recovery of the authentication key. NIST SP 800-38D requires "
                    "that GCM IVs never be reused under the same key."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="IV or nonce appears to be hardcoded rather than randomly generated.",
                )],
                recommendation=(
                    "Generate a fresh random IV for every encryption operation using a "
                    "cryptographically secure source: os.urandom(12) for GCM (96-bit IV), "
                    "os.urandom(16) for CBC (128-bit IV). Prepend the IV to the ciphertext "
                    "so it can be recovered for decryption — it does not need to be secret."
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
                title="Non-cryptographic random used for a security-sensitive value",
                description=(
                    "A non-cryptographic random number generator (Math.random, random.random, "
                    "java.util.Random, C rand()) is used near a token, session ID, secret, or "
                    "similar security-sensitive value. These PRNGs are seeded from predictable "
                    "sources and are not suitable for cryptographic use — an attacker who knows "
                    "the seed or observes enough outputs can predict future values. OWASP A02 "
                    "and NIST SP 800-90A require a CSPRNG for all security tokens."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Insecure PRNG used near security-sensitive variable.",
                )],
                recommendation=(
                    "Use a cryptographically secure random source: "
                    "Python → secrets.token_urlsafe() / secrets.token_bytes() / os.urandom(); "
                    "Node.js → crypto.randomBytes() / crypto.randomUUID(); "
                    "Java → java.security.SecureRandom; "
                    "Go → crypto/rand; "
                    "Browser → crypto.getRandomValues()."
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
                title="Symmetric encryption key or HMAC secret hardcoded in source",
                description=(
                    "A cryptographic key or HMAC secret is assigned directly from a string "
                    "literal in source code. Anyone with read access to the repository — "
                    "including every past and future collaborator, CI runner, and git-hosting "
                    "employee — can extract and use the key. Key rotation is also impossible "
                    "without a code change and redeploy. PCI DSS Req. 3.6 requires that "
                    "cryptographic keys be stored securely, separate from the encrypted data "
                    "and the application code."
                ),
                category="crypto_misuse",
                severity="medium",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    excerpt=line.strip()[:120],
                    description="Cryptographic key literal detected in source.",
                )],
                recommendation=(
                    "Move the key to an environment variable or a secrets manager "
                    "(AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager). "
                    "Read it at runtime: os.getenv('ENCRYPTION_KEY') or equivalent. "
                    "If the key was ever committed to git history, rotate it immediately — "
                    "deleting the line does not remove it from history."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings
