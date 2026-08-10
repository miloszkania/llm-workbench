import streamlit as st

from src import widgets

st.set_page_config(
    layout="wide",
    page_title="Pipeline: Home"
)

# Define all subpages
new_prompt = st.Page("pages/new_prompt.py", title="New Prompt")
history = st.Page("pages/history.py", title="History")
presets = st.Page("pages/presets.py", title="Presets")
prompt_details = st.Page("pages/prompt_details.py", title="Prompt Details")
batch_details = st.Page("pages/batch_details.py", title="Batch Details")
dashboard = st.Page("pages/dashboard.py", title="Dashboard")
dashboard_clean = st.Page("pages/dashboard_clean.py", title="Dashboard (Clean)")


navigation = st.navigation({
    "Menu": [
        new_prompt,
        history,
        presets,
        dashboard,
        dashboard_clean,
    ],
    "Unavailable": [
        prompt_details,
        batch_details,
    ],
})

navigation.run()

# Hide the hidden section
st.sidebar.markdown(
    body="<style>.st-emotion-cache-1jv7wse.e1lpckdq12:nth-child(2) { display: none; }</style>",
    unsafe_allow_html=True,
)


widgets.batch_ids_picker(canvas=st.sidebar)