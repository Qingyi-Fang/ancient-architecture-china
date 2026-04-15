"""古建筑地图可视化模块（Folium + Streamlit）。"""

from __future__ import annotations

import folium
import pandas as pd
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static


def _detect_coordinate_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """自动识别经纬度字段名，提升不同数据源兼容性。"""
    lat_candidates = ["纬度", "纬度（中文）", "lat", "latitude", "Latitude"]
    lon_candidates = ["经度", "经度（中文）", "lng", "lon", "longitude", "Longitude"]

    lat_col = next((col for col in lat_candidates if col in df.columns), None)
    lon_col = next((col for col in lon_candidates if col in df.columns), None)
    return lat_col, lon_col


def create_china_building_map(df: pd.DataFrame, selected_province: str | None = None) -> folium.Map:
    """创建全国古建筑分布地图（支持省份筛选）。"""
    # 中国地理中心 + 全国视角缩放
    china_map = folium.Map(location=[35.0, 108.0], zoom_start=4, tiles="OpenStreetMap")

    if df.empty:
        return china_map

    result = df.copy()
    province_col = "省级政区名称（中文）"
    address_col = "地址（中文）"
    name_col = "单位名称（中文）"
    era_col = "时代（中文）"
    batch_col = "批次（中文）"

    # 若选择了省份，仅展示该省数据
    if selected_province and province_col in result.columns:
        result = result[result[province_col] == selected_province].copy()

    lat_col, lon_col = _detect_coordinate_columns(result)
    if lat_col is None or lon_col is None or address_col not in result.columns:
        # 无坐标或地址字段时，返回空底图
        return china_map

    # 转为数值坐标，非法值置为 NaN，后续统一过滤
    result[lat_col] = pd.to_numeric(result[lat_col], errors="coerce")
    result[lon_col] = pd.to_numeric(result[lon_col], errors="coerce")
    result[address_col] = result[address_col].fillna("").astype(str).str.strip()

    # 跳过无地址或无经纬度记录
    valid_mask = (
        result[address_col] != ""
    ) & result[lat_col].notna() & result[lon_col].notna()
    plot_df = result[valid_mask].copy()

    marker_cluster = MarkerCluster(name="古建筑点位").add_to(china_map)

    for _, row in plot_df.iterrows():
        name = str(row.get(name_col, "")).strip() or "未命名"
        era = str(row.get(era_col, "")).strip() or "未知"
        address = str(row.get(address_col, "")).strip() or "未知"
        batch = str(row.get(batch_col, "")).strip() or "未知"

        # 弹窗使用简洁 HTML，便于快速人工查看
        popup_html = f"""
        <div style="font-size:13px; line-height:1.6; min-width:220px;">
            <div style="font-weight:700; color:#5C3317; margin-bottom:4px;">{name}</div>
            <div><b>朝代：</b>{era}</div>
            <div><b>地址：</b>{address}</div>
            <div><b>批次：</b>{batch}</div>
        </div>
        """

        folium.Marker(
            location=[row[lat_col], row[lon_col]],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=name,
            # Folium 默认图标色没有 brown，这里使用接近棕色的 darkred
            icon=folium.Icon(color="darkred", icon="home", prefix="fa"),
        ).add_to(marker_cluster)

    return china_map


def display_map_in_streamlit(df: pd.DataFrame, selected_province: str | None = None) -> None:
    """在 Streamlit 中渲染古建筑分布地图。"""
    china_map = create_china_building_map(df, selected_province=selected_province)
    folium_static(china_map, width=None, height=500)
