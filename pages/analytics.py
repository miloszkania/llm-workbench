from datetime import date
from functools import partial
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analytics, charts, widgets
from src.ui import page


FILTER_KEYS = (
    "analytics_date_range",
    "analytics_models",
    "analytics_categories",
    "analytics_label_source",
    "analytics_judge_configs",
    "analytics_judge_models",
    "analytics_minimum_sample_size",
)

METRIC_CARD_MIN_WIDTH = 190
FILTER_FIELD_MIN_WIDTH = 250
JUDGE_FILTER_MIN_WIDTH = 375
RESPONSIVE_BREAKPOINT = 900

# tables with more rows get a fixed, scrollable height
MAX_TABLE_ROWS_WITHOUT_SCROLL = 20
SCROLLABLE_TABLE_HEIGHT = 750

SHARE_FORMAT = st.column_config.NumberColumn(format="%.1f%%")
DURATION_FORMAT = st.column_config.NumberColumn(format="%.2f s")
TOKENS_FORMAT = st.column_config.NumberColumn(format="%.0f")
COST_FORMAT = st.column_config.NumberColumn(format="$%.6f")


##### FILTERS AND FORMATTING

def reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def parse_date_range(selected_dates: date | tuple[date, ...]) -> tuple[date | None, date | None]:
    if isinstance(selected_dates, tuple):
        start_date = selected_dates[0] if len(selected_dates) >= 1 else None
        end_date = selected_dates[1] if len(selected_dates) >= 2 else None
        return start_date, end_date

    return selected_dates, selected_dates


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "—"

    if seconds < 60:
        return f"{seconds:.1f} s"

    if seconds < 3600:
        return f"{seconds / 60:.1f} min"

    return f"{seconds / 3600:.1f} h"


def order_by_interaction_count(frame: pd.DataFrame, column: str) -> list[str]:
    # most used values first
    return frame.groupby(column)["interaction_count"].sum().sort_values(ascending=False).index.tolist()


##### SHARED COMPONENTS

def display_chart(figure: go.Figure, export_name: str) -> None:
    st.plotly_chart(figure, width="stretch", config=charts.CHART_CONFIG)

    export_options = [
        ("Download PDF", partial(charts.export_chart_image, figure, "pdf"), "pdf", "application/pdf"),
        ("Download PNG", partial(charts.export_chart_image, figure, "png"), "png", "image/png"),
        ("Download interactive HTML", partial(charts.export_chart_html, figure), "html", "text/html"),
    ]

    with st.popover("Export chart", icon=":material/download:"):
        st.caption("Select the export file format.")

        # generate the file only after the user selects a format
        for label, data, extension, mime in export_options:
            st.download_button(
                label,
                data=data,
                file_name=f"llm-workbench-{export_name}.{extension}",
                mime=mime,
                key=f"analytics_export_{export_name}_{extension}",
                on_click="ignore",
                width="stretch",
            )


def display_summary_table(
        summary: pd.DataFrame,
        column_titles: dict[str, str],
        column_config: dict[str, Any],
) -> None:
    # show only the listed columns, in the listed order, under their display titles
    table = summary[list(column_titles)].rename(columns=column_titles)

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height="content" if len(table) <= MAX_TABLE_ROWS_WITHOUT_SCROLL else SCROLLABLE_TABLE_HEIGHT,
        column_config=column_config,
    )


