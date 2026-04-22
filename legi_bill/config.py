import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LEGISCAN_BASE_URL = "https://api.legiscan.com/"
CLAUDE_MODEL = "claude-sonnet-4-6"
DEFAULT_STATE = "CA"
REQUEST_DELAY_SECONDS = 0.5

ENVIRONMENTAL_KEYWORDS = [
    "environment",
    "climate",
    "emissions",
    "carbon",
    "pollution",
    "water quality",
    "air quality",
    "CEQA",
    "clean energy",
    "renewable",
    "greenhouse gas",
    "hazardous waste",
    "pesticide",
    "biodiversity",
    "wildfire",
    "drought",
    "toxic",
    "landfill",
    "recycling",
    "sea level",
]

ENVIRONMENTAL_SUBJECTS = {
    "Natural Resources",
    "Environmental Safety and Toxic Materials",
    "Climate Change",
    "Water",
    "Energy",
    "Air Pollution",
    "Agriculture",
    "Public Health",
    "Forestry and Forest Products",
    "Fish and Wildlife",
    "Land Use and Planning",
}

SUMMARY_SYSTEM_PROMPT = (
    "You are a nonpartisan legislative analyst specializing in California "
    "environmental law. Your task is to produce plain-language summaries of "
    "California environmental bills for a general business audience. "
    "Summaries must be:\n"
    "- Factually accurate and neutral in tone\n"
    "- Written at an 8th-grade reading level\n"
    "- Between 150 and 250 words\n"
    "- Structured as: (1) What the bill does, (2) Who it affects, "
    "(3) Key requirements or deadlines, (4) Current status\n"
    "Do not include your own opinion or predict passage likelihood."
)

COMPLIANCE_QUESTIONS_PROMPT = (
    "Based on this bill, generate exactly 5 yes/no or short-answer "
    "compliance questions that a business compliance officer should ask "
    "to determine whether this bill affects their company's operations. "
    "Format as a numbered list. Each question must be specific to the "
    "bill's requirements — no generic questions."
)


def load_config() -> dict:
    legiscan_key = os.getenv("LEGISCAN_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not legiscan_key:
        raise EnvironmentError(
            "LEGISCAN_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    if not anthropic_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    raw_db_path = os.getenv("LEGI_BILL_DB_PATH", "~/.legi_bill/bills.db")
    db_path = str(Path(raw_db_path).expanduser())
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    return {
        "legiscan_api_key": legiscan_key,
        "anthropic_api_key": anthropic_key,
        "db_path": db_path,
    }
