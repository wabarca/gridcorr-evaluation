# -*- coding: utf-8 -*-
"""
Map generation module using Cartopy, Matplotlib, and DEM Hillshade.
"""

import os
from typing import Optional, Tuple, List
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, LightSource
from matplotlib.gridspec import GridSpec
import cartopy.crs as ccrs
import cartopy.feature as cfeature

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

from ..config.constants import (
    COLOR_PALETTES,
    CHIRPS_RAIN_COLORS,
    CHIRPS_RAIN_CMAP,
    CHIRPS_DAILY_LEVELS,
    CHIRPS_DAILY_TICKS,
    CHIRPS_DAILY_VMAX,
    CHIRPS_PERIOD_LEVELS,
    CHIRPS_PERIOD_TICKS,
    CHIRPS_PERIOD_VMAX,
    CHIRPS_ANNUAL_LEVELS,
    CHIRPS_ANNUAL_TICKS,
    CHIRPS_ANNUAL_VMAX,
    CHIRPS_BINS,
    CHIRPS_MAX_MM,
    CHIRTS_BINS,
    CHIRTS_VMIN,
    CHIRTS_VMAX,
)
from ..io.netcdf_loader import rename_coords_latlon
from ..core.spatial import calculate_hillshade


def _figsize_from_extent(extent: Tuple[float, float, float, float], base_height: float = 5.8) -> Tuple[float, float]:
    """Calcula el tamaño de figura (ancho, alto) a partir del extent geográfico preservando la relación de aspecto del país o territorio."""
    xmin, xmax, ymin, ymax = extent
    dx = abs(xmax - xmin)
    dy = abs(ymax - ymin)
    if dy <= 0:
        return (base_height, base_height)
    aspect = dx / dy
    width = base_height * aspect
    return (width, base_height)


def _extract_station_value(
    r: pd.Series,
    value_col: Optional[str] = None,
    var: str = "",
    stat: str = ""
) -> Optional[float]:
    """
    Extrae de forma precisa y segura el valor numérico de una estación desde una fila/Series.
    Si se especifica value_col (ej. 'delta_grid', 'residual_corr', 'improvement_RMSE_pct'),
    busca únicamente columnas compatibles con dicha métrica y NO cae en observaciones crudas de estación.
    """
    if value_col is not None:
        # Búsqueda exacta
        if value_col in r.index and pd.notna(r[value_col]):
            try:
                v = float(r[value_col])
                if np.isfinite(v):
                    return v
            except (ValueError, TypeError):
                pass

        # Búsqueda por alias específico de la métrica
        v_low = str(value_col).lower()
        if "delta" in v_low or "diff" in v_low:
            for c in ["delta_grid", "delta", "grid_diff", "diff"]:
                if c in r.index and pd.notna(r[c]):
                    try:
                        v = float(r[c])
                        if np.isfinite(v):
                            return v
                    except (ValueError, TypeError):
                        pass
            return None

        if "resid" in v_low or "err" in v_low:
            for c in ["residual_corr", "err_corr", "residual", "resid"]:
                if c in r.index and pd.notna(r[c]):
                    try:
                        v = float(r[c])
                        if np.isfinite(v):
                            return v
                    except (ValueError, TypeError):
                        pass
            return None

        if "improv" in v_low:
            for c in ["improvement_RMSE_pct", "improvement_pct", "Improvement_RMSE_pct", "imp_pct"]:
                if c in r.index and pd.notna(r[c]):
                    try:
                        v = float(r[c])
                        if np.isfinite(v):
                            return v
                    except (ValueError, TypeError):
                        pass
            return None

    # Si no se pasó value_col o es para observación (Side-by-side)
    candidates = [
        f"{var}_{stat}_obs", f"{var}_{stat}", f"{var}_obs", f"{var}_station",
        f"{stat}_obs", "accum_obs", "obs", "precip_station", "precipitation", "temperature",
        "value", "val", "data"
    ]
    for c in candidates:
        if c in r.index and pd.notna(r[c]):
            try:
                v = float(r[c])
                if np.isfinite(v):
                    return v
            except (ValueError, TypeError):
                continue

    for c in r.index:
        c_str = str(c).lower()
        if c_str not in [
            "station_id", "id", "lon", "lat", "elev", "elevation", "year", "date", "month", "time",
            "delta_grid", "residual_corr", "err_raw", "err_corr", "grid_raw", "grid_corr",
            "improvement_rmse_pct", "improvement_pct"
        ]:
            if pd.notna(r[c]):
                try:
                    v = float(r[c])
                    if np.isfinite(v):
                        return v
                except (ValueError, TypeError):
                    continue
    return None


def _render_callout_badge(
    ax,
    st_lon: float,
    st_lat: float,
    lbl_lon: float,
    lbl_lat: float,
    text: str,
    proj: ccrs.Projection,
    fontsize: float = 8.5,
) -> None:
    """Renderiza una línea conectora fina y una etiqueta exterior nítida con borde suave."""
    ax.plot(
        [st_lon, lbl_lon],
        [st_lat, lbl_lat],
        color="#0F172A",
        linewidth=0.85,
        linestyle="-",
        alpha=0.80,
        transform=proj,
        zorder=10,
    )
    ax.text(
        lbl_lon,
        lbl_lat,
        str(text),
        transform=proj,
        fontsize=fontsize,
        fontweight="bold",
        color="#0F172A",
        ha="center",
        va="center",
        bbox=dict(
            boxstyle="round,pad=0.25",
            fc="#FFFFFF",
            ec="#1E293B",
            lw=0.80,
            alpha=0.95,
        ),
        zorder=12,
    )