def display_metric_cards(
        metrics: analytics.OverviewMetrics,
        label_distribution: pd.DataFrame,
        label_coverage: int,
) -> None:
    label_count = int(label_distribution["count"].sum())
    success_count = int(label_distribution.loc[label_distribution["label"] == "success", "count"].iloc[0])
    # calculate success only from the currently selected label source
    success_percentage = success_count / label_count * 100 if label_count else 0.0
    total_cost = metrics.target_cost + metrics.judging_cost

    # each row contains (label, value, help text) of its metric cards
    metric_rows = [
        [
            ("Interactions", f"{metrics.interaction_count:,}", None),
            ("Target models", f"{metrics.target_model_count:,}", None),
            ("Categories", f"{metrics.category_count:,}", None),
            (
                "Label coverage",
                f"{label_coverage:,} / {metrics.interaction_count:,}",
                "Number of interactions covered by the selected label source.",
            ),
        ],
        [
            (
                "Success rate",
                f"{success_percentage:.1f}%",
                f"{success_count:,} of {label_count:,} labels are successes.",
            ),
            (
                "Total cost",
                f"${total_cost:,.4f}",
                f"Target interactions: \\${metrics.target_cost:,.4f} · Judging: \\${metrics.judging_cost:,.4f}",
            ),
            ("Target tokens", f"{metrics.token_usage:,}", None),
            ("Median duration", format_seconds(metrics.median_duration_seconds), None),
        ],
    ]

    metric_grid = st.container(key="analytics_metrics")

    for metric_row in metric_rows:
        row = metric_grid.container(horizontal=True, gap="xsmall")
        for label, value, help_text in metric_row:
            row.metric(label, value, help=help_text, border=True, width="stretch")


def display_coverage(label: str, covered: int, total: int) -> None:
    percentage = covered / total if total else 0.0
    st.markdown(f"**{label}**")
    st.progress(percentage, text=f"{covered:,} of {total:,} · {percentage:.1%}")


##### ANALYTICS VIEWS

def display_overview(
        filtered_interactions: pd.DataFrame,
        filtered_judge_results: pd.DataFrame,
        label_distribution: pd.DataFrame,
        label_source_caption: str,
        metrics: analytics.OverviewMetrics,
) -> None:
    st.subheader("Outcomes")
    st.caption(label_source_caption)

    if int(label_distribution["count"].sum()) > 0:
        display_chart(charts.create_label_distribution_chart(label_distribution), "label_distribution")
    else:
        st.info("No labels from the selected source match the current filters.")

    st.subheader("Activity and cost")
    activity_column, cost_column = st.columns(2)
    activity = analytics.summarize_activity(filtered_interactions)
    costs = analytics.summarize_costs(filtered_interactions, filtered_judge_results)

    with activity_column:
        st.markdown("**Interactions over time**")
        if activity.empty:
            st.info("No valid interaction timestamps are available.")
        else:
            display_chart(charts.create_activity_chart(activity), "interactions_over_time")

    with cost_column:
        st.markdown("**Cost over time**")
        if costs.empty:
            st.info("No valid cost timestamps are available.")
        elif not costs["total_cost"].gt(0).any():
            st.info(
                "No costs were recorded for the selected filters. "
                "The selected models may be free, or pricing data may be unavailable."
            )
        else:
            display_chart(charts.create_cost_chart(costs), "cost_over_time")

    st.subheader("Data coverage")
    coverage = [
        ("Categorized interactions", metrics.categorized_interaction_count),
        ("Manually labeled interactions", metrics.manually_labeled_interaction_count),
        ("Judge-evaluated interactions", metrics.judged_interaction_count),
    ]

    for column, (label, covered) in zip(st.columns(len(coverage)), coverage):
        with column:
            display_coverage(label, covered, metrics.interaction_count)


def display_model_table(model_summary: pd.DataFrame) -> None:
    display_summary_table(
        model_summary,
        column_titles={
            "model": "Model",
            "interaction_count": "Interactions",
            "label_count": "Labels",
            "success_count": "Success",
            "refusal_count": "Refusal",
            "unclear_count": "Unclear",
            "success_share": "Success share",
            "median_duration_seconds": "Median duration",
            "median_tokens": "Median tokens",
            "total_cost": "Total target cost",
            "average_cost": "Average target cost",
        },
        column_config={
            "Success share": SHARE_FORMAT,
            "Median duration": DURATION_FORMAT,
            "Median tokens": TOKENS_FORMAT,
            "Total target cost": COST_FORMAT,
            "Average target cost": COST_FORMAT,
        },
    )


