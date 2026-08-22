import streamlit as st

from src import database, view_utils, widgets

interaction_ids = st.query_params.get("id")

# interaction ids were not specified in the url -> redirect
if not interaction_ids:
    st.switch_page("pages/history.py")


def load_interactions(interaction_ids):
    interaction_ids = interaction_ids.split(",")
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

    return interactions


def ensure_same_experiment(experiment_input, interactions):
    if any(
            (i["interaction"]["prompt"], i["interaction"]["system_prompt"], i["interaction"]["categories"])
            != (experiment_input["prompt"], experiment_input["system_prompt"], experiment_input["categories"])
            for i in interactions
    ):
        st.session_state["error_message"] = ("The selected interactions do not belong to the same experiment! "
                                             "They need to have sent identical prompts.")
        st.switch_page("pages/history.py")


def display_experiment_overview(interactions):
    def count_labels(label):
        return sum(
            sum([1 if i["label"] == label else 0 for i in current_interaction["judge_results"]])
            for current_interaction in interactions
        )

    num_success = count_labels("success")
    num_refusal = count_labels("refusal")
    num_unclear = count_labels("unclear")

    judging_price = sum(
        sum([i["price"] for i in single_interaction["judge_results"]])
        for single_interaction in interactions
    )
    interaction_price = sum([i["interaction"]["price"] for i in interactions])

    st.markdown(f"##### Tested models: {', '.join(sorted({f"`{i['interaction']['model']}`" for i in interactions}))}")
    st.markdown(
        f"**{num_success}** successes · **{num_refusal}** refusals · **{num_unclear}** unclear · "
        f"interaction: **\\${interaction_price:.4f}** · "
        f"judging: **\\${judging_price:.4f}**"
    )


def display_prompt(experiment_input):
    st.header("Prompt")

    matching_preset = database.get_preset_id_by_content(
        experiment_input["prompt"], experiment_input["system_prompt"], experiment_input["categories"]
    )
    if matching_preset:
        st.caption(f"Matches preset #{matching_preset}")

    parse_markdown = st.toggle("Parse Markdown", value=True, key="parse_md_prompt")

    if parse_markdown:
        if experiment_input["system_prompt"]:
            with st.container(border=True, height="stretch"):
                st.caption("System prompt")
                st.markdown(experiment_input["system_prompt"])

        with st.container(border=True, height="stretch"):
            st.caption("User prompt")
            st.markdown(experiment_input["prompt"])

    else:
        if experiment_input["system_prompt"]:
            st.text_area(
                "System prompt",
                value=experiment_input["system_prompt"],
                height="content",
                key="system_prompt",
            )

        st.text_area(
            "User prompt",
            value=experiment_input["prompt"],
            height="content",
            key="prompt",
        )


def display_categories(experiment_input, interactions):
    col_select_categories, col_save_categories = st.columns([2, 1])
    categories = col_select_categories.multiselect(
        "Categories",
        options=view_utils.get_all_categories(),
        default=view_utils.unparse_categories_from_json(experiment_input["categories"] or []),
        accept_new_options=True,
        key="categories",
    )

    col_save_categories.space()
    if col_save_categories.button("Save categories", type="primary"):
        for i in interactions:
            database.set_interaction_categories(i["interaction"]["id"], categories)
        st.success("Categories updated!")

    widgets.save_preset_button(
        experiment_input["prompt"],
        experiment_input["system_prompt"],
        categories
    )



# get interaction and judge result objects of all selected prompts
interactions = load_interactions(interaction_ids)
experiment_input = interactions[0]["interaction"]

# check if all selected interactions have the same prompt and categories (then, together they can be called an experiment)
ensure_same_experiment(experiment_input, interactions)


### Start frontend

view_utils.page_config("Experiment results")
st.title("Experiment Results")
st.page_link("pages/history.py", label="← Show all interactions")

# show ids
if len(interactions) == 1:
    st.subheader(f"ID: `{interactions[0]['interaction']['id']}`")
else:
    st.subheader(f"IDs: {', '.join(f'`{i["interaction"]["id"]}`' for i in interactions)}")

# display total label counts, total prices and models that were tested
display_experiment_overview(interactions)
st.divider()

# prompt information
display_prompt(experiment_input)

# categories
display_categories(experiment_input, interactions)
st.divider()


# display outcomes and judge results
for interaction_object in interactions:
    widgets.interaction_card(interaction_object)
