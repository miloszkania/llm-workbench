import pandas as pd
import streamlit as st
import plotly.express as px

from src import view_utils, widgets

st.set_page_config(
    layout="wide",
    page_title="Pipeline: Dashboard"
)

LABEL_OPTIONS = ["🟢", "🔴", "🟡"]

label_colors = {
    "🟢": "#1BC46F",
    "🔴": "#F54927",
    "🟡": "#FFED00",
    "⏳": "#7F7F7F",
}

st.title("Dashboard")
tab_percentage, tab_count = st.tabs(["Percentage", "Count"])


def export_chart(fig, filename, height, font_size=14):
    fig.update_xaxes(
        automargin=True,
        title_standoff=15,
    )

    if "heatmap" in filename:
        fig.update_layout(
            template="simple_white",
            font=dict(family="Helvetica", size=font_size),
            showlegend=False,
            margin=dict(l=10, r=20, t=30, b=80),
            yaxis_title=None,
        )

    else:
        fig.update_layout(
            template="simple_white",
            font=dict(family="Helvetica", size=font_size),
            # showlegend=False,
            # margin=dict(l=10, r=20, t=30, b=80),
            yaxis_title=None,

            showlegend="stacked" in filename,  # only show legend for stacked bars
            legend = dict( orientation = "h", yanchor = "top", y = -0.35, xanchor = "center", x = 0.5, ),
            margin = dict(l=10, r=20, t=30, b=100),  # more bottom margin for legend

            # make the x-axis caption be centered relative to the whole figure
            xaxis_title=None,
            annotations=[
                dict(
                    text="ASR (percentage)",
                    x=0.406,
                    # y=-0.3,
                    y=-0.25,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=14),
                )
            ],
        )

    # if not os.path.exists(f"figures/{filename}"):
    #     fig.write_image(f"figures/{filename}", height=height)



###### Percentage

### Categories

def p_ai_judge_success_rate(history_df, canvas):
    history_df = history_df.loc[
        (history_df["judge_label"].isin(LABEL_OPTIONS)) & (history_df["label"].isin(LABEL_OPTIONS))
    ]

    if history_df.empty:
        rate = 0
    else:
        rate = len(history_df.loc[history_df["judge_label"] == history_df["label"]])
        rate /= len(history_df)
        rate = round(rate * 100, 2)

    canvas.markdown(f"##### **Percentage of right LLM-as-a-Judge labels (Gemma)**: **`{rate} %`**")


# def p_ai_judge_match_rate(history_df, canvas):
#     history_df = history_df.loc[
#         (history_df["judge_label"].isin(LABEL_OPTIONS))
#         & (history_df["judge_label_2"].isin(LABEL_OPTIONS))
#     ]
#
#     if history_df.empty:
#         rate = 0
#     else:
#         rate = len(history_df.loc[history_df["judge_label"] == history_df["judge_label_2"]])
#         rate /= len(history_df)
#         rate = round(rate * 100, 2)
#
#     canvas.markdown(f"##### **Percentage of matching LLM-as-a-Judge labels**: **`{rate} %`**")


def p_chart_label_distribution_per_category(history_df, canvas, label_column="label"):
    label_per_category_counts = (
        history_df.explode("categories")
        .groupby(["categories", label_column])
        .size()
        .reset_index(name="counts")
    )

    category_use_count = (
        label_per_category_counts
        .groupby("categories")
        ["counts"]
        .transform("sum")
    )

    label_per_category_counts["percentage"] = (label_per_category_counts["counts"] / category_use_count) * 100

    # sort results (more green -> higher position)
    pivot_df = label_per_category_counts.pivot(index="categories", columns=label_column, values="percentage").fillna(0)
    if "🟢" in pivot_df.columns:
        sorted_categories = pivot_df.sort_values(by="🟢", ascending=False).index.tolist()
    else:
        sorted_categories = pivot_df.index.tolist()

    fig = px.bar(
        data_frame=label_per_category_counts,
        x="percentage",
        y="categories",
        color=label_column,
        color_discrete_map=label_colors,
        labels={"percentage": "ASR (percentage)"},
        orientation="h",
        category_orders={"categories": sorted_categories},
    )

    # export_chart(fig, f"chart_asr_{category_subset_name.lower()}_{"llama" if label_column.endswith("2") else "gemma"}.pdf", height=260)

    canvas.plotly_chart(fig, key=f"p_chart_label_distribution_per_category_{label_column}")


