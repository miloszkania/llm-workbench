import streamlit as st

from src import view_utils

view_utils.page_config("New Judge Configuration")

st.title("New Judge Configuration")

if st.button("Back to judge settings"):
    st.switch_page("pages/judge_settings.py")

st.divider()

### Name
st.subheader("Name")
st.write("The identifier of the configuration containing max. 64 characters "
         "(allowed characters: letters, numbers, `-`, `_`).")
config_name = st.text_input(
    "Configuration name",
    placeholder="my-configuration",
    max_chars=64,
    key="judge_config_name",
)

st.divider()

### Explanation
st.subheader("Explanation")
st.write("Specify if the judge model, apart from the label (`success`, `refusal`, or `unclear`), should also "
         "include a brief explanation (max. 500 characters).")
require_explanation = st.toggle("Require judge explanation?")

st.divider()

### Instruction
st.subheader("Evaluation instructions")
st.write("Enter the prompt with the rules that the judge should follow when evaluating the interactions. "
         "**Note that the judge-given labels directly depend on prompt you enter!**")

with st.expander("Prompt format"):
    if require_explanation:
        st.write("""
            - Write **`[PROMPT]`** where the jailbreak prompt should be attached.
            - Write **`[RESPONSE]`** where the response from the attacked model should be attached.
            - Don't forget to mention that a brief judgment explanation is needed.
            - The expected judge output is:
            ```
            Label: [success | refusal | unclear]
            Explanation: [brief explanation]
            ```
        """)
    else:
        st.write("""
            - Write **`[PROMPT]`** where the jailbreak prompt should be attached.
            - Write **`[RESPONSE]`** where the response from the attacked model should be attached.
            - The expected judge output is:
            ```
            Label: [success | refusal | unclear]
            ```
        """)

judge_prompt = st.text_area(
    "Instruction for the judge",
    max_chars=2000,
)

st.divider()

if st.button("Save configuration", type="primary"):
    pass
