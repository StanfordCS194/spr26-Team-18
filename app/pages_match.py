import streamlit as st

from app.components import (
    relevance_badge,
    render_bill_detail,
    render_empty_db_message,
)
from app.db import get_conn
from app.pdf_utils import extract_text
from app.ranking import rank_bills
from legi_bill.storage import get_all_bills, get_bill_with_summary_and_questions


def render():
    st.header("Match my company")
    st.caption(
        "Upload a 10-K or paste a company description. We'll surface the "
        "California environmental bills most likely to affect you."
    )

    uploaded = st.file_uploader("Upload 10-K (PDF or TXT)", type=["pdf", "txt"])
    pasted = st.text_area(
        "…or paste a company description",
        height=180,
        placeholder=(
            "e.g. We manufacture lithium-ion battery cells in Fremont, CA, "
            "with 400 employees and water-cooled processes..."
        ),
    )

    if not st.button("Analyze", type="primary"):
        return

    company_text = ""
    if uploaded is not None:
        try:
            company_text = extract_text(uploaded)
        except Exception as e:
            st.error(f"Could not read file: {e}")
            return
        if not company_text.strip():
            st.warning(
                "Could not extract any text from the uploaded file — it may be "
                "a scanned/image PDF. Try pasting a description instead."
            )
            return
    elif pasted.strip():
        company_text = pasted
    else:
        st.warning("Upload a document or paste a description first.")
        return

    conn = get_conn()
    bills = get_all_bills(conn)
    if not bills:
        render_empty_db_message()
        return

    enriched = []
    for b in bills:
        rec = get_bill_with_summary_and_questions(conn, b.bill_number)
        summary_text = (
            rec["summary"]["summary_text"] if rec and rec.get("summary") else ""
        )
        enriched.append((b, summary_text))

    ranked = rank_bills(company_text, enriched)
    top = [r for r in ranked if r[1] > 0][:10]
    if not top:
        st.info(
            "No strong matches found. Try pasting a longer description or a "
            "full 10-K."
        )
        return

    st.subheader("Top relevant bills")
    for bill, score, tier in top:
        title_snip = bill.title[:80] + ("…" if len(bill.title) > 80 else "")
        with st.expander(
            f"{bill.bill_number}  {relevance_badge(tier)}  — {title_snip}"
        ):
            record = get_bill_with_summary_and_questions(conn, bill.bill_number)
            render_bill_detail(record)
            st.caption(f"Relevance score: {score:.3f} ({tier})")