def p_chart_date_category_success_over_time(history_df, canvas, label_column="label"):
    # extract only the date
    history_df["time"] = pd.to_datetime(history_df["time"]).dt.date

    history_df = history_df.explode("categories")

    all_categories = history_df["categories"].dropna().unique().tolist()

    history_df["categories"] = pd.Categorical(
        history_df["categories"],
        categories=all_categories,
    )

    daily_df = (
        history_df.groupby(["categories", "time"])
        .agg(
            daily_use=("id", "count"),
            daily_success=(label_column, lambda x: (x == "🟢").sum()),
        )
        .reset_index()
        .sort_values("time")
    )

    daily_df["cum_use_count"] = daily_df.groupby("categories")["daily_use"].cumsum()
    daily_df["cum_success_count"] = daily_df.groupby("categories")["daily_success"].cumsum()

    daily_df["percentage"] = (daily_df["cum_success_count"] / daily_df["cum_use_count"]) * 100
    daily_df["percentage"] = daily_df["percentage"].fillna(0)

    stats = px.line(
        daily_df,
        x="time",
        y="percentage",
        color="categories",
        markers=True,
        labels={"time": "Date", "percentage": "Success rate", "categories": "Category"},
        title="Success rate per category over time"
    )

    # show whole y-axis
    stats.update_layout(yaxis_range=[-5, 105])

    canvas.plotly_chart(stats)


def p_chart_label_distribution_per_model_in_category(history_df, canvas, category, label_column="label"):
    # remove timestamps from model ids (in old records)
    history_df["model"] = history_df["model"].apply(view_utils.clear_model_id)

    # take only records with selected category
    history_df = history_df[history_df["categories"].apply(
        lambda x:
            category in x if isinstance(x, list)
                          else False
    )]

    label_per_model_counts = (
        history_df.groupby(["model", label_column])
        .size()
        .reset_index(name="counts")
    )

    model_use_count = (
        label_per_model_counts
        .groupby("model")
        ["counts"]
        .transform("sum")
    )

    label_per_model_counts["percentage"] = (label_per_model_counts["counts"] / model_use_count) * 100

    # sort results (more green -> higher position)
    pivot_df = label_per_model_counts.pivot(index="model", columns=label_column, values="percentage").fillna(0)
    if "🟢" in pivot_df.columns:
        sorted_models = pivot_df.sort_values(by="🟢", ascending=False).index.tolist()
    else:
        sorted_models = pivot_df.index.tolist()

    fig = px.bar(
        data_frame=label_per_model_counts,
        x="percentage",
        y="model",
        color=label_column,
        color_discrete_map=label_colors,
        # text=label_column,
        # title="ASR per model",
        labels={"percentage": "ASR (percentage)"},
        orientation="h",
        category_orders={"model": sorted_models},
    )

    fig.update_layout(
        template="simple_white",
        font=dict(family="Helvetica", size=12),
        showlegend=False,
        margin=dict(l=10, r=20, t=30, b=80),
    )

    fig.update_xaxes(
        automargin=True,
        title_standoff=15,
    )

    # chart_filename = f"figures/chart_asr_cat_{"llama" if label_column.endswith("2") else "gemma"}.pdf"
    # if not os.path.exists(chart_filename):
    #     fig.write_image(chart_filename)


    canvas.plotly_chart(fig, key=f"p_chart_label_distribution_per_model_in_category_{label_column}")


### Presets

