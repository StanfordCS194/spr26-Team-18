"""Legal cost savings calculator.

Detects company industry from free text, applies state-specific rate
adjustments, and builds a line-item estimate of what a compliance lawyer
would bill for the same work Legi-Bill automates.

Rate data: 2024 Clio Legal Trends Report, ABA Legal Technology Survey,
BLS Occupational Employment Statistics (lawyers, May 2023).
State multipliers: BLS regional wage indices for legal occupations.
"""
from __future__ import annotations
import re
from typing import Optional

# ── California legislative volume (2023-24 session) ──────────────────────────
# Source: Capitol Weekly, "Some statistics from the 2023-24 legislative session"
#         CalMatters / LAist — bills signed by Governor Newsom, 2023 and 2024
CA_BILLS_INTRODUCED = 4_821   # total bills introduced across both years
CA_BILLS_SIGNED     = 1_684   # signed into law (890 in 2023 + 794 in 2024)

INDUSTRY_RATES: dict[str, dict] = {
    "environmental": {"label": "Environmental Attorney",                  "rate": 425},
    "finance":       {"label": "Securities & Finance Counsel",            "rate": 595},
    "healthcare":    {"label": "Healthcare Regulatory Attorney",          "rate": 480},
    "tech":          {"label": "Technology & IP Counsel",                 "rate": 460},
    "manufacturing": {"label": "Product Liability & Regulatory Counsel",  "rate": 390},
    "retail":        {"label": "Consumer Goods Attorney",                 "rate": 365},
    "real_estate":   {"label": "Real Estate Counsel",                     "rate": 340},
    "agriculture":   {"label": "Agriculture & Food Regulatory Attorney",  "rate": 355},
    "general":       {"label": "General Corporate Counsel",               "rate": 410},
}

# Annual compliance legal-spend benchmarks for small-to-mid companies.
# Source: Thomson Reuters Legal Tracker 2023, ACC Chief Legal Officer Survey 2024.
INDUSTRY_BENCHMARKS: dict[str, dict] = {
    "environmental": {"low": 35_000,  "high": 65_000,  "note": "for ongoing environmental compliance counsel"},
    "finance":       {"low": 60_000,  "high": 120_000, "note": "for securities & regulatory compliance"},
    "healthcare":    {"low": 50_000,  "high": 90_000,  "note": "for healthcare regulatory matters"},
    "tech":          {"low": 30_000,  "high": 60_000,  "note": "for technology regulatory & IP compliance"},
    "manufacturing": {"low": 35_000,  "high": 70_000,  "note": "for product liability & regulatory work"},
    "retail":        {"low": 25_000,  "high": 50_000,  "note": "for consumer goods regulatory compliance"},
    "real_estate":   {"low": 20_000,  "high": 45_000,  "note": "for real estate regulatory compliance"},
    "agriculture":   {"low": 20_000,  "high": 40_000,  "note": "for agricultural & food regulatory compliance"},
    "general":       {"low": 25_000,  "high": 55_000,  "note": "for general corporate compliance counsel"},
}

# Rate multipliers relative to national baseline (1.00).
# Source: BLS Occupational Employment & Wage Statistics, lawyers (SOC 23-1011), May 2023.
STATE_MULTIPLIERS: dict[str, float] = {
    "AL": 0.75, "AK": 0.95, "AZ": 0.87, "AR": 0.72, "CA": 1.30,
    "CO": 1.00, "CT": 1.15, "DE": 1.05, "FL": 0.88, "GA": 0.83,
    "HI": 1.10, "ID": 0.80, "IL": 1.05, "IN": 0.80, "IA": 0.78,
    "KS": 0.78, "KY": 0.76, "LA": 0.80, "ME": 0.85, "MD": 1.10,
    "MA": 1.20, "MI": 0.85, "MN": 0.95, "MS": 0.72, "MO": 0.83,
    "MT": 0.80, "NE": 0.82, "NV": 0.92, "NH": 0.95, "NJ": 1.18,
    "NM": 0.80, "NY": 1.25, "NC": 0.83, "ND": 0.80, "OH": 0.85,
    "OK": 0.78, "OR": 1.00, "PA": 0.92, "RI": 1.00, "SC": 0.78,
    "SD": 0.78, "TN": 0.80, "TX": 0.90, "UT": 0.88, "VT": 0.88,
    "VA": 1.05, "WA": 1.15, "WV": 0.75, "WI": 0.85, "WY": 0.80,
    "DC": 1.35,
}

