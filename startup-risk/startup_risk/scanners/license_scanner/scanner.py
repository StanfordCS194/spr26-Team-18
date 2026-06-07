from __future__ import annotations

import json
import os
import re
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
from startup_risk.scanners.license_scanner.parsers import dotnet, generic, go, java, npm, php, python, ruby, rust
from startup_risk.scanners.license_scanner.registry_metadata import RegistryMetadataError, fetch_registry_metadata
from startup_risk.scanners.license_scanner.reporting import (
    SCANNER_ID,
    SCANNER_VERSION,
    classification_for_unknown_license,
    finding_for_flag,
    finding_for_license,
    finding_for_skipped,
)
from startup_risk.scanners.license_scanner.safe_artifacts import (
    UnsafeArtifactError,
    download_artifact,
    iter_likely_license_texts,
    safe_extract_archive,
)
from startup_risk.scanners.license_scanner.source_repo import SourceRepoError, fetch_source_repo_license_evidence
from startup_risk.scanners.license_scanner.licenses import detect_license_from_text


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
        enable_registry_metadata: bool = False,
        enable_artifact_inspection: bool = False,
        enable_source_repo: bool = False,
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
        self.enable_registry_metadata = enable_registry_metadata
        self.enable_artifact_inspection = enable_artifact_inspection
        self.enable_source_repo = enable_source_repo

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        provider = self.batch_provider
        if not self.deterministic_only and provider is None:
            provider = provider_from_env(self.provider_name)

        discovered = discover(snapshot)
        dependencies = self._parse_dependencies(discovered.manifests, discovered.vendored_files)
        dependencies = _dedupe_dependencies(dependencies)
        _mark_self_dependencies(dependencies)
        registry_skipped = self._enrich_registry_metadata(dependencies) if self.enable_registry_metadata else []
        artifact_skipped = self._enrich_artifacts(dependencies) if self.enable_artifact_inspection else []
        source_skipped = self._enrich_source_repos(dependencies) if self.enable_source_repo else []

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
        for skipped in registry_skipped:
            findings.append(finding_for_skipped(skipped))
        for skipped in artifact_skipped:
            findings.append(finding_for_skipped(skipped))
        for skipped in source_skipped:
            findings.append(finding_for_skipped(skipped))
        for dependency in dependencies:
            for flag in dependency.flags:
                if (
                    flag.startswith("vendored_root:")
                    or flag.startswith("dependency_scope:")
                    or flag.startswith("artifact_url:")
                    or flag.startswith("integrity:")
                    or flag.startswith("source_repo:")
                    or flag in {"local_project", "self_dependency", "vendored_license_metadata_present"}
                ):
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

    def _enrich_registry_metadata(self, dependencies: list[Dependency]) -> list[str]:
        skipped: list[str] = []
        for dependency in dependencies:
            if _skip_license_risk(dependency) or _license_value(dependency):
                continue
            try:
                metadata = fetch_registry_metadata(dependency)
            except RegistryMetadataError as exc:
                skipped.append(f"{dependency.ecosystem}:{dependency.name}: registry metadata lookup failed: {exc}")
                continue
            if metadata.evidence is not None:
                dependency.evidence.append(metadata.evidence)
                dependency.declared_license = metadata.evidence.detected_license
            if metadata.artifact_url and not _flag_value(dependency, "artifact_url"):
                dependency.flags.append(f"artifact_url:{metadata.artifact_url}")
            if metadata.source_repo_url and not _flag_value(dependency, "source_repo"):
                dependency.flags.append(f"source_repo:{metadata.source_repo_url}")
        return skipped

    def _enrich_artifacts(self, dependencies: list[Dependency]) -> list[str]:
        skipped: list[str] = []
        for dependency in dependencies:
            if _skip_license_risk(dependency) or _license_value(dependency):
                continue
            artifact_url = _flag_value(dependency, "artifact_url")
            if not artifact_url:
                continue
            try:
                archive = download_artifact(artifact_url, integrity=_flag_value(dependency, "integrity"))
                extracted = safe_extract_archive(archive)
                for path, text in iter_likely_license_texts(extracted):
                    detected = detect_license_from_text(text)
                    if detected or text.strip():
                        evidence = LicenseEvidence(
                            source="package_artifact",
                            file=path,
                            line=1,
                            text=text[:8000],
                            detected_license=detected,
                            confidence="medium" if detected else "low",
                        )
                        dependency.evidence.append(evidence)
                        if detected:
                            dependency.declared_license = detected
                            break
            except UnsafeArtifactError as exc:
                skipped.append(f"{dependency.ecosystem}:{dependency.name}: artifact inspection skipped: {exc}")
            except Exception as exc:
                skipped.append(f"{dependency.ecosystem}:{dependency.name}: artifact inspection failed: {exc}")
        return skipped

    def _enrich_source_repos(self, dependencies: list[Dependency]) -> list[str]:
        skipped: list[str] = []
        for dependency in dependencies:
            if _skip_license_risk(dependency) or _license_value(dependency):
                continue
            source_repo = _flag_value(dependency, "source_repo")
            if not source_repo:
                continue
            try:
                evidence = fetch_source_repo_license_evidence(source_repo)
            except SourceRepoError as exc:
                skipped.append(f"{dependency.ecosystem}:{dependency.name}: source repo lookup failed: {exc}")
                continue
            if evidence is not None:
                dependency.evidence.append(evidence)
                if evidence.detected_license:
                    dependency.declared_license = evidence.detected_license
        return skipped

    def _parse_dependencies(self, manifests, vendored_files) -> list[Dependency]:
        dependencies: list[Dependency] = []
        for file in manifests:
            dependencies.extend(npm.parse(file))
            dependencies.extend(python.parse(file))
            dependencies.extend(rust.parse(file))
            dependencies.extend(go.parse(file))
            dependencies.extend(java.parse(file))
            dependencies.extend(ruby.parse(file))
            dependencies.extend(php.parse(file))
            dependencies.extend(dotnet.parse(file))
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
            if _needs_llm_review(dependency)
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
    deterministic = _deterministic_classification(dependency, deterministic_only=deterministic_only)
    if llm_error or llm_result is None:
        return deterministic
    llm_license = normalize_license(llm_result.detected_license)
    confidence = llm_result.confidence
    if llm_license is None:
        unknown = classification_for_unknown_license(dependency, deterministic_only=deterministic_only)
        return replace(
            unknown,
            confidence="low" if llm_result.confidence == "low" else unknown.confidence,
            explanation="The scanner and LLM review could not establish a license from the available local evidence.",
            source="llm",
        )
    if confidence == "high" and not is_known_spdx_like(llm_license):
        confidence = "medium"
    llm_classification = classify_license(
        llm_license,
        has_notice=_has_notice(dependency),
        source="llm",
        content_data_context=_is_content_data_dependency(dependency),
    )
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