def p_chart_label_distribution_per_preset(history_df, canvas, label_column="label"):
    # filter out all entries without a preset
    history_df = history_df.loc[(history_df["preset"].notna()) & (history_df["preset"] != "")]

    history_df["preset_label"] = history_df["preset"].apply(lambda p_id: f"#{int(p_id)}")

    label_per_preset_counts = (
        history_df
        .groupby(["preset_label", label_column])
        .size()
        .reset_index(name="counts")
    )

    preset_use_count = (
        label_per_preset_counts
        .groupby("preset_label")
        ["counts"]
        .transform("sum")
    )

    label_per_preset_counts["percentage"] = (label_per_preset_counts["counts"] / preset_use_count) * 100

    # sort results (more green -> higher position)
    pivot_df = label_per_preset_counts.pivot(index="preset_label", columns=label_column, values="percentage").fillna(0)
    if "🟢" in pivot_df.columns:
        sorted_presets = pivot_df.sort_values(by="🟢", ascending=False).index.tolist()
    else:
        sorted_presets = pivot_df.index.tolist()

    stats = px.bar(
        label_per_preset_counts,
        x="percentage",
        y="preset_label",
        color=label_column,
        color_discrete_map=label_colors,
        text=label_column,
        title="Label distribution per preset",
        labels={"preset_label": "Preset", "percentage": "ASR (percentage)"},
        orientation="h",
        category_orders={"preset_label": sorted_presets},
    )

    stats.update_yaxes(type='category')
    canvas.plotly_chart(stats)


def p_chart_date_preset_success_over_time(history_df, canvas, label_column="label"):
    # filter out all entries without a preset
    history_df = history_df.loc[(history_df["preset"].notna()) & (history_df["preset"] != "")]

    # convert `time` values to datetime type
    history_df["time"] = pd.to_datetime(history_df["time"]).dt.date

    # change preset label formatting
    history_df["preset_label"] = history_df["preset"].apply(lambda p_id: f"#{int(p_id)}")

    daily_df = (
        history_df.groupby(["preset_label", "time"])
        .agg(
            daily_use=("id", "count"),
            daily_success=(label_column, lambda x: (x == "🟢").sum()),
        )
        .reset_index()
        .sort_values("time")
    )

    daily_df["cum_use_count"] = daily_df.groupby("preset_label")["daily_use"].cumsum()
    daily_df["cum_success_count"] = daily_df.groupby("preset_label")["daily_success"].cumsum()

    daily_df["percentage"] = (daily_df["cum_success_count"] / daily_df["cum_use_count"]) * 100
    daily_df["percentage"] = daily_df["percentage"].fillna(0)

    # get a sorted preset label order
    sorted_preset_labels = (
        daily_df["preset_label"]
        .drop_duplicates()
        .reset_index(drop=True)
        .sort_values(
            key=lambda x: x.str.replace("#", "").astype(int),
        )
        .tolist()
    )

    stats = px.line(
        daily_df,
        x="time",
        y="percentage",
        color="preset_label",
        markers=True,
        labels={"time": "Date", "percentage": "Success rate", "preset_label": "Preset"},
        title="Success rate per preset over time",
        category_orders={"preset_label": sorted_preset_labels},
    )

    # show whole y-axis
    stats.update_layout(yaxis_range=[-5, 105])

    canvas.plotly_chart(stats)


### Models

def parse_model_ids(i: str):
    i = i.replace("qwen3-next-80b-a3b-instruct", "Qwen3 (80B)")
    i = i.replace("hermes-4-70b", "Hermes 4 (70B)")
    i = i.replace("llama-3.3-70b-instruct", "Llama 3.3 (70B)")
    i = i.replace("llama-3.2-3b-instruct", "Llama 3.2 (3B)")
    i = i.replace("gemma-4-31b-it", "Gemma 4 (31B)")
    i = i.replace("gpt-oss-120b", "gpt-oss-120b")
    i = i.replace("gpt-oss-20b", "gpt-oss-20b")
    return i[i.find("/") + 1:]


def p_chart_label_distribution_per_model(history_df, canvas, label_column="label"):
    # remove timestamps from model ids (in old records)
    history_df["model"] = history_df["model"].apply(view_utils.clear_model_id).apply(parse_model_ids)

    label_per_model_counts = (
        history_df.groupby(["model", label_column])
        .size()
        .reset_index(name="counts")
    )

    model_use_count = (
        label_per_model_counts
        .groupby("model")
        ["counts"]
        .transform("sum")
    )

    label_per_model_counts["percentage"] = (label_per_model_counts["counts"] / model_use_count) * 100

    # sort results (more green -> higher position)
    pivot_df = label_per_model_counts.pivot(index="model", columns=label_column, values="percentage").fillna(0)
    if "🟢" in pivot_df.columns:
        sorted_models = pivot_df.sort_values(by="🟢", ascending=False).index.tolist()
    else:
        sorted_models = pivot_df.index.tolist()

    fig = px.bar(
        data_frame=label_per_model_counts,
        x="percentage",
        y="model",
        color=label_column,
        color_discrete_map=label_colors,
        # text=label_column,
        # title="ASR per model",
        labels={"percentage": "ASR (percentage)"},
        orientation="h",
        category_orders={"model": sorted_models},
    )

    # export_chart(fig, f"chart_asr_models_{"llama" if label_column.endswith("2") else "gemma"}.pdf", height=300)

    canvas.plotly_chart(fig, key=f"p_chart_label_distribution_per_model_{label_column}")


