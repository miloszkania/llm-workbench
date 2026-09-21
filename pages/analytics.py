from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics, view_utils


LABEL_COLORS = {
    "success": "#1BC46F",
    "refusal": "#F54927",
    "unclear": "#D9A300",
}

TARGET_COLOR = "#0072B2"
JUDGING_COLOR = "#E69F00"

FILTER_KEYS = (
    "analytics_date_range",
    "analytics_models",
    "analytics_categories",
    "analytics_label_source",
    "analytics_judge_configs",
    "analytics_judge_models",
)

CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": False,
}

DAY_IN_MILLISECONDS = 24 * 60 * 60 * 1000
DAILY_BAR_WIDTH = DAY_IN_MILLISECONDS * 7 // 10
METRIC_CARD_MIN_WIDTH = 190
FILTER_FIELD_MIN_WIDTH = 250
JUDGE_FILTER_MIN_WIDTH = 375
RESPONSIVE_BREAKPOINT = 900


def reset_filters() -> None:
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def parse_date_range(selected_dates: date | tuple[date, ...]) -> tuple[date | None, date | None]:
    if isinstance(selected_dates, tuple):
        start_date = selected_dates[0] if len(selected_dates) >= 1 else None
        end_date = selected_dates[1] if len(selected_dates) >= 2 else None
        return start_date, end_date

    return selected_dates, selected_dates


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"

    if seconds < 60:
        return f"{seconds:.1f} s"

    if seconds < 3600:
        return f"{seconds / 60:.1f} min"

    return f"{seconds / 3600:.1f} h"


def display_metric_cards(
        metrics: analytics.OverviewMetrics,
        label_distribution: pd.DataFrame,
        label_coverage: int,
) -> None:
    label_count = int(label_distribution["count"].sum())
    success_count = int(
        label_distribution.loc[label_distribution["label"] == "success", "count"].iloc[0]
    )
    success_percentage = success_count / label_count * 100 if label_count else 0.0
    total_cost = metrics.target_cost + metrics.judging_cost

    metric_grid = st.container(key="analytics-metrics")
    first_row = metric_grid.container(
        horizontal=True,
        gap="xsmall",
    )
    first_row.metric(
        "Interactions",
        f"{metrics.interaction_count:,}",
        border=True,
        width="stretch",
    )
    first_row.metric(
        "Target models",
        f"{metrics.target_model_count:,}",
        border=True,
        width="stretch",
    )
    first_row.metric(
        "Categories",
        f"{metrics.category_count:,}",
        border=True,
        width="stretch",
    )
    first_row.metric(
        "Label coverage",
        f"{label_coverage:,} / {metrics.interaction_count:,}",
        help="Number of interactions covered by the selected label source.",
        border=True,
        width="stretch",
    )

    second_row = metric_grid.container(
        horizontal=True,
        gap="xsmall",
    )
    second_row.metric(
        "Success rate",
        f"{success_percentage:.1f}%",
        help=f"{success_count:,} of {label_count:,} labels are successes.",
        border=True,
        width="stretch",
    )
    second_row.metric(
        "Total cost",
        f"${total_cost:,.4f}",
        help=(
            f"Target interactions: \\${metrics.target_cost:,.4f} · "
            f"Judging: \\${metrics.judging_cost:,.4f}"
        ),
        border=True,
        width="stretch",
    )
    second_row.metric(
        "Target tokens",
        f"{metrics.token_usage:,}",
        border=True,
        width="stretch",
    )
    second_row.metric(
        "Median duration",
        format_duration(metrics.median_duration_seconds),
        border=True,
        width="stretch",
    )


def create_label_distribution_chart(label_distribution: pd.DataFrame) -> go.Figure:
    chart_data = label_distribution.copy()
    chart_data["label_name"] = chart_data["label"].str.capitalize()

    figure = px.bar(
        chart_data,
        x="count",
        y="label_name",
        color="label",
        orientation="h",
        text="count",
        custom_data=["percentage"],
        color_discrete_map=LABEL_COLORS,
        labels={"count": "Labels", "label_name": ""},
    )
    figure.update_traces(
        texttemplate="%{text:,} · %{customdata[0]:.1f}%",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,} labels<br>%{customdata[0]:.1f}%<extra></extra>",
    )
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=["Unclear", "Refusal", "Success"],
    )
    figure.update_layout(
        height=320,
        showlegend=False,
        margin=dict(l=10, r=80, t=10, b=10),
    )

    return figure


def configure_daily_bar_chart(figure: go.Figure, dates: pd.Series) -> None:
    figure.update_traces(width=DAILY_BAR_WIDTH)
    figure.update_xaxes(tickformat="%b %d\n%Y")

    if dates.empty:
        return

    first_date = dates.min()
    last_date = dates.max()

    # Plotly uses a millisecond-wide range for a single date by default.
    # A fixed two-day window keeps the daily bar readable and centered.
    if first_date == last_date:
        figure.update_xaxes(
            range=[
                first_date - pd.Timedelta(days=1),
                last_date + pd.Timedelta(days=1),
            ],
            tickmode="array",
            tickvals=[first_date],
            ticktext=[first_date.strftime("%b %d, %Y")],
        )


def create_activity_chart(activity: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        activity,
        x="date",
        y="interaction_count",
        labels={"date": "Date", "interaction_count": "Interactions"},
    )
    figure.update_traces(
        marker_color=TARGET_COLOR,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,} interactions<extra></extra>",
    )
    configure_daily_bar_chart(figure, activity["date"])
    figure.update_yaxes(rangemode="tozero")

    if not activity.empty and activity["interaction_count"].max() <= 10:
        figure.update_yaxes(dtick=1)

    figure.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=10, b=10),
    )

    return figure


