import streamlit as st

from llm_workbench import experiments, records
from llm_workbench.errors import OpenRouterRequestError
from llm_workbench.ui import error_display


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
                prompt_id = records.save_prompt(prompt, system_prompt, categories)
                result = experiments.generate_and_evaluate_interactions(
                    model,
                    prompt_id,
                    judge_config,
                    judge_models,
                    repetition_count,
                    on_interaction_start=update_interaction_progress,
                    on_judgment_start=update_judgment_progress,
                )

                succeeded_interactions = len(result.interaction_ids)
                status.update(
                    label=(
                        f"Run finished · {succeeded_interactions} of {repetition_count} "
                        f"interaction{'s' if repetition_count != 1 else ''} succeeded"
                    ),
                    state="error" if succeeded_interactions == 0 else "complete",
                    expanded=True,
                )

                st.session_state["interaction_errors"] = result.interaction_errors
                st.session_state["succeeded_interaction_count"] = succeeded_interactions

                if not result.interaction_ids:
                    # no interactions succeeded, rerun to re-enable the button and display the errors
                    st.rerun()
                else:
                    # redirect to the prompt/batch details page
                    st.session_state["failed_judgments"] = result.failed_judgments

                    param_string = ",".join(map(str, result.interaction_ids))  # parse [1, 2, 3, 4] into 1,2,3,4
                    st.switch_page("pages/experiment_results.py", query_params={"id": param_string})

            except OpenRouterRequestError as error:
                status.update(label="Run interrupted", state="error")
                error_display.display_error(error)