def relax_1d_positions(
    initial_pos: List[float],
    min_sep: float,
    min_bound: Optional[float] = None,
    max_bound: Optional[float] = None,
    max_iter: int = 100,
) -> List[float]:
    """
    Relaja coordenadas 1D de forma no lineal para garantizar que cada par de etiquetas adyacentes
    tenga una separación mínima estricta (min_sep), preservando el orden espacial original
    y minimizando la desviación respecto a las posiciones de las estaciones.
    """
    n = len(initial_pos)
    if n <= 1:
        return list(initial_pos)

    pos = np.array(initial_pos, dtype=float)

    for _ in range(max_iter):
        moved = False
        for i in range(n - 1):
            dist = pos[i + 1] - pos[i]
            if dist < min_sep:
                overlap = min_sep - dist
                shift = overlap / 2.0
                pos[i] -= shift
                pos[i + 1] += shift
                moved = True

        if min_bound is not None and pos[0] < min_bound:
            pos[0] = min_bound
            for i in range(n - 1):
                if pos[i + 1] < pos[i] + min_sep:
                    pos[i + 1] = pos[i] + min_sep

        if max_bound is not None and pos[-1] > max_bound:
            pos[-1] = max_bound
            for i in range(n - 1, 0, -1):
                if pos[i - 1] > pos[i] - min_sep:
                    pos[i - 1] = pos[i] - min_sep

        if not moved:
            break

    return list(pos)


def plot_all_station_labels_harmonious(
    ax,
    stations_df: pd.DataFrame,
    extent: Tuple[float, float, float, float],
    proj: ccrs.Projection,
    var: Optional[str] = None,
    stat: Optional[str] = None,
    value_col: Optional[str] = None,
    delta_raster: Optional[xr.DataArray] = None,
    units: Optional[str] = None,
    is_pct: bool = False,
    fontsize: float = 7.5,
) -> None:
    """
    Coloca etiquetas numéricas cercanas y armónicas a cada estación meteorológica,
    utilizando una optimización de fuerzas repulsivas 2D para garantizar que no se
    superpongan entre sí ni queden excesivamente alejadas del punto de observación.
    """
    if stations_df is None or stations_df.empty:
        return

    xmin, xmax, ymin, ymax = extent
    dx_span = xmax - xmin
    dy_span = ymax - ymin

    valid_stations = []
    for _, r in stations_df.iterrows():
        if "lon" not in r or "lat" not in r or pd.isna(r["lon"]) or pd.isna(r["lat"]):
            continue
        lon = float(r["lon"])
        lat = float(r["lat"])

        val = None
        if value_col is not None:
            val = _extract_station_value(r, value_col=value_col)
        elif var is not None:
            val = _extract_station_value(r, var=var, stat=stat)
        else:
            val = _extract_station_value(r)

        if (val is None or not np.isfinite(val)) and delta_raster is not None:
            try:
                val = float(delta_raster.sel(lon=lon, lat=lat, method="nearest").values)
            except Exception:
                val = None

        # Descartar nulos y valores faltantes CDT (-99, -999)
        if val is None or not np.isfinite(val) or float(val) <= -90.0:
            continue

        u_str = (units or "").lower()
        if is_pct:
            txt = f"{val:+.1f}%"
        elif "mm" in u_str:
            if value_col in ("delta_grid", "residual_corr", "residual_raw") or delta_raster is not None:
                txt = f"{val:+.0f}"
            else:
                txt = f"{val:.0f}"
        else:
            if value_col in ("delta_grid", "residual_corr", "residual_raw") or delta_raster is not None:
                txt = f"{val:+.2f}"
            else:
                txt = f"{val:.1f}"

        valid_stations.append({
            "lon": lon,
            "lat": lat,
            "val": float(val),
            "text": txt,
        })

    if not valid_stations:
        return

    n = len(valid_stations)
    st_x = np.array([p["lon"] for p in valid_stations], dtype=float)
    st_y = np.array([p["lat"] for p in valid_stations], dtype=float)

    # Parámetros adaptativos de geometría y relajación
    box_w = max(0.08, min(0.15, dx_span * 0.045))
    box_h = max(0.05, min(0.09, dy_span * 0.050))
    r_target = max(0.06, min(0.12, dx_span * 0.035))
    r_max = max(0.12, min(0.22, dx_span * 0.070))

    lbl_x = st_x.copy()
    lbl_y = st_y.copy()

    # Vector inicial hacia cuadrante menos denso
    for i in range(n):
        diff_x = st_x[i] - st_x
        diff_y = st_y[i] - st_y
        dist_sq = diff_x**2 + diff_y**2
        mask = (dist_sq > 1e-6) & (dist_sq < 0.25**2)
        if np.any(mask):
            vx = -np.sum(diff_x[mask] / (dist_sq[mask] + 1e-4))
            vy = -np.sum(diff_y[mask] / (dist_sq[mask] + 1e-4))
            norm_v = np.hypot(vx, vy)
            if norm_v > 1e-4:
                vx /= norm_v
                vy /= norm_v
            else:
                vx, vy = 0.707, 0.707
        else:
            vx, vy = 0.707, 0.707
        lbl_x[i] = st_x[i] + vx * r_target
        lbl_y[i] = st_y[i] + vy * r_target

    # Relajación 2D por iteraciones
    for _ in range(60):
        for i in range(n):
            for j in range(i + 1, n):
                dx = lbl_x[j] - lbl_x[i]
                dy = lbl_y[j] - lbl_y[i]
                overlap_x = box_w - abs(dx)
                overlap_y = box_h - abs(dy)
                if overlap_x > 0 and overlap_y > 0:
                    if overlap_x < overlap_y:
                        shift = overlap_x * 0.55
                        sgn = 1.0 if dx >= 0 else -1.0
                        lbl_x[j] += shift * sgn
                        lbl_x[i] -= shift * sgn
                    else:
                        shift = overlap_y * 0.55
                        sgn = 1.0 if dy >= 0 else -1.0
                        lbl_y[j] += shift * sgn
                        lbl_y[i] -= shift * sgn

        for i in range(n):
            dx_orig = lbl_x[i] - st_x[i]
            dy_orig = lbl_y[i] - st_y[i]
            curr_r = np.hypot(dx_orig, dy_orig)
            if curr_r > r_max:
                lbl_x[i] = st_x[i] + (dx_orig / curr_r) * r_max
                lbl_y[i] = st_y[i] + (dy_orig / curr_r) * r_max
            elif curr_r < 0.04:
                lbl_x[i] = st_x[i] + (dx_orig / max(curr_r, 1e-4)) * 0.06
                lbl_y[i] = st_y[i] + (dy_orig / max(curr_r, 1e-4)) * 0.06

            lbl_x[i] = np.clip(lbl_x[i], xmin + 0.04, xmax - 0.04)
            lbl_y[i] = np.clip(lbl_y[i], ymin + 0.04, ymax - 0.04)

    # Renderizado de líneas directrices y badges numéricos
    for i, p in enumerate(valid_stations):
        sx, sy = st_x[i], st_y[i]
        lx, ly = lbl_x[i], lbl_y[i]

        ax.plot(
            [sx, lx], [sy, ly],
            color="#334155",
            linewidth=0.65,
            linestyle="-",
            alpha=0.85,
            transform=proj,
            zorder=10,
        )
        ax.text(
            lx, ly,
            p["text"],
            transform=proj,
            fontsize=fontsize,
            fontweight="bold",
            color="#0F172A",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.20",
                facecolor="#FFFFFF",
                edgecolor="#64748B",
                linewidth=0.55,
                alpha=0.92,
            ),
            zorder=12,
        )


