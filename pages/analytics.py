from datetime import date
from functools import partial

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics, view_utils, widgets


LABEL_COLORS = {
    "success": "#1BC46F",
    "refusal": "#F54927",
    "unclear": "#D9A300",
}

TARGET_COLOR = "#0072B2"
JUDGING_COLOR = "#E69F00"
DURATION_COLOR_SCALE = [
    [0.0, "#56B4E9"],
    [0.5, "#0072B2"],
    [1.0, "#003B5C"],
]

FILTER_KEYS = (
    "analytics_date_range",
    "analytics_models",
    "analytics_categories",
    "analytics_label_source",
    "analytics_judge_configs",
    "analytics_judge_models",
    "analytics_minimum_sample_size",
)

CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": False,
}

CHART_EXPORT_WIDTH = 1400
MINIMUM_CHART_EXPORT_HEIGHT = 500
DAY_IN_MILLISECONDS = 24 * 60 * 60 * 1000
DAILY_BAR_WIDTH = DAY_IN_MILLISECONDS * 7 // 10
METRIC_CARD_MIN_WIDTH = 190
FILTER_FIELD_MIN_WIDTH = 250
JUDGE_FILTER_MIN_WIDTH = 375
RESPONSIVE_BREAKPOINT = 900


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


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"

    if seconds < 60:
        return f"{seconds:.1f} s"

    if seconds < 3600:
        return f"{seconds / 60:.1f} min"

    return f"{seconds / 3600:.1f} h"


##### CHART EXPORT

def prepare_chart_for_export(figure: go.Figure) -> go.Figure:
    # copy the figure, so export changes don't affect the dashboard
    export_figure = go.Figure(figure)

    # add enough space for axis titles and long values
    export_figure.update_xaxes(automargin=True)
    export_figure.update_yaxes(automargin=True)

    # allow model names next to scatter points to use the chart margins
    export_figure.update_traces(
        cliponaxis=False,
        selector={"type": "scatter"},
    )

    return export_figure


def export_chart_image(figure: go.Figure, image_format: str) -> bytes:
    export_figure = prepare_chart_for_export(figure)
    height = max(export_figure.layout.height or 0, MINIMUM_CHART_EXPORT_HEIGHT)

    # png needs a larger scale, while pdf remains vector-based
    scale = 2 if image_format == "png" else 1

    return export_figure.to_image(
        format=image_format,
        width=CHART_EXPORT_WIDTH,
        height=height,
        scale=scale,
    )


def export_chart_html(figure: go.Figure) -> bytes:
    export_figure = prepare_chart_for_export(figure)

    # include plotly, so the downloaded chart also works offline
    return export_figure.to_html(
        config=CHART_CONFIG,
        full_html=True,
        include_plotlyjs=True,
    ).encode("utf-8")


def display_chart(figure: go.Figure, export_name: str) -> None:
    st.plotly_chart(
        figure,
        width="stretch",
        config=CHART_CONFIG,
    )

    with st.popover("Export chart", icon=":material/download:"):
        st.caption("Select the export file format.")

        # generate the file only after the user selects a format
        st.download_button(
            "Download PDF",
            data=partial(export_chart_image, figure, "pdf"),
            file_name=f"llm-workbench-{export_name}.pdf",
            mime="application/pdf",
            key=f"analytics-export-{export_name}-pdf",
            on_click="ignore",
            width="stretch",
        )
        st.download_button(
            "Download PNG",
            data=partial(export_chart_image, figure, "png"),
            file_name=f"llm-workbench-{export_name}.png",
            mime="image/png",
            key=f"analytics-export-{export_name}-png",
            on_click="ignore",
            width="stretch",
        )
        st.download_button(
            "Download interactive HTML",
            data=partial(export_chart_html, figure),
            file_name=f"llm-workbench-{export_name}.html",
            mime="text/html",
            key=f"analytics-export-{export_name}-html",
            on_click="ignore",
            width="stretch",
        )


##### METRIC CARDS

