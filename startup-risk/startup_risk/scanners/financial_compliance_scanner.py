from __future__ import annotations

import re

from startup_risk.core.ids import stable_finding_id
from startup_risk.core.models import (
    Finding,
    FindingEvidence,
    RepositorySnapshot,
    Severity,
    SourceLocation,
)


_SOURCE_EXTENSIONS = frozenset({
    ".js", ".jsx", ".ts", ".tsx",
    ".py", ".go", ".rb", ".java", ".kt", ".cs",
    ".swift", ".php", ".c", ".cpp", ".rs", ".scala",
})

_CONFIG_EXTENSIONS = frozenset({
    ".json", ".yaml", ".yml", ".toml", ".env", ".ini", ".cfg", ".xml",
})

_SCANNABLE_EXTENSIONS = _SOURCE_EXTENSIONS | _CONFIG_EXTENSIONS

_SKIP_PATH_ROLES = frozenset({"tests"})
_MAX_LINE_LEN = 500
_CONTEXT_RADIUS = 6

# Ordered from earliest to latest stage — used for stage_gte comparisons.
_STAGES = ["pre_seed", "seed", "series_a", "series_b", "series_c_plus"]

_STAGE_ALIASES: dict[str, str] = {
    "pre-seed": "pre_seed",
    "preseed": "pre_seed",
    "pre_seed": "pre_seed",
    "seed": "seed",
    "series-a": "series_a",
    "series_a": "series_a",
    "seriesa": "series_a",
    "a": "series_a",
    "series-b": "series_b",
    "series_b": "series_b",
    "seriesb": "series_b",
    "b": "series_b",
    "series-c": "series_c_plus",
    "series_c": "series_c_plus",
    "seriesc": "series_c_plus",
    "series-c+": "series_c_plus",
    "series_c_plus": "series_c_plus",
    "c": "series_c_plus",
    "c+": "series_c_plus",
    "growth": "series_c_plus",
    "late-stage": "series_c_plus",
    "late_stage": "series_c_plus",
    "pre-ipo": "series_c_plus",
    "pre_ipo": "series_c_plus",
}


def _normalize_stage(stage: str | None) -> str:
    if not stage:
        return "seed"
    return _STAGE_ALIASES.get(stage.strip().lower().replace(" ", "-"), "seed")


def _stage_gte(stage: str, minimum: str) -> bool:
    try:
        return _STAGES.index(stage) >= _STAGES.index(minimum)
    except ValueError:
        return False


def _context(lines: list[str], index: int) -> str:
    lo = max(0, index - _CONTEXT_RADIUS)
    hi = min(len(lines), index + _CONTEXT_RADIUS + 1)
    return " ".join(lines[lo:hi])


# ── Rule: equity_grant_no_409a (Seed+) ────────────────────────────────────────
# IRC §409A requires options be granted at fair market value; violations trigger
# immediate income recognition, 20% excise tax, and interest on deferred amounts.

_EQUITY_GRANT = re.compile(
    r"""\b(?:stock[\s_-]?option|option[\s_-]?grant|equity[\s_-]?grant
        |grant[\s_-]?date|option[\s_-]?pool|strike[\s_-]?price
        |exercise[\s_-]?price|cliff[\s_-]?vest|vesting[\s_-]?schedule
        |\biso\b|\bnso\b|\brsu\b|incentive[\s_-]?stock[\s_-]?option)\b""",
    re.IGNORECASE | re.VERBOSE,
)
_EQUITY_409A = re.compile(
    r"\b(?:409[a_-]?a|fair[\s_-]?market[\s_-]?value|\bfmv\b|independent[\s_-]?valuation|409a[\s_-]?report)\b",
    re.IGNORECASE,
)

# ── Rule: restricted_stock_no_83b (Pre-seed / Seed) ──────────────────────────
# Founders must file IRC §83(b) within 30 days of receiving restricted stock to
# lock in low ordinary income; missing the window is irreversible.

_RESTRICTED_STOCK = re.compile(
    r"\b(?:restricted[\s_-]?stock|founder[\s_-]?stock|founder[\s_-]?shares?|stock[\s_-]?purchase[\s_-]?agreement|\bspa\b|vesting[\s_-]?schedule)\b",
    re.IGNORECASE,
)
_83B_ELECTION = re.compile(
    # 83(b) ends with ')' which is non-word, so no trailing \b for that branch.
    r"(?:\b83[\s_-]?b\b|\bsection[\s_-]?83\b|83\(b\)|\b83b[\s_-]?election\b)",
    re.IGNORECASE,
)

# ── Rule: contractor_payment_no_1099 (All stages) ─────────────────────────────
# IRS requires Form 1099-NEC for any contractor paid $600+ in a year; missing
# filings carry $310/form penalty plus potential backup withholding obligations.

_CONTRACTOR_PAYMENT = re.compile(
    # No leading \b: snake_case identifiers like pay_contractor embed the term
    # after a '_' which is a word character, so \b would miss them.
    r"(?:contractor|freelancer|independent[\s_-]?contractor|gig[\s_-]?worker|vendor[\s_-]?payment|1099[\s_-]?worker)",
    re.IGNORECASE,
)
_TAX_REPORTING_1099 = re.compile(
    r"\b(?:1099|w[\s_-]?9\b|w9\b|tax[\s_-]?id|taxpayer[\s_-]?id|\bein\b|withhold|irs[\s_-]?report|backup[\s_-]?withhold)\b",
    re.IGNORECASE,
)

# ── Rule: payroll_no_withholding (All stages) ──────────────────────────────────
# Employers must withhold FICA, federal income tax, state/local taxes, and remit
# via EFTPS; failure-to-deposit penalties start at 2% of owed taxes.

_PAYROLL_DISBURSE = re.compile(
    r"\b(?:process[\s_-]?payroll|run[\s_-]?payroll|pay[\s_-]?employee|direct[\s_-]?deposit[\s_-]?amount|employee[\s_-]?salary|salary[\s_-]?disburs|payroll[\s_-]?run)\b",
    re.IGNORECASE,
)
_PAYROLL_TAX = re.compile(
    r"\b(?:\bfica\b|\bfuta\b|\bsuta\b|state[\s_-]?withhold|payroll[\s_-]?tax|federal[\s_-]?withhold|form[\s_-]?941|eftps)\b",
    re.IGNORECASE,
)

# ── Rule: iso_exercise_no_form_3921 (Series A+) ───────────────────────────────
# Corporations must file Form 3921 for each ISO exercise by Jan 31; failure
# carries up to $310/form. ISO exercises also trigger AMT exposure for employees.

_ISO_EXERCISE = re.compile(
    r"\b(?:iso[\s_-]?exercise|option[\s_-]?exercise|early[\s_-]?exercise|exercised[\s_-]?options?|exercise[\s_-]?shares?)\b",
    re.IGNORECASE,
)
_FORM_3921 = re.compile(
    r"\b(?:form[\s_-]?3921|3921|\bamt\b|alternative[\s_-]?minimum[\s_-]?tax|iso[\s_-]?report)\b",
    re.IGNORECASE,
)

# ── Rule: payment_processing_no_sales_tax (Series B+) ─────────────────────────
# Post-South Dakota v. Wayfair (2018), economic nexus thresholds (~$100K revenue
# or 200 transactions per state) require sales tax collection without physical
# presence; 45 states + DC levy sales tax.