def _deterministic_classification(dependency: Dependency, *, deterministic_only: bool) -> LicenseClassification:
    license_value = _license_value(dependency)
    if license_value is None:
        return classification_for_unknown_license(dependency, deterministic_only=deterministic_only)
    return classify_license(
        license_value,
        has_notice=_has_notice(dependency),
        content_data_context=_is_content_data_dependency(dependency),
    )


def _has_notice(dependency: Dependency) -> bool:
    if "vendored_license_metadata_present" in dependency.flags:
        return True
    notice_or_metadata_files = {
        "cargo.lock",
        "cargo.toml",
        "composer.json",
        "package-lock.json",
        "package.json",
        "pyproject.toml",
        "readme.chromium",
    }
    for evidence in dependency.evidence:
        filename = (evidence.file or "").lower().rsplit("/", maxsplit=1)[-1]
        if filename.startswith(("notice", "license", "copying")) or filename in notice_or_metadata_files:
            return True
        if evidence.source in {"lockfile", "local_manifest", "registry_metadata", "package_artifact", "source_repo"}:
            return True
    return False


def _skip_license_risk(dependency: Dependency) -> bool:
    if "self_dependency" in dependency.flags or "local_project" in dependency.flags:
        return True
    return dependency.source_type == "metadata"


def _needs_llm_review(dependency: Dependency) -> bool:
    if _skip_license_risk(dependency):
        return False
    classification = _deterministic_classification(dependency, deterministic_only=False)
    return classification.normalized_license is None or classification.priority != "low"


def _is_content_data_dependency(dependency: Dependency) -> bool:
    text = " ".join(
        [
            dependency.name,
            dependency.source_file or "",
            *[evidence.text or "" for evidence in dependency.evidence[:3]],
        ]
    ).lower()
    indicators = (
        "browser",
        "browserslist",
        "caniuse",
        "compat",
        "data",
        "dataset",
        "docs",
        "documentation",
        "mdn",
        "metadata",
        "spdx",
        "webidl",
    )
    return any(indicator in text for indicator in indicators)


def _flag_value(dependency: Dependency, prefix: str) -> str | None:
    marker = prefix + ":"
    for flag in dependency.flags:
        if flag.startswith(marker):
            return flag.removeprefix(marker)
    return None


def _mark_self_dependencies(dependencies: list[Dependency]) -> None:
    local_names_by_ecosystem: dict[str, set[str]] = {}
    for dependency in dependencies:
        if "local_project" not in dependency.flags:
            continue
        local_names_by_ecosystem.setdefault(dependency.ecosystem, set()).add(_normalize_package_name(dependency.name))

    for dependency in dependencies:
        if "local_project" in dependency.flags:
            continue
        local_names = local_names_by_ecosystem.get(dependency.ecosystem, set())
        if _normalize_package_name(dependency.name) in local_names and "self_dependency" not in dependency.flags:
            dependency.flags.append("self_dependency")


def _normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


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
    return _merge_npm_manifest_specs_into_lockfile(list(by_key.values()))


def _merge_npm_manifest_specs_into_lockfile(dependencies: list[Dependency]) -> list[Dependency]:
    lockfile_by_name: dict[str, list[Dependency]] = {}
    for dependency in dependencies:
        if dependency.ecosystem == "npm" and dependency.source_type == "lockfile":
            lockfile_by_name.setdefault(_normalize_package_name(dependency.name), []).append(dependency)

    merged: list[Dependency] = []
    for dependency in dependencies:
        if dependency.ecosystem != "npm" or dependency.source_type != "manifest":
            merged.append(dependency)
            continue
        lockfile_matches = lockfile_by_name.get(_normalize_package_name(dependency.name), [])
        if len(lockfile_matches) != 1:
            merged.append(dependency)
            continue
        target = lockfile_matches[0]
        target.evidence.extend(dependency.evidence)
        target.flags.extend(flag for flag in dependency.flags if flag not in target.flags)
        if target.declared_license is None and dependency.declared_license:
            target.declared_license = dependency.declared_license
    return merged


def _dedupe_findings(findings: Iterable[Finding]) -> list[Finding]:
    by_id = {finding.id: finding for finding in findings}
    return sorted(by_id.values(), key=lambda finding: finding.id)


def _item_id(dependency: Dependency) -> str:
    return dependency.key.replace("/", "_").replace(":", "_").replace("@", "_")[:180]


def priority_rank(priority: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}[priority]


def max_priority(left: str, right: str) -> str:
    return left if priority_rank(left) >= priority_rank(right) else right
