from __future__ import annotations

from startup_risk.scanners.accessibility_scanner import AccessibilityScanner
from startup_risk.scanners.ai_governance_scanner import AIGovernanceScanner
from startup_risk.scanners.analytics_privacy import AnalyticsPrivacyScanner
from startup_risk.scanners.crypto_misuse_scanner import CryptoMisuseScanner
from startup_risk.scanners.auth_agent import AuthAccessControlAgent
from startup_risk.scanners.cicd_scanner import CICDSecurityScanner
from startup_risk.scanners.error_disclosure_scanner import ErrorDisclosureScanner
from startup_risk.scanners.legal_docs_scanner import LegalDocScanner
from startup_risk.scanners.rate_limit_scanner import RateLimitScanner
from startup_risk.scanners.base import InventoryScanner, Scanner
from startup_risk.scanners.code_compliance_scanner import CodeComplianceScanner
from startup_risk.scanners.custom_scanner import CustomScanner
from startup_risk.scanners.dependency_scanner import DependencyRiskScanner
from startup_risk.scanners.dependency_vuln_scanner import DependencyVulnScanner
from startup_risk.scanners.financial_compliance_scanner import FinancialComplianceScanner
from startup_risk.scanners.infra_agent import InfraMisconfigAgent
from startup_risk.scanners.license_scanner import LicenseRiskScanner
from startup_risk.scanners.outdated_deps_scanner import OutdatedDepsScanner
from startup_risk.scanners.pii_agent import PIIDataFlowAgent
from startup_risk.scanners.repo_inventory import RepoInventoryScanner
from startup_risk.scanners.secret_scanner import SecretScanner
from startup_risk.scanners.static_hygiene import StaticHygieneScanner
from startup_risk.scanners.vuln_exploitability_agent import VulnExploitabilityAgent


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
    vuln_osv: bool = True,
    outdated_registry: bool = True,
    custom_questionnaire: dict | None = None,
    custom_prd_text: str | None = None,
    funding_round: str | None = None,
    entity_type: str | None = None,
    industry: str | None = None,
    international: bool | None = None,
    multi_state: bool | None = None,
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
        OutdatedDepsScanner(enable_registry=outdated_registry),
        AnalyticsPrivacyScanner(),
        AIGovernanceScanner(),
        CryptoMisuseScanner(),
        AccessibilityScanner(),
        CodeComplianceScanner(),
        # LLM reasoning agents. Each is no-op safe: returns [] without an LLM key.
        AuthAccessControlAgent(),
        PIIDataFlowAgent(),
        InfraMisconfigAgent(),
        VulnExploitabilityAgent(enable_osv=vuln_osv),
        FinancialComplianceScanner(
            funding_round=funding_round,
            entity_type=entity_type,
            industry=industry,
            international=international,
            multi_state=multi_state,
        ),
        LegalDocScanner(),
        CICDSecurityScanner(),
        ErrorDisclosureScanner(),
        RateLimitScanner(),
        # Opt-in: returns [] unless a questionnaire/PRD and an LLM are available.
        CustomScanner(
            questionnaire=custom_questionnaire,
            prd_text=custom_prd_text,
        ),
    ]


def default_inventory_scanner() -> InventoryScanner:
    return RepoInventoryScanner()
