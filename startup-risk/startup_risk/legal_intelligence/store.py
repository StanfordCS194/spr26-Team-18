from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from startup_risk.legal_intelligence.ingest import normalize_authority
from startup_risk.legal_intelligence.models import LegalAuthority, LegalGuidanceRule, LegalSourceQuery


class LegalIntelligenceStore:
    """JSONL-backed store for normalized authorities and distilled guidance."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.authorities_path = self.root / "authorities.jsonl"
        self.rules_path = self.root / "guidance_rules.jsonl"
        self.sources_path = self.root / "source_queries.jsonl"

    def load_authorities(self) -> list[LegalAuthority]:
        return [
            normalize_authority(row)
            for row in self._read_jsonl(self.authorities_path)
        ]

    def save_authorities(self, authorities: list[LegalAuthority]) -> None:
        self._write_jsonl(self.authorities_path, [item.model_dump(mode="json") for item in authorities])

    def append_authorities(self, authorities: list[LegalAuthority]) -> None:
        self.upsert_authorities(authorities)

    def upsert_authorities(self, authorities: list[LegalAuthority]) -> list[LegalAuthority]:
        """Merge authorities and return records whose content is new or changed."""
        now = datetime.now(timezone.utc)
        existing = {authority.source_id: authority for authority in self.load_authorities()}
        changed: list[LegalAuthority] = []
        for authority in authorities:
            content_hash = authority.content_hash or _authority_hash(authority)
            old = existing.get(authority.source_id)
            first_seen = old.first_seen if old else now
            merged = authority.model_copy(
                update={
                    "content_hash": content_hash,
                    "first_seen": first_seen,
                    "last_seen": now,
                    "last_checked": now,
                }
            )
            if old is None or old.content_hash != content_hash:
                changed.append(merged)
            existing[authority.source_id] = authority
            existing[authority.source_id] = merged
        self.save_authorities(sorted(existing.values(), key=lambda item: item.source_id))
        return changed

    def load_rules(self) -> list[LegalGuidanceRule]:
        return [
            LegalGuidanceRule.model_validate(row)
            for row in self._read_jsonl(self.rules_path)
        ]

    def save_rules(self, rules: list[LegalGuidanceRule]) -> None:
        self._write_jsonl(self.rules_path, [item.model_dump(mode="json") for item in rules])

    def append_rules(self, rules: list[LegalGuidanceRule]) -> None:
        existing = {rule.id: rule for rule in self.load_rules()}
        for rule in rules:
            existing[rule.id] = rule
        self.save_rules(sorted(existing.values(), key=lambda item: item.id))

    def update_rule(self, rule_id: str, **updates) -> LegalGuidanceRule:
        rules = self.load_rules()
        for index, rule in enumerate(rules):
            if rule.id == rule_id:
                updated = rule.model_copy(update=updates)
                rules[index] = updated
                self.save_rules(sorted(rules, key=lambda item: item.id))
                return updated
        raise KeyError(rule_id)

    def load_source_queries(self) -> list[LegalSourceQuery]:
        return [
            LegalSourceQuery.model_validate(row)
            for row in self._read_jsonl(self.sources_path)
        ]

    def save_source_queries(self, queries: list[LegalSourceQuery]) -> None:
        self._write_jsonl(self.sources_path, [item.model_dump(mode="json") for item in queries])

    def append_source_query(self, query: LegalSourceQuery) -> None:
        existing = {item.id: item for item in self.load_source_queries()}
        existing[query.id] = query
        self.save_source_queries(sorted(existing.values(), key=lambda item: item.id))

    def status(self) -> dict:
        authorities = self.load_authorities()
        rules = self.load_rules()
        queries = self.load_source_queries()
        checked = [item.last_checked for item in queries if item.last_checked]
        return {
            "authority_count": len(authorities),
            "rule_count": len(rules),
            "enabled_rule_count": sum(1 for rule in rules if rule.enabled and rule.review_status != "rejected"),
            "source_count": len(queries),
            "last_checked": max(checked).isoformat() if checked else None,
            "rules_path": str(self.rules_path),
            "authorities_path": str(self.authorities_path),
            "sources_path": str(self.sources_path),
        }

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        path.write_text(content, encoding="utf-8")


def _authority_hash(authority: LegalAuthority) -> str:
    payload = authority.model_dump(mode="json", exclude={"first_seen", "last_seen", "last_checked", "content_hash"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
