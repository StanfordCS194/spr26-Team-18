"""
AI Governance Scanner
=====================
Static checks for AI/ML regulatory compliance signals. Targets the EU AI Act
(2024/1689), NIST AI RMF, and emerging US state AI bills.

Seven checks, grouped into two tiers:

  Repo-level (fire at most once per scan):
    1. No model card — AI model shipped without documentation of intended use,
       limitations, and known biases.
    2. No bias / fairness testing — ML evaluation code with no fairness metrics.
    3. No AI transparency disclosure — public-facing AI features with no
       disclosure that the user is interacting with or being affected by AI.

  Per-file (can fire multiple times):
    4. Automated decision without human override — high-stakes decisions
       (credit, hiring, medical, content moderation) applied programmatically
       with no human-review or appeal path visible in context.
    5. Model inference without confidence thresholding — predictions acted on
       directly without checking a confidence / probability score.
    6. Training data without provenance — dataset loading with no source,
       license, or copyright attribution in context.
    7. No AI inference audit log — LLM / ML inference calls with no structured
       logging of inputs and outputs for audit purposes.
"""
from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    FileSnapshot,
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    Severity,
    SourceLocation,
)

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------

_SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".java", ".go",
    ".cs", ".php", ".kt", ".rs", ".scala", ".ipynb",
})
_CONFIG_EXTENSIONS = frozenset({".yml", ".yaml", ".json", ".toml"})
_DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt"})

_CONTEXT_RADIUS = 8  # lines above/below a trigger line included as evidence

# ---------------------------------------------------------------------------
# Repo-level patterns
# ---------------------------------------------------------------------------