def display_model_analytics(
        interactions: pd.DataFrame,
        label_records: pd.DataFrame,
        minimum_sample_size: int,
) -> None:
    st.subheader("Model comparison")
    st.caption(
        "Interactions count target calls; n on outcome charts counts labels from the "
        "selected source. Costs and duration describe target calls only."
    )
    model_summary = analytics.summarize_models(interactions, label_records)
    display_model_table(model_summary)

    comparable_models = analytics.filter_by_sample_size(model_summary, minimum_sample_size)
    st.markdown("**Label distribution by model**")
    if comparable_models.empty:
        st.info("No model has enough labels for the selected minimum sample size.")
    else:
        display_chart(
            charts.create_group_label_distribution_chart(comparable_models, "model"), "model_label_distribution"
        )

    st.markdown("**Success by model and category**")
    model_categories = analytics.summarize_model_categories(interactions, label_records)
    comparable_cells = analytics.filter_by_sample_size(model_categories, minimum_sample_size)
    if comparable_cells.empty:
        st.info("No model-category pair has enough labels for the selected minimum sample size.")
    else:
        available_models = set(comparable_cells["model"])
        model_order = [model for model in model_summary["model"] if model in available_models]
        category_order = order_by_interaction_count(comparable_cells, "category")
        display_chart(
            charts.create_model_category_heatmap(comparable_cells, model_order, category_order),
            "model_category_success",
        )

    st.markdown("**Average target cost vs success**")
    scatter_data = comparable_models.loc[
        comparable_models["success_share"].notna()
        & comparable_models["average_cost"].notna()
    ].copy()
    if scatter_data.empty:
        st.info("No model has both enough labels and recorded target cost data for this comparison.")
    else:
        display_chart(charts.create_model_cost_scatter(scatter_data), "model_cost_success")


def display_category_analytics(
        interactions: pd.DataFrame,
        label_records: pd.DataFrame,
        minimum_sample_size: int,
) -> None:
    st.subheader("Category comparison")
    st.caption(
        "An interaction assigned to multiple categories contributes once to each of "
        "them, so category totals may exceed the overall interaction count."
    )
    category_summary = analytics.summarize_categories(interactions, label_records)

    if category_summary.empty:
        st.info("No categorized interactions match the current filters.")
        return

    st.markdown("**Interactions by category**")
    display_chart(charts.create_category_usage_chart(category_summary), "category_usage")

    st.markdown("**Label distribution by category**")
    comparable_categories = analytics.filter_by_sample_size(category_summary, minimum_sample_size)
    if comparable_categories.empty:
        st.info("No category has enough labels for the selected minimum sample size.")
    else:
        display_chart(
            charts.create_group_label_distribution_chart(comparable_categories, "category"),
            "category_label_distribution",
        )


def display_preset_table(preset_summary: pd.DataFrame) -> None:
    display_summary_table(
        preset_summary,
        column_titles={
            "preset_label": "Preset",
            "prompt": "Prompt",
            "categories": "Categories",
            "interaction_count": "Interactions",
            "target_model_count": "Target models",
            "label_count": "Labels",
            "success_count": "Success",
            "refusal_count": "Refusal",
            "unclear_count": "Unclear",
            "success_share": "Success share",
            "median_duration_seconds": "Median duration",
            "median_tokens": "Median tokens",
            "total_cost": "Total target cost",
            "average_cost": "Average target cost",
        },
        column_config={
            "Prompt": st.column_config.TextColumn(width="large"),
            "Categories": st.column_config.MultiselectColumn(),
            "Success share": SHARE_FORMAT,
            "Median duration": DURATION_FORMAT,
            "Median tokens": TOKENS_FORMAT,
            "Total target cost": COST_FORMAT,
            "Average target cost": COST_FORMAT,
        },
    )


