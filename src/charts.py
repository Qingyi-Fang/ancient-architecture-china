"""可视化图表模块（Plotly）。"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 古建筑主题配色（暖棕米白）
MAIN_COLOR = "#8B4513"
ACCENT_1 = "#A0522D"
ACCENT_2 = "#D2691E"
ACCENT_3 = "#CD853F"
ACCENT_4 = "#DEB887"
BG_COLOR = "#F5F3F0"

PIE_COLORS = [
    "#8B4513",
    "#A0522D",
    "#CD853F",
    "#D2691E",
    "#DEB887",
    "#C4A882",
    "#B8956A",
    "#A08060",
]


def _apply_common_layout(fig: go.Figure, height: int) -> go.Figure:
    """统一图表样式：中文友好、透明背景、简洁边距。"""
    fig.update_layout(
        height=height,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#3D2B1F"),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def classify_building_category(name: str) -> str:
    """根据建筑名称推断类别。"""
    if pd.isna(name):
        return "其他"

    text = str(name).strip()
    if not text:
        return "其他"

    # 按业务优先级判断类别
    if any(keyword in text for keyword in ("桥", "梁")):
        return "桥梁"
    if any(keyword in text for keyword in ("宅", "院", "楼", "居", "庄", "第", "屋")):
        return "民居"
    if any(keyword in text for keyword in ("衙", "署", "官", "司")):
        return "官府"
    if any(keyword in text for keyword in ("宫", "殿")):
        return "皇宫"
    if any(keyword in text for keyword in ("文庙", "书院", "会馆", "祠堂")):
        return "公共建筑"
    return "其他"


def create_province_bar_chart(df: pd.DataFrame) -> go.Figure:
    """横向柱状图：各省份古建筑数量（前15）。"""
    col = "省级政区名称（中文）"
    province_counts = (
        df[col].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().value_counts().head(15)
        if col in df.columns
        else pd.Series(dtype=int)
    )
    plot_df = province_counts.sort_values(ascending=True).rename_axis("省份").reset_index(name="数量")

    fig = px.bar(
        plot_df,
        x="数量",
        y="省份",
        orientation="h",
        title="各省份古建筑数量（前15）",
        color_discrete_sequence=[MAIN_COLOR],
    )
    fig.update_traces(texttemplate="%{x}", textposition="outside")
    fig.update_xaxes(title_text="古建筑数量")
    fig.update_yaxes(title_text="省份")
    return _apply_common_layout(fig, height=450)


def create_era_bar_chart(df: pd.DataFrame) -> go.Figure:
    """柱状图：主要朝代（唐、宋、元、明、清）古建筑数量。"""
    era_col = "时代（中文）"
    eras = ["唐", "宋", "元", "明", "清"]
    era_counts: dict[str, int] = {era: 0 for era in eras}

    if era_col in df.columns:
        era_series = df[era_col].fillna("").astype(str)
        for era in eras:
            era_counts[era] = int(era_series.str.contains(era, regex=False, na=False).sum())

    plot_df = pd.DataFrame({"朝代": eras, "数量": [era_counts[era] for era in eras]})
    fig = px.bar(
        plot_df,
        x="朝代",
        y="数量",
        title="主要朝代古建筑数量",
        color_discrete_sequence=[ACCENT_1],
    )
    fig.update_traces(texttemplate="%{y}", textposition="outside")
    fig.update_xaxes(title_text="朝代")
    fig.update_yaxes(title_text="古建筑数量")
    return _apply_common_layout(fig, height=350)


def create_batch_pie_chart(df: pd.DataFrame) -> go.Figure:
    """饼图：各批次古建筑占比。"""
    col = "批次（中文）"
    batch_counts = (
        df[col].fillna("").astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if col in df.columns
        else pd.Series(dtype=int)
    )
    plot_df = batch_counts.rename_axis("批次").reset_index(name="数量")

    fig = px.pie(
        plot_df,
        names="批次",
        values="数量",
        title="各批次古建筑占比",
        color_discrete_sequence=PIE_COLORS,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _apply_common_layout(fig, height=350)


def create_category_bar_chart(df: pd.DataFrame) -> go.Figure:
    """柱状图：建筑类别（民居/官府/皇宫/桥梁/公共/其他）数量。"""
    name_col = "单位名称（中文）"
    categories = ["民居", "官府", "皇宫", "桥梁", "公共建筑", "其他"]

    if name_col in df.columns:
        category_series = df[name_col].apply(classify_building_category)
        category_counts = category_series.value_counts()
    else:
        category_counts = pd.Series(dtype=int)

    plot_df = pd.DataFrame({
        "类别": categories,
        "数量": [int(category_counts.get(cat, 0)) for cat in categories],
    })

    fig = px.bar(
        plot_df,
        x="类别",
        y="数量",
        title="建筑类别数量分布",
        color_discrete_sequence=[ACCENT_3],
    )
    fig.update_traces(texttemplate="%{y}", textposition="outside")
    fig.update_xaxes(title_text="建筑类别")
    fig.update_yaxes(title_text="数量")
    return _apply_common_layout(fig, height=350)