def display_metric_cards(
        metrics: analytics.OverviewMetrics,
        label_distribution: pd.DataFrame,
        label_coverage: int,
) -> None:
    label_count = int(label_distribution["count"].sum())
    success_count = int(
        label_distribution.loc[label_distribution["label"] == "success", "count"].iloc[0]
    )
    # calculate success only from the currently selected label source
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


##### CHARTS

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

    # plotly uses a millisecond-wide range if there is only one date
    # add one day on each side to keep the bar visible and centered
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


def create_group_label_distribution_chart(
        summary: pd.DataFrame,
        group_column: str,
) -> go.Figure:
    chart_data = summary.melt(
        id_vars=[group_column, "label_count"],
        value_vars=list(analytics.LABEL_COUNT_COLUMNS),
        var_name="label",
        value_name="count",
    )
    chart_data["label"] = chart_data["label"].str.removesuffix("_count")
    chart_data["percentage"] = chart_data["count"] / chart_data["label_count"] * 100

    # hide percentages that would not fit inside their bar segment
    chart_data["text"] = chart_data["percentage"].apply(
        lambda percentage: f"{percentage:.0f}%" if percentage >= 5 else ""
    )

    group_order = summary[group_column].tolist()
    figure = px.bar(
        chart_data,
        x="percentage",
        y=group_column,
        color="label",
        orientation="h",
        barmode="stack",
        text="text",
        custom_data=["count", "label_count"],
        color_discrete_map=LABEL_COLORS,
        labels={
            "percentage": "Share of labels",
            group_column: "",
            "label": "Label",
        },
    )
    figure.update_traces(
        textposition="inside",
        hovertemplate=(
            "%{y}<br>%{fullData.name}: %{customdata[0]:,}"
            "<br>%{x:.1f}% of %{customdata[1]:,} labels<extra></extra>"
        ),
    )
    figure.update_xaxes(range=[0, 100], ticksuffix="%")
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(group_order)),
    )
    figure.update_layout(
        height=min(max(340, len(summary) * 42 + 110), 850),
        legend_title_text=None,
        legend_orientation="h",
        legend_y=-0.15,
        margin=dict(l=10, r=20, t=10, b=55),
    )

    return figure


def create_category_usage_chart(category_summary: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        category_summary,
        x="interaction_count",
        y="category",
        orientation="h",
        text="interaction_count",
        labels={"interaction_count": "Interactions", "category": ""},
    )
    figure.update_traces(
        marker_color=TARGET_COLOR,
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,} interactions<extra></extra>",
    )
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(category_summary["category"].tolist())),
    )
    figure.update_layout(
        height=min(max(340, len(category_summary) * 38 + 80), 850),
        margin=dict(l=10, r=60, t=10, b=10),
    )

    return figure


def create_model_category_heatmap(
        model_category_summary: pd.DataFrame,
        model_order: list[str],
        category_order: list[str],
) -> go.Figure:
    # build matrices for the cell color, text and hover details
    metric_columns = [
        "success_share",
        "label_count",
        *analytics.LABEL_COUNT_COLUMNS,
    ]
    matrices = {
        column: (
            model_category_summary
            .pivot(index="model", columns="category", values=column)
            .reindex(index=model_order, columns=category_order)
        )
        for column in metric_columns
    }
    custom_data = [
        [
            [
                matrices["label_count"].loc[model, category],
                matrices["success_count"].loc[model, category],
                matrices["refusal_count"].loc[model, category],
                matrices["unclear_count"].loc[model, category],
            ]
            for category in category_order
        ]
        for model in model_order
    ]
    cell_text = [
        [
            (
                f"{matrices['success_share'].loc[model, category]:.0f}%"
                f"<br>n={matrices['label_count'].loc[model, category]:.0f}"
                if pd.notna(matrices["success_share"].loc[model, category])
                else ""
            )
            for category in category_order
        ]
        for model in model_order
    ]

    figure = go.Figure(go.Heatmap(
        z=matrices["success_share"].values,
        x=category_order,
        y=model_order,
        customdata=custom_data,
        zmin=0,
        zmax=100,
        colorscale=[
            [0.0, LABEL_COLORS["refusal"]],
            [0.5, LABEL_COLORS["unclear"]],
            [1.0, LABEL_COLORS["success"]],
        ],
        colorbar=dict(title="Success", ticksuffix="%"),
        text=cell_text,
        texttemplate="%{text}",
        hoverongaps=False,
        hovertemplate=(
            "Model: %{y}<br>Category: %{x}<br>Success: %{z:.1f}%"
            "<br>Labels: %{customdata[0]:.0f}"
            "<br>Success: %{customdata[1]:.0f}"
            "<br>Refusal: %{customdata[2]:.0f}"
            "<br>Unclear: %{customdata[3]:.0f}<extra></extra>"
        ),
    ))
    figure.update_yaxes(autorange="reversed")
    figure.update_xaxes(tickangle=-30)
    figure.update_layout(
        height=min(max(360, len(model_order) * 58 + 140), 800),
        margin=dict(l=10, r=20, t=10, b=90),
    )

    return figure