STATE_LABELS: dict[str, str] = {
    "AL": "Alabama",       "AK": "Alaska",         "AZ": "Arizona",
    "AR": "Arkansas",      "CA": "California",     "CO": "Colorado",
    "CT": "Connecticut",   "DE": "Delaware",        "FL": "Florida",
    "GA": "Georgia",       "HI": "Hawaii",          "ID": "Idaho",
    "IL": "Illinois",      "IN": "Indiana",         "IA": "Iowa",
    "KS": "Kansas",        "KY": "Kentucky",        "LA": "Louisiana",
    "ME": "Maine",         "MD": "Maryland",        "MA": "Massachusetts",
    "MI": "Michigan",      "MN": "Minnesota",       "MS": "Mississippi",
    "MO": "Missouri",      "MT": "Montana",         "NE": "Nebraska",
    "NV": "Nevada",        "NH": "New Hampshire",   "NJ": "New Jersey",
    "NM": "New Mexico",    "NY": "New York",        "NC": "North Carolina",
    "ND": "North Dakota",  "OH": "Ohio",            "OK": "Oklahoma",
    "OR": "Oregon",        "PA": "Pennsylvania",    "RI": "Rhode Island",
    "SC": "South Carolina","SD": "South Dakota",    "TN": "Tennessee",
    "TX": "Texas",         "UT": "Utah",            "VT": "Vermont",
    "VA": "Virginia",      "WA": "Washington",      "WV": "West Virginia",
    "WI": "Wisconsin",     "WY": "Wyoming",         "DC": "Washington D.C.",
}

# Keywords use word-boundary regex matching (\b...\b) so "fund" won't match
# "refund", "plant" won't match "transplant", etc.
_INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "environmental": [
        # Core identity
        "environmental", "clean energy", "cleantech", "clean tech",
        # Energy sources
        "solar", "wind energy", "wind farm", "renewable", "geothermal",
        "hydropower", "biomass", "biofuel",
        # Climate / emissions
        "carbon", "emissions", "greenhouse gas", "net zero", "carbon neutral",
        "carbon offset", "carbon capture", "decarbonization",
        # Clean transport
        "electric vehicle", "ev charging", "charging network", "battery storage",
        # Waste / water
        "waste management", "recycling", "pollution", "water treatment",
        "wastewater", "remediation",
        # Misc
        "sustainability", "climate", "esg", "green building", "leed",
    ],
    "finance": [
        # Core identity
        "finance", "financial", "fintech", "financial services",
        # Banking
        "bank", "banking", "neobank", "credit union",
        # Investment
        "investment", "investing", "investor", "venture capital", "vc", "vc firm",
        "private equity", "pe firm", "growth equity", "series a", "series b",
        "series c", "hedge fund", "mutual fund", "asset management",
        "wealth management", "family office",
        # Markets
        "trading", "securities", "brokerage", "stock", "equity", "derivatives",
        "fixed income", "forex", "foreign exchange",
        # Insurance / lending
        "insurance", "insurtech", "lending", "lender", "mortgage", "credit",
        "underwriting", "reinsurance",
        # Payments / accounting
        "payments", "payroll", "accounting", "cpa", "bookkeeping", "tax advisory",
        "tax firm", "audit", "remittance", "crypto", "blockchain", "defi",
    ],
    "healthcare": [
        # Core identity
        "healthcare", "health care", "health tech", "healthtech", "medtech",
        # Providers
        "hospital", "clinic", "medical practice", "urgent care", "dental",
        "veterinary", "nursing home", "assisted living",
        # Life sciences
        "biotech", "pharmaceutical", "pharma", "drug discovery", "therapeutics",
        "genomics", "clinical trials", "contract research", "cro", "fda",
        # Devices / diagnostics
        "medical device", "diagnostic", "imaging", "laboratory", "pathology",
        # Digital health
        "telemedicine", "telehealth", "mental health", "behavioral health",
        "electronic health record", "ehr", "emr", "health information",
        # Misc
        "wellness", "patient", "patients", "patient care",
        "surgical", "surgery", "organ", "health insurance", "pharmacy",
    ],
    "tech": [
        # Core identity
        "tech company", "technology company", "software company", "software firm",
        "software", "saas", "paas", "iaas",
        # AI / ML
        "artificial intelligence", "machine learning", "deep learning",
        "large language model", "generative ai", "llm", "nlp",
        # Infrastructure
        "cloud", "devops", "infrastructure", "cybersecurity", "network security",
        # Product types
        "platform", "marketplace platform", "developer tools", "api company",
        "mobile app", "web app", "enterprise software", "erp", "crm",
        # Emerging tech
        "ar", "vr", "augmented reality", "virtual reality", "iot",
        "internet of things", "robotics", "automation software", "drone",
        "web3", "nft",
        # General signals (startup/scaleup omitted — too generic across industries)
        "b2b software", "b2c app", "digital product",
        "engineering team", "product company", "tech startup",
    ],
    "manufacturing": [
        # Core identity
        "manufacturing", "manufacturer", "contract manufacturer",
        "industrial", "factory", "production facility", "assembly line",
        # Materials / sectors
        "chemical", "specialty chemical", "steel", "aluminum", "metal",
        "plastics", "rubber", "composites", "textile mill", "paper mill",
        # Verticals
        "automotive", "aerospace", "defense contractor", "semiconductor",
        "electronics manufacturing", "pcb", "circuit board",
        "food processing", "beverage production", "brewing", "distillery",
        # Processes
        "machining", "fabrication", "3d printing", "additive manufacturing",
        "cnc", "injection molding",
    ],
    "retail": [
        # Core identity
        "retail", "retailer", "ecommerce", "e-commerce", "online store",
        "direct to consumer", "dtc",
        # Channels
        "brick and mortar", "omnichannel", "marketplace seller",
        "subscription box", "pop-up",
        # Categories
        "fashion", "apparel", "clothing brand", "footwear", "luxury goods",
        "beauty brand", "cosmetics", "personal care", "skincare",
        "sporting goods", "outdoor gear", "home goods", "furniture",
        "electronics retail", "pet products",
        # Food retail
        "restaurant", "food service", "grocery", "convenience store",
        "food & beverage", "beverage brand", "snack brand", "hospitality",
        # Misc
        "consumer brand", "consumer goods", "merchandise", "wholesale",
    ],
    "real_estate": [
        # Core identity
        "real estate", "commercial real estate", "cre", "realty",
        # Development
        "property developer", "real estate developer", "homebuilder",
        "construction", "general contractor", "subcontractor",
        # Investment
        "reit", "real estate investment", "multifamily", "single family",
        "residential development", "mixed use",
        # Services
        "property management", "facility management", "building management",
        "hoa", "title company", "escrow", "real estate broker",
        "mortgage lender", "appraisal",
        # Architecture
        "architecture firm", "architectural", "interior design",
    ],
    "agriculture": [
        # Core identity
        "agriculture", "agricultural", "agribusiness", "agtech", "ag tech",
        # Farming
        "farm", "farming", "farmer", "ranching", "ranch", "grower",
        "crop production", "harvest", "irrigation",
        # Livestock / aquaculture
        "livestock", "dairy", "poultry", "cattle", "aquaculture",
        "fishing", "seafood",
        # Specialty
        "organic farming", "vertical farming", "hydroponics",
        "precision agriculture", "viticulture", "winery", "orchard",
        # Food supply chain
        "food production", "food supply", "food manufacturer",
        "food safety", "usda", "agricultural commodities",
    ],
}

