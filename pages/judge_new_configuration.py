import streamlit as st

from llm_workbench import db
from llm_workbench.ui import page

page.page_config("New Judge Configuration")

st.title("New Judge Configuration")

if st.button("Back to judge settings"):
    st.switch_page("pages/judge_settings.py")

st.divider()


### Name
st.subheader("Name")
st.write("The identifier of the configuration containing max. 64 characters.")
config_name = st.text_input(
    "Configuration name",
    placeholder="my-configuration",
    max_chars=64,
    key="judge_config_name",
)

st.divider()

### Explanation
st.subheader("Explanation")
st.write(
    "Specify if the judge model, apart from the label (`success`, `refusal`, or `unclear`), should also "
    "include a brief explanation (max. 500 characters)."
)
require_explanation = st.toggle("Require judge explanation?")

st.divider()

### Instruction
st.subheader("Evaluation instructions")
st.write(
    "Enter the prompt with the rules that the judge should follow when evaluating the responses. "
    "**Note that the judge-given labels directly depend on prompt you enter!**"
)

with st.expander("Expected prompt format", expanded=True):
    if require_explanation:
        st.write("""
            - Write **`[PROMPT]`** where the jailbreak prompt should be attached.
            - Write **`[RESPONSE]`** where the response from the attacked model should be attached.
            - Don't forget to mention that a brief judgment explanation is needed.
            - The expected judge output is:
            ```
            [success | refusal | unclear], Explanation: [brief explanation]
            ```
        """)
    else:
        st.write("""
            - Write **`[PROMPT]`** where the jailbreak prompt should be attached.
            - Write **`[RESPONSE]`** where the response from the attacked model should be attached.
            - The expected judge output is:
            ```
            [success | refusal | unclear]
            ```
        """)

judge_prompt = st.text_area(
    "Instruction for the judge",
    max_chars=4000,
    height="content",
)

st.divider()

### Submit
if st.button("Save configuration", type="primary"):
    config_name = config_name.strip()
    judge_prompt = judge_prompt.strip()

    if not config_name:
        st.error("You need to enter the configuration name!")
    elif len(config_name) > 64:
        st.error("The configuration name can have at most 64 characters!")
    elif db.judges.get_judge_configuration_by_id(config_name) is not None:
        st.error(f"A configuration with name `{config_name}` already exists!")

    elif not judge_prompt:
        st.error("You need to enter the evaluation instructions!")
    elif len(judge_prompt) > 4000:
        st.error("The evaluation instructions can have at most 4000 characters!")
    elif "[PROMPT]" not in judge_prompt or "[RESPONSE]" not in judge_prompt:
        st.error("The instructions must contain **`[PROMPT]`** and **`[RESPONSE]`**!")

    else:
        db.judges.insert_judge_configuration(config_name, judge_prompt, require_explanation)
        st.success("Saved!")
        st.session_state["created_config"] = config_name
        st.switch_page("pages/judge_settings.py")