# Signals that an AI/ML model is present in the repo
_MODEL_PRESENCE_PATTERN = re.compile(
    r"""
    (?:
        # Python: loading or defining a model
        (?:model\s*=\s*)?(?:load_model|from_pretrained|AutoModel|AutoTokenizer
            |Pipeline|joblib\.load|pickle\.load|torch\.load|tf\.keras\.models\.load)
        # Generic: model files
        | \.(pt|pth|onnx|pkl|h5|safetensors|bin)\b
        # LLM API calls
        | openai\.(?:ChatCompletion|Completion|chat\.completions)
        | anthropic\.(?:Anthropic|messages\.create)
        | (?:bedrock|vertex_ai|genai)
        | LangChain|LlamaIndex|haystack
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Model-card documents at repo level
_MODEL_CARD_PATHS = re.compile(
    r"(?:^|/)(?:model.?card|model.?doc|about.?model|system.?card|model.?sheet)s?(?:\.\w+)?$",
    re.IGNORECASE,
)

# Fairness / bias testing frameworks and metrics
_FAIRNESS_PATTERN = re.compile(
    r"\b(?:fairlearn|aif360|responsibleai|themis.?ml|fairness.?indicator"
    r"|demographic.?parity|equal.?opportunit|disparate.?impact|equalized.?odds"
    r"|bias.?test|fairness.?metric|protected.?attribute|sensitive.?feature"
    r"|audit.?model|model.?audit)\b",
    re.IGNORECASE,
)

# Public-facing AI disclosure text
_AI_DISCLOSURE_PATTERN = re.compile(
    r"\b(?:powered.?by.?ai|generated.?by.?ai|ai.?generated|this.?is.?an.?ai"
    r"|you.?are.?chatting.?with.?an.?ai|automated.?decision|ai.?assistant"
    r"|chatbot.?disclosure|bot.?disclosure|not.?a.?human|ai.?may.?make.?mistakes"
    r"|results.?generated.?by|ai.?driven.?recommendation)\b",
    re.IGNORECASE,
)

# User-facing chat / recommendation / UI rendering patterns
_PUBLIC_AI_FEATURE_PATTERN = re.compile(
    r"""(?:
        # Chat or response rendering
        (?:chat|message|reply|response|output|result|answer)
            \s*[=:+\.]\s*
            (?:await\s+)?
            (?:openai|anthropic|bedrock|genai|llm|model|chain|agent|pipeline|client)
            [\.\(]
        # Recommendation display
        | render.*(?:recommendation|suggestion|prediction|score)
        | (?:recommendation|suggestion|prediction).*(?:display|render|show|present|return)
        # Returning AI output directly to user
        | return\s+.*(?:completion|generated_text|choices\[|\.content|\.text)
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# ---------------------------------------------------------------------------
# Per-file patterns
# ---------------------------------------------------------------------------

# High-stakes automated-decision trigger words
_HIGH_STAKES_DECISION_PATTERN = re.compile(
    r"\b(?:credit.?score|loan.?approv|hiring.?decision|resume.?screen"
    r"|employ(?:ment)?.?decision|background.?check|insurance.?approv"
    r"|fraud.?decision|content.?moderat|account.?suspend|ban.?user"
    r"|medical.?diagnosis|medical.?decision|treatment.?recommend"
    r"|risk.?score|eligibilit)\b",
    re.IGNORECASE,
)

# Human-review / appeal / override patterns
_HUMAN_OVERRIDE_PATTERN = re.compile(
    r"\b(?:human.?review|manual.?review|human.?in.?the.?loop|hitl"
    r"|appeal|dispute|override|escalat|reviewer|flag.?for.?review"
    r"|require.?approval|pending.?review|supervisor|second.?opinion)\b",
    re.IGNORECASE,
)

# Model inference / prediction calls
_INFERENCE_CALL_PATTERN = re.compile(
    r"""(?:
        \.predict(?:_proba)?\s*\(
        | \.generate\s*\(
        | \.forward\s*\(
        | model\s*\(\s*(?:input|x|data|tensor|prompt)
        | (?:chat\.completions|ChatCompletion)\.create
        | messages\.create\s*\(
        | pipeline\s*\(
        | \.run\s*\(\s*(?:input|query|question|prompt)
        | inference\s*\(
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Confidence / probability thresholding
_CONFIDENCE_PATTERN = re.compile(
    r"\b(?:confidence|probability|proba|score|threshold|min_confidence"
    r"|predict_proba|softmax|logit|certainty|reliability)\b",
    re.IGNORECASE,
)

# Dataset / training data loading
_DATASET_LOAD_PATTERN = re.compile(
    r"""(?:
        load_dataset\s*\(
        | datasets\.load
        | pd\.read_(?:csv|parquet|json|feather)\s*\(
        | spark\.read
        | tf\.data\.Dataset
        | torch\.utils\.data
        | DataLoader\s*\(
        | open\s*\([^)]*\.(?:csv|tsv|parquet|jsonl)
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Data provenance / license attribution
_PROVENANCE_PATTERN = re.compile(
    r"\b(?:license|citation|source|provenance|attribution|doi|huggingface\.co"
    r"|kaggle\.com|data.?card|dataset.?card|terms.?of.?use|copyright)\b",
    re.IGNORECASE,
)

# LLM / ML inference log patterns
_INFERENCE_LOG_PATTERN = re.compile(
    r"""(?:
        (?:logger?|log|logging)\.(?:info|debug|warning|error)\s*\(
        | console\.log\s*\(
        | print\s*\(
        | structlog\|loguru
        | datadog\.statsd
        | cloudwatch
        | (?:audit|trace|span)\.(?:log|record|emit|add_event)
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def _context(lines: list[str], index: int, radius: int = _CONTEXT_RADIUS) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class AIGovernanceScanner:
    """
    Static checks for AI/ML governance and regulatory compliance signals.

    Targets the EU AI Act (2024/1689), NIST AI RMF, and US state AI bills.
    All checks are purely regex-based — no AST, no LLM calls.
    """

    id = "ai_governance"
    name = "AI Governance"
    version = "1.0.0"

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []

        # Determine whether the repo contains AI/ML model usage at all
        model_files = self._collect_model_files(snapshot)
        if not model_files:
            return []  # non-AI repo — no findings applicable

        # Repo-level checks
        if not self._repo_has_model_card(snapshot):
            findings.append(self._no_model_card_finding(model_files))

        if not self._repo_has_fairness_tests(snapshot):
            findings.append(self._no_fairness_testing_finding(model_files))

        if self._repo_has_public_ai_features(snapshot) and not self._repo_has_disclosure(snapshot):
            findings.append(self._no_disclosure_finding(snapshot))

        # Per-file checks
        for file in snapshot.files:
            if file.text is None or file.extension not in _SOURCE_EXTENSIONS:
                continue
            findings.extend(self._check_automated_decision_no_override(file))
            findings.extend(self._check_inference_no_confidence(file))
            findings.extend(self._check_dataset_no_provenance(file))
            findings.extend(self._check_inference_no_audit_log(file))

        return findings

    # ------------------------------------------------------------------
    # Repo-level helpers
    # ------------------------------------------------------------------

    def _collect_model_files(self, snapshot: RepositorySnapshot) -> list[tuple[str, int]]:
        """Return (path, line_no) for each file with AI/ML model usage."""
        hits: list[tuple[str, int]] = []
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.extension not in _SOURCE_EXTENSIONS | _CONFIG_EXTENSIONS:
                continue
            for line_no, line in enumerate(file.text.splitlines(), 1):
                if _MODEL_PRESENCE_PATTERN.search(line):
                    hits.append((file.path, line_no))
                    break
        return hits

    def _repo_has_model_card(self, snapshot: RepositorySnapshot) -> bool:
        for file in snapshot.files:
            if _MODEL_CARD_PATHS.search(file.path):
                return True
            if file.extension in _DOC_EXTENSIONS and file.text:
                low = file.text[:2000].lower()
                if "model card" in low or "system card" in low or "model sheet" in low:
                    return True
        return False

    def _repo_has_fairness_tests(self, snapshot: RepositorySnapshot) -> bool:
        return any(
            file.text and _FAIRNESS_PATTERN.search(file.text)
            for file in snapshot.files
            if file.extension in _SOURCE_EXTENSIONS | _CONFIG_EXTENSIONS
        )

    def _repo_has_public_ai_features(self, snapshot: RepositorySnapshot) -> bool:
        return any(
            file.text and _PUBLIC_AI_FEATURE_PATTERN.search(file.text)
            for file in snapshot.files
            if file.extension in _SOURCE_EXTENSIONS
        )

    def _repo_has_disclosure(self, snapshot: RepositorySnapshot) -> bool:
        return any(
            file.text and _AI_DISCLOSURE_PATTERN.search(file.text)
            for file in snapshot.files
        )

    # ------------------------------------------------------------------
    # Repo-level findings
    # ------------------------------------------------------------------

    def _no_model_card_finding(self, model_files: list[tuple[str, int]]) -> Finding:
        capped = model_files[:4]
        seed = "|".join(sorted(f"{p}:{n}" for p, n in capped))
        evidence = [
            FindingEvidence(
                location=SourceLocation(path=path, line_start=line_no, line_end=line_no),
                description="AI/ML model usage detected here.",
            )
            for path, line_no in capped
        ]
        return Finding(
            id=stable_finding_id(self.id, "no_model_card", seed),
            title="AI model deployed without a model card",
            description=(
                "The repository loads or calls AI/ML models but contains no model card, "
                "system card, or equivalent documentation describing the model's intended "
                "use, known limitations, training data, and bias evaluations. "
                "EU AI Act Art. 11 requires technical documentation for high-risk AI systems; "
                "NIST AI RMF GOVERN 1.1 requires similar transparency for all AI systems."
            ),
            category="ai_governance",
            severity="low",
            confidence="medium",
            evidence=evidence,
            recommendation=(
                "Create a MODEL_CARD.md at the repo root documenting: intended use, "
                "out-of-scope uses, training data sources and licenses, evaluation results "
                "(including fairness metrics), and known limitations."
            ),
            scanner_id=self.id,
            scanner_version=self.version,
        )

    def _no_fairness_testing_finding(self, model_files: list[tuple[str, int]]) -> Finding:
        capped = model_files[:3]
        seed = "fairness|" + "|".join(sorted(p for p, _ in capped))
        evidence = [
            FindingEvidence(
                location=SourceLocation(path=path, line_start=line_no, line_end=line_no),
                description="ML model usage detected — no fairness evaluation found in the repository.",
            )
            for path, line_no in capped
        ]
        return Finding(
            id=stable_finding_id(self.id, "no_fairness_testing", seed),
            title="ML model used without bias or fairness evaluation",
            description=(
                "The repository uses machine learning models but contains no detectable "
                "fairness metrics, bias testing libraries (fairlearn, AIF360, Responsible AI), "
                "or protected-attribute evaluation. Undetected bias in model outputs can "
                "create discriminatory outcomes and violates EU AI Act Art. 9 (risk management), "
                "US Equal Credit Opportunity Act (ECOA), and FTC guidance on algorithmic bias."
            ),
            category="ai_governance",
            severity="low",
            confidence="low",
            evidence=evidence,
            recommendation=(
                "Add bias evaluation using a library such as fairlearn or AIF360 before "
                "production deployment. Measure demographic parity, equalized odds, and "
                "disparate impact across protected groups (age, gender, race, disability)."
            ),
            scanner_id=self.id,
            scanner_version=self.version,
        )

    def _no_disclosure_finding(self, snapshot: RepositorySnapshot) -> Finding:
        hits = [
            (file.path, line_no)
            for file in snapshot.files
            if file.text and file.extension in _SOURCE_EXTENSIONS
            for line_no, line in enumerate(file.text.splitlines(), 1)
            if _PUBLIC_AI_FEATURE_PATTERN.search(line)
        ][:4]
        seed = "disclosure|" + "|".join(sorted(f"{p}:{n}" for p, n in hits))
        evidence = [
            FindingEvidence(
                location=SourceLocation(path=path, line_start=line_no, line_end=line_no),
                description="AI-generated output returned to user with no disclosure found.",
            )
            for path, line_no in hits
        ]
        return Finding(
            id=stable_finding_id(self.id, "no_ai_disclosure", seed),
            title="AI-generated content shown to users without disclosure",
            description=(
                "The repository renders AI-generated content or recommendations to end users "
                "but contains no disclosure that AI is involved. EU AI Act Art. 50 requires "
                "that users be informed when interacting with an AI system. The FTC Act §5 "
                "prohibits deceptive practices, which includes hiding AI involvement in "
                "consumer-facing decisions or communications."
            ),
            category="ai_governance",
            severity="low",
            confidence="low",
            evidence=evidence,
            recommendation=(
                "Add a visible disclosure wherever AI-generated content is presented — "
                "e.g., 'Generated by AI', 'AI-assisted recommendation', or a persistent "
                "chatbot indicator. For automated decision-making, disclose that AI was "
                "used and provide a means to request human review."
            ),
            scanner_id=self.id,
            scanner_version=self.version,
        )

    # ------------------------------------------------------------------
    # Per-file checks
    # ------------------------------------------------------------------

    def _check_automated_decision_no_override(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]
        seen_seeds: set[str] = set()

        for i, line in enumerate(lines):
            if not _HIGH_STAKES_DECISION_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _HUMAN_OVERRIDE_PATTERN.search(ctx):
                continue
            seed = f"{file.path}:{i}"
            if seed in seen_seeds:
                continue
            seen_seeds.add(seed)
            findings.append(Finding(
                id=stable_finding_id(self.id, "automated_decision_no_override", seed),
                title="High-stakes automated decision without human-override path",
                description=(
                    "Code makes or applies an automated decision in a high-risk domain "
                    "(credit, hiring, medical, fraud, content moderation) with no visible "
                    "human-review, appeal, or override mechanism in the surrounding context. "
                    "EU AI Act Art. 14 mandates human oversight for high-risk AI systems. "
                    "US FCRA and ECOA require adverse-action notices and the right to dispute."
                ),
                category="ai_governance",
                severity="low",
                confidence="medium",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    snippet=ctx,
                    description="High-stakes decision with no human-review or appeal path detected.",
                )],
                recommendation=(
                    "Add a human-review queue or appeal endpoint for consequential AI decisions. "
                    "Log the model inputs, outputs, and confidence score with each decision. "
                    "Provide users with an adverse-action notice and the ability to request "
                    "a human reviewer."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    def _check_inference_no_confidence(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]
        seen_seeds: set[str] = set()

        for i, line in enumerate(lines):
            if not _INFERENCE_CALL_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _CONFIDENCE_PATTERN.search(ctx):
                continue
            seed = f"{file.path}:{i}"
            if seed in seen_seeds:
                continue
            seen_seeds.add(seed)
            findings.append(Finding(
                id=stable_finding_id(self.id, "inference_no_confidence_threshold", seed),
                title="Model inference result applied without confidence thresholding",
                description=(
                    "A model prediction or generation is used directly without checking a "
                    "confidence score, probability, or reliability threshold. Acting on "
                    "low-confidence outputs without a fallback can cause silent errors "
                    "in production. NIST AI RMF MEASURE 2.5 requires tracking model "
                    "confidence and uncertainty."
                ),
                category="ai_governance",
                severity="low",
                confidence="low",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    snippet=ctx,
                    description="Inference call with no confidence check in surrounding context.",
                )],
                recommendation=(
                    "Check the model's confidence or probability score before acting on its "
                    "output. For classification, apply a minimum-confidence threshold and "
                    "route uncertain predictions to a human or a fallback. For generative "
                    "models, use temperature or logprobs to detect low-certainty outputs."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    def _check_dataset_no_provenance(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]
        seen_seeds: set[str] = set()

        for i, line in enumerate(lines):
            if not _DATASET_LOAD_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _PROVENANCE_PATTERN.search(ctx):
                continue
            seed = f"{file.path}:{i}"
            if seed in seen_seeds:
                continue
            seen_seeds.add(seed)
            findings.append(Finding(
                id=stable_finding_id(self.id, "dataset_no_provenance", seed),
                title="Training dataset loaded without license or provenance attribution",
                description=(
                    "A dataset is loaded for training or evaluation with no visible source, "
                    "license, or attribution in the surrounding code or comments. Using "
                    "unlicensed or improperly attributed training data creates copyright "
                    "liability and may violate EU AI Act Art. 10 (data governance) and "
                    "NIST AI RMF MAP 2.3."
                ),
                category="ai_governance",
                severity="low",
                confidence="low",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    snippet=ctx,
                    description="Dataset loaded with no license or source attribution nearby.",
                )],
                recommendation=(
                    "Document the dataset's name, source URL, license, and any usage "
                    "restrictions in a comment adjacent to the load call or in a DATA_CARD.md. "
                    "Verify the license permits your use case (especially commercial use and "
                    "model training)."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings

    def _check_inference_no_audit_log(self, file: FileSnapshot) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()  # type: ignore[union-attr]
        seen_seeds: set[str] = set()

        for i, line in enumerate(lines):
            if not _INFERENCE_CALL_PATTERN.search(line):
                continue
            ctx = _context(lines, i)
            if _INFERENCE_LOG_PATTERN.search(ctx):
                continue
            seed = f"{file.path}:{i}"
            if seed in seen_seeds:
                continue
            seen_seeds.add(seed)
            findings.append(Finding(
                id=stable_finding_id(self.id, "inference_no_audit_log", seed),
                title="AI inference call with no audit logging of inputs and outputs",
                description=(
                    "A model inference call occurs with no visible logging of the input "
                    "prompt or context and the model's output. Without an audit trail, it "
                    "is impossible to investigate incidents, detect drift, or demonstrate "
                    "regulatory compliance. EU AI Act Art. 12 requires automatic logging "
                    "of events for high-risk AI systems; NIST AI RMF GOVERN 1.4 requires "
                    "traceability."
                ),
                category="ai_governance",
                severity="low",
                confidence="low",
                evidence=[FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=i + 1, line_end=i + 1),
                    snippet=ctx,
                    description="Inference call with no structured logging detected nearby.",
                )],
                recommendation=(
                    "Log each inference request and response with a unique request ID, "
                    "timestamp, model version, truncated/hashed input, and output. "
                    "Store logs in a tamper-evident, append-only store with an appropriate "
                    "retention period (minimum 30 days for incident response; longer for "
                    "regulated domains)."
                ),
                scanner_id=self.id,
                scanner_version=self.version,
            ))
        return findings
