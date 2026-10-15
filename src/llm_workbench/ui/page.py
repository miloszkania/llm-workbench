import streamlit as st


def page_config(name: str | None = None) -> None:
    st.set_page_config(
        layout="wide",
        page_title=f"{name} | LLM Workbench" if name else "LLM Workbench"
    )
