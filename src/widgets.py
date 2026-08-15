import json
from datetime import datetime, timedelta
from operator import indexOf
from zoneinfo import ZoneInfo

import openrouter.errors.openroutererror
import streamlit as st

from src import view_utils, database, judge, openrouter_api

LABEL_OPTIONS = ["🟢", "🔴", "🟡"]


def model_picker(prompt_data=None):
    SORTING_OPTIONS = {
        "most-popular": "Most popular",
        "newest": "Newest",
        "latency-low-to-high": "Lowest latency",
        "pricing-low-to-high": "Lowest price",
        "throughput-high-to-low": "Highest throughput",
        "intelligence-high-to-low": "Highest intelligence",
        "context-high-to-low": "Largest context window",
    }

    def set_random_free_model(): st.session_state["model"] = "openrouter/free"

    st.header("Model")

    model_filter = st.segmented_control(
        "Model type",
        options=["All", "Free"],
        default="All",
        required=True,
    )

    model_sorting = st.segmented_control(
        "Sort by",
        options=list(SORTING_OPTIONS),
        format_func=lambda x: SORTING_OPTIONS[x],
        default="most-popular",
        required=True,
    )

    model_ids = view_utils.get_model_ids(only_free_models=model_filter == "Free", sort=model_sorting)

    with st.spinner("Loading available models...", show_time=True):
        # Starting a new prompt, with no previous data as placeholder
        if prompt_data is None or prompt_data.empty:
            st.selectbox(
                "Select a model",
                placeholder="Model",
                options=model_ids,
                index=None,
                key="model",
            )

        # There is placeholder data, and it's present in the up-to-date model list
        elif prompt_data["model"] in model_ids:
            st.selectbox(
                "Select a model",
                placeholder=prompt_data["model"],
                options=model_ids,
                index=indexOf(model_ids, prompt_data["model"]),
                key="model",
            )

        # There is placeholder data, but it's not present in the up-to-date model list
        else:
            st.selectbox(
                "Select a model",
                placeholder=prompt_data["model"],
                options=model_ids,
                index=None,
                key="model",
            )

        # Button for "openrouter/free" - random model will be selected
        if model_filter == "Free" and "openrouter/free" in model_ids:
            st.button(
                "Random free model",
                type="secondary",
                on_click=set_random_free_model,
            )

    st.divider()


def prompt_input_display(prompt_data, history_table=None, batch_prompt_ids=None):
    def toggle_categories_update_button(): st.session_state["categories_changed"] = True

    st.header("Prompt")

    if prompt_data["preset"]:
        st.caption(f"(used preset #{int(prompt_data["preset"])})")

    st.text_area(
        "System prompt",
        value=prompt_data["system_prompt"],
        height="content",
        key="system_prompt",
    )

    st.text_area(
        "Prompt",
        value=prompt_data["prompt"],
        height="content",
        key="prompt",
    )

    categories = st.multiselect(
        "Categories",
        options=view_utils.get_all_categories(history_table),
        accept_new_options=True,
        default=prompt_data["categories"],
        on_change=toggle_categories_update_button,
        key="categories",
    )

    # Update categories button
    if st.session_state.categories_changed:
        if st.button("Update categories", type="secondary"):
            if not batch_prompt_ids:
                batch_prompt_ids = [prompt_data["id"]]

            for prompt_id in batch_prompt_ids:
                database.set_prompt_categories(prompt_id, json.dumps(categories, ensure_ascii=False))
            st.success("Categories updated")


    # Save as preset button
    save_preset_button()

    # Re-run button
    send_prompt_button_with_repetitions("Re-run")

    st.divider()


def send_prompt_button_with_repetitions(button_label="Send"):
    model = st.session_state["model"]
    system_prompt = st.session_state["system_prompt"]
    prompt = st.session_state["prompt"]
    categories = st.session_state["categories"]

    with st.spinner("Sending the request and waiting for response...", show_time=True):
        col1, col2 = st.columns([1, 5])
        repetition_count = col2.number_input(
            "Repetitions",
            min_value=1,
            max_value=50,
            value=1,
            key="repetition_count",
        )

        col1.space("small")

        if col1.button(f"{button_label}{f" ({model})" if model else ""}", type="primary"):
            if not model:
                st.error("You need to enter the model!")
            elif not prompt:
                st.error("You need to enter the prompt!")
            else:
                try:
                    view_utils.send_prompt(model, system_prompt, prompt, categories, repetition_count)
                except openrouter.errors.toomanyrequestsresponse_error.TooManyRequestsResponseError:
                    st.error("Too many requests - rate limited by OpenRouter. Try again later.")
                except openrouter.errors.openroutererror.OpenRouterError as e:
                    if "flagged" in e:
                        st.error(f"The request to {model} was flagged by OpenInterface. Try again with a different model.")
                    else:
                        st.error(f"OpenRouter error: {e}. Try again later.")