# Alias para compatibilidad
plot_all_station_labels_outer_margin = plot_all_station_labels_harmonious



def _place_station_label(
    ax,
    lon: float,
    lat: float,
    text: str,
    placed_positions: List[Tuple[float, float]],
    proj: ccrs.Projection,
    d_lon: float = 0.08,
    d_lat: float = 0.06,
    fontsize: float = 9.0,
    extent: Optional[Tuple[float, float, float, float]] = None,
) -> None:
    """Colocación puntual individual de etiquetas para compatibilidad."""
    if not text or str(text).strip() == "":
        return
    _render_callout_badge(ax, lon, lat, lon + d_lon, lat + d_lat, text, proj, fontsize)


def _should_show_labels(
    stations_df: Optional[pd.DataFrame],
    extent: Tuple[float, float, float, float],
    show_labels: Optional[bool] = None,
) -> bool:
    """
    Determina si se deben mostrar etiquetas flotantes de texto o únicamente simbología limpia de estaciones.
    REGLA: En mapas donde el dominio sea regional/Centroamérica (amplitud > 5.0°), NUNCA se muestran
    etiquetas numéricas de estaciones para evitar saturación visual y permitir visualización limpia.
    El etiquetado se reserva EXCLUSIVAMENTE para dominios de países individuales (amplitud <= 5.0°).
    """
    if show_labels is False:
        return False
    if stations_df is None or len(stations_df) == 0:
        return False

    xmin, xmax, ymin, ymax = extent
    span_lon = abs(xmax - xmin)
    span_lat = abs(ymax - ymin)
    max_span = max(span_lon, span_lat)

    # Si el dominio es regional / Centroamérica (> 5.0°), NUNCA mostrar etiquetas
    if max_span > 5.0:
        return False

    # Para dominios de países individuales (<= 5.0°), mostrar etiquetas si no fue desactivado
    if show_labels is True:
        return True

    return len(stations_df) <= 40


def _place_text_no_overlap(
    ax, x: float, y: float, text: str, placed: List, dx: float = 0.15, dy: float = 0.15, max_tries: int = 12
):
    """Retrocompatibilidad: coloca etiqueta delegando a _place_station_label."""
    proj = ccrs.PlateCarree()
    _place_station_label(ax, x, y, text, placed, proj, d_lon=dx, d_lat=dy)



def _plot_side_by_side_stations(
    ax,
    stations_obs_year: Optional[pd.DataFrame],
    proj: ccrs.Projection,
    var: str,
    stat: str,
    cmap_name: str,
    norm,
    is_regional: bool,
    extent: Tuple[float, float, float, float],
    units: str,
    do_labels: bool,
) -> None:
    """Renderiza estaciones en mapas lado a lado con puntos limpios en escala regional o marcadores nítidos en país."""
    if stations_obs_year is None or stations_obs_year.empty:
        return

    cmap_obj = plt.get_cmap(cmap_name)

    for _, r in stations_obs_year.iterrows():
        if "lon" not in r or "lat" not in r or pd.isna(r["lon"]) or pd.isna(r["lat"]):
            continue
        lon = float(r["lon"])
        lat = float(r["lat"])
        val = _extract_station_value(r, var=var, stat=stat)

        if is_regional:
            # En Centroamérica y Caribe: puntos limpios de precisión (sin círculo de borde grande)
            if val is not None and np.isfinite(val) and float(val) > -90.0:
                facecolor = cmap_obj(norm(val))
            else:
                facecolor = "#1E293B"
            ax.plot(
                lon, lat,
                marker="o",
                markersize=2.2,
                markeredgewidth=0,
                markerfacecolor=facecolor,
                transform=proj,
                zorder=10,
            )
        else:
            # En mapa de país individual: marcadores nítidos para referencia
            ax.plot(
                lon, lat,
                marker="o",
                markersize=5.0,
                markeredgecolor="#0F172A",
                markerfacecolor="#FFFFFF",
                markeredgewidth=0.9,
                transform=proj,
                zorder=10,
            )

    if do_labels and not is_regional:
        plot_all_station_labels_harmonious(
            ax, stations_obs_year, extent, proj, var=var, stat=stat, units=units, fontsize=9.0
        )


