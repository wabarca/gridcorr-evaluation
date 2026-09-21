# -*- coding: utf-8 -*-
"""
Interactive Georeferenced WebGIS Map Viewer component for Streamlit.
Renders raster overlays over real map tile servers (Esri Satellite, OSM, Topo)
with complete dynamic Layer Selection (Original, Corrected, Difference, DEM, Stations),
colormap manipulation, range controls, opacity, and interactive station popups.
"""

import os
import io
import base64
import glob
import re
from typing import Optional, Tuple, List, Dict, Any
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib as mpl
import matplotlib.cm as cm
import streamlit as st
from PIL import Image

from ...application.models import AnalysisResult, AnalysisRequest, ProductType, ProcessingMode
from ...io.netcdf_loader import (
    load_daily_chirts_raw,
    load_daily_chirts_corr,
    load_dem_dataset,
    rename_coords_latlon,
)
from ...core.spatial import load_daily_sum_for_year, load_annual_temp_stat
from ...core.climatology import load_period_stat_raw, load_period_stat_corr, get_dates_for_period


BASEMAPS = {
    "Esri World Imagery (Satélite Alta Res.)": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
    },
    "OpenStreetMap (Estándar)": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
    },
    "CartoDB Positron (Mapa Claro)": {
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "attribution": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> &copy; <a href='https://carto.com/attributions'>CARTO</a>"
    },
    "CartoDB Dark Matter (Mapa Oscuro)": {
        "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "attribution": "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> &copy; <a href='https://carto.com/attributions'>CARTO</a>"
    },
    "OpenTopoMap (Topográfico con relieve)": {
        "url": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "attribution": "Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap"
    },
}

COLORMAPS = [
    "viridis",
    "coolwarm",
    "RdYlBu_r",
    "Spectral_r",
    "turbo",
    "YlGnBu",
    "Blues",
    "plasma",
    "magma",
    "inferno",
    "PuOr_r",
    "BrBG",
    "jet"
]

RASTER_LAYER_OPTIONS = [
    "✨ Rejilla Corregida (CDT Merged)",
    "🛰️ Rejilla Original (Raw)",
    "🔄 Diferencia Espacial ΔGRID (Corregido − Original)",
    "🏔️ Topografía / Relieve (DEM)",
    "📂 Archivo NetCDF Específico / Salida",
    "🚫 Ninguna (Solo Mapa Base y Estaciones)",
]

STATION_LAYER_OPTIONS = [
    "📍 Observado in-situ (Estaciones)",
    "✨ Rejilla Corregida CDT en Estación",
    "🛰️ Rejilla Original Raw en Estación",
    "⚠️ Residuo (Corregido − Observado)",
    "🔄 Diferencia (Corregido − Original)",
    "📈 Mejora de RMSE (%)",
    "🚫 Ocultar Marcadores de Estaciones",
]


def raster_to_base64_png(
    data_2d: np.ndarray,
    cmap_name: str,
    vmin: float,
    vmax: float,
    opacity: float = 0.85
) -> str:
    """
    Convierte una matriz 2D geoespacial en una imagen PNG en base64 con la paleta y opacidad especificadas.
    """
    denom = max(vmax - vmin, 1e-6)
    norm_data = np.clip((data_2d - vmin) / denom, 0.0, 1.0)

    try:
        cmap = mpl.colormaps.get_cmap(cmap_name)
    except Exception:
        cmap = cm.get_cmap(cmap_name)

    rgba = cmap(norm_data)
    mask_nan = ~np.isfinite(data_2d)
    rgba[mask_nan] = [0, 0, 0, 0]
    rgba[~mask_nan, 3] = opacity

    rgba_8bit = (rgba * 255).astype(np.uint8)
    img = Image.fromarray(rgba_8bit, mode="RGBA")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _get_station_color(metric_name: str, val: float, vmin: float, vmax: float) -> str:
    """Retorna un color hexadecimal según la métrica y valor de la estación."""
    if not np.isfinite(val):
        return "#718096"

    if "mejora" in metric_name.lower():
        return "#10B981" if val > 0 else "#EF4444"  # Verde si mejora, rojo si empeora
    elif "residuo" in metric_name.lower() or "diferencia" in metric_name.lower():
        if abs(val) < 0.2:
            return "#3B82F6"  # Azul / Neutro
        return "#F59E0B" if val > 0 else "#8B5CF6"
    else:
        return "#EF4444"


