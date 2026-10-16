from typing import Any

import streamlit as st

from llm_workbench import db, formatting, records
from llm_workbench.analytics import stats
from llm_workbench.ui import error_display, interaction_view, judge_selection, model_selection, page, run_controls, system_prompt_controls


def redirect_to_prompts(error_message: str) -> None:
    st.session_state["error_message"] = error_message
    st.switch_page("pages/prompts.py")


def load_prompt(prompt_id_param: str | None) -> dict[str, Any]:
    # prompt id was not specified in the url -> redirect
    if not prompt_id_param:
        st.switch_page("pages/prompts.py")

    if not prompt_id_param.isdigit():
        redirect_to_prompts(f"'{prompt_id_param}' is not a valid prompt ID.")

    prompt_object = db.prompts.get_prompt_by_id(int(prompt_id_param))

    if prompt_object is None:
        redirect_to_prompts(f"No prompt with ID={prompt_id_param} could be found.")

    return prompt_object


@st.dialog("Run prompt", width="medium")
def display_run_prompt_dialog(interactions, prompt_object):
    st.header("Review or edit prompts")
    st.caption("Changing the prompt or system prompt saves and runs it as a new prompt.")
    st.text_area(
        "User prompt",
        value=prompt_object["prompt"],
        height="content",
        key="prompt",
    )
    system_prompt_controls.system_prompt_input(
        "system_prompt",
        value=prompt_object["system_prompt"],
        height="content",
    )
    display_categories(prompt_object, key_prefix="", save_button=False)
    st.divider()

    st.header("Select a target model")

    # if only one model was used in the original interaction, suggest using it again
    originally_used_models = list(set([i["interaction"]["model"] for i in interactions]))
    default_model = originally_used_models[0] if len(originally_used_models) == 1 else None

    model_selection.model_picker(default_model=default_model)
    st.divider()

    st.header("LLM-as-a-Judge Evaluation")


    # enable judging by default if any interaction has been judged before
    judging_enabled = st.toggle(
        "Evaluate responses with LLM judges",
        value=(sum([len(i["judge_results"]) for i in interactions]) > 0),
    )

    if judging_enabled:
        judge_config, judge_models = judge_selection.judge_model_and_configuration_selector()
    else:
        judge_config, judge_models = None, []

    st.divider()

    run_controls.send_prompt_button_with_repetitions(judge_config, judge_models, button_label="Run prompt")


def display_experiment_overview(interactions, canvas):
    def count_labels(label):
        return sum(
            sum([1 if i["label"] == label else 0 for i in current_interaction["judge_results"]])
            for current_interaction in interactions
        )

    num_success = count_labels("success")
    num_refusal = count_labels("refusal")
    num_unclear = count_labels("unclear")

    judging_price = sum(
        sum([i["price"] or 0 for i in single_interaction["judge_results"]])
        for single_interaction in interactions
    )
    interaction_price = sum([i["interaction"]["price"] or 0 for i in interactions])

    canvas.markdown(f"##### Tested models: {', '.join(sorted({f"`{i['interaction']['model']}`" for i in interactions}))}")
    canvas.markdown(
        f"**{num_success}** successes · **{num_refusal}** refusals · **{num_unclear}** unclear · "
        f"target: **\\${interaction_price:.4f}** · "
        f"judging: **\\${judging_price:.4f}**"
    )


def clear_interaction_filters():
    # drop the preselected run from the url and reset every filter widget to "all"
    st.query_params.pop("run", None)
    for key in [key for key in st.session_state if str(key).startswith("results_run_filter_")]:
        del st.session_state[key]
    st.session_state["results_model_filter"] = []
    st.session_state["results_label_filter"] = []


def display_interaction_filters(interactions):
    runs = {run["run_id"]: run for run in records.summarize_runs(interactions)}
    models = sorted({i["interaction"]["model"] for i in interactions})

    def format_run(run_id):
        if run_id is None:
            return f"All runs ({len(runs)})"

        run = runs[run_id]
        return formatting.format_run_label(run["number"], run["started_at"], run["interaction_count"])

    # preselect the run passed in the url (e.g. after running the prompt)
    run_param = st.query_params.get("run")
    run_options = [None, *runs]

    # a bordered box, so the filters stand apart and it's visible when responses are hidden
    with st.container(border=True):
        with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
            title = st.empty()
            clear_button = st.empty()

        col_run, col_models, col_labels = st.columns(3)
        run_id = col_run.selectbox(
            "Run",
            options=run_options,
            index=run_options.index(run_param) if run_param in runs else 0,
            format_func=format_run,
            # a new run in the url resets the selection made for the previous one
            key=f"results_run_filter_{run_param}",
        )
        selected_models = col_models.multiselect(
            "Target models",
            options=models,
            placeholder="All models",
            key="results_model_filter",
        )
        selected_labels = col_labels.multiselect(
            "Manual labels",
            options=[*stats.LABELS, None],
            format_func=lambda label: label.capitalize() if label else "No label",
            placeholder="All labels",
            key="results_label_filter",
        )

        filtered_interactions = records.filter_prompt_interactions(interactions, run_id, selected_models, selected_labels)

        title.markdown(
            f"**Filters** · :gray[Showing {len(filtered_interactions)} of "
            f"{formatting.pluralize(len(interactions), 'response')}]"
        )
        clear_button.button(
            "Clear filters",
            icon=":material/filter_alt_off:",
            type="tertiary",
            disabled=run_id is None and not selected_models and not selected_labels,
            on_click=clear_interaction_filters,
            key="results_clear_filters_button",
        )

    return filtered_interactions