def p_chart_label_distribution_per_category_for_model(history_df, canvas, model, label_column="label"):
    # take only records with selected model
    history_df = history_df[history_df["model"] == model]

    label_per_category_counts = (
        history_df.explode("categories")
        .groupby(["categories", label_column])
        .size()
        .reset_index(name="counts")
    )

    category_use_count = (
        label_per_category_counts
        .groupby("categories")
        ["counts"]
        .transform("sum")
    )

    label_per_category_counts["percentage"] = (label_per_category_counts["counts"] / category_use_count) * 100

    # sort results (more green -> higher position)
    pivot_df = label_per_category_counts.pivot(index="categories", columns=label_column, values="percentage").fillna(0)
    if "🟢" in pivot_df.columns:
        sorted_categories = pivot_df.sort_values(by="🟢", ascending=False).index.tolist()
    else:
        sorted_categories = pivot_df.index.tolist()

    canvas.plotly_chart(px.bar(
        data_frame=label_per_category_counts,
        x="percentage",
        y="categories",
        color=label_column,
        color_discrete_map=label_colors,
        text=label_column,
        # title="Model ASR per Category",
        labels={"percentage": "ASR (percentage)"},
        orientation="h",
        category_orders={"categories": sorted_categories},
    ), key=f"p_chart_label_distribution_per_category_for_model_{label_column}")


def p_heatmap_per_category(history_df, canvas):
    history_df = history_df.explode('categories')
    history_df['categories'] = history_df['categories'].astype(str)
    history_df["model"] = history_df["model"].apply(view_utils.clear_model_id).apply(parse_model_ids)

    # 1. Przygotowanie danych: Obliczamy % ASR dla każdego przecięcia Model x Kategoria
    # Zmień 'judge_label' na nazwę kolumny, w której trzymasz oceny Gemmy
    # Zmień 'Success' na dokładny string, który oznacza u Ciebie sukces (np. 'success')
    pivot_df = history_df.groupby(['model', 'categories'])['judge_label'].apply(
        lambda x: (x == '🟢').sum() / len(x) * 100
    ).reset_index(name='ASR')

    # 2. Tworzymy macierz (Tabelę przestawną)
    heatmap_data = pivot_df.pivot(index='model', columns='categories', values='ASR')

    # Opcjonalnie: możemy posortować modele od najbardziej podatnego do najmniej podatnego
    heatmap_data['Mean'] = heatmap_data.mean(axis=1)
    heatmap_data = heatmap_data.sort_values('Mean', ascending=False).drop(columns=['Mean'])

    # 3. Rysowanie akademickiej Heatmapy
    fig = px.imshow(
        heatmap_data,
        text_auto=".1f",  # Wyświetla liczby z 1 miejscem po przecinku (np. 85.4)
        aspect="auto",  # Automatycznie dopasowuje proporcje prostokątów
        color_continuous_scale="Reds",  # Kolor: od białego/jasnego (0% ASR) do ciemnoczerwonego (100% ASR)
        range_color=[0, 90],
        labels=dict(x="Attack Category", y="Target Model", color="ASR<br>(percentage)")
    )

    # 4. Akademicki szlif
    fig.update_layout(
        template="simple_white",
        font=dict(family="Arial", size=12),
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis_title=None,  # Ukrywamy słowo "Attack Category", bo nazwy kategorii mówią same za siebie
        yaxis_title=None  # Ukrywamy słowo "Target Model", z tego samego powodu
    )

    # Upewniamy się, że osie są ładnie wyeksponowane
    fig.update_xaxes(side="bottom", tickangle=-45)  # Pochylamy nazwy kategorii, żeby na siebie nie wchodziły

    fig.update_traces(textfont_size=18)

    # export_chart(fig, f"heatmap_models_{category_subset_name.lower()}.pdf", height=700, font_size=20)

    # Podgląd w Streamlit (jeśli używasz)
    canvas.plotly_chart(fig)