_PAYMENT_PROCESSING = re.compile(
    r"\b(?:payment[\s_-]?intent|checkout[\s_-]?session|invoice[\s_-]?item|charge[\s_-]?create|subscription[\s_-]?create|billing[\s_-]?portal|stripe[\s_-]?charge)\b",
    re.IGNORECASE,
)
_SALES_TAX = re.compile(
    r"\b(?:sales[\s_-]?tax|vat[\s_-]?rate|tax[\s_-]?code|tax[\s_-]?rate|avalara|taxjar|nexus|tax[\s_-]?exempt|tax[\s_-]?calculation|tax[\s_-]?collect)\b",
    re.IGNORECASE,
)

# ── Rule: intl_transfer_no_fbar (Series B+) ───────────────────────────────────
# FBAR (FinCEN 114) is due June 15 if aggregate foreign account balances exceed
# $10K at any point; Form 8938 (FATCA) applies to higher thresholds; civil
# penalties for willful non-filing reach $100K+ per violation.

_INTL_PAYMENT = re.compile(
    r"\b(?:swift[\s_-]?code|\biban\b|wire[\s_-]?transfer|foreign[\s_-]?payment|international[\s_-]?transfer|cross[\s_-]?border[\s_-]?payment|fx[\s_-]?transfer|foreign[\s_-]?wire)\b",
    re.IGNORECASE,
)
_FBAR_CONTROLS = re.compile(
    r"\b(?:\bfbar\b|\bfatca\b|foreign[\s_-]?bank|form[\s_-]?8938|\bfincen\b|\bofac\b|sanctions[\s_-]?screen|fincen[\s_-]?114)\b",
    re.IGNORECASE,
)

# ── Rule: nol_no_382_limit (Series B+) ────────────────────────────────────────
# IRC §382 limits the annual use of pre-change NOL carryforwards after an
# "ownership change" (>50% shift in ownership over 3 years); equity financing
# rounds can trigger this limitation, permanently capping NOL utilization.

_NOL_TRACKING = re.compile(
    r"\b(?:net[\s_-]?operating[\s_-]?loss|\bnol\b|tax[\s_-]?loss[\s_-]?carryforward|loss[\s_-]?carryover|nol[\s_-]?balance)\b",
    re.IGNORECASE,
)
_NOL_382 = re.compile(
    r"\b(?:section[\s_-]?382|382[\s_-]?limitation|ownership[\s_-]?change|annual[\s_-]?382|382[\s_-]?annual[\s_-]?limit)\b",
    re.IGNORECASE,
)

# ── Rule: rd_expense_no_credit (Series B+) ────────────────────────────────────
# IRC §41 R&D Tax Credit (up to 20% of qualifying research expenses above a base
# amount) requires contemporaneous documentation of qualified research activities,
# wages, supplies, and contract research. Amortization under §174 now mandatory.

_RD_EXPENSE = re.compile(
    r"\b(?:r[\s_&]?d[\s_-]?expense|research[\s_-]?expense|qualified[\s_-]?research|\bqre\b|research[\s_-]?labor|174[\s_-]?amortiz)\b",
    re.IGNORECASE,
)
_RD_CREDIT = re.compile(
    r"\b(?:section[\s_-]?41|r[\s_&]?d[\s_-]?credit|research[\s_-]?credit|form[\s_-]?6765|6765|section[\s_-]?174)\b",
    re.IGNORECASE,
)

# ── Rule: exec_comp_no_162m (Series C+) ───────────────────────────────────────
# IRC §162(m) caps the tax deduction for "covered employee" compensation at $1M;
# post-TCJA the performance-based exception is eliminated and the covered employee
# list is permanent, making pre-IPO comp planning critical.

_EXEC_COMP = re.compile(
    r"\b(?:executive[\s_-]?compensation|ceo[\s_-]?salary|cfo[\s_-]?comp|named[\s_-]?executive|covered[\s_-]?employee|exec[\s_-]?bonus)\b",
    re.IGNORECASE,
)
_COMP_162M = re.compile(
    r"\b(?:162[\s_-]?m|section[\s_-]?162|one[\s_-]?million[\s_-]?deduction|deduction[\s_-]?limit|performance[\s_-]?based[\s_-]?comp)\b",
    re.IGNORECASE,
)

# ── Rule: stock_issuance_no_qsbs (Seed+) ──────────────────────────────────────
# IRC §1202 excludes 100% of capital gains on QSBS held 5+ years; qualification
# is locked in at issuance — companies with ≤$50M aggregate gross assets and
# satisfying the active business test qualify. Tracking is the issuer's responsibility;
# investors cannot retroactively establish QSBS status after the fact.

_STOCK_ISSUANCE = re.compile(
    # No leading \b: snake_case names like record_stock_issuance embed these terms
    # after '_' (a word character), so \b would miss them.
    r"(?:issue[\s_-]?shares?|issue[\s_-]?stock|original[\s_-]?issuance|stock[\s_-]?issuance|share[\s_-]?issuance|preferred[\s_-]?stock[\s_-]?issu|common[\s_-]?stock[\s_-]?issu|new[\s_-]?shares?[\s_-]?issu)",
    re.IGNORECASE,
)
_QSBS_CONTROLS = re.compile(
    r"\b(?:1202|qsbs|qualified[\s_-]?small[\s_-]?business|gross[\s_-]?assets[\s_-]?test|qsbs[\s_-]?eligible|section[\s_-]?1202)\b",
    re.IGNORECASE,
)

# ── Rule: iso_grant_no_100k_limit (Series A+) ─────────────────────────────────
# IRC §422(d) caps the FMV of stock first exercisable under ISOs in any calendar
# year at $100,000 per employee; excess automatically converts to NSOs, losing
# the preferential ISO tax treatment and triggering W-2 income at exercise instead
# of long-term capital gain deferral until sale.

_ISO_GRANT = re.compile(
    # No leading \b: identifiers like create_iso_grant embed these terms after '_'.
    r"(?:grant[\s_-]?iso|create[\s_-]?iso|issue[\s_-]?iso|new[\s_-]?iso|incentive[\s_-]?stock[\s_-]?option|iso[\s_-]?award|iso[\s_-]?grant)",
    re.IGNORECASE,
)
_ISO_100K_LIMIT = re.compile(
    r"(?:\b100[\s,]?000\b|100k[\s_-]?(?:limit|cap|annual)|\b422[\s_-]?d\b|annual[\s_-]?iso[\s_-]?(?:limit|cap)|iso[\s_-]?(?:limit|cap|threshold)|\bnso[\s_-]?conver|excess[\s_-]?iso)",
    re.IGNORECASE,
)

# ── Rule: deferred_comp_no_409a (Series A+) ───────────────────────────────────
# IRC §409A governs ALL non-qualified deferred compensation — not just options —
# including severance, retention bonuses, and deferred bonus plans. Non-compliant
# arrangements cause immediate income inclusion + 20% excise tax + interest for
# the employee; companies face withholding liability for 20% of the deferred amount.

_DEFERRED_COMP = re.compile(
    r"\b(?:severance[\s_-]?agreement|severance[\s_-]?pay|deferred[\s_-]?compensation|bonus[\s_-]?deferral|retention[\s_-]?bonus[\s_-]?defer|nonqualified[\s_-]?deferred|separation[\s_-]?payment)\b",
    re.IGNORECASE,
)
_409A_DEFERRED = re.compile(
    r"\b(?:409a|section[\s_-]?409|short[\s_-]?term[\s_-]?deferral|separation[\s_-]?from[\s_-]?service|409a[\s_-]?compliant|specified[\s_-]?employee)\b",
    re.IGNORECASE,
)

# ── Rule: change_of_control_no_280g (Series B+) ────────────────────────────────
# IRC §280G denies deduction for "excess parachute payments" (>3× base comp) on
# a change of control; IRC §4999 imposes a 20% excise tax on the recipient.
# The only full escape is the private-company shareholder safe-harbor vote under
# §280G(b)(5) — requiring independent valuation, 75% approval, and proper disclosure.

