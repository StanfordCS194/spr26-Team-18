from __future__ import annotations

from collections.abc import Callable

from models import ComplianceFinding, ComplianceReport, ComplianceRule, Evidence, ProductRiskProfile


RuleEvaluator = Callable[[ProductRiskProfile, ComplianceRule], ComplianceFinding]


RULES: tuple[tuple[ComplianceRule, RuleEvaluator], ...] = ()


def analyze_profile(profile: ProductRiskProfile) -> ComplianceReport:
    findings = [evaluator(profile, rule) for rule, evaluator in RULES]
    findings.sort(key=_finding_sort_key)
    return ComplianceReport(profile=profile, findings=findings)


def _finding_sort_key(finding: ComplianceFinding) -> tuple[int, int, str]:
    status_rank = {"review_recommended": 0, "needs_more_info": 1, "not_flagged": 2}
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    return (status_rank[finding.status], priority_rank[finding.priority], finding.name)


def _evidence(profile: ProductRiskProfile, labels: tuple[str, ...]) -> list[Evidence]:
    return [
        item
        for item in profile.evidence
        if any(item.label == label or item.label.startswith(label) for label in labels)
    ]


def _not_flagged(rule: ComplianceRule, rationale: str) -> ComplianceFinding:
    return ComplianceFinding(
        rule_id=rule.id,
        name=rule.name,
        status="not_flagged",
        priority=rule.priority,
        confidence="low",
        rationale=rationale,
    )


def _finding(
    rule: ComplianceRule,
    status: str,
    confidence: str,
    rationale: str,
    evidence: list[Evidence],
    missing_facts: list[str] | None = None,
) -> ComplianceFinding:
    return ComplianceFinding(
        rule_id=rule.id,
        name=rule.name,
        status=status,  # type: ignore[arg-type]
        priority=rule.priority,
        confidence=confidence,  # type: ignore[arg-type]
        rationale=rationale,
        evidence=evidence[:5],
        missing_facts=missing_facts or [],
        suggested_controls=list(rule.suggested_controls),
    )


def _coppa(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("minor users", "data collected:", "ads/tracking"))
    collects_personal_data = bool(profile.data_collected or profile.ads_or_tracking)
    if profile.child_directed and collects_personal_data:
        return _finding(
            rule,
            "review_recommended",
            "high",
            "The PRD suggests the product may be directed to children under 13 and collect personal information or persistent identifiers.",
            evidence,
            ["Confirm whether users under 13 can register or use the product."],
        )
    if profile.likely_minors and collects_personal_data:
        return _finding(
            rule,
            "needs_more_info",
            "medium",
            "The PRD mentions minors and personal data, but it is unclear whether the product is child-directed or has actual knowledge of under-13 users.",
            evidence,
            [
                "Is the service directed to children under 13?",
                "Will the product collect birthdate or otherwise know when a user is under 13?",
                "Do third-party analytics, ads, or SDKs collect persistent identifiers from under-13 users?",
            ],
        )
    return _not_flagged(rule, "No clear under-13 personal-data trigger was found in the PRD.")


def _minor_safety(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("minor users", "messaging/social features", "ads/tracking", "data collected:"))
    risky_features = any(
        [
            profile.messaging,
            profile.social_or_recommendation_features,
            profile.ads_or_tracking,
            profile.geolocation,
            profile.biometric_data,
        ]
    )
    if profile.likely_minors and risky_features:
        return _finding(
            rule,
            "review_recommended",
            "high",
            "The PRD suggests minors may use the product and includes features commonly scrutinized in child and teen safety laws.",
            evidence,
            [
                "Which US states will the product launch in?",
                "Will accounts for users under 18 use privacy-protective defaults?",
                "Will the product profile minors or rank/recommend content to minors?",
            ],
        )
    if profile.likely_minors:
        return _finding(
            rule,
            "needs_more_info",
            "medium",
            "The PRD indicates likely minor users, but the riskier product features are not fully specified.",
            evidence,
            [
                "Will minors have public profiles, messaging, social feeds, recommendations, or targeted ads?",
                "Will age be self-declared, estimated, or verified?",
            ],
        )
    return _not_flagged(rule, "No clear under-18 audience signal was found in the PRD.")