def create_preset_model_heatmap(
        preset_model_summary: pd.DataFrame,
        preset_order: list[str],
        model_order: list[str],
) -> go.Figure:
    # keep every heatmap value in the same preset and model order
    metric_columns = [
        "success_share",
        "label_count",
        *analytics.LABEL_COUNT_COLUMNS,
    ]
    matrices = {
        column: (
            preset_model_summary
            .pivot(index="preset_label", columns="model", values=column)
            .reindex(index=preset_order, columns=model_order)
        )
        for column in metric_columns
    }
    custom_data = [
        [
            [
                matrices["label_count"].loc[preset, model],
                matrices["success_count"].loc[preset, model],
                matrices["refusal_count"].loc[preset, model],
                matrices["unclear_count"].loc[preset, model],
            ]
            for model in model_order
        ]
        for preset in preset_order
    ]
    cell_text = [
        [
            (
                f"{matrices['success_share'].loc[preset, model]:.0f}%"
                f"<br>n={matrices['label_count'].loc[preset, model]:.0f}"
                if pd.notna(matrices["success_share"].loc[preset, model])
                else ""
            )
            for model in model_order
        ]
        for preset in preset_order
    ]

    figure = go.Figure(go.Heatmap(
        z=matrices["success_share"].values,
        x=model_order,
        y=preset_order,
        customdata=custom_data,
        zmin=0,
        zmax=100,
        colorscale=[
            [0.0, LABEL_COLORS["refusal"]],
            [0.5, LABEL_COLORS["unclear"]],
            [1.0, LABEL_COLORS["success"]],
        ],
        colorbar=dict(title="Success", ticksuffix="%"),
        text=cell_text,
        texttemplate="%{text}",
        hoverongaps=False,
        hovertemplate=(
            "Preset: %{y}<br>Target model: %{x}<br>Success: %{z:.1f}%"
            "<br>Labels: %{customdata[0]:.0f}"
            "<br>Success: %{customdata[1]:.0f}"
            "<br>Refusal: %{customdata[2]:.0f}"
            "<br>Unclear: %{customdata[3]:.0f}<extra></extra>"
        ),
    ))
    # plotly skips some labels on larger heatmaps unless every tick is explicit
    figure.update_yaxes(
        autorange="reversed",
        tickmode="array",
        tickvals=preset_order,
        ticktext=preset_order,
    )
    figure.update_xaxes(tickangle=-25)
    figure.update_layout(
        height=min(max(380, len(preset_order) * 60 + 150), 850),
        margin=dict(l=10, r=20, t=10, b=120),
    )

    return figure