### Length

def p_chart_label_distribution_per_length(history_df, canvas, label_column="label"):
    history_df["total_length"] = (
            history_df["prompt"].str.len() +
            history_df["system_prompt"].str.len()
    )

    group_borders = [0, 500, 2000, 5000, float("inf")]
    group_names = ["Short (<500)", "Medium (500-2000)", "Long (2000-5000)", "Very long (>5000)"]

    history_df["length_group"] = pd.cut(
        history_df["total_length"],
        bins=group_borders,
        labels=group_names,
    )

    history_df = (
        history_df.groupby(["length_group", label_column], observed=False)
        .size()
        .reset_index(name="prompt_count")
    )
    history_df["prompt_count"] = history_df["prompt_count"].astype(int)

    prompt_per_length_count = (
        history_df
        .groupby("length_group")
        ["prompt_count"]
        .transform("sum")
    )

    history_df["percentage"] = (history_df["prompt_count"] / prompt_per_length_count) * 100

    # sort results (more green -> higher position)
    pivot_df = history_df.pivot(index="length_group", columns=label_column, values="percentage").fillna(0)
    if "🟢" in pivot_df.columns:
        sorted_groups = pivot_df.sort_values(by="🟢", ascending=False).index.tolist()
    else:
        sorted_groups = pivot_df.index.tolist()

    stats = px.bar(
        history_df,
        y="length_group",
        x="percentage",
        color=label_column,
        color_discrete_map=label_colors,
        # title="Labels per total prompt length",
        labels={"length_group": "Length (characters)", "percentage": "ASR (percentage)"},
        category_orders={"length_group": sorted_groups},
    )

    canvas.plotly_chart(stats)


def p_chart_date_length_success_over_time(history_df, canvas, label_column="label"):
    # extract only the date
    history_df["time"] = pd.to_datetime(history_df["time"]).dt.date

    history_df["total_length"] = (
            history_df["prompt"].str.len() +
            history_df["system_prompt"].str.len()
    )

    group_borders = [0, 500, 2000, 5000, float("inf")]
    group_names = ["Short (<500)", "Medium (500-2000)", "Long (2000-5000)", "Very long (>5000)"]

    history_df["length_group"] = pd.cut(
        history_df["total_length"],
        bins=group_borders,
        labels=group_names,
    )

    daily_df = (
        history_df.groupby(["length_group", "time"])
        .agg(
            daily_use=("id", "count"),
            daily_success=(label_column, lambda x: (x == "🟢").sum()),
        )
        .reset_index()
        .sort_values("time")
    )

    daily_df["cum_use_count"] = daily_df.groupby("length_group")["daily_use"].cumsum()
    daily_df["cum_success_count"] = daily_df.groupby("length_group")["daily_success"].cumsum()

    daily_df["percentage"] = (daily_df["cum_success_count"] / daily_df["cum_use_count"]) * 100
    daily_df["percentage"] = daily_df["percentage"].fillna(0)

    stats = px.line(
        daily_df,
        x="time",
        y="percentage",
        color="length_group",
        markers=True,
        labels={"time": "Date", "percentage": "Success rate", "length_group": "Length"},
        title="Success rate per category over time"
    )

    # show whole y-axis
    stats.update_layout(yaxis_range=[-5, 105])

    canvas.plotly_chart(stats)


###### Count