def plot_side_by_side(
    da_left: xr.DataArray,
    da_right: xr.DataArray,
    year: str | int,
    stations_obs_year: pd.DataFrame,
    out_png: str,
    dem: Optional[xr.DataArray] = None,
    var: str = "precip",
    stat: str = "accum",
    bins: Optional[int] = None,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    cmap: Optional[str] = None,
    extent: Optional[Tuple[float, float, float, float]] = None,
    units: Optional[str] = None,
    show_labels: Optional[bool] = None,
) -> str:
    """
    Genera un mapa comparativo lado a lado (Original vs Corregido) en resolución 4K UHD con estaciones,
    calculando dinámicamente las dimensiones según la relación de aspecto del país/dominio.
    """
    da_left = rename_coords_latlon(da_left)
    da_right = rename_coords_latlon(da_right)

    proj = ccrs.PlateCarree()

    if extent is None:
        lon_vals = da_left["lon"].values
        lat_vals = da_left["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    dx_span = abs(extent[1] - extent[0])
    dy_span = abs(extent[3] - extent[2])
    is_regional = max(dx_span, dy_span) > 5.0
    do_labels = _should_show_labels(stations_obs_year, extent, show_labels)

    # Identificar si es precipitación o temperatura
    is_precip = var.lower() in ["precip", "pr", "rain", "lluvia"]

    # Cálculo dinámico de dimensiones en 4K UHD
    fig_w, fig_h = _figsize_from_extent(extent, base_height=5.2)
    fig = plt.figure(figsize=(fig_w * 2 + 0.8, fig_h + 2.0), dpi=350)

    # Esquema: Fila 0 = 2 Mapas lado a lado (wspace=0.015), Barra de colores centrada compacta abajo
    gs = GridSpec(1, 2, figure=fig, wspace=0.015)
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.18, top=0.82)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="#334155"
    )

    if is_precip:
        if cmap is None:
            cmap = COLOR_PALETTES.get("chirps_field", "chirps_rain_custom")
        if units is None:
            units = "mm"

        stat_str = str(stat).lower().strip()
        year_str = str(year).lower().strip()

        # Comprobar si corresponde a fecha diaria puntual (YYYY-MM-DD o YYYYMMDD)
        is_iso_date = bool(len(year_str) == 10 and year_str[4] == "-" and year_str[7] == "-") or bool(len(year_str) == 8 and year_str.isdigit())
        is_daily_mode = (
            stat_str in ["daily", "day", "doy", "doy_mean", "doy_max", "doy_min", "diario", "diaria"]
            or is_iso_date
        )

        # Comprobar si corresponde a meses, agrupación de meses o temporadas
        month_season_keywords = [
            "aso", "mjj", "djfm", "mes", "month", "season", "temporada", "trimestre", "semestre",
            "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"
        ]
        is_period_mode = (
            stat_str in ["season", "month", "months", "period", "seasonal", "monthly", "estacional", "mensual"]
            or any(kw in year_str for kw in month_season_keywords)
            or (isinstance(stat, str) and stat.upper() in ["ASO", "MJJ", "DJFM", "A", "N"])
        )

        # La escala diaria aplica estrictamente cuando es una fecha puntual (y no un período/meses)
        if is_period_mode:
            # 1. Escala mensual, agrupación de meses o estacional: 0 - 2000 mm con división de 100 mm
            levels = CHIRPS_PERIOD_LEVELS if (vmin is None and vmax is None and bins is None) else (
                np.linspace(vmin if vmin is not None else 0.0, vmax if vmax is not None else CHIRPS_PERIOD_VMAX, (bins or len(CHIRPS_RAIN_COLORS)) + 1)
            )
            ticks = CHIRPS_PERIOD_TICKS if (vmin is None and vmax is None and bins is None) else None
            stat_label_es = "Estacional" if ("season" in stat_str or any(s in year_str.upper() for s in ["ASO", "MJJ", "DJFM"])) else "Mensual"
            cbar_lbl = f"Precipitación {stat_label_es.lower()} ({units})"
        elif is_daily_mode:
            # 2. Escala diaria: 0 - 500 mm con división de 25 mm
            levels = CHIRPS_DAILY_LEVELS if (vmin is None and vmax is None and bins is None) else (
                np.linspace(vmin if vmin is not None else 0.0, vmax if vmax is not None else CHIRPS_DAILY_VMAX, (bins or len(CHIRPS_RAIN_COLORS)) + 1)
            )
            ticks = CHIRPS_DAILY_TICKS if (vmin is None and vmax is None and bins is None) else None
            stat_label_es = "Diaria" if stat_str == "daily" else ("Climatología DOY" if "doy" in stat_str else "Diaria")
            cbar_lbl = f"Precipitación diaria ({units})"
        else:
            # 3. Escala anual acumulada: 0 - 4000 mm con división de 200 mm
            levels = CHIRPS_ANNUAL_LEVELS if (vmin is None and vmax is None and bins is None) else (
                np.linspace(vmin if vmin is not None else 0.0, vmax if vmax is not None else CHIRPS_ANNUAL_VMAX, (bins or len(CHIRPS_RAIN_COLORS)) + 1)
            )
            ticks = CHIRPS_ANNUAL_TICKS if (vmin is None and vmax is None and bins is None) else None
            stat_label_es = "Acumulado Anual" if stat_str in ["accum", "anual", "annual"] else stat.capitalize()
            cbar_lbl = f"Precipitación anual acumulada ({units})" if stat_str in ["accum", "anual", "annual"] else f"Precipitación ({units})"

        norm = BoundaryNorm(
            levels,
            ncolors=len(CHIRPS_RAIN_COLORS) if (isinstance(cmap, str) and cmap in ("chirps_rain_custom", "YlGnBu")) else (getattr(cmap, "N", len(CHIRPS_RAIN_COLORS))),
            clip=False
        )

        # Relieve DEM opcional
        hs_masked, dem_extent = None, None
        if dem is not None:
            try:
                hs_masked, dem_extent = calculate_hillshade(dem)
            except Exception:
                hs_masked, dem_extent = None, None

        # Supertítulo general
        fig.suptitle(
            f"Comparación CHIRPS vs CHIRPS Corregido — {year}\nPuntos: {stat_label_es} OBSERVADO en estaciones meteorológicas",
            fontsize=14.5, fontweight="bold", y=0.96, color="#0F172A"
        )

        # Panel izquierdo
        ax1 = fig.add_subplot(gs[0, 0], projection=proj)
        ax1.coastlines(resolution="10m", linewidth=0.75, color="#1E293B")
        ax1.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.70, edgecolor="#1E293B")
        ax1.add_feature(states, linewidth=0.55, alpha=0.7)
        ax1.add_feature(cfeature.LAKES.with_scale("10m"), linewidth=0.35, edgecolor="#1E293B", facecolor="none")
        ax1.add_feature(cfeature.RIVERS.with_scale("10m"), linewidth=0.35, edgecolor="#3B82F6")
        ax1.set_extent(extent, crs=proj)

        gl1 = ax1.gridlines(draw_labels=True, linewidth=0.45, color="#94A3B8", alpha=0.55, linestyle="--")
        gl1.right_labels = False
        gl1.top_labels = False
        gl1.left_labels = True
        gl1.bottom_labels = True
        gl1.xlabel_style = {"size": 10.0, "weight": "bold"}
        gl1.ylabel_style = {"size": 10.0, "weight": "bold"}

        if hs_masked is not None:
            ax1.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

        mesh1 = ax1.pcolormesh(
            da_left["lon"].values, da_left["lat"].values, da_left.values,
            transform=proj, cmap=cmap, norm=norm, shading="auto",
            alpha=0.85 if hs_masked is not None else 1.0,
            zorder=1 if hs_masked is not None else None
        )

        _plot_side_by_side_stations(ax1, stations_obs_year, proj, "precip", stat, cmap, norm, is_regional, extent, units, do_labels)

        # Panel derecho
        ax2 = fig.add_subplot(gs[0, 1], projection=proj)
        ax2.coastlines(resolution="10m", linewidth=0.75, color="#1E293B")
        ax2.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.70, edgecolor="#1E293B")
        ax2.add_feature(states, linewidth=0.55, alpha=0.7)
        ax2.add_feature(cfeature.LAKES.with_scale("10m"), linewidth=0.35, edgecolor="#1E293B", facecolor="none")
        ax2.add_feature(cfeature.RIVERS.with_scale("10m"), linewidth=0.35, edgecolor="#3B82F6")
        ax2.set_extent(extent, crs=proj)

        gl2 = ax2.gridlines(draw_labels=True, linewidth=0.45, color="#94A3B8", alpha=0.55, linestyle="--")
        gl2.right_labels = True
        gl2.top_labels = False
        gl2.left_labels = False
        gl2.bottom_labels = True
        gl2.xlabel_style = {"size": 10.0, "weight": "bold"}
        gl2.ylabel_style = {"size": 10.0, "weight": "bold"}

        if hs_masked is not None:
            ax2.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

        mesh2 = ax2.pcolormesh(
            da_right["lon"].values, da_right["lat"].values, da_right.values,
            transform=proj, cmap=cmap, norm=norm, shading="auto",
            alpha=0.85 if hs_masked is not None else 1.0,
            zorder=1 if hs_masked is not None else None
        )

        _plot_side_by_side_stations(ax2, stations_obs_year, proj, "precip", stat, cmap, norm, is_regional, extent, units, do_labels)

        # Títulos de paneles
        ax1.set_title(f"CHIRPSv2 Original — {stat_label_es} {year}", fontsize=13.0, fontweight="bold", y=1.02, color="#1E293B")
        ax2.set_title(f"CHIRPSv2 Corregido (CDT) — {stat_label_es} {year}", fontsize=13.0, fontweight="bold", y=1.02, color="#1E293B")

        # Barra de colores centrada y compacta proporcional al mapa de mejora
        cax = fig.add_axes([0.375, 0.075, 0.25, 0.022])
        cbar = fig.colorbar(mesh2, cax=cax, orientation="horizontal", boundaries=levels, spacing="proportional")
        if ticks is not None:
            cbar.set_ticks(ticks)
        else:
            tick_step = (levels[-1] - levels[0]) / 10
            cbar.set_ticks(np.arange(levels[0], levels[-1] + 1e-6, tick_step))
        cbar.set_label(cbar_lbl, fontsize=10.0, fontweight="bold", labelpad=6)
        cbar.ax.tick_params(labelsize=9.0)

        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        fig.savefig(out_png, dpi=350, bbox_inches="tight")
        plt.close(fig)

    else:
        # Temperatura (CHIRTS)
        if bins is None:
            bins = CHIRTS_BINS
        if vmax is None:
            vmax = CHIRTS_VMAX
        if vmin is None:
            vmin = CHIRTS_VMIN
        if cmap is None:
            cmap = COLOR_PALETTES["chirts_field"]
        if units is None:
            units = "°C"

        levels = np.linspace(vmin, vmax, bins + 1)
        norm = BoundaryNorm(levels, ncolors=plt.get_cmap(cmap).N, clip=False)

        # Relieve DEM opcional
        hs_masked, dem_extent = None, None
        if dem is not None:
            hs_masked, dem_extent = calculate_hillshade(dem)

        # Supertítulo general
        fig.suptitle(
            f"Comparación CHIRTS vs CHIRTS Corregido — {year}\nPuntos: Estadístico OBSERVADO en estaciones meteorológicas",
            fontsize=14.5, fontweight="bold", y=0.96, color="#0F172A"
        )

        # Panel izquierdo
        ax1 = fig.add_subplot(gs[0, 0], projection=proj)
        ax1.coastlines(resolution="10m", linewidth=0.75, color="#1E293B")
        ax1.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.70, edgecolor="#1E293B")
        ax1.add_feature(states, linewidth=0.55, alpha=0.7)
        ax1.set_extent(extent, crs=proj)

        gl1 = ax1.gridlines(draw_labels=True, linewidth=0.45, color="#94A3B8", alpha=0.55, linestyle="--")
        gl1.right_labels = False
        gl1.top_labels = False
        gl1.left_labels = True
        gl1.bottom_labels = True
        gl1.xlabel_style = {"size": 10.0, "weight": "bold"}
        gl1.ylabel_style = {"size": 10.0, "weight": "bold"}

        if hs_masked is not None:
            ax1.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

        mesh1 = ax1.pcolormesh(
            da_left["lon"].values, da_left["lat"].values, da_left.values,
            transform=proj, cmap=cmap, norm=norm, shading="auto", alpha=0.80, zorder=1
        )

        _plot_side_by_side_stations(ax1, stations_obs_year, proj, var, stat, cmap, norm, is_regional, extent, units, do_labels)

        # Panel derecho
        ax2 = fig.add_subplot(gs[0, 1], projection=proj)
        ax2.coastlines(resolution="10m", linewidth=0.75, color="#1E293B")
        ax2.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.70, edgecolor="#1E293B")
        ax2.add_feature(states, linewidth=0.55, alpha=0.7)
        ax2.set_extent(extent, crs=proj)

        gl2 = ax2.gridlines(draw_labels=True, linewidth=0.45, color="#94A3B8", alpha=0.55, linestyle="--")
        gl2.xlabel_style = {"size": 10.0, "weight": "bold"}
        gl2.ylabel_style = {"size": 10.0, "weight": "bold"}
        gl2.right_labels = True
        gl2.top_labels = False
        gl2.left_labels = False
        gl2.bottom_labels = True

        if hs_masked is not None:
            ax2.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

        mesh2 = ax2.pcolormesh(
            da_right["lon"].values, da_right["lat"].values, da_right.values,
            transform=proj, cmap=cmap, norm=norm, shading="auto", alpha=0.80, zorder=1
        )

        _plot_side_by_side_stations(ax2, stations_obs_year, proj, var, stat, cmap, norm, is_regional, extent, units, do_labels)

        # Títulos de paneles
        ax1.set_title(f"CHIRTS Original — {var.upper()} {stat} ({year})", fontsize=13.0, fontweight="bold", y=1.02, color="#1E293B")
        ax2.set_title(f"CHIRTS Corregido (CDT) — {var.upper()} {stat} ({year})", fontsize=13.0, fontweight="bold", y=1.02, color="#1E293B")

        # Barra de colores centrada y compacta proporcional al mapa de mejora
        cax = fig.add_axes([0.375, 0.075, 0.25, 0.022])
        cbar = fig.colorbar(mesh2, cax=cax, orientation="horizontal", boundaries=levels, spacing="proportional")
        cbar.set_label(f"Temperatura ({units})", fontsize=10.0, fontweight="bold", labelpad=6)
        cbar.ax.tick_params(labelsize=9.0)

        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        fig.savefig(out_png, dpi=350, bbox_inches="tight")
        plt.close(fig)

    return out_png