def display_prompt(prompt_object):
    st.header("Prompt")

    parse_markdown = st.toggle("Parse Markdown", value=True, key="parse_md_prompt")

    if parse_markdown:
        with st.container(border=True, height="stretch"):
            st.caption("User prompt")
            st.markdown(prompt_object["prompt"])

    else:
        st.text_area(
            "User prompt",
            value=prompt_object["prompt"],
            height="content",
            key=f"overview_{prompt_object['id']}_prompt",
        )

    system_prompt_controls.system_prompt_view(
        prompt_object["system_prompt"],
        key=f"overview_{prompt_object['id']}_system_prompt",
        parse_markdown=parse_markdown,
    )


def display_categories(prompt_object, key_prefix, save_button):
    if save_button:
        col_select_categories, col_save_categories = st.columns([2, 1])
    else:
        col_select_categories, col_save_categories = st, None

    categories = col_select_categories.multiselect(
        "Categories",
        options=records.get_all_categories(),
        default=formatting.parse_categories_from_json(prompt_object["categories"]),
        accept_new_options=True,
        key=f"{key_prefix}categories",
    )

    if col_save_categories:
        col_save_categories.space()
        if col_save_categories.button("Save categories", type="primary"):
            db.prompts.set_prompt_categories(prompt_object["id"], formatting.categories_to_json(categories))
            st.success("Categories updated!")



prompt_object = load_prompt(st.query_params.get("prompt"))
interactions = records.get_prompt_interactions(prompt_object["id"])


### Start frontend

page.page_config("Experiment results")
st.title("Experiment Results")
st.page_link("pages/prompts.py", label="← Show all prompts")

col_overview, col_rerun = st.columns([2, 1])

col_overview.subheader(formatting.format_prompt_label(prompt_object["id"], prompt_object["title"]))

with col_rerun.container(horizontal=True, horizontal_alignment="right"):
    # filled once the filters are applied, since it judges only the displayed responses
    judge_all_button = st.empty()
    if st.button("Run prompt…", type="primary"):
        display_run_prompt_dialog(interactions, prompt_object)

# display the filters, then total label counts, total prices and models that were tested of the filtered interactions
if interactions:
    filtered_interactions = display_interaction_filters(interactions)
    display_experiment_overview(filtered_interactions, st)
else:
    filtered_interactions = []

# only responses with a text from the target can be judged
judgeable_interactions = [i for i in filtered_interactions if i["interaction"]["response"]]
if judge_all_button.button(
        "Judge all displayed…",
        disabled=not judgeable_interactions,
        help=f"Run judging on the {formatting.pluralize(len(judgeable_interactions), 'displayed response')}.",
        key="results_judge_all_button",
):
    interaction_view.display_run_judging_dialog(judgeable_interactions, key_prefix="judge_all")

st.divider()

# if not all interactions succeeded or any judgments failed, let the user know here
interaction_errors = st.session_state.pop("interaction_errors", [])
succeeded_interaction_count = st.session_state.pop("succeeded_interaction_count", len(interactions))
if interaction_errors:
    error_display.display_interaction_errors(
        succeeded_interactions=succeeded_interaction_count,
        interaction_errors=interaction_errors,
    )


failed_judgments = st.session_state.pop("failed_judgments", [])
if failed_judgments:
    error_display.display_failed_judgments_information(failed_judgments)

if interaction_errors or failed_judgments:
    st.divider()

# prompt information
display_prompt(prompt_object)

# categories
display_categories(prompt_object, key_prefix=f"overview_{prompt_object['id']}_", save_button=True)
st.divider()


# display outcomes and judge results
if not interactions:
    st.info("This prompt hasn't been run yet.")
elif not filtered_interactions:
    st.info("No responses match the selected filters.")

for interaction_object in filtered_interactions:
    interaction_view.interaction_card(interaction_object)
