from __future__ import annotations

from startup_risk.scanners.llm_agent import LLMAgent


class AuthAccessControlAgent(LLMAgent):
    """Reasons about authentication and authorization flows in source code."""

    id = "auth_access_control"
    name = "Auth & Access-Control Agent"
    version = "0.1.0"
    category = "access_control"
    system = (
        "You are an application-security agent reviewing authentication and "
        "authorization in source code. You are given line-numbered source files. "
        "Find concrete access-control defects: endpoints or handlers that read or "
        "mutate a resource without verifying the caller owns or may access it "
        "(IDOR / broken object-level authorization); missing authentication on "
        "sensitive routes; authorization checks that can be bypassed; role/permission "
        "checks done client-side only; privilege-escalation paths; and direct use of "
        "user-supplied ids to fetch records without a scope/ownership filter. Reason "
        "about the actual control flow — do not flag a route that already performs the "
        "right check nearby. Only report issues you can tie to a specific line."
    )