def plot_delta_grid_field(
    da_raw: Optional[xr.DataArray],
    da_corr: Optional[xr.DataArray],
    dem: xr.DataArray,
    out_png: str,
    title: str,
    extent: Optional[Tuple[float, float, float, float]] = None,
    cmap: str = "RdBu_r",
    delta_override: Optional[xr.DataArray] = None,
    units: str = "°C",
    stations_df: Optional[pd.DataFrame] = None,
    show_labels: Optional[bool] = None,
) -> str:
    """
    Genera un mapa de campo continuo de ΔGRID = Corregido − Original,
    superponiendo opcionalmente los puntos de estación con sus valores numéricos de diferencia,
    ajustado a la relación de aspecto del país.
    """
    dem = rename_coords_latlon(dem)

    if delta_override is None:
        if da_raw is None or da_corr is None:
            raise ValueError("Se requieren da_raw y da_corr si delta_override no se suministra.")
        da_raw = rename_coords_latlon(da_raw)
        da_corr = rename_coords_latlon(da_corr)
        # Asegurar cálculo de diferencia estricto en celdas con datos válidos en ambos productos
        raw_vals = da_raw.where(np.isfinite(da_raw))
        corr_vals = da_corr.where(np.isfinite(da_corr))
        delta = (corr_vals - raw_vals).where(np.isfinite(corr_vals) & np.isfinite(raw_vals))
    else:
        delta = rename_coords_latlon(delta_override)
        delta = delta.where(np.isfinite(delta))

    proj = ccrs.PlateCarree()

    if extent is None:
        lon_vals = delta["lon"].values
        lat_vals = delta["lat"].values
        # Considerar únicamente coordenadas con datos válidos en delta
        valid_mask = np.isfinite(delta.values)
        if np.any(valid_mask):
            lons_mesh, lats_mesh = np.meshgrid(lon_vals, lat_vals) if valid_mask.shape == (len(lat_vals), len(lon_vals)) else (lon_vals, lat_vals)
            xmin = float(np.nanmin(lons_mesh[valid_mask]))
            xmax = float(np.nanmax(lons_mesh[valid_mask]))
            ymin = float(np.nanmin(lats_mesh[valid_mask]))
            ymax = float(np.nanmax(lats_mesh[valid_mask]))
        else:
            xmin = float(np.nanmin(lon_vals))
            xmax = float(np.nanmax(lon_vals))
            ymin = float(np.nanmin(lat_vals))
            ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    dx_span = abs(extent[1] - extent[0])
    dy_span = abs(extent[3] - extent[2])
    is_regional = max(dx_span, dy_span) > 5.0
    d_lon = max(0.04, dx_span * 0.025)
    d_lat = max(0.03, dy_span * 0.025)
    do_labels = _should_show_labels(stations_df, extent, show_labels)

    data = delta.values
    vmax = np.nanmax(np.abs(data))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.8)
    fig = plt.figure(figsize=(figsize[0], figsize[1] + 1.2), dpi=350)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.18, top=0.90)

    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=8)
    ax.set_xlabel("Longitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)
    ax.set_ylabel("Latitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)

    ax.coastlines(resolution="10m", linewidth=0.7, color="#1E293B")
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.65, edgecolor="#1E293B")

    states = cfeature.NaturalEarthFeature(category="cultural", name="admin_1_states_provinces_lines", scale="10m", facecolor="none", edgecolor="#334155")
    ax.add_feature(states, linewidth=0.5, alpha=0.7)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="#94A3B8", alpha=0.55, linestyle="--")
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8.5, "weight": "bold"}
    gl.ylabel_style = {"size": 8.5, "weight": "bold"}

    hs_masked, dem_extent = calculate_hillshade(dem)
    ax.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

    mesh = ax.pcolormesh(
        delta["lon"].values, delta["lat"].values, data,
        transform=proj, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto", alpha=0.85, zorder=1
    )

    # Superposición de estaciones con valor numérico de la diferencia o simbología limpia
    if stations_df is not None and not stations_df.empty and not is_regional:
        for _, r in stations_df.iterrows():
            if "lon" not in r or "lat" not in r or pd.isna(r["lon"]) or pd.isna(r["lat"]):
                continue
            x, y = float(r["lon"]), float(r["lat"])
            ax.plot(x, y, marker="o", markersize=4.5, markeredgecolor="#0F172A", markerfacecolor="#FFFFFF", markeredgewidth=1.0, transform=proj, zorder=8)
        if do_labels:
            plot_all_station_labels_harmonious(ax, stations_df, extent, proj, value_col="delta_grid", delta_raster=delta, units=units)

    cax = fig.add_axes([0.25, 0.08, 0.50, 0.024])
    cbar = fig.colorbar(mesh, cax=cax, orientation="horizontal")
    cbar.set_label(f"Diferencia espacial (Corregido − Original) [{units}]", fontsize=9.5, fontweight="bold", labelpad=6)
    cbar.ax.tick_params(labelsize=8.5)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=350)
    plt.close(fig)
    return out_png


