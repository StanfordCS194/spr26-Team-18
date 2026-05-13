import json
from typing import Optional

import streamlit as st
from openai import OpenAI

from app.pdf_utils import extract_text
from legi_bill.config import OPENAI_MODEL, load_config

SYSTEM_PROMPT = """You are a financial compliance analyst assisting a company with IRS-related reporting and tax compliance.

Your task is to analyze the provided financial document or company disclosure text and identify potential IRS compliance risk areas. Focus on:
- corporate tax reporting and filing requirements
- payroll and employment tax withholding/reporting
- information reporting (1099, 1098, 1095, W-2)
- deductions, credits, and tax basis documentation
- record retention and documentation practices
- any indicators of unusual or missing disclosure relevant to IRS compliance

Do not provide tax advice. Instead, identify possible compliance concerns in the document and suggest high-level next steps for further review by a qualified tax professional.

Return ONLY valid JSON following this schema:
{
  "overall_risk": "Low|Moderate|High|Unknown",
  "risk_score": <int 0-100>,
  "summary": "Short summary of the IRS compliance scan.",
  "issues": [
    {
      "area": "Payroll tax | Corporate tax | Reporting | Deductions | Recordkeeping | Other",
      "finding": "What the document suggests might require attention.",
      "recommendation": "High-level next step for review or remediation."
    }
  ],
  "notes": ["Any assumptions or limitations of the analysis."]
}
"""

PROMPT_TEMPLATE = """COMPANY NAME: {company_name}

DOCUMENT TEXT:
{document_text}

Analyze the document and return the JSON payload exactly as described above. If the document has no obvious IRS compliance issues, set overall_risk to \"Low\" and return an empty issues array. If the text is too short to form a useful opinion, set overall_risk to \"Unknown\" and include a note explaining the limitation.
"""


def run_irs_compliance_audit(document_text: str, company_name: Optional[str] = None) -> dict:
    cfg = load_config()
    api_key = cfg.get("openai_api_key", "")
    if not api_key or api_key.startswith("stub"):
        raise ValueError("OPENAI_API_KEY is not configured. Set it in .env to enable IRS compliance auditing.")

    client = OpenAI(api_key=api_key)
    audit_text = document_text.strip()
    if len(audit_text) > 30000:
        audit_text = audit_text[:30000] + "\n\n[TRUNCATED: document exceeded 30,000 characters]"

    prompt = PROMPT_TEMPLATE.format(
        company_name=company_name or "(unspecified)",
        document_text=audit_text,
    )

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def render():
    st.header("Financial Compliance Audit")
    st.caption(
        "Upload a financial document or spreadsheet (PDF, TXT, CSV, Excel) or paste company disclosure text "
        "to get a preliminary IRS compliance risk assessment."
    )

    uploaded = st.file_uploader(
        "Upload financial document (PDF, TXT, CSV, or Excel)",
        type=["pdf", "txt", "csv", "xlsx", "xls"],
    )
    pasted = st.text_area(
        "Or paste financial document text",
        height=220,
        placeholder=(
            "e.g. excerpts from a 10-K, tax disclosure, payroll summary, or "
            "management discussion of accounting policies."
        ),
    )
    company_name = st.text_input("Company name (optional)")

    if not st.button("Run IRS compliance scan", type="primary"):
        st.info("Upload a document or paste text, then click the button to analyze.")
        return

    document_text = ""
    if uploaded is not None:
        try:
            document_text = extract_text(uploaded)
        except Exception as exc:
            st.error(f"Could not read uploaded file: {exc}")
            return
        if not document_text.strip():
            st.warning(
                "Could not extract any text from the uploaded file. If this is a scanned PDF, try pasting the text instead."
            )
            return
    elif pasted.strip():
        document_text = pasted
    else:
        st.warning("Please upload a document or paste text first.")
        return

    with st.spinner("Analyzing IRS compliance risk..."):
        try:
            result = run_irs_compliance_audit(document_text, company_name=company_name)
        except Exception as exc:
            st.error(f"IRS compliance audit failed: {exc}")
            return

    overall_risk = result.get("overall_risk", "Unknown")
    risk_score = result.get("risk_score")
    summary = result.get("summary", "No summary returned.")
    issues = result.get("issues", [])
    notes = result.get("notes", [])

    st.subheader("IRS Compliance Risk")
    st.metric("Overall risk", overall_risk, delta=f"Score {risk_score or 'N/A'}")
    st.write(summary)

    if issues:
        st.markdown("#### Potential compliance issues")
        for issue in issues:
            st.markdown(
                f"**{issue.get('area', 'Other')}**: {issue.get('finding', 'No finding provided.')}")
            st.markdown(f"- Recommendation: {issue.get('recommendation', 'No recommendation provided.')}")
            st.write("---")
    else:
        st.success("No obvious IRS compliance issues were identified in the provided text.")

    if notes:
        st.markdown("#### Notes")
        for note in notes:
            st.write(f"- {note}")

    st.info(
        "This audit is a prototype and not a substitute for professional tax or legal advice. "
        "Review the results with an IRS compliance specialist."
    )