_CHANGE_OF_CONTROL = re.compile(
    r"\b(?:change[\s_-]?of[\s_-]?control|change[\s_-]?in[\s_-]?control|coc[\s_-]?event|acquisition[\s_-]?trigger|severance[\s_-]?acceleration|double[\s_-]?trigger|single[\s_-]?trigger|acceleration[\s_-]?on[\s_-]?(?:acquisition|merger|sale))\b",
    re.IGNORECASE,
)
_PARACHUTE_CONTROLS = re.compile(
    r"\b(?:280g|section[\s_-]?280|golden[\s_-]?parachute|parachute[\s_-]?payment|4999|280g[\s_-]?analysis|safe[\s_-]?harbor[\s_-]?vote|excise[\s_-]?tax[\s_-]?gross[\s_-]?up)\b",
    re.IGNORECASE,
)

# ── Rule: espp_no_form_3922 (Series A+) ───────────────────────────────────────
# Corporations must file Form 3922 for each transfer of stock to an employee
# under a §423 ESPP by January 31; failure carries up to $310/form. Unlike ISOs,
# the taxable event (ordinary income vs. qualified disposition) is determined at
# sale, so the transfer record is the only contemporaneous documentation.

_ESPP_ACTIVITY = re.compile(
    r"(?:espp|employee[\s_-]?stock[\s_-]?purchase[\s_-]?plan|stock[\s_-]?purchase[\s_-]?plan[\s_-]?offering|espp[\s_-]?enrollment|espp[\s_-]?purchase|espp[\s_-]?transfer)",
    re.IGNORECASE,
)
_FORM_3922 = re.compile(
    r"\b(?:form[\s_-]?3922|3922|espp[\s_-]?report|espp[\s_-]?transfer[\s_-]?report|423[\s_-]?plan[\s_-]?report)\b",
    re.IGNORECASE,
)

# ── Rule: intercompany_no_transfer_pricing (Series B+) ─────────────────────────
# IRC §482 requires that controlled transactions (IP licensing, management fees,
# intercompany loans, cost-sharing) reflect arm's-length pricing; the IRS can
# reallocate income across entities if pricing is not at arm's length. Penalties
# for underpayment are 20–40% of the understated amount; contemporaneous
# documentation (the "best method" analysis) is the primary defense.

_INTERCOMPANY_TX = re.compile(
    r"\b(?:intercompany[\s_-]?(?:loan|payment|transfer|charge|service|fee)|related[\s_-]?party[\s_-]?(?:transaction|payment|transfer)|parent[\s_-]?company[\s_-]?(?:loan|fee|charge)|subsidiary[\s_-]?(?:royalt|service[\s_-]?fee|management[\s_-]?fee))\b",
    re.IGNORECASE,
)
_TRANSFER_PRICING = re.compile(
    r"\b(?:transfer[\s_-]?pricing|arm[\s_-]?s?[\s_-]?length|section[\s_-]?482|482[\s_-]?study|contemporaneous[\s_-]?documentation|comparable[\s_-]?uncontrolled|cost[\s_-]?sharing[\s_-]?agreement)\b",
    re.IGNORECASE,
)

# ── Rule: foreign_subsidiary_no_gilti (Series B+) ─────────────────────────────
# GILTI (IRC §951A) requires US shareholders of CFCs to include global intangible
# low-taxed income in gross income annually regardless of distribution; Subpart F
# (§951) does the same for specified passive income categories. US companies with
# any foreign subsidiary that earns profit must file Form 5471 and evaluate GILTI.

_FOREIGN_SUBSIDIARY = re.compile(
    r"\b(?:foreign[\s_-]?subsidiary|controlled[\s_-]?foreign[\s_-]?corp|cfc[\s_-]?income|foreign[\s_-]?entity[\s_-]?profit|offshore[\s_-]?subsidiary|foreign[\s_-]?sub[\s_-]?income)\b",
    re.IGNORECASE,
)
_GILTI_CONTROLS = re.compile(
    r"\b(?:gilti|section[\s_-]?951|subpart[\s_-]?f|cfc[\s_-]?tax|global[\s_-]?intangible|form[\s_-]?5471|5471|foreign[\s_-]?tax[\s_-]?credit|ftc[\s_-]?credit)\b",
    re.IGNORECASE,
)

# ── Rule: revenue_no_asc606 (Series C+) ───────────────────────────────────────
# ASC 606 / IFRS 15 requires revenue to be recognized when (or as) performance
# obligations are satisfied under the five-step model. IRC §451 now generally
# conforms taxable income recognition to GAAP, meaning ASC 606 errors flow
# through to the tax return. Multi-year SaaS contracts, implementation fees, and
# usage-based pricing each require distinct performance-obligation analysis.

_REVENUE_RECOGNITION = re.compile(
    r"(?:recognize[\s_-]?revenue|revenue[\s_-]?recognition|deferred[\s_-]?revenue[\s_-]?schedul|performance[\s_-]?obligation|contract[\s_-]?revenue[\s_-]?recogni|subscription[\s_-]?revenue[\s_-]?recogni)",
    re.IGNORECASE,
)
_ASC_606_CONTROLS = re.compile(
    r"\b(?:asc[\s_-]?606|asc606|ifrs[\s_-]?15|five[\s_-]?step[\s_-]?model|performance[\s_-]?obligation[\s_-]?identif|stand[\s_-]?alone[\s_-]?selling[\s_-]?price|ssp[\s_-]?allocation|irc[\s_-]?451)\b",
    re.IGNORECASE,
)

# ── Rule: interest_expense_no_163j (Series C+) ───────────────────────────────
# IRC §163(j) limits the deduction for business interest expense to 30% of
# "adjusted taxable income" (ATI); disallowed interest becomes a carryforward.
# ATI no longer includes depreciation/amortization add-backs post-2021 (EBIT not
# EBITDA), substantially tightening the cap for asset-heavy or levered companies.

_INTEREST_EXPENSE = re.compile(
    r"(?:interest[\s_-]?expense[\s_-]?record|loan[\s_-]?interest[\s_-]?pay|debt[\s_-]?service[\s_-]?interest|deduct[\s_-]?interest[\s_-]?expense|business[\s_-]?interest[\s_-]?expense|note[\s_-]?interest[\s_-]?accrual)",
    re.IGNORECASE,
)
_163J_CONTROLS = re.compile(
    r"\b(?:163[\s_-]?j|section[\s_-]?163|interest[\s_-]?limitation|adjusted[\s_-]?taxable[\s_-]?income|\bati[\s_-]?limit|30[\s_-]?percent[\s_-]?(?:ati|limit)|interest[\s_-]?carryforward[\s_-]?tax)\b",
    re.IGNORECASE,
)

# ── Rule: rd_expense_no_174_amortization (Seed+) ─────────────────────────────
# Post-2022, IRC §174 mandates 5-year (domestic) / 15-year (foreign) amortization
# of all specified R&D expenditures; immediate expensing is no longer permitted.
# ASC 730 still allows full expensing on the financial statements, so companies
# must track a deferred tax liability for the book/tax timing difference.

