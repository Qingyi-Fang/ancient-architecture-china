"""Streamlit 主入口：中国古建筑·数字图谱。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.charts import (
    classify_building_category,
    create_batch_pie_chart,
    create_category_bar_chart,
    create_era_bar_chart,
    create_province_bar_chart,
)
from src.data_loader import (
    DEFAULT_ELIGIBLE_OUTPUT_PATH,
    export_filtered_data,
    filter_eligible_buildings,
    load_excel_data,
)
from src.map_viz import display_map_in_streamlit


# 页面基础配置
st.set_page_config(
    page_title="中国古建筑·数字图谱",
    page_icon="🏛️",
    layout="wide",
)


@st.cache_data
def load_app_data() -> pd.DataFrame:
    """加载应用数据：优先读取已处理 CSV，不存在则从 Excel 重建。"""
    processed_path = Path(DEFAULT_ELIGIBLE_OUTPUT_PATH)
    if processed_path.exists():
        return pd.read_csv(processed_path, encoding="utf-8-sig")

    raw_df = load_excel_data()
    eligible_df = filter_eligible_buildings(raw_df)
    export_filtered_data(eligible_df, output_path=processed_path)
    return eligible_df


def get_main_era(df: pd.DataFrame) -> str:
    """计算主要朝代（出现次数最多）。"""
    era_col = "时代（中文）"
    if era_col not in df.columns or df.empty:
        return "-"

    era_keywords = ["唐", "宋", "元", "明", "清"]
    counts: dict[str, int] = {}
    era_series = df[era_col].fillna("").astype(str)
    for era in era_keywords:
        counts[era] = int(era_series.str.contains(era, regex=False, na=False).sum())

    major_era = max(counts, key=counts.get) if counts else "-"
    return major_era if counts.get(major_era, 0) > 0 else "-"


def get_main_category(df: pd.DataFrame) -> str:
    """计算主要建筑类别（出现次数最多）。"""
    name_col = "单位名称（中文）"
    if name_col not in df.columns or df.empty:
        return "-"

    category_series = df[name_col].apply(classify_building_category)
    if category_series.empty:
        return "-"
    return str(category_series.value_counts().idxmax())


def build_sidebar(df: pd.DataFrame) -> tuple[str, str]:
    """构建侧边栏并返回视图和省份筛选值。"""
    st.sidebar.title("🏛️ 中国古建筑·数字图谱")
    view = st.sidebar.radio(
        "选择视图",
        ["📊 总览仪表板", "🗺️ 地图探索"],
        index=0,
    )

    province_col = "省级政区名称（中文）"
    if province_col in df.columns:
        provinces = sorted(
            [
                p
                for p in df[province_col].fillna("").astype(str).str.strip().unique().tolist()
                if p
            ]
        )
    else:
        provinces = []

    selected_province = st.sidebar.selectbox(
        "省份筛选",
        ["全部"] + provinces,
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("数据来源：全国重点文物保护单位公开数据")
    st.sidebar.caption("赛事信息：古建筑保护与数字化设计相关赛题")
    return view, selected_province


def apply_province_filter(df: pd.DataFrame, selected_province: str) -> pd.DataFrame:
    """按省份联动筛选数据。"""
    province_col = "省级政区名称（中文）"
    if selected_province == "全部" or province_col not in df.columns:
        return df.copy()
    return df[df[province_col] == selected_province].copy()


def render_dashboard(filtered_df: pd.DataFrame) -> None:
    """渲染总览仪表板视图。"""
    st.title("中国古建筑·数字图谱")
    st.caption("以数据可视化方式呈现古建筑分布、年代与类别特征。")

    # KPI 卡片
    total_count = int(len(filtered_df))
    province_count = int(
        filtered_df["省级政区名称（中文）"].replace("", pd.NA).nunique(dropna=True)
        if "省级政区名称（中文）" in filtered_df.columns
        else 0
    )
    major_era = get_main_era(filtered_df)
    major_category = get_main_category(filtered_df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("古建筑总数", f"{total_count:,}")
    c2.metric("覆盖省份", f"{province_count}")
    c3.metric("主要朝代", major_era)
    c4.metric("主要类别", major_category)

    # 第一行：省份横向柱状图
    st.plotly_chart(create_province_bar_chart(filtered_df), use_container_width=True)

    # 第二行：朝代柱状图 + 批次饼图
    left, right = st.columns(2)
    with left:
        st.plotly_chart(create_era_bar_chart(filtered_df), use_container_width=True)
    with right:
        st.plotly_chart(create_batch_pie_chart(filtered_df), use_container_width=True)

    # 第三行：建筑类别柱状图
    st.plotly_chart(create_category_bar_chart(filtered_df), use_container_width=True)

    # 第四行：数据摘要表格
    st.subheader("数据摘要（前20条）")
    st.dataframe(filtered_df.head(20), use_container_width=True, hide_index=True)


def render_map_view(filtered_df: pd.DataFrame, selected_province: str) -> None:
    """渲染地图探索视图。"""
    st.title("🗺️ 地图探索")
    st.caption("在地图中查看古建筑空间分布，可结合省份筛选进行探索。")

    st.info(f"当前筛选古建筑数量：{len(filtered_df)} 条")

    map_province = None if selected_province == "全部" else selected_province
    display_map_in_streamlit(filtered_df, selected_province=map_province)

    st.subheader("古建筑列表")
    show_cols = [col for col in ["单位名称（中文）", "时代（中文）", "地址（中文）", "批次（中文）"] if col in filtered_df.columns]
    st.dataframe(filtered_df.loc[:, show_cols], use_container_width=True, hide_index=True)


def main() -> None:
    """应用主函数。"""
    df = load_app_data()
    view, selected_province = build_sidebar(df)
    filtered_df = apply_province_filter(df, selected_province)

    if view == "📊 总览仪表板":
        render_dashboard(filtered_df)
    else:
        render_map_view(filtered_df, selected_province)


if __name__ == "__main__":
    main()
