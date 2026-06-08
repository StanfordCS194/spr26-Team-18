from __future__ import annotations

from startup_risk.scanners.base import InventoryScanner, Scanner
from startup_risk.scanners.code_compliance_scanner import CodeComplianceScanner
from startup_risk.scanners.dependency_scanner import DependencyRiskScanner
from startup_risk.scanners.dependency_vuln_scanner import DependencyVulnScanner
from startup_risk.scanners.license_scanner import LicenseRiskScanner
from startup_risk.scanners.outdated_deps_scanner import OutdatedDepsScanner
from startup_risk.scanners.repo_inventory import RepoInventoryScanner
from startup_risk.scanners.secret_scanner import SecretScanner
from startup_risk.scanners.static_hygiene import StaticHygieneScanner


def default_scanners(
    *,
    deterministic_license_only: bool = False,
    license_llm_provider: str | None = None,
    license_llm_model: str | None = None,
    license_batch_timeout_seconds: int = 24 * 60 * 60,
    license_poll_interval_seconds: int = 60,
    license_llm_prompt_token_budget: int = 200_000,
    license_llm_max_batch_requests: int = 50_000,
    license_llm_max_batch_file_bytes: int = 200_000_000,
    license_registry_metadata: bool = False,
    license_artifact_inspection: bool = False,
    license_source_repo: bool = False,
    vuln_osv: bool = False,
) -> list[Scanner]:
    return [
        StaticHygieneScanner(),
        DependencyRiskScanner(),
        SecretScanner(),
        LicenseRiskScanner(
            deterministic_only=deterministic_license_only,
            provider_name=license_llm_provider,
            model_name=license_llm_model,
            batch_timeout_seconds=license_batch_timeout_seconds,
            poll_interval_seconds=license_poll_interval_seconds,
            llm_prompt_token_budget=license_llm_prompt_token_budget,
            llm_max_batch_requests=license_llm_max_batch_requests,
            llm_max_batch_file_bytes=license_llm_max_batch_file_bytes,
            enable_registry_metadata=license_registry_metadata,
            enable_artifact_inspection=license_artifact_inspection,
            enable_source_repo=license_source_repo,
        ),
        DependencyVulnScanner(enable_osv=vuln_osv),
        OutdatedDepsScanner(),
        CodeComplianceScanner(),
    ]


def default_inventory_scanner() -> InventoryScanner:
    return RepoInventoryScanner()
