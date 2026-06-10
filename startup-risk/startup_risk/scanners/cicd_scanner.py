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

# GitHub Actions workflow files only
_WORKFLOW_PATH = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$", re.IGNORECASE)

# Trusted action namespaces — we only flag *third-party* actions without SHA pins
_TRUSTED_NAMESPACES = frozenset({
    "actions", "github", "aws-actions", "azure", "docker",
    "google-github-actions", "hashicorp", "gradle", "gradle/actions",
    "codecov", "sonarsource",
})

# Matches `uses: owner/repo@ref` — captures owner and full ref
_USES_PATTERN = re.compile(
    r"^\s+uses:\s+([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-/]+)@([a-f0-9]{40}|[^\s#]+)",
    re.MULTILINE,
)

# A 40-char hex string → already pinned to a commit SHA
_SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")

# pull_request_target trigger (elevated permissions, runs in base-branch context)
_PRT_TRIGGER = re.compile(r"\bpull_request_target\b")

# checkout of PR head inside pull_request_target — classic code-injection pattern
_HEAD_REF_CHECKOUT = re.compile(
    r"ref:\s*\$\{\{\s*(?:github\.event\.pull_request\.head\.(?:sha|ref)|github\.head_ref)\s*\}\}"
)

# Secrets or env vars set at the workflow/job level exposed to all steps
_SECRET_IN_ENV = re.compile(
    r"env:\s*\n(?:\s+\S.*\n)*?\s+\w+:\s*\$\{\{\s*secrets\.",
    re.MULTILINE,
)

# permissions: write-all or no explicit permissions block (defaults to read/write on older repos)
_WRITE_ALL = re.compile(r"permissions:\s*write-all", re.IGNORECASE)


class CICDSecurityScanner:
    """Static checks for GitHub Actions security misconfigurations."""

    id = "cicd_security"
    name = "CI/CD Pipeline Security"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        workflow_files = [f for f in snapshot.files if _WORKFLOW_PATH.match(f.path)]

        if not workflow_files:
            return findings

        for file in workflow_files:
            if file.text is None:
                continue
            findings.extend(self._check_unpinned_actions(file))
            findings.extend(self._check_pull_request_target(file))
            findings.extend(self._check_write_all_permissions(file))

        return findings

    def _check_unpinned_actions(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        for match in _USES_PATTERN.finditer(file.text):  # type: ignore[arg-type]
            owner = match.group(1)
            ref = match.group(3)
            if owner.lower() in _TRUSTED_NAMESPACES:
                continue
            if _SHA_PATTERN.match(ref):
                continue  # already pinned to a SHA
            line_no = file.text[: match.start()].count("\n") + 1  # type: ignore[index]
            findings.append(
                Finding(
                    id=stable_finding_id(self.id, "unpinned_action", f"{file.path}:{match.group(0).strip()}"),
                    title=f"Third-party GitHub Action not pinned to a commit SHA",
                    description=(
                        f"The action `{owner}/{match.group(2)}@{ref}` uses a mutable tag or branch "
                        "reference. A tag can be force-pushed to point at new, potentially malicious "
                        "code, making your CI pipeline a supply-chain attack vector. GitHub's own "
                        "security hardening guide recommends pinning all third-party actions to a "
                        "full 40-character commit SHA."
                    ),
                    category="supply_chain",
                    severity="medium",
                    confidence="high",
                    evidence=[
                        FindingEvidence(
                            location=SourceLocation(path=file.path, line_start=line_no, line_end=line_no),
                            description=f"Action `{owner}/{match.group(2)}@{ref}` uses a mutable ref.",
                            excerpt=match.group(0).strip()[:120],
                        )
                    ],
                    recommendation=(
                        f"Replace `@{ref}` with the full commit SHA of the version you trust. "
                        "Example: `uses: {owner}/{match.group(2)}@<40-char-sha>  # {ref}`. "
                        "Tools like `pin-github-action` or Dependabot can automate this."
                    ),
                    scanner_id=self.id,
                    scanner_version=self.version,
                )
            )
        return findings

    def _check_pull_request_target(self, file: FileSnapshot) -> list[Finding]:
        text = file.text  # type: ignore[assignment]
        if not _PRT_TRIGGER.search(text):
            return []
        if not _HEAD_REF_CHECKOUT.search(text):
            return []

        line_no = next(
            (i + 1 for i, ln in enumerate(text.splitlines()) if _HEAD_REF_CHECKOUT.search(ln)),
            1,
        )
        return [
            Finding(
                id=stable_finding_id(self.id, "pull_request_target_checkout", file.path),
                title="pull_request_target workflow checks out PR head — arbitrary code execution risk",
                description=(
                    "This workflow is triggered by `pull_request_target` (runs with write permissions "
                    "and access to secrets) and checks out the PR contributor's code via "
                    "`github.head_ref` or `github.event.pull_request.head.sha`. An attacker can "
                    "submit a PR that modifies workflow steps and exfiltrate repository secrets. "
                    "This pattern has been used in real-world supply-chain attacks (CVE-2021-21124)."
                ),
                category="supply_chain",
                severity="critical",
                confidence="high",
                evidence=[
                    FindingEvidence(
                        location=SourceLocation(path=file.path, line_start=line_no, line_end=line_no),
                        description="PR head ref checked out inside a pull_request_target workflow.",
                    )
                ],
                recommendation=(
                    "Do not check out the PR head in a `pull_request_target` workflow unless you "
                    "have explicitly audited the code first. Use `pull_request` (read-only) for "
                    "untrusted PR code, and `pull_request_target` only for trusted, already-merged "
                    "code. See github.com/nicowillis/ghas-security for mitigations."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]

    def _check_write_all_permissions(self, file: FileSnapshot) -> list[Finding]:
        text = file.text  # type: ignore[assignment]
        if not _WRITE_ALL.search(text):
            return []

        line_no = next(
            (i + 1 for i, ln in enumerate(text.splitlines()) if _WRITE_ALL.search(ln)),
            1,
        )
        return [
            Finding(
                id=stable_finding_id(self.id, "write_all_permissions", file.path),
                title="Workflow grants write-all permissions to GITHUB_TOKEN",
                description=(
                    "`permissions: write-all` grants every available permission to the workflow's "
                    "GITHUB_TOKEN, including the ability to write to the repository, publish "
                    "packages, and manage issues and PRs. If any step in the workflow is "
                    "compromised, the attacker inherits all of these permissions. GitHub recommends "
                    "the principle of least privilege: only grant the specific permissions needed."
                ),
                category="supply_chain",
                severity="medium",
                confidence="high",
                evidence=[
                    FindingEvidence(
                        location=SourceLocation(path=file.path, line_start=line_no, line_end=line_no),
                        description="`permissions: write-all` found in workflow.",
                    )
                ],
                recommendation=(
                    "Replace `permissions: write-all` with an explicit minimal set, e.g.:\n"
                    "  permissions:\n"
                    "    contents: read\n"
                    "    pull-requests: write"
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            )
        ]