def create_cost_chart(costs: pd.DataFrame) -> go.Figure:
    chart_data = costs.melt(
        id_vars="date",
        value_vars=["target_cost", "judging_cost"],
        var_name="source",
        value_name="cost",
    )
    chart_data["source"] = chart_data["source"].map({
        "target_cost": "Target interactions",
        "judging_cost": "Judging",
    })

    figure = px.bar(
        chart_data,
        x="date",
        y="cost",
        color="source",
        barmode="stack",
        labels={"date": "Date", "cost": "Cost", "source": "Source"},
        color_discrete_map={
            "Target interactions": TARGET_COLOR,
            "Judging": JUDGING_COLOR,
        },
    )
    figure.update_traces(
        hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: $%{y:.6f}<extra></extra>",
    )
    configure_daily_bar_chart(figure, costs["date"])
    figure.update_yaxes(tickprefix="$", tickformat=".4f")
    figure.update_layout(
        height=340,
        legend_title_text=None,
        legend_orientation="h",
        legend_y=-0.25,
        margin=dict(l=10, r=10, t=10, b=55),
    )

    return figure


def display_coverage(label: str, covered: int, total: int) -> None:
    percentage = covered / total if total else 0.0
    st.markdown(f"**{label}**")
    st.progress(percentage, text=f"{covered:,} of {total:,} · {percentage:.1%}")


view_utils.page_config("Analytics")
st.title("Analytics")
st.caption("Explore experiment outcomes, activity, cost, and data coverage.")

# keep responsive overrides local to the keyed analytics containers
st.html(
    f"""
    <style>
        .st-key-analytics-metrics [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
            flex: 1 1 {METRIC_CARD_MIN_WIDTH}px;
            min-width: {METRIC_CARD_MIN_WIDTH}px;
        }}

        .st-key-analytics-primary-filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
            flex: 1 1 {FILTER_FIELD_MIN_WIDTH}px;
            min-width: {FILTER_FIELD_MIN_WIDTH}px;
        }}

        .st-key-analytics-judge-filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
            flex: 1 1 {JUDGE_FILTER_MIN_WIDTH}px;
            min-width: {JUDGE_FILTER_MIN_WIDTH}px;
        }}

        @media (max-width: {RESPONSIVE_BREAKPOINT}px) {{
            .st-key-analytics-metrics [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"],
            .st-key-analytics-primary-filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                flex-basis: calc(50% - 0.25rem);
            }}

            .st-key-analytics-judge-filters [data-testid="stHorizontalBlock"] > [data-testid="stElementContainer"] {{
                flex-basis: 100%;
            }}
        }}
    </style>
    """
)

interactions = analytics.load_interactions()
judge_results = analytics.load_judge_results()

if interactions.empty:
    st.info("No interaction data yet. Run an experiment to start building analytics.")
    st.stop()

model_options = sorted(interactions["model"].dropna().unique().tolist())
category_options = sorted({category for assigned in interactions["categories"] for category in assigned})
judge_config_options = sorted(judge_results["judge_config_id"].dropna().unique().tolist())
judge_model_options = sorted(judge_results["judge_model"].dropna().unique().tolist())
valid_times = interactions["time"].dropna()

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

    primary_filter_grid = st.container(key="analytics-primary-filters")
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

    if label_source == "LLM judge":
        judge_filter_grid = st.container(key="analytics-judge-filters")
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
latest_judge_results = analytics.get_latest_judge_results(filtered_judge_results)
valid_latest_judge_results = latest_judge_results.loc[
    latest_judge_results["label"].isin(analytics.LABELS)
]

if label_source == "Manual":
    selected_labels = filtered_interactions["manual_label"]
    label_coverage = int(selected_labels.isin(analytics.LABELS).sum())
    label_source_caption = "Each manually labeled interaction contributes one label."
else:
    selected_labels = valid_latest_judge_results["label"]
    label_coverage = valid_latest_judge_results["interaction_id"].nunique()
    label_source_caption = (
        "Each judge model and configuration contributes its latest label per interaction. "
        "Judging costs include all evaluations."
    )

label_distribution = analytics.summarize_labels(selected_labels)
metrics = analytics.get_overview_metrics(filtered_interactions, filtered_judge_results)

display_metric_cards(metrics, label_distribution, label_coverage)

st.subheader("Outcomes")
st.caption(label_source_caption)

if int(label_distribution["count"].sum()) > 0:
    st.plotly_chart(
        create_label_distribution_chart(label_distribution),
        width="stretch",
        config=CHART_CONFIG,
    )
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
        st.plotly_chart(
            create_activity_chart(activity),
            width="stretch",
            config=CHART_CONFIG,
        )

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
        st.plotly_chart(
            create_cost_chart(costs),
            width="stretch",
            config=CHART_CONFIG,
        )

st.subheader("Data coverage")
coverage_columns = st.columns(3)

with coverage_columns[0]:
    display_coverage(
        "Categorized interactions",
        metrics.categorized_interaction_count,
        metrics.interaction_count,
    )

with coverage_columns[1]:
    display_coverage(
        "Manually labeled interactions",
        metrics.manually_labeled_interaction_count,
        metrics.interaction_count,
    )

with coverage_columns[2]:
    display_coverage(
        "Judge-evaluated interactions",
        metrics.judged_interaction_count,
        metrics.interaction_count,
    )
