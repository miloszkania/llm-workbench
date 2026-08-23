import plotly.graph_objects as go
import streamlit
from plotly.subplots import make_subplots
import streamlit as st

from src import view_utils


LABEL_ORDER = ["🔴", "🟢", "🟡"]

LABEL_NAMES = {
    "🔴": "Refusal",
    "🟢": "Success",
    "🟡": "Unclear",
}

LABEL_COLORS = {
    "🔴": "#F54927",
    "🟢": "#1BC46F",
    "🟡": "#D9A300",
}

CATEGORY_NAMES = {
    "style-injection": "Style Injection",
    "role-playing": "Role-Playing",
    "direct": "Direct baseline",
    "low-res-languages": "Low-Resource Languages",
    "obfuscation": "Obfuscation",
    "distractions": "Distractions",
    "emotions": "Emotions",
    "credit-card": "Credit Card Skimming",
    "election": "Election Tampering",
    "keylogger": "Keylogger",
    "genocide": "Genocide Justification",
}

HEATMAP_CATEGORY_NAMES = {
    **CATEGORY_NAMES,
    "style-injection": "Style<br>Injection",
    "role-playing": "Role-Playing",
    "direct": "Direct<br>baseline",
    "low-res-languages": "Low-Resource<br>Languages",
    "credit-card": "Credit Card<br>Skimming",
    "election": "Election<br>Tampering",
    "genocide": "Genocide<br>Justification",
}

TEMPLATE_ORDER = [
    "style-injection",
    "role-playing",
    "direct",
    "low-res-languages",
    "obfuscation",
    "distractions",
    "emotions",
]

PAYLOAD_ORDER = [
    "keylogger",
    "election",
    "credit-card",
    "genocide",
]

MODEL_ORDER = [
    "Hermes 4 (70B)",
    "Llama 3.3 (70B)",
    "Qwen3-Next (80B)",
    "Llama 3.2 (3B)",
    "Gemma 4 (31B)",
    "gpt-oss-20b (21B)",
    "gpt-oss-120b (117B)",
]

history_table = view_utils.get_all_history_entries(fill_null=True)

if history_table.empty:
   st.info("No data yet!")
   st.stop()


def parse_model_ids(i: str):
    i = i.replace(
        "qwen3-next-80b-a3b-instruct",
        "Qwen3-Next (80B)",
    )
    i = i.replace("hermes-4-70b", "Hermes 4 (70B)")
    i = i.replace(
        "llama-3.3-70b-instruct",
        "Llama 3.3 (70B)",
    )
    i = i.replace(
        "llama-3.2-3b-instruct",
        "Llama 3.2 (3B)",
    )
    i = i.replace("gemma-4-31b-it", "Gemma 4 (31B)")
    i = i.replace("gpt-oss-120b", "gpt-oss-120b (117B)")
    i = i.replace("gpt-oss-20b", "gpt-oss-20b (21B)")
    return i[i.find("/") + 1:]


def build_asr_matrix(history_df, category_order):
    data = history_df.explode("categories")
    data = data[data["categories"].isin(category_order)].copy()
    data["model"] = (
        data["model"]
        .apply(view_utils.remove_timestamp_from_model_id)
        .apply(parse_model_ids)
    )

    rates = (
        data.groupby(["model", "categories"])["judge_label"]
        .apply(lambda labels: (labels == "🟢").mean() * 100)
        .unstack()
    )

    return rates.reindex(
        index=MODEL_ORDER,
        columns=category_order,
    )


def p_combined_asr_heatmaps(history_df):
    condition_matrix = build_asr_matrix(
        history_df,
        TEMPLATE_ORDER,
    )
    payload_matrix = build_asr_matrix(
        history_df,
        PAYLOAD_ORDER,
    )

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_yaxes=True,
        row_heights=[0.56, 0.44],
        vertical_spacing=0.24,
        subplot_titles=(
            "Attack categories + direct baseline",
            "Payloads",
        ),
    )

    for row, matrix in enumerate(
        [condition_matrix, payload_matrix],
        start=1,
    ):
        fig.add_trace(
            go.Heatmap(
                z=matrix.values,
                x=[
                    HEATMAP_CATEGORY_NAMES[name]
                    for name in matrix.columns
                ],
                y=matrix.index,
                text=matrix.values,
                texttemplate="%{text:.1f}",
                textfont=dict(size=24),
                coloraxis="coloraxis",
                hovertemplate=(
                    "Model: %{y}<br>"
                    "Category: %{x}<br>"
                    "ASR: %{z:.1f}%<extra></extra>"
                ),
            ),
            row=row,
            col=1,
        )

    fig.update_layout(
        template="simple_white",
        width=1250,
        height=1140,
        font=dict(family="Helvetica", size=26),
        margin=dict(l=230, r=130, t=75, b=90),
        coloraxis=dict(
            colorscale="Reds",
            cmin=0,
            cmax=90,
            colorbar=dict(
                tickfont=dict(size=24),
                len=0.86,
                thickness=24,
                x=1.02,
                y=0.5,
            ),
        ),
    )

    fig.update_annotations(font=dict(size=30))
    for annotation in fig.layout.annotations:
        annotation.y += 0.015
    fig.add_annotation(
        text="ASR (%)",
        x=1.064,
        y=0.945,
        xref="paper",
        yref="paper",
        xanchor="center",
        yanchor="bottom",
        showarrow=False,
        font=dict(size=27),
    )
    fig.update_xaxes(
        tickangle=-50,
        tickfont=dict(size=26),
        row=1,
        col=1,
    )
    fig.update_xaxes(
        tickangle=0,
        tickfont=dict(size=26),
        row=2,
        col=1,
    )
    fig.update_yaxes(
        title_text=None,
        tickfont=dict(size=26),
        showticklabels=True,
    )

    # filename = "heatmap_models_conditions_and_payloads.pdf"
    # fig.write_image(
    #     f"../Paper/figures/results/{filename}",
    #     width=1250,
    #     height=1140,
    # )
    st.plotly_chart(fig, use_container_width=True)