def _age_verification(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("adult content", "minor users", "biometric data", "data collected:"))
    if profile.adult_content:
        return _finding(
            rule,
            "review_recommended",
            "high",
            "The PRD references adult or harmful-to-minors content, which can trigger state age-verification requirements.",
            evidence,
            [
                "What percentage of product content is adult or harmful to minors?",
                "Which states will the product be available in?",
                "Will verification data be retained, shared, or processed by a vendor?",
            ],
        )
    if profile.likely_minors and profile.social_or_recommendation_features:
        return _finding(
            rule,
            "needs_more_info",
            "medium",
            "The PRD suggests a social product used by minors; state-specific age assurance or parental consent review may be needed.",
            evidence,
            [
                "Does the product meet any state definition of social media platform?",
                "Will app stores, device signals, or a third-party vendor provide age assurance?",
            ],
        )
    return _not_flagged(rule, "No adult-content or social-minor age assurance trigger was found.")


def _hipaa(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("health data/context", "data collected: health information"))
    if profile.health_data and profile.healthcare_context:
        return _finding(
            rule,
            "review_recommended",
            "high",
            "The PRD mentions health information and healthcare-entity or business-associate context.",
            evidence,
            [
                "Is the company a covered entity or acting for a covered entity?",
                "Will the company sign business associate agreements?",
                "Is the information used for treatment, payment, or healthcare operations?",
            ],
        )
    if profile.health_data:
        return _finding(
            rule,
            "needs_more_info",
            "medium",
            "The PRD mentions health data, but HIPAA depends on covered-entity or business-associate status.",
            evidence,
            [
                "Who are the customers: consumers, employers, providers, health plans, or clinics?",
                "Will the product receive data from providers, health plans, EHRs, or claims systems?",
                "Will business associate agreements be required?",
            ],
        )
    return _not_flagged(rule, "No health-data signal was found in the PRD.")


def _ftc_health_privacy(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("health data/context", "data collected: health information", "ads/tracking"))
    if profile.health_data and not profile.healthcare_context:
        return _finding(
            rule,
            "review_recommended",
            "medium",
            "The PRD suggests consumer health or wellness data outside a clear HIPAA context, which still raises FTC privacy and security risk.",
            evidence,
            [
                "What health-related claims will the product, privacy policy, or marketing make?",
                "Will health data be shared with analytics, advertising, or AI vendors?",
                "What breach notification obligations apply to health records or connected devices?",
            ],
        )
    return _not_flagged(rule, "No consumer health privacy signal outside HIPAA was found.")


def _state_privacy(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("data collected:", "ads/tracking", "biometric data"))
    sensitive = bool(profile.sensitive_data)
    if profile.data_collected and (sensitive or profile.ads_or_tracking):
        return _finding(
            rule,
            "review_recommended",
            "medium",
            "The PRD includes personal data plus sensitive data, tracking, or advertising that may trigger state privacy-law obligations.",
            evidence,
            [
                "What states are in scope and what user volume thresholds are expected?",
                "Will the product sell/share data or use targeted advertising?",
                "Will users have access, deletion, correction, opt-out, and appeal flows?",
            ],
        )
    if profile.data_collected:
        return _finding(
            rule,
            "needs_more_info",
            "low",
            "The PRD includes personal data, but volume, state scope, and data use are not clear enough to prioritize state privacy obligations.",
            evidence,
            [
                "Which states are in scope?",
                "How many consumers are expected?",
                "Will data be sold, shared, or used for targeted advertising or profiling?",
            ],
        )
    return _not_flagged(rule, "No personal-data collection signal was found.")


def _biometric(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("biometric data", "data collected: biometric data"))
    if profile.biometric_data:
        return _finding(
            rule,
            "review_recommended",
            "high",
            "The PRD suggests biometric processing such as face, voice, or liveness verification.",
            evidence,
            [
                "Will biometric templates or identifiers be created or retained?",
                "Which states will users be in?",
                "Will written consent, retention limits, and vendor terms be implemented?",
            ],
        )
    return _not_flagged(rule, "No biometric-data signal was found.")


def _ferpa(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("education context", "minor users", "data collected:"))
    if profile.education_context:
        return _finding(
            rule,
            "needs_more_info",
            "medium",
            "The PRD references education users or school context; FERPA review depends on whether student education records are handled for schools.",
            evidence,
            [
                "Will schools or districts provide student records?",
                "Is the product acting as a school official/vendor under a district contract?",
                "Can parents/students inspect or delete relevant records?",
            ],
        )
    return _not_flagged(rule, "No school or student-record context was found.")


