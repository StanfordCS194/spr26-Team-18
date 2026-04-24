import streamlit as st

from app.pages_bills import render as render_bills
from app.pages_legislators import render as render_legislators
from app.pages_match import render as render_match

st.set_page_config(page_title="Legi-Bill", layout="wide")

PAGES = {
    "Bill Summaries": render_bills,
    "Legislator Tracker": render_legislators,
    "Match my company": render_match,
}


def main():
    st.sidebar.title("Legi-Bill")
    choice = st.sidebar.radio("Features", list(PAGES.keys()), index=2)
    st.sidebar.caption(
        "California environmental legislation for mid-market companies"
    )
    PAGES[choice]()


if __name__ == "__main__":
    main()