def create_model_cost_scatter(model_summary: pd.DataFrame) -> go.Figure:
    # don't display an empty color scale if no duration was recorded
    color_column = (
        "median_duration_seconds"
        if model_summary["median_duration_seconds"].notna().any()
        else None
    )
    figure = px.scatter(
        model_summary,
        x="average_cost",
        y="success_share",
        size="interaction_count",
        color=color_column,
        text="model",
        custom_data=[
            "model",
            "label_count",
            "success_count",
            "refusal_count",
            "unclear_count",
            "interaction_count",
        ],
        labels={
            "average_cost": "Average target cost",
            "success_share": "Success share",
            "median_duration_seconds": "Median duration (s)",
        },
        color_continuous_scale=DURATION_COLOR_SCALE,
        size_max=42,
    )
    figure.update_traces(
        textposition="top center",
        marker_opacity=0.85,
        marker_line_color="#17324D",
        marker_line_width=1,
        hovertemplate=(
            "%{customdata[0]}<br>Average target cost: $%{x:.6f}"
            "<br>Success: %{y:.1f}%"
            "<br>Labels: %{customdata[1]:,}"
            "<br>Success: %{customdata[2]:,}"
            "<br>Refusal: %{customdata[3]:,}"
            "<br>Unclear: %{customdata[4]:,}"
            "<br>Interactions: %{customdata[5]:,}<extra></extra>"
        ),
    )
    figure.update_xaxes(tickprefix="$", tickformat=".6f", rangemode="tozero")
    figure.update_yaxes(range=[0, 100], ticksuffix="%")
    figure.update_layout(
        height=460,
        margin=dict(l=10, r=20, t=10, b=10),
    )

    return figure


def create_judge_agreement_heatmap(
        agreement: pd.DataFrame,
        judge_order: list[str],
) -> go.Figure:
    # keep the same judge order in every heatmap matrix
    agreement_share = (
        agreement
        .pivot(index="judge_a", columns="judge_b", values="agreement_share")
        .reindex(index=judge_order, columns=judge_order)
    )
    overlap_count = (
        agreement
        .pivot(index="judge_a", columns="judge_b", values="overlap_count")
        .reindex(index=judge_order, columns=judge_order)
    )
    agreement_count = (
        agreement
        .pivot(index="judge_a", columns="judge_b", values="agreement_count")
        .reindex(index=judge_order, columns=judge_order)
    )
    custom_data = [
        [
            [
                overlap_count.loc[judge_a, judge_b],
                agreement_count.loc[judge_a, judge_b],
            ]
            for judge_b in judge_order
        ]
        for judge_a in judge_order
    ]
    cell_text = [
        [
            (
                f"{agreement_share.loc[judge_a, judge_b]:.0f}%"
                f"<br>n={overlap_count.loc[judge_a, judge_b]:.0f}"
                if pd.notna(agreement_share.loc[judge_a, judge_b])
                else ""
            )
            for judge_b in judge_order
        ]
        for judge_a in judge_order
    ]

    figure = go.Figure(go.Heatmap(
        z=agreement_share.values,
        x=judge_order,
        y=judge_order,
        customdata=custom_data,
        zmin=0,
        zmax=100,
        colorscale=[
            [0.0, LABEL_COLORS["refusal"]],
            [0.5, LABEL_COLORS["unclear"]],
            [1.0, LABEL_COLORS["success"]],
        ],
        colorbar=dict(title="Agreement", ticksuffix="%"),
        text=cell_text,
        texttemplate="%{text}",
        hoverongaps=False,
        hovertemplate=(
            "Judge A: %{y}<br>Judge B: %{x}<br>Agreement: %{z:.1f}%"
            "<br>Matching labels: %{customdata[1]:.0f}"
            "<br>Shared interactions: %{customdata[0]:.0f}<extra></extra>"
        ),
    ))
    figure.update_yaxes(autorange="reversed")
    figure.update_xaxes(tickangle=-25)
    figure.update_layout(
        height=min(max(420, len(judge_order) * 80 + 160), 850),
        margin=dict(l=10, r=20, t=10, b=120),
    )

    return figure