def display_preset_analytics(
        presets: pd.DataFrame,
        interactions: pd.DataFrame,
        label_records: pd.DataFrame,
        minimum_sample_size: int,
) -> None:
    st.subheader("Preset comparison")
    st.caption(
        "Presets act as current configuration markers. A match requires the same "
        "prompt, system prompt, and set of categories, so editing a preset updates "
        "these statistics immediately."
    )
    widgets.preset_table_preview(presets)

    if presets.empty:
        st.info("No presets are available to compare with the selected interactions.")
        return

    preset_summary = analytics.summarize_presets(presets, interactions, label_records)
    display_preset_table(preset_summary)

    comparable_presets = analytics.filter_by_sample_size(preset_summary, minimum_sample_size)
    st.markdown("**Label distribution by preset**")
    if comparable_presets.empty:
        st.info("No preset has enough labels for the selected minimum sample size.")
    else:
        preset_order = comparable_presets["preset_label"].tolist()
        label_distribution_chart = charts.create_group_label_distribution_chart(comparable_presets, "preset_label")
        # show the id next to every bar instead of letting plotly thin the axis
        label_distribution_chart.update_yaxes(
            categoryorder="array",
            categoryarray=preset_order,
            autorange="reversed",
            tickmode="array",
            tickvals=preset_order,
            ticktext=preset_order,
        )
        display_chart(label_distribution_chart, "preset_label_distribution")

    st.markdown("**Success by preset and target model**")
    preset_models = analytics.summarize_preset_models(presets, interactions, label_records)
    comparable_cells = analytics.filter_by_sample_size(preset_models, minimum_sample_size)
    if comparable_cells.empty:
        st.info("No preset-model pair has enough labels for the selected minimum sample size.")
    else:
        available_presets = set(comparable_cells["preset_label"])
        preset_order = [preset for preset in preset_summary["preset_label"] if preset in available_presets]
        model_order = order_by_interaction_count(comparable_cells, "model")
        display_chart(
            charts.create_preset_model_heatmap(comparable_cells, preset_order, model_order),
            "preset_model_success",
        )


def display_judge_table(judge_summary: pd.DataFrame) -> None:
    display_summary_table(
        judge_summary,
        column_titles={
            "judge_setup": "Judge setup",
            "evaluation_count": "Evaluations",
            "interaction_count": "Interactions",
            "label_count": "Latest labels",
            "success_count": "Success",
            "refusal_count": "Refusal",
            "unclear_count": "Unclear",
            "success_share": "Success share",
            "median_duration_seconds": "Median duration",
            "total_cost": "Total judging cost",
            "average_cost": "Average judging cost",
        },
        column_config={
            "Success share": SHARE_FORMAT,
            "Median duration": DURATION_FORMAT,
            "Total judging cost": COST_FORMAT,
            "Average judging cost": COST_FORMAT,
        },
    )


def display_judge_analytics(
        judge_results: pd.DataFrame,
        minimum_sample_size: int,
) -> None:
    st.subheader("Judge comparison")
    st.caption(
        "Costs and duration include every evaluation. Outcome and agreement charts "
        "use the latest valid label per interaction, judge model, and configuration."
    )

    judge_summary = analytics.summarize_judges(judge_results)

    if judge_summary.empty:
        st.info("No judge evaluations match the current filters.")
        return

    display_judge_table(judge_summary)

    comparable_judges = analytics.filter_by_sample_size(judge_summary, minimum_sample_size)
    st.markdown("**Label distribution by judge setup**")
    if comparable_judges.empty:
        st.info("No judge setup has enough labels for the selected minimum sample size.")
    else:
        display_chart(
            charts.create_group_label_distribution_chart(comparable_judges, "judge_setup"),
            "judge_label_distribution",
        )

    st.markdown("**Agreement between judge setups**")
    judge_order = comparable_judges["judge_setup"].tolist()
    if len(judge_order) < 2:
        st.info("Select at least two judge setups with enough labels to compare agreement.")
    else:
        agreement = analytics.summarize_judge_agreement(judge_results)
        agreement = analytics.filter_by_sample_size(agreement, minimum_sample_size, count_column="overlap_count")
        agreement = agreement.loc[agreement["judge_a"].isin(judge_order) & agreement["judge_b"].isin(judge_order)]
        pairwise_agreement = agreement.loc[agreement["judge_a"] != agreement["judge_b"]]

        if pairwise_agreement.empty:
            st.info("No pair of judge setups has enough shared interactions for the selected minimum sample size.")
        else:
            display_chart(charts.create_judge_agreement_heatmap(agreement, judge_order), "judge_agreement")

    st.markdown("**Judging cost vs duration**")
    efficiency_data = judge_summary.loc[
        judge_summary["average_cost"].notna()
        & judge_summary["median_duration_seconds"].notna()
    ].copy()
    if efficiency_data.empty:
        st.info("No judge setup has both recorded cost and duration data.")
    else:
        display_chart(charts.create_judge_efficiency_scatter(efficiency_data), "judge_cost_duration")


