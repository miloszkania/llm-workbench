import streamlit as st

from llm_workbench import db, formatting
from llm_workbench.llm import judge
from llm_workbench.errors import OpenRouterRequestError
from llm_workbench.ui import error_display, judge_selection


@st.dialog("Run judging", width="medium")
def display_run_judging_dialog(interaction_object) -> None:
    judge_config, judge_models = judge_selection.judge_model_and_configuration_selector()
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
                error_display.display_error(error)


def interaction_card(interaction_object) -> None:
    interaction_id = interaction_object["interaction"]["id"]

    with st.expander(f"Response #{interaction_id}", expanded=True):
        # count judge labels
        num_success = sum([1 if i["label"] == "success" else 0 for i in interaction_object["judge_results"]])
        num_refusal = sum([1 if i["label"] == "refusal" else 0 for i in interaction_object["judge_results"]])
        num_unclear = sum([1 if i["label"] == "unclear" else 0 for i in interaction_object["judge_results"]])
        judging_price = sum(i["price"] or 0 for i in interaction_object["judge_results"])

        col_overview, col_manual_label = st.columns([3, 1])

        # Overview (the response number is already shown by the expander)
        col_overview.markdown(f"##### from `{interaction_object['interaction']['model']}`")
        col_overview.markdown(
                 f"**{num_success}** successes · **{num_refusal}** refusals · **{num_unclear}** unclear · "
                 f"started at **{formatting.format_timestamp(interaction_object['interaction']['time'])}** · "
                 f"took **{formatting.format_duration(interaction_object['interaction']['duration'])}** · "
                 f"**{interaction_object['interaction']['token_usage']}** tokens · "
                 f"target: **\\${interaction_object['interaction']['price'] or 0:.4f}** · "
                 f"judging: **\\${judging_price:.4f}**"
        )

        # Manual label field
        def update_manual_label():
            new_label = st.session_state[f"manual_label_{interaction_id}"]
            db.interactions.set_interaction_label(interaction_id, new_label)
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
            col_judge.info("No LLM-as-a-Judge evaluations were performed for this response.")
