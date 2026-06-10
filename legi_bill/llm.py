from __future__ import annotations

import sys
from pathlib import Path


STARTUP_RISK_ROOT = Path(__file__).resolve().parents[1] / "startup-risk"
if str(STARTUP_RISK_ROOT) not in sys.path:
    sys.path.insert(0, str(STARTUP_RISK_ROOT))

from startup_risk.llm import (  # noqa: E402
    ChatClient,
    ChatResponse,
    LLMConfigError,
    LLMProviderCapabilityError,
    get_chat_client,
    load_llm_config,
)

__all__ = [
    "ChatClient",
    "ChatResponse",
    "LLMConfigError",
    "LLMProviderCapabilityError",
    "get_chat_client",
    "load_llm_config",
]
