from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from src import view_utils, database, openrouter_api, judge, errors
from src.errors import OpenRouterRequestError


def model_filter_and_sort_controls(canvas=st, key_prefix=""):
    sorting_options = {
        "most-popular": "Most popular",
        "newest": "Newest",
        "latency-low-to-high": "Lowest latency",
        "pricing-low-to-high": "Lowest price",
        "throughput-high-to-low": "Highest throughput",
        "intelligence-high-to-low": "Highest intelligence",
        "context-high-to-low": "Largest context window",
    }

    favorites_only = canvas.toggle(
        "Show only favorite models",
        key=f"{key_prefix}favorites-only"
    )

    model_filter = canvas.segmented_control(
        "Model type",
        options=["All", "Free", "Paid"],
        default="All",
        required=True,
        key=f"{key_prefix}model-filter",
    )

    model_sorting = canvas.segmented_control(
        "Sort by",
        options=list(sorting_options),
        format_func=lambda x: sorting_options[x],
        default="most-popular",
        required=True,
        key=f"{key_prefix}model-sorting",
    )

    try:
        selected_models = view_utils.get_models(
            model_filter=model_filter,
            sort=model_sorting,
        )
    except OpenRouterRequestError as error:
        errors.display_error(error, canvas)
        return [], model_filter

    if favorites_only:
        favorite_models = database.get_favorite_models()
        selected_models = [i for i in selected_models if i.id in favorite_models]

    return selected_models, model_filter


def model_picker(default_model=None, canvas=st, key_prefix=""):
    models, model_filter = model_filter_and_sort_controls(canvas, key_prefix)
    model_ids = [model.id for model in models]

    # Starting a new prompt, with no previous data as placeholder
    if not default_model:
        selected_model_id = canvas.selectbox(
            "Select a model",
            placeholder="Model",
            options=model_ids,
            index=None,
            key=f"{key_prefix}model",
        )

    # There is placeholder data, and it's present in the up-to-date model list
    elif default_model in model_ids:
        selected_model_id = canvas.selectbox(
            "Select a model",
            placeholder=default_model,
            options=model_ids,
            index=model_ids.index(default_model),
            key=f"{key_prefix}model",
        )

    # There is placeholder data, but it's not present in the up-to-date model list
    else:
        selected_model_id = canvas.selectbox(
            "Select a model",
            placeholder=default_model,
            options=model_ids,
            index=None,
            key=f"{key_prefix}model",
        )

    def set_random_free_model(): st.session_state[f"{key_prefix}model"] = "openrouter/free"

    # Button for "openrouter/free" - random model will be selected
    if model_filter == "Free" and "openrouter/free" in model_ids:
        canvas.button(
            "Random free model",
            type="secondary",
            on_click=set_random_free_model,
            key=f"{key_prefix}random-model-button",
        )

    # Model pricing
    if selected_model_id:
        try:
            model_object = view_utils.get_model_object(selected_model_id)

            if float(model_object.data.pricing.prompt) >= 0 and float(model_object.data.pricing.completion) >= 0:
                canvas.caption(f"***Price***: starting at "
                     f"**{view_utils.format_model_price(model_object.data.pricing.prompt, markdown=True)} "
                               f"per 1M input tokens** · "
                     f"**{view_utils.format_model_price(model_object.data.pricing.completion, markdown=True)} "
                               f"per 1M output tokens**")
            else:
                canvas.caption("***Price***: varies by model")

        except OpenRouterRequestError as error:
            errors.display_error(error, canvas)

    canvas.divider()


