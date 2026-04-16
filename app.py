"""Streamlit 主入口：中国古建筑·数字图谱。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import requests

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

# 自定义CSS - 调整侧边栏宽度和主区域
st.markdown(
    """
    <style>
        /* 缩小侧边栏 */
        [data-testid="stSidebar"] {
            min-width: 200px !important;
            max-width: 200px !important;
        }
        
        /* 主内容区域最大化 */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        
        /* 减少页面默认边距 */
        .appview-container .main .block-container {
            padding-top: 1rem !important;
        }
        
        /* 隐藏Streamlit默认的菜单和footer */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
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


def get_era_label(era_text: str) -> str:
    """从时代文本中提取用于展示的朝代标签。"""
    if pd.isna(era_text):
        return "其他"
    text = str(era_text).strip()
    for era in ["唐", "宋", "元", "明", "清"]:
        if era in text:
            return era
    return text or "其他"


def calculate_building_score(row: pd.Series) -> float:
    """根据保护级别、年代、稀有性、历史价值计算综合评分。"""
    batch_text = str(row.get("批次（中文）", "")).strip()
    era_text = str(row.get("时代（中文）", "")).strip()
    name_text = str(row.get("单位名称（中文）", "")).strip()

    # 1. 保护级别（35%）
    protection_score = 60
    if any(keyword in batch_text for keyword in ["第一批", "第八批"]):
        protection_score = 100
    elif any(keyword in batch_text for keyword in ["第二批", "第七批"]):
        protection_score = 85
    elif any(keyword in batch_text for keyword in ["第三批", "第六批"]):
        protection_score = 70
    elif any(keyword in batch_text for keyword in ["第四批", "第五批"]):
        protection_score = 60

    # 2. 年代久远度（30%）
    era_score = 40
    if any(keyword in era_text for keyword in ["唐", "隋", "汉", "晋", "南北朝", "北朝", "南朝", "三国", "秦"]):
        era_score = 100
    elif "宋" in era_text:
        era_score = 85
    elif "元" in era_text:
        era_score = 70
    elif "明" in era_text:
        era_score = 55
    elif "清" in era_text:
        era_score = 40

    # 3. 建筑稀有性（20%）
    rarity_score = 50
    if any(keyword in name_text for keyword in ["宫", "殿", "桥", "梁"]):
        rarity_score = 100
    elif any(keyword in name_text for keyword in ["衙", "署", "府", "官"]):
        rarity_score = 85
    elif any(keyword in name_text for keyword in ["宅", "院", "楼", "居", "庄", "第"]):
        rarity_score = 70

    # 4. 历史价值（15%）
    historical_score = 100 if any(
        keyword in name_text for keyword in ["第一", "最早", "唯一", "标志性", "最大", "最古"]
    ) else 60

    total_score = (
        protection_score * 0.35
        + era_score * 0.30
        + rarity_score * 0.20
        + historical_score * 0.15
    )
    return round(float(total_score), 1)


def get_star_rating(score: float) -> str:
    """根据综合评分返回星级。"""
    if score >= 90:
        return "⭐⭐⭐⭐⭐"
    if score >= 75:
        return "⭐⭐⭐⭐"
    if score >= 60:
        return "⭐⭐⭐"
    if score >= 45:
        return "⭐⭐"
    return "⭐"