_RD_COST_TREATMENT = re.compile(
    r"(?:research[\s_-]?(?:cost|expenditure|expense)[\s_-]?(?:expensed|written[\s_-]?off|as[\s_-]?incurred|immediately)|development[\s_-]?cost[\s_-]?(?:expensed|written[\s_-]?off|as[\s_-]?incurred)|r[\s_&]?d[\s_-]?(?:cost|spend|expenditure)[\s_-]?(?:expensed|written|immediate)|software[\s_-]?dev[\s_-]?cost[\s_-]?(?:expensed|written))",
    re.IGNORECASE,
)
_174_AMORTIZATION_CTRL = re.compile(
    r"\b(?:section[\s_-]?174|174[\s_-]?amortiz|five[\s_-]?year[\s_-]?(?:amortiz|capitaliz)[\s_-]?research|15[\s_-]?year[\s_-]?amortiz[\s_-]?(?:foreign|intl)|asc[\s_-]?730[\s_-]?capitaliz|asc[\s_-]?350[\s_-]?40|capitalize[\s_-]?research[\s_-]?expenditure|specified[\s_-]?research[\s_-]?expenditure)\b",
    re.IGNORECASE,
)

# ── Rule: payroll_no_eftps_schedule (All stages) ─────────────────────────────
# IRS assigns deposit schedules (monthly ≤ $50K lookback; semiweekly $50K+);
# failure-to-deposit penalties escalate 2%→5%→10%→15% based on days late.
# EFTPS enrollment is mandatory for all federal tax deposits.

_PAYROLL_TAX_PAYMENT = re.compile(
    r"(?:payroll[\s_-]?tax[\s_-]?(?:deposit|remit|payment|paid)|federal[\s_-]?tax[\s_-]?deposit|employer[\s_-]?tax[\s_-]?(?:remit|deposit|payment)|fica[\s_-]?(?:deposit|remit|payment)|941[\s_-]?(?:deposit|remit|payment))",
    re.IGNORECASE,
)
_EFTPS_SCHEDULE_CTRL = re.compile(
    r"\b(?:eftps|semiweekly[\s_-]?depositor|monthly[\s_-]?depositor|lookback[\s_-]?period|deposit[\s_-]?schedule|form[\s_-]?944|next[\s_-]?business[\s_-]?day[\s_-]?deposit|ftd[\s_-]?(?:penalty|alert))\b",
    re.IGNORECASE,
)

# ── Rule: remote_employee_no_state_nexus (Seed+) ─────────────────────────────
# A single employee working in a state creates corporate income tax nexus and
# employer withholding registration obligations — separate from Wayfair sales tax
# nexus. Remote-first startups routinely miss state income tax return filings
# and payroll registrations across states where employees are located.

_REMOTE_EMPLOYEE_STATE = re.compile(
    # No leading \b: hire_remote_employee_in_... embeds these terms after '_'
    r"(?:remote[\s_-]?employee[\s_-]?(?:in|based|located)|out[\s_-]?of[\s_-]?state[\s_-]?employee|employee[\s_-]?(?:in|across)[\s_-]?(?:multiple|different|another|other)[\s_-]?state|multi[\s_-]?state[\s_-]?employee|home[\s_-]?state[\s_-]?(?:payroll|tax|withhold)|state[\s_-]?of[\s_-]?employment[\s_-]?tax)",
    re.IGNORECASE,
)
_STATE_NEXUS_CTRL = re.compile(
    r"\b(?:state[\s_-]?(?:income[\s_-]?tax[\s_-]?)?nexus|income[\s_-]?tax[\s_-]?nexus|state[\s_-]?(?:corporate[\s_-]?)?tax[\s_-]?registr|state[\s_-]?apportionment|single[\s_-]?sales[\s_-]?factor|throwback[\s_-]?rule|state[\s_-]?income[\s_-]?tax[\s_-]?return|corporate[\s_-]?return[\s_-]?(?:filed|per)[\s_-]?state)\b",
    re.IGNORECASE,
)

# ── Rule: safe_note_no_classification (All stages) ───────────────────────────
# SAFEs and convertible notes require ASC 480 / ASC 815 classification (debt vs.
# equity; bifurcation of embedded conversion features). SAFEs mis-booked as equity
# instead of liability distort the balance sheet. Interest on convertible notes is
# ordinary income under IRC §1273 OID rules; deemed dividends arise on notes with
# beneficial conversion features.

_SAFE_CONVERTIBLE = re.compile(
    # No outer \b: convertible_note_balance has 'note' followed by '_' (word char),
    # so trailing \b would never match inside snake_case identifiers.
    r"(?:safe[\s_-]?(?:note|investment|agreement|round|investor|holder)|simple[\s_-]?agreement[\s_-]?for[\s_-]?future[\s_-]?equity|convertible[\s_-]?(?:note|debt|instrument)|note[\s_-]?conversion|safe[\s_-]?conversion|priced[\s_-]?round[\s_-]?conversion|safe[\s_-]?cap[\s_-]?table)",
    re.IGNORECASE,
)
_NOTE_CLASSIFICATION_CTRL = re.compile(
    r"\b(?:asc[\s_-]?480|asc[\s_-]?815|debt[\s_-]?(?:vs|or)[\s_-]?equity|liability[\s_-]?classif|equity[\s_-]?classif|bifurcat|original[\s_-]?issue[\s_-]?discount|\boid\b|note[\s_-]?interest[\s_-]?accrual|deemed[\s_-]?dividend|beneficial[\s_-]?conversion[\s_-]?feature|\bbcf\b)\b",
    re.IGNORECASE,
)