def _marketing(profile: ProductRiskProfile, rule: ComplianceRule) -> ComplianceFinding:
    evidence = _evidence(profile, ("data collected: email", "data collected: phone"))
    has_contact = "email" in profile.data_collected or "phone" in profile.data_collected
    if has_contact:
        return _finding(
            rule,
            "needs_more_info",
            "low",
            "The PRD suggests collection of email or phone data; marketing and notification consent rules may matter depending on use.",
            evidence,
            [
                "Will email or SMS be used for marketing, reminders, or referrals?",
                "Will opt-in, unsubscribe, and quiet-hour controls be built?",
                "Will messages be automated or autodialed?",
            ],
        )
    return _not_flagged(rule, "No email or phone contact signal was found.")


RULES = (
    (
        ComplianceRule(
            id="coppa",
            name="COPPA / Children's Privacy",
            priority="high",
            description="Children's Online Privacy Protection Act review for under-13 users and personal information.",
            review_questions=(),
            suggested_controls=(
                "Age gate or age-aware onboarding",
                "Verifiable parental consent flow where needed",
                "Child-specific privacy notice",
                "Data minimization and parent access/deletion workflow",
                "Review analytics, ads, and SDK collection from child users",
            ),
        ),
        _coppa,
    ),
    (
        ComplianceRule(
            id="minor_safety",
            name="Teen / Minor Privacy and Safety",
            priority="high",
            description="State child safety, teen privacy, age-appropriate design, and harmful-design review.",
            review_questions=(),
            suggested_controls=(
                "Privacy-protective defaults for minors",
                "Limits on public profiles, messaging, geolocation, and targeted ads",
                "Minor-specific risk assessment",
                "Parental controls where appropriate",
            ),
        ),
        _minor_safety,
    ),
    (
        ComplianceRule(
            id="age_verification",
            name="Age Verification / Age Assurance",
            priority="high",
            description="Age assurance review for adult content, social media, or regulated minor access.",
            review_questions=(),
            suggested_controls=(
                "Data-minimizing age assurance strategy",
                "Vendor review for verification data handling",
                "Retention limits for verification artifacts",
                "Fallback path for users who cannot verify automatically",
            ),
        ),
        _age_verification,
    ),
    (
        ComplianceRule(
            id="hipaa",
            name="HIPAA",
            priority="high",
            description="HIPAA covered entity and business associate review.",
            review_questions=(),
            suggested_controls=(
                "Covered entity/business associate analysis",
                "Business associate agreement workflow",
                "PHI access controls, audit logging, and encryption",
                "Minimum necessary data model",
            ),
        ),
        _hipaa,
    ),
    (
        ComplianceRule(
            id="ftc_health_privacy",
            name="FTC Health Privacy and Security",
            priority="medium",
            description="FTC review for consumer health data, privacy claims, security, and breach notification.",
            review_questions=(),
            suggested_controls=(
                "Privacy claim review",
                "Health data sharing limits",
                "Security controls appropriate to health data",
                "Health breach notification assessment",
            ),
        ),
        _ftc_health_privacy,
    ),
    (
        ComplianceRule(
            id="state_privacy",
            name="State Consumer Privacy",
            priority="medium",
            description="US state privacy-law review for personal data, sensitive data, targeted advertising, and profiling.",
            review_questions=(),
            suggested_controls=(
                "Consumer rights request flows",
                "Sensitive-data consent or limitation controls",
                "Targeted advertising and sale/share opt-outs",
                "Data inventory and retention schedule",
            ),
        ),
        _state_privacy,
    ),
    (
        ComplianceRule(
            id="biometric_privacy",
            name="Biometric Privacy",
            priority="high",
            description="State biometric privacy review for face, voice, liveness, and identity verification data.",
            review_questions=(),
            suggested_controls=(
                "Written biometric notice and consent",
                "Retention and deletion schedule",
                "Vendor restrictions on biometric data",
                "Avoid retaining raw ID/selfie artifacts unless necessary",
            ),
        ),
        _biometric,
    ),
    (
        ComplianceRule(
            id="ferpa",
            name="FERPA / Education Privacy",
            priority="medium",
            description="FERPA and student-data vendor review.",
            review_questions=(),
            suggested_controls=(
                "School/district contract review",
                "Student record access controls",
                "Parent/student access and correction workflow",
                "Limits on secondary use of student data",
            ),
        ),
        _ferpa,
    ),
    (
        ComplianceRule(
            id="marketing_messaging",
            name="Marketing / Messaging Consent",
            priority="low",
            description="CAN-SPAM, TCPA, and notification consent review.",
            review_questions=(),
            suggested_controls=(
                "Opt-in records for SMS where needed",
                "Unsubscribe and preference center",
                "Transactional vs marketing message classification",
                "Quiet hours and frequency caps",
            ),
        ),
        _marketing,
    ),
)
