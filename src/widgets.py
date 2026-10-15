from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from src import database, errors, experiments, formatting, judge, openrouter_api, records
from src.ui import model_selection
from src.errors import OpenRouterRequestError


def send_prompt_button_with_repetitions(
        judge_config: str | None = None,
        judge_models: list[str] | None = None,
        button_label: str = "Run",
) -> None:
    model = st.session_state["model"]
    system_prompt = st.session_state["system_prompt"]
    prompt = st.session_state["prompt"]
    categories = st.session_state["categories"]

    col_btn_run, col_repetitions = st.columns([1, 6])
    repetition_count = col_repetitions.number_input(
        "Number of target interactions to run",
        min_value=1,
        max_value=50,
        value=1,
        help="Each interaction independently sends the prompt to the target model and will be separately evaluated "
             "by each selected judge.",
        key="repetition_count",
    )

    col_btn_run.space("small")

    run_button = col_btn_run.empty()

    if run_button.button(
            button_label,
            type="primary",
            width="stretch",
            key=f"{button_label}_interactions_button",
    ):
        if not model:
            st.error("You need to enter the model!")
        elif not prompt:
            st.error("You need to enter the prompt!")
        else:
            run_button.button(
                "Running…",
                type="primary",
                width="stretch",
                disabled=True,
                key=f"{button_label}_interactions_button_disabled",
            )

            status = st.status("Starting run…", expanded=True)

            if judge_config and judge_models:
                # prepare both interaction and judgment progress bars
                col_interaction, col_judgment = status.columns(2)
                interaction_progress = col_interaction.empty()
                judgment_progress = col_judgment.empty()
            else:
                # only prepare the interaction progress bar
                interaction_progress = status.empty()
                judgment_progress = None

            current_interaction = 0

            def update_interaction_progress(current: int, total: int) -> None:
                # increase the current_interaction counter
                nonlocal current_interaction
                current_interaction = current

                # update the label
                status.update(
                    label=f"Interaction {current} of {total} · Waiting for target response…",
                    expanded=True,
                )

                # update the progress bar
                interaction_progress.progress(
                    value=current / total,
                    text=f"Interaction {current} of {total}",
                )

                # clear the judgment progress (if judging is also included)
                if judgment_progress is not None:
                    judgment_progress.empty()

            def update_judgment_progress(current: int, total: int) -> None:
                # update the label
                status.update(
                    label=(
                        f"Interaction {current_interaction} of {repetition_count} "
                        f"· Judgment {current} of {total}…"
                    ),
                    expanded=True,
                )

                # update the progress bar
                if judgment_progress is not None:
                    judgment_progress.progress(
                        value=current / total,
                        text=f"Judgment {current} of {total}",
                    )

            try:
                interaction_ids, interaction_errors, failed_judgments = experiments.generate_and_evaluate_interactions(
                    model,
                    system_prompt,
                    prompt,
                    categories,
                    judge_config,
                    judge_models,
                    repetition_count,
                    on_interaction_start=update_interaction_progress,
                    on_judgment_start=update_judgment_progress,
                )

                succeeded_interactions = len(interaction_ids)
                status.update(
                    label=(
                        f"Run finished · {succeeded_interactions} of {repetition_count} "
                        f"interaction{'s' if repetition_count != 1 else ''} succeeded"
                    ),
                    state="error" if succeeded_interactions == 0 else "complete",
                    expanded=True,
                )

                if interaction_errors and not interaction_ids:
                    # no interactions succeeded, rerun to re-enable the button and display the errors
                    st.session_state["interaction_errors"] = interaction_errors
                    st.session_state["succeeded_interaction_count"] = 0
                    st.rerun()
                else:
                    # redirect to the prompt/batch details page
                    st.session_state["failed_judgments"] = failed_judgments
                    st.session_state["interaction_errors"] = interaction_errors
                    st.session_state["succeeded_interaction_count"] = succeeded_interactions

                    param_string = ",".join(map(str, interaction_ids))  # parse [1, 2, 3, 4] into 1,2,3,4
                    st.switch_page("pages/experiment_results.py", query_params={"id": param_string})

            except OpenRouterRequestError as error:
                status.update(label="Run interrupted", state="error")
                errors.display_error(error)


def save_preset_button(
        prompt: str,
        system_prompt: str | None,
        categories: list[str],
) -> None:
    if st.button("Add preset", type="secondary"):
        if not prompt:
            st.error("You need to enter the prompt!")
        else:
            preset_id = records.add_preset(system_prompt, prompt, categories)
            st.success(f"Saved as preset #{preset_id}")