_LEGAL_TASKS: list[dict] = [
    {
        "category": "Research & Discovery",
        "badge": "Read & indexed by Legi-Bill",
        "tasks": [
            {
                # ~2 min per bill to scan title + subject tags across all introduced bills.
                # Uses CA_BILLS_INTRODUCED (4,821) — the real legislative volume a lawyer faces.
                "name": "Regulatory landscape scan",
                "description": f"Title & subject scan across all {CA_BILLS_INTRODUCED:,} bills introduced in the 2023-24 CA session",
                "base_hours": 8.0,
                "per_bill_hours": 0.033,   # ~2 min per bill
                "use_introduced": True,
            },
            {
                # ~5 min per signed bill to read summary and flag for relevance.
                # Uses CA_BILLS_SIGNED (1,684) — only enacted law needs deeper screening.
                "name": "Bill applicability screening",
                "description": f"Summary review of all {CA_BILLS_SIGNED:,} bills signed into law to flag client-relevant ones",
                "base_hours": 0.0,
                "per_bill_hours": 0.083,   # ~5 min per bill
                "use_signed": True,
            },
            {
                # Deep history review only on relevant bills — uses matched count
                "name": "Legislative history & amendments review",
                "description": "Review bill history, prior versions, and effective dates",
                "base_hours": 2.0,
                "per_bill_hours": 0.2,
                "use_total": False,
            },
            {
                "name": "Deadline & compliance date mapping",
                "description": "Map all enforcement dates, filing windows, and grace periods",
                "base_hours": 1.5,
                "per_bill_hours": 0.1,
                "use_total": False,
            },
        ],
    },
    {
        "category": "Analysis & Documentation",
        "badge": "AI-summarized in seconds",
        "tasks": [
            {
                "name": "Plain-language bill summaries",
                "description": "Write client-readable summaries of every applicable bill",
                "base_hours": 0.0,
                "per_bill_hours": 1.0,
                "use_total": False,
            },
            {
                "name": "Client-specific applicability memo",
                "description": "Legal memo tying each bill to the company's specific operations",
                "base_hours": 4.0,
                "per_bill_hours": 0.3,
                "use_total": False,
            },
            {
                "name": "Compliance gap analysis",
                "description": "Compare current practices to what each regulation requires",
                "base_hours": 6.0,
                "per_bill_hours": 0.0,
            },
            {
                "name": "Risk & penalty exposure report",
                "description": "Quantify potential fines, penalties, and legal liability per bill",
                "base_hours": 4.0,
                "per_bill_hours": 0.0,
            },
        ],
    },
    {
        "category": "Strategic Planning",
        "badge": "Recommendations ready instantly",
        "tasks": [
            {
                "name": "Priority ranking & action plan",
                "description": "Order compliance tasks by urgency and business impact",
                "base_hours": 3.0,
                "per_bill_hours": 0.0,
            },
            {
                "name": "Internal policy recommendations",
                "description": "Draft policy updates needed to achieve compliance",
                "base_hours": 3.5,
                "per_bill_hours": 0.0,
            },
            {
                "name": "Regulatory filing assistance",
                "description": "Review and assist with required regulatory disclosures",
                "base_hours": 2.0,
                "per_bill_hours": 0.0,
            },
        ],
    },
    {
        "category": "Client Communication",
        "badge": "Ongoing monitoring active",
        "tasks": [
            {
                "name": "Initial client consultation",
                "description": "Kickoff meeting to understand company operations and goals",
                "base_hours": 2.0,
                "per_bill_hours": 0.0,
            },
            {
                "name": "Findings presentation & Q&A",
                "description": "Present analysis to leadership; answer follow-up questions",
                "base_hours": 3.0,
                "per_bill_hours": 0.0,
            },
            {
                "name": "Amendment & new-bill monitoring",
                "description": "Ongoing watch for regulatory changes affecting the client",
                "base_hours": 4.0,
                "per_bill_hours": 0.0,
            },
            {
                "name": "Ad-hoc email Q&A",
                "description": "Billed in 15-minute increments throughout the engagement",
                "base_hours": 3.0,
                "per_bill_hours": 0.0,
            },
        ],
    },
]


