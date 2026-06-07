from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from startup_risk.core.models import Finding, RepositorySnapshot
from startup_risk.scanners.license_scanner.discovery import discover
from startup_risk.scanners.license_scanner.licenses import classify_license, is_known_spdx_like, normalize_license
from startup_risk.scanners.license_scanner.llm.anthropic_batch import AnthropicBatchProvider
from startup_risk.scanners.license_scanner.llm.base import BatchProvider, build_prompt
from startup_risk.scanners.license_scanner.llm.openai_batch import OpenAIBatchProvider, estimate_openai_request_bytes
from startup_risk.scanners.license_scanner.models import (
    Dependency,
    LLMBatchResponse,
    LLMItemResult,
    LLMTask,
    LLMTaskItem,
    LicenseClassification,
    LicenseEvidence,
)
from startup_risk.scanners.license_scanner.parsers import generic, npm, python, rust
from startup_risk.scanners.license_scanner.reporting import (
    SCANNER_ID,
    SCANNER_VERSION,
    classification_for_unknown_license,
    finding_for_flag,
    finding_for_license,
    finding_for_skipped,
)


class LicenseScannerConfigError(ValueError):
    """Raised when a normal license scan lacks required batch LLM configuration."""


class LicenseRiskScanner:
    id = SCANNER_ID
    name = "License Risk"
    version = SCANNER_VERSION

    def __init__(
        self,
        *,
        deterministic_only: bool = False,
        batch_provider: BatchProvider | None = None,
        provider_name: str | None = None,
        batch_timeout_seconds: int = 24 * 60 * 60,
        poll_interval_seconds: int = 60,
        task_item_limit: int = 10,
        llm_prompt_token_budget: int | None = None,
        llm_max_batch_requests: int | None = None,
        llm_max_batch_file_bytes: int | None = None,
    ) -> None:
        self.deterministic_only = deterministic_only
        self.batch_provider = batch_provider
        self.provider_name = provider_name
        self.batch_timeout_seconds = batch_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.task_item_limit = task_item_limit
        self.llm_prompt_token_budget = llm_prompt_token_budget or int(
            os.getenv("LICENSE_SCANNER_LLM_PROMPT_TOKEN_BUDGET", "200000")
        )
        self.llm_max_batch_requests = llm_max_batch_requests or int(
            os.getenv("LICENSE_SCANNER_LLM_MAX_BATCH_REQUESTS", "50000")
        )
        self.llm_max_batch_file_bytes = llm_max_batch_file_bytes or int(
            os.getenv("LICENSE_SCANNER_LLM_MAX_BATCH_FILE_BYTES", "200000000")
        )

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        provider = self.batch_provider
        if not self.deterministic_only and provider is None:
            provider = provider_from_env(self.provider_name)

        discovered = discover(snapshot)
        dependencies = self._parse_dependencies(discovered.manifests, discovered.vendored_files)
        dependencies = _dedupe_dependencies(dependencies)

        llm_results: dict[str, LLMItemResult] = {}
        llm_errors: dict[str, str] = {}
        if not self.deterministic_only:
            tasks, task_to_items, budget_errors = self._build_llm_tasks(dependencies)
            llm_errors.update(budget_errors)
            responses = provider.submit_and_wait(
                tasks,
                timeout_seconds=self.batch_timeout_seconds,
                poll_interval_seconds=self.poll_interval_seconds,
            )
            llm_results, response_errors = _parse_batch_responses(responses, task_to_items)
            llm_errors.update(response_errors)

        findings: list[Finding] = []
        for skipped in discovered.skipped:
            findings.append(finding_for_skipped(skipped))
        for dependency in dependencies:
            for flag in dependency.flags:
                if flag.startswith("vendored_root:") or flag.startswith("dependency_scope:") or flag == "local_project":
                    continue
                findings.append(finding_for_flag(dependency, flag))
            if _skip_license_risk(dependency):
                continue
            if "vendored_missing_license" in dependency.flags:
                continue
            item_id = _item_id(dependency)
            classification = _merged_classification(
                dependency,
                llm_results.get(item_id),
                llm_errors.get(item_id),
                deterministic_only=self.deterministic_only,
            )
            if llm_errors.get(item_id):
                findings.append(
                    finding_for_license(
                        dependency,
                        LicenseClassification(
                            normalized_license=None,
                            priority="high",
                            confidence="high",
                            explanation=f"LLM batch review failed or was incomplete: {llm_errors[item_id]}",
                            recommendation="Review this dependency license manually and rerun the nightly batch scan.",
                            source="llm",
                        ),
                        rule="llm_batch_error",
                    )
                )
            finding = finding_for_license(
                dependency,
                classification,
                rule="unknown_license" if classification.normalized_license is None else None,
            )
            if finding is not None:
                findings.append(finding)
        return _dedupe_findings(findings)

    def _parse_dependencies(self, manifests, vendored_files) -> list[Dependency]:
        dependencies: list[Dependency] = []
        for file in manifests:
            dependencies.extend(npm.parse(file))
            dependencies.extend(python.parse(file))
            dependencies.extend(rust.parse(file))
        dependencies.extend(generic.parse_vendored(vendored_files))
        return dependencies

    def _build_llm_tasks(self, dependencies: list[Dependency]) -> tuple[list[LLMTask], dict[str, list[str]], dict[str, str]]:
        items = [
            LLMTaskItem(
                item_id=_item_id(dependency),
                dependency_key=dependency.key,
                dependency_name=dependency.name,
                ecosystem=dependency.ecosystem,
                declared_license=dependency.declared_license,
                evidence=dependency.evidence,
            )
            for dependency in dependencies
            if not _skip_license_risk(dependency)
        ]
        tasks: list[LLMTask] = []
        task_to_items: dict[str, list[str]] = {}
        budget_errors: dict[str, str] = {}
        used_prompt_tokens = 0
        used_file_bytes = 0
        for index in range(0, len(items), self.task_item_limit):
            chunk = items[index : index + self.task_item_limit]
            task_index = len(tasks) + 1
            task_id = f"license-scan-{task_index:04d}"
            prompt = build_prompt(chunk)
            estimated_tokens = estimate_prompt_tokens(prompt)
            estimated_bytes = estimate_task_request_bytes(task_id, chunk, prompt)
            if (
                len(tasks) + 1 > self.llm_max_batch_requests
                or used_prompt_tokens + estimated_tokens > self.llm_prompt_token_budget
                or used_file_bytes + estimated_bytes > self.llm_max_batch_file_bytes
            ):
                reason = (
                    "LLM batch budget exceeded before this dependency could be queued "
                    f"(configured prompt tokens={self.llm_prompt_token_budget}, "
                    f"requests={self.llm_max_batch_requests}, file bytes={self.llm_max_batch_file_bytes})."
                )
                for item in chunk:
                    budget_errors[item.item_id] = reason
                continue
            task = LLMTask(
                task_id=task_id,
                items=chunk,
                prompt=prompt,
                estimated_prompt_tokens=estimated_tokens,
                estimated_request_bytes=estimated_bytes,
            )
            tasks.append(task)
            task_to_items[task_id] = [item.item_id for item in chunk]
            used_prompt_tokens += estimated_tokens
            used_file_bytes += estimated_bytes
        return tasks, task_to_items, budget_errors