def plot_delta_grid_at_stations(
    stations_df: pd.DataFrame,
    dem: xr.DataArray,
    out_png: str,
    title: str,
    extent: Optional[Tuple[float, float, float, float]] = None,
    cmap: str = "RdBu_r",
    units: str = "°C",
    show_labels: Optional[bool] = None,
) -> str:
    """
    Genera un mapa de puntos de ΔGRID en estaciones ajustado al aspect ratio del territorio.
    """
    proj = ccrs.PlateCarree()
    dem = rename_coords_latlon(dem)

    lats = stations_df["lat"].values
    lons = stations_df["lon"].values
    delta = stations_df["delta_grid"].values

    if extent is None:
        lon_vals = dem["lon"].values
        lat_vals = dem["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    dx_span = abs(extent[1] - extent[0])
    dy_span = abs(extent[3] - extent[2])
    d_lon = max(0.04, dx_span * 0.025)
    d_lat = max(0.03, dy_span * 0.025)
    do_labels = _should_show_labels(stations_df, extent, show_labels)

    vmax = np.nanmax(np.abs(delta))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.8)
    fig = plt.figure(figsize=(figsize[0], figsize[1] + 1.2), dpi=350)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.18, top=0.90)

    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=8)
    ax.set_xlabel("Longitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)
    ax.set_ylabel("Latitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)

    ax.coastlines(resolution="10m", linewidth=0.7, color="#1E293B")
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.65, edgecolor="#1E293B")

    states = cfeature.NaturalEarthFeature(category="cultural", name="admin_1_states_provinces_lines", scale="10m", facecolor="none", edgecolor="#334155")
    ax.add_feature(states, linewidth=0.5, alpha=0.7)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="#94A3B8", alpha=0.55, linestyle="--")
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8.5, "weight": "bold"}
    gl.ylabel_style = {"size": 8.5, "weight": "bold"}

    hs_masked, dem_extent = calculate_hillshade(dem)
    ax.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

    marker_size = 36 if do_labels else 24
    sc = ax.scatter(lons, lats, c=delta, cmap=cmap, vmin=vmin, vmax=vmax, s=marker_size, edgecolors="#0F172A", linewidths=0.5, transform=proj, zorder=3)
    if do_labels:
        plot_all_station_labels_harmonious(ax, stations_df, extent, proj, value_col="delta_grid", units=units)

    cax = fig.add_axes([0.25, 0.08, 0.50, 0.024])
    cbar = fig.colorbar(sc, cax=cax, orientation="horizontal")
    cbar.set_label(f"Diferencia espacial (Corregido − Original) [{units}]", fontsize=9.5, fontweight="bold", labelpad=6)
    cbar.ax.tick_params(labelsize=8.5)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=350)
    plt.close(fig)
    return out_png


