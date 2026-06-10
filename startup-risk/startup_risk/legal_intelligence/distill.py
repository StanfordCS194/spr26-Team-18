from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable

from startup_risk.legal_intelligence.models import LegalAuthority, LegalCitation, LegalGuidanceRule
from startup_risk.llm import get_batch_provider
from startup_risk.scanners.license_scanner.models import LLMTask


_SYSTEM_PROMPT = (
    "You distill legal authorities into scanner-ready compliance guidance. "
    "Use only the provided source text and metadata. Do not invent statutes, cases, "
    "citations, company facts, files, or code evidence. Return only valid JSON."
)


def distill_legal_guidance(
    authorities: Iterable[LegalAuthority],
    *,
    provider: str | None = None,
    model: str | None = None,
    batch_provider=None,
    timeout_seconds: int | None = None,
    poll_interval_seconds: int | None = None,
) -> list[LegalGuidanceRule]:
    """Batch-distill legal authorities into scanner guidance using the shared gateway."""

    authority_list = list(authorities)
    if not authority_list:
        return []

    tasks = [_task_for_authority(authority) for authority in authority_list]
    provider_client = batch_provider or get_batch_provider(
        provider=provider,
        model=model,
        max_batch_requests=int(os.getenv("LEGAL_INTELLIGENCE_MAX_BATCH_REQUESTS", "10000")),
        max_batch_file_bytes=int(os.getenv("LEGAL_INTELLIGENCE_MAX_BATCH_FILE_BYTES", "50000000")),
        max_prompt_tokens=int(os.getenv("LEGAL_INTELLIGENCE_MAX_PROMPT_TOKENS", "200000")),
    )
    responses = provider_client.submit_and_wait(
        tasks,
        timeout_seconds=timeout_seconds or int(os.getenv("LEGAL_INTELLIGENCE_BATCH_TIMEOUT_SECONDS", "86400")),
        poll_interval_seconds=poll_interval_seconds or int(os.getenv("LEGAL_INTELLIGENCE_POLL_INTERVAL_SECONDS", "30")),
    )
    authorities_by_id = {authority.source_id: authority for authority in authority_list}

    rules: list[LegalGuidanceRule] = []
    for response in responses:
        if response.error or not response.output_text:
            continue
        authority_id = response.task_id.removeprefix("legal-guidance-")
        authority = authorities_by_id.get(authority_id)
        if authority is None:
            continue
        rules.extend(_parse_rules(response.output_text, authority))
    return rules


def _task_for_authority(authority: LegalAuthority) -> LLMTask:
    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        "Return this exact JSON shape:\n"
        '{"rules":[{"category":"privacy|financial_compliance|employment_payroll|security_controls|'
        'licensing|consumer_protection|healthcare|ai_data_governance|legal|compliance",'
        '"title":"short scanner guidance title","legal_basis":"source-backed legal obligation",'
        '"risk_signal":"repo or company signal this guidance should influence",'
        '"detection_hints":["short concrete scanner hints"],'
        '"finding_rationale":"one sentence explaining why a matching finding matters",'
        '"recommendation":"short remediation guidance",'
        '"confidence":"low|medium|high"}]}\n\n'
        f"AUTHORITY METADATA:\n{json.dumps(authority.model_dump(mode='json', exclude={'source_text'}), sort_keys=True)}\n\n"
        f"SOURCE TEXT:\n{authority.source_text[:12000]}"
    )
    estimated_tokens = max(1, len(prompt) // 4)
    return LLMTask(
        task_id=f"legal-guidance-{authority.source_id}",
        items=[],
        prompt=prompt,
        estimated_prompt_tokens=estimated_tokens,
        estimated_request_bytes=len(prompt.encode("utf-8")),
    )


def _parse_rules(raw: str, authority: LegalAuthority) -> list[LegalGuidanceRule]:
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        return []
    items = parsed.get("rules") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return []

    citation = LegalCitation(
        title=authority.title,
        citation=authority.citation,
        url=authority.url,
        authority_type=authority.authority_type,
        jurisdiction=authority.jurisdiction,
    )
    if not (citation.citation or citation.url):
        return []
    rules: list[LegalGuidanceRule] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Legal compliance guidance")
        legal_basis = str(item.get("legal_basis") or "")[:1000]
        risk_signal = str(item.get("risk_signal") or "")[:600]
        if not legal_basis or not risk_signal:
            continue
        rule_id = _stable_rule_id(authority.source_id, title, index)
        rules.append(
            LegalGuidanceRule(
                id=rule_id,
                authority_id=authority.source_id,
                category=str(item.get("category") or authority.topic),
                title=title[:160],
                legal_basis=legal_basis,
                risk_signal=risk_signal,
                detection_hints=[
                    str(hint)[:240]
                    for hint in (item.get("detection_hints") or [])
                    if str(hint).strip()
                ][:8],
                finding_rationale=str(item.get("finding_rationale") or legal_basis)[:600],
                recommendation=str(item.get("recommendation") or "Review this issue with counsel.")[:400],
                citations=[citation],
                confidence=str(item.get("confidence") or "low").lower(),
                source_interpretation=True,
                source_hash=authority.content_hash,
                industry_tags=[
                    str(tag).lower()
                    for tag in authority.metadata.get("industry_tags", [])
                    if str(tag).strip()
                ],
                scanner_categories=[
                    str(item.get("category") or authority.topic).strip().lower().replace("-", "_").replace(" ", "_")
                ],
            )
        )
    return rules


def _stable_rule_id(authority_id: str, title: str, index: int) -> str:
    digest = hashlib.sha256(f"{authority_id}:{title}:{index}".encode("utf-8")).hexdigest()[:12]
    return f"legal_guidance.{digest}"