def save_preset_button():
    prompt = st.session_state["prompt"]
    system_prompt = st.session_state.get("system_prompt")
    categories = st.session_state.get("categories")

    if st.button("Add preset", type="secondary"):
        if not prompt:
            st.error("You need to enter the prompt!")
        else:
            preset_id = view_utils.add_preset(system_prompt, prompt, categories)
            st.success(f"Saved as preset #{preset_id}")


def single_prompt_response_display(prompt_data):
    def toggle_label_update_button(): st.session_state.label_changed = True

    ##### Model
    st.markdown(f"##### from `{prompt_data["model"]}`")

    ##### Response
    tab_md, tab_ta = st.tabs(["Markdown", "Rawtext"])

    with tab_md.expander(f"Full response for ID={prompt_data["id"]}", expanded=True):
        st.markdown(prompt_data["response"])

    tab_ta.text_area(
        f"Response for ID={prompt_data["id"]}",
        value=prompt_data["response"],
        height=250,
        key=f"response_{prompt_data["id"]}",
    )


    ##### LLM-as-a-Judge Label

    # There is no LLM judge label
    if prompt_data["judge_label"] not in LABEL_OPTIONS:
        st.warning(f"The LLM-as-a-Judge label is not available.")

        # Button to try to get LLM judge label
        if st.button(
            "Get LLM-as-a-Judge feedback",
            type="secondary",
            key=f"btn_get_judge_label_{prompt_data["id"]}",
        ):
            with st.spinner("Waiting for judge response...", show_time=True):
                judge_model, judge_label_response = judge.get_llm_judge_label(
                    prompt_data["id"],
                    prompt_data["system_prompt"],
                    prompt_data["prompt"],
                    prompt_data["response"],
                )

                # It worked and we have the LLM judge label now
                if judge_model:
                    st.selectbox(
                        f"LLM-as-a-Judge Label for ID={prompt_data["id"]} by {judge_model}",
                        options=LABEL_OPTIONS,
                        placeholder=judge_label_response,
                        index=None,
                        disabled=True,
                        key=f"judge_label_{prompt_data["id"]}",
                    )

                    if prompt_data["label"] not in LABEL_OPTIONS:
                        prompt_data["label"] = judge_label_response

                # The attempt didn't work - still no LLM judge label
                else:
                    st.error(f"The LLM-as-a-Judge label is not available due to an OpenRouter error: {judge_label_response}")

    # There already is a LLM judge label
    else:
        st.selectbox(
            f"LLM-as-a-Judge Label for ID={prompt_data["id"]}",
            options=LABEL_OPTIONS,
            placeholder=prompt_data["judge_label"],
            index=None,
            disabled=True,
            key=f"judge_label_{prompt_data["id"]}",
        )


    ##### Label
    st.selectbox(
        f"Label for ID={prompt_data["id"]}",
        options=LABEL_OPTIONS,
        placeholder=prompt_data["label"],
        index=None,
        on_change=toggle_label_update_button,
        key=f"label_{prompt_data["id"]}",
    )


    ##### Update label button
    if st.session_state.label_changed:
        if st.button(f"Update label for ID={prompt_data["id"]}", type="primary"):
            label_value = st.session_state[f"label_{prompt_data["id"]}"]
            if label_value:
                database.set_prompt_label(int(prompt_data["id"]), label_value)
                st.success("Label updated")

    st.divider()


def prompt_other_information_display(prompt_data):
    st.header("Other information")
    st.markdown(f"""
    ##### **Duration**: `{prompt_data["duration"]}`

    ##### **Token usage**: `{prompt_data["token_usage"]}`
    """)


def preset_table_preview(preset_table=None):
    with st.spinner("Getting preset data...", show_time=True):
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

    canvas.subheader("Show prompt/batch details")

    details_prompt_id = canvas.multiselect(
        "Prompt IDs",
        placeholder="Prompt IDs",
        options=history_table["id"],
        accept_new_options=True,
    )

    if details_prompt_id is not None:
        if canvas.button("Go"):
            param_string = ",".join(map(str, details_prompt_id))
            st.switch_page("pages/batch_details.py", query_params={"ids": param_string})

    canvas.divider()


def api_key_details(canvas=st.sidebar):
    canvas.subheader("OpenRouter Details")

    # check if the api key can be authentified
    try:
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
    canvas.write(f"**Remaining credits:** \${remaining_credits:.2f}")

    canvas.space("xxsmall")

    # key limit
    if metadata.limit:
        canvas.progress(metadata.limit_remaining / metadata.limit)
        canvas.write(f"**Credit limit:** \${metadata.limit_remaining:.2f} / \${metadata.limit:.2f} remaining")

        canvas.space("xxsmall")

    # usage
    canvas.write(f"**Daily usage:** ${metadata.usage_daily:.2f}")
    canvas.write(f"**Weekly usage:** ${metadata.usage_weekly:.2f}")
    canvas.write(f"**Monthly usage:** ${metadata.usage_monthly:.2f}")