def plot_residual_corr_at_stations_with_dem(
    stations_df: pd.DataFrame,
    dem: xr.DataArray,
    out_png: str,
    title: str,
    extent: Optional[Tuple[float, float, float, float]] = None,
    cmap: str = "RdBu_r",
    units: str = "°C",
    value_col: str = "residual_corr",
    show_labels: Optional[bool] = None,
) -> str:
    """
    Genera un mapa de puntos del residuo de la grilla corregida en estaciones: (Grid_corr - Obs).
    """
    proj = ccrs.PlateCarree()
    dem = rename_coords_latlon(dem)

    lats = stations_df["lat"].values
    lons = stations_df["lon"].values
    vals = stations_df[value_col].astype(float).values

    if extent is None:
        lon_vals = dem["lon"].values
        lat_vals = dem["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    dx_span = abs(extent[1] - extent[0])
    dy_span = abs(extent[3] - extent[2])
    d_lon = max(0.04, dx_span * 0.025)
    d_lat = max(0.03, dy_span * 0.025)
    do_labels = _should_show_labels(stations_df, extent, show_labels)

    vmax = np.nanmax(np.abs(vals))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.8)
    fig = plt.figure(figsize=(figsize[0], figsize[1] + 1.2), dpi=300)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.18, top=0.90)

    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=8)
    ax.set_xlabel("Longitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)
    ax.set_ylabel("Latitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)

    ax.coastlines(resolution="10m", linewidth=0.7, color="#1E293B")
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.65, edgecolor="#1E293B")

    states = cfeature.NaturalEarthFeature(category="cultural", name="admin_1_states_provinces_lines", scale="10m", facecolor="none", edgecolor="#334155")
    ax.add_feature(states, linewidth=0.5, alpha=0.7)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="#94A3B8", alpha=0.55, linestyle="--")
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8.5, "weight": "bold"}
    gl.ylabel_style = {"size": 8.5, "weight": "bold"}

    hs_masked, dem_extent = calculate_hillshade(dem)
    ax.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

    marker_size = 36 if do_labels else 24
    sc = ax.scatter(lons, lats, c=vals, cmap=cmap, vmin=vmin, vmax=vmax, s=marker_size, edgecolors="#0F172A", linewidths=0.5, transform=proj, zorder=3)

    cax = fig.add_axes([0.25, 0.08, 0.50, 0.024])
    cbar = fig.colorbar(sc, cax=cax, orientation="horizontal")
    cbar.set_label(f"Residuo corregido = Grid_corr − Obs [{units}]", fontsize=9.5, fontweight="bold", labelpad=6)
    cbar.ax.tick_params(labelsize=8.5)

    if do_labels:
        plot_all_station_labels_harmonious(ax, stations_df, extent, proj, value_col=value_col, units=units)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_png


