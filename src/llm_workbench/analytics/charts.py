from collections.abc import Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from llm_workbench.analytics.stats import LABEL_COUNT_COLUMNS


LABEL_COLORS = {
    "success": "#1BC46F",
    "refusal": "#F54927",
    "unclear": "#D9A300",
}
SHARE_COLOR_SCALE = [
    [0.0, LABEL_COLORS["refusal"]],
    [0.5, LABEL_COLORS["unclear"]],
    [1.0, LABEL_COLORS["success"]],
]

TARGET_COLOR = "#0072B2"
JUDGING_COLOR = "#E69F00"
DURATION_COLOR_SCALE = [
    [0.0, "#56B4E9"],
    [0.5, "#0072B2"],
    [1.0, "#003B5C"],
]

CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": False,
}

CHART_EXPORT_WIDTH = 1400
MINIMUM_CHART_EXPORT_HEIGHT = 500
DAY_IN_MILLISECONDS = 24 * 60 * 60 * 1000
DAILY_BAR_WIDTH = DAY_IN_MILLISECONDS * 7 // 10

LABEL_HOVER_LINES = (
    "<br>Labels: %{customdata[0]:.0f}"
    "<br>Success: %{customdata[1]:.0f}"
    "<br>Refusal: %{customdata[2]:.0f}"
    "<br>Unclear: %{customdata[3]:.0f}<extra></extra>"
)


##### EXPORT

def prepare_chart_for_export(figure: go.Figure) -> go.Figure:
    # copy the figure, so export changes don't affect the dashboard
    export_figure = go.Figure(figure)

    # add enough space for axis titles and long values
    export_figure.update_xaxes(automargin=True)
    export_figure.update_yaxes(automargin=True)

    # allow model names next to scatter points to use the chart margins
    export_figure.update_traces(cliponaxis=False, selector={"type": "scatter"})

    return export_figure


def export_chart_image(figure: go.Figure, image_format: str) -> bytes:
    export_figure = prepare_chart_for_export(figure)
    height = max(export_figure.layout.height or 0, MINIMUM_CHART_EXPORT_HEIGHT)

    # png needs a larger scale, while pdf remains vector-based
    scale = 2 if image_format == "png" else 1

    return export_figure.to_image(format=image_format, width=CHART_EXPORT_WIDTH, height=height, scale=scale)


def export_chart_html(figure: go.Figure) -> bytes:
    export_figure = prepare_chart_for_export(figure)

    # include plotly, so the downloaded chart also works offline
    return export_figure.to_html(config=CHART_CONFIG, full_html=True, include_plotlyjs=True).encode("utf-8")


##### HELPERS

def _scaled_height(row_count: int, row_height: int, padding: int, minimum: int, maximum: int) -> int:
    # grow the chart with the number of rows, within readable limits
    return min(max(minimum, row_count * row_height + padding), maximum)


def _create_share_heatmap(
        summary: pd.DataFrame,
        index: str,
        columns: str,
        index_order: list[str],
        column_order: list[str],
        share_column: str,
        sample_size_column: str,
        hover_columns: Sequence[str],
        hovertemplate: str,
        colorbar_title: str,
) -> go.Figure:
    def to_matrix(values: str) -> pd.DataFrame:
        # keep every matrix in the same row and column order
        return (
            summary
            .pivot(index=index, columns=columns, values=values)
            .reindex(index=index_order, columns=column_order)
        )

    shares = to_matrix(share_column)
    sample_sizes = to_matrix(sample_size_column)
    hover_matrices = [to_matrix(column) for column in hover_columns]

    custom_data = [
        [[matrix.loc[row, column] for matrix in hover_matrices] for column in column_order]
        for row in index_order
    ]
    cell_text = [
        [
            (
                f"{shares.loc[row, column]:.0f}%<br>n={sample_sizes.loc[row, column]:.0f}"
                if pd.notna(shares.loc[row, column])
                else ""
            )
            for column in column_order
        ]
        for row in index_order
    ]

    return go.Figure(go.Heatmap(
        z=shares.values,
        x=column_order,
        y=index_order,
        customdata=custom_data,
        zmin=0,
        zmax=100,
        colorscale=SHARE_COLOR_SCALE,
        colorbar=dict(title=colorbar_title, ticksuffix="%"),
        text=cell_text,
        texttemplate="%{text}",
        hoverongaps=False,
        hovertemplate=hovertemplate,
    ))