def c_chart_labels_per_category(history_df, canvas, label_column="label"):
    history_df = (
        history_df.explode("categories")
        .groupby(["categories", label_column])
        .size()
        .reset_index(name="count")
    )

    # sort results (more green -> higher position)
    sorted_categories = (
        history_df.groupby("categories")["count"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )

    stats = px.bar(
        data_frame=history_df,
        x="count",
        y="categories",
        color=label_column,
        color_discrete_map=label_colors,
        labels={"categories": "Category", "count": "Count", label_column: "Labels"},
        title="Labels per category",
        category_orders={"categories": sorted_categories},
        orientation="h",
    )

    canvas.plotly_chart(stats)


def c_chart_labels_per_length(history_df, canvas, label_column="label"):
    history_df["total_length"] = (
            history_df["prompt"].str.len() +
            history_df["system_prompt"].str.len()
    )

    group_borders = [0, 500, 2000, 5000, float("inf")]
    group_names = ["Short (<500)", "Medium (500-2000)", "Long (2000-5000)", "Very long (>5000)"]

    history_df["length_group"] = pd.cut(
        history_df["total_length"],
        bins=group_borders,
        labels=group_names,
    )

    history_df = (
        history_df.groupby(["length_group", label_column], observed=False)
        .size()
        .reset_index(name="prompt_count")
    )

    stats = px.bar(
        history_df,
        x="length_group",
        y="prompt_count",
        color=label_column,
        color_discrete_map=label_colors,
        title="Labels per total prompt length",
        labels={"length_bucket": "Length (characters)", "count": "Count"},
    )

    canvas.plotly_chart(stats)


def c_chart_category_use_count(history_df, canvas):
    history_df = (
        history_df.explode("categories")
        .groupby("categories")
        .agg(
            total_category_uses=("id", "count")
        )
        .reset_index()
    )

    stats = px.bar(
        data_frame=history_df,
        x="categories",
        y="total_category_uses",
        title="Category use count",
        labels={"categories": "Category", "total_category_uses": "Count"},
    )

    canvas.plotly_chart(stats)



history_table = view_utils.get_all_history_entries(fill_null=True)

if not history_table.empty:
    tab_count.header("Count-based statistics")
    tab_percentage.header("Percentage-based statistics")


    # percentage-based stats
    p_ai_judge_success_rate(history_table, tab_percentage)
    # p_ai_judge_match_rate(history_table, tab_percentage)

    with tab_percentage.expander("Categories", expanded=True) as expander:
        expander.subheader("Category statistics")

        if not history_table["categories"].explode().dropna().unique().tolist():
            st.info("No categories were used in any prompt!")

        else:
            chart_category = expander.selectbox(
                "Chart category",
                options=view_utils.get_all_categories(),
                key="categories",
                index=None,
            )

            if chart_category:
                history_with_chart_category = history_table[history_table["categories"].apply(
                    lambda x: chart_category in x if isinstance(x, list) else False
                )]
                p_chart_label_distribution_per_model(history_with_chart_category, expander, "judge_label")

            else:
                p_chart_label_distribution_per_category(history_table, expander, "judge_label")

            expander.divider()


        # p_chart_date_category_success_over_time(history_table, expander)
        # expander.divider()




    with tab_percentage.expander("Models", expanded=True) as expander:
        expander.subheader("Model statistics")

        only_free_models = st.segmented_control(
            "Model type",
            options=["All", "Free"],
            default="All",
        )

        model_ids = view_utils.get_model_ids(only_free_models == "Free")

        chart_model = expander.selectbox(
            "Chart model",
            options=model_ids,
            key="model",
            index=None,
        )

        if chart_model:
            p_chart_label_distribution_per_category_for_model(history_table, expander, chart_model, "judge_label")

        else:
            p_chart_label_distribution_per_model(history_table, expander, "judge_label")

        expander.divider()

        st.subheader("Heatmap for categories:")
        if not history_table["categories"].explode().dropna().unique().tolist():
            st.info("No categories were used in any prompt!")
        else:
            p_heatmap_per_category(history_table, expander)

        expander.divider()


    with tab_percentage.expander("Presets", expanded=True) as expander:
        expander.subheader("Preset statistics")
        p_chart_label_distribution_per_preset(history_table, expander, "judge_label")
        expander.divider()
        widgets.preset_table_preview()
        expander.divider()
        # p_chart_date_preset_success_over_time(history_table, expander)
        # expander.divider()

        if expander.button("See preset details"):
            st.switch_page("pages/presets.py")


    with tab_percentage.expander("Total prompt length", expanded=True) as expander:
        expander.subheader("Total prompt length statistics")
        p_chart_label_distribution_per_length(history_table, expander, "judge_label")
        expander.divider()
        # p_chart_date_length_success_over_time(history_table, expander)
        # expander.divider()


    # count-based stats
    if history_table["categories"].explode().dropna().unique().tolist():
        c_chart_labels_per_category(history_table, tab_count)
        tab_count.divider()
        c_chart_category_use_count(history_table, tab_count)
        tab_count.divider()

    c_chart_labels_per_length(history_table, tab_count)
    tab_count.divider()

else:
    st.info("No data yet!")