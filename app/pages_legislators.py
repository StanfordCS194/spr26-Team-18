import streamlit as st


def render():
    st.header("Legislator Tracker")
    st.info(
        "Coming soon — this feature will track voting records and committee "
        "assignments for California legislators on environmental bills."
    )
    with st.container(border=True):
        st.subheader("Sen. Jane Example (D-District 11)")
        st.caption("Committee on Environmental Quality — Chair")
        st.write("**Bills authored this session:** 4")
        st.write("**Environmental bills voted on:** 22 (20 aye, 2 nay)")
        st.caption("Mock data — feature not yet implemented.")