def send_prompt_button_with_repetitions(judge_config=None, judge_models=None, button_label="Run"):
    model = st.session_state["model"]
    system_prompt = st.session_state["system_prompt"]
    prompt = st.session_state["prompt"]
    categories = st.session_state["categories"]

    with st.spinner("Sending the request and waiting for response…", show_time=True):
        col1, col2 = st.columns([1, 6])
        repetition_count = col2.number_input(
            "Number of target interactions to run",
            min_value=1,
            max_value=50,
            value=1,
            help="Each interaction independently sends the prompt to the target model and will be separately evaluated "
                 "by each selected judge.",
            key="repetition_count",
        )

        col1.space("small")

        if col1.button(button_label, type="primary", width="stretch"):
            if not model:
                st.error("You need to enter the model!")
            elif not prompt:
                st.error("You need to enter the prompt!")
            else:
                try:
                    interaction_ids, failed_interactions, failed_judgments = view_utils.generate_and_evaluate_interactions(
                        model, system_prompt, prompt, categories, judge_config, judge_models, repetition_count
                    )

                    # no interactions succeeded, display the error message right away, don't redirect
                    if failed_interactions and not interaction_ids:
                        display_failed_interactions_information(interaction_ids, failed_interactions)
                    else:
                        # redirect to the prompt/batch details page
                        st.session_state["failed_judgments"] = failed_judgments
                        st.session_state["failed_interactions"] = failed_interactions

                        param_string = ",".join(map(str, interaction_ids))  # parse [1, 2, 3, 4] into 1,2,3,4
                        st.switch_page("pages/experiment_results.py", query_params={"id": param_string})

                except OpenRouterRequestError as error:
                    errors.display_error(error)


def save_preset_button(prompt, system_prompt, categories):
    if st.button("Add preset", type="secondary"):
        if not prompt:
            st.error("You need to enter the prompt!")
        else:
            preset_id = view_utils.add_preset(system_prompt, prompt, categories)
            st.success(f"Saved as preset #{preset_id}")


@st.dialog("Run judging", width="medium")
def display_run_judging_dialog(interaction_object):
    judge_models, judge_config = judge_model_and_configuration_selector()
    st.divider()

    if st.button("Run judging", type="primary"):
        if not judge_models or not judge_config:
            st.error("Select at least one judge model and a judge configuration!")
        else:
            with st.spinner("Waiting for judge response…", show_time=True):
                try:
                    failed_judgments = judge.evaluate_and_store_interaction(
                        interaction_object["interaction"]["id"],
                        interaction_object["interaction"]["system_prompt"],
                        interaction_object["interaction"]["prompt"],
                        interaction_object["interaction"]["response"],
                        judge_config,
                        judge_models
                    )
                    st.session_state["failed_judgments"] = failed_judgments
                    st.rerun()
                except OpenRouterRequestError as error:
                    errors.display_error(error)


def interaction_card(interaction_object):
    interaction_id = interaction_object["interaction"]["id"]

    with st.expander(f"Interaction #{interaction_id}", expanded=True):
        # count judge labels
        num_success = sum([1 if i["label"] == "success" else 0 for i in interaction_object["judge_results"]])
        num_refusal = sum([1 if i["label"] == "refusal" else 0 for i in interaction_object["judge_results"]])
        num_unclear = sum([1 if i["label"] == "unclear" else 0 for i in interaction_object["judge_results"]])
        judging_price = sum(i["price"] for i in interaction_object["judge_results"])

        col_overview, col_manual_label = st.columns([3, 1])

        # Overview
        col_overview.header(f"Interaction #{interaction_id}")
        col_overview.markdown(f"##### from `{interaction_object['interaction']['model']}`")
        col_overview.markdown(
                 f"**{num_success}** successes · **{num_refusal}** refusals · **{num_unclear}** unclear · "
                 f"started at **{view_utils.format_timestamp(interaction_object['interaction']['time'])}** · "
                 f"took **{view_utils.format_duration(interaction_object['interaction']['duration'])}** · "
                 f"**{interaction_object['interaction']['token_usage']}** tokens · "
                 f"interaction: **\\${interaction_object['interaction']['price']:.4f}** · "
                 f"judging: **\\${judging_price:.4f}**"
        )

        # Manual label field
        def update_manual_label():
            new_label = st.session_state[f"manual_label_{interaction_id}"]
            database.set_interaction_label(interaction_id, new_label)
            col_manual_label.success("Label saved!")

        possible_labels = ["success", "refusal", "unclear", None]
        existing_manual_label = interaction_object["interaction"]["manual_label"]
        col_manual_label.selectbox(
            label="Set a manual label",
            options=possible_labels,
            format_func=lambda x: x.capitalize() if x else "No label",
            placeholder="Select a label…",
            index=(possible_labels.index(existing_manual_label) if existing_manual_label else None),
            key=f"manual_label_{interaction_id}",
            on_change=update_manual_label,
        )

        st.divider()

        col_response, col_judge = st.columns(2)

        # Response
        col_response.subheader("Response")
        parse_markdown = col_response.toggle("Parse Markdown", value=True, key=f"parse_md_{interaction_id}")

        if parse_markdown:
            with col_response.container(border=True, height="stretch"):
                st.markdown(interaction_object["interaction"]["response"])
        else:
            col_response.text_area(
                f"Response for ID={interaction_id}",
                value=interaction_object["interaction"]["response"],
                height="stretch",
                key=f"response_{interaction_id}",
            )

        # Judge results
        col_title, col_button = col_judge.columns(2)
        col_title.subheader("Judge results")

        # allow running the judge only if there was any response from the target
        if interaction_object["interaction"]["response"]:
            with col_button.container(horizontal=True, horizontal_alignment="right"):
                if st.button("Run judging…", type="primary", key=f"{interaction_id}_run_judge"):
                    display_run_judging_dialog(interaction_object)

        if len(interaction_object["judge_results"]) > 0:
            for judge_result in interaction_object["judge_results"]:
                label = judge_result["label"]
                explanation = judge_result["explanation"] or ""

                if label == "success": display_fct = col_judge.success
                elif label == "refusal": display_fct = col_judge.error
                elif label == "unclear": display_fct = col_judge.warning
                else: continue

                display_fct(
                    title=f"{label} · {judge_result['judge_model']} · {judge_result["judge_config_id"]}",
                    body=explanation,
                )
        else:
            col_judge.info("No LLM-as-a-Judge evaluations were performed for this interaction.")