def create_judge_efficiency_scatter(judge_summary: pd.DataFrame) -> go.Figure:
    cost_midpoint = (
        judge_summary["average_cost"].min()
        + judge_summary["average_cost"].max()
    ) / 2

    # place labels toward the center of the chart
    text_positions = judge_summary["average_cost"].apply(
        lambda cost: "middle right" if cost <= cost_midpoint else "middle left"
    ).tolist()
    figure = px.scatter(
        judge_summary,
        x="average_cost",
        y="median_duration_seconds",
        size="evaluation_count",
        text="judge_setup",
        custom_data=[
            "judge_setup",
            "evaluation_count",
            "interaction_count",
            "label_count",
            "total_cost",
        ],
        labels={
            "average_cost": "Average judging cost",
            "median_duration_seconds": "Median judging duration",
        },
        size_max=42,
    )
    figure.update_traces(
        textposition=text_positions,
        marker_color=JUDGING_COLOR,
        marker_opacity=0.85,
        marker_line_color="#704A00",
        marker_line_width=1,
        hovertemplate=(
            "%{customdata[0]}<br>Average cost: $%{x:.6f}"
            "<br>Median duration: %{y:.2f} s"
            "<br>Evaluations: %{customdata[1]:,}"
            "<br>Interactions: %{customdata[2]:,}"
            "<br>Latest labels: %{customdata[3]:,}"
            "<br>Total cost: $%{customdata[4]:.6f}<extra></extra>"
        ),
    )
    figure.update_xaxes(tickprefix="$", tickformat=".6f", rangemode="tozero")
    figure.update_yaxes(tickformat=".2f", ticksuffix=" s", rangemode="tozero")
    figure.update_layout(
        height=460,
        margin=dict(l=10, r=20, t=10, b=10),
    )

    return figure


##### ANALYTICS VIEWS