def _configure_daily_bar_chart(figure: go.Figure, dates: pd.Series) -> None:
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
            range=[first_date - pd.Timedelta(days=1), last_date + pd.Timedelta(days=1)],
            tickmode="array",
            tickvals=[first_date],
            ticktext=[first_date.strftime("%b %d, %Y")],
        )


##### OUTCOMES

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
    figure.update_yaxes(categoryorder="array", categoryarray=["Unclear", "Refusal", "Success"])
    figure.update_layout(height=320, showlegend=False, margin=dict(l=10, r=80, t=10, b=10))

    return figure


def create_group_label_distribution_chart(
        summary: pd.DataFrame,
        group_column: str,
) -> go.Figure:
    chart_data = summary.melt(
        id_vars=[group_column, "label_count"],
        value_vars=list(LABEL_COUNT_COLUMNS),
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
        labels={"percentage": "Share of labels", group_column: "", "label": "Label"},
    )
    figure.update_traces(
        textposition="inside",
        hovertemplate=(
            "%{y}<br>%{fullData.name}: %{customdata[0]:,}"
            "<br>%{x:.1f}% of %{customdata[1]:,} labels<extra></extra>"
        ),
    )
    figure.update_xaxes(range=[0, 100], ticksuffix="%")
    figure.update_yaxes(categoryorder="array", categoryarray=list(reversed(group_order)))
    figure.update_layout(
        height=_scaled_height(len(summary), row_height=42, padding=110, minimum=340, maximum=850),
        legend_title_text=None,
        legend_orientation="h",
        legend_y=-0.15,
        margin=dict(l=10, r=20, t=10, b=55),
    )

    return figure


##### ACTIVITY AND COST

def create_activity_chart(activity: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        activity,
        x="date",
        y="interaction_count",
        labels={"date": "Date", "interaction_count": "Responses"},
    )
    figure.update_traces(
        marker_color=TARGET_COLOR,
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,} responses<extra></extra>",
    )
    _configure_daily_bar_chart(figure, activity["date"])
    figure.update_yaxes(rangemode="tozero")

    # avoid fractional ticks for small counts
    if not activity.empty and activity["interaction_count"].max() <= 10:
        figure.update_yaxes(dtick=1)

    figure.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))

    return figure