def preset_table_preview(preset_table=None):
    with st.spinner("Getting preset data…"):
        if preset_table is None:
            preset_table = view_utils.get_all_preset_entries()

    with st.expander("All presets"):
        if not preset_table.empty:
            st.dataframe(
                preset_table,
                height="content" if len(preset_table) <= 20 else 750,
                hide_index=True,

                column_order=[
                    "id",
                    "categories",
                    "prompt",
                    "system_prompt",
                ],

                column_config={
                    "id": st.column_config.TextColumn(
                        "ID",
                    ),
                    "prompt": st.column_config.TextColumn(
                        "Prompt",
                        width="large",
                    ),
                    "system_prompt": st.column_config.TextColumn(
                        "System Prompt",
                        width="large",
                    ),
                    "categories": st.column_config.MultiselectColumn(
                        "Categories",
                    ),
                },
            )
        else:
            st.warning("There are no presets yet.")


def batch_ids_picker(history_table=None, canvas=st):
    if history_table is None:
        history_table = view_utils.get_all_history_entries()

    if history_table.empty:
        return

    canvas.subheader("Show experiment results")

    details_prompt_id = canvas.multiselect(
        "Prompt IDs",
        placeholder="Select one or more IDs",
        options=history_table["id"],
        accept_new_options=True,
    )

    if details_prompt_id is not None:
        if canvas.button("Go"):
            param_string = ",".join(map(str, details_prompt_id))
            st.switch_page("pages/experiment_results.py", query_params={"id": param_string})

    canvas.divider()