def render_webgis_viewer(result: AnalysisResult) -> None:
    """
    Renderiza el visor WebGIS interactivo con selector de capas raster y vectoriales.
    """
    st.subheader("🌐 Visor Georreferenciado Interactivo (WebGIS)")

    req = result.request if hasattr(result, "request") and result.request is not None else None

    with st.expander("📖 **Guía de Uso del Visor y Selector de Capas**", expanded=False):
        st.markdown(
            r"""
            ### 🗂️ Control de Capas y Funcionalidades:
            - **Selector de Capa Raster**: Permite alternar al instante entre la **Rejilla Corregida (CDT)**, la **Rejilla Original (Raw)**, la **Diferencia Espacial $\Delta\text{GRID}$**, el **Relieve DEM** o cualquier archivo NetCDF disponible.
            - **Selector de Capa de Estaciones**: Elija qué variable visualizar en los pines de estaciones (Medición observada, valor en grilla cruda/corregida, residuo de error o porcentaje de mejora).
            - **Selector de Año / Fecha**: Si el análisis cubrió múltiples años o fechas, use el selector para proyectar la malla de ese período específico.
            - **Personalización Dinámica**: Ajuste en vivo la paleta cromática, opacidad y rango dinámico ($V_{\min} - V_{\max}$).
            - **Popups Interactivos**: Haga clic en cualquier estación para desplegar la ficha técnica completa con todas sus métricas.
            """
        )

    # 1. Encontrar años o fechas disponibles
    available_years: List[int] = []
    if req and req.yini and req.yend:
        available_years = list(range(req.yini, req.yend + 1))
    else:
        # Extraer años de CSVs generados
        for cp in result.generated_csvs:
            match = re.search(r"(\d{4})", os.path.basename(cp))
            if match:
                y = int(match.group(1))
                if 1900 <= y <= 2100 and y not in available_years:
                    available_years.append(y)
        available_years = sorted(available_years)

    # 2. Descubrir archivos NetCDF en la carpeta de salida o proyecto
    nc_files = sorted(glob.glob(os.path.join(result.output_dir, "**", "*.nc"), recursive=True))
    if req:
        if req.dir_merged and os.path.exists(req.dir_merged):
            nc_files.extend(sorted(glob.glob(os.path.join(req.dir_merged, "**", "*.nc"), recursive=True))[:10])
        if req.dir_original and os.path.exists(req.dir_original):
            nc_files.extend(sorted(glob.glob(os.path.join(req.dir_original, "**", "*.nc"), recursive=True))[:10])
    nc_files = sorted(list(set(nc_files)))

    # =========================================================================
    # SECCIÓN DE CONTROLES: SELECTOR DE CAPAS
    # =========================================================================
    st.markdown("#### 🗂️ Selección de Capas a Desplegar")
    lay_col1, lay_col2, lay_col3 = st.columns([1.6, 1.6, 1.2])

    with lay_col1:
        raster_choice = st.selectbox(
            "🛰️ **Capa Raster (Malla Continua)**",
            options=RASTER_LAYER_OPTIONS,
            index=0,
            key="webgis_raster_choice"
        )

    with lay_col2:
        station_choice = st.selectbox(
            "📍 **Capa de Estaciones (Puntos)**",
            options=STATION_LAYER_OPTIONS,
            index=0,
            key="webgis_station_choice"
        )

    with lay_col3:
        selected_year = None
        if available_years and len(available_years) > 1 and raster_choice not in ["🏔️ Topografía / Relieve (DEM)", "📂 Archivo NetCDF Específico / Salida", "🚫 Ninguna (Solo Mapa Base y Estaciones)"]:
            selected_year = st.selectbox("📅 **Año / Período**", options=available_years, index=0, key="webgis_year_select")
        elif available_years and len(available_years) == 1:
            selected_year = available_years[0]

    selected_nc_path = None
    if raster_choice == "📂 Archivo NetCDF Específico / Salida":
        if nc_files:
            selected_nc_path = st.selectbox("Seleccione archivo NetCDF:", options=nc_files, format_func=lambda x: os.path.basename(x), key="webgis_custom_nc")
        else:
            st.warning("No se encontraron archivos NetCDF adicionales en las carpetas analizadas.")

    # =========================================================================
    # CARGA DE DATOS RASTER SEGÚN LA CAPA SELECCIONADA
    # =========================================================================
    da_current: Optional[xr.DataArray] = None
    layer_unit = "°C" if req and req.product == ProductType.CHIRTS else "mm"
    target_year = selected_year or (available_years[0] if available_years else 1991)

    try:
        stat_str = "mean"
        if req and req.stat:
            stat_str = req.stat.value if hasattr(req.stat, "value") else str(req.stat)
            if stat_str.lower() in ["all", "todos"]:
                stat_str = "mean"

        if raster_choice == "✨ Rejilla Corregida (CDT Merged)":
            if req and req.product == ProductType.CHIRPS:
                da_current = load_daily_sum_for_year(req.dir_merged, target_year, "precip_mrg_", "precip")
                layer_unit = "mm"
            elif req and req.product == ProductType.CHIRTS:
                if req.mode == ProcessingMode.DAILY and req.date_str:
                    da_current = load_daily_chirts_corr(req.dir_merged, req.date_str, prefix=req.var)
                elif req.mode == ProcessingMode.PERIOD:
                    dates = get_dates_for_period(target_year, req.period_type.value if hasattr(req.period_type, "value") else str(req.period_type), req.season, req.months)
                    da_current = load_period_stat_corr(req.dir_merged, dates, var=req.var, stat=stat_str)
                else:
                    prefix_corr = f"{req.var}_mrg_"
                    da_current = load_annual_temp_stat(req.dir_merged, target_year, prefix=prefix_corr, varname=req.var, stat=stat_str)
                layer_unit = "°C"

        elif raster_choice == "🛰️ Rejilla Original (Raw)":
            if req and req.product == ProductType.CHIRPS:
                da_current = load_daily_sum_for_year(req.dir_original, target_year, "precip_", "precip")
                layer_unit = "mm"
            elif req and req.product == ProductType.CHIRTS:
                if req.mode == ProcessingMode.DAILY and req.date_str:
                    da_current = load_daily_chirts_raw(req.dir_original, req.date_str, req.prefix_original)
                elif req.mode == ProcessingMode.PERIOD:
                    dates = get_dates_for_period(target_year, req.period_type.value if hasattr(req.period_type, "value") else str(req.period_type), req.season, req.months)
                    da_current = load_period_stat_raw(req.dir_original, dates, prefix_chirts=req.prefix_original, stat=stat_str)
                else:
                    da_current = load_annual_temp_stat(req.dir_original, target_year, prefix=req.prefix_original, varname=req.var, stat=stat_str)
                layer_unit = "°C"

        elif raster_choice == "🔄 Diferencia Espacial ΔGRID (Corregido − Original)":
            if req and req.product == ProductType.CHIRPS:
                da_raw = load_daily_sum_for_year(req.dir_original, target_year, "precip_", "precip")
                da_corr = load_daily_sum_for_year(req.dir_merged, target_year, "precip_mrg_", "precip")
                da_current = rename_coords_latlon(da_corr) - rename_coords_latlon(da_raw)
                layer_unit = "Δ mm"
            elif req and req.product == ProductType.CHIRTS:
                if req.mode == ProcessingMode.DAILY and req.date_str:
                    da_raw = load_daily_chirts_raw(req.dir_original, req.date_str, req.prefix_original)
                    da_corr = load_daily_chirts_corr(req.dir_merged, req.date_str, prefix=req.var)
                elif req.mode == ProcessingMode.PERIOD:
                    dates = get_dates_for_period(target_year, req.period_type.value if hasattr(req.period_type, "value") else str(req.period_type), req.season, req.months)
                    da_raw = load_period_stat_raw(req.dir_original, dates, prefix_chirts=req.prefix_original, stat=stat_str)
                    da_corr = load_period_stat_corr(req.dir_merged, dates, var=req.var, stat=stat_str)
                else:
                    prefix_corr = f"{req.var}_mrg_"
                    da_raw = load_annual_temp_stat(req.dir_original, target_year, prefix=req.prefix_original, varname=req.var, stat=stat_str)
                    da_corr = load_annual_temp_stat(req.dir_merged, target_year, prefix=prefix_corr, varname=req.var, stat=stat_str)
                da_current = rename_coords_latlon(da_corr) - rename_coords_latlon(da_raw)
                layer_unit = "Δ °C"

        elif raster_choice == "🏔️ Topografía / Relieve (DEM)":
            if req and req.dem_path and os.path.exists(req.dem_path):
                da_current = load_dem_dataset(req.dem_path)
                layer_unit = "m s.n.m."

        elif raster_choice == "📂 Archivo NetCDF Específico / Salida" and selected_nc_path:
            ds = xr.open_dataset(selected_nc_path)
            ds = rename_coords_latlon(ds)
            var_name = list(ds.data_vars.keys())[0]
            da = ds[var_name]
            if "time" in da.dims:
                da = da.isel(time=0)
            da_current = da
            layer_unit = "unidades"
    except Exception as e:
        st.info(f"Nota: No se pudo cargar dinámicamente la malla {raster_choice}: {e}")

    # =========================================================================
    # CARGA DE DATOS DE ESTACIONES
    # =========================================================================
    df_stations = None
    target_csv = None

    # Buscar CSV de comparación del año seleccionado si existe
    if selected_year:
        year_csvs = [p for p in result.generated_csvs if f"_{selected_year}_" in os.path.basename(p) and "cmp_estaciones" in os.path.basename(p)]
        if year_csvs:
            target_csv = year_csvs[0]

    if target_csv is None:
        for p in result.generated_csvs:
            if "cmp_estaciones" in p or "improvement_stations" in p or "summary_daily_by_station" in p:
                target_csv = p
                break

    if target_csv and os.path.exists(target_csv):
        try:
            df_stations = pd.read_csv(target_csv)
        except Exception:
            df_stations = None
    elif result.summary_station_df is not None:
        df_stations = result.summary_station_df.copy()

    # =========================================================================
    # CONTROLES DE ESTILO Y VISUALIZACIÓN
    # =========================================================================
    st.markdown("#### 🎨 Estilo y Parámetros del Mapa")
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.5, 1.5, 1.5])

    with ctrl_col1:
        basemap_choice = st.selectbox("🗺️ **Mapa Base**", options=list(BASEMAPS.keys()), index=0, key="webgis_basemap")

    with ctrl_col2:
        default_cmap = "coolwarm" if "diferencia" in raster_choice.lower() else ("Blues" if "precip" in layer_unit.lower() or "mm" in layer_unit.lower() else "viridis")
        cmap_idx = COLORMAPS.index(default_cmap) if default_cmap in COLORMAPS else 0
        cmap_choice = st.selectbox("🎨 **Paleta de Colores**", options=COLORMAPS, index=cmap_idx, key="webgis_cmap")

    with ctrl_col3:
        opacity = st.slider("👁️ **Opacidad del Raster**", min_value=0.0, max_value=1.0, value=0.75, step=0.05, key="webgis_opacity")

    # Controles de Rango Dinámico (vmin / vmax)
    vmin_val, vmax_val = 0.0, 100.0
    extent_bounds: Optional[Tuple[float, float, float, float]] = None

    if da_current is not None:
        da_current = rename_coords_latlon(da_current)
        grid_vals = da_current.values.astype(float)
        valid_vals = grid_vals[np.isfinite(grid_vals)]
        if len(valid_vals) > 0:
            raw_min = float(np.percentile(valid_vals, 1))
            raw_max = float(np.percentile(valid_vals, 99))
        else:
            raw_min, raw_max = 0.0, 100.0

        r_col1, r_col2 = st.columns(2)
        with r_col1:
            vmin_val = st.number_input("Valor Mínimo (vmin)", value=round(raw_min, 2), step=0.5, key="webgis_vmin")
        with r_col2:
            vmax_val = st.number_input("Valor Máximo (vmax)", value=round(raw_max, 2), step=0.5, key="webgis_vmax")

        lats = da_current["lat"].values
        lons = da_current["lon"].values
        lat_min, lat_max = float(np.nanmin(lats)), float(np.nanmax(lats))
        lon_min, lon_max = float(np.nanmin(lons)), float(np.nanmax(lons))
        extent_bounds = (lat_min, lon_min, lat_max, lon_max)

    # =========================================================================
    # GENERAR OVERLAY RASTER EN BASE64
    # =========================================================================
    raster_overlay_js = ""
    center_lat, center_lon = 13.7942, -88.8965
    zoom_level = 8

    if da_current is not None and extent_bounds is not None and raster_choice != "🚫 Ninguna (Solo Mapa Base y Estaciones)":
        lat_min, lon_min, lat_max, lon_max = extent_bounds
        center_lat = (lat_min + lat_max) / 2.0
        center_lon = (lon_min + lon_max) / 2.0

        grid_vals = da_current.values.astype(float)
        # Invertir si latitud es creciente de Sur a Norte para la imagen Leaflet
        if da_current["lat"].values[0] < da_current["lat"].values[-1]:
            grid_vals = np.flipud(grid_vals)

        b64_png = raster_to_base64_png(grid_vals, cmap_choice, vmin_val, vmax_val, opacity)
        raster_overlay_js = f"""
        var imageBounds = [[{lat_min}, {lon_min}], [{lat_max}, {lon_max}]];
        var rasterLayer = L.imageOverlay('data:image/png;base64,{b64_png}', imageBounds, {{
            opacity: {opacity},
            interactive: false
        }}).addTo(map);
        map.fitBounds(imageBounds);
        """

    # =========================================================================
    # GENERAR MARCADORES DE ESTACIONES
    # =========================================================================
    station_markers_js = ""
    if station_choice != "🚫 Ocultar Marcadores de Estaciones" and df_stations is not None and not df_stations.empty:
        lat_cols = [c for c in df_stations.columns if c.lower() in ["lat", "latitude", "latitud"]]
        lon_cols = [c for c in df_stations.columns if c.lower() in ["lon", "longitude", "longitud", "long"]]
        id_cols = [c for c in df_stations.columns if "id" in c.lower() or "est" in c.lower() or "name" in c.lower()]

        if lat_cols and lon_cols:
            lat_col = lat_cols[0]
            lon_col = lon_cols[0]
            id_col = id_cols[0] if id_cols else None

            markers_list = []
            for _, row in df_stations.iterrows():
                try:
                    lat = float(row[lat_col])
                    lon = float(row[lon_col])
                except (ValueError, TypeError):
                    continue

                st_id = str(row[id_col]) if id_col else f"Estación ({lat:.3f}, {lon:.3f})"

                # Obtener valor relevante según selección de estación
                st_val = np.nan
                val_label = ""
                if station_choice == "📍 Observado in-situ (Estaciones)":
                    for c in ["obs", "accum_obs", "precip_station", "tmax_station", "tmin_station"]:
                        if c in row.index and pd.notna(row[c]):
                            st_val = float(row[c])
                            val_label = f"Obs: {st_val:.1f} {layer_unit}"
                            break
                elif station_choice == "✨ Rejilla Corregida CDT en Estación":
                    if "grid_corr" in row.index and pd.notna(row["grid_corr"]):
                        st_val = float(row["grid_corr"])
                        val_label = f"CDT Corr: {st_val:.1f} {layer_unit}"
                elif station_choice == "🛰️ Rejilla Original Raw en Estación":
                    if "grid_raw" in row.index and pd.notna(row["grid_raw"]):
                        st_val = float(row["grid_raw"])
                        val_label = f"Raw: {st_val:.1f} {layer_unit}"
                elif station_choice == "⚠️ Residuo (Corregido − Observado)":
                    for c in ["residual_corr", "error_corr"]:
                        if c in row.index and pd.notna(row[c]):
                            st_val = float(row[c])
                            val_label = f"Residuo: {st_val:+.2f} {layer_unit}"
                            break
                    if np.isnan(st_val) and "grid_corr" in row.index and "obs" in row.index:
                        st_val = float(row["grid_corr"]) - float(row["obs"])
                        val_label = f"Residuo: {st_val:+.2f} {layer_unit}"
                elif station_choice == "🔄 Diferencia (Corregido − Original)":
                    if "delta_grid" in row.index and pd.notna(row["delta_grid"]):
                        st_val = float(row["delta_grid"])
                        val_label = f"ΔGRID: {st_val:+.2f} {layer_unit}"
                    elif "grid_corr" in row.index and "grid_raw" in row.index:
                        st_val = float(row["grid_corr"]) - float(row["grid_raw"])
                        val_label = f"ΔGRID: {st_val:+.2f} {layer_unit}"
                elif station_choice == "📈 Mejora de RMSE (%)":
                    for c in ["improvement_RMSE_pct", "improvement_pct"]:
                        if c in row.index and pd.notna(row[c]):
                            st_val = float(row[c])
                            val_label = f"Mejora RMSE: {st_val:+.1f}%"
                            break

                dot_color = _get_station_color(station_choice, st_val, vmin_val, vmax_val)
                tooltip_txt = f"{st_id} ({val_label})" if val_label else st_id

                popup_rows = "".join([
                    f"<tr><td style='padding:2px 6px; font-weight:bold; color:#4B5563;'>{c}:</td>"
                    f"<td style='padding:2px 6px; color:#1F2937;'>{row[c]}</td></tr>"
                    for c in df_stations.columns if str(c).lower() not in ["date", "time"]
                ][:8])

                popup_html = (
                    f"<div style='font-family:sans-serif; font-size:12px; min-width:180px;'>"
                    f"<div style='font-weight:bold; color:#1E3A8A; font-size:13px; border-bottom:1px solid #E5E7EB; padding-bottom:3px; margin-bottom:4px;'>"
                    f"📍 {st_id}</div>"
                    f"<table style='width:100%; border-collapse:collapse;'>{popup_rows}</table>"
                    f"</div>"
                )

                marker_code = f"""
                L.circleMarker([{lat}, {lon}], {{
                    radius: 6.5,
                    fillColor: '{dot_color}',
                    color: '#FFFFFF',
                    weight: 1.5,
                    opacity: 1.0,
                    fillOpacity: 0.95
                }}).bindPopup("{popup_html}").bindTooltip("{tooltip_txt}", {{permanent: false, direction: 'top'}}).addTo(map);
                """
                markers_list.append(marker_code)

            station_markers_js = "\n".join(markers_list)

    # 6. Configuración de tiles del mapa base
    tile_info = BASEMAPS[basemap_choice]
    tile_url = tile_info["url"]
    tile_attr = tile_info["attribution"]

    # 7. Construcción de HTML/JavaScript de Leaflet
    legend_title = f"{raster_choice.split('(')[0].strip()} [{layer_unit}]"
    leaflet_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                height: 100%;
                width: 100%;
                background: #F8FAFC;
            }}
            #map {{
                height: 600px;
                width: 100%;
                border-radius: 8px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}
            .legend {{
                padding: 8px 12px;
                font: 12px sans-serif;
                background: rgba(255, 255, 255, 0.92);
                box-shadow: 0 0 15px rgba(0,0,0,0.2);
                border-radius: 6px;
                line-height: 18px;
                color: #1F2937;
            }}
            .legend-title {{
                font-weight: bold;
                font-size: 11px;
                margin-bottom: 4px;
                color: #111827;
            }}
            .leaflet-popup-content-wrapper {{
                border-radius: 8px;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map', {{
                center: [{center_lat}, {center_lon}],
                zoom: {zoom_level},
                zoomControl: true
            }});

            L.tileLayer('{tile_url}', {{
                attribution: '{tile_attr}',
                maxZoom: 18
            }}).addTo(map);

            // Capa Raster Georreferenciada
            {raster_overlay_js}

            // Capa Vectorial de Estaciones
            {station_markers_js}

            // Control de Escala Métrica
            L.control.scale({{metric: true, imperial: false}}).addTo(map);

            // Leyenda de Escala y Rango
            var legend = L.control({{position: 'bottomright'}});
            legend.onAdd = function (map) {{
                var div = L.DomUtil.create('div', 'legend');
                div.innerHTML = '<div class="legend-title">{legend_title}</div>' +
                                '<div style="display:flex; justify-content:space-between; width:150px; font-weight:bold; font-size:11px;">' +
                                '<span>{vmin_val:.1f}</span><span>{((vmin_val+vmax_val)/2.0):.1f}</span><span>{vmax_val:.1f}</span></div>';
                return div;
            }};
            legend.addTo(map);
        </script>
    </body>
    </html>
    """

    if hasattr(st, "iframe"):
        st.iframe(leaflet_html, height=630, width="stretch")
    else:
        import streamlit.components.v1 as components
        components.html(leaflet_html, height=630, scrolling=False)
