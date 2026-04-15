"""数据加载与筛选模块。

本模块用于：
1) 从原始 Excel 读取全国重点文物保护单位数据；
2) 按大赛要求筛选“古建筑”且排除近现代条目；
3) 将筛选结果保存为 UTF-8 编码 CSV；
4) 返回筛选结果的摘要信息，便于页面展示。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# 项目根目录：src/data_loader.py 的上一级是 src，再上一级是项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# 原始 Excel 数据路径（根据你的项目结构固定在 data/raw 下）
RAW_EXCEL_PATH = PROJECT_ROOT / "data" / "raw" / "CulRelPro_China_1961-2019.xls"
# 默认输出 CSV 路径
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "heritage_buildings_raw.csv"

# 业务上需要保留的列（与 Excel 列名保持一致，方便后续映射）
OUTPUT_COLUMNS = [
    "序号",
    "单位名称（中文）",
    "时代（中文）",
    "地址（中文）",
    "类型（中文）",
    "批次（中文）",
    "省级政区名称（中文）",
    "市级政区名称（中文）",
    "县级政区名称（中文）",
]


def _ensure_required_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    """校验 DataFrame 是否包含业务必需列，不满足时抛出明确异常。"""
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise KeyError(f"缺少必要列: {missing_columns}")


@st.cache_data
def load_excel_data() -> pd.DataFrame:
    """加载全国重点文物保护单位原始 Excel 数据。

    功能说明：
    - 从 data/raw/CulRelPro_China_1961-2019.xls 读取数据；
    - 指定 sheet_name='Tab.1'；
    - 使用 pathlib 管理路径；
    - 通过 st.cache_data 缓存，避免重复 I/O；
    - 对文本列做基础清洗，降低乱码/空值导致的后续筛选异常风险。
    """
    if not RAW_EXCEL_PATH.exists():
        raise FileNotFoundError(f"未找到原始 Excel 文件: {RAW_EXCEL_PATH}")

    try:
        # .xls 优先使用 xlrd 引擎读取
        df = pd.read_excel(RAW_EXCEL_PATH, sheet_name="Tab.1", engine="xlrd")
    except Exception:
        # 回退读取：让 pandas 自动选择可用引擎，提升兼容性
        df = pd.read_excel(RAW_EXCEL_PATH, sheet_name="Tab.1")

    # 统一列名与关键文本列的空白，避免“看起来相同但匹配失败”
    df.columns = [str(col).strip() for col in df.columns]
    for text_col in ["类型（中文）", "时代（中文）", "单位名称（中文）", "批次（中文）", "省级政区名称（中文）"]:
        if text_col in df.columns:
            # 先转字符串再清洗，确保后续 str.contains 稳定
            df[text_col] = df[text_col].fillna("").astype(str).str.strip()

    return df


@st.cache_data
def filter_ancient_buildings(df: pd.DataFrame) -> pd.DataFrame:
    """从全国数据中筛选符合大赛要求的古建筑数据。

    筛选条件：
    1) “类型（中文）”必须精确等于“古建筑”；
    2) “时代（中文）”中排除包含：近现代 / 中华民国 / 中华人民共和国；
    3) “时代（中文）”中排除包含 1911 及之后年份（正则识别 1911+）。
    """
    required_columns = ["类型（中文）", "时代（中文）"]
    _ensure_required_columns(df, required_columns)

    # 拷贝后处理，避免在外部 DataFrame 上产生副作用
    result = df.copy()
    result["类型（中文）"] = result["类型（中文）"].fillna("").astype(str).str.strip()
    result["时代（中文）"] = result["时代（中文）"].fillna("").astype(str).str.strip()

    # 条件1：类型精确匹配“古建筑”
    is_ancient_building = result["类型（中文）"] == "古建筑"

    # 条件2：排除特定近现代关键词
    modern_keywords_pattern = r"近现代|中华民国|中华人民共和国"
    contains_modern_keywords = result["时代（中文）"].str.contains(
        modern_keywords_pattern,
        regex=True,
        na=False,
    )

    # 条件3：排除 1911 及之后年份
    # 说明：匹配 1911-1999、2000 及以后常见 4 位年份
    year_1911_plus_pattern = r"(191[1-9]|19[2-9]\d|20\d{2}|21\d{2})"
    contains_1911_plus_year = result["时代（中文）"].str.contains(
        year_1911_plus_pattern,
        regex=True,
        na=False,
    )

    filtered_df = result[is_ancient_building & ~contains_modern_keywords & ~contains_1911_plus_year].copy()
    return filtered_df


def save_filtered_data(df: pd.DataFrame, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> None:
    """将筛选后的数据按指定列保存为 UTF-8 编码 CSV。"""
    _ensure_required_columns(df, OUTPUT_COLUMNS)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 仅输出业务要求列，保证与模板表头一致
    export_df = df.loc[:, OUTPUT_COLUMNS].copy()
    export_df.to_csv(path, index=False, encoding="utf-8")


@st.cache_data
def get_data_summary(df: pd.DataFrame) -> dict[str, Any]:
    """返回筛选后数据摘要统计信息。

    返回字段：
    - total_count: 总记录数
    - province_count: 覆盖省份数
    - batch_list: 涉及批次列表（去重后排序）
    - sample_records: 前5条记录（名称 + 朝代）
    """
    required_columns = ["单位名称（中文）", "时代（中文）", "批次（中文）", "省级政区名称（中文）"]
    _ensure_required_columns(df, required_columns)

    summary_df = df.copy()
    for col in required_columns:
        summary_df[col] = summary_df[col].fillna("").astype(str).str.strip()

    batch_list = sorted([item for item in summary_df["批次（中文）"].unique().tolist() if item])

    sample_records = (
        summary_df.loc[:, ["单位名称（中文）", "时代（中文）"]]
        .head(5)
        .rename(columns={"单位名称（中文）": "name", "时代（中文）": "era"})
        .to_dict(orient="records")
    )

    return {
        "total_count": int(len(summary_df)),
        "province_count": int(summary_df["省级政区名称（中文）"].replace("", pd.NA).nunique(dropna=True)),
        "batch_list": batch_list,
        "sample_records": sample_records,
    }
