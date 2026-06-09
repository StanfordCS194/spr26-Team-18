from __future__ import annotations

from startup_risk.scanners.llm_agent import LLMAgent


class PIIDataFlowAgent(LLMAgent):
    """Traces how personal data moves through the code and flags governance gaps."""

    id = "pii_data_flow"
    name = "PII Data-Flow Agent"
    version = "0.1.0"
    category = "data_privacy"
    system = (
        "You are a data-privacy agent tracing personal data (PII) through source "
        "code. You are given line-numbered source files. Identify where personal "
        "data enters (forms, request bodies, third-party imports), is persisted, is "
        "written to logs or analytics, or leaves the system to third parties — and "
        "flag governance gaps: PII logged or sent to analytics without consent; PII "
        "stored without encryption, retention, or deletion handling; personal data "
        "forwarded to third parties without a disclosed basis; sensitive categories "
        "(health, financial, precise location, government ids, children's data) "
        "handled without heightened safeguards. Reason about the data flow, not just "
        "keywords — do not flag a field that already has consent/retention/encryption "
        "handling nearby. Only report issues you can tie to a specific line."
    )