@st.dialog("Run judging", width="medium")
def display_run_judging_dialog(interaction_object) -> None:
    judge_config, judge_models = judge_model_and_configuration_selector()
    st.divider()

    interaction_id = interaction_object["interaction"]["id"]
    run_judging_button = st.empty()

    if run_judging_button.button(
            "Run judging",
            type="primary",
            key=f"{interaction_id}_run_judging_button",
    ):
        if not judge_models or not judge_config:
            st.error("Select at least one judge model and a judge configuration!")
        else:
            # disable the run judging button
            run_judging_button.button(
                "Judging…",
                type="primary",
                disabled=True,
                key=f"{interaction_id}_run_judging_button_disabled",
            )

            status = st.status("Starting judging…", expanded=True)
            judgment_progress = status.progress(
                value=0,
                text=f"Judgments: 0 of {len(judge_models)}",
            )

            def update_judgment_progress(current: int, total: int) -> None:
                status.update(label=f"Judgment {current} of {total}…")
                judgment_progress.progress(
                    value=current / total,
                    text=f"Judgment {current} of {total}",
                )

            try:
                failed_judgments = judge.evaluate_and_store_interaction(
                    interaction_id,
                    interaction_object["interaction"]["system_prompt"],
                    interaction_object["interaction"]["prompt"],
                    interaction_object["interaction"]["response"],
                    judge_config,
                    judge_models,
                    on_judgment_start=update_judgment_progress,
                )
                succeeded_judgments = len(judge_models) - len(failed_judgments)
                status.update(
                    label=(
                        f"Judging finished · {succeeded_judgments} of {len(judge_models)} "
                        f"judgment{'s' if len(judge_models) != 1 else ''} succeeded"
                    ),
                    state="error" if succeeded_judgments == 0 else "complete",
                    expanded=True,
                )
                st.session_state["failed_judgments"] = failed_judgments
                st.rerun()
            except OpenRouterRequestError as error:
                status.update(label="Judging interrupted", state="error")
                errors.display_error(error)


def interaction_card(interaction_object) -> None:
    interaction_id = interaction_object["interaction"]["id"]

    with st.expander(f"Interaction #{interaction_id}", expanded=True):
        # count judge labels
        num_success = sum([1 if i["label"] == "success" else 0 for i in interaction_object["judge_results"]])
        num_refusal = sum([1 if i["label"] == "refusal" else 0 for i in interaction_object["judge_results"]])
        num_unclear = sum([1 if i["label"] == "unclear" else 0 for i in interaction_object["judge_results"]])
        judging_price = sum(i["price"] or 0 for i in interaction_object["judge_results"])

        col_overview, col_manual_label = st.columns([3, 1])

        # Overview
        col_overview.header(f"Interaction #{interaction_id}")
        col_overview.markdown(f"##### from `{interaction_object['interaction']['model']}`")
        col_overview.markdown(
                 f"**{num_success}** successes · **{num_refusal}** refusals · **{num_unclear}** unclear · "
                 f"started at **{formatting.format_timestamp(interaction_object['interaction']['time'])}** · "
                 f"took **{formatting.format_duration(interaction_object['interaction']['duration'])}** · "
                 f"**{interaction_object['interaction']['token_usage']}** tokens · "
                 f"interaction: **\\${interaction_object['interaction']['price'] or 0:.4f}** · "
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


def preset_table_preview(preset_table: pd.DataFrame | None = None) -> None:
    with st.spinner("Getting preset data…"):
        if preset_table is None:
            preset_table = records.get_all_presets()

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


def batch_ids_picker(
        history_table: pd.DataFrame | None = None,
        canvas: Any = st,
) -> None:
    if history_table is None:
        history_table = records.get_all_interactions()

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


def api_key_details(canvas: Any = st.sidebar) -> None:
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


def judge_model_and_configuration_selector(
        default_config: str | None = None,
        default_models: list[str] | None = None,
) -> tuple[str | None, list[str]]:
    if not default_config and not default_models:
        default_config, default_models = database.get_default_judge_settings()

    # Models
    st.subheader("Models")
    st.write("Select up to three models that will evaluate the interactions following your selected configuration.")

    # Not using widgets.model_picker() here since we need a multiselect instead of a selectbox
    models, _ = model_selection.model_filter_and_sort_controls(key_prefix="judge_")
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
                model_object = model_selection.get_model_object(model_id)
                price_table_rows.append({
                    "Model": model_id,
                    "Input / 1M tokens": formatting.format_model_price(model_object.data.pricing.prompt),
                    "Output / 1M tokens": formatting.format_model_price(model_object.data.pricing.completion),
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

    return selected_configuration, selected_models_ids


def display_failed_judgments_information(
        failed_judgments,
        canvas: Any = st,
) -> None:
    canvas.error(f"{len(failed_judgments)} judge evaluation{'s' if len(failed_judgments) != 1 else ''} could not be completed:")
    for failed_judgment in failed_judgments:
        errors.display_error(
            error=failed_judgment["error"],
            canvas=canvas,
            context=f"Interaction `{failed_judgment['interaction_id']}` "
                    f"· judge `{failed_judgment['judge_model']}`",
        )


def display_interaction_errors(
        succeeded_interactions: int,
        interaction_errors: Sequence[Exception],
        canvas: Any = st,
) -> None:
    canvas.warning(f"Only {succeeded_interactions} interaction{'s' if succeeded_interactions != 1 else ''} "
               f"succeeded. In other interactions, the following errors occurred:")
    for interaction_error in interaction_errors:
        errors.display_error(
            error=interaction_error,
            canvas=canvas,
        )