def plot_improvement_at_stations_with_dem(
    stations_df: pd.DataFrame,
    dem: xr.DataArray,
    out_png: str,
    title: str,
    extent: Optional[Tuple[float, float, float, float]] = None,
    cmap: str = "RdBu_r",
    show_labels: Optional[bool] = None,
) -> str:
    """
    Genera un mapa de puntos de mejora porcentual de RMSE en estaciones.
    """
    proj = ccrs.PlateCarree()
    dem = rename_coords_latlon(dem)

    lats = stations_df["lat"].values
    lons = stations_df["lon"].values
    col = "improvement_RMSE_pct" if "improvement_RMSE_pct" in stations_df.columns else ("improvement_pct" if "improvement_pct" in stations_df.columns else stations_df.columns[2])
    values = stations_df[col].values.astype(float)

    if extent is None:
        lon_vals = dem["lon"].values
        lat_vals = dem["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    dx_span = abs(extent[1] - extent[0])
    dy_span = abs(extent[3] - extent[2])
    d_lon = max(0.04, dx_span * 0.025)
    d_lat = max(0.03, dy_span * 0.025)
    do_labels = _should_show_labels(stations_df, extent, show_labels)

    vmax = np.nanmax(np.abs(values))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 10.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.8)
    fig = plt.figure(figsize=(figsize[0], figsize[1] + 1.2), dpi=300)
    fig.subplots_adjust(left=0.08, right=0.92, bottom=0.18, top=0.90)

    ax = fig.add_subplot(1, 1, 1, projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=8)
    ax.set_xlabel("Longitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)
    ax.set_ylabel("Latitud [°]", fontsize=9.5, fontweight="bold", labelpad=5)

    ax.coastlines(resolution="10m", linewidth=0.7, color="#1E293B")
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.65, edgecolor="#1E293B")

    states = cfeature.NaturalEarthFeature(category="cultural", name="admin_1_states_provinces_lines", scale="10m", facecolor="none", edgecolor="#334155")
    ax.add_feature(states, linewidth=0.5, alpha=0.7)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="#94A3B8", alpha=0.55, linestyle="--")
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8.5, "weight": "bold"}
    gl.ylabel_style = {"size": 8.5, "weight": "bold"}

    hs_masked, dem_extent = calculate_hillshade(dem)
    ax.imshow(hs_masked, extent=dem_extent, origin="lower", transform=proj, cmap="gray", alpha=0.5, zorder=0)

    marker_size = 36 if do_labels else 24
    sc = ax.scatter(lons, lats, c=values, cmap=cmap, vmin=vmin, vmax=vmax, s=marker_size, edgecolors="#0F172A", linewidths=0.5, transform=proj, zorder=3)

    cax = fig.add_axes([0.25, 0.08, 0.50, 0.024])
    cbar = fig.colorbar(sc, cax=cax, orientation="horizontal")
    cbar.set_label("Mejora relativa de RMSE [%] (Positivo = mejora, Negativo = empeora)", fontsize=9.5, fontweight="bold", labelpad=6)
    cbar.ax.tick_params(labelsize=8.5)

    if do_labels:
        plot_all_station_labels_harmonious(ax, stations_df, extent, proj, value_col=col, is_pct=True)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return out_png