@st.cache_data(show_spinner=False)
def load_china_province_geojson() -> dict:
    """加载中国省份 GeoJSON（用于 choropleth）。

    说明：
    - 该 geojson 的 properties.name 与中文省份名一致
    - 运行时从 GitHub Gist raw 拉取，使用 st.cache_data 缓存避免重复网络请求
    """
    geojson_url = (
        "https://gist.githubusercontent.com/songkeys/e0e3467a7e2ab1e571de9ed4296fbc2a/"
        "raw/859f420ba8104f384e0d915a42cbf29fe94d947d/China%20Province%20GeoJSON"
    )
    resp = requests.get(geojson_url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def normalize_province_name(name: str) -> str:
    """标准化省份名称，尽量匹配 geojson 的 properties.name。"""
    if pd.isna(name):
        return ""
    s = str(name).strip()

    # 去掉常见后缀（避免“北京市/河北省/广西壮族自治区”与 geojson 的“北京/河北/广西”不匹配）
    for suffix in ["省", "市", "自治区", "特别行政区"]:
        s = s.replace(suffix, "")

    # 处理少数带民族冠词的自治区写法
    s = s.replace("壮族", "").replace("回族", "").replace("维吾尔", "")
    s = s.strip()
    return s


def reset_province_filter() -> None:
    """重置省份筛选到默认值。"""
    st.session_state["province_filter"] = "全部"


def clear_selected_map_province() -> None:
    """清除地图点击选择的省份。"""
    st.session_state["selected_map_province"] = None


def clear_dashboard_selected_province() -> None:
    """清除总览页地图点击选择的省份。"""
    st.session_state["dashboard_selected_province"] = None


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
        st.button("重置", width="stretch", on_click=reset_province_filter, help="重置省份")

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
    st.sidebar.markdown('<hr class="sidebar-sep" />', unsafe_allow_html=True)
    st.sidebar.button("清除省份选择", width="stretch", on_click=clear_selected_map_province, help="清除地图点击选择的省份")

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


def build_scored_ranking_table(df: pd.DataFrame, top_n: int = 20, include_region: bool = False) -> pd.DataFrame:
    """构建综合评分排名表，复用主页面评分标准。"""
    ranking_df = df.copy()
    if ranking_df.empty:
        if include_region:
            return pd.DataFrame(columns=["排名", "建筑名称", "朝代", "年代", "市/区", "综合评分", "星级"])
        return pd.DataFrame(columns=["排名", "建筑名称", "朝代", "年代", "省份", "保护批次", "综合评分", "星级"])

    ranking_df["综合评分"] = ranking_df.apply(calculate_building_score, axis=1)
    ranking_df["朝代"] = ranking_df["时代（中文）"].apply(get_era_label) if "时代（中文）" in ranking_df.columns else "其他"
    ranking_df["星级"] = ranking_df["综合评分"].apply(get_star_rating)
    ranking_df = ranking_df.sort_values(by="综合评分", ascending=False).head(top_n).reset_index(drop=True)
    ranking_df.insert(0, "排名", range(1, len(ranking_df) + 1))

    if include_region:
        region_series = ""
        if "市级政区名称（中文）" in ranking_df.columns and "县级政区名称（中文）" in ranking_df.columns:
            city = ranking_df["市级政区名称（中文）"].fillna("").astype(str).str.strip()
            district = ranking_df["县级政区名称（中文）"].fillna("").astype(str).str.strip()
            region_series = city.where(city != "", district)
            region_series = region_series.where(region_series != "", district)
        elif "市级政区名称（中文）" in ranking_df.columns:
            region_series = ranking_df["市级政区名称（中文）"]
        elif "县级政区名称（中文）" in ranking_df.columns:
            region_series = ranking_df["县级政区名称（中文）"]

        return pd.DataFrame({
            "排名": ranking_df["排名"],
            "建筑名称": ranking_df["单位名称（中文）"] if "单位名称（中文）" in ranking_df.columns else "",
            "朝代": ranking_df["朝代"],
            "年代": ranking_df["时代（中文）"] if "时代（中文）" in ranking_df.columns else "",
            "市/区": region_series,
            "综合评分": ranking_df["综合评分"],
            "星级": ranking_df["星级"],
        })

    return pd.DataFrame({
        "排名": ranking_df["排名"],
        "建筑名称": ranking_df["单位名称（中文）"] if "单位名称（中文）" in ranking_df.columns else "",
        "朝代": ranking_df["朝代"],
        "年代": ranking_df["时代（中文）"] if "时代（中文）" in ranking_df.columns else "",
        "省份": ranking_df["省级政区名称（中文）"] if "省级政区名称（中文）" in ranking_df.columns else "",
        "保护批次": ranking_df["批次（中文）"] if "批次（中文）" in ranking_df.columns else "",
        "综合评分": ranking_df["综合评分"],
        "星级": ranking_df["星级"],
    })


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

    # 赛题布局：左省份排名列表 + 中国地图 + 右朝代排名列表（高度 500px 对齐）
    province_col = "省级政区名称（中文）"
    era_col = "时代（中文）"

    # 统计：省份数量
    if province_col in filtered_df.columns:
        prov_series = filtered_df[province_col].fillna("").astype(str)
        prov_norm = prov_series.apply(normalize_province_name)
        province_counts = prov_norm[prov_norm != ""].value_counts()
    else:
        province_counts = pd.Series(dtype=int)

    # 统计：朝代数量（唐/宋/元/明/清，其余合并为“其他”）
    era_major = ["唐", "宋", "元", "明", "清"]

    def classify_era(era_text: str) -> str:
        if pd.isna(era_text):
            return "其他"
        s = str(era_text)
        for e in era_major:
            if e in s:
                return e
        return "其他"

    if era_col in filtered_df.columns:
        era_series = filtered_df[era_col].fillna("").astype(str)
        era_counts = era_series.apply(classify_era).value_counts()
    else:
        era_counts = pd.Series(dtype=int)

    # 构造地图数据：把“无数据省份”也补为 0，便于用浅灰色显示
    geojson = load_china_province_geojson()
    geo_provinces = [f["properties"]["name"] for f in geojson.get("features", [])]
    # 地图需要包含中国所有省份/行政区图形：不做排除
    geo_provinces_main = geo_provinces

    all_prov_df = pd.DataFrame({"省份": geo_provinces_main})
    count_df = province_counts.rename_axis("省份").reset_index(name="数量")
    map_df = all_prov_df.merge(count_df, on="省份", how="left")
    map_df["数量"] = map_df["数量"].fillna(0).astype(int)

    # 中列：choropleth 地图（连续棕色系；0 显示为浅灰）
    max_count = int(map_df["数量"].max()) if not map_df.empty else 0
    color_scale = [
        [0.0, "#E0E0E0"],  # 无数据省份
        [0.2, "#DEB887"],
        [0.6, "#CD853F"],
        [1.0, "#8B4513"],
    ]

    fig = px.choropleth(
        map_df,
        geojson=geojson,
        locations="省份",
        featureidkey="properties.name",
        color="数量",
        color_continuous_scale=color_scale,
        range_color=(0, max_count if max_count > 0 else 1),
        hover_data={"省份": True, "数量": True},
    )
    fig.update_traces(
        marker_line_width=0.4,
        marker_line_color="rgba(74,55,40,0.35)",
        hovertemplate="省份名称：%{location}<br>%{z}座<extra></extra>",
    )
    fig.update_layout(
        height=650,
        showlegend=False,
        coloraxis_showscale=False,  # 不显示图例
        # 把地图绘制区域压满画布，避免顶部留白
        geo=dict(fitbounds="locations", visible=False, domain=dict(x=[0, 1], y=[0, 1])),
        autosize=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0, pad=0),  # 去掉所有边距与内边距
        # 关闭拖拽缩放，优先支持单击选中省份
        dragmode=False,
    )

    if "dashboard_selected_province" not in st.session_state:
        st.session_state["dashboard_selected_province"] = None

    # 左右列表：固定外层高度与地图一致，标题固定在顶部，列表区域独立滚动
    # 这样可保证：三列顶部对齐且底边与中列地图严格一致
    left_html = [
        "<div style='min-height:650px; height:650px; display:flex; flex-direction:column; padding-right:6px;'>",
        "<h4 style='font-size: 15px; margin-bottom: 5px; white-space: nowrap; text-align:center; color:#8B4513; font-weight:800;'>"
        "🏛️ 古建筑数量省份排名</h4>",
        "<div style='flex:1; overflow-y:auto;'>",
    ]
    for i, (prov, cnt) in enumerate(province_counts.sort_values(ascending=False).items(), start=1):
        if i > 10:  # 只展示 Top 10
            break
        left_html.append(
            "<div style='color:#4A3728; margin:8px 0; padding:6px 8px; border-radius:10px; background:rgba(139,69,19,0.06);'>"
            f"<span style='font-weight:800; color:#8B4513; width:24px; display:inline-block;'>{i}</span>"
            f"{prov}：<span style='font-weight:800; color:#8B4513;'>{int(cnt)}</span>座</div>"
        )
    left_html.append("</div></div>")

    right_html = [
        "<div style='min-height:650px; height:650px; display:flex; flex-direction:column; padding-left:6px;'>",
        "<h4 style='font-size: 15px; margin-bottom: 5px; white-space: nowrap; text-align:center; color:#8B4513; font-weight:800;'>"
        "📅 古建筑数量朝代排名</h4>",
        "<div style='flex:1; overflow-y:auto;'>",
    ]
    right_order = [e for e in era_major] + (["其他"] if int(era_counts.get("其他", 0)) > 0 else [])
    for i, e in enumerate(right_order, start=1):
        cnt = int(era_counts.get(e, 0))
        right_html.append(
            "<div style='color:#4A3728; margin:8px 0; padding:6px 8px; border-radius:10px; background:rgba(160,82,45,0.06);'>"
            f"<span style='font-weight:800; color:#A0522D; width:24px; display:inline-block;'>{i}</span>"
            f"{e}：<span style='font-weight:800; color:#A0522D;'>{cnt}</span>座</div>"
        )
    right_html.append("</div></div>")

    selected_dashboard_province = st.session_state.get("dashboard_selected_province")

    if selected_dashboard_province:
        st.button("← 返回总览", on_click=clear_dashboard_selected_province)
        col_map, col_table = st.columns([2, 3])
        with col_map:
            clicked_province = st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"dashboard_map_detail_{selected_dashboard_province}",
                on_select="rerun",
                config={"scrollZoom": True},
                selection_mode=("points",),
            )
            if clicked_province and clicked_province.selection:
                points = clicked_province.selection.points
                if points:
                    province_name = points[0].get("location")
                    if province_name:
                        st.session_state["dashboard_selected_province"] = province_name
                        st.rerun()

        with col_table:
            province_df = filtered_df[
                filtered_df[province_col].fillna("").astype(str).apply(normalize_province_name) == selected_dashboard_province
            ].copy()
            st.subheader(f"{selected_dashboard_province} · 古建筑评分排名")
            province_ranking_df = build_scored_ranking_table(province_df, top_n=20, include_region=True)
            st.dataframe(province_ranking_df, width="stretch", hide_index=True)
    else:
        col_left, col_center, col_right = st.columns([0.8, 4, 0.8])
        with col_left:
            st.markdown("".join(left_html), unsafe_allow_html=True)
        with col_center:
            # 强制中列内容从顶部开始（避免地图上方空白）
            st.markdown(
                """
                <style>
                .map-container {
                    margin-top: 0;
                    padding-top: 0;
                    display: flex;
                    flex-direction: column;
                    justify-content: flex-start;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            st.markdown('<div class="map-container">', unsafe_allow_html=True)
            # 渲染地图（保持原有方式）
            clicked_province = st.plotly_chart(
                fig,
                use_container_width=True,
                key="dashboard_map",
                on_select="rerun",
                config={"scrollZoom": True},
                selection_mode=("points",),
            )
            if clicked_province and clicked_province.selection:
                points = clicked_province.selection.points
                if points:
                    province_name = points[0].get("location")
                    if province_name:
                        st.session_state["dashboard_selected_province"] = province_name
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col_right:
            st.markdown("".join(right_html), unsafe_allow_html=True)

    # 第三行：建筑类别柱状图
    st.plotly_chart(create_category_bar_chart(filtered_df), width="stretch")

    # 第四行：古建筑综合评分排名
    display_df = build_scored_ranking_table(filtered_df, top_n=20, include_region=False)
    st.dataframe(display_df, width="stretch", hide_index=True)


def render_map_view(filtered_df: pd.DataFrame, selected_province: str) -> None:
    """渲染地图探索视图。"""
    st.title("地图探索")
    st.caption("在地图中查看古建筑空间分布，可结合省份筛选进行探索。")

    st.info(f"当前筛选古建筑数量：{len(filtered_df)} 条")

    # 使用 Plotly 省份地图以支持点击交互；左侧约 40%，右侧约 60%
    province_col = "省级政区名称（中文）"
    plot_df = filtered_df.copy()
    if province_col in plot_df.columns:
        plot_df["地图省份"] = plot_df[province_col].fillna("").astype(str).apply(normalize_province_name)
        province_counts = plot_df["地图省份"][plot_df["地图省份"] != ""].value_counts()
    else:
        plot_df["地图省份"] = ""
        province_counts = pd.Series(dtype=int)

    geojson = load_china_province_geojson()
    geo_provinces = [f["properties"]["name"] for f in geojson.get("features", [])]
    all_prov_df = pd.DataFrame({"省份": geo_provinces})
    count_df = province_counts.rename_axis("省份").reset_index(name="数量")
    map_df = all_prov_df.merge(count_df, on="省份", how="left")
    map_df["数量"] = map_df["数量"].fillna(0).astype(int)

    fig = px.choropleth(
        map_df,
        geojson=geojson,
        locations="省份",
        featureidkey="properties.name",
        color="数量",
        color_continuous_scale=[[0.0, "#E0E0E0"], [0.2, "#DEB887"], [0.6, "#CD853F"], [1.0, "#8B4513"]],
        hover_data={"省份": True, "数量": True},
        custom_data=["省份"],
    )
    fig.update_traces(
        marker_line_width=0.4,
        marker_line_color="rgba(74,55,40,0.35)",
        hovertemplate="省份名称：%{location}<br>%{z}座<extra></extra>",
    )
    fig.update_layout(
        height=620,
        showlegend=False,
        coloraxis_showscale=False,
        geo=dict(fitbounds="locations", visible=False, domain=dict(x=[0, 1], y=[0, 1])),
        autosize=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0, pad=0),
        # 关闭拖拽缩放，优先支持单击选中省份
        dragmode=False,
        clickmode="event+select",
    )

    col_map, col_table = st.columns([2, 3])
    with col_map:
        chart_data = st.plotly_chart(
            fig,
            use_container_width=True,
            key="china_map",
            on_select="rerun",
            config={"scrollZoom": True},
            selection_mode=("points",),
        )
        if chart_data and chart_data.selection and chart_data.selection.points:
            point = chart_data.selection.points[0]
            selected_name = point.get("location")
            if not selected_name and point.get("customdata"):
                selected_name = point["customdata"][0]
            if selected_name:
                st.session_state["selected_map_province"] = selected_name

    with col_table:
        selected_map_province = st.session_state.get("selected_map_province")
        if selected_map_province:
            province_df = plot_df[plot_df["地图省份"] == selected_map_province].copy()
            st.subheader(f"{selected_map_province} · 古建筑评分排名")
            province_ranking_df = build_scored_ranking_table(province_df, top_n=20, include_region=True)
            st.dataframe(province_ranking_df, width="stretch", hide_index=True)
        else:
            st.markdown("### 👆 点击地图上的省份查看详情")


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