def create_cost_chart(costs: pd.DataFrame) -> go.Figure:
    chart_data = costs.melt(
        id_vars="date",
        value_vars=["target_cost", "judging_cost"],
        var_name="source",
        value_name="cost",
    )
    chart_data["source"] = chart_data["source"].map({
        "target_cost": "Target model",
        "judging_cost": "Judging",
    })

    figure = px.bar(
        chart_data,
        x="date",
        y="cost",
        color="source",
        barmode="stack",
        labels={"date": "Date", "cost": "Cost", "source": "Source"},
        color_discrete_map={"Target model": TARGET_COLOR, "Judging": JUDGING_COLOR},
    )
    figure.update_traces(hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: $%{y:.6f}<extra></extra>")
    _configure_daily_bar_chart(figure, costs["date"])
    figure.update_yaxes(tickprefix="$", tickformat=".4f")
    figure.update_layout(
        height=340,
        legend_title_text=None,
        legend_orientation="h",
        legend_y=-0.25,
        margin=dict(l=10, r=10, t=10, b=55),
    )

    return figure


##### MODELS, CATEGORIES AND PROMPTS

def create_category_usage_chart(category_summary: pd.DataFrame) -> go.Figure:
    figure = px.bar(
        category_summary,
        x="interaction_count",
        y="category",
        orientation="h",
        text="interaction_count",
        labels={"interaction_count": "Responses", "category": ""},
    )
    figure.update_traces(
        marker_color=TARGET_COLOR,
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>%{x:,} responses<extra></extra>",
    )
    figure.update_yaxes(
        categoryorder="array",
        categoryarray=list(reversed(category_summary["category"].tolist())),
    )
    figure.update_layout(
        height=_scaled_height(len(category_summary), row_height=38, padding=80, minimum=340, maximum=850),
        margin=dict(l=10, r=60, t=10, b=10),
    )

    return figure


def create_model_category_heatmap(
        model_category_summary: pd.DataFrame,
        model_order: list[str],
        category_order: list[str],
) -> go.Figure:
    figure = _create_share_heatmap(
        model_category_summary,
        index="model",
        columns="category",
        index_order=model_order,
        column_order=category_order,
        share_column="success_share",
        sample_size_column="label_count",
        hover_columns=["label_count", *LABEL_COUNT_COLUMNS],
        hovertemplate="Model: %{y}<br>Category: %{x}<br>Success: %{z:.1f}%" + LABEL_HOVER_LINES,
        colorbar_title="Success",
    )
    figure.update_yaxes(autorange="reversed")
    figure.update_xaxes(tickangle=-30)
    figure.update_layout(
        height=_scaled_height(len(model_order), row_height=58, padding=140, minimum=360, maximum=800),
        margin=dict(l=10, r=20, t=10, b=90),
    )

    return figure


def create_prompt_model_heatmap(
        prompt_model_summary: pd.DataFrame,
        prompt_order: list[str],
        model_order: list[str],
) -> go.Figure:
    figure = _create_share_heatmap(
        prompt_model_summary,
        index="prompt_label",
        columns="model",
        index_order=prompt_order,
        column_order=model_order,
        share_column="success_share",
        sample_size_column="label_count",
        hover_columns=["label_count", *LABEL_COUNT_COLUMNS],
        hovertemplate="Prompt: %{y}<br>Target model: %{x}<br>Success: %{z:.1f}%" + LABEL_HOVER_LINES,
        colorbar_title="Success",
    )
    # plotly skips some labels on larger heatmaps unless every tick is explicit
    figure.update_yaxes(autorange="reversed", tickmode="array", tickvals=prompt_order, ticktext=prompt_order)
    figure.update_xaxes(tickangle=-25)
    figure.update_layout(
        height=_scaled_height(len(prompt_order), row_height=60, padding=150, minimum=380, maximum=850),
        margin=dict(l=10, r=20, t=10, b=120),
    )

    return figure


def create_model_cost_scatter(model_summary: pd.DataFrame) -> go.Figure:
    # don't display an empty color scale if no duration was recorded
    color_column = "median_duration_seconds" if model_summary["median_duration_seconds"].notna().any() else None

    figure = px.scatter(
        model_summary,
        x="average_cost",
        y="success_share",
        size="interaction_count",
        color=color_column,
        text="model",
        custom_data=["model", "label_count", *LABEL_COUNT_COLUMNS, "interaction_count"],
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
            "<br>Responses: %{customdata[5]:,}<extra></extra>"
        ),
    )
    figure.update_xaxes(tickprefix="$", tickformat=".6f", rangemode="tozero")
    figure.update_yaxes(range=[0, 100], ticksuffix="%")
    figure.update_layout(height=460, margin=dict(l=10, r=20, t=10, b=10))

    return figure


##### JUDGES

def create_judge_agreement_heatmap(
        agreement: pd.DataFrame,
        judge_order: list[str],
) -> go.Figure:
    figure = _create_share_heatmap(
        agreement,
        index="judge_a",
        columns="judge_b",
        index_order=judge_order,
        column_order=judge_order,
        share_column="agreement_share",
        sample_size_column="overlap_count",
        hover_columns=["overlap_count", "agreement_count"],
        hovertemplate=(
            "Judge A: %{y}<br>Judge B: %{x}<br>Agreement: %{z:.1f}%"
            "<br>Matching labels: %{customdata[1]:.0f}"
            "<br>Shared responses: %{customdata[0]:.0f}<extra></extra>"
        ),
        colorbar_title="Agreement",
    )
    figure.update_yaxes(autorange="reversed")
    figure.update_xaxes(tickangle=-25)
    figure.update_layout(
        height=_scaled_height(len(judge_order), row_height=80, padding=160, minimum=420, maximum=850),
        margin=dict(l=10, r=20, t=10, b=120),
    )

    return figure


def create_judge_efficiency_scatter(judge_summary: pd.DataFrame) -> go.Figure:
    cost_midpoint = (judge_summary["average_cost"].min() + judge_summary["average_cost"].max()) / 2

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
        custom_data=["judge_setup", "evaluation_count", "interaction_count", "label_count", "total_cost"],
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
            "<br>Responses: %{customdata[2]:,}"
            "<br>Latest labels: %{customdata[3]:,}"
            "<br>Total cost: $%{customdata[4]:.6f}<extra></extra>"
        ),
    )
    figure.update_xaxes(tickprefix="$", tickformat=".6f", rangemode="tozero")
    figure.update_yaxes(tickformat=".2f", ticksuffix=" s", rangemode="tozero")
    figure.update_layout(height=460, margin=dict(l=10, r=20, t=10, b=10))

    return figure