def inject_responsive_styles() -> None:
    # apply responsive styles only to the analytics containers
    st.html(
        f"""
        <style>
            .st-key-analytics_metrics [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                flex: 1 1 {METRIC_CARD_MIN_WIDTH}px;
                min-width: {METRIC_CARD_MIN_WIDTH}px;
            }}

            .st-key-analytics_primary_filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                flex: 1 1 {FILTER_FIELD_MIN_WIDTH}px;
                min-width: {FILTER_FIELD_MIN_WIDTH}px;
            }}

            .st-key-analytics_judge_filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                flex: 1 1 {JUDGE_FILTER_MIN_WIDTH}px;
                min-width: {JUDGE_FILTER_MIN_WIDTH}px;
            }}

            .st-key-analytics_view [data-testid="stButtonGroup"] button {{
                min-height: 3rem;
            }}

            .st-key-analytics_view [data-testid="stButtonGroup"] button p {{
                font-size: 1rem;
                font-weight: 600;
            }}

            .st-key-analytics_view [data-testid="stButtonGroup"] button[aria-checked="true"] {{
                box-shadow: inset 0 0 0 1px currentColor;
            }}

            @media (max-width: {RESPONSIVE_BREAKPOINT}px) {{
                .st-key-analytics_metrics [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"],
                .st-key-analytics_primary_filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                    flex-basis: calc(50% - 0.25rem);
                }}

                .st-key-analytics_judge_filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                    flex-basis: 100%;
                }}
            }}
        </style>
        """
    )


##### PAGE

page.page_config("Analytics")
st.title("Analytics")
st.caption("Explore experiment outcomes, activity, cost, and data coverage.")

inject_responsive_styles()

# load analytics data before preparing filter options
interactions = analytics.load_interactions()
judge_results = analytics.load_judge_results()
presets = analytics.load_presets()

if interactions.empty:
    st.info("No interaction data yet. Run an experiment to start building analytics.")
    st.stop()

# prepare all values available in the filter fields
model_options = sorted(interactions["model"].dropna().unique().tolist())
category_options = sorted({category for assigned in interactions["categories"] for category in assigned})
judge_config_options = sorted(judge_results["judge_config_id"].dropna().unique().tolist())
judge_model_options = sorted(judge_results["judge_model"].dropna().unique().tolist())
valid_times = interactions["time"].dropna()
current_view = st.session_state.get("analytics_view", "Overview")

