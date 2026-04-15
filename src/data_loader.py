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
# 主题筛选结果默认导出路径
DEFAULT_ELIGIBLE_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "eligible_buildings.csv"

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

# 统一的中文字段白名单（用于读取与导出，便于人工核查）
CHINESE_COLUMNS = [
    "序号",
    "编号",
    "分类号",
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

    excel_path = RAW_EXCEL_PATH
    df = pd.read_excel(
        excel_path,
        sheet_name="Tab.1",
        header=3,  # 第4行作为列名（中文）
        skiprows=None,
    )

    # 统一列名与关键文本列的空白，避免“看起来相同但匹配失败”
    df.columns = [str(col).strip() for col in df.columns]

    # 仅保留中文列：先删除“（英文）”字段，再按中文白名单裁剪
    english_cols = [col for col in df.columns if "（英文）" in str(col)]
    if english_cols:
        df = df.drop(columns=english_cols)
    keep_cols = [col for col in CHINESE_COLUMNS if col in df.columns]
    df = df.loc[:, keep_cols].copy()

    # 第5行通常是英文列名说明（会被当作首行数据），这里按“序号”无法转为数字进行剔除
    if "序号" in df.columns and not df.empty:
        serial_num = pd.to_numeric(df["序号"], errors="coerce")
        df = df[serial_num.notna()].copy()

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
    2) “时代（中文）”中排除包含：近现代 / 中华民国 / 中华人民共和国。
    """
    result = df.copy()

    # 仅在实际存在目标列时进行筛选，避免因缺列直接报错
    if "类型（中文）" not in result.columns or "时代（中文）" not in result.columns:
        return result

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

    filtered_df = result[is_ancient_building & ~contains_modern_keywords].copy()
    return filtered_df


@st.cache_data
def filter_by_era(df: pd.DataFrame) -> pd.DataFrame:
    """按时代筛选 1911 年及以前建筑（空值默认排除）。"""
    result = df.copy()
    era_col = "时代（中文）"
    if era_col not in result.columns:
        print("[filter_by_era] 缺少'时代（中文）'列，返回原始数据")
        return result

    print(f"[filter_by_era] 输入记录数: {len(result)}")

    # Step 1: 排除时代为空（按需求建议，nan 直接排除）
    era_series = result[era_col]
    not_na_mask = era_series.notna() & (era_series.astype(str).str.strip() != "")
    result = result[not_na_mask].copy()
    result[era_col] = result[era_col].astype(str).str.strip()
    print(f"[filter_by_era] 排除空时代后记录数: {len(result)}")

    # Step 2: 排除近现代关键词
    modern_pattern = r"民国|中华民国|中华人民共和国|近现代|近代"
    contains_modern = result[era_col].str.contains(modern_pattern, regex=True, na=False)
    result = result[~contains_modern].copy()
    print(f"[filter_by_era] 排除近现代关键词后记录数: {len(result)}")

    # Step 3: 提取具体年份；若存在年份且最大年份 > 1911 则排除
    extracted_years = result[era_col].str.findall(r"\d{3,4}")

    def _year_rule(year_list: list[str]) -> bool:
        if not year_list:
            return True
        year_nums = [int(y) for y in year_list]
        return max(year_nums) <= 1911

    year_keep_mask = extracted_years.apply(_year_rule)
    result = result[year_keep_mask].copy()
    print(f"[filter_by_era] 按具体年份筛选后记录数: {len(result)}")

    # Step 4: 处理“世纪”格式（如 10世纪=901-1000，属于 1911 年前）
    # 仅对“无具体年份但有世纪”的记录应用规则：世纪 <= 19 保留，>=20 排除
    century_num = pd.to_numeric(result[era_col].str.extract(r"(\d{1,2})\s*世纪")[0], errors="coerce")
    has_year = result[era_col].str.contains(r"\d{3,4}", regex=True, na=False)
    has_century = century_num.notna()
    century_keep_mask = (~has_century) | has_year | (century_num <= 19)
    result = result[century_keep_mask].copy()
    print(f"[filter_by_era] 按世纪规则筛选后记录数: {len(result)}")

    return result


@st.cache_data
def filter_eligible_buildings(df):
    """
    从古建筑数据中筛选出符合大赛主题的建筑
    排除：任何带"庙"字的建筑、寺庙、宝塔、石窟、石刻、宗教建筑
    保留：民居、官府、皇宫、桥梁
    """
    print(f"[filter_eligible_buildings] 输入记录数: {len(df)}")

    # 1. 排除"石窟寺及石刻"类型
    if '类型（中文）' in df.columns:
        df = df[df['类型（中文）'] != '石窟寺及石刻']
        print(f"[filter_eligible_buildings] 排除石窟寺及石刻后: {len(df)}")

    # 2. 定义排除关键词（只要名称包含任一关键词就排除）
    exclude_keywords = [
        '庙',  # 任何带庙字的
        '寺', '塔', '宫', '观', '庵', '堂', '殿',
        '石窟', '石刻', '造像', '经幢',
        '佛', '菩萨', '罗汉', '天尊',
        '清真', '教堂', '礼拜',
    ]

    # 3. 名称筛选函数
    def should_exclude(name):
        if pd.isna(name):
            return True
        name_str = str(name)
        for kw in exclude_keywords:
            if kw in name_str:
                return True
        return False

    # 4. 应用筛选
    if '单位名称（中文）' in df.columns:
        before = len(df)
        mask = ~df['单位名称（中文）'].apply(should_exclude)
        df = df[mask]
        print(f"[filter_eligible_buildings] 名称筛选后: {len(df)} (排除 {before - len(df)} 条)")

    # 5. 时间筛选：排除空时代、近现代关键词，以及首个四位年份 > 1911 的记录
    if "时代（中文）" in df.columns:
        before_era = len(df)
        era_series = df["时代（中文）"]

        # nan/空值直接排除
        non_empty_mask = era_series.notna() & (era_series.astype(str).str.strip() != "")
        df = df[non_empty_mask].copy()
        df["时代（中文）"] = df["时代（中文）"].astype(str).str.strip()

        # 排除关键词：民国、近代、现代、中华人民共和国
        era_exclude_pattern = r"民国|近代|现代|中华人民共和国"
        has_modern_keyword = df["时代（中文）"].str.contains(era_exclude_pattern, regex=True, na=False)

        # 提取第一个四位数字；若 > 1911 则排除，<= 1911 保留；无四位年份则不因年份被排除
        first_year = pd.to_numeric(df["时代（中文）"].str.extract(r"(\d{4})")[0], errors="coerce")
        year_over_1911 = first_year.notna() & (first_year > 1911)

        df = df[~(has_modern_keyword | year_over_1911)].copy()
        print(f"[filter_eligible_buildings] 时间筛选后: {len(df)} (筛选前 {before_era} 条)")

    return df

def get_filter_summary(original_df: pd.DataFrame, filtered_df: pd.DataFrame) -> dict[str, Any]:
    """返回筛选前后数量对比及被排除主要类型统计。"""
    original_count = int(len(original_df))
    filtered_count = int(len(filtered_df))
    excluded_count = int(max(original_count - filtered_count, 0))

    name_col = "单位名称（中文）"
    type_col = "类型（中文）"
    excluded_type_stats: dict[str, int] = {}

    if name_col in original_df.columns and type_col in original_df.columns and name_col in filtered_df.columns:
        # 通过名称差集估计被排除集合，用于展示主要排除类型分布
        original_names = original_df[name_col].fillna("").astype(str).str.strip()
        filtered_name_set = set(filtered_df[name_col].fillna("").astype(str).str.strip())
        excluded_mask = ~original_names.isin(filtered_name_set)

        excluded_subset = original_df.loc[excluded_mask, [name_col, type_col]].copy()
        text_series = (
            excluded_subset[name_col].fillna("").astype(str).str.strip() + " "
            + excluded_subset[type_col].fillna("").astype(str).str.strip()
        ).str.strip()

        excluded_type_stats = {
            "寺类": int(text_series.str.contains("寺", regex=False, na=False).sum()),
            "庙类(不含文庙)": int((text_series.str.contains("庙", regex=False, na=False) & ~text_series.str.contains("文庙", regex=False, na=False)).sum()),
            "塔类": int(text_series.str.contains("塔", regex=False, na=False).sum()),
            "宫类(非皇宫语义)": int((text_series.str.contains("宫", regex=False, na=False) & ~text_series.str.contains(r"皇宫|宫殿|故宫|王府|王宫|行宫", regex=True, na=False)).sum()),
            "观类": int(text_series.str.contains("观", regex=False, na=False).sum()),
            "庵/堂类": int(text_series.str.contains(r"庵|堂", regex=True, na=False).sum()),
        }

    return {
        "original_count": original_count,
        "filtered_count": filtered_count,
        "excluded_count": excluded_count,
        "excluded_type_stats": excluded_type_stats,
    }


def save_filtered_data(df: pd.DataFrame, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> None:
    """将筛选后的数据按指定列保存为 UTF-8 编码 CSV。"""
    _ensure_required_columns(df, OUTPUT_COLUMNS)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 仅输出业务要求列，保证与模板表头一致
    export_df = df.loc[:, OUTPUT_COLUMNS].copy()
    export_df.to_csv(path, index=False, encoding="utf-8")


def export_filtered_data(
    df: pd.DataFrame,
    output_path: str | Path = DEFAULT_ELIGIBLE_OUTPUT_PATH,
) -> Path:
    """将筛选后的数据导出为 CSV（仅中文列，UTF-8 BOM 编码）。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 导出时仅保留中文字段，避免英文辅助列影响人工核查
    export_cols = [col for col in CHINESE_COLUMNS if col in df.columns]
    export_df = df.loc[:, export_cols].copy() if export_cols else df.copy()
    print(f"[export_filtered_data] 导出列名: {list(export_df.columns)}")
    print(f"[export_filtered_data] 导出记录数: {len(export_df)}")
    export_df.to_csv(path, index=False, encoding="utf-8-sig")

    print(f"导出完成: {path.resolve()} (共 {len(export_df)} 条记录)")
    return path


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


if __name__ == "__main__":
    # 测试入口：加载数据 -> 古建筑筛选 -> 主题筛选 -> 自动导出，便于人工核查
    all_df = load_excel_data()
    ancient_df = filter_ancient_buildings(all_df)
    eligible_df = filter_eligible_buildings(ancient_df)
    export_filtered_data(eligible_df)
