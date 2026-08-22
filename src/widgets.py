from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import openrouter.errors.openroutererror
import streamlit as st

from src import view_utils, database, openrouter_api


def model_picker(default_model=None, canvas=st, key_prefix=""):
    sorting_options = {
        "most-popular": "Most popular",
        "newest": "Newest",
        "latency-low-to-high": "Lowest latency",
        "pricing-low-to-high": "Lowest price",
        "throughput-high-to-low": "Highest throughput",
        "intelligence-high-to-low": "Highest intelligence",
        "context-high-to-low": "Largest context window",
    }

    def set_random_free_model(): st.session_state["model"] = "openrouter/free"

    model_filter = canvas.segmented_control(
        "Model type",
        options=["All", "Free"],
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

    model_ids = view_utils.get_model_ids(only_free_models=model_filter == "Free", sort=model_sorting)

    # Starting a new prompt, with no previous data as placeholder
    if not default_model:
        canvas.selectbox(
            "Select a model",
            placeholder="Model",
            options=model_ids,
            index=None,
            key=f"{key_prefix}model",
        )

    # There is placeholder data, and it's present in the up-to-date model list
    elif default_model in model_ids:
        canvas.selectbox(
            "Select a model",
            placeholder=default_model,
            options=model_ids,
            index=model_ids.index(default_model),
            key=f"{key_prefix}model",
        )

    # There is placeholder data, but it's not present in the up-to-date model list
    else:
        canvas.selectbox(
            "Select a model",
            placeholder=default_model,
            options=model_ids,
            index=None,
            key=f"{key_prefix}model",
        )

    # Button for "openrouter/free" - random model will be selected
    if model_filter == "Free" and "openrouter/free" in model_ids:
        canvas.button(
            "Random free model",
            type="secondary",
            on_click=set_random_free_model,
            key=f"{key_prefix}random-model-button",
        )

    canvas.divider()


def send_prompt_button_with_repetitions(judge_config=None, judge_models=None, button_label="Run"):
    model = st.session_state["model"]
    system_prompt = st.session_state["system_prompt"]
    prompt = st.session_state["prompt"]
    categories = st.session_state["categories"]

    with st.spinner("Sending the request and waiting for response…", show_time=True):
        col1, col2 = st.columns([1, 5])
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

        if col1.button(button_label, type="primary"):
            if not model:
                st.error("You need to enter the model!")
            elif not prompt:
                st.error("You need to enter the prompt!")
            else:
                try:
                    view_utils.generate_and_evaluate_interactions(
                        model, system_prompt, prompt, categories, judge_config, judge_models, repetition_count
                    )
                except openrouter.errors.toomanyrequestsresponse_error.TooManyRequestsResponseError:
                    st.error("Too many requests - rate limited by OpenRouter. Try again later.")
                except openrouter.errors.openroutererror.OpenRouterError as e:
                    if "flagged" in e:
                        st.error(f"The request to {model} was flagged by OpenInterface. "
                                 f"Try again with a different model.")
                    else:
                        st.error(f"OpenRouter error: {e}. Try again later.")


def save_preset_button(prompt, system_prompt, categories):
    if st.button("Add preset", type="secondary"):
        if not prompt:
            st.error("You need to enter the prompt!")
        else:
            preset_id = view_utils.add_preset(system_prompt, prompt, categories)
            st.success(f"Saved as preset #{preset_id}")


def interaction_card(interaction_object):
    interaction_id = interaction_object["interaction"]["id"]

    with st.expander(f"Interaction #{interaction_id}", expanded=True):
        with st.container(border=True):
            # count judge labels
            num_success = sum([1 if i["label"] == "success" else 0 for i in interaction_object["judge_results"]])
            num_refusal = sum([1 if i["label"] == "refusal" else 0 for i in interaction_object["judge_results"]])
            num_unclear = sum([1 if i["label"] == "unclear" else 0 for i in interaction_object["judge_results"]])
            judging_price = sum(i["price"] for i in interaction_object["judge_results"])

            # Overview
            st.header(f"Interaction #{interaction_id}")
            st.markdown(f"##### from `{interaction_object['interaction']['model']}`")
            st.markdown(
                     f"**{num_success}** successes · **{num_refusal}** refusals · **{num_unclear}** unclear · "
                     f"started at **{view_utils.format_timestamp(interaction_object['interaction']['time'])}** · "
                     f"took **{view_utils.format_duration(interaction_object['interaction']['duration'])}** · "
                     f"**{interaction_object['interaction']['token_usage']}** tokens · "
                     f"interaction: **\\${interaction_object['interaction']['price']:.4f}** · "
                     f"judging: **\\${judging_price:.4f}**"
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
            col_judge.subheader("Judge results")
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
                height="content",
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
    try:
        with canvas.spinner(text="Fetching account information…"):
            metadata = openrouter_api.get_key_metadata()
            credits = openrouter_api.get_credits()
    except openrouter.errors.UnauthorizedResponseError:
        canvas.caption("**API Key:** 🔴 Authentication failed, check `OPENROUTER_API_KEY`")
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


def judge_model_and_configuration_selector():
    default_config, default_models = database.get_default_judge_settings()

    # Models
    st.subheader("Models")
    st.write("Select up to three models that will evaluate the interactions following your selected configuration.")

    # Not using widgets.model_picker() here since we need a multiselect instead of a selectbox
    sorting_options = {
        "most-popular": "Most popular",
        "newest": "Newest",
        "latency-low-to-high": "Lowest latency",
        "pricing-low-to-high": "Lowest price",
        "throughput-high-to-low": "Highest throughput",
        "intelligence-high-to-low": "Highest intelligence",
        "context-high-to-low": "Largest context window",
    }

    model_filter = st.segmented_control(
        "Model type",
        options=["All", "Free"],
        default="All",
        required=True,
        key="model_filter",
    )

    model_sorting = st.segmented_control(
        "Sort by",
        options=list(sorting_options),
        format_func=lambda x: sorting_options[x],
        default="most-popular",
        required=True,
        key="model_sorting",
    )

    model_ids = view_utils.get_model_ids(only_free_models=model_filter == "Free", sort=model_sorting)

    # load the current models and check if they are still available
    previous_selected_models = [m for m in default_models if m in model_ids]

    selected_models = st.multiselect(
        "Select up to 3 judge models",
        options=model_ids,
        default=previous_selected_models,
        max_selections=3,
        filter_mode="contains",
        key="selected_judge_models", # to prevent resetting after changing the filters
    )

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

    return selected_models, selected_configuration
