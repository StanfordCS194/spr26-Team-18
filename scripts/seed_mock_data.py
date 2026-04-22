"""Populate the Legi-Bill DB with mock California environmental bills.

Useful for demoing the Streamlit UI without running the LegiScan scraper or
burning Anthropic API credits. Safe to re-run: all inserts are upserts.

Usage:
    python scripts/seed_mock_data.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legi_bill.models import Bill, BillSummary, ComplianceQuestion
from legi_bill.storage import (
    init_db,
    insert_compliance_questions,
    upsert_bill,
    upsert_summary,
)

DEFAULT_DB_PATH = "~/.legi_bill/bills.db"
MOCK_MODEL = "mock-seed-data"


MOCK_BILLS = [
    {
        "bill": Bill(
            bill_id=900253,
            bill_number="SB-253",
            title="Climate Corporate Data Accountability Act",
            description=(
                "Requires large US companies doing business in California with "
                "over $1 billion in annual revenue to publicly disclose Scope 1, "
                "Scope 2, and Scope 3 greenhouse gas emissions."
            ),
            state="CA",
            status="Chaptered",
            session_year=2023,
            url="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB253",
            subjects=["Climate Change", "Air Pollution", "Public Health"],
        ),
        "summary": (
            "This bill requires any US company with more than $1 billion in "
            "annual revenue that does business in California to publicly report "
            "its greenhouse gas emissions each year. Companies must disclose "
            "direct emissions (Scope 1), emissions from purchased energy "
            "(Scope 2), and emissions from their supply chain and customers "
            "(Scope 3). Reports go to a nonprofit emissions reporting "
            "organization and must be independently verified. The first Scope "
            "1 and 2 reports are due starting in 2026, with Scope 3 reports "
            "beginning in 2027. Who it affects: private and public companies "
            "over the revenue threshold, regardless of where they are "
            "headquartered, if they operate in California. Penalties for "
            "noncompliance can reach $500,000 per reporting year. Current "
            "status: signed into law; the California Air Resources Board is "
            "finalizing implementing regulations."
        ),
        "questions": [
            "Does your company have more than $1B in annual revenue and any operations, employees, or customers in California?",
            "Have you already calculated Scope 1 and Scope 2 emissions for at least the most recent fiscal year?",
            "Do you have visibility into Scope 3 emissions across your supply chain and downstream product use?",
            "Is your emissions data ready for third-party assurance or verification?",
            "Have you budgeted for annual public emissions reporting and potential penalties of up to $500,000?",
        ],
    },
    {
        "bill": Bill(
            bill_id=900261,
            bill_number="SB-261",
            title="Greenhouse gases: climate-related financial risk",
            description=(
                "Requires companies doing business in California with revenue "
                "over $500 million to prepare biennial climate-related "
                "financial risk reports aligned with TCFD recommendations."
            ),
            state="CA",
            status="Chaptered",
            session_year=2023,
            url="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240SB261",
            subjects=["Climate Change", "Public Health"],
        ),
        "summary": (
            "This bill requires any company with more than $500 million in "
            "annual revenue that does business in California to publish a "
            "climate-related financial risk report every two years. The "
            "report must describe the company's climate-related risks — such "
            "as physical damage from extreme weather or transition risks from "
            "regulatory change — and the steps it is taking to reduce and "
            "adapt to those risks. Reports must be publicly posted on the "
            "company's website. Who it affects: any company over the revenue "
            "threshold, including subsidiaries and partnerships, that has "
            "operations in California. Reports are due beginning January 1, "
            "2026. Current status: signed into law; enforcement and reporting "
            "format guidance is being developed."
        ),
        "questions": [
            "Does your company exceed $500M in annual revenue with any California operations?",
            "Have you conducted a climate scenario analysis or TCFD-aligned risk assessment in the past two years?",
            "Do you have documented mitigation and adaptation plans for identified climate risks?",
            "Is there an owner within the company responsible for publishing and updating the biennial report?",
            "Have your risk disclosures been reviewed by legal counsel for consistency with SEC and other filings?",
        ],
    },
    {
        "bill": Bill(
            bill_id=901279,
            bill_number="AB-1279",
            title="California Climate Crisis Act",
            description=(
                "Establishes statewide policy to achieve net-zero greenhouse "
                "gas emissions by 2045 and reduce emissions 85% below 1990 "
                "levels by that date."
            ),
            state="CA",
            status="Chaptered",
            session_year=2022,
            url="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202120220AB1279",
            subjects=["Climate Change", "Energy", "Air Pollution"],
        ),
        "summary": (
            "This bill writes into state law a target of net-zero greenhouse "
            "gas emissions across California by 2045, with an interim goal of "
            "cutting emissions at least 85% below 1990 levels by the same "
            "date. The California Air Resources Board is required to update "
            "its Scoping Plan to lay out how the state will hit these targets, "
            "and to identify strategies for removing carbon from the "
            "atmosphere. Who it affects: utilities, large industrial emitters, "
            "transportation fleet operators, building owners, and any company "
            "subject to California's cap-and-trade program. Key deadlines: "
            "CARB Scoping Plan updates every five years; net-zero target by "
            "2045. Current status: signed into law and in effect; most "
            "compliance obligations flow through downstream CARB regulations."
        ),
        "questions": [
            "Is your company subject to California's cap-and-trade program or large facility reporting rules?",
            "Have you set internal emissions reduction targets aligned with a net-zero-by-2045 trajectory?",
            "Do you operate vehicle fleets or buildings in California that will be affected by CARB Scoping Plan measures?",
            "Have you evaluated the cost of purchasing offsets or carbon removal credits to meet future caps?",
            "Is your capital planning process accounting for accelerated electrification and fuel-switching deadlines?",
        ],
    },
    {
        "bill": Bill(
            bill_id=900054,
            bill_number="SB-54",
            title=(
                "Plastic Pollution Prevention and Packaging Producer "
                "Responsibility Act"
            ),
            description=(
                "Requires producers of single-use packaging and plastic food "
                "service ware to ensure that all covered material is "
                "recyclable or compostable by 2032, with source reduction and "
                "recycling rate targets."
            ),
            state="CA",
            status="Chaptered",
            session_year=2022,
            url="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202120220SB54",
            subjects=[
                "Environmental Safety and Toxic Materials",
                "Natural Resources",
            ],
        ),
        "summary": (
            "This bill places responsibility for plastic packaging waste on "
            "the producers that create it. By 2032, all single-use packaging "
            "and plastic food service ware sold or distributed in California "
            "must be recyclable or compostable. Producers must also cut "
            "plastic packaging by 25% (by weight and by item count) and hit a "
            "65% recycling rate for plastic covered material. A Producer "
            "Responsibility Organization (PRO) collects fees from producers to "
            "fund recycling infrastructure and environmental mitigation. Who "
            "it affects: manufacturers, brand owners, and importers of "
            "consumer-packaged goods sold in California; food service "
            "operators; online retailers shipping into the state. Key "
            "deadlines: PRO registration; annual source reduction reporting; "
            "full compliance by 2032. Current status: in effect; CalRecycle "
            "is building out implementing regulations and PRO approval."
        ),
        "questions": [
            "Does your company manufacture, import, or sell goods with single-use plastic packaging in California?",
            "Have you joined or begun engagement with the state-approved Producer Responsibility Organization?",
            "Do you have a plan to make all covered packaging recyclable or compostable by 2032?",
            "Have you modeled the financial impact of PRO fees on your California packaging SKUs?",
            "Is your packaging supply chain tracking the data CalRecycle will require for annual reports?",
        ],
    },
    {
        "bill": Bill(
            bill_id=901137,
            bill_number="SB-1137",
            title=(
                "Health and Safety Code: oil and gas operations: location "
                "restrictions"
            ),
            description=(
                "Prohibits new oil and gas production wells and certain "
                "operations within 3,200 feet of homes, schools, health "
                "facilities, and other sensitive receptors."
            ),
            state="CA",
            status="Chaptered",
            session_year=2022,
            url="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202120220SB1137",
            subjects=["Public Health", "Energy", "Land Use and Planning"],
        ),
        "summary": (
            "This bill creates a 3,200-foot setback between new oil and gas "
            "production wells and homes, schools, day cares, health "
            "facilities, prisons, and similar sensitive sites. Within the "
            "setback zone, new wells cannot be permitted, and existing wells "
            "face additional pollution controls — leak detection, noise and "
            "light mitigation, and emissions monitoring — enforced by the "
            "state's oil and gas regulator. Who it affects: upstream oil and "
            "gas operators with California production assets, midstream "
            "service providers, and landowners near existing operations. Key "
            "deadlines: setback applies to new permits immediately; existing "
            "wells must meet enhanced operating requirements on a staggered "
            "schedule. Current status: signed into law and upheld by voters "
            "in a 2024 referendum; CalGEM is rolling out implementing rules."
        ),
        "questions": [
            "Does your company operate or hold leases on oil and gas wells in California?",
            "Do any of your existing wells fall within 3,200 feet of a residence, school, or health facility?",
            "Have you budgeted for enhanced leak detection, emissions monitoring, and mitigation equipment?",
            "Have you updated your permit pipeline to account for the ban on new wells in setback zones?",
            "Are your landowner and community disclosures aligned with the bill's notice requirements?",
        ],
    },
    {
        "bill": Bill(
            bill_id=900841,
            bill_number="AB-841",
            title="Energy: transportation electrification: school buses",
            description=(
                "Directs investor-owned utilities to prioritize transportation "
                "electrification investments, with dedicated funding for "
                "zero-emission school buses in disadvantaged communities."
            ),
            state="CA",
            status="Chaptered",
            session_year=2020,
            url="https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=201920200AB841",
            subjects=["Energy", "Air Pollution", "Public Health"],
        ),
        "summary": (
            "This bill steers California's investor-owned utilities toward "
            "faster transportation electrification. It requires utilities to "
            "propose infrastructure investments — charging equipment, "
            "distribution upgrades, and customer rebates — that support the "
            "state's zero-emission vehicle goals, with priority for "
            "commercial fleets, school buses, and disadvantaged communities. "
            "A dedicated program funds the replacement of diesel school buses "
            "with zero-emission models and the associated charging "
            "infrastructure. Who it affects: electric utilities, school "
            "districts, transit agencies, and companies running commercial "
            "vehicle fleets in California. Key deadlines: utility program "
            "filings at the California Public Utilities Commission; annual "
            "school bus replacement grant cycles. Current status: in effect; "
            "funding continues through CPUC-approved programs."
        ),
        "questions": [
            "Does your company operate commercial or medium/heavy-duty vehicle fleets served by a California investor-owned utility?",
            "Have you evaluated utility rebate and make-ready programs that could offset charging infrastructure costs?",
            "Are your depots and routes located in communities flagged as disadvantaged for priority funding?",
            "Do you have an internal fleet electrification plan with timelines aligned to state ZEV targets?",
            "Have you coordinated with your utility on distribution upgrades needed for fleet charging loads?",
        ],
    },
]


def seed(db_path: str) -> int:
    conn = init_db(db_path)
    for entry in MOCK_BILLS:
        bill = entry["bill"]
        upsert_bill(conn, bill)

        upsert_summary(
            conn,
            BillSummary(
                bill_id=bill.bill_id,
                summary_text=entry["summary"],
                model_used=MOCK_MODEL,
                cache_hit=False,
                input_tokens=0,
                output_tokens=0,
            ),
        )

        insert_compliance_questions(
            conn,
            bill.bill_id,
            [
                ComplianceQuestion(
                    bill_id=bill.bill_id,
                    question_number=i + 1,
                    question_text=q,
                )
                for i, q in enumerate(entry["questions"])
            ],
        )
    return len(MOCK_BILLS)


def main():
    db_path = str(
        Path(os.getenv("LEGI_BILL_DB_PATH", DEFAULT_DB_PATH)).expanduser()
    )
    count = seed(db_path)
    print(f"Seeded {count} mock bills into {db_path}")


if __name__ == "__main__":
    main()