def provider_from_env(provider_name: str | None = None) -> BatchProvider:
    _load_local_dotenv()
    provider = (provider_name or os.getenv("LICENSE_SCANNER_LLM_PROVIDER") or "openai").lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LicenseScannerConfigError(
                "OPENAI_API_KEY is required for license scanning unless --deterministic-only is set."
            )
        return OpenAIBatchProvider(
            api_key=api_key,
            model=os.getenv("LICENSE_SCANNER_OPENAI_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
            max_batch_requests=int(os.getenv("LICENSE_SCANNER_LLM_MAX_BATCH_REQUESTS", "50000")),
            max_batch_file_bytes=int(os.getenv("LICENSE_SCANNER_LLM_MAX_BATCH_FILE_BYTES", "200000000")),
            max_prompt_tokens=int(os.getenv("LICENSE_SCANNER_LLM_PROMPT_TOKEN_BUDGET", "200000")),
        )
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LicenseScannerConfigError(
                "ANTHROPIC_API_KEY is required for license scanning unless --deterministic-only is set."
            )
        return AnthropicBatchProvider(
            api_key=api_key,
            model=os.getenv("LICENSE_SCANNER_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
    raise LicenseScannerConfigError("LICENSE_SCANNER_LLM_PROVIDER must be 'openai' or 'anthropic'.")


def _load_local_dotenv() -> None:
    """Load simple KEY=VALUE pairs from the nearest .env without overriding real env vars."""
    for directory in [Path.cwd(), *Path.cwd().parents]:
        env_path = directory / ".env"
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


def estimate_prompt_tokens(text: str) -> int:
    # Conservative approximation for preflight budgeting without requiring tokenizer packages.
    return max(1, (len(text) + 2) // 3)


def estimate_task_request_bytes(task_id: str, items: list[LLMTaskItem], prompt: str) -> int:
    task = LLMTask(task_id=task_id, items=items, prompt=prompt, estimated_prompt_tokens=estimate_prompt_tokens(prompt))
    return estimate_openai_request_bytes(task, os.getenv("LICENSE_SCANNER_OPENAI_MODEL", "gpt-4o-mini"))


def _merged_classification(
    dependency: Dependency,
    llm_result: LLMItemResult | None,
    llm_error: str | None,
    *,
    deterministic_only: bool,
) -> LicenseClassification:
    license_value = _license_value(dependency)
    deterministic = (
        classification_for_unknown_license(dependency, deterministic_only=deterministic_only)
        if license_value is None
        else classify_license(license_value, has_notice=_has_notice(dependency))
    )
    if llm_error or llm_result is None:
        return deterministic
    llm_license = normalize_license(llm_result.detected_license)
    confidence = llm_result.confidence
    if llm_license is None:
        unknown = classification_for_unknown_license(dependency, deterministic_only=deterministic_only)
        return replace(
            unknown,
            confidence="low" if llm_result.confidence == "low" else unknown.confidence,
            explanation=llm_result.reason or unknown.explanation,
            source="llm",
        )
    if confidence == "high" and not is_known_spdx_like(llm_license):
        confidence = "medium"
    llm_classification = classify_license(llm_license, has_notice=_has_notice(dependency), source="llm")
    llm_classification = replace(llm_classification, confidence=confidence)

    if llm_result.needs_review or llm_result.is_custom_or_modified:
        return LicenseClassification(
            normalized_license=llm_license,
            priority="high" if llm_result.is_custom_or_modified else max_priority(deterministic.priority, "medium"),
            confidence=confidence,
            explanation=llm_result.reason or "Batch LLM review marked this license evidence for review.",
            recommendation="Review the license evidence manually before approving production use.",
            source="llm",
        )

    if deterministic.priority == "high" and deterministic.normalized_license is not None:
        return deterministic
    if priority_rank(llm_classification.priority) > priority_rank(deterministic.priority):
        return llm_classification
    if deterministic.normalized_license is None and llm_classification.normalized_license is not None:
        return llm_classification
    return deterministic


def _parse_batch_responses(
    responses: list[LLMBatchResponse],
    task_to_items: dict[str, list[str]],
) -> tuple[dict[str, LLMItemResult], dict[str, str]]:
    results: dict[str, LLMItemResult] = {}
    errors: dict[str, str] = {}
    for response in responses:
        expected_items = set(task_to_items.get(response.task_id, []))
        if response.error:
            for item_id in expected_items:
                errors[item_id] = response.error
            continue
        try:
            payload = json.loads(response.output_text or "{}")
            rows = payload["items"]
            if not isinstance(rows, list):
                raise ValueError("items must be a list")
        except Exception as exc:
            for item_id in expected_items:
                errors[item_id] = f"malformed batch JSON for {response.task_id}: {exc}"
            continue
        seen: set[str] = set()
        for row in rows:
            try:
                item = _item_result_from_row(row)
            except Exception as exc:
                continue
            if item.item_id not in expected_items:
                continue
            results[item.item_id] = item
            seen.add(item.item_id)
        for missing in expected_items - seen:
            errors[missing] = f"missing item result in {response.task_id}"
    return results, errors


def _item_result_from_row(row: object) -> LLMItemResult:
    if not isinstance(row, dict):
        raise ValueError("item must be an object")
    confidence = row.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        raise ValueError("invalid confidence")
    return LLMItemResult(
        item_id=str(row["task_item_id"]),
        detected_license=row.get("detected_license"),
        confidence=confidence,
        evidence=[str(item) for item in row.get("evidence", []) if item],
        is_custom_or_modified=bool(row.get("is_custom_or_modified")),
        needs_review=bool(row.get("needs_review")),
        reason=str(row.get("reason") or ""),
    )


def _license_value(dependency: Dependency) -> str | None:
    if dependency.declared_license:
        return dependency.declared_license
    for evidence in dependency.evidence:
        if evidence.detected_license:
            return evidence.detected_license
    return None


def _has_notice(dependency: Dependency) -> bool:
    return any((evidence.file or "").lower().rsplit("/", maxsplit=1)[-1].startswith("notice") for evidence in dependency.evidence)


def _skip_license_risk(dependency: Dependency) -> bool:
    return dependency.source_type == "metadata" and "local_project" not in dependency.flags


def _dedupe_dependencies(dependencies: Iterable[Dependency]) -> list[Dependency]:
    by_key: dict[tuple[str, str, str | None], Dependency] = {}
    for dependency in dependencies:
        key = (dependency.ecosystem, dependency.name, dependency.version)
        current = by_key.get(key)
        if current is None:
            by_key[key] = dependency
            continue
        current.evidence.extend(dependency.evidence)
        current.flags.extend(flag for flag in dependency.flags if flag not in current.flags)
        if current.declared_license is None and dependency.declared_license:
            current.declared_license = dependency.declared_license
    return list(by_key.values())


def _dedupe_findings(findings: Iterable[Finding]) -> list[Finding]:
    by_id = {finding.id: finding for finding in findings}
    return sorted(by_id.values(), key=lambda finding: finding.id)


def _item_id(dependency: Dependency) -> str:
    return dependency.key.replace("/", "_").replace(":", "_").replace("@", "_")[:180]


def priority_rank(priority: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[priority]


def max_priority(left: str, right: str) -> str:
    return left if priority_rank(left) >= priority_rank(right) else right
