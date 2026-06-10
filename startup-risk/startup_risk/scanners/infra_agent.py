from __future__ import annotations

from startup_risk.scanners.llm_agent import LLMAgent

_INFRA_EXTENSIONS = frozenset({".yml", ".yaml", ".tf", ".toml", ".json", ".sh", ".conf", ".ini", ".env"})

# Extensionless / specially-named infra files matched by filename.
_INFRA_FILENAMES = frozenset({
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "procfile", "makefile", ".env", "nginx.conf",
})
_INFRA_NAME_HINTS = ("dockerfile", "docker-compose", "k8s", "kubernetes", "terraform", "helm")


class InfraMisconfigAgent(LLMAgent):
    """Reviews infrastructure-as-code and config for security misconfigurations."""

    id = "infra_misconfig"
    name = "Infra / IaC Misconfig Agent"
    version = "0.1.0"
    category = "infrastructure"
    extensions = _INFRA_EXTENSIONS
    system = (
        "You are an infrastructure-security agent reviewing infrastructure-as-code "
        "and configuration (Dockerfiles, docker-compose, Kubernetes manifests, "
        "Terraform, CI workflows, nginx, env/config files). You are given "
        "line-numbered files. Find concrete misconfigurations: containers running as "
        "root or with privileged/elevated capabilities; secrets or credentials baked "
        "into images or committed config; overly permissive CORS or network exposure "
        "(0.0.0.0, public buckets, open security groups, exposed admin ports); "
        "disabled TLS/cert verification; missing resource limits; latest/untagged "
        "image pins; and debug/insecure flags enabled in production config. Reason "
        "about the actual setting — do not flag a value that is already locked down. "
        "Only report issues you can tie to a specific line."
    )

    def _is_eligible(self, file) -> bool:
        if file.text is None:
            return False
        name = file.path.lower().split("/")[-1]
        if name in _INFRA_FILENAMES or any(h in file.path.lower() for h in _INFRA_NAME_HINTS):
            return True
        return file.extension in self.extensions