def build_label_distribution(
    history_df,
    category_order,
    label_column="judge_label",
):
    data = history_df.explode("categories")
    data = data[data["categories"].isin(category_order)].copy()

    counts = (
        data.groupby(["categories", label_column])
        .size()
        .unstack(fill_value=0)
    )
    percentages = counts.div(
        counts.sum(axis=1),
        axis=0,
    ) * 100

    return percentages.reindex(
        index=category_order,
        columns=LABEL_ORDER,
        fill_value=0,
    )


def build_model_label_distribution(
    history_df,
    label_column="judge_label",
):
    data = history_df.copy()
    data["model"] = (
        data["model"]
        .apply(view_utils.remove_timestamp_from_model_id)
        .apply(parse_model_ids)
    )

    counts = (
        data.groupby(["model", label_column])
        .size()
        .unstack(fill_value=0)
    )
    percentages = counts.div(
        counts.sum(axis=1),
        axis=0,
    ) * 100
    percentages = percentages.reindex(
        columns=LABEL_ORDER,
        fill_value=0,
    )

    return percentages.sort_values(
        by="🟢",
        ascending=False,
    )
    # return percentages.sort_values(MODEL_ORDER)


BAR_FONT_SIZE = 23
BAR_WIDTH = 0.82
BAR_ROW_HEIGHT = 65
BAR_TOP_MARGIN = 105
BAR_BOTTOM_MARGIN = 110
BAR_FIGURE_WIDTH = 1100
BAR_LEFT_MARGIN = 270
BAR_RIGHT_MARGIN = 50


def export_label_distribution(
    distribution,
    displayed_rows,
    filename,
    hover_row_name,
):
    fig = go.Figure()

    for label in LABEL_ORDER:
        fig.add_trace(
            go.Bar(
                x=distribution[label],
                y=displayed_rows,
                name=LABEL_NAMES[label],
                marker_color=LABEL_COLORS[label],
                orientation="h",
                width=BAR_WIDTH,
                hovertemplate=(
                    f"{hover_row_name}: %{{y}}<br>"
                    f"Label: {LABEL_NAMES[label]}<br>"
                    "Share: %{x:.1f}%<extra></extra>"
                ),
            )
        )

    figure_height = (
        BAR_TOP_MARGIN
        + BAR_BOTTOM_MARGIN
        + BAR_ROW_HEIGHT * len(displayed_rows)
    )

    fig.update_layout(
        template="simple_white",
        barmode="stack",
        bargap=0.08,
        width=BAR_FIGURE_WIDTH,
        height=figure_height,
        font=dict(
            family="Helvetica",
            size=BAR_FONT_SIZE,
        ),
        margin=dict(
            l=BAR_LEFT_MARGIN,
            r=BAR_RIGHT_MARGIN,
            t=BAR_TOP_MARGIN,
            b=BAR_BOTTOM_MARGIN,
        ),
        legend=dict(
            orientation="h",
            xref="container",
            yref="container",
            xanchor="center",
            x=0.5,
            yanchor="top",
            y=0.95,
            font=dict(size=BAR_FONT_SIZE),
        ),
        legend_traceorder="normal",
    )
    fig.update_xaxes(
        title_text=None,
        tickfont=dict(size=BAR_FONT_SIZE),
        range=[0, 100],
        dtick=20,
    )
    fig.update_yaxes(
        title_text=None,
        tickfont=dict(size=BAR_FONT_SIZE),
        autorange="reversed",
    )
    fig.add_annotation(
        text="Evaluation label distribution (%)",
        x=0.5,
        xref="paper",
        xanchor="center",
        xshift=(BAR_RIGHT_MARGIN - BAR_LEFT_MARGIN) / 2,
        y=-0.05,
        yref="paper",
        yanchor="top",
        yshift=-44,
        showarrow=False,
        font=dict(
            family="Helvetica",
            size=BAR_FONT_SIZE,
        ),
    )

    streamlit.plotly_chart(fig)

    # fig.write_image(
    #     f"../Paper/figures/results/{filename}",
    #     width=BAR_FIGURE_WIDTH,
    #     height=figure_height,
    # )


def p_category_label_distribution(
    history_df,
    category_order,
    filename,
    label_column="judge_label",
):
    distribution = build_label_distribution(
        history_df,
        category_order,
        label_column,
    )
    displayed_categories = [
        CATEGORY_NAMES[category]
        for category in distribution.index
    ]

    export_label_distribution(
        distribution,
        displayed_categories,
        filename,
        hover_row_name="Category",
    )


def p_model_label_distribution(
    history_df,
    label_column,
    filename,
):
    distribution = build_model_label_distribution(
        history_df,
        label_column,
    )

    export_label_distribution(
        distribution,
        distribution.index.tolist(),
        filename,
        hover_row_name="Target model",
    )


if history_table["categories"].explode().dropna().unique().tolist():
    p_combined_asr_heatmaps(history_table)
    st.divider()
    p_category_label_distribution(
        history_table,
        TEMPLATE_ORDER,
        filename=(
            "chart_label_distribution_"
            "template_categories_gemma.pdf"
        ),
        label_column="judge_label",
    )
    st.divider()
    p_category_label_distribution(
        history_table,
        PAYLOAD_ORDER,
        filename="chart_asr_task_categories_gemma.pdf",
        label_column="judge_label",
    )
st.divider()
p_model_label_distribution(
    history_table,
    label_column="judge_label",
    filename="chart_asr_models_gemma.pdf",
)
st.divider()