def detect_industry(text: str) -> str:
    lower = text.lower()
    scores: dict[str, int] = {ind: 0 for ind in _INDUSTRY_KEYWORDS}
    for industry, keywords in _INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, lower):
                scores[industry] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


def calculate_savings(
    matched_bill_count: int,
    industry: str,
    state: Optional[str] = None,
    hourly_rate_override: Optional[float] = None,
) -> dict:
    """Calculate legal savings.

    Scan/screening tasks use real CA legislative volume constants
    (CA_BILLS_INTRODUCED, CA_BILLS_SIGNED) — the actual number of bills
    a lawyer faces, not just our DB size.
    Analysis/deep-dive tasks use matched_bill_count — bills relevant to
    this specific company — so hours vary per company description.
    """
    industry_info = INDUSTRY_RATES.get(industry, INDUSTRY_RATES["general"])
    base_rate = float(industry_info["rate"])

    state_code = (state or "").upper()
    multiplier = STATE_MULTIPLIERS.get(state_code, 1.0)
    state_label = STATE_LABELS.get(state_code, "National average")

    rate = float(hourly_rate_override) if hourly_rate_override else round(base_rate * multiplier, 0)

    benchmark = INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["general"])

    categories = []
    grand_hours = 0.0
    grand_cost = 0.0

    for cat in _LEGAL_TASKS:
        cat_tasks = []
        for task in cat["tasks"]:
            if task.get("use_introduced"):
                count = CA_BILLS_INTRODUCED
            elif task.get("use_signed"):
                count = CA_BILLS_SIGNED
            else:
                count = matched_bill_count
            hours = round(task["base_hours"] + task["per_bill_hours"] * count, 1)
            cost = round(hours * rate, 0)
            grand_hours += hours
            grand_cost += cost
            cat_tasks.append(
                {
                    "name": task["name"],
                    "description": task["description"],
                    "hours": hours,
                    "cost": int(cost),
                }
            )
        categories.append(
            {
                "category": cat["category"],
                "badge": cat["badge"],
                "tasks": cat_tasks,
                "subtotal_hours": round(sum(t["hours"] for t in cat_tasks), 1),
                "subtotal_cost": int(sum(t["cost"] for t in cat_tasks)),
            }
        )

    return {
        "industry": industry,
        "lawyer_title": industry_info["label"],
        "hourly_rate": rate,
        "base_rate": base_rate,
        "state": state_code or None,
        "state_label": state_label,
        "state_multiplier": multiplier,
        "ca_bills_introduced": CA_BILLS_INTRODUCED,
        "ca_bills_signed": CA_BILLS_SIGNED,
        "matched_bill_count": matched_bill_count,
        "total_hours": round(grand_hours, 1),
        "total_cost": int(grand_cost),
        "benchmark_low": benchmark["low"],
        "benchmark_high": benchmark["high"],
        "benchmark_note": benchmark["note"],
        "categories": categories,
    }
