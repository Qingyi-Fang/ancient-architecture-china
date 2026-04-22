"""Streamlit 主入口：中国古建筑·数字图谱。"""

from __future__ import annotations

from pathlib import Path
import html as html_module
import re
import os
from collections import Counter
from typing import Optional
import random

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFilter

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
        :root{
            --aa-bg:#F7F2EA;
            --aa-card:#FFFFFF;
            --aa-text:#2C2018;
            --aa-muted:rgba(44,32,24,.62);
            --aa-border:rgba(74,55,40,.12);
            --aa-shadow:0 10px 24px rgba(44,22,10,.08);
            --aa-accent:#8B4513;
        }

        /* 全局背景与排版更“比赛展示” */
        [data-testid="stAppViewContainer"]{
            background: radial-gradient(1200px 600px at 20% 0%, rgba(222,184,135,.22), transparent 60%),
                        radial-gradient(900px 500px at 80% 10%, rgba(139,69,19,.10), transparent 55%),
                        var(--aa-bg);
        }
        html, body, [data-testid="stAppViewContainer"]{
            color: var(--aa-text);
        }

        /* 禁止页面级横向滚动（避免出现底部横向滑动条） */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main, .main .block-container{
            overflow-x: hidden !important;
            max-width: 100% !important;
        }

        /* 主内容区域：更舒展的左右留白 */
        .main .block-container {
            max-width: 1180px !important;
            padding-left: 1.0rem !important;
            padding-right: 1.0rem !important;
            padding-top: .8rem !important;
        }

        /* 缩小侧边栏 */
        [data-testid="stSidebar"] {
            min-width: 200px !important;
            max-width: 200px !important;
        }

        /* 统一卡片样式（HTML 包裹用） */
        .aa-card{
            background:var(--aa-card);
            border:1px solid var(--aa-border);
            border-radius:16px;
            box-shadow:var(--aa-shadow);
            padding:16px 16px;
        }
        .aa-card-title{
            font-size:14px;
            color:var(--aa-muted);
            font-weight:700;
            letter-spacing:.06em;
            margin-bottom:10px;
        }
        .aa-hint{
            color:var(--aa-muted);
            font-size:13px;
            margin-top:2px;
        }

        /* AI 解说正文：字号/颜色与 caption、.aa-hint 一致；小标题略强调 */
        .aa-ai-commentary{
            line-height:1.65;
        }
        .aa-ai-commentary .aa-ai-section-title{
            font-size:14px;
            font-weight:800;
            color:var(--aa-text);
            margin:0.75rem 0 0.4rem 0;
            letter-spacing:.02em;
        }
        .aa-ai-commentary .aa-ai-section-title:first-child{
            margin-top:0;
        }
        .aa-ai-commentary .aa-ai-body{
            font-size:13px;
            color:var(--aa-muted);
            margin:0 0 0.5rem 0;
        }
        .aa-ai-commentary .aa-ai-body strong{
            font-weight:700;
            color:rgba(44,32,24,0.82);
        }

        /* 弹窗风格：与首页卡片保持一致 */
        [data-testid="stDialog"] [role="dialog"]{
            border-radius: 16px !important;
            border: 1px solid rgba(255, 255, 255, 0.38) !important;
            background: rgba(255, 255, 255, 0.62) !important;
            box-shadow: 0 14px 36px rgba(44,22,10,.15) !important;
            backdrop-filter: blur(4px) !important;
            -webkit-backdrop-filter: blur(4px) !important;
            width: 70vw !important;
            max-width: 70vw !important;
        }
        [data-testid="stDialog"] [role="dialog"] .aa-card{
            background: rgba(244, 238, 228, 0.78) !important;
            border: 1px solid rgba(196, 176, 150, 0.45) !important;
            box-shadow: 0 8px 22px rgba(44,22,10,.10) !important;
        }

        /* KPI 数字更突出 */
        [data-testid="stMetricValue"]{
            color:var(--aa-accent) !important;
        }
        [data-testid="stMetric"]{
            background: rgba(255, 255, 255, 0.42) !important;
            border: 1px solid rgba(255, 255, 255, 0.38) !important;
            border-radius: 12px !important;
            box-shadow: 0 8px 20px rgba(44,22,10,.07) !important;
            backdrop-filter: blur(3px) !important;
            -webkit-backdrop-filter: blur(3px) !important;
            padding: 10px 12px !important;
            min-height: 92px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
        }
        [data-testid="stMetricLabel"]{
            justify-content: center !important;
            text-align: center !important;
            color: var(--aa-muted) !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricValue"]{
            justify-content: center !important;
            text-align: center !important;
            font-size: 1.9rem !important;
            line-height: 1.1 !important;
            margin-top: 4px !important;
        }

        /* 地图搜索里的古建筑卡片按钮：与首页卡片同风格（仅主内容区） */
        [data-testid="stMain"] .stButton > button {
            background: rgba(255, 255, 255, 0.42) !important;
            border: 1px solid rgba(255, 255, 255, 0.38) !important;
            border-radius: 14px !important;
            box-shadow: 0 8px 20px rgba(44,22,10,.07) !important;
            backdrop-filter: blur(3px) !important;
            -webkit-backdrop-filter: blur(3px) !important;
            color: #2C2018 !important;
            min-height: 120px !important;
            padding: 12px 14px !important;
            line-height: 1.5 !important;
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            white-space: pre-line !important;
        }
        [data-testid="stMain"] .stButton > button:hover {
            border-color: rgba(139, 69, 19, 0.35) !important;
            box-shadow: 0 10px 24px rgba(44,22,10,.1) !important;
            transform: translateY(-1px);
        }
        [data-testid="stMain"] .stButton > button:focus,
        [data-testid="stMain"] .stButton > button:focus-visible {
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(139,69,19,.2) !important;
        }

        /* 表格/图表容器更贴合卡片 */
        [data-testid="stDataFrame"], .stPlotlyChart{
            border-radius: 12px;
        }

        /* 彻底隐藏 Plotly 工具栏占位层（避免出现空白白条） */
        .js-plotly-plot .plotly .modebar,
        .js-plotly-plot .plotly .modebar-container,
        .js-plotly-plot .plotly .modebar-group,
        .js-plotly-plot .plotly-notifier {
            display: none !important;
        }
        .js-plotly-plot .plotly .modebar-container{
            height: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        /* Plotly 外层容器强制透明，杜绝残留白底条 */
        .stPlotlyChart,
        .stPlotlyChart > div,
        .stPlotlyChart .js-plotly-plot,
        .stPlotlyChart .plot-container,
        .stPlotlyChart .svg-container{
            background: transparent !important;
        }

        /* 隐藏 Plotly on_select 产生的 Reset/控件占位（常见为白色长条） */
        .stPlotlyChart button,
        .stPlotlyChart [data-testid="stBaseButton-secondary"],
        .stPlotlyChart [data-testid^="stBaseButton-"],
        .stPlotlyChart [data-testid="stButton"],
        .stPlotlyChart .stButton,
        .stPlotlyChart form{
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            width: 0 !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            overflow: hidden !important;
        }

        /* 压缩图表与下一个模块之间的留白（避免地图下方出现大块空余） */
        [data-testid="stAppViewContainer"] .stPlotlyChart{
            margin-bottom: .25rem !important;
        }
        [data-testid="stAppViewContainer"] .element-container{
            margin-bottom: .25rem !important;
        }
        [data-testid="stAppViewContainer"] h3{
            margin-top: .65rem !important;
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
    dimensions = calculate_building_dimensions(row)
    total_score = (
        dimensions["保护级别"] * 0.35
        + dimensions["年代久远度"] * 0.30
        + dimensions["建筑稀有性"] * 0.20
        + dimensions["历史价值"] * 0.15
    )
    return round(float(total_score), 1)


def calculate_building_dimensions(row: pd.Series) -> dict[str, float]:
    """计算古建筑四维评分（用于雷达图与解说）。"""
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

    return {
        "保护级别": float(protection_score),
        "年代久远度": float(era_score),
        "建筑稀有性": float(rarity_score),
        "历史价值": float(historical_score),
    }


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


def create_building_radar_chart(building_name: str, dimensions: dict[str, float]) -> go.Figure:
    """创建单体古建筑四维评分雷达图。"""
    labels = list(dimensions.keys())
    values = list(dimensions.values())
    # 闭合雷达图
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            line=dict(color="#8B4513", width=2),
            fillcolor="rgba(139,69,19,0.25)",
            marker=dict(color="#8B4513", size=6),
            name=building_name,
        )
    )
    fig.update_layout(
        title=dict(text=f"{building_name} · 四维价值雷达", y=0.98, yanchor="top"),
        showlegend=False,
        height=400,
        margin=dict(l=32, r=32, t=56, b=72),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color="#4A3728"),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            domain=dict(x=[0.02, 0.98], y=[0.02, 0.90]),
            radialaxis=dict(range=[0, 100], tickfont=dict(size=10), gridcolor="rgba(60,45,30,0.2)"),
            angularaxis=dict(
                tickfont=dict(size=12, color="#4A3728"),
                ticklen=6,
            ),
        ),
    )
    return fig


def format_ai_commentary_html(raw: str) -> str:
    """将 AI 解说 Markdown（## 标题、**加粗**）转为 HTML，正文样式由 .aa-ai-commentary 控制。"""
    text = raw.replace("\r\n", "\n").strip()
    text = re.sub(r"  \n", "\n", text)
    chunks: list[str] = []

    def inline_bold(s: str) -> str:
        parts = re.split(r"(\*\*.+?\*\*)", s)
        out: list[str] = []
        for part in parts:
            if len(part) >= 4 and part.startswith("**") and part.endswith("**"):
                inner = html_module.escape(part[2:-2])
                out.append(f"<strong>{inner}</strong>")
            else:
                out.append(html_module.escape(part))
        return "".join(out)

    def paragraph_html(body: str) -> str:
        lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
        inner = "<br/>".join(inline_bold(ln) for ln in lines)
        return f'<p class="aa-ai-body">{inner}</p>'

    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            lines = block.split("\n", 1)
            title = re.sub(r"^#+\s*", "", lines[0]).strip()
            chunks.append(f'<div class="aa-ai-section-title">{html_module.escape(title)}</div>')
            if len(lines) > 1 and lines[1].strip():
                chunks.append(paragraph_html(lines[1].strip()))
        else:
            chunks.append(paragraph_html(block))

    return "".join(chunks)


