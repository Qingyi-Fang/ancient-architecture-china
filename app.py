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
    initial_sidebar_state="expanded",
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


def reset_province_filter() -> None:
    """重置省份筛选到默认值。"""
    st.session_state["province_filter"] = "全部"


def build_sidebar(df: pd.DataFrame) -> tuple[str, str, str]:
    """构建侧边栏并返回视图、省份和搜索关键词。"""
    # 注入高级新中式极简样式，仅作用于侧边栏与控件
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;600;700&display=swap');

        /* 主内容区紧凑化：减少首屏空白，提升展示完整度 */
        [data-testid="stMainBlockContainer"] {
            padding-top: 1rem !important;
            padding-bottom: 0.6rem !important;
        }

        /* 隐藏 Streamlit 顶部工具栏（Deploy 与右上菜单） */
        header[data-testid="stHeader"] {
            display: none !important;
            height: 0 !important;
        }

        [data-testid="stAppViewContainer"] .main {
            padding-bottom: 0 !important;
            margin-top: 0 !important;
        }

        footer {
            visibility: hidden;
            height: 0;
        }

        section[data-testid="stSidebar"] {
            background-color: #7A3D17;
            min-width: 280px;
            max-width: 280px;
            overflow-y: hidden !important;
            padding-top: 0 !important;
            margin-top: 0 !important;
            --primary-color: #5F7F72 !important;
        }

        /* 清除侧边栏顶部保留头部占位（造成标题上方空白） */
        section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* 侧边栏固定显示：隐藏收缩按钮并禁用收缩位移 */
        [data-testid="stSidebarCollapseButton"] {
            display: none !important;
        }

        section[data-testid="stSidebar"][aria-expanded="false"] {
            margin-left: 0 !important;
        }

        section[data-testid="stSidebar"] > div {
            padding: 0.22rem 1rem 1.25rem 1rem;
            height: 100vh;
            overflow-y: hidden !important;
            display: flex;
            flex-direction: column;
            gap: 0;
            margin-top: 0 !important;
        }

        section[data-testid="stSidebar"] .stSidebarContent,
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-top: 0 !important;
            margin-top: 0 !important;
        }

        section[data-testid="stSidebar"] * {
            font-family: "Noto Serif SC", "SimSun", serif !important;
            color: #F5F0E6;
        }

        /* 修复 Streamlit 内置图标字体被覆盖导致的乱码文本（如 keyboard_double_*） */
        section[data-testid="stSidebar"] .material-symbols-rounded,
        section[data-testid="stSidebar"] .material-icons,
        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] span {
            font-family: "Material Symbols Rounded", "Material Icons" !important;
            font-weight: normal !important;
            font-style: normal !important;
        }

        section[data-testid="stSidebar"] .sidebar-title {
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 2rem;
            font-weight: 600;
            text-align: center;
            letter-spacing: 0.02em;
            line-height: 1.42;
            margin: -0.08rem 0 0.55rem 0;
            color: #F5F0E6;
            white-space: normal;
            word-break: keep-all;
        }

        section[data-testid="stSidebar"] .sidebar-module-title {
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 1.08rem;
            font-weight: 700;
            text-align: center;
            margin: 0.8rem 0 0.55rem 0;
            color: #F5F0E6;
        }

        section[data-testid="stSidebar"] .stRadio {
            border: 1px solid rgba(232, 224, 213, 0.62);
            border-radius: 18px;
            padding: 3.25rem 0.78rem 1rem 0.78rem;
            margin: 0.4rem 0 1rem 0;
            background: rgba(250, 240, 230, 0.07);
            position: relative;
        }

        section[data-testid="stSidebar"] .stRadio::before {
            content: "选择视图";
            position: absolute;
            top: 0.76rem;
            left: 50%;
            transform: translateX(-50%);
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 1.12rem;
            font-weight: 700;
            color: #F5F0E6;
            white-space: nowrap;
        }

        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] input {
            background-color: #FAF0E6 !important;
            border: 1px solid rgba(226, 214, 200, 0.92) !important;
            border-radius: 8px !important;
            color: #4C2A17 !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="select"] * {
            color: #4C2A17 !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
        section[data-testid="stSidebar"] input:hover {
            border-color: rgba(232, 224, 213, 1) !important;
        }

        section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
        section[data-testid="stSidebar"] input:focus {
            border-color: #5F7F72 !important;
            outline: none !important;
            box-shadow: 0 0 0 1px rgba(95, 127, 114, 0.45) inset !important;
        }

        div[data-baseweb="popover"] * {
            background-color: #FFFFFF !important;
            color: #4C2A17 !important;
        }

        /* 下拉弹层输入框：去英文占位突兀感 + 统一光标/聚焦色 */
        div[data-baseweb="popover"] input::placeholder {
            color: transparent !important;
        }

        div[data-baseweb="popover"] input {
            caret-color: #5F7F72 !important;
            border-color: rgba(226, 214, 200, 0.92) !important;
            box-shadow: none !important;
        }

        div[data-baseweb="popover"] input:focus {
            border-color: #5F7F72 !important;
            box-shadow: 0 0 0 1px rgba(95, 127, 114, 0.45) !important;
        }

        section[data-testid="stSidebar"] [role="option"]:hover {
            background-color: #F5D6D9 !important;
            color: #4C2A17 !important;
        }

        section[data-testid="stSidebar"] input::placeholder {
            color: #B0A294 !important;
            font-family: "Noto Serif SC", "SimSun", serif !important;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label {
            border: 1px solid rgba(232, 224, 213, 0.8);
            border-radius: 18px;
            padding: 0.46rem 0.48rem;
            margin: 0 !important;
            background: rgba(250, 240, 230, 0.05);
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            width: 100%;
            transition: all 0.15s ease-in-out;
            min-height: 68px;
            box-shadow: inset 0 0 0 1px rgba(245, 240, 230, 0.08);
            box-sizing: border-box;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.56rem;
            align-items: stretch;
            width: 100%;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label p {
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 0.96rem;
            letter-spacing: 0.02em;
            white-space: nowrap;
            line-height: 1.2;
            font-weight: 600;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: rgba(250, 240, 230, 0.1);
            border-color: rgba(245, 240, 230, 0.95);
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: linear-gradient(
                180deg,
                rgba(250, 240, 230, 0.24) 0%,
                rgba(250, 240, 230, 0.14) 100%
            );
            border-color: #F5F0E6;
            box-shadow: inset 0 0 0 1px rgba(245, 240, 230, 0.35);
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
            color: #F5F0E6 !important;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        }

        /* 隐藏单选控件自身可视圆点，仅保留按钮选中样式 */
        section[data-testid="stSidebar"] [role="radiogroup"] label input[type="radio"] {
            display: none !important;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child,
        section[data-testid="stSidebar"] [role="radiogroup"] label [data-baseweb="radio"] {
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* 清理 radio 的隐藏 label，避免出现顶部重叠小字 */
        section[data-testid="stSidebar"] .stRadio > label {
            display: none !important;
        }

        section[data-testid="stSidebar"] .sidebar-sep {
            display: none;
        }

        /* 省份筛选/搜索功能：稳定简洁的模块标题样式 */
        section[data-testid="stSidebar"] .sidebar-field-title {
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 1.12rem;
            font-weight: 700;
            text-align: center;
            color: #F5F0E6;
            margin: 0.3rem 0 0.55rem 0;
            letter-spacing: 0.02em;
        }

        /* 省份筛选/搜索控件：更克制的比赛风输入区 */
        section[data-testid="stSidebar"] .stSelectbox,
        section[data-testid="stSidebar"] .stTextInput {
            margin-bottom: 0.72rem;
            padding: 0.42rem 0.46rem 0.22rem 0.46rem;
            border: 1px solid rgba(232, 224, 213, 0.4);
            border-radius: 14px;
            background: rgba(250, 240, 230, 0.03);
        }

        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] .stTextInput input {
            border: 1px solid rgba(226, 214, 200, 0.92) !important;
            border-radius: 10px !important;
            min-height: 42px !important;
            font-size: 0.95rem !important;
            color: #4C2A17 !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div {
            background: rgba(250, 240, 230, 0.78) !important;
        }

        section[data-testid="stSidebar"] .stTextInput input {
            background: rgba(250, 240, 230, 0.76) !important;
        }

        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div:hover,
        section[data-testid="stSidebar"] .stTextInput input:hover {
            border-color: rgba(232, 224, 213, 1) !important;
        }

        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div:focus-within,
        section[data-testid="stSidebar"] .stTextInput input:focus {
            border-color: #5F7F72 !important;
            box-shadow: 0 0 0 1px rgba(95, 127, 114, 0.45) !important;
        }

        section[data-testid="stSidebar"] .stTextInput input {
            caret-color: #5F7F72 !important;
        }

        /* 搜索框最终覆盖：彻底去除红色边框残留 */
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div {
            border: 1px solid rgba(226, 214, 200, 0.92) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div:hover {
            border-color: rgba(232, 224, 213, 1) !important;
        }

        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div:focus-within {
            border-color: #5F7F72 !important;
            box-shadow: 0 0 0 1px rgba(95, 127, 114, 0.45) !important;
        }

        section[data-testid="stSidebar"] .stTextInput input:focus,
        section[data-testid="stSidebar"] .stTextInput input:focus-visible,
        section[data-testid="stSidebar"] .stSelectbox input:focus,
        section[data-testid="stSidebar"] .stSelectbox input:focus-visible {
            outline: none !important;
            border-color: #5F7F72 !important;
            box-shadow: none !important;
            caret-color: #5F7F72 !important;
        }

        section[data-testid="stSidebar"] .sidebar-footer {
            margin-top: auto;
            padding-top: 0.5rem;
            border-top: 1px solid #E8E0D5;
            font-size: 0.78rem;
            color: #F5F0E6;
            line-height: 1.5;
            text-align: center;
            font-weight: 300;
            background-color: #7A3D17;
            padding-bottom: 0.2rem;
            position: static;
        }

        section[data-testid="stSidebar"] .stTextInput,
        section[data-testid="stSidebar"] .stSelectbox,
        section[data-testid="stSidebar"] .stRadio {
            width: 100%;
        }

        /* 省份重置按钮：与下拉拼接成同一体 */
        section[data-testid="stSidebar"] .stButton > button {
            min-height: 42px !important;
            height: 42px !important;
            border-radius: 0 10px 10px 0 !important;
            border: 1px solid rgba(226, 214, 200, 0.92) !important;
            border-left: none !important;
            background: rgba(250, 240, 230, 0.78) !important;
            color: #6B4B35 !important;
            font-size: 0.95rem !important;
            padding: 0 !important;
            margin-left: -0.48rem !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            border-color: rgba(232, 224, 213, 1) !important;
            background: rgba(250, 240, 230, 0.84) !important;
        }

        section[data-testid="stSidebar"] .stButton > button:focus,
        section[data-testid="stSidebar"] .stButton > button:focus-visible {
            outline: none !important;
            box-shadow: 0 0 0 1px rgba(95, 127, 114, 0.45) !important;
            border-color: #5F7F72 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 模块一：项目主标题（纯文字）
    st.sidebar.markdown('<div class="sidebar-title">中国古建筑<br>数字图谱</div>', unsafe_allow_html=True)

    # 模块二：视图切换（卡片内标题样式）
    view = st.sidebar.radio(
        "选择视图",
        ["总览仪表板", "地图探索"],
        index=0,
        label_visibility="collapsed",
    )

    # 模块三：省份筛选（稳定布局，保留原有逻辑）
    st.sidebar.markdown('<hr class="sidebar-sep" />', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="sidebar-field-title">省份筛选</div>', unsafe_allow_html=True)

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

    # 省份筛选状态：初始化为“全部”
    if "province_filter" not in st.session_state:
        st.session_state["province_filter"] = "全部"

    # 省份筛选 + 右侧紧凑重置
    province_select_col, province_reset_col = st.sidebar.columns([9, 2], gap="small")
    with province_select_col:
        selected_province = st.selectbox(
            "省份筛选",
            ["全部"] + provinces,
            index=0,
            label_visibility="collapsed",
            key="province_filter",
        )
    with province_reset_col:
        st.markdown("<div style='height:3px'></div>", unsafe_allow_html=True)
        st.button("重置", use_container_width=True, on_click=reset_province_filter, help="重置省份")

    # 模块四：名称搜索（稳定布局 + 实时过滤）
    st.sidebar.markdown('<hr class="sidebar-sep" />', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="sidebar-field-title">搜索功能</div>', unsafe_allow_html=True)
    search_keyword = st.sidebar.text_input(
        "搜索功能",
        value="",
        placeholder="搜索古建筑名称",
        label_visibility="collapsed",
    )

    # 底部信息区（固定两行说明）
    st.sidebar.markdown(
        """
        <div class="sidebar-footer">
            数据来源:全国重点文物保护单位公开数据
        </div>
        """,
        unsafe_allow_html=True,
    )
    return view, selected_province, search_keyword


def apply_province_filter(df: pd.DataFrame, selected_province: str) -> pd.DataFrame:
    """按省份联动筛选数据。"""
    province_col = "省级政区名称（中文）"
    if selected_province == "全部" or province_col not in df.columns:
        return df.copy()
    return df[df[province_col] == selected_province].copy()


def apply_name_search_filter(df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    """按古建筑名称进行模糊搜索筛选。"""
    name_col = "单位名称（中文）"
    normalized_keyword = keyword.strip()
    if not normalized_keyword or name_col not in df.columns:
        return df.copy()

    matched = df[name_col].fillna("").astype(str).str.contains(normalized_keyword, regex=False, na=False)
    return df[matched].copy()


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
    st.title("地图探索")
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
    view, selected_province, search_keyword = build_sidebar(df)
    filtered_df = apply_province_filter(df, selected_province)
    filtered_df = apply_name_search_filter(filtered_df, search_keyword)

    if view == "总览仪表板":
        render_dashboard(filtered_df)
    else:
        render_map_view(filtered_df, selected_province)


if __name__ == "__main__":
    main()
