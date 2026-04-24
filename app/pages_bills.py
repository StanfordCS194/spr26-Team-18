import streamlit as st

from app.components import render_bill_detail, render_empty_db_message
from app.db import get_conn
from legi_bill.storage import get_all_bills, get_bill_with_summary_and_questions


def render():
    st.header("Bill Summaries")
    st.caption(
        "Plain-language summaries of California environmental bills, generated "
        "from the Legi-Bill database."
    )

    conn = get_conn()
    bills = get_all_bills(conn)
    if not bills:
        render_empty_db_message()
        return

    col_list, col_detail = st.columns([1, 2])
    with col_list:
        labels = [f"{b.bill_number} — {b.title[:60]}" for b in bills]
        idx = st.radio(
            "Bills",
            range(len(bills)),
            format_func=lambda i: labels[i],
            label_visibility="collapsed",
        )
    with col_detail:
        record = get_bill_with_summary_and_questions(conn, bills[idx].bill_number)
        render_bill_detail(record)