def build_building_ai_commentary(row: pd.Series, score: float, stars: str) -> str:
    """生成古建筑 AI 解说（无模型依赖）：四段 Markdown，含保护与参观拓展。"""
    name = str(row.get("单位名称（中文）", "该古建筑")).strip() or "该古建筑"
    era = str(row.get("时代（中文）", "")).strip() or "年代待考"
    batch = str(row.get("批次（中文）", "")).strip() or "未标注批次"
    province = str(row.get("省级政区名称（中文）", "")).strip()
    city = str(row.get("市级政区名称（中文）", "")).strip()
    district = str(row.get("县级政区名称（中文）", "")).strip()
    category = classify_building_category(name)
    dimensions = calculate_building_dimensions(row)

    region = " / ".join([x for x in [province, city, district] if x]) or "地区信息待补充"
    dim_rank = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
    best_dim = dim_rank[0][0]
    weak_dim = dim_rank[-1][0]
    dim_desc = "、".join([f"{k}{v:.0f}" for k, v in dimensions.items()])

    return (
        "## 历史脉络与地域背景  \n"
        f"**{name}**坐落于**{region}**，文献与登记信息所示时代为**{era}**，在类型上归入**{category}**。"
        f"结合政区语境，可将该遗存置于地方社会史与匠作传统中理解；若需深入，可比对同省同类文保单位的形制与题记材料。  \n"
        f"本应用内综合评分为 **{score} 分（{stars}）**，四维为 {dim_desc}，供观展时快速把握价值侧重。  \n"
        "## 形制特征与遗产价值  \n"
        f"从空间与功能角度看，该类建筑常见院落组织、木结构体系与装饰意匠等要素，反映礼制、居住或公共活动的不同需求。"
        f"评分上**{best_dim}**最为突出，宜作为讲解主线；**{weak_dim}**相对较低，解说中可提示观众结合实地勘察或档案再行印证。  \n"
        "## 保护与传承建议  \n"
        f"登记保护信息为**{batch}**。建议落实预防性保护思维：定期开展现状勘察与病害记录，木结构注意防潮防火与虫蛀监测，"
        f"修缮应坚持「最小干预、可识别、可逆」原则；展示上可采用分层解说（遗存本体 / 历史层积 / 当代利用），并推进数字化测绘与档案公开，"
        f"便于学术利用与公众教育。  \n"
        "## 参观与导览提示  \n"
        "到访前建议核实开放时段与预约政策，身着便于步行的鞋履并预留讲解时间。"
        "参观时请勿触摸彩绘与木石构件，勿使用闪光灯拍摄敏感壁画或彩塑；雨雪天气注意屋面滴水与地面湿滑。"
        "若在宗教或礼仪场所，请遵守现场秩序与着装要求，轻声缓步以尊重文化遗产与使用者。"
    )


def get_deepseek_api_key() -> Optional[str]:
    """读取 DeepSeek API Key（优先 secrets，其次环境变量）。"""
    try:
        if "DEEPSEEK_API_KEY" in st.secrets:
            key = str(st.secrets["DEEPSEEK_API_KEY"]).strip()
            if key:
                return key
    except Exception:
        pass

    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    return env_key or None


@st.cache_data(show_spinner=False, ttl=3600)
def generate_ai_commentary_with_deepseek(
    building_name: str,
    era: str,
    batch: str,
    province: str,
    city: str,
    district: str,
    category: str,
    score: float,
    stars: str,
    dim_desc: str,
    best_dim: str,
    weak_dim: str,
) -> str:
    """调用 DeepSeek API，按四段结构化提示生成深度解说。"""
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    region = " / ".join([x for x in [province, city, district] if x]) or "地区信息待补充"
    system_prompt = (
        "你兼具中国建筑史与文物建筑保护领域素养，担任数字展陈与公众教育语境下的讲解员。"
        "输出须为可上屏的专业中文，术语准确（如构架、形制、院落、木作、修缮、预防性保护、活化利用等），避免空话与过度抒情。"
        "\n\n【版式】使用 Markdown，且必须依次包含下列四个二级标题（##），标题字面须完全一致：\n"
        "## 历史脉络与地域背景\n"
        "## 形制特征与遗产价值\n"
        "## 保护与传承建议\n"
        "## 参观与导览提示\n"
        "每个标题下写 2–4 句；全文总字数约 480–800 字。可恰当使用 **加粗** 强调关键概念。"
        "\n\n【各段要点】\n"
        "1) 历史脉络：时代、政区地缘、在区域建筑谱系或类型学中的大致位置；信息不足时用「一般认为」「尚需档案印证」等谨慎表述。\n"
        "2) 形制与价值：紧扣「类别」与给定「四维」及最强/最弱维度，点到空间组织、结构或装饰意匠的代表性；勿虚构具体营造年代、匠师名或未经核实的轶事。\n"
        "3) 保护与传承：结合保护批次与建筑类型，从修缮原则（最小干预、可逆、可识别）、日常监测、防火防潮防虫、档案与数字化、合理展示利用等中选 2–4 条展开为可操作建议；勿编造真实不存在的修缮工程名称或批文号。\n"
        "4) 参观导览：面向访客，写行前准备（开放信息、预约、交通大类提示）、参观礼仪、摄影与文物保护边界、天气/季节与安全提示；无具体开放时间时写普适建议。\n"
    )
    user_prompt = (
        f"请基于下列结构化数据撰写解说（数据可能不全，请在缺项处合理泛化而非杜撰）：\n"
        f"- 建筑名称：{building_name}\n"
        f"- 地区：{region}\n"
        f"- 时代：{era}\n"
        f"- 建筑类别（应用内分类）：{category}\n"
        f"- 保护批次：{batch}\n"
        f"- 综合评分：{score:.1f}（{stars}）\n"
        f"- 四维评分：{dim_desc}\n"
        f"- 最强维度：{best_dim}\n"
        f"- 相对薄弱维度：{weak_dim}\n\n"
        "严格按系统提示的四段标题与字数要求输出，不要输出开场白或结语套话。"
    )

    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.55,
            "max_tokens": 1100,
        },
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    text = str(content).strip()
    if not text:
        raise RuntimeError("DeepSeek 返回内容为空")
    return text


def build_building_commentary(row: pd.Series, score: float, stars: str) -> tuple[str, bool]:
    """优先使用 DeepSeek 生成解说；失败时回退本地模板。"""
    name = str(row.get("单位名称（中文）", "该古建筑")).strip() or "该古建筑"
    era = str(row.get("时代（中文）", "")).strip() or "年代待考"
    batch = str(row.get("批次（中文）", "")).strip() or "未标注批次"
    province = str(row.get("省级政区名称（中文）", "")).strip()
    city = str(row.get("市级政区名称（中文）", "")).strip()
    district = str(row.get("县级政区名称（中文）", "")).strip()
    category = classify_building_category(name)
    dimensions = calculate_building_dimensions(row)
    dim_rank = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
    best_dim = dim_rank[0][0]
    weak_dim = dim_rank[-1][0]
    dim_desc = "、".join([f"{k}{v:.0f}" for k, v in dimensions.items()])

    try:
        ai_text = generate_ai_commentary_with_deepseek(
            building_name=name,
            era=era,
            batch=batch,
            province=province,
            city=city,
            district=district,
            category=category,
            score=score,
            stars=stars,
            dim_desc=dim_desc,
            best_dim=best_dim,
            weak_dim=weak_dim,
        )
        return ai_text, True
    except Exception:
        return build_building_ai_commentary(row, score, stars), False