def api_key_details(canvas=st.sidebar):
    canvas.subheader("OpenRouter Details")

    # check if the api key can be authentified
    with canvas.spinner(text="Fetching account information…"):
        # get key metadata
        try:
            metadata = openrouter_api.get_key_metadata()
        except OpenRouterRequestError as error:
            errors.display_error(error, canvas, context="Could not fetch API key information.")
            return

        # get credits
        try:
            credits = openrouter_api.get_credits()
        except OpenRouterRequestError as error:
            errors.display_error(error, canvas, context="Could not fetch credit information.")
            return

    # key label
    canvas.write(f"**API Key:** 🟢 `{metadata.label}`")

    # key expiration
    if metadata.expires_at:
        local_expiration_date = metadata.expires_at.astimezone(datetime.now().astimezone().tzinfo)

        # check if the key expires in less than 24 hours
        if metadata.expires_at - datetime.now(ZoneInfo("UTC")) < timedelta(days=1):
            canvas.write(f"**Expires at:** ⚠️ {local_expiration_date.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            canvas.write(f"**Expires at:** {local_expiration_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # credits
    remaining_credits = credits.total_credits - credits.total_usage
    canvas.write(f"**Remaining credits:** ${remaining_credits:.4f}")

    canvas.space("xxsmall")

    # key limit
    if metadata.limit:
        canvas.progress(metadata.limit_remaining / metadata.limit)
        canvas.write(f"**Credit limit:** ${metadata.limit_remaining:.4f} / ${metadata.limit:.4f} remaining")

        canvas.space("xxsmall")

    # usage
    canvas.write(f"**Daily usage:** ${metadata.usage_daily:.4f}")
    canvas.write(f"**Weekly usage:** ${metadata.usage_weekly:.4f}")
    canvas.write(f"**Monthly usage:** ${metadata.usage_monthly:.4f}")


def judge_model_and_configuration_selector(default_config=None, default_models=None):
    if not default_config and not default_models:
        default_config, default_models = database.get_default_judge_settings()

    # Models
    st.subheader("Models")
    st.write("Select up to three models that will evaluate the interactions following your selected configuration.")

    # Not using widgets.model_picker() here since we need a multiselect instead of a selectbox
    models, _ = model_filter_and_sort_controls(key_prefix="judge_")
    model_ids = [model.id for model in models]

    # load the current models and check if they are still available
    previous_selected_models = [m for m in default_models if m in model_ids] if default_models else []

    # to prevent already picked options from getting removed when changing model filters,
    # include them as possible options even if they don't match the filter.
    currently_selected_models = st.session_state.get("selected_judge_models", previous_selected_models)
    model_options = model_ids + [m for m in currently_selected_models if not m in model_ids]

    selected_models_ids = st.multiselect(
        "Select up to three judge models",
        options=model_options,
        default=previous_selected_models,
        max_selections=3,
        filter_mode="contains",
        key="selected_judge_models",
    )

    # Model pricing
    if selected_models_ids:
        st.space()
        st.caption("**Starting prices:**")

        price_table_rows = []
        for model_id in selected_models_ids:
            try:
                model_object = view_utils.get_model_object(model_id)
                price_table_rows.append({
                    "Model": model_id,
                    "Input / 1M tokens": view_utils.format_model_price(model_object.data.pricing.prompt),
                    "Output / 1M tokens": view_utils.format_model_price(model_object.data.pricing.completion),
                })
            except OpenRouterRequestError as error:
                errors.display_error(error)
                price_table_rows.append({
                    "Model": model_id,
                    "Input / 1M tokens": "Pricing unavailable",
                    "Output / 1M tokens": "Pricing unavailable",
                })

        st.dataframe(price_table_rows, hide_index=True)


    # Configuration
    st.space()
    st.subheader("Configuration")

    saved_configuration_ids = database.get_saved_configuration_ids()
    previous_selected_configuration = (
        saved_configuration_ids.index(default_config) if default_config in saved_configuration_ids else None
    )

    selected_configuration = st.selectbox(
        "Select a configuration",
        options=saved_configuration_ids,
        index=previous_selected_configuration,
    )

    return selected_models_ids, selected_configuration


def display_failed_judgments_information(failed_judgments, canvas=st):
    canvas.error(f"{len(failed_judgments)} judge evaluation{'s' if len(failed_judgments) != 1 else ''} could not be completed:")
    for failed_judgment in failed_judgments:
        errors.display_error(
            error=failed_judgment["error"],
            canvas=canvas,
            context=f"Interaction `{failed_judgment['interaction_id']}` "
                    f"· judge `{failed_judgment['judge_model']}`",
        )


def display_failed_interactions_information(interactions, failed_interactions, canvas=st):
    canvas.warning(f"Only {len(interactions)} interaction{'s' if len(interactions) != 1 else ''} "
               f"succeeded. The following errors occurred:")
    for failed_interaction in failed_interactions:
        errors.display_error(
            error=failed_interaction,
            canvas=canvas,
        )