class FinancialComplianceScanner:
    """Detects stage-specific IRS/tax compliance gaps in financial code patterns.

    Pass ``funding_round`` at construction to enable stage-gated rules (e.g. §409A
    checks activate at Seed, §382 NOL limits at Series B). Accepted values:
    ``pre_seed``, ``seed``, ``series_a``, ``series_b``, ``series_c_plus`` plus common
    aliases such as "Series A", "series-b", "growth", "pre-ipo".  Defaults to "seed"
    when omitted or unrecognised.
    """

    id = "financial_compliance"
    name = "Financial Compliance"
    version = "1.3.0"

    def __init__(self, *, funding_round: str | None = None) -> None:
        self._stage = _normalize_stage(funding_round)

    @property
    def stage(self) -> str:
        return self._stage

    def scan(self, snapshot: RepositorySnapshot) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[str] = set()
        for file in snapshot.files:
            if file.text is None:
                continue
            if file.path_role in _SKIP_PATH_ROLES:
                continue
            if file.extension not in _SCANNABLE_EXTENSIONS:
                continue
            for finding in self._scan_file(file):
                if finding.id not in seen:
                    seen.add(finding.id)
                    findings.append(finding)
        return findings

    def _scan_file(self, file) -> list[Finding]:
        findings: list[Finding] = []
        lines = file.text.splitlines()

        for i, line in enumerate(lines):
            if len(line) > _MAX_LINE_LEN:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*", "/*")):
                continue

            ctx = _context(lines, i)
            lineno = i + 1

            # §83(b) — Pre-seed / Seed: founders with restricted stock must file
            # within 30 days; missing the window permanently raises their tax basis.
            if _stage_gte(self._stage, "pre_seed") and not _stage_gte(self._stage, "series_a"):
                if _RESTRICTED_STOCK.search(stripped) and not _83B_ELECTION.search(ctx):
                    findings.append(self._finding(
                        rule="restricted_stock_no_83b",
                        title="Restricted stock issued without IRC §83(b) election handling",
                        description=(
                            "Founder or early employee restricted stock is being granted or "
                            "tracked without any reference to an IRC §83(b) election. Founders "
                            "must file the §83(b) election with the IRS within 30 days of "
                            "receiving unvested restricted stock; missing this window is "
                            "irreversible and causes ordinary income recognition at each vest."
                        ),
                        severity="high",
                        recommendation=(
                            "Add a §83(b) election reminder and filing deadline to the stock "
                            "grant workflow. The election must be postmarked within 30 days of "
                            "the grant date; provide a template letter citing IRC §83(b) and "
                            "confirm filing with the IRS service center."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

            # §409A — Seed+: every option grant must be at FMV per an independent
            # appraisal; violations cause immediate income inclusion + 20% excise tax.
            if _stage_gte(self._stage, "seed"):
                if _EQUITY_GRANT.search(stripped) and not _EQUITY_409A.search(ctx):
                    severity: Severity = "high" if _stage_gte(self._stage, "series_a") else "medium"
                    findings.append(self._finding(
                        rule="equity_grant_no_409a",
                        title="Equity grant without IRC §409A fair-market-value reference",
                        description=(
                            "An option grant or equity award is being processed without any "
                            "reference to a §409A valuation or fair market value determination. "
                            "IRC §409A requires that stock options be granted at no less than "
                            "FMV on the grant date, established by an independent qualified "
                            "appraisal. Violations result in immediate ordinary income "
                            "recognition, a 20% excise tax, and interest — borne by the "
                            "employee, not the company."
                        ),
                        severity=severity,
                        recommendation=(
                            "Obtain a §409A independent valuation from a qualified appraiser "
                            "before each grant date, or within 12 months of any material event "
                            "(new financing round, material change in business). Store the "
                            "report and cite the FMV in the option grant agreement. Refresh "
                            "the valuation at least annually."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §1202 QSBS — Seed+: qualification is locked in at issuance and can
                # mean a 100% capital-gains exclusion for investors; no retroactive fixes.
                if _STOCK_ISSUANCE.search(stripped) and not _QSBS_CONTROLS.search(ctx):
                    findings.append(self._finding(
                        rule="stock_issuance_no_qsbs",
                        title="Stock issuance without IRC §1202 QSBS qualification tracking",
                        description=(
                            "Stock is being issued without any reference to IRC §1202 Qualified "
                            "Small Business Stock (QSBS) eligibility. Investors who hold QSBS "
                            "for 5+ years can exclude 100% of capital gains (up to $10M or 10× "
                            "basis per investor). Qualification is permanently determined at "
                            "issuance: the company must be a domestic C-Corp with ≤$50M in "
                            "aggregate gross assets at issuance and satisfy the active business "
                            "test. Once a financing round pushes gross assets above $50M, new "
                            "shares lose QSBS status — prior shares retain it."
                        ),
                        severity="medium",
                        recommendation=(
                            "At each stock issuance, record and attest aggregate gross assets "
                            "to confirm the $50M threshold has not been crossed. Issue a §1202 "
                            "representation letter to investors at closing. Obtain a legal opinion "
                            "on QSBS eligibility for each round. Track QSBS status per share lot "
                            "in your cap table software (Carta and Pulley both support QSBS flags)."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §174 mandatory amortization — Seed+: post-2022 change requires all
                # R&D expenditures to be capitalized and amortized, not expensed immediately.
                if _RD_COST_TREATMENT.search(stripped) and not _174_AMORTIZATION_CTRL.search(ctx):
                    findings.append(self._finding(
                        rule="rd_expense_no_174_amortization",
                        title="R&D expenditures treated as immediately expensed without IRC §174 amortization",
                        description=(
                            "Research or development costs appear to be expensed as incurred "
                            "without reference to IRC §174 mandatory amortization. Effective for "
                            "tax years beginning after December 31, 2021, §174 requires all "
                            "specified research or experimental expenditures to be capitalized "
                            "and amortized: 5-year ratable amortization for domestic R&D "
                            "(midpoint convention — effectively 10% year 1) and 15-year for "
                            "foreign R&D. Immediate expensing under ASC 730 still applies on "
                            "the GAAP financial statements, creating a permanent book/tax "
                            "difference that must be tracked as a deferred tax liability."
                        ),
                        severity="medium",
                        recommendation=(
                            "Identify all §174 qualified research expenditures (wages, supplies, "
                            "contract research) and establish an amortization schedule for the "
                            "tax return. If prior tax years (2022+) were filed with immediate "
                            "expensing, consider an accounting method change (Form 3115) or "
                            "amended return. Track the resulting deferred tax liability in the "
                            "tax provision. Consult a tax advisor on which software development "
                            "costs qualify as §174 vs. §263A vs. ASC 350-40 capital items."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # State income tax nexus — Seed+: a single remote employee in another
                # state creates corporate income tax and payroll registration obligations
                # distinct from Wayfair sales tax nexus.
                if _REMOTE_EMPLOYEE_STATE.search(stripped) and not _STATE_NEXUS_CTRL.search(ctx):
                    findings.append(self._finding(
                        rule="remote_employee_no_state_nexus",
                        title="Remote employee in another state without state income tax nexus analysis",
                        description=(
                            "One or more employees appear to work in a state other than the "
                            "company's principal state, without any reference to state income "
                            "tax nexus or apportionment analysis. A single employee in a state "
                            "typically creates: (1) corporate income tax nexus requiring a state "
                            "return; (2) employer payroll tax registration and withholding in "
                            "that state; (3) potential state unemployment insurance (SUI) "
                            "obligations. This is separate from Wayfair sales tax nexus and "
                            "applies even at pre-revenue stage. Non-filing penalties vary by "
                            "state but commonly include 5–25% of unpaid tax plus interest."
                        ),
                        severity="medium",
                        recommendation=(
                            "For each state where an employee is based, consult a state tax "
                            "advisor on nexus, filing, and registration obligations before the "
                            "first paycheck. Register with the state department of revenue "
                            "(corporate income tax) and department of labor (payroll/SUI). "
                            "Determine the applicable apportionment formula (single-sales-factor "
                            "vs. three-factor). Use a PEO or multi-state payroll provider "
                            "(Rippling, Gusto) that handles state registrations automatically."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

            # Form 1099-NEC — All stages: $600+ contractor payments require a 1099.
            if _CONTRACTOR_PAYMENT.search(stripped) and not _TAX_REPORTING_1099.search(ctx):
                findings.append(self._finding(
                    rule="contractor_payment_no_1099",
                    title="Contractor payment code without Form 1099-NEC / W-9 handling",
                    description=(
                        "Code references contractor or freelancer payments without nearby "
                        "Form 1099-NEC filing logic or W-9 collection. IRS requires that "
                        "businesses file Form 1099-NEC for each contractor paid $600 or more "
                        "in a calendar year. Failure carries $310/form penalty (up to "
                        "$3.282M/year for large filers) plus potential backup withholding "
                        "obligations at 24%."
                    ),
                    severity="medium",
                    recommendation=(
                        "Collect a signed Form W-9 before the first payment to any contractor. "
                        "Track cumulative annual payments per vendor. Automate Form 1099-NEC "
                        "generation and filing by January 31 each year. Consider an accounting "
                        "integration (e.g., Gusto, QuickBooks) to handle 1099 compliance."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            # Payroll tax withholding — All stages.
            if _PAYROLL_DISBURSE.search(stripped) and not _PAYROLL_TAX.search(ctx):
                findings.append(self._finding(
                    rule="payroll_no_withholding",
                    title="Payroll disbursement without tax-withholding signals",
                    description=(
                        "Payroll processing code is present without nearby FICA, federal/state "
                        "withholding, or FUTA/SUTA references. Employers must withhold employee "
                        "FICA (7.65%), federal income tax, and state/local taxes, and remit "
                        "employer-share FICA and unemployment taxes via EFTPS. Failure-to-deposit "
                        "penalties start at 2% and escalate to 15% for deposits more than 10 days "
                        "late."
                    ),
                    severity="high",
                    recommendation=(
                        "Use a registered payroll provider (Gusto, Rippling, ADP) that handles "
                        "FICA splits, federal and state withholding, Form 941 quarterly deposits, "
                        "and W-2 generation. If building custom payroll logic, integrate IRS "
                        "withholding tables and EFTPS deposit schedules explicitly."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            # SAFE / convertible note classification — All stages.
            if _SAFE_CONVERTIBLE.search(stripped) and not _NOTE_CLASSIFICATION_CTRL.search(ctx):
                findings.append(self._finding(
                    rule="safe_note_no_classification",
                    title="SAFE or convertible note without ASC 480/815 accounting classification",
                    description=(
                        "A SAFE (Simple Agreement for Future Equity) or convertible note is "
                        "referenced without any indication of proper accounting classification "
                        "under ASC 480 or ASC 815. SAFEs are generally recorded as liabilities "
                        "under GAAP until conversion — not equity — and misclassification "
                        "inflates reported equity and understates liabilities. Convertible notes "
                        "require bifurcation analysis for embedded conversion features. Interest "
                        "on convertible notes is subject to OID rules under IRC §1273 if issued "
                        "at a discount, creating ordinary income for the holder regardless of "
                        "cash payments. Deemed dividends can arise if conversion terms contain "
                        "a beneficial conversion feature at issuance."
                    ),
                    severity="medium",
                    recommendation=(
                        "For each SAFE or convertible note: (1) determine ASC 480 / ASC 815 "
                        "classification (liability vs. equity); (2) test for bifurcation of "
                        "the embedded conversion feature under ASC 815-15; (3) compute OID if "
                        "issued below face value and accrue using the effective interest method; "
                        "(4) disclose in financial statement footnotes. Engage a technical "
                        "accounting advisor for the initial classification — especially for notes "
                        "with variable conversion mechanics (MFN provisions, valuation caps with "
                        "pro-rata rights, or interest that accrues into principal)."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            # Payroll tax deposit schedule — All stages: EFTPS deposit schedules
            # (monthly/semiweekly based on lookback period) carry FTD penalties
            # of 2–15% for late deposits — a common pre-seed and seed oversight.
            if _PAYROLL_TAX_PAYMENT.search(stripped) and not _EFTPS_SCHEDULE_CTRL.search(ctx):
                findings.append(self._finding(
                    rule="payroll_no_eftps_schedule",
                    title="Payroll tax deposit without IRS EFTPS deposit schedule compliance",
                    description=(
                        "Payroll tax deposits are referenced without indication of a proper "
                        "IRS EFTPS deposit schedule. The IRS assigns employers to a monthly "
                        "schedule (lookback period tax liability ≤ $50K) or semiweekly schedule "
                        "($50K+). Failure-to-deposit (FTD) penalties escalate: 2% for 1–5 days "
                        "late, 5% for 6–15 days, 10% for >15 days, and 15% for amounts still "
                        "unpaid 10+ days after an IRS notice. New employers default to monthly "
                        "for their first calendar year. EFTPS enrollment is required for all "
                        "federal tax deposits. A common startup mistake: founders remit taxes "
                        "monthly when a semiweekly schedule is required after a fundraise "
                        "increases headcount mid-year."
                    ),
                    severity="medium",
                    recommendation=(
                        "Determine your deposit schedule using the lookback period (four "
                        "quarters ending June 30 of the prior year). Enroll in EFTPS "
                        "(eftps.gov) before the first deposit is due. Use a payroll provider "
                        "(Gusto, Rippling, ADP) that automates EFTPS deposits on the correct "
                        "schedule and recalculates your depositor classification annually "
                        "each November."
                    ),
                    file=file, lineno=lineno, excerpt=stripped[:200],
                ))

            # Form 3921 / AMT — Series A+: ISO exercises trigger mandatory reporting.
            if _stage_gte(self._stage, "series_a"):
                if _ISO_EXERCISE.search(stripped) and not _FORM_3921.search(ctx):
                    findings.append(self._finding(
                        rule="iso_exercise_no_form_3921",
                        title="ISO exercise without Form 3921 / AMT disclosure",
                        description=(
                            "Incentive stock option (ISO) exercises are being recorded without "
                            "any reference to Form 3921 or alternative minimum tax (AMT) "
                            "considerations. Corporations must file Form 3921 with the IRS and "
                            "furnish a copy to each ISO-exercising employee by January 31. "
                            "Additionally, ISO spread at exercise is an AMT preference item "
                            "for employees — failing to disclose this can expose employees to "
                            "unexpected AMT liability."
                        ),
                        severity="medium",
                        recommendation=(
                            "Generate and file Form 3921 for each ISO exercise (IRS deadline: "
                            "January 31 following exercise). Notify exercising employees of "
                            "their AMT exposure in writing at the time of exercise. Penalties "
                            "for failure to file are $310/form up to $3.282M/year."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §422(d) ISO $100K limit — Series A+: excess ISOs silently become NSOs,
                # converting capital-gain treatment at sale into ordinary income at exercise.
                if _ISO_GRANT.search(stripped) and not _ISO_100K_LIMIT.search(ctx):
                    findings.append(self._finding(
                        rule="iso_grant_no_100k_limit",
                        title="ISO grant without IRC §422(d) $100K annual-limit check",
                        description=(
                            "An incentive stock option (ISO) grant is being created without "
                            "any reference to the §422(d) annual $100,000 limit. IRC §422(d) "
                            "caps the aggregate FMV of stock (measured at grant date) that may "
                            "first become exercisable under all ISOs held by one employee in "
                            "any calendar year at $100,000. Options exceeding this cap "
                            "automatically convert to NSOs — employees lose the capital-gains "
                            "deferral benefit and instead owe ordinary income tax at exercise, "
                            "and the company must include the spread in W-2 wages."
                        ),
                        severity="medium",
                        recommendation=(
                            "Before each ISO grant, compute the cumulative FMV of all unvested "
                            "ISOs scheduled to first become exercisable in the same calendar year "
                            "for that employee. If the new grant would push the total above "
                            "$100,000, split the excess into NSOs. Cap table systems such as "
                            "Carta can automate this check; manual grants in code should "
                            "explicitly assert the limit."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §409A on non-stock deferred comp — Series A+: severance and bonus
                # deferral plans fall under §409A just as stock options do.
                if _DEFERRED_COMP.search(stripped) and not _409A_DEFERRED.search(ctx):
                    findings.append(self._finding(
                        rule="deferred_comp_no_409a",
                        title="Severance or deferred-compensation code without IRC §409A compliance",
                        description=(
                            "Severance agreements, deferred bonuses, or separation payments are "
                            "being handled without any reference to IRC §409A. §409A applies to "
                            "all non-qualified deferred compensation — not just stock options — "
                            "and requires a fixed payment schedule, permissible distribution "
                            "triggers (separation from service, disability, death, change of "
                            "control, fixed date), and a 6-month delay for specified employees. "
                            "Non-compliant plans result in immediate income inclusion, a 20% "
                            "excise tax, and interest for the employee; companies face 20% "
                            "withholding liability on the entire deferred amount."
                        ),
                        severity="high",
                        recommendation=(
                            "Review all severance and bonus-deferral agreements with tax counsel "
                            "to confirm they either qualify for the short-term deferral exception "
                            "(payment within 2½ months of year-end) or are structured with §409A-"
                            "compliant payment triggers and schedules. Severance payable only on "
                            "involuntary termination may qualify for the separation-pay exception; "
                            "all other arrangements need a formal §409A compliance analysis."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # ESPP Form 3922 — Series A+: each ESPP stock transfer requires
                # a Form 3922 filed by January 31; the transfer record is the only
                # contemporaneous documentation that determines the sale's tax treatment.
                if _ESPP_ACTIVITY.search(stripped) and not _FORM_3922.search(ctx):
                    findings.append(self._finding(
                        rule="espp_no_form_3922",
                        title="ESPP activity without Form 3922 transfer-reporting reference",
                        description=(
                            "Employee Stock Purchase Plan (ESPP) activity is present without "
                            "any reference to Form 3922. Corporations must file Form 3922 with "
                            "the IRS and furnish a copy to each employee for every transfer of "
                            "stock under a §423(b) ESPP, by January 31 of the year following "
                            "the transfer. Unlike ISOs, the qualifying vs. disqualifying "
                            "disposition determination happens at sale, making the Form 3922 "
                            "transfer record the sole contemporaneous basis for the employee's "
                            "eventual tax treatment. Failure to file: $310/form, up to $3.282M/year."
                        ),
                        severity="medium",
                        recommendation=(
                            "Generate Form 3922 for every ESPP purchase date and file with the "
                            "IRS by January 31 of the following year. Furnish copies to employees "
                            "by the same deadline. Store transfer records (purchase date, FMV at "
                            "purchase, FMV at offering, purchase price) permanently — employees "
                            "may need them years later when they sell."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

            # Wayfair sales tax nexus — Series B+: economic nexus in 45 states.
            if _stage_gte(self._stage, "series_b"):
                if _PAYMENT_PROCESSING.search(stripped) and not _SALES_TAX.search(ctx):
                    findings.append(self._finding(
                        rule="payment_processing_no_sales_tax",
                        title="Payment processing without sales-tax / economic-nexus handling",
                        description=(
                            "Billing or checkout code is present without evidence of sales tax "
                            "calculation or nexus tracking. Following South Dakota v. Wayfair "
                            "(2018), 45 states + DC impose economic nexus thresholds — typically "
                            "$100K in annual revenue or 200 transactions per state — requiring "
                            "sales tax collection without physical presence. SaaS products are "
                            "taxable in many states as electronically delivered services."
                        ),
                        severity="medium",
                        recommendation=(
                            "Integrate a tax-calculation service (Avalara AvaTax, TaxJar, or "
                            "Stripe Tax) to determine per-state tax obligations in real time. "
                            "Register for a sales tax permit in each nexus state before "
                            "collecting. Review product taxability by state — software-as-a-service "
                            "treatment varies significantly."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # FBAR / FATCA — Series B+: foreign accounts above $10K aggregate.
                if _INTL_PAYMENT.search(stripped) and not _FBAR_CONTROLS.search(ctx):
                    findings.append(self._finding(
                        rule="intl_transfer_no_fbar",
                        title="International wire transfer without FBAR / FATCA compliance signals",
                        description=(
                            "International payment or wire transfer code is present without "
                            "reference to FBAR (FinCEN 114), FATCA (Form 8938), or OFAC "
                            "sanctions screening. If aggregate foreign bank account balances "
                            "exceed $10,000 at any point during the year, FinCEN 114 must be "
                            "filed by April 15 (auto-extended to October 15). Form 8938 applies "
                            "at higher thresholds. Willful non-filing carries civil penalties "
                            "of the greater of $100,000 or 50% of account balance per violation."
                        ),
                        severity="high",
                        recommendation=(
                            "Add OFAC sanctions screening before initiating any international "
                            "wire transfer. Maintain a register of all foreign bank accounts "
                            "and automate FinCEN 114 / Form 8938 filing reminders. Consult a "
                            "tax advisor on FBAR aggregation rules across all controlled entities "
                            "and subsidiaries."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §382 NOL limitation — Series B+: equity financing rounds can trigger
                # ownership changes that cap annual NOL utilization permanently.
                if _NOL_TRACKING.search(stripped) and not _NOL_382.search(ctx):
                    findings.append(self._finding(
                        rule="nol_no_382_limit",
                        title="NOL carryforward tracked without IRC §382 ownership-change limitation",
                        description=(
                            "Net operating loss (NOL) carryforwards are being tracked without "
                            "reference to IRC §382 limitations. When a company undergoes an "
                            "\"ownership change\" (more than 50-percentage-point shift in "
                            "ownership over a rolling 3-year period), §382 permanently caps the "
                            "annual amount of pre-change NOLs that can offset taxable income to "
                            "the product of the entity value and the long-term tax-exempt rate. "
                            "Each financing round is a potential ownership change trigger."
                        ),
                        severity="medium",
                        recommendation=(
                            "Perform a §382 ownership-change study after each equity financing "
                            "round and annually. Maintain a capitalization table with historical "
                            "ownership percentages for all 5%-or-greater shareholders. Record "
                            "the §382 annual limitation in your tax provision; work with a tax "
                            "advisor before utilizing NOL carryforwards on any tax return."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §41 R&D Credit — Series B+: qualifying research expenses need contemporaneous
                # documentation; §174 amortization now mandatory (TCJA 2017, effective 2022).
                if _RD_EXPENSE.search(stripped) and not _RD_CREDIT.search(ctx):
                    findings.append(self._finding(
                        rule="rd_expense_no_credit_tracking",
                        title="R&D expense tracked without IRC §41 research credit documentation",
                        description=(
                            "Research or development expenses are present without reference to "
                            "the IRC §41 R&D Tax Credit or §174 amortization rules. The §41 "
                            "credit provides up to 20% of qualified research expenses (QREs) "
                            "above a computed base amount and requires contemporaneous "
                            "documentation of qualified research activities, employee time, "
                            "supplies, and contract research costs. As of 2022, §174 requires "
                            "5-year domestic / 15-year foreign amortization of R&D expenditures "
                            "rather than immediate expensing."
                        ),
                        severity="low",
                        recommendation=(
                            "Implement a QRE tracking system that captures employee time on "
                            "qualifying research projects, supply costs, and contract research "
                            "payments. File Form 6765 to claim the credit. Document the four-part "
                            "§41 test for each activity: (1) permitted purpose, (2) technological "
                            "uncertainty, (3) process of experimentation, (4) technological nature."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §280G / §4999 golden parachute — Series B+: change-of-control payments
                # over 3× base comp trigger a 20% excise tax and lose deductibility.
                if _CHANGE_OF_CONTROL.search(stripped) and not _PARACHUTE_CONTROLS.search(ctx):
                    findings.append(self._finding(
                        rule="change_of_control_no_280g",
                        title="Change-of-control acceleration without IRC §280G analysis",
                        description=(
                            "Change-of-control triggers — including equity acceleration, "
                            "severance, and bonus payments — are present without reference to "
                            "IRC §280G or §4999. If the total value of payments to a "
                            "\"disqualified individual\" (officer, 1% shareholder, or highly "
                            "compensated employee) exceeds 3× their average annual compensation "
                            "(base amount), the excess is a non-deductible \"excess parachute "
                            "payment\" and the recipient owes a 20% excise tax on top of "
                            "ordinary income tax. This is commonly triggered by equity "
                            "acceleration on acquisition and can cost founders and executives "
                            "hundreds of thousands of dollars in unexpected taxes."
                        ),
                        severity="high",
                        recommendation=(
                            "Before finalizing any change-of-control provisions, run a §280G "
                            "calculation to identify potential excess parachute payments. For "
                            "private companies, consider a shareholder safe-harbor vote under "
                            "§280G(b)(5): with 75% shareholder approval after proper disclosure, "
                            "all parachute payments are excluded from §280G. Structure equity "
                            "acceleration as double-trigger where possible to reduce the value "
                            "counted as a parachute payment."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # §482 transfer pricing — Series B+: every related-party transaction
                # must use arm's-length pricing with contemporaneous documentation.
                if _INTERCOMPANY_TX.search(stripped) and not _TRANSFER_PRICING.search(ctx):
                    findings.append(self._finding(
                        rule="intercompany_no_transfer_pricing",
                        title="Intercompany transaction without IRC §482 transfer-pricing documentation",
                        description=(
                            "Intercompany or related-party transactions are being handled without "
                            "reference to IRC §482 transfer pricing. Every transaction between "
                            "a US parent and a related foreign or domestic entity — including IP "
                            "licensing, management fees, intercompany loans, and cost-sharing "
                            "arrangements — must be priced at arm's length per §482. The IRS can "
                            "reallocate income across entities if pricing deviates from the arm's-"
                            "length standard, and penalties for underpayment range from 20% to 40% "
                            "of the tax understated, plus interest."
                        ),
                        severity="high",
                        recommendation=(
                            "Prepare contemporaneous §482 transfer-pricing documentation before "
                            "filing the first tax return that includes the intercompany transaction. "
                            "The documentation must identify the 'best method' (CUP, RPM, TNMM, etc.), "
                            "benchmark the arm's-length range, and be maintained as a permanent "
                            "record. Intercompany agreements should be in writing and executed before "
                            "the transactions occur. Work with a transfer-pricing specialist."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # GILTI / Subpart F §951A — Series B+: US shareholders of CFCs must
                # include foreign subsidiary income in US gross income annually.
                if _FOREIGN_SUBSIDIARY.search(stripped) and not _GILTI_CONTROLS.search(ctx):
                    findings.append(self._finding(
                        rule="foreign_subsidiary_no_gilti",
                        title="Foreign subsidiary income without GILTI (§951A) / Subpart F analysis",
                        description=(
                            "Foreign subsidiary or CFC income is being tracked without reference "
                            "to GILTI (IRC §951A) or Subpart F (IRC §951). If the company owns "
                            "≥10% of a Controlled Foreign Corporation (CFC), GILTI requires US "
                            "shareholders to include the CFC's 'global intangible low-taxed income' "
                            "in gross income each year, regardless of whether earnings are distributed. "
                            "Subpart F similarly captures passive and related-party income. Form 5471 "
                            "must be filed for each CFC, with penalties of $10,000–$50,000 per missed "
                            "filing."
                        ),
                        severity="high",
                        recommendation=(
                            "For each foreign subsidiary, determine whether it qualifies as a CFC "
                            "(US shareholders owning ≥10% controlling ≥50%). File Form 5471 annually "
                            "for every CFC. Compute the GILTI inclusion and the associated deemed-paid "
                            "foreign tax credit (§960). Consider making the §962 election to apply "
                            "corporate rates, or the §951A high-tax exclusion election if the CFC "
                            "pays foreign tax at ≥90% of the US rate."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

            # §162(m) exec comp deduction limit — Series C+.
            if _stage_gte(self._stage, "series_c_plus"):
                if _EXEC_COMP.search(stripped) and not _COMP_162M.search(ctx):
                    findings.append(self._finding(
                        rule="exec_comp_no_162m",
                        title="Executive compensation without IRC §162(m) deduction-limit analysis",
                        description=(
                            "Executive compensation is being set or tracked without reference to "
                            "IRC §162(m), which permanently caps the tax deduction for "
                            "\"covered employee\" compensation at $1,000,000. Post-TCJA (2018), "
                            "the performance-based compensation exception is eliminated, and the "
                            "covered employee list is permanent (once covered, always covered — "
                            "including post-termination). Pre-IPO compensation decisions lock in "
                            "future deductibility; misstructured equity packages can create "
                            "permanent deduction losses worth millions."
                        ),
                        severity="medium",
                        recommendation=(
                            "Identify all current and prospective covered employees (CEO, CFO, "
                            "and the three highest-paid officers). Model §162(m) deductibility "
                            "for each compensation element — base, bonus, equity. Structure "
                            "equity grants with vesting schedules that defer income recognition. "
                            "Consult tax counsel before finalizing any executive comp package "
                            "above the $1M threshold."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # ASC 606 / IRC §451 revenue recognition — Series C+: the five-step
                # model governs both GAAP and taxable income recognition post-TCJA.
                if _REVENUE_RECOGNITION.search(stripped) and not _ASC_606_CONTROLS.search(ctx):
                    findings.append(self._finding(
                        rule="revenue_no_asc606",
                        title="Revenue recognition code without ASC 606 / IRC §451 framework reference",
                        description=(
                            "Revenue is being recognized or deferred without reference to ASC 606 "
                            "or IRC §451. ASC 606 requires revenue to be recognized when (or as) "
                            "performance obligations are satisfied under the five-step model: "
                            "(1) identify the contract, (2) identify performance obligations, "
                            "(3) determine transaction price, (4) allocate to obligations, "
                            "(5) recognize when satisfied. IRC §451(b) now generally requires "
                            "taxable income recognition no later than the financial-statement "
                            "recognition date, meaning ASC 606 errors flow directly into the "
                            "tax return. Multi-year SaaS contracts with implementation fees or "
                            "usage-based pricing are especially prone to misclassification."
                        ),
                        severity="medium",
                        recommendation=(
                            "Document the ASC 606 performance obligation analysis for each "
                            "material revenue stream (subscription, professional services, usage). "
                            "Reconcile deferred revenue balances on the balance sheet to "
                            "performance obligation schedules. Confirm that the tax return "
                            "revenue recognition policy is aligned with ASC 606 per IRC §451(b). "
                            "Engage a Big 4 or boutique technical accounting firm for the "
                            "initial adoption review if not already completed."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

                # IRC §163(j) business interest limitation — Series C+: post-2021,
                # ATI excludes D&A add-backs, making the cap significantly tighter.
                if _INTEREST_EXPENSE.search(stripped) and not _163J_CONTROLS.search(ctx):
                    findings.append(self._finding(
                        rule="interest_expense_no_163j",
                        title="Business interest expense without IRC §163(j) limitation analysis",
                        description=(
                            "Business interest expense is being recorded or deducted without "
                            "reference to the IRC §163(j) limitation. Post-TCJA, the deduction "
                            "for business interest expense is limited to 30% of \"adjusted "
                            "taxable income\" (ATI). Since 2022, ATI is computed on an EBIT "
                            "basis (depreciation and amortization add-backs removed), not EBITDA, "
                            "substantially reducing the cap for companies with significant D&A. "
                            "Disallowed interest becomes a carryforward but cannot be deducted "
                            "until a future year with sufficient ATI capacity."
                        ),
                        severity="medium",
                        recommendation=(
                            "Compute the §163(j) limitation before finalizing the tax return: "
                            "30% × ATI (EBIT basis post-2021). Track the interest carryforward "
                            "balance separately from NOL carryforwards. If the company has "
                            "venture debt or a credit facility, model the §163(j) impact on "
                            "net deductibility across the debt term. Consider whether the real "
                            "property or farming trade/business elections apply to remove "
                            "certain operations from the §163(j) limit."
                        ),
                        file=file, lineno=lineno, excerpt=stripped[:200],
                    ))

        return findings

    def _finding(
        self,
        *,
        rule: str,
        title: str,
        description: str,
        severity: Severity,
        recommendation: str,
        file,
        lineno: int,
        excerpt: str,
    ) -> Finding:
        return Finding(
            id=stable_finding_id(self.id, rule, f"{file.path}:{lineno}"),
            title=title,
            description=description,
            category="financial_compliance",
            severity=severity,
            confidence="medium",
            evidence=[
                FindingEvidence(
                    location=SourceLocation(path=file.path, line_start=lineno),
                    description=f"Matched {rule} pattern at stage={self._stage}.",
                    excerpt=excerpt,
                )
            ],
            recommendation=recommendation,
            scanner_id=self.id,
            scanner_version=self.version,
        )