@st.dialog("古建筑详情", width="large")
def show_building_detail_dialog(row_data: dict[str, object]) -> None:
    """点击卡片后显示弹窗：雷达图 + AI解说。"""
    # 中文注释：弹窗内容以 session_state 为准，支持“相似建筑”点击后在弹窗内切换
    active_row_data = st.session_state.get("active_building_dialog_row") or row_data
    st.session_state["active_building_dialog_row"] = active_row_data

    name = str(active_row_data.get("单位名称（中文）", "古建筑")).strip() or "古建筑"
    score = float(active_row_data.get("综合评分", 0))
    stars = str(active_row_data.get("星级", get_star_rating(score)))
    row_series = pd.Series(active_row_data)

    st.markdown(
        f"""
        <div class="aa-card" style="padding:12px 14px;">
            <div class="aa-card-title">建筑信息</div>
            <div style="font-size:22px; font-weight:900; color:#2C2018;">{name}</div>
            <div class="aa-hint">综合评分：<b>{score:.1f}</b> 分 · {stars}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    show_radar = st.checkbox("显示雷达图（可选）", value=True, key=f"dialog_show_radar_{name}")
    if show_radar:
        dimensions = calculate_building_dimensions(row_series)
        radar_fig = create_building_radar_chart(name, dimensions)
        st.plotly_chart(radar_fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### AI 深度解说")
    use_realtime_ai = st.checkbox(
        "启用 DeepSeek 实时解说（较慢）",
        value=False,
        key=f"dialog_use_realtime_ai_{name}",
    )
    st.caption(
        "默认使用本地解说模板（更快）；勾选上方选项后将调用 DeepSeek 实时生成，通常需等待数秒至十余秒。"
    )
    with st.spinner("正在生成解说，请稍候…"):
        if use_realtime_ai:
            commentary, is_realtime_ai = build_building_commentary(row_series, score, stars)
        else:
            commentary, is_realtime_ai = build_building_ai_commentary(row_series, score, stars), False
    st.markdown(
        f'<div class="aa-ai-commentary">{format_ai_commentary_html(commentary)}</div>',
        unsafe_allow_html=True,
    )
    st.caption("解说来源：DeepSeek 实时生成" if is_realtime_ai else "解说来源：本地模板（未配置 DeepSeek 或调用失败）")

    # ===== 相似建筑推荐 =====
    # 中文注释：相似推荐计算量较大，改为按需开启，保证弹窗先秒开
    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
    show_similar = st.checkbox(
        "显示相似建筑推荐（可选）",
        value=False,
        key=f"dialog_show_similar_{name}",
    )
    if not show_similar:
        st.caption("勾选后再计算并展示相似建筑推荐。")
        return
    st.markdown(
        """
        <div style="font-size:14px; color:#8B4513; font-weight:bold; margin-bottom:10px;">
            🏛️ 相似建筑推荐
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        full_df = load_app_data()
    except Exception:
        full_df = pd.DataFrame()

    if full_df.empty:
        st.caption("暂无可用于推荐的完整数据集。")
        return

    # 中文注释：准备当前建筑的匹配维度
    cur_name = str(row_series.get("单位名称（中文）", "")).strip()
    cur_era_label = get_era_label(str(row_series.get("时代（中文）", "")))
    cur_category = classify_building_category(cur_name)
    cur_province = str(row_series.get("省级政区名称（中文）", "")).strip()

    # 中文注释：构造候选集，排除当前建筑本身（同名+同省视为同一条）
    cand = full_df.copy()
    if "单位名称（中文）" in cand.columns:
        cand_name = cand["单位名称（中文）"].fillna("").astype(str).str.strip()
    else:
        cand_name = pd.Series([""] * len(cand))
    if "省级政区名称（中文）" in cand.columns:
        cand_prov = cand["省级政区名称（中文）"].fillna("").astype(str).str.strip()
    else:
        cand_prov = pd.Series([""] * len(cand))
    cand = cand[~((cand_name == cur_name) & (cand_prov == cur_province))].copy()

    if cand.empty:
        st.caption("暂无可推荐的相似建筑。")
        return

    # 中文注释：计算候选的朝代/类型/省份匹配度，并按匹配度+评分排序
    cand["__朝代"] = cand["时代（中文）"].apply(get_era_label) if "时代（中文）" in cand.columns else "其他"
    cand["__类型"] = cand["单位名称（中文）"].fillna("").astype(str).apply(classify_building_category) if "单位名称（中文）" in cand.columns else "其他"
    cand["__省份"] = cand_prov.loc[cand.index]

    cand["__match_era"] = (cand["__朝代"] == cur_era_label).astype(int)
    cand["__match_cat"] = (cand["__类型"] == cur_category).astype(int)
    cand["__match_prov"] = (cand["__省份"] == cur_province).astype(int)
    cand["__match_score"] = cand["__match_era"] + cand["__match_cat"] + cand["__match_prov"]

    # 中文注释：复用评分函数计算综合评分与星级（若已存在则覆盖为一致口径）
    cand["综合评分"] = cand.apply(calculate_building_score, axis=1)
    cand["星级"] = cand["综合评分"].apply(get_star_rating)

    rec_df = (
        cand.sort_values(by=["__match_score", "综合评分"], ascending=[False, False])
        .head(3)
        .reset_index(drop=True)
    )

    if rec_df.empty:
        st.caption("暂无可推荐的相似建筑。")
        return

    # 中文注释：推荐卡片（3 列横排），点击后切换弹窗展示内容
    rec_cols = st.columns(3)
    for i in range(min(3, len(rec_df))):
        r = rec_df.iloc[i]
        r_name = str(r.get("单位名称（中文）", "未知古建")).strip() or "未知古建"
        r_era = get_era_label(str(r.get("时代（中文）", "")))
        r_prov = str(r.get("省级政区名称（中文）", "")).strip() or "未知省份"
        r_stars = str(r.get("星级", "⭐"))

        label = f"{r_name}\n{r_era} · {r_prov}\n{r_stars}"
        with rec_cols[i]:
            if st.button(label, key=f"sim_rec_{name}_{i}", use_container_width=True):
                st.session_state["active_building_dialog_row"] = r.to_dict()
                st.rerun()


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
    # 递增重置令牌，强制重建地图组件以清除 Plotly 选中高亮
    st.session_state["map_selection_reset_token"] = st.session_state.get("map_selection_reset_token", 0) + 1


def clear_dashboard_selected_province() -> None:
    """清除总览页地图点击选择的省份。"""
    st.session_state["dashboard_selected_province"] = None
    # 递增重置令牌，强制重建总览页地图组件以清除 Plotly 选中高亮/残留 selection
    st.session_state["dashboard_map_reset_token"] = st.session_state.get("dashboard_map_reset_token", 0) + 1


def build_sidebar(df: pd.DataFrame) -> tuple[str, str, str]:
    """构建侧边栏并返回视图、省份和搜索关键词。"""
    # 注入高级新中式极简样式，仅作用于侧边栏与控件
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=ZCOOL+XiaoWei&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@300;400;600;700&display=swap');

        /* 主内容区紧凑化：减少首屏空白，提升展示完整度 */
        [data-testid="stMainBlockContainer"] {
            padding-top: 0.2rem !important;
            padding-bottom: 0.6rem !important;
            margin-top: 0 !important;
        }

        /* 隐藏 Streamlit 顶部工具栏（Deploy 与右上菜单） */
        header[data-testid="stHeader"] {
            display: none !important;
            height: 0 !important;
        }

        [data-testid="stAppViewContainer"] .main {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
        }

        /* 清除主区域首元素默认上边距，避免标题前出现空条 */
        [data-testid="stMainBlockContainer"] > div:first-child {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }

        footer {
            visibility: hidden;
            height: 0;
        }

        section[data-testid="stSidebar"] {
            background-color: #7A3D17;
            min-width: 200px !important;
            max-width: 200px !important;
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
            padding: 0.08rem 0.24rem 0.2rem 0.24rem;
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
            font-family: "Ma Shan Zheng", "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 1.92rem;
            font-weight: 700;
            text-align: center;
            letter-spacing: 0.03em;
            line-height: 1.3;
            margin: 0.14rem 0 0.44rem 0;
            color: #F5F0E6;
            white-space: normal;
            word-break: keep-all;
        }

        section[data-testid="stSidebar"] .sidebar-module-title {
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 0.9rem;
            font-weight: 700;
            text-align: center;
            margin: 0.56rem 0 0.35rem 0;
            color: #F5F0E6;
        }

        /* 让“选择视图”组件的外层与本体都占满可用宽度 */
        section[data-testid="stSidebar"] .element-container:has(.stRadio) {
            width: 100% !important;
            margin-top: 0.16rem !important;
        }

        section[data-testid="stSidebar"] .stRadio {
            border: 1px solid rgba(245, 230, 209, 0.58);
            border-radius: 16px;
            padding: 2.1rem 0.34rem 0.4rem 0.34rem;
            margin: 0.08rem 0 0.22rem 0;
            background: linear-gradient(
                180deg,
                rgba(255, 247, 235, 0.12) 0%,
                rgba(250, 240, 230, 0.05) 100%
            );
            position: relative;
            display: block !important;
            width: 100% !important;
            min-width: 100% !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
            box-sizing: border-box;
            box-shadow: 0 8px 18px rgba(48, 24, 11, 0.2), inset 0 0 0 1px rgba(255, 250, 242, 0.08);
        }

        section[data-testid="stSidebar"] .stRadio::before {
            content: "选择视图";
            position: absolute;
            top: 0.36rem;
            left: 50%;
            transform: translateX(-50%);
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 0.88rem;
            font-weight: 700;
            color: #FFF7EA;
            white-space: nowrap;
            letter-spacing: 0.08em;
            padding: 0.06rem 0.35rem;
            border-radius: 999px;
            background: rgba(122, 61, 23, 0.45);
            border: 1px solid rgba(245, 230, 209, 0.38);
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
            border-color: #FFE6B8 !important;
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(255, 230, 184, 0.65), 0 0 16px rgba(255, 220, 160, 0.42) !important;
        }

        /* 下拉弹层：与侧边栏主题一致的棕金风格 */
        div[data-baseweb="popover"] {
            border-radius: 12px !important;
            overflow: hidden !important;
            box-shadow: 0 10px 24px rgba(44, 22, 10, 0.34) !important;
            border: 1px solid rgba(239, 214, 186, 0.35) !important;
        }

        div[data-baseweb="popover"] * {
            color: #F6E9D8 !important;
        }

        div[data-baseweb="popover"] ul,
        div[data-baseweb="popover"] [role="listbox"],
        div[data-baseweb="popover"] [data-testid="stSelectboxVirtualDropdown"] {
            background: linear-gradient(180deg, #8A4E25 0%, #6F3C1C 100%) !important;
        }

        /* 下拉弹层输入框：去英文占位突兀感 + 统一光标/聚焦色 */
        div[data-baseweb="popover"] input::placeholder {
            color: rgba(246, 233, 216, 0.45) !important;
        }

        div[data-baseweb="popover"] input {
            caret-color: #F6D5AF !important;
            background: rgba(255, 245, 232, 0.1) !important;
            border: 1px solid rgba(239, 214, 186, 0.46) !important;
            color: #F6E9D8 !important;
            box-shadow: none !important;
        }

        div[data-baseweb="popover"] input:focus {
            border-color: #FFE6B8 !important;
            box-shadow: 0 0 0 2px rgba(255, 230, 184, 0.45) !important;
        }

        section[data-testid="stSidebar"] [role="option"] {
            background: transparent !important;
            color: #F6E9D8 !important;
            border-radius: 8px !important;
            margin: 2px 6px !important;
            transition: all 0.12s ease !important;
        }

        section[data-testid="stSidebar"] [role="option"]:hover {
            background: rgba(246, 213, 175, 0.22) !important;
            color: #FFF3E3 !important;
        }

        section[data-testid="stSidebar"] [role="option"][aria-selected="true"] {
            background: linear-gradient(180deg, rgba(246, 213, 175, 0.45) 0%, rgba(221, 169, 116, 0.32) 100%) !important;
            color: #FFF6EA !important;
            box-shadow: inset 0 0 0 1px rgba(246, 213, 175, 0.4) !important;
        }

        section[data-testid="stSidebar"] input::placeholder {
            color: #B0A294 !important;
            font-family: "Noto Serif SC", "SimSun", serif !important;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label {
            border: 1px solid rgba(241, 224, 204, 0.72);
            border-radius: 14px;
            padding: 0.36rem 0.35rem;
            margin: 0 !important;
            background: linear-gradient(
                180deg,
                rgba(255, 247, 235, 0.14) 0%,
                rgba(250, 240, 230, 0.07) 100%
            );
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            width: 100%;
            transition: all 0.18s ease-in-out;
            min-height: 42px;
            box-shadow: inset 0 0 0 1px rgba(255, 247, 235, 0.16);
            box-sizing: border-box;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: 0.32rem;
            align-items: stretch;
            width: 100% !important;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label p {
            font-family: "ZCOOL XiaoWei", "Noto Serif SC", "SimSun", serif !important;
            font-size: 0.82rem;
            letter-spacing: 0.04em;
            white-space: nowrap;
            line-height: 1.2;
            font-weight: 700;
            color: #FFF3E2 !important;
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: linear-gradient(
                180deg,
                rgba(255, 247, 235, 0.2) 0%,
                rgba(250, 240, 230, 0.1) 100%
            );
            border-color: rgba(255, 244, 227, 0.96);
            transform: translateY(-1px);
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: linear-gradient(
                180deg,
                rgba(255, 246, 231, 0.32) 0%,
                rgba(230, 185, 137, 0.28) 100%
            );
            border-color: rgba(255, 246, 231, 0.95);
            box-shadow: inset 0 0 0 1px rgba(255, 248, 237, 0.62), 0 3px 10px rgba(48, 24, 11, 0.18);
        }

        section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
            color: #6B3C1D !important;
            text-shadow: none;
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
            font-size: 0.9rem;
            font-weight: 700;
            text-align: center;
            color: #F5F0E6;
            margin: 0.02rem 0 0.12rem 0;
            letter-spacing: 0.02em;
        }

        /* 省份筛选/搜索控件：更克制的比赛风输入区 */
        section[data-testid="stSidebar"] .stSelectbox,
        section[data-testid="stSidebar"] .stTextInput {
            margin-bottom: 0.18rem;
            padding: 0.1rem 0.16rem 0 0.16rem;
            border: none !important;
            border-radius: 0;
            background: transparent;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] .stTextInput:focus-within {
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] .stTextInput input {
            border: 1px solid rgba(226, 214, 200, 0.92) !important;
            border-radius: 8px !important;
            min-height: 32px !important;
            font-size: 0.8rem !important;
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
            border-color: #FFE6B8 !important;
            box-shadow: 0 0 0 2px rgba(255, 230, 184, 0.65), 0 0 16px rgba(255, 220, 160, 0.42) !important;
        }

        section[data-testid="stSidebar"] .stTextInput input {
            caret-color: #8B4A1E !important;
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
            border-color: #FFE6B8 !important;
            box-shadow: 0 0 0 2px rgba(255, 230, 184, 0.65), 0 0 16px rgba(255, 220, 160, 0.42) !important;
        }

        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"],
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="base-input"],
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"]:focus-within,
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="base-input"]:focus-within {
            border-color: #FFE6B8 !important;
            box-shadow: none !important;
            outline: none !important;
        }

        /* 清除 BaseWeb 输入框默认红色高亮/报错态 */
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div,
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div:hover,
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div:focus-within,
        section[data-testid="stSidebar"] .stTextInput div[data-baseweb="input"] > div:focus-visible {
            border-color: #FFE6B8 !important;
            box-shadow: 0 0 0 2px rgba(255, 230, 184, 0.65), 0 0 16px rgba(255, 220, 160, 0.42) !important;
            outline: none !important;
        }

        section[data-testid="stSidebar"] .stTextInput input,
        section[data-testid="stSidebar"] .stTextInput input:focus,
        section[data-testid="stSidebar"] .stTextInput input:focus-visible,
        section[data-testid="stSidebar"] .stTextInput input:active,
        section[data-testid="stSidebar"] .stTextInput input[aria-invalid="true"],
        section[data-testid="stSidebar"] .stTextInput [aria-invalid="true"] {
            border-color: #FFE6B8 !important;
            outline: none !important;
            box-shadow: none !important;
            -webkit-appearance: none !important;
            appearance: none !important;
        }

        section[data-testid="stSidebar"] .stTextInput input:focus,
        section[data-testid="stSidebar"] .stTextInput input:focus-visible,
        section[data-testid="stSidebar"] .stSelectbox input:focus,
        section[data-testid="stSidebar"] .stSelectbox input:focus-visible {
            outline: none !important;
            border-color: #FFE6B8 !important;
            box-shadow: none !important;
            caret-color: #8B4A1E !important;
        }

        section[data-testid="stSidebar"] .sidebar-footer {
            margin-top: auto;
            padding-top: 0.22rem;
            border-top: 1px solid #E8E0D5;
            font-size: 0.6rem;
            color: #F5F0E6;
            line-height: 1.3;
            text-align: left;
            font-weight: 300;
            background-color: #7A3D17;
            padding-bottom: 0.1rem;
            position: static;
            word-break: break-word;
        }

        section[data-testid="stSidebar"] .stTextInput,
        section[data-testid="stSidebar"] .stSelectbox,
        section[data-testid="stSidebar"] .stRadio {
            width: 100%;
        }

        /* 通用按钮：改为更明显的浅金卡片风（覆盖 disabled） */
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button,
        section[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] button[kind="secondary"],
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
            min-height: 31px !important;
            height: 31px !important;
            border-radius: 10px !important;
            border: 1.5px solid #F3D9BB !important;
            background: linear-gradient(180deg, #F0D4B4 0%, #E4BE96 100%) !important;
            color: #4A2812 !important;
            font-size: 0.72rem !important;
            padding: 0 0.24rem !important;
            margin-left: 0 !important;
            box-shadow: 0 3px 10px rgba(53, 28, 12, 0.22), inset 0 0 0 1px rgba(255, 247, 237, 0.65) !important;
            font-weight: 700 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #4A2812 !important;
            transition: all 0.15s ease !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover,
        section[data-testid="stSidebar"] .stButton > button:hover,
        section[data-testid="stSidebar"] button[kind="secondary"]:hover,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
            border-color: #FFE7CA !important;
            background: linear-gradient(180deg, #F5DEC3 0%, #ECCAAB 100%) !important;
            transform: translateY(-1px);
        }

        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:focus,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:focus-visible,
        section[data-testid="stSidebar"] .stButton > button:focus,
        section[data-testid="stSidebar"] .stButton > button:focus-visible,
        section[data-testid="stSidebar"] button[kind="secondary"]:focus,
        section[data-testid="stSidebar"] button[kind="secondary"]:focus-visible {
            outline: none !important;
            border-color: #FFE6B8 !important;
            box-shadow: 0 0 0 2px rgba(255, 230, 184, 0.65), 0 0 16px rgba(255, 220, 160, 0.42) !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:active,
        section[data-testid="stSidebar"] .stButton > button:active,
        section[data-testid="stSidebar"] button[kind="secondary"]:active {
            transform: translateY(1px);
            filter: brightness(0.98);
        }

        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button[disabled],
        section[data-testid="stSidebar"] .stButton > button:disabled,
        section[data-testid="stSidebar"] .stButton > button[disabled],
        section[data-testid="stSidebar"] button[kind="secondary"]:disabled,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:disabled {
            border: 1.5px solid #E0BC95 !important;
            background: linear-gradient(180deg, #E8C8A5 0%, #DCAA79 100%) !important;
            color: #5A3117 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #5A3117 !important;
            box-shadow: inset 0 0 0 1px rgba(255, 247, 237, 0.45) !important;
            cursor: not-allowed !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stButton"] > button span,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button p,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button div,
        section[data-testid="stSidebar"] .stButton > button span,
        section[data-testid="stSidebar"] .stButton > button p,
        section[data-testid="stSidebar"] .stButton > button div {
            color: #4A2812 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #4A2812 !important;
            font-weight: 700 !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled span,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled p,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled div,
        section[data-testid="stSidebar"] .stButton > button:disabled span,
        section[data-testid="stSidebar"] .stButton > button:disabled p,
        section[data-testid="stSidebar"] .stButton > button:disabled div {
            color: #5A3117 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #5A3117 !important;
        }

        section[data-testid="stSidebar"] .sidebar-action {
            margin-top: 0.02rem;
            margin-bottom: 0.16rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 模块一：项目主标题（纯文字）
    st.sidebar.markdown('<div class="sidebar-title">匠意千年</div>', unsafe_allow_html=True)

    # 模块二：视图切换（卡片内标题样式）
    view = st.sidebar.radio(
        "选择视图",
        ["总览仪表板", "地图探索"],
        index=0,
        label_visibility="collapsed",
    )
    # 中文注释：切换视图时清理“建筑详情弹窗”残留状态，避免进入新视图后自动弹出旧弹窗
    last_view = st.session_state.get("last_selected_view")
    if last_view is not None and last_view != view:
        st.session_state["show_building_dialog"] = False
        st.session_state["active_building_dialog_row"] = None
    st.session_state["last_selected_view"] = view

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

    # 省份筛选 + 紧凑重置按钮
    selected_province = st.sidebar.selectbox(
        "省份筛选",
        ["全部"] + provinces,
        index=0,
        label_visibility="collapsed",
        key="province_filter",
    )
    st.sidebar.markdown('<div class="sidebar-action">', unsafe_allow_html=True)
    st.sidebar.button("重置省份", width="stretch", on_click=reset_province_filter)
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

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
    st.sidebar.button("清除地图省份", width="stretch", on_click=clear_selected_map_province)

    st.sidebar.markdown(
        """
        <div class="sidebar-footer">
            数据来源:全国重点文物保护单位
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


@st.cache_data(show_spinner=False)
def build_name_word_frequencies(df: pd.DataFrame, top_n: int = 120) -> dict[str, int]:
    """从建筑名称中提取词频（中文分词优先，失败时回退到双字切分）。"""
    name_col = "单位名称（中文）"
    if name_col not in df.columns or df.empty:
        return {}

    stop_words = {
        "中国", "全国", "重点", "文物", "保护", "单位", "古建筑", "建筑",
        "遗址", "旧址", "旧居", "文物保护", "保护单位", "不可移动", "文物点",
        "一号", "二号", "三号", "四号", "五号", "六号", "七号", "八号", "九号", "十号",
    }
    text_series = df[name_col].fillna("").astype(str).str.strip()
    text_series = text_series[text_series != ""]
    if text_series.empty:
        return {}

    token_counter: Counter[str] = Counter()
    try:
        import jieba  # type: ignore

        for name in text_series.tolist():
            clean_text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", name)
            for token in jieba.lcut(clean_text):
                word = token.strip()
                if not word or len(word) < 2:
                    continue
                if word in stop_words:
                    continue
                token_counter[word] += 1
    except Exception:
        # 回退策略：提取中文连续串并做双字切分，保证无 jieba 时也可展示
        for name in text_series.tolist():
            chunks = re.findall(r"[\u4e00-\u9fff]{2,}", name)
            for chunk in chunks:
                for i in range(len(chunk) - 1):
                    token = chunk[i:i + 2]
                    if token in stop_words:
                        continue
                    token_counter[token] += 1

    # 加一点建筑类型关键词，提升词云可读性
    keyword_boost = ["寺", "庙", "塔", "宫", "殿", "祠", "楼", "阁", "桥", "城", "门", "院", "堂", "府", "观"]
    for name in text_series.tolist():
        for k in keyword_boost:
            if k in name:
                token_counter[k] += 1

    return dict(token_counter.most_common(top_n))


def get_font_path() -> Optional[str]:
    """自动下载并返回中文字体路径；下载失败则返回 None（词云使用默认字体，中文可能乱码）。"""
    font_dir = Path(__file__).resolve().parent / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    font_path = font_dir / "SourceHanSansSC-Regular.otf"

    if font_path.exists():
        return str(font_path)

    url = (
        "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/"
        "SourceHanSansSC-Regular.otf"
    )
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        font_path.write_bytes(response.content)
        return str(font_path)
    except Exception:
        return None


def render_name_word_cloud(df: pd.DataFrame) -> None:
    """渲染建筑名称词云。"""
    frequencies = build_name_word_frequencies(df, top_n=120)
    st.markdown(
        """
        <div style="font-size:18px; color:#8B4513; font-weight:bold; text-align:center; margin-bottom:10px;">
            建筑名称词云
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("基于当前筛选数据的建筑名称高频词（动态联动省份与搜索条件）。")

    if not frequencies:
        st.info("当前筛选条件下暂无可用于词云的名称词汇。")
        return

    try:
        from wordcloud import WordCloud  # type: ignore

        font_path = get_font_path()

        base_wc_kwargs: dict[str, object] = {
            "width": 2600,
            "height": 1200,
            "max_words": 260,
            "background_color": "#FFFFFF",
            "mode": "RGB",
            "color_func": ancient_theme_color_func,
            "prefer_horizontal": 0.82,
            "random_state": 42,
            "margin": 1,
            "contour_width": 0,
            "scale": 3,
            "min_font_size": 8,
            "max_font_size": 220,
            "collocations": False,
            "repeat": False,
        }
        if font_path:
            base_wc_kwargs["font_path"] = font_path

        mask = build_wordcloud_mask(shape="tower", width=2600, height=1200)

        wc = WordCloud(mask=mask, relative_scaling=0.32, **base_wc_kwargs)
        try:
            wc.generate_from_frequencies(frequencies)
        except Exception:
            # 兜底：塔型失败时回退到简化桥形，保证可见
            fallback_mask = build_wordcloud_mask(shape="river_bridge", width=2600, height=1200)
            wc = WordCloud(mask=fallback_mask, **base_wc_kwargs)
            wc.generate_from_frequencies(frequencies)
        wc_img = Image.fromarray(wc.to_array())
        # 轻度锐化，降低词云字体在页面缩放后的发糊感
        wc_img = wc_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=220, threshold=2))
        # 固定显示宽度，避免容器拉伸插值导致模糊
        st.image(wc_img, width=1200)
    except Exception as e:
        st.warning(f"词云生成失败：{e}")


def ancient_theme_color_func(
    word: str,
    font_size: int,
    position: tuple[int, int],
    orientation: int,
    random_state: Optional[object] = None,
    **kwargs: object,
) -> str:
    """词云配色：与侧边栏统一的棕金新中式色板。"""
    palette = [
        "#5C2F16",  # 深棕
        "#7A3D17",  # 主题棕
        "#8B4513",  # 马鞍棕
        "#A35A22",  # 橙棕
        "#B87333",  # 铜色
        "#C08A52",  # 金棕
        "#D2A56F",  # 浅金棕
        "#6B4B35",  # 灰棕
    ]
    try:
        if random_state is not None and hasattr(random_state, "randrange"):
            idx = int(random_state.randrange(len(palette)))
        else:
            idx = random.randrange(len(palette))
        return palette[idx]
    except Exception:
        # 保险兜底：任何异常都回退到主题主色
        return "#7A3D17"


def build_wordcloud_mask(shape: str, width: int, height: int) -> np.ndarray:
    """构建词云形状蒙版：china_map / jiangnan_bridge / tower / bridge / river_bridge。"""
    img = Image.new("L", (width, height), 255)  # 白色=屏蔽区
    draw = ImageDraw.Draw(img)

    if shape == "china_map":
        # 使用项目内现有中国省份 GeoJSON，栅格化为词云蒙版
        try:
            geojson = load_china_province_geojson()
            features = geojson.get("features", [])

            all_lons: list[float] = []
            all_lats: list[float] = []
            for feature in features:
                geometry = feature.get("geometry", {})
                gtype = geometry.get("type")
                coords = geometry.get("coordinates", [])

                polygons = []
                if gtype == "Polygon":
                    polygons = [coords]
                elif gtype == "MultiPolygon":
                    polygons = coords

                for polygon in polygons:
                    for ring in polygon:
                        for point in ring:
                            if len(point) >= 2:
                                all_lons.append(float(point[0]))
                                all_lats.append(float(point[1]))

            if not all_lons or not all_lats:
                raise ValueError("GeoJSON 坐标为空")

            min_lon, max_lon = min(all_lons), max(all_lons)
            min_lat, max_lat = min(all_lats), max(all_lats)

            # 留少量边距，避免轮廓贴边
            x_pad = width * 0.02
            y_pad = height * 0.04

            def project(lon: float, lat: float) -> tuple[int, int]:
                x = x_pad + (lon - min_lon) / (max_lon - min_lon) * (width - 2 * x_pad)
                # 图像坐标 y 轴向下，纬度需翻转
                y = y_pad + (max_lat - lat) / (max_lat - min_lat) * (height - 2 * y_pad)
                return int(x), int(y)

            for feature in features:
                geometry = feature.get("geometry", {})
                gtype = geometry.get("type")
                coords = geometry.get("coordinates", [])

                polygons = []
                if gtype == "Polygon":
                    polygons = [coords]
                elif gtype == "MultiPolygon":
                    polygons = coords

                for polygon in polygons:
                    if not polygon:
                        continue
                    # 仅绘制外环即可形成可用轮廓
                    outer_ring = polygon[0]
                    points = [project(float(p[0]), float(p[1])) for p in outer_ring if len(p) >= 2]
                    if len(points) >= 3:
                        draw.polygon(points, fill=0)

            return np.array(img)
        except Exception:
            # 失败时回退到河桥造型，确保页面可渲染
            return build_wordcloud_mask("river_bridge", width, height)

    elif shape == "jiangnan_bridge":
        # 参考“江南水乡线稿”：屋檐 + 石拱桥 + 水波 + 小舟
        # 连绵屋檐（上方主轮廓）
        draw.polygon(
            [
                (int(width * 0.08), int(height * 0.34)),
                (int(width * 0.23), int(height * 0.20)),
                (int(width * 0.34), int(height * 0.30)),
                (int(width * 0.49), int(height * 0.22)),
                (int(width * 0.62), int(height * 0.31)),
                (int(width * 0.76), int(height * 0.24)),
                (int(width * 0.90), int(height * 0.36)),
                (int(width * 0.90), int(height * 0.44)),
                (int(width * 0.08), int(height * 0.44)),
            ],
            fill=0,
        )
        # 左侧房屋主体
        draw.polygon(
            [
                (int(width * 0.04), int(height * 0.56)),
                (int(width * 0.16), int(height * 0.44)),
                (int(width * 0.28), int(height * 0.56)),
                (int(width * 0.28), int(height * 0.67)),
                (int(width * 0.04), int(height * 0.67)),
            ],
            fill=0,
        )
        # 石拱桥桥面
        draw.rounded_rectangle(
            [int(width * 0.30), int(height * 0.49), int(width * 0.86), int(height * 0.62)],
            radius=30,
            fill=0,
        )
        # 拱桥桥孔（挖空）
        arch_hole = [
            int(width * 0.44),
            int(height * 0.52),
            int(width * 0.72),
            int(height * 0.88),
        ]
        draw.pieslice(arch_hole, start=180, end=360, fill=255)
        # 桥孔下沿回补一点厚度，保持石拱视觉
        draw.rectangle(
            [int(width * 0.43), int(height * 0.62), int(width * 0.73), int(height * 0.69)],
            fill=0,
        )
        # 水波（下方两条带状轮廓）
        draw.rounded_rectangle(
            [int(width * 0.06), int(height * 0.74), int(width * 0.52), int(height * 0.83)],
            radius=34,
            fill=0,
        )
        draw.rounded_rectangle(
            [int(width * 0.02), int(height * 0.80), int(width * 0.40), int(height * 0.90)],
            radius=40,
            fill=0,
        )
        # 小舟
        draw.polygon(
            [
                (int(width * 0.62), int(height * 0.84)),
                (int(width * 0.78), int(height * 0.84)),
                (int(width * 0.74), int(height * 0.89)),
                (int(width * 0.58), int(height * 0.89)),
            ],
            fill=0,
        )
        # 日轮（小圆点缀）
        draw.ellipse(
            [int(width * 0.66), int(height * 0.06), int(width * 0.72), int(height * 0.14)],
            fill=0,
        )

    elif shape == "tower":
        # 塔基（梯形）
        draw.polygon(
            [
                (int(width * 0.24), int(height * 0.9)),
                (int(width * 0.76), int(height * 0.9)),
                (int(width * 0.67), int(height * 0.72)),
                (int(width * 0.33), int(height * 0.72)),
            ],
            fill=0,
        )
        # 塔身分层
        draw.rectangle([int(width * 0.36), int(height * 0.28), int(width * 0.64), int(height * 0.72)], fill=0)
        draw.rectangle([int(width * 0.39), int(height * 0.18), int(width * 0.61), int(height * 0.28)], fill=0)
        draw.polygon(
            [
                (int(width * 0.5), int(height * 0.06)),
                (int(width * 0.68), int(height * 0.18)),
                (int(width * 0.32), int(height * 0.18)),
            ],
            fill=0,
        )

    elif shape == "bridge":
        # 强识别石拱桥：厚桥面 + 单孔大拱 + 左右桥台 + 基座
        # 桥面主体（占画面核心区域，保证一眼识别）
        draw.rounded_rectangle(
            [int(width * 0.05), int(height * 0.26), int(width * 0.95), int(height * 0.56)],
            radius=72,
            fill=0,
        )
        # 护栏上沿（强化“桥”而非普通拱形）
        draw.rounded_rectangle(
            [int(width * 0.12), int(height * 0.18), int(width * 0.88), int(height * 0.28)],
            radius=38,
            fill=0,
        )
        # 左右桥台（石拱桥典型支撑）
        draw.rectangle([int(width * 0.05), int(height * 0.46), int(width * 0.25), int(height * 0.78)], fill=0)
        draw.rectangle([int(width * 0.75), int(height * 0.46), int(width * 0.95), int(height * 0.78)], fill=0)

        # 单孔主拱（挖空，形成石拱桥核心视觉）
        main_hole = [
            int(width * 0.23),
            int(height * 0.34),
            int(width * 0.77),
            int(height * 1.02),
        ]
        draw.pieslice(main_hole, start=180, end=360, fill=255)

        # 桥基石带（承托感）
        draw.rounded_rectangle(
            [int(width * 0.03), int(height * 0.66), int(width * 0.97), int(height * 0.84)],
            radius=34,
            fill=0,
        )

        # 桥栏节奏（少量开窗，避免太碎）
        for x_ratio in [0.24, 0.36, 0.50, 0.64, 0.76]:
            cx = int(width * x_ratio)
            draw.rectangle([cx - 24, int(height * 0.28), cx + 24, int(height * 0.40)], fill=255)

    else:
        # river_bridge: 长河 + 拱桥（默认）
        # 长河（弯带）
        river_poly = [
            (int(width * 0.02), int(height * 0.78)),
            (int(width * 0.16), int(height * 0.72)),
            (int(width * 0.3), int(height * 0.75)),
            (int(width * 0.46), int(height * 0.69)),
            (int(width * 0.62), int(height * 0.73)),
            (int(width * 0.8), int(height * 0.68)),
            (int(width * 0.98), int(height * 0.73)),
            (int(width * 0.98), int(height * 0.96)),
            (int(width * 0.78), int(height * 0.92)),
            (int(width * 0.62), int(height * 0.95)),
            (int(width * 0.46), int(height * 0.9)),
            (int(width * 0.3), int(height * 0.95)),
            (int(width * 0.14), int(height * 0.9)),
            (int(width * 0.02), int(height * 0.94)),
        ]
        draw.polygon(river_poly, fill=0)

        # 桥面
        draw.rounded_rectangle(
            [int(width * 0.18), int(height * 0.3), int(width * 0.82), int(height * 0.44)],
            radius=28,
            fill=0,
        )
        # 桥拱（挖空）
        bridge_holes = [(0.37, 0.11), (0.5, 0.12), (0.63, 0.11)]
        for cx, hw in bridge_holes:
            hole = [
                int(width * (cx - hw)),
                int(height * 0.4),
                int(width * (cx + hw)),
                int(height * 0.86),
            ]
            draw.pieslice(hole, start=180, end=360, fill=255)

    return np.array(img)


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


def build_full_scored_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """构建完整评分榜（按综合评分降序）。"""
    if df.empty:
        return pd.DataFrame(columns=["排名", "建筑名称", "朝代", "省份", "星级", "综合评分"])

    ranking_df = df.copy()
    ranking_df["综合评分"] = ranking_df.apply(calculate_building_score, axis=1)
    ranking_df["星级"] = ranking_df["综合评分"].apply(get_star_rating)
    ranking_df["朝代"] = ranking_df["时代（中文）"].apply(get_era_label) if "时代（中文）" in ranking_df.columns else "其他"
    ranking_df = ranking_df.sort_values(by="综合评分", ascending=False).reset_index(drop=True)
    ranking_df.insert(0, "排名", range(1, len(ranking_df) + 1))
    return ranking_df


@st.cache_data(show_spinner=False, ttl=3600)
def generate_ai_card_hint_with_deepseek(
    building_name: str,
    era: str,
    batch: str,
    province: str,
    city: str,
    district: str,
    category: str,
    score: float,
    stars: str,
) -> str:
    """调用 DeepSeek 生成卡片一行解析（简短版）。"""
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    region = " / ".join([x for x in [province, city, district] if x]) or "地区信息待补充"
    system_prompt = "你是古建筑评分助手。只输出一行中文短句（不超过18字），说明该建筑评分靠前原因。禁止换行、禁止编号。"
    user_prompt = (
        f"建筑：{building_name}\n地区：{region}\n时代：{era}\n类别：{category}\n"
        f"保护批次：{batch}\n评分：{score:.1f}（{stars}）\n"
        "请输出一句原因说明。"
    )
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
            "max_tokens": 80,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    text = str(content).replace("\n", " ").strip(" 。")
    if not text:
        raise RuntimeError("DeepSeek 返回内容为空")
    return text[:24]


def build_rule_based_card_hint(row: pd.Series) -> str:
    """基于评分维度生成一行预设解析。"""
    dims = calculate_building_dimensions(row)
    if dims.get("保护级别", 0) >= 85:
        return "国家级重点保护单位"
    if dims.get("年代久远度", 0) >= 85:
        return "始建于唐宋，历史悠久"
    if dims.get("建筑稀有性", 0) >= 85:
        return "建筑类型罕见，研究价值高"
    if dims.get("历史价值", 0) >= 85:
        return "见证重要历史事件"
    return "年代久远，保护级别高"


def get_card_ai_hint(row: pd.Series) -> str:
    """获取卡片一行解析：优先 DeepSeek，失败回退规则文案。"""
    name_raw = str(row.get("单位名称（中文）", "该古建筑")).strip() or "该古建筑"
    era_raw = str(row.get("时代（中文）", "")).strip() or str(row.get("朝代", "其他"))
    batch_raw = str(row.get("批次（中文）", "")).strip() or "未标注批次"
    prov_raw = str(row.get("省级政区名称（中文）", "")).strip()
    city_raw = str(row.get("市级政区名称（中文）", "")).strip()
    dist_raw = str(row.get("县级政区名称（中文）", "")).strip()
    score_raw = float(row.get("综合评分", 0))
    stars = str(row.get("星级", "⭐"))
    category_raw = classify_building_category(name_raw)
    try:
        return generate_ai_card_hint_with_deepseek(
            building_name=name_raw,
            era=era_raw,
            batch=batch_raw,
            province=prov_raw,
            city=city_raw,
            district=dist_raw,
            category=category_raw,
            score=score_raw,
            stars=stars,
        )
    except Exception:
        return build_rule_based_card_hint(row)


def render_ranking_cards(
    ranking_df: pd.DataFrame,
    cards_per_row: int = 5,
    limit: Optional[int] = None,
    show_ai_hint: bool = False,
    enable_click_dialog: bool = False,
    click_query_param: str = "dialog_rank",
    click_keep_detail_page: bool = False,
    direct_open_dialog: bool = False,
) -> None:
    """渲染评分榜卡片（统一卡片样式，可复用在总览和详情页）。"""
    if ranking_df.empty:
        st.info("当前筛选条件下暂无可用于评分排行的古建筑数据。")
        return

    display_df = ranking_df.head(limit).copy() if limit is not None else ranking_df.copy()
    total = len(display_df)

    # 中文注释：按每行列数循环渲染卡片，保持统一视觉样式
    for start in range(0, total, cards_per_row):
        cols = st.columns(cards_per_row)
        for offset in range(cards_per_row):
            idx = start + offset
            with cols[offset]:
                if idx >= total:
                    st.empty()
                    continue
                row = display_df.iloc[idx]
                rank = int(row.get("排名", idx + 1))
                name = str(row.get("单位名称（中文）", "未知古建")).strip() or "未知古建"
                era = str(row.get("朝代", "其他")).strip() or "其他"
                province = str(row.get("省级政区名称（中文）", "未知省份")).strip() or "未知省份"
                stars = str(row.get("星级", "⭐"))
                ai_hint_html = ""
                if show_ai_hint:
                    # 中文注释：调用共用解析函数，避免重复 AI/规则逻辑
                    row_series = row if isinstance(row, pd.Series) else pd.Series(row)
                    ai_hint = get_card_ai_hint(row_series)

                    ai_hint_html = (
                        f'<div style="margin-top:8px; font-size:12px; color:#6B4B35; '
                        f'font-style:italic; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                        f'AI解析：{ai_hint}</div>'
                    )

                # 中文注释：可选的“整卡可点击”能力（用于详情页点击弹窗）
                rank_for_click = int(row.get("排名", idx + 1))
                card_open = ""
                card_close = ""
                if enable_click_dialog and not direct_open_dialog:
                    # 中文注释：详情页点击卡片时保留 view_detail_page=1，避免刷新后跳回总览
                    prefix = "view_detail_page=1&" if click_keep_detail_page else ""
                    card_open = (
                        f'<a href="?{prefix}{click_query_param}={rank_for_click}" '
                        f'style="text-decoration:none; color:inherit;">'
                    )
                    card_close = "</a>"
                if direct_open_dialog and enable_click_dialog:
                    # 中文注释：详情页“直接弹窗”模式——使用原生按钮触发弹窗（不改 URL、不跳转）
                    btn_label = (
                        f"第{rank}名\n"
                        f"{name}\n"
                        f"朝代：{era}\n"
                        f"省份：{province}\n"
                        f"星级：{stars}"
                    )
                    if st.button(btn_label, key=f"detail_card_click_{rank_for_click}", use_container_width=True):
                        st.session_state["show_building_dialog"] = True
                        st.session_state["active_building_dialog_row"] = row.to_dict()
                else:
                    st.markdown(
                        f"""
                        {card_open}
                        <div style="
                            background:#FAF0E6;
                            border:1px solid #DEB887;
                            border-radius:12px;
                            padding:16px;
                            margin-top:8px;
                            margin-bottom:20px;
                            min-height:180px;
                            color:#4A3728;
                            cursor:{'pointer' if enable_click_dialog else 'default'};
                        ">
            <div style="font-weight:700; color:#8B4513; margin-bottom:8px; text-align:center;">第{rank}名</div>
                            <div style="font-weight:800; color:#8B4513; margin-bottom:8px; line-height:1.4;">{name}</div>
                            <div style="margin-bottom:6px;">朝代：{era}</div>
                            <div style="margin-bottom:6px;">省份：{province}</div>
                            <div style="margin-bottom:6px;">星级：{stars}</div>
                            {ai_hint_html}
                        </div>
                        {card_close}
                        """,
                        unsafe_allow_html=True,
                    )


def render_top_treasure_cards(df: pd.DataFrame, top_n: int = 5) -> None:
    """渲染“国家宝藏·顶级古建评分榜”卡片模块。"""
    st.markdown(
        """
        <div style="
            text-align:center;
            font-size:18px;
            color:#8B4513;
            font-weight:bold;
            margin: 10px 0 10px 0;
        ">
            <span style="
                display:inline-flex;
                align-items:center;
                justify-content:center;
                min-width:38px;
                height:24px;
                border:1px solid rgba(139,69,19,.35);
                border-radius:6px;
                font-size:13px;
                font-weight:800;
                color:#8B4513;
                margin-right:8px;
                background:rgba(139,69,19,.06);
            ">国藏</span>国家宝藏 · 顶级古建评分榜（Top 5）
        </div>
        """,
        unsafe_allow_html=True,
    )

    ranking_df = build_full_scored_ranking(df)
    top_df = ranking_df.head(top_n).copy()
    if top_df.empty:
        st.info("当前筛选条件下暂无可用于评分排行的古建筑数据。")
        return

    # 中文注释：点击整张卡片后，通过查询参数触发同一详情弹窗（复用地图探索页弹窗逻辑）
    clicked_idx_raw = str(st.query_params.get("treasure_card_idx", "")).strip()
    if clicked_idx_raw.isdigit():
        clicked_idx = int(clicked_idx_raw)
        if 0 <= clicked_idx < len(top_df):
            st.session_state["show_building_dialog"] = True
            st.session_state["active_building_dialog_row"] = top_df.iloc[clicked_idx].to_dict()
        try:
            del st.query_params["treasure_card_idx"]
        except Exception:
            pass

    cols = st.columns(5)
    for idx in range(5):
        with cols[idx]:
            if idx >= len(top_df):
                st.empty()
                continue
            row = top_df.iloc[idx]
            rank = int(row.get("排名", idx + 1))
            name = str(row.get("单位名称（中文）", "未知古建")).strip() or "未知古建"
            era = str(row.get("朝代", "其他")).strip() or "其他"
            province = str(row.get("省级政区名称（中文）", "未知省份")).strip() or "未知省份"
            stars = str(row.get("星级", "⭐"))

            btn_label = (
                f"第{rank}名\n"
                f"{name}\n"
                f"朝代：{era}\n"
                f"省份：{province}\n"
                f"星级：{stars}"
            )
            if st.button(btn_label, key=f"top_treasure_card_{idx}", use_container_width=True):
                st.session_state["show_building_dialog"] = True
                st.session_state["active_building_dialog_row"] = row.to_dict()

    # 中文注释：使用 Markdown + HTML 渲染纯文字“查看更多”，放在卡片模块外部右下角
    st.markdown(
        """
        <style>
        .treasure-more-wrap{
            display:flex;
            justify-content:flex-end;
            margin-top:8px;
        }
        .treasure-more-link{
            text-decoration:none;
            color:#8B4513;
            font-size:14px;
            line-height:1.2;
        }
        .treasure-more-link:hover{
            text-decoration:underline;
        }
        </style>
        <div class="treasure-more-wrap">
            <a class="treasure-more-link" href="?view_detail_page=1">查看更多 →</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_treasure_detail_page(df: pd.DataFrame) -> None:
    """渲染全国古建筑综合评分排行榜详情页。"""
    # 中文注释：左上角纯文字“返回总览”，与“查看更多”样式保持对称
    st.markdown(
        """
        <style>
        .treasure-back-wrap{
            display:flex;
            justify-content:flex-start;
            margin-top:2px;
            margin-bottom:4px;
        }
        .treasure-back-link{
            text-decoration:none;
            color:#8B4513;
            font-size:14px;
            line-height:1.2;
        }
        .treasure-back-link:hover{
            text-decoration:underline;
        }
        </style>
        <div class="treasure-back-wrap">
            <a class="treasure-back-link" href="?view_detail_page=0">← 返回总览</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="text-align:center; margin: 6px 0 4px 0;">
            <div style="font-size:30px; font-weight:900; color:#8B4513;">
                <span style="
                    display:inline-flex;
                    align-items:center;
                    justify-content:center;
                    min-width:42px;
                    height:28px;
                    border:1px solid rgba(139,69,19,.35);
                    border-radius:7px;
                    font-size:14px;
                    font-weight:800;
                    color:#8B4513;
                    margin-right:10px;
                    background:rgba(139,69,19,.06);
                    vertical-align:middle;
                ">总榜</span>全国古建筑综合评分排行榜
            </div>
            <div style="font-size:14px; color:#4A3728; margin-top:6px;">
                基于保护级别、年代久远、稀有性、历史价值的综合评估
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ranking_df = build_full_scored_ranking(df)
    if ranking_df.empty:
        st.info("当前筛选条件下暂无可用于评分排行的古建筑数据。")
        return

    # 中文注释：详情页卡片点击采用“直接弹窗”，不依赖 URL 参数

    # 中文注释：详情页分页参数（每页 12 张卡片，即每行 4 张共 3 行）
    page_size = 12
    total_items = len(ranking_df)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    current_page = int(st.session_state.get("treasure_detail_page_index", 1))
    current_page = min(max(current_page, 1), total_pages)
    st.session_state["treasure_detail_page_index"] = current_page

    page_col1, page_col2, page_col3 = st.columns([1.2, 2.2, 1.6])
    with page_col1:
        st.caption(f"共 {total_items} 条")
    with page_col2:
        # 中文注释：通过下拉页码实现分页切换，避免超长页面
        selected_page = st.selectbox(
            "页码",
            options=list(range(1, total_pages + 1)),
            index=current_page - 1,
            key="treasure_detail_page_select",
            label_visibility="collapsed",
        )
        if int(selected_page) != current_page:
            st.session_state["treasure_detail_page_index"] = int(selected_page)
            st.rerun()
    with page_col3:
        st.caption(f"第 {current_page} / {total_pages} 页")

    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    page_df = ranking_df.iloc[start_idx:end_idx].copy()

    # 中文注释：详情页卡片按钮样式（仅作用于当前“卡片区”，尽量贴近原卡片视觉）
    st.markdown(
        """
        <div class="aa-detail-card-scope"></div>
        <style>
        /* 作用域：仅命中包含 .aa-detail-card-scope 的容器内按钮 */
        div:has(> .aa-detail-card-scope) div[data-testid="stButton"] > button{
            width:100% !important;
            background:#FAF0E6 !important;
            border:1px solid #DEB887 !important;
            border-radius:12px !important;
            padding:16px !important;
            margin-top:8px !important;
            margin-bottom:20px !important;
            min-height:180px !important;
            color:#4A3728 !important;
            text-align:left !important;
            white-space:pre-line !important;
            line-height:1.5 !important;
            font-weight:700 !important;
            box-shadow: 0 8px 20px rgba(44,22,10,.07) !important;
            cursor:pointer !important;
            /* 中文注释：强制卡片内所有文字左对齐 */
            justify-content:flex-start !important;
            align-items:flex-start !important;
        }
        div:has(> .aa-detail-card-scope) div[data-testid="stButton"] > button *{
            text-align:left !important;
            justify-content:flex-start !important;
            align-items:flex-start !important;
        }
        div:has(> .aa-detail-card-scope) div[data-testid="stButton"] > button:hover{
            border-color: rgba(139,69,19,0.35) !important;
            box-shadow: 0 10px 24px rgba(44,22,10,.1) !important;
            transform: translateY(-1px);
        }
        div:has(> .aa-detail-card-scope) div[data-testid="stButton"] > button:focus,
        div:has(> .aa-detail-card-scope) div[data-testid="stButton"] > button:focus-visible{
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(139,69,19,.2) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 中文注释：详情页采用每行 4 张卡片展示当前页榜单（外观保持不变，点击直接弹窗）
    render_ranking_cards(
        page_df,
        cards_per_row=4,
        limit=None,
        enable_click_dialog=True,
        direct_open_dialog=True,
    )
    # 中文注释：在卡片区域底部增加留白，避免页面视觉过于拥挤
    st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)


def render_dashboard(filtered_df: pd.DataFrame) -> None:
    """渲染总览仪表板视图。"""
    # 省份详情/总览状态
    if "dashboard_selected_province" not in st.session_state:
        st.session_state["dashboard_selected_province"] = None
    if "dashboard_map_reset_token" not in st.session_state:
        st.session_state["dashboard_map_reset_token"] = 0
    if "view_detail_page" not in st.session_state:
        st.session_state["view_detail_page"] = False

    # 中文注释：接收“查看更多”链接参数并同步到 session_state
    qp_view_detail = str(st.query_params.get("view_detail_page", "")).strip().lower()
    if qp_view_detail in {"1", "true", "yes"}:
        st.session_state["view_detail_page"] = True
        st.session_state["treasure_detail_page_index"] = 1
        try:
            del st.query_params["view_detail_page"]
        except Exception:
            pass
    elif qp_view_detail in {"0", "false", "no"}:
        st.session_state["view_detail_page"] = False
        try:
            del st.query_params["view_detail_page"]
        except Exception:
            pass

    selected_dashboard_province = st.session_state.get("dashboard_selected_province")
    view_detail_page = bool(st.session_state.get("view_detail_page", False))

    # 中文注释：切换到评分榜详情页时，直接渲染详情并结束当前总览渲染
    if view_detail_page:
        render_treasure_detail_page(filtered_df)
        return

    # 仅总览页展示左上角项目标题；详情页不显示
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

    # 顶部KPI：仅总览显示（省份详情页隐藏）
    if not selected_dashboard_province:
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
        height=470,
        showlegend=False,
        coloraxis_showscale=False,  # 不显示图例
        # 把地图绘制区域压满画布，避免顶部留白
        geo=dict(
            fitbounds="locations",
            visible=False,
            domain=dict(x=[0, 1], y=[0, 1]),
            center=dict(lat=37, lon=105),
            projection=dict(scale=1.62),
            bgcolor="#F7F2EA",
        ),
        autosize=False,
        paper_bgcolor="#F7F2EA",
        plot_bgcolor="#F7F2EA",
        margin=dict(l=0, r=0, t=0, b=0, pad=0),  # 去掉所有边距与内边距
        # 关闭拖拽缩放，优先支持单击选中省份
        dragmode=False,
    )

    # 左右列表：不启用任何内部滚动（避免出现滑动条）
    # 通过限制展示条目数量 + 紧凑样式，保证布局稳定
    left_html = [
        "<div style='display:flex; flex-direction:column; padding-right:6px;'>",
        "<h4 style='font-size:clamp(14px,1.15vw,18px); margin-bottom:10px; white-space:nowrap; line-height:1.2; text-align:center; color:#8B4513; font-weight:bold;'>"
        "<span style='display:inline-flex; align-items:center; justify-content:center; min-width:34px; height:22px; border:1px solid rgba(139,69,19,.35); border-radius:6px; font-size:12px; font-weight:800; color:#8B4513; margin-right:8px; background:rgba(139,69,19,.06);'>省榜</span>古建筑数量省份排名</h4>",
        "<div style='flex:1;'>",
    ]
    for i, (prov, cnt) in enumerate(province_counts.sort_values(ascending=False).items(), start=1):
        if i > 8:  # 只展示 Top 8（避免撑出内部滚动条）
            break
        left_html.append(
            "<div style='color:#4A3728; margin:6px 0; padding:6px 8px; border-radius:10px; background:rgba(139,69,19,0.06); font-size:14px;'>"
            f"<span style='font-weight:800; color:#8B4513; width:24px; display:inline-block;'>{i}</span>"
            f"{prov}：<span style='font-weight:800; color:#8B4513;'>{int(cnt)}</span>座</div>"
        )
    left_html.append("</div></div>")

    right_html = [
        "<div style='display:flex; flex-direction:column; padding-left:6px;'>",
        "<h4 style='font-size:clamp(14px,1.15vw,18px); margin-bottom:10px; white-space:nowrap; line-height:1.2; text-align:center; color:#8B4513; font-weight:bold;'>"
        "<span style='display:inline-flex; align-items:center; justify-content:center; min-width:34px; height:22px; border:1px solid rgba(139,69,19,.35); border-radius:6px; font-size:12px; font-weight:800; color:#8B4513; margin-right:8px; background:rgba(139,69,19,.06);'>朝榜</span>古建筑数量朝代排名</h4>",
        "<div style='flex:1;'>",
    ]
    right_order = [e for e in era_major] + (["其他"] if int(era_counts.get("其他", 0)) > 0 else [])
    for i, e in enumerate(right_order, start=1):
        cnt = int(era_counts.get(e, 0))
        right_html.append(
            "<div style='color:#4A3728; margin:6px 0; padding:6px 8px; border-radius:10px; background:rgba(160,82,45,0.06); font-size:14px;'>"
            f"<span style='font-weight:800; color:#A0522D; width:24px; display:inline-block;'>{i}</span>"
            f"{e}：<span style='font-weight:800; color:#A0522D;'>{cnt}</span>座</div>"
        )
    right_html.append("</div></div>")

    if selected_dashboard_province:
        st.markdown(
            """
            <style>
            /* 中文注释：省份详情页“返回总览”按钮改为更协调的横向卡片按钮 */
            div:has(> .aa-dashboard-back-scope) div[data-testid="stButton"] > button{
                min-height: 38px !important;
                height: 38px !important;
                border-radius: 10px !important;
                padding: 0 10px !important;
                font-size: 0.88rem !important;
                font-weight: 700 !important;
                white-space: nowrap !important;
                line-height: 1 !important;
                justify-content: center !important;
                align-items: center !important;
            }
            </style>
            <div class="aa-dashboard-back-scope"></div>
            """,
            unsafe_allow_html=True,
        )
        back_col, _ = st.columns([1.5, 8.5])
        with back_col:
            st.button(
                "← 返回总览",
                on_click=clear_dashboard_selected_province,
                use_container_width=True,
            )
        col_map, col_table = st.columns([2, 3])
        with col_map:
            clicked_province = st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"dashboard_map_detail_{selected_dashboard_province}_{st.session_state['dashboard_map_reset_token']}",
                on_select="rerun",
                config={"scrollZoom": True, "displayModeBar": False},
                selection_mode=("points",),
            )
            if clicked_province and clicked_province.selection:
                points = clicked_province.selection.points
                if points:
                    province_name = points[0].get("location")
                    if province_name:
                        current_selected = st.session_state.get("dashboard_selected_province")
                        if province_name != current_selected:
                            st.session_state["dashboard_selected_province"] = province_name
                            st.rerun()

        with col_table:
            province_df = filtered_df[
                filtered_df[province_col].fillna("").astype(str).apply(normalize_province_name) == selected_dashboard_province
            ].copy()
            st.subheader(f"{selected_dashboard_province} · 古建筑评分排名")
            province_ranking_df = build_scored_ranking_table(province_df, top_n=20, include_region=True)
            st.markdown(
                """
                <style>
                /* 中文注释：仅调整 DataFrame 主题样式，不改变原有组件渲染方式 */
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"]{
                    border:1px solid rgba(139,69,19,.22) !important;
                    border-radius:16px !important;
                    overflow:hidden !important;
                    box-shadow:0 10px 24px rgba(44,22,10,.10) !important;
                    background:linear-gradient(180deg, rgba(255,255,255,.64) 0%, rgba(250,240,230,.52) 100%) !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] thead th{
                    background:linear-gradient(180deg, rgba(139,69,19,.16) 0%, rgba(139,69,19,.10) 100%) !important;
                    color:#5E341A !important;
                    font-weight:800 !important;
                    letter-spacing:.02em !important;
                    border-bottom:1px solid rgba(139,69,19,.22) !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] tbody td{
                    color:#4A3728 !important;
                    border-bottom:1px solid rgba(139,69,19,.10) !important;
                    font-size:14px !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] tbody tr td:first-child{
                    color:#7A3D17 !important;
                    font-weight:800 !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] tbody tr:nth-child(even) td{
                    background:rgba(250,240,230,.66) !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] tbody tr:nth-child(odd) td{
                    background:rgba(255,255,255,.42) !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] tbody tr:hover td{
                    background:rgba(222,184,135,.34) !important;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] [data-testid="stHorizontalBlock"],
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] [data-testid="stVerticalBlock"]{
                    scrollbar-width: thin;
                    scrollbar-color: rgba(139,69,19,.45) rgba(245,236,225,.55);
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] ::-webkit-scrollbar{
                    height: 10px;
                    width: 10px;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb{
                    background: rgba(139,69,19,.45);
                    border-radius: 999px;
                }
                div:has(> .aa-ranking-scope) [data-testid="stDataFrame"] ::-webkit-scrollbar-track{
                    background: rgba(245,236,225,.55);
                }
                </style>
                <div class="aa-ranking-scope"></div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(province_ranking_df, use_container_width=True, hide_index=True)
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
                key=f"dashboard_map_{st.session_state['dashboard_map_reset_token']}",
                on_select="rerun",
                config={"scrollZoom": True, "displayModeBar": False},
                selection_mode=("points",),
            )
            if clicked_province and clicked_province.selection:
                points = clicked_province.selection.points
                if points:
                    province_name = points[0].get("location")
                    if province_name:
                        current_selected = st.session_state.get("dashboard_selected_province")
                        if province_name != current_selected:
                            st.session_state["dashboard_selected_province"] = province_name
                            st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col_right:
            st.markdown("".join(right_html), unsafe_allow_html=True)

    # 第三行（插入）：国家宝藏 Top5 评分榜（仅在总览时渲染）
    if not selected_dashboard_province:
        render_top_treasure_cards(filtered_df, top_n=5)

    # 第四行（插入）：建筑名称词云（仅在总览时渲染；省份详情页跳过以提升流畅度）
    if not selected_dashboard_province:
        # 中文注释：点击卡片准备弹窗时，跳过词云重渲染，优先提升“点卡即弹窗”响应速度
        if not st.session_state.get("_opening_dialog_now", False):
            render_name_word_cloud(filtered_df)


def render_map_view(filtered_df: pd.DataFrame, selected_province: str) -> None:
    """渲染地图探索视图。"""
    st.markdown(
        f"""
        <div class="aa-card">
            <div class="aa-card-title">地图探索</div>
            <div style="font-size:28px; font-weight:900; letter-spacing:.02em;">古建筑空间分布</div>
            <div class="aa-hint">当前筛选：<b>{len(filtered_df)}</b> 条 · 点击省份查看该省评分排名</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
        height=460,
        showlegend=False,
        coloraxis_showscale=False,
        geo=dict(
            fitbounds="locations",
            visible=False,
            domain=dict(x=[0, 1], y=[0, 1]),
            center=dict(lat=35, lon=105),
            projection=dict(scale=2.05),
            bgcolor="#F7F2EA",
        ),
        autosize=False,
        paper_bgcolor="#F7F2EA",
        plot_bgcolor="#F7F2EA",
        margin=dict(l=0, r=0, t=0, b=0, pad=0),
        # 关闭拖拽缩放，优先支持单击选中省份
        dragmode=False,
        clickmode="event+select",
    )

    col_map, col_table = st.columns([2, 3], gap="large")
    if "map_selection_reset_token" not in st.session_state:
        st.session_state["map_selection_reset_token"] = 0

    with col_map:
        st.markdown("<div class='aa-card-title' style='margin-bottom:6px;'>全国热度地图</div>", unsafe_allow_html=True)
        chart_data = st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"china_map_{st.session_state['map_selection_reset_token']}",
            on_select="rerun",
            config={"scrollZoom": True, "displayModeBar": False},
            selection_mode=("points",),
        )
        if chart_data and chart_data.selection and chart_data.selection.points:
            point = chart_data.selection.points[0]
            selected_name = point.get("location")
            if not selected_name and point.get("customdata"):
                selected_name = point["customdata"][0]
            if selected_name:
                current_selected = st.session_state.get("selected_map_province")
                if selected_name != current_selected:
                    st.session_state["selected_map_province"] = selected_name
                    st.rerun()

    with col_table:
        selected_map_province = st.session_state.get("selected_map_province")
        if selected_map_province:
            st.markdown("<div class='aa-card'>", unsafe_allow_html=True)
            province_df = plot_df[plot_df["地图省份"] == selected_map_province].copy()
            st.markdown(f"<div class='aa-card-title'>省份详情</div>", unsafe_allow_html=True)
            st.subheader(f"{selected_map_province} · 古建筑名录")
            st.markdown("#### 古建筑名字卡片")

            # 为地图探索详情补充打分列，便于卡片选择 + 雷达图 + 解说联动
            card_df = province_df.copy()
            if not card_df.empty:
                card_df["综合评分"] = card_df.apply(calculate_building_score, axis=1)
                card_df["星级"] = card_df["综合评分"].apply(get_star_rating)
                card_df = card_df.sort_values(by="综合评分", ascending=False).reset_index(drop=True)

            if card_df.empty:
                st.info("该省暂无可展示的古建筑卡片。")
            else:
                max_cards = min(18, len(card_df))
                cols_per_row = 3
                clicked_row_data: Optional[dict[str, object]] = None
                for start in range(0, max_cards, cols_per_row):
                    row_cols = st.columns(cols_per_row)
                    for offset, c in enumerate(row_cols):
                        idx = start + offset
                        if idx >= max_cards:
                            continue
                        row = card_df.iloc[idx]
                        name = str(row.get("单位名称（中文）", "")).strip() or f"古建筑{idx + 1}"
                        era = get_era_label(str(row.get("时代（中文）", "")))
                        score = float(row.get("综合评分", 0))
                        stars = str(row.get("星级", ""))
                        label = f"{name}\n{era} · {score:.1f}分 {stars}"
                        if c.button(label, key=f"building_card_{selected_map_province}_{idx}", use_container_width=True):
                            clicked_row_data = row.to_dict()

                if clicked_row_data:
                    # 中文注释：通过 session_state 统一打开弹窗，便于弹窗内切换相似建筑
                    st.session_state["show_building_dialog"] = True
                    st.session_state["active_building_dialog_row"] = clicked_row_data
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                """
                <div class="aa-card" style="padding:12px 14px;">
                    <div class="aa-card-title">操作提示</div>
                    <div style="font-size:16px; font-weight:900; margin-bottom:4px;">选择一个省份</div>
                    <div class="aa-hint">在左侧地图单击省份区域，这里会展示该省的评分排名。</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def main() -> None:
    """应用主函数。"""
    df = load_app_data()
    view, selected_province, search_keyword = build_sidebar(df)
    filtered_df = apply_province_filter(df, selected_province)
    filtered_df = apply_name_search_filter(filtered_df, search_keyword)

    pending_dialog_row = None
    if st.session_state.get("show_building_dialog") and st.session_state.get("active_building_dialog_row"):
        pending_dialog_row = st.session_state.get("active_building_dialog_row")
        st.session_state["show_building_dialog"] = False
        st.session_state["_opening_dialog_now"] = True
    else:
        st.session_state["_opening_dialog_now"] = False

    if view == "总览仪表板":
        render_dashboard(filtered_df)
    else:
        render_map_view(filtered_df, selected_province)

    # 中文注释：统一在主流程末尾打开弹窗；并在本轮结束后复位“弹窗提速模式”
    if pending_dialog_row:
        show_building_detail_dialog(pending_dialog_row)
    st.session_state["_opening_dialog_now"] = False


if __name__ == "__main__":
    main()
