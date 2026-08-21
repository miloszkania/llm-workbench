import streamlit as st

from src import database, view_utils, widgets

interaction_ids = st.query_params.get("id")

# interaction ids were not specified in the url -> redirect
if not interaction_ids:
    st.switch_page("pages/history.py")


interaction_ids = interaction_ids.split(",")

# get interaction and judge result objects of all selected prompts
interactions = []

for interaction_id in interaction_ids:
    interaction_object = database.get_interaction_by_id(interaction_id)

    # interaction with id interaction_id could not be found -> redirect
    if len(interaction_object) == 0:
        st.session_state["error_message"] = f"An interaction with with ID={interaction_id} could not be found."
        st.switch_page("pages/history.py")

    judge_results = database.get_judge_results_by_interaction(interaction_id)
    if judge_results:
        judge_results = sorted(judge_results, key=lambda x: x["label"])
    else:
        judge_results = []

    interactions.append({
        "interaction": interaction_object[0],
        "judge_results": judge_results,
    })

# check if all selected interactions have the same prompt (then, together they can be called an experiment)
for i in range(1, len(interactions)):
    if interactions[i - 1]["interaction"]["prompt"] != interactions[i]["interaction"]["prompt"]\
            or interactions[i - 1]["interaction"]["system_prompt"] != interactions[i]["interaction"]["system_prompt"]\
            or interactions[i - 1]["interaction"]["categories"] != interactions[i]["interaction"]["categories"]:
        st.session_state["error_message"] = ("The selected interactions do not belong to the same experiment! "
                                             "They need to have sent identical prompts.")
        st.switch_page("pages/history.py")


### Start frontend

view_utils.page_config("Experiment results")
st.title("Experiment Results")
st.page_link("pages/history.py", label="← Show all interactions")

# show ids
if len(interactions) == 1:
    st.subheader(f"ID: `{interactions[0]['interaction']['id']}`")
else:
    st.subheader(f"IDs: {', '.join(f'`{i["interaction"]["id"]}`' for i in interactions)}")

st.divider()

# prompt information
st.header("Prompt")
parse_markdown = st.toggle("Parse Markdown", value=True, key="parse_md_prompt")

if parse_markdown:
    if interactions[0]["interaction"]["system_prompt"]:
        with st.container(border=True, height="stretch"):
            st.caption("System prompt")
            st.markdown(interactions[0]["interaction"]["system_prompt"])

    with st.container(border=True, height="stretch"):
        st.caption("User prompt")
        st.markdown(interactions[0]["interaction"]["prompt"])

else:
    if interactions[0]["interaction"]["system_prompt"]:
        st.text_area(
            "System prompt",
            value=interactions[0]["interaction"]["system_prompt"],
            height="content",
            key="system_prompt",
        )

    st.text_area(
        "User prompt",
        value=interactions[0]["interaction"]["prompt"],
        height="content",
        key="prompt",
    )

# categories
col_select_categories, col_save_categories = st.columns([2, 1])
categories = col_select_categories.multiselect(
    "Categories",
    options=view_utils.get_all_categories(),
    default=view_utils.unparse_categories_from_json(interactions[0]["interaction"]["categories"] or []),
    accept_new_options=True,
    key="categories",
)

col_save_categories.space()
if col_save_categories.button("Save categories", type="primary"):
    for i in interactions:
        database.set_interaction_categories(i["interaction"]["id"], categories)
    st.success("Categories updated!")

widgets.save_preset_button(
    interactions[0]["interaction"]["prompt"],
    interactions[0]["interaction"]["system_prompt"],
    categories
)

st.divider()

# show interaction cards
for interaction_object in interactions:
    widgets.interaction_card(interaction_object)