def display_coverage(label: str, covered: int, total: int) -> None:
    percentage = covered / total if total else 0.0
    st.markdown(f"**{label}**")
    st.progress(percentage, text=f"{covered:,} of {total:,} · {percentage:.1%}")


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
        display_chart(
            create_label_distribution_chart(label_distribution),
            "label-distribution",
        )
    else:
        st.info("No labels from the selected source match the current filters.")

    st.subheader("Activity and cost")
    activity_column, cost_column = st.columns(2)
    activity = analytics.summarize_activity(filtered_interactions)
    costs = analytics.summarize_costs(
        filtered_interactions,
        filtered_judge_results,
    )

    with activity_column:
        st.markdown("**Interactions over time**")
        if activity.empty:
            st.info("No valid interaction timestamps are available.")
        else:
            display_chart(
                create_activity_chart(activity),
                "interactions-over-time",
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
            display_chart(
                create_cost_chart(costs),
                "cost-over-time",
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


def display_model_table(model_summary: pd.DataFrame) -> None:
    table = model_summary.rename(columns={
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
    })
    table = table[[
        "Model",
        "Interactions",
        "Labels",
        "Success",
        "Refusal",
        "Unclear",
        "Success share",
        "Median duration",
        "Median tokens",
        "Total target cost",
        "Average target cost",
    ]]

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height="content" if len(table) <= 20 else 750,
        column_config={
            "Success share": st.column_config.NumberColumn(format="%.1f%%"),
            "Median duration": st.column_config.NumberColumn(format="%.2f s"),
            "Median tokens": st.column_config.NumberColumn(format="%.0f"),
            "Total target cost": st.column_config.NumberColumn(format="$%.6f"),
            "Average target cost": st.column_config.NumberColumn(format="$%.6f"),
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

    comparable_models = model_summary.loc[
        model_summary["label_count"] >= minimum_sample_size
    ].copy()
    st.markdown("**Label distribution by model**")
    if comparable_models.empty:
        st.info("No model has enough labels for the selected minimum sample size.")
    else:
        display_chart(
            create_group_label_distribution_chart(comparable_models, "model"),
            "model-label-distribution",
        )

    st.markdown("**Success by model and category**")
    model_categories = analytics.summarize_model_categories(
        interactions,
        label_records,
    )
    comparable_cells = model_categories.loc[
        model_categories["label_count"] >= minimum_sample_size
    ].copy()
    if comparable_cells.empty:
        st.info(
            "No model-category pair has enough labels for the selected minimum "
            "sample size."
        )
    else:
        model_order = [
            model
            for model in model_summary["model"]
            if model in set(comparable_cells["model"])
        ]
        category_order = (
            comparable_cells
            .groupby("category")["interaction_count"]
            .sum()
            .sort_values(ascending=False)
            .index
            .tolist()
        )
        display_chart(
            create_model_category_heatmap(
                comparable_cells,
                model_order,
                category_order,
            ),
            "model-category-success",
        )

    st.markdown("**Average target cost vs success**")
    scatter_data = comparable_models.loc[
        comparable_models["success_share"].notna()
        & comparable_models["average_cost"].notna()
    ].copy()
    if scatter_data.empty:
        st.info(
            "No model has both enough labels and recorded target cost data for this "
            "comparison."
        )
    else:
        display_chart(
            create_model_cost_scatter(scatter_data),
            "model-cost-success",
        )


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
    display_chart(
        create_category_usage_chart(category_summary),
        "category-usage",
    )

    st.markdown("**Label distribution by category**")
    comparable_categories = category_summary.loc[
        category_summary["label_count"] >= minimum_sample_size
    ].copy()
    if comparable_categories.empty:
        st.info("No category has enough labels for the selected minimum sample size.")
    else:
        display_chart(
            create_group_label_distribution_chart(
                comparable_categories,
                "category",
            ),
            "category-label-distribution",
        )


def display_preset_table(preset_summary: pd.DataFrame) -> None:
    table = preset_summary.rename(columns={
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
    })
    table = table[[
        "Preset",
        "Prompt",
        "Categories",
        "Interactions",
        "Target models",
        "Labels",
        "Success",
        "Refusal",
        "Unclear",
        "Success share",
        "Median duration",
        "Median tokens",
        "Total target cost",
        "Average target cost",
    ]]

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height="content" if len(table) <= 20 else 750,
        column_config={
            "Prompt": st.column_config.TextColumn(width="large"),
            "Categories": st.column_config.MultiselectColumn(),
            "Success share": st.column_config.NumberColumn(format="%.1f%%"),
            "Median duration": st.column_config.NumberColumn(format="%.2f s"),
            "Median tokens": st.column_config.NumberColumn(format="%.0f"),
            "Total target cost": st.column_config.NumberColumn(format="$%.6f"),
            "Average target cost": st.column_config.NumberColumn(format="$%.6f"),
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

    preset_summary = analytics.summarize_presets(
        presets,
        interactions,
        label_records,
    )
    display_preset_table(preset_summary)

    comparable_presets = preset_summary.loc[
        preset_summary["label_count"] >= minimum_sample_size
    ].copy()
    st.markdown("**Label distribution by preset**")
    if comparable_presets.empty:
        st.info("No preset has enough labels for the selected minimum sample size.")
    else:
        preset_order = comparable_presets["preset_label"].tolist()
        label_distribution_chart = create_group_label_distribution_chart(
            comparable_presets,
            "preset_label",
        )
        # show the id next to every bar instead of letting plotly thin the axis
        label_distribution_chart.update_yaxes(
            categoryorder="array",
            categoryarray=preset_order,
            autorange="reversed",
            tickmode="array",
            tickvals=preset_order,
            ticktext=preset_order,
        )
        display_chart(
            label_distribution_chart,
            "preset-label-distribution",
        )

    st.markdown("**Success by preset and target model**")
    preset_models = analytics.summarize_preset_models(
        presets,
        interactions,
        label_records,
    )
    comparable_cells = preset_models.loc[
        preset_models["label_count"] >= minimum_sample_size
    ].copy()
    if comparable_cells.empty:
        st.info(
            "No preset-model pair has enough labels for the selected minimum "
            "sample size."
        )
    else:
        available_presets = set(comparable_cells["preset_label"])
        preset_order = [
            preset
            for preset in preset_summary["preset_label"]
            if preset in available_presets
        ]
        model_order = (
            comparable_cells
            .groupby("model")["interaction_count"]
            .sum()
            .sort_values(ascending=False)
            .index
            .tolist()
        )
        display_chart(
            create_preset_model_heatmap(
                comparable_cells,
                preset_order,
                model_order,
            ),
            "preset-model-success",
        )


def display_judge_table(judge_summary: pd.DataFrame) -> None:
    table = judge_summary.rename(columns={
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
    })
    table = table[[
        "Judge setup",
        "Evaluations",
        "Interactions",
        "Latest labels",
        "Success",
        "Refusal",
        "Unclear",
        "Success share",
        "Median duration",
        "Total judging cost",
        "Average judging cost",
    ]]

    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height="content" if len(table) <= 20 else 750,
        column_config={
            "Success share": st.column_config.NumberColumn(format="%.1f%%"),
            "Median duration": st.column_config.NumberColumn(format="%.2f s"),
            "Total judging cost": st.column_config.NumberColumn(format="$%.6f"),
            "Average judging cost": st.column_config.NumberColumn(format="$%.6f"),
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

    comparable_judges = judge_summary.loc[
        judge_summary["label_count"] >= minimum_sample_size
    ].copy()
    st.markdown("**Label distribution by judge setup**")
    if comparable_judges.empty:
        st.info("No judge setup has enough labels for the selected minimum sample size.")
    else:
        display_chart(
            create_group_label_distribution_chart(
                comparable_judges,
                "judge_setup",
            ),
            "judge-label-distribution",
        )

    st.markdown("**Agreement between judge setups**")
    judge_order = comparable_judges["judge_setup"].tolist()
    if len(judge_order) < 2:
        st.info("Select at least two judge setups with enough labels to compare agreement.")
    else:
        agreement = analytics.summarize_judge_agreement(judge_results)
        agreement = agreement.loc[
            agreement["judge_a"].isin(judge_order)
            & agreement["judge_b"].isin(judge_order)
            & agreement["overlap_count"].ge(minimum_sample_size)
        ].copy()
        pairwise_agreement = agreement.loc[
            agreement["judge_a"] != agreement["judge_b"]
        ]

        if pairwise_agreement.empty:
            st.info(
                "No pair of judge setups has enough shared interactions for the "
                "selected minimum sample size."
            )
        else:
            display_chart(
                create_judge_agreement_heatmap(agreement, judge_order),
                "judge-agreement",
            )

    st.markdown("**Judging cost vs duration**")
    efficiency_data = judge_summary.loc[
        judge_summary["average_cost"].notna()
        & judge_summary["median_duration_seconds"].notna()
    ].copy()
    if efficiency_data.empty:
        st.info("No judge setup has both recorded cost and duration data.")
    else:
        display_chart(
            create_judge_efficiency_scatter(efficiency_data),
            "judge-cost-duration",
        )


##### PAGE

view_utils.page_config("Analytics")
st.title("Analytics")
st.caption("Explore experiment outcomes, activity, cost, and data coverage.")

# apply responsive styles only to the analytics containers
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

    # keep judge filters available for judge labels and the Judges view
    if label_source == "LLM judge" or current_view == "Judges":
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

# use one latest valid label for every judge setup
latest_judge_results = analytics.get_latest_judge_results(filtered_judge_results)
valid_latest_judge_results = latest_judge_results.loc[
    latest_judge_results["label"].isin(analytics.LABELS)
]

# choose labels used by the shared metrics and outcome charts
if label_source == "Manual":
    label_records = analytics.get_manual_label_records(filtered_interactions)
    label_source_caption = "Each manually labeled interaction contributes one label."
else:
    label_records = analytics.get_judge_label_records(valid_latest_judge_results)
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
    display_overview(
        filtered_interactions,
        filtered_judge_results,
        label_distribution,
        label_source_caption,
        metrics,
    )
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
        display_model_analytics(
            filtered_interactions,
            label_records,
            minimum_sample_size,
        )
    elif selected_view == "Categories":
        display_category_analytics(
            filtered_interactions,
            label_records,
            minimum_sample_size,
        )
    elif selected_view == "Presets":
        display_preset_analytics(
            presets,
            filtered_interactions,
            label_records,
            minimum_sample_size,
        )
    else:
        if label_source == "Manual":
            st.info(
                "Judge analytics use LLM judge results. The label source selector "
                "still controls the shared KPI cards above."
            )
        display_judge_analytics(
            filtered_judge_results,
            minimum_sample_size,
        )
