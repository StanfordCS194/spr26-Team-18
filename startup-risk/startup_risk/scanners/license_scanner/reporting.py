from __future__ import annotations

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import Finding, FindingEvidence, SourceLocation
from startup_risk.scanners.license_scanner.models import Dependency, LicenseClassification, LicenseEvidence


SCANNER_ID = "license_risk"
SCANNER_VERSION = "1.0.0"
MAX_EVIDENCE_EXCERPT_CHARS = 800


def finding_for_license(
    dependency: Dependency,
    classification: LicenseClassification,
    *,
    rule: str | None = None,
    extra_description: str | None = None,
) -> Finding | None:
    if classification.priority == "low" and rule is None:
        return None
    rule_id = rule or f"{classification.priority}_license"
    title = _title(dependency, classification, rule_id)
    evidence = [_finding_evidence(item) for item in dependency.evidence] or [
        FindingEvidence(
            location=_location(dependency.source_file, dependency.source_line),
            description="Dependency source location.",
        )
    ]
    return Finding(
        id=stable_finding_id(SCANNER_ID, rule_id, dependency.key),
        title=title,
        description=extra_description or classification.explanation,
        category="license_risk",
        severity=classification.priority,
        confidence=classification.confidence,
        evidence=evidence,
        recommendation=classification.recommendation,
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def finding_for_flag(dependency: Dependency, flag: str) -> Finding:
    if flag.startswith("npm_lifecycle_script:"):
        script = flag.split(":", maxsplit=1)[1]
        title = "NPM lifecycle script should not be executed by scanner"
        description = (
            f"The package metadata declares an npm {script} lifecycle script. "
            "The license scanner records this as metadata only and must not execute it."
        )
        recommendation = "Review the script before installing this package in other workflows; keep scanner execution data-only."
        severity = "medium"
    elif flag == "vendored_missing_license":
        title = "Vendored code has no clear license file"
        description = "A vendored component was detected without a LICENSE, COPYING, or NOTICE file."
        recommendation = "Identify the upstream project and add license evidence before production use."
        severity = "low" if is_dev_dependency(dependency) else "high"
    else:
        title = "License scanner review flag"
        description = f"The dependency has scanner flag {flag}."
        recommendation = "Review the flagged dependency metadata."
        severity = "medium"
    return Finding(
        id=stable_finding_id(SCANNER_ID, flag, dependency.key),
        title=title,
        description=description,
        category="license_risk",
        severity=severity,
        confidence="medium" if flag == "vendored_missing_license" and severity != "high" else "high",
        evidence=[_finding_evidence(item) for item in dependency.evidence] or [
            FindingEvidence(location=_location(dependency.source_file, dependency.source_line), description="Flagged dependency.")
        ],
        recommendation=recommendation,
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def finding_for_skipped(path_and_reason: str) -> Finding:
    return Finding(
        id=stable_finding_id(SCANNER_ID, "skipped_license_input", path_and_reason),
        title="License scanner skipped an input",
        description=f"The scanner could not use this potential license/dependency input: {path_and_reason}",
        category="license_risk",
        severity="medium",
        confidence="high",
        evidence=[FindingEvidence(description=path_and_reason)],
        recommendation="Increase scanner limits or inspect this file manually if it contains dependency or license data.",
        scanner_id=SCANNER_ID,
        scanner_version=SCANNER_VERSION,
    )


def _title(dependency: Dependency, classification: LicenseClassification, rule_id: str) -> str:
    label = f"{dependency.name}{'@' + dependency.version if dependency.version else ''}"
    if rule_id == "llm_batch_error":
        return f"Review LLM batch result for {label}"
    if rule_id == "unknown_license":
        return f"Resolve unknown license for {label}"
    if classification.normalized_license is None:
        return f"Review unknown license for {label}"
    return f"Review {classification.normalized_license} license for {label}"


def _finding_evidence(evidence: LicenseEvidence) -> FindingEvidence:
    return FindingEvidence(
        location=_location(evidence.file, evidence.line),
        description=_description(evidence),
        excerpt=_bounded_excerpt(evidence.text),
    )


def _description(evidence: LicenseEvidence) -> str:
    if evidence.detected_license:
        return f"{evidence.source} evidence indicates {evidence.detected_license}."
    return f"{evidence.source} evidence did not establish a license."


def _location(path: str | None, line: int | None) -> SourceLocation | None:
    if path is None:
        return None
    return SourceLocation(path=path, line_start=line, line_end=line)


def _bounded_excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= MAX_EVIDENCE_EXCERPT_CHARS:
        return text
    return text[:MAX_EVIDENCE_EXCERPT_CHARS].rstrip() + "..."


def classification_for_unknown_license(
    dependency: Dependency,
    *,
    deterministic_only: bool,
) -> LicenseClassification:
    if (
        is_vendored_dependency(dependency)
        and "vendored_license_metadata_present" not in dependency.flags
        and not is_dev_dependency(dependency)
    ):
        priority = "high"
        confidence = "medium"
    elif is_dev_dependency(dependency):
        priority = "low"
        confidence = "low" if _only_weak_path_evidence(dependency) else "medium"
    else:
        priority = "medium"
        confidence = "medium"

    recommendation = "Resolve via package registry metadata, package artifact inspection, or manual review."
    if deterministic_only:
        recommendation += " Run with registry/artifact/LLM enrichment before treating this as confirmed risk."

    return LicenseClassification(
        normalized_license=None,
        priority=priority,
        confidence=confidence,
        explanation="The scanner did not establish a license for this dependency from the available local evidence.",
        recommendation=recommendation,
        source="deterministic",
    )


def is_dev_dependency(dependency: Dependency) -> bool:
    if any(
        flag in {
            "dependency_scope:devDependencies",
            "dependency_scope:docs",
            "dependency_scope:lockfile_dev",
            "dependency_scope:optionalDependencies",
            "dependency_scope:test",
        }
        for flag in dependency.flags
    ):
        return True
    return is_docs_path(dependency.source_file) or is_test_or_fixture_path(dependency.source_file)


def is_test_or_fixture_path(path: str | None) -> bool:
    if not path:
        return False
    parts = path.lower().split("/")
    return any(part in {"test", "tests", "fixtures", "examples"} for part in parts)


def is_docs_path(path: str | None) -> bool:
    if not path:
        return False
    lower = path.lower()
    return lower.startswith("docs/") or "/docs/" in lower


def is_vendored_dependency(dependency: Dependency) -> bool:
    return dependency.relationship == "vendored" or dependency.source_type == "vendored_code"


def _only_weak_path_evidence(dependency: Dependency) -> bool:
    return not any(evidence.detected_license or evidence.text for evidence in dependency.evidence)