# empty multiselect fields include all available values
with st.expander("Filters", expanded=True):
    filter_header = st.container(
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="center",
    )
    filter_header.caption(
        "Empty model, category, and judge selections include all available values.",
        width=650,
    )
    filter_header.button("Reset filters", on_click=reset_filters)

    primary_filter_grid = st.container(key="analytics_primary_filters")
    first_filter_row = primary_filter_grid.container(
        horizontal=True,
        gap="xsmall",
    )

    if valid_times.empty:
        selected_dates = None
        first_filter_row.caption(
            "Date filtering is unavailable because no valid timestamps were found.",
            width="stretch",
        )
    else:
        selected_dates = first_filter_row.date_input(
            "Date range",
            value=(valid_times.min().date(), valid_times.max().date()),
            min_value=valid_times.min().date(),
            max_value=valid_times.max().date(),
            help="Filter interactions by the date on which they were started.",
            format="YYYY-MM-DD",
            key="analytics_date_range",
            width="stretch",
        )

    selected_models = first_filter_row.multiselect(
        "Target models",
        options=model_options,
        placeholder="All target models",
        key="analytics_models",
        width="stretch",
    )
    selected_categories = first_filter_row.multiselect(
        "Categories",
        options=category_options,
        placeholder="All categories",
        key="analytics_categories",
        width="stretch",
    )

    label_source = st.segmented_control(
        "Label source",
        options=["LLM judge", "Manual"],
        default="LLM judge" if not judge_results.empty else "Manual",
        required=True,
        width="stretch",
        key="analytics_label_source",
    )

    selected_judge_configs = []
    selected_judge_models = []

    # keep judge filters available for judge labels and the Judges view
    if label_source == "LLM judge" or current_view == "Judges":
        judge_filter_grid = st.container(key="analytics_judge_filters")
        judge_filter_row = judge_filter_grid.container(
            horizontal=True,
            gap="xsmall",
        )
        selected_judge_configs = judge_filter_row.multiselect(
            "Judge configurations",
            options=judge_config_options,
            placeholder="All judge configurations",
            key="analytics_judge_configs",
            width="stretch",
        )
        selected_judge_models = judge_filter_row.multiselect(
            "Judge models",
            options=judge_model_options,
            placeholder="All judge models",
            key="analytics_judge_models",
            width="stretch",
        )

# filter interactions first and use their ids to filter judge results
start_date, end_date = parse_date_range(selected_dates) if selected_dates else (None, None)
filtered_interactions = analytics.filter_interactions(
    interactions,
    start_date=start_date,
    end_date=end_date,
    models=selected_models or None,
    categories=selected_categories or None,
)

if filtered_interactions.empty:
    st.warning("No interactions match the selected filters.")
    st.stop()

filtered_judge_results = analytics.filter_judge_results(
    judge_results,
    interaction_ids=filtered_interactions["id"].tolist(),
    judge_config_ids=selected_judge_configs or None,
    judge_models=selected_judge_models or None,
)

# choose labels used by the shared metrics and outcome charts
if label_source == "Manual":
    label_records = analytics.get_manual_label_records(filtered_interactions)
    label_source_caption = "Each manually labeled interaction contributes one label."
else:
    # use the latest label of every judge setup
    latest_judge_results = analytics.get_latest_judge_results(filtered_judge_results)
    label_records = analytics.get_judge_label_records(latest_judge_results)
    label_source_caption = (
        "Each judge model and configuration contributes its latest label per interaction. "
        "Judging costs include all evaluations."
    )

label_distribution = analytics.summarize_labels(label_records["label"])
label_coverage = label_records["interaction_id"].nunique()
metrics = analytics.get_overview_metrics(filtered_interactions, filtered_judge_results)

display_metric_cards(metrics, label_distribution, label_coverage)

# switch between detailed analytics without changing the shared filters and metrics
st.space(20)
st.subheader("Results analytics")
selected_view = st.segmented_control(
    "Analytics view",
    options=["Overview", "Models", "Categories", "Presets", "Judges"],
    default="Overview",
    required=True,
    width="stretch",
    key="analytics_view",
    label_visibility="collapsed",
)

if selected_view == "Overview":
    display_overview(filtered_interactions, filtered_judge_results, label_distribution, label_source_caption, metrics)
else:
    minimum_sample_size = int(st.number_input(
        "Minimum labels per group",
        min_value=1,
        value=3,
        step=1,
        help=(
            "Hide small samples from outcome and agreement charts. Summary tables "
            "always show every group."
        ),
        key="analytics_minimum_sample_size",
    ))

    if selected_view == "Models":
        display_model_analytics(filtered_interactions, label_records, minimum_sample_size)
    elif selected_view == "Categories":
        display_category_analytics(filtered_interactions, label_records, minimum_sample_size)
    elif selected_view == "Presets":
        display_preset_analytics(presets, filtered_interactions, label_records, minimum_sample_size)
    else:
        if label_source == "Manual":
            st.info(
                "Judge analytics use LLM judge results. The label source selector "
                "still controls the shared KPI cards above."
            )
        display_judge_analytics(filtered_judge_results, minimum_sample_size)
