# -*- coding: utf-8 -*-
"""
Application services for orchestrating CHIRPS and CHIRTS scientific processing workflows.
"""

import os
import glob
import re
import shutil
import stat
import gc
import time
import datetime
import json
from typing import Callable, Optional, List, Dict
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
import xarray as xr

from .models import (
    AnalysisRequest,
    AnalysisResult,
    ProductType,
    ProcessingMode,
    StatType,
    PeriodType,
)
from .validators import validate_analysis_request
from ..config.constants import SEASONS, MONTH_NAMES_ES
from ..io.cdt_parser import parse_cdt_csv
from ..io.netcdf_loader import (
    load_daily_chirts_raw,
    load_daily_chirts_corr,
    load_dem_dataset,
    rename_coords_latlon,
)
from ..io.exporters import (
    export_cmp_csv,
    build_global_station_csv,
    build_station_improvement_csv,
)
from ..core.metrics import (
    compute_annual_metrics_from_csv,
    compute_station_metrics_global,
    compute_station_metrics_from_csv,
    summarize_daily_global,
    summarize_daily_by_station,
)
from ..core.spatial import (
    load_daily_sum_for_year,
    annual_station_accum,
    load_annual_temp_stat,
    annual_station_stat,
)
from ..core.climatology import (
    get_dates_for_period,
    make_period_title,
    load_period_stat_raw,
    load_period_stat_corr,
    period_station_stat,
    compute_climatology_doy_by_station,
    process_year_worker,
)
from ..visualization.maps import (
    plot_side_by_side,
    plot_delta_grid_field,
    plot_delta_grid_at_stations,
    plot_residual_corr_at_stations_with_dem,
    plot_improvement_at_stations_with_dem,
)
from ..visualization.plots import (
    plot_rmse_bars,
    plot_kge_components,
    plot_boxplot_errors,
    plot_boxplot_errors_single,
    plot_boxplot_rmse_by_station,
    plot_boxplot_improvement_pct_by_station,
    plot_scatter_obs_vs_grid,
    plot_scatter_obs_vs_grid_single,
    plot_scatter_rmse_raw_vs_corr,
    plot_scatter_rmse_vs_improvement,
    plot_climatology_doy_station,
    plot_climatology_doy_station_tripanel,
)

ProgressCallback = Optional[Callable[[float, str], None]]
CancelCheck = Optional[Callable[[], bool]]


def _log_msg(msg: str) -> str:
    """Añade timestamp a la línea de registro."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    return f"[{ts}] {msg}"


def generate_doy_climatology_for_stations(
    df_obs_long: pd.DataFrame,
    req: AnalysisRequest,
    res: AnalysisResult,
    out_clim_dir: str,
    progress: ProgressCallback = None,
    cancel_check: CancelCheck = None,
    pct_start: float = 0.85,
    pct_end: float = 0.98,
) -> bool:
    """
    Construye la serie diaria y genera el ciclo climatológico diario por estación.
    Adapta el cálculo y los gráficos dinámicamente según el alcance temporal:
    - Serie multianual completa (DOY 1–365)
    - Un solo año (DOY 1–365 del año seleccionado)
    - Temporadas climáticas (ej. ASO, DJFM, MAM, etc.)
    - Mes individual o agrupación de meses (ej. Mayo, MJJ)
    """
    if df_obs_long is None or df_obs_long.empty:
        return False

    is_precip = "chirps" in req.product.value.lower() or "precip" in str(req.var).lower()
    var = "precip" if is_precip else req.var
    prefix_raw = req.prefix_original if (req.prefix_original and req.prefix_original != "temp_") else ("precip_" if is_precip else req.prefix_original)

    all_years = sorted(df_obs_long["year"].unique()) if "year" in df_obs_long.columns else []
    if not all_years and "date" in df_obs_long.columns:
        df_obs_long["year"] = pd.to_datetime(df_obs_long["date"]).dt.year
        all_years = sorted(df_obs_long["year"].unique())

    yini = req.yini or (all_years[0] if all_years else 1991)
    yend = req.yend or (all_years[-1] if all_years else 2020)
    years = [y for y in all_years if yini <= y <= yend]
    if not years:
        years = all_years if all_years else [yini]

    # Determinar si es modo Período (Temporada o Mes/Agrupación de Meses) o Modo Anual
    is_period_mode = (
        req.mode == ProcessingMode.PERIOD
        or getattr(req, "period_type", None) in ["season", "months", PeriodType.SEASON, PeriodType.MONTHS]
    )
    months_order: Optional[List[int]] = None
    period_title_label = ""
    period_type_val = req.period_type.value if hasattr(req.period_type, "value") else str(getattr(req, "period_type", ""))

    if is_period_mode:
        if period_type_val == "season" and req.season:
            season_cfg = SEASONS.get(req.season, {})
            months_order = season_cfg.get("months", [])
            period_title_label = req.season
        elif period_type_val == "months" and req.months:
            months_raw = req.months if isinstance(req.months, (list, tuple)) else [req.months]
            months_order = [int(m) for m in months_raw]
            if len(months_order) == 1:
                period_title_label = MONTH_NAMES_ES.get(months_order[0], f"Mes {months_order[0]}")
            else:
                period_title_label = f"{MONTH_NAMES_ES.get(months_order[0], '')[:3]}–{MONTH_NAMES_ES.get(months_order[-1], '')[:3]}"
        else:
            period_title_label = "Período"
    else:
        period_title_label = "Anual"

    os.makedirs(out_clim_dir, exist_ok=True)
    out_station_dir = os.path.join(out_clim_dir, "by_station")
    clim_base_dir = os.path.join(out_clim_dir, "climatology_doy")
    os.makedirs(out_station_dir, exist_ok=True)
    os.makedirs(clim_base_dir, exist_ok=True)

    is_single_year = len(years) == 1
    years_label = f"{years[0]}" if is_single_year else f"{years[0]}–{years[-1]}"

    daily_csv = os.path.join(out_clim_dir, f"daily_timeseries_{var}_{years[0]}_{years[-1]}.csv")
    df_daily: Optional[pd.DataFrame] = None

    if os.path.exists(daily_csv) and os.path.getsize(daily_csv) > 100:
        try:
            df_loaded = pd.read_csv(daily_csv)
            req_cols = {"date", "station_id", "obs", "raw", "corr"}
            if req_cols.issubset(set(df_loaded.columns)) and not df_loaded.empty:
                df_daily = df_loaded
                reuse_msg = f"Reutilizando serie diaria existente: {os.path.basename(daily_csv)}"
                res.execution_logs.append(_log_msg(reuse_msg))
                if progress:
                    progress(pct_start, reuse_msg)
        except Exception:
            df_daily = None

    if df_daily is None:
        if is_period_mode:
            doy_init_msg = f"Construyendo serie diaria para Climatología ({period_title_label}, {len(years)} {'año' if is_single_year else 'años'})..."
        else:
            doy_init_msg = f"Construyendo serie diaria para Climatología DOY 1–365 ({len(years)} {'año' if is_single_year else 'años'})..."

        if progress:
            progress(pct_start, doy_init_msg)
        res.execution_logs.append(_log_msg(doy_init_msg))

        # Filtrar fechas por período si aplica
        df_obs_work = df_obs_long.copy()
        df_obs_work["date_str"] = df_obs_work["date"].astype(str).str.replace("-", "")

        tasks = []
        for y in years:
            if is_period_mode:
                try:
                    p_type_arg = req.period_type.value if hasattr(req.period_type, "value") else str(req.period_type)
                    dates_y = get_dates_for_period(year=y, period_type=p_type_arg, season=req.season, months=req.months)
                    df_year_slice = df_obs_work[df_obs_work["date_str"].isin(dates_y)]
                except Exception:
                    df_year_slice = df_obs_work[df_obs_work["year"] == y]
            else:
                df_year_slice = df_obs_work[df_obs_work["year"] == y]

            if not df_year_slice.empty:
                tasks.append((y, df_year_slice, req.dir_original, req.dir_merged, var, prefix_raw))

        if not tasks:
            tasks = [
                (y, df_obs_work[df_obs_work["year"] == y], req.dir_original, req.dir_merged, var, prefix_raw)
                for y in years
            ]

        try:
            with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as ex:
                dfs = list(ex.map(process_year_worker, tasks))
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Procesando serie diaria secuencialmente por: {e}"))
            dfs = [process_year_worker(t) for t in tasks]

        if not dfs:
            return False

        dfs = [d for d in dfs if d is not None and not d.empty]
        if not dfs:
            return False

        df_daily = pd.concat(dfs, ignore_index=True)
        if df_daily.empty:
            return False

        df_daily = df_daily.sort_values(["station_id", "date"]).reset_index(drop=True)
        df_daily.to_csv(daily_csv, index=False)

    if daily_csv not in res.generated_csvs:
        res.generated_csvs.append(daily_csv)

    for sid, g in df_daily.groupby("station_id"):
        out_csv_st = os.path.join(out_station_dir, f"daily_timeseries_{var}_station_{sid}.csv")
        g.sort_values("date").to_csv(out_csv_st, index=False)
        if out_csv_st not in res.generated_csvs:
            res.generated_csvs.append(out_csv_st)

    station_files = [f for f in os.listdir(out_station_dir) if f.endswith(".csv")]
    total_st = len(station_files)

    for idx, fname in enumerate(station_files):
        if cancel_check and cancel_check():
            cancel_msg = f"🛑 Proceso cancelado por el usuario en DOY estación {idx+1}/{total_st}."
            res.execution_logs.append(_log_msg(cancel_msg))
            res.error_message = cancel_msg
            res.success = False
            if progress:
                progress(1.0, cancel_msg)
            return False

        cur_pct = pct_start + (pct_end - pct_start) * ((idx + 1) / max(total_st, 1))
        sid = fname.split("_")[-1].replace(".csv", "")
        doy_msg = f"Calculando ciclo climatológico ({period_title_label} - {var.upper()}) para estación {sid} ({idx+1}/{total_st})..."
        if progress:
            progress(cur_pct, doy_msg)
        res.execution_logs.append(_log_msg(doy_msg))

        csv_st_path = os.path.join(out_station_dir, fname)
        st_dir = os.path.join(clim_base_dir, f"station_{sid}")
        os.makedirs(st_dir, exist_ok=True)

        csv_clim = os.path.join(st_dir, f"clim_doy_{var}_station_{sid}.csv")
        compute_climatology_doy_by_station(csv_st_path, var, csv_clim, drop_feb29=True, months_order=months_order)
        if csv_clim not in res.generated_csvs:
            res.generated_csvs.append(csv_clim)
        if sid not in res.doy_stations:
            res.doy_stations.append(sid)

        if sid not in res.doy_plots_by_station:
            res.doy_plots_by_station[sid] = {}

        # Construir títulos descriptivos y context-aware
        if is_period_mode:
            is_cross_season = bool(months_order and months_order[0] == 12 and any(m < 12 for m in months_order[1:]))
            if is_cross_season:
                first_m_name = MONTH_NAMES_ES.get(months_order[0], "Dic")[:3].capitalize()
                last_m_name = MONTH_NAMES_ES.get(months_order[-1], "Mar")[:3].capitalize()
                if is_single_year:
                    season_detail = f"{req.season or 'Período'} ({first_m_name} {years[0]-1} – {last_m_name} {years[0]})"
                else:
                    season_detail = f"{req.season or 'Período'} ({first_m_name} [año ant.] – {last_m_name} [año eval.]) ({years_label})"
            else:
                season_detail = f"{period_title_label} {years_label}" if is_single_year else f"{period_title_label} ({years_label})"

            if is_single_year:
                title_tri = f"Serie Diaria — Estación: {sid} — {season_detail}"
            else:
                title_tri = f"Ciclo Climatológico Diario Multianual — Estación: {sid} — {season_detail}"
        else:
            if is_single_year:
                title_tri = f"Serie Diaria (DOY 1–365) — Estación: {sid} — Año {years_label}"
            else:
                title_tri = f"Ciclo Climatológico Diario Multianual (DOY 1–365) — Estación: {sid} ({years_label})"

        stats_to_plot = ["accum", "mean", "max"] if is_precip else ["mean", "max", "min"]
        for stat_name in stats_to_plot:
            out_png = os.path.join(st_dir, f"clim_doy_{var}_{stat_name}_station_{sid}.png")
            stat_display = "Acumulado" if stat_name == "accum" else ("Promedio" if stat_name == "mean" else ("Máximo" if stat_name == "max" else "Mínimo"))

            if is_period_mode:
                if is_single_year:
                    title_stat = f"{stat_display} Diario — Estación: {sid} — {season_detail}"
                else:
                    title_stat = f"{stat_display} Climatológico — Estación: {sid} — {season_detail}"
            else:
                if is_single_year:
                    title_stat = f"{stat_display} (DOY 1–365) — Estación: {sid} — Año {years_label}"
                else:
                    title_stat = f"{stat_display} Climatológico (DOY 1–365) — Estación: {sid} ({years_label})"

            plot_climatology_doy_station(csv_clim, var, sid, out_png, stat=stat_name, title=title_stat)
            if out_png not in res.generated_plots:
                res.generated_plots.append(out_png)
            res.doy_plots_by_station[sid][stat_name] = out_png

        out_png_tri = os.path.join(st_dir, f"clim_doy_{var}_tripanel_station_{sid}.png")
        plot_climatology_doy_station_tripanel(csv_clim, var, sid, out_png_tri, title=title_tri)
        if out_png_tri not in res.generated_plots:
            res.generated_plots.append(out_png_tri)
        res.doy_plots_by_station[sid]["tripanel"] = out_png_tri

    # Resúmenes globales y por estación
    summary_global = summarize_daily_global(df_daily, var)
    summary_global_csv = os.path.join(out_clim_dir, f"summary_daily_global_{var}.csv")
    summary_global.to_csv(summary_global_csv, index=False, float_format="%.4f")
    if summary_global_csv not in res.generated_csvs:
        res.generated_csvs.append(summary_global_csv)
    if res.summary_global_df is None:
        res.summary_global_df = summary_global

    summary_station = summarize_daily_by_station(df_daily, var=var)
    summary_station_csv = os.path.join(out_clim_dir, f"summary_daily_by_station_{var}.csv")
    summary_station.to_csv(summary_station_csv, index=False, float_format="%.4f")
    if summary_station_csv not in res.generated_csvs:
        res.generated_csvs.append(summary_station_csv)
    if res.summary_station_df is None:
        res.summary_station_df = summary_station
    if res.rankings_df is None:
        res.rankings_df = summary_station

    return True


class ChirpsService:
    """Servicio de orquestación para análisis y visualización de CHIRPS (precipitación)."""

    def run(
        self,
        req: AnalysisRequest,
        progress_callback: ProgressCallback = None,
        progress: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> AnalysisResult:
        cb = progress_callback or progress
        res = AnalysisResult(output_dir=req.out_dir, request=req)
        try:
            init_msg = "Inicializando análisis CHIRPS y cargando datos..."
            if cb:
                cb(0.02, init_msg)
            res.execution_logs.append(_log_msg(init_msg))

            meta, df_obs_long = parse_cdt_csv(req.csv_path, "precip_station")
            df_obs_long["date"] = pd.to_datetime(df_obs_long["date"], format="%Y%m%d")

            # Enrutamiento según modo de operación
            if req.mode == ProcessingMode.DAILY_EVAL:
                return self._run_daily_eval(req, df_obs_long, res, cb, cancel_check=cancel_check)
            elif req.mode == ProcessingMode.DAILY:
                return self._run_daily(req, df_obs_long, res, cb, cancel_check=cancel_check)
            elif req.mode == ProcessingMode.PERIOD:
                return self._run_period(req, df_obs_long, res, cb, cancel_check=cancel_check)
            else:
                return self._run_annual(req, df_obs_long, res, cb, cancel_check=cancel_check)

        except Exception as e:
            err_msg = f"ERROR: {str(e)}"
            res.success = False
            res.error_message = str(e)
            res.execution_logs.append(_log_msg(err_msg))
            return res

    def _run_daily_eval(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        if progress:
            progress(0.05, "Iniciando evaluación diaria multianual para CHIRPS...")
        res.execution_logs.append(_log_msg("Iniciando evaluación diaria multianual (CHIRPS precipitación)..."))

        years = sorted(df_obs_long["year"].unique())
        out_dir = os.path.join(req.out_dir, "precip", "daily_eval")
        os.makedirs(out_dir, exist_ok=True)

        success = generate_doy_climatology_for_stations(
            df_obs_long=df_obs_long,
            req=req,
            res=res,
            out_clim_dir=out_dir,
            progress=progress,
            cancel_check=cancel_check,
            pct_start=0.10,
            pct_end=0.85,
        )
        if not success and res.error_message:
            return res

        daily_csvs = [c for c in res.generated_csvs if "daily_timeseries_precip_" in os.path.basename(c)]
        if not daily_csvs:
            res.error_message = "No se generó la serie diaria consolidada."
            res.success = False
            return res

        df_daily = pd.read_csv(daily_csvs[0])
        if "year" not in df_daily.columns:
            df_daily["year"] = pd.to_datetime(df_daily["date"].astype(str), format="%Y%m%d").dt.year

        summary_station = res.summary_station_df
        if summary_station is not None:
            rank_csv = os.path.join(out_dir, "ranking_stations_precip_daily_eval.csv")
            summary_station.to_csv(rank_csv, index=False, float_format="%.4f")
            if rank_csv not in res.generated_csvs:
                res.generated_csvs.append(rank_csv)

        # Métricas anuales a partir de la serie diaria multianual
        annual_rows = []
        for y in years:
            df_y = df_daily[df_daily["year"] == y]
            if not df_y.empty:
                m_y = compute_all_station_metrics(
                    df_y["obs"].values, df_y["raw"].values, df_y["corr"].values,
                    is_precip=True
                )
                m_y["year"] = int(y)
                annual_rows.append(m_y)
        if annual_rows:
            df_annual = pd.DataFrame(annual_rows)
            if "year" in df_annual.columns:
                cols = ["year"] + [c for c in df_annual.columns if c != "year"]
                df_annual = df_annual[cols]
            metrics_annual_csv = os.path.join(out_dir, "metrics_annual_precip_daily_eval.csv")
            df_annual.to_csv(metrics_annual_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(metrics_annual_csv)
            res.metrics_df = df_annual

            png_rmse = plot_rmse_bars(df_annual, "precip", "daily_eval", out_dir)
            res.generated_plots.append(png_rmse)

            png_kge = plot_kge_components(df_annual, "precip", "daily_eval", out_dir)
            if png_kge:
                res.generated_plots.append(png_kge)
        else:
            res.metrics_df = summary_global

        # Gráficos diagnósticos en estaciones (Boxplot y Scatter global de la serie)
        out_box = os.path.join(out_dir, "boxplot_errors_precip_daily_eval.png")
        plot_boxplot_errors_single(df_daily, "precip", "daily_eval", out_box)
        res.generated_plots.append(out_box)

        out_sc = os.path.join(out_dir, "scatter_obs_vs_grid_precip_daily_eval.png")
        plot_scatter_obs_vs_grid_single(df_daily, "precip", "daily_eval", out_sc)
        res.generated_plots.append(out_sc)

        # Generar scatter plots y boxplots por período/año para estaciones
        is_period_mode = (
            req.mode == ProcessingMode.PERIOD
            or (hasattr(req, "period_type") and req.period_type in [PeriodType.SEASON, PeriodType.MONTHS])
        )
        p_type_arg = req.period_type.value if hasattr(req.period_type, "value") else str(getattr(req, "period_type", "annual"))

        for y in years:
            if is_period_mode:
                try:
                    dates_y = get_dates_for_period(year=y, period_type=p_type_arg, season=req.season, months=req.months)
                    df_slice = df_daily[df_daily["date"].astype(str).str.replace("-", "").isin(dates_y)]
                    if req.period_type == PeriodType.SEASON:
                        label = f"{req.season.lower()}_{y}"
                        title_label = make_period_title("season", y, season=req.season)
                    else:
                        m_list = req.months if isinstance(req.months, (list, tuple)) else [req.months]
                        m_names = [MONTH_NAMES_ES[int(m)].lower() for m in m_list]
                        label = f"{'-'.join(m_names)}_{y}"
                        title_label = make_period_title("months", y, months=m_list)
                except Exception:
                    df_slice = df_daily[df_daily["year"] == y]
                    label = f"{y}"
                    title_label = f"Año {y}"
            else:
                df_slice = df_daily[df_daily["year"] == y]
                label = f"{y}"
                title_label = f"Año {y}"

            if df_slice.empty:
                continue

            for stat_name in ["accum", "mean", "max"]:
                if stat_name == "accum":
                    df_st_agg = df_slice.groupby(["station_id", "lon", "lat"]).agg({"obs": "sum", "raw": "sum", "corr": "sum"}).reset_index()
                elif stat_name == "mean":
                    df_st_agg = df_slice.groupby(["station_id", "lon", "lat"]).agg({"obs": "mean", "raw": "mean", "corr": "mean"}).reset_index()
                else:
                    df_st_agg = df_slice.groupby(["station_id", "lon", "lat"]).agg({"obs": "max", "raw": "max", "corr": "max"}).reset_index()

                out_sc_p = os.path.join(out_dir, f"scatter_obs_vs_grid_precip_{stat_name}_{label}.png")
                plot_scatter_obs_vs_grid_single(
                    df_st_agg, "precip", stat_name, out_sc_p,
                    title=f"CHIRPS {stat_name.capitalize()} — Observado vs Rejilla Satelital — {title_label}"
                )
                if out_sc_p not in res.generated_plots:
                    res.generated_plots.append(out_sc_p)

                out_box_p = os.path.join(out_dir, f"boxplot_errors_precip_{stat_name}_{label}.png")
                plot_boxplot_errors_single(df_st_agg, "precip", stat_name, out_box_p)
                if out_box_p not in res.generated_plots:
                    res.generated_plots.append(out_box_p)

        # Mapa de mejora en estaciones sobre DEM
        dem = None
        if req.dem_path and os.path.exists(req.dem_path):
            try:
                dem = load_dem_dataset(req.dem_path)
            except Exception:
                dem = None

        imp_rows = []
        for (sid, lat, lon), g in df_daily.groupby(["station_id", "lat", "lon"]):
            o = g["obs"].values
            r = g["raw"].values
            c = g["corr"].values
            m = np.isfinite(o) & np.isfinite(r) & np.isfinite(c)
            if np.sum(m) >= 2:
                rmse_r = float(np.sqrt(np.mean((r[m] - o[m])**2)))
                rmse_c = float(np.sqrt(np.mean((c[m] - o[m])**2)))
                delta_rmse = rmse_r - rmse_c
                den = max(rmse_r, rmse_c, 1e-6)
                imp_pct = 100.0 * delta_rmse / den
                imp_rows.append({
                    "station_id": sid,
                    "lat": lat,
                    "lon": lon,
                    "RMSE_raw": rmse_r,
                    "RMSE_corr": rmse_c,
                    "delta_RMSE": delta_rmse,
                    "improvement_RMSE_pct": imp_pct,
                    "improvement_pct": imp_pct,
                })
        if imp_rows:
            df_imp = pd.DataFrame(imp_rows)
            imp_csv = os.path.join(out_dir, "improvement_stations_precip_daily_eval_RMSE.csv")
            df_imp.to_csv(imp_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(imp_csv)

            out_map_imp = os.path.join(out_dir, "improvement_RMSEpct_stations_precip_daily_eval.png")
            extent_plot = req.extent or (
                float(df_daily["lon"].min()) - 0.2, float(df_daily["lon"].max()) + 0.2,
                float(df_daily["lat"].min()) - 0.2, float(df_daily["lat"].max()) + 0.2
            )
            plot_improvement_at_stations_with_dem(
                df_imp, dem, out_map_imp,
                "CHIRPS — Mejora vs estaciones (Serie Diaria Multianual)",
                extent=extent_plot, show_labels=req.show_labels
            )
            res.generated_maps.append(out_map_imp)

        fin_msg = "Evaluación diaria multianual de CHIRPS completada exitosamente."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res

    def _run_daily(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        date = req.date_str
        day_msg = f"Procesando mapa diario CHIRPS para fecha {date}..."
        if progress:
            progress(0.10, day_msg)
        res.execution_logs.append(_log_msg(day_msg))

        dem = None
        if req.dem_path and os.path.exists(req.dem_path):
            try:
                dem = load_dem_dataset(req.dem_path)
            except Exception:
                dem = None

        prefix_raw = req.prefix_original if (req.prefix_original and req.prefix_original != "temp_") else "precip_"
        da_raw = load_daily_chirts_raw(req.dir_original, date, prefix_raw)
        da_corr = load_daily_chirts_corr(req.dir_merged, date, prefix="precip")

        if dem is None:
            dem = xr.zeros_like(da_raw)

        target_date = pd.to_datetime(date, format="%Y-%m-%d")
        df_day = df_obs_long[df_obs_long["date"] == target_date].copy()
        df_day = df_day.rename(columns={"precip_station": "obs"})
        stations_obs_day = df_day[["station_id", "lon", "lat", "elev", "obs"]]

        extent_plot = req.extent or (
            float(da_raw.lon.min()), float(da_raw.lon.max()),
            float(da_raw.lat.min()), float(da_raw.lat.max())
        )

        out_maps_dir = os.path.join(req.out_dir, "precip", "daily")
        os.makedirs(out_maps_dir, exist_ok=True)

        out_png = os.path.join(out_maps_dir, f"precip_daily_{date}.png")
        plot_side_by_side(
            da_left=da_raw, da_right=da_corr, dem=dem, year=date, var="precip",
            stat="daily", stations_obs_year=stations_obs_day, out_png=out_png, extent=extent_plot,
            show_labels=req.show_labels,
        )
        res.generated_maps.append(out_png)

        csv_path = os.path.join(out_maps_dir, f"precip_daily_{date}_cmp_estaciones.csv")
        export_cmp_csv(stations_obs_day, da_raw, da_corr, date, "precip", "daily", csv_path)
        res.generated_csvs.append(csv_path)

        eval_daily_dir = os.path.join(req.out_dir, "precip", "eval", "daily", str(date))
        os.makedirs(eval_daily_dir, exist_ok=True)

        # Diagnósticos
        df_cmp = pd.read_csv(csv_path)
        stations_delta_df = pd.DataFrame({"lat": df_cmp["lat"], "lon": df_cmp["lon"], "delta_grid": df_cmp["grid_corr"] - df_cmp["grid_raw"]})

        out_png_delta_field = os.path.join(eval_daily_dir, f"delta_grid_field_precip_daily_{date}.png")
        plot_delta_grid_field(
            da_raw=da_raw, da_corr=da_corr, dem=dem, out_png=out_png_delta_field,
            title=f"CHIRPS Diario — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — {date}",
            extent=extent_plot,
            units="mm",
            stations_df=stations_delta_df,
            show_labels=req.show_labels,
        )
        res.generated_maps.append(out_png_delta_field)

        out_png_delta_st = os.path.join(eval_daily_dir, f"delta_grid_stations_precip_daily_{date}.png")
        plot_delta_grid_at_stations(
            stations_delta_df, dem, out_png_delta_st,
            f"CHIRPS — Diferencia en estaciones — {date}",
            extent=extent_plot, units="mm", show_labels=req.show_labels
        )
        res.generated_maps.append(out_png_delta_st)

        obs_col = "precip_daily_obs" if "precip_daily_obs" in df_cmp.columns else ("obs" if "obs" in df_cmp.columns else df_cmp.columns[3])
        stations_resid_df = pd.DataFrame({"lat": df_cmp["lat"], "lon": df_cmp["lon"], "residual_corr": df_cmp["grid_corr"] - df_cmp[obs_col]})
        out_png_resid_st = os.path.join(eval_daily_dir, f"residual_corr_stations_precip_daily_{date}.png")
        plot_residual_corr_at_stations_with_dem(
            stations_resid_df, dem, out_png_resid_st,
            f"CHIRPS — Residuo (Corr − Obs) en estaciones — {date}",
            extent=extent_plot, units="mm", show_labels=req.show_labels
        )
        res.generated_maps.append(out_png_resid_st)

        shutil.copy(csv_path, eval_daily_dir)

        # Métricas, rankings y gráficos estadísticos para la fecha diaria
        try:
            obs = df_cmp[obs_col].values.astype(float)
            raw = df_cmp["grid_raw"].values.astype(float)
            corr = df_cmp["grid_corr"].values.astype(float)

            m_dict = compute_all_station_metrics(obs, raw, corr, is_precip=True)
            m_dict["date"] = str(date)
            df_metrics = pd.DataFrame([m_dict])
            metrics_csv = os.path.join(eval_daily_dir, f"metrics_daily_precip_{date}.csv")
            df_metrics.to_csv(metrics_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(metrics_csv)
            res.metrics_df = df_metrics

            df_rank = compute_station_metrics_from_csv(csv_path, "precip", "daily")
            rank_csv = os.path.join(eval_daily_dir, f"ranking_stations_daily_precip_{date}.csv")
            df_rank.to_csv(rank_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(rank_csv)
            res.rankings_df = df_rank

            daily_improve_csv = os.path.join(eval_daily_dir, f"improvement_stations_precip_daily_{date}_RMSE.csv")
            build_station_improvement_csv([csv_path], "precip", "daily", daily_improve_csv, metric="rmse")
            res.generated_csvs.append(daily_improve_csv)
            df_imp = pd.read_csv(daily_improve_csv)

            out_map_imp = os.path.join(eval_daily_dir, f"improvement_RMSEpct_stations_precip_daily_{date}.png")
            plot_improvement_at_stations_with_dem(
                df_imp, dem, out_map_imp,
                f"CHIRPS — Mejora vs estaciones — {date}",
                extent=extent_plot, show_labels=req.show_labels
            )
            res.generated_maps.append(out_map_imp)

            out_box = os.path.join(eval_daily_dir, f"boxplot_errors_precip_daily_{date}.png")
            plot_boxplot_errors_single(df_cmp, "precip", "daily", out_box)
            res.generated_plots.append(out_box)

            out_sc = os.path.join(eval_daily_dir, f"scatter_obs_vs_grid_precip_daily_{date}.png")
            plot_scatter_obs_vs_grid_single(df_cmp, "precip", "daily", out_sc)
            res.generated_plots.append(out_sc)
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Advertencia en generación de estadísticos diarios: {e}"))

        fin_msg = f"Procesamiento diario CHIRPS para {date} completado."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res

    def _run_period(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        dem = None
        if req.dem_path and os.path.exists(req.dem_path):
            try:
                dem = load_dem_dataset(req.dem_path)
            except Exception:
                dem = None

        stats_to_run = [req.stat.value] if (req.stat and req.stat != StatType.ALL) else ["accum"]
        yini = req.yini or 1991
        yend = req.yend or 2020
        years = list(range(yini, yend + 1))

        periods = []
        if req.period_type == PeriodType.SEASON:
            periods = list(SEASONS.keys()) if req.all_seasons else [req.season]
        else:
            periods = [req.months]

        total_steps = len(years) * len(periods) * len(stats_to_run)
        step_idx = 0
        prefix_raw = req.prefix_original if (req.prefix_original and req.prefix_original != "temp_") else "precip_"

        for year in years:
            for p in periods:
                if cancel_check and cancel_check():
                    cancel_msg = f"🛑 Proceso cancelado por el usuario en período {year}."
                    res.execution_logs.append(_log_msg(cancel_msg))
                    res.error_message = cancel_msg
                    res.success = False
                    if progress:
                        progress(1.0, cancel_msg)
                    return res

                if req.period_type == PeriodType.SEASON:
                    season = p
                    dates = get_dates_for_period(year, "season", season=season)
                    label = f"{season}_{year}"
                    title_label = make_period_title("season", year, season=season)
                else:
                    if isinstance(p, int):
                        months = [p]
                    elif isinstance(p, (list, tuple)):
                        months = list(p)
                    else:
                        months = [5, 6, 7]
                    dates = get_dates_for_period(year, "months", months=months)
                    months_names = [MONTH_NAMES_ES[m].lower() for m in months]
                    label = f"{'-'.join(months_names)}_{year}"
                    title_label = make_period_title("months", year, months=months)

                if not dates:
                    continue

                for stat_name in stats_to_run:
                    step_idx += 1
                    pct = 0.05 + 0.90 * (step_idx / max(total_steps, 1))
                    step_msg = f"Procesando período CHIRPS {label} ({stat_name})..."
                    if progress:
                        progress(pct, step_msg)
                    res.execution_logs.append(_log_msg(step_msg))

                    da_raw = load_period_stat_raw(req.dir_original, dates, prefix_raw, stat_name)
                    da_corr = load_period_stat_corr(req.dir_merged, dates, "precip", stat_name)
                    stations_obs = period_station_stat(df_obs_long, dates, "precip", stat_name)

                    if dem is None:
                        dem = xr.zeros_like(da_raw)

                    extent_plot = req.extent or (
                        float(da_raw.lon.min()), float(da_raw.lon.max()),
                        float(da_raw.lat.min()), float(da_raw.lat.max())
                    )

                    out_dir = os.path.join(req.out_dir, "precip", "period", stat_name)
                    os.makedirs(out_dir, exist_ok=True)
                    out_png = os.path.join(out_dir, f"precip_{stat_name}_{label}.png")
                    plot_side_by_side(
                        da_left=da_raw, da_right=da_corr, dem=dem, year=title_label,
                        var="precip", stat=stat_name, stations_obs_year=stations_obs, out_png=out_png, extent=extent_plot,
                        show_labels=req.show_labels,
                    )
                    res.generated_maps.append(out_png)

                    csv_path = os.path.join(out_dir, f"precip_{stat_name}_{label}_cmp_estaciones.csv")
                    export_cmp_csv(stations_obs, da_raw, da_corr, label, "precip", stat_name, csv_path)
                    res.generated_csvs.append(csv_path)

                    eval_period_dir = os.path.join(req.out_dir, "precip", "eval", "period", stat_name, label)
                    os.makedirs(eval_period_dir, exist_ok=True)

                    out_png_delta_field = os.path.join(eval_period_dir, f"delta_grid_field_precip_{stat_name}_{label}.png")
                    plot_delta_grid_field(
                        da_raw, da_corr, dem, out_png_delta_field,
                        f"CHIRPS {stat_name.capitalize()} — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — {title_label}",
                        extent=extent_plot, units="mm", stations_df=stations_obs, show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_png_delta_field)

                    if os.path.exists(csv_path):
                        df_cmp_p = pd.read_csv(csv_path)
                        if "grid_corr" in df_cmp_p.columns and "grid_raw" in df_cmp_p.columns:
                            df_cmp_p["delta_grid"] = df_cmp_p["grid_corr"] - df_cmp_p["grid_raw"]
                            out_png_delta_st = os.path.join(eval_period_dir, f"delta_grid_stations_precip_{stat_name}_{label}.png")
                            plot_delta_grid_at_stations(
                                df_cmp_p, dem, out_png_delta_st,
                                f"CHIRPS {stat_name} — Diferencia en estaciones — {title_label}",
                                extent=extent_plot, units="mm", show_labels=req.show_labels
                            )
                            res.generated_maps.append(out_png_delta_st)

                        if "err_corr" in df_cmp_p.columns:
                            df_cmp_p["residual_corr"] = df_cmp_p["err_corr"]
                            out_png_resid_st = os.path.join(eval_period_dir, f"residual_corr_stations_precip_{stat_name}_{label}.png")
                            plot_residual_corr_at_stations_with_dem(
                                df_cmp_p, dem, out_png_resid_st,
                                f"CHIRPS {stat_name} — Residuo (Corr − Obs) en estaciones — {title_label}",
                                extent=extent_plot, units="mm", show_labels=req.show_labels
                            )
                            res.generated_maps.append(out_png_resid_st)

                    period_improve_csv = os.path.join(eval_period_dir, f"improvement_stations_precip_{stat_name}_{label}_RMSE.csv")
                    build_station_improvement_csv([csv_path], "precip", stat_name, period_improve_csv, metric="rmse")
                    res.generated_csvs.append(period_improve_csv)

                    df_imp = pd.read_csv(period_improve_csv)
                    out_map_imp_period = os.path.join(eval_period_dir, f"improvement_RMSEpct_stations_precip_{stat_name}_{label}.png")
                    plot_improvement_at_stations_with_dem(
                        df_imp, dem, out_map_imp_period,
                        f"CHIRPS {stat_name} — Mejora de RMSE [%] — {title_label}",
                        extent=extent_plot, show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_map_imp_period)

                    out_box_rmse = os.path.join(eval_period_dir, f"boxplot_RMSE_stations_precip_{stat_name}_{label}.png")
                    plot_boxplot_rmse_by_station(df_imp, "precip", stat_name, label, out_box_rmse)
                    res.generated_plots.append(out_box_rmse)

                    out_box_imp = os.path.join(eval_period_dir, f"boxplot_improvement_RMSEpct_stations_precip_{stat_name}_{label}.png")
                    plot_boxplot_improvement_pct_by_station(df_imp, "precip", stat_name, label, out_box_imp)
                    res.generated_plots.append(out_box_imp)

                    out_sc_rmse = os.path.join(eval_period_dir, f"scatter_RMSE_raw_vs_corr_precip_{stat_name}_{label}.png")
                    plot_scatter_rmse_raw_vs_corr(df_imp, "precip", stat_name, label, out_sc_rmse)
                    res.generated_plots.append(out_sc_rmse)

                    out_box_err = os.path.join(eval_period_dir, f"boxplot_errors_precip_{stat_name}_{label}.png")
                    plot_boxplot_errors_single(csv_path, "precip", stat_name, out_box_err)
                    res.generated_plots.append(out_box_err)

                    out_sc_obs = os.path.join(eval_period_dir, f"scatter_obs_vs_grid_precip_{stat_name}_{label}.png")
                    plot_scatter_obs_vs_grid_single(
                        csv_path, "precip", stat_name, out_sc_obs,
                        title=f"CHIRPS {stat_name.capitalize()} — Observado vs Rejilla Satelital — {title_label}"
                    )
                    res.generated_plots.append(out_sc_obs)

        # Resumen global y rankings para todos los períodos evaluados
        all_period_csvs = [c for c in res.generated_csvs if "cmp_estaciones" in c]
        if all_period_csvs:
            try:
                base_stat = stats_to_run[0]
                period_base_eval_dir = os.path.join(req.out_dir, "precip", "eval", "period", base_stat)
                df_metrics, metrics_csv = compute_annual_metrics_from_csv(all_period_csvs, "precip", base_stat, period_base_eval_dir)
                if metrics_csv:
                    res.generated_csvs.append(metrics_csv)
                res.metrics_df = df_metrics

                png_sc_glob = plot_scatter_obs_vs_grid(
                    all_period_csvs, "precip", base_stat, period_base_eval_dir,
                    title=f"CHIRPS {base_stat.capitalize()} — Observado vs Rejilla Satelital — Resumen Global ({len(all_period_csvs)} Períodos)"
                )
                if png_sc_glob:
                    res.generated_plots.append(png_sc_glob)

                png_box_glob = plot_boxplot_errors(all_period_csvs, "precip", base_stat, period_base_eval_dir)
                if png_box_glob:
                    res.generated_plots.append(png_box_glob)

                df_rank = compute_station_metrics_global(all_period_csvs, "precip", base_stat)
                rank_csv = os.path.join(period_base_eval_dir, f"ranking_stations_period_precip_{base_stat}.csv")
                df_rank.to_csv(rank_csv, index=False, float_format="%.4f")
                res.generated_csvs.append(rank_csv)
                res.rankings_df = df_rank
            except Exception as e:
                res.execution_logs.append(_log_msg(f"Advertencia en métricas globales de períodos: {e}"))

        # Climatología DOY 1–365 por Estación
        try:
            base_stat = stats_to_run[0] if stats_to_run else "accum"
            period_base_eval_dir = os.path.join(req.out_dir, "precip", "eval", "period", base_stat)
            generate_doy_climatology_for_stations(
                df_obs_long, req, res, period_base_eval_dir,
                progress=progress, cancel_check=cancel_check,
                pct_start=0.92, pct_end=0.99,
            )
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Advertencia en generación DOY períodos: {e}"))

        fin_msg = "Análisis de períodos de CHIRPS completado exitosamente."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res

    def _run_annual(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, cb: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        dem = None
        if req.dem_path and os.path.exists(req.dem_path):
            try:
                dem = load_dem_dataset(req.dem_path)
            except Exception:
                dem = None

        yini = req.yini or 1991
        yend = req.yend or 2020
        years = list(range(yini, yend + 1))
        total_years = len(years)

        out_maps_dir = os.path.join(req.out_dir, "precip", "accum")
        base_eval_dir = os.path.join(req.out_dir, "precip", "eval", "annual", "accum")
        global_dir = os.path.join(base_eval_dir, "global")
        by_year_dir = os.path.join(base_eval_dir, "by_year")
        os.makedirs(out_maps_dir, exist_ok=True)
        os.makedirs(global_dir, exist_ok=True)
        os.makedirs(by_year_dir, exist_ok=True)

        deltas_for_global = []

        for i, year in enumerate(years):
            if cancel_check and cancel_check():
                cancel_msg = f"🛑 Proceso cancelado por el usuario en el año {year}."
                res.execution_logs.append(_log_msg(cancel_msg))
                res.error_message = cancel_msg
                res.success = False
                if cb:
                    cb(1.0, cancel_msg)
                return res

            pct = 0.05 + 0.80 * (i / max(total_years, 1))
            msg = f"Procesando CHIRPS año {year} ({i+1}/{total_years})..."
            if cb:
                cb(pct, msg)
            res.execution_logs.append(_log_msg(msg))

            stations_obs_year = annual_station_accum(df_obs_long, year)
            prefix_raw = req.prefix_original if (req.prefix_original and req.prefix_original != "temp_") else "precip_"
            da_chirps = load_daily_sum_for_year(req.dir_original, year, prefix_raw, "precip")
            da_merged = load_daily_sum_for_year(req.dir_merged, year, "precip_mrg_", "precip")

            if dem is None:
                dem = xr.zeros_like(da_chirps)

            extent_plot = req.extent or (
                float(da_chirps.lon.min()), float(da_chirps.lon.max()),
                float(da_chirps.lat.min()), float(da_chirps.lat.max())
            )

            deltas_for_global.append(da_merged - da_chirps)

            out_png = os.path.join(out_maps_dir, f"precip_accum_anual_{year}.png")
            plot_side_by_side(
                da_left=da_chirps,
                da_right=da_merged,
                dem=dem,
                year=year,
                stations_obs_year=stations_obs_year,
                out_png=out_png,
                var="precip",
                stat="accum",
                extent=extent_plot,
                show_labels=req.show_labels,
            )
            res.generated_maps.append(out_png)

            # Diagnósticos espaciales anuales por año
            year_dir = os.path.join(by_year_dir, str(year))
            os.makedirs(year_dir, exist_ok=True)
            out_png_delta_field = os.path.join(year_dir, f"delta_grid_field_precip_accum_{year}.png")
            plot_delta_grid_field(
                da_chirps, da_merged, dem, out_png_delta_field,
                f"CHIRPS Acumulado — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — {year}",
                extent=extent_plot, units="mm", stations_df=stations_obs_year, show_labels=req.show_labels
            )
            res.generated_maps.append(out_png_delta_field)

            # Exportar CSV de comparación anual para métricas
            csv_cmp_year = os.path.join(out_maps_dir, f"precip_accum_anual_{year}_cmp_estaciones.csv")
            export_cmp_csv(stations_obs_year, da_chirps, da_merged, year, "precip", "accum", csv_cmp_year)
            res.generated_csvs.append(csv_cmp_year)

            if os.path.exists(csv_cmp_year):
                df_cmp_yr = pd.read_csv(csv_cmp_year)
                if "grid_corr" in df_cmp_yr.columns and "grid_raw" in df_cmp_yr.columns:
                    df_cmp_yr["delta_grid"] = df_cmp_yr["grid_corr"] - df_cmp_yr["grid_raw"]
                    out_png_delta_st = os.path.join(year_dir, f"delta_grid_stations_precip_accum_{year}.png")
                    plot_delta_grid_at_stations(
                        df_cmp_yr, dem, out_png_delta_st,
                        f"CHIRPS Acumulado — Diferencia en estaciones — {year}",
                        extent=extent_plot, units="mm", show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_png_delta_st)

                if "err_corr" in df_cmp_yr.columns:
                    df_cmp_yr["residual_corr"] = df_cmp_yr["err_corr"]
                    out_png_resid_st = os.path.join(year_dir, f"residual_corr_stations_precip_accum_{year}.png")
                    plot_residual_corr_at_stations_with_dem(
                        df_cmp_yr, dem, out_png_resid_st,
                        f"CHIRPS Acumulado — Residuo (Corr − Obs) en estaciones — {year}",
                        extent=extent_plot, units="mm", show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_png_resid_st)

                    out_box_yr = os.path.join(year_dir, f"boxplot_errors_precip_accum_{year}.png")
                    plot_boxplot_errors_single(csv_cmp_year, "precip", "accum", out_box_yr)
                    res.generated_plots.append(out_box_yr)

                    out_sc_yr = os.path.join(year_dir, f"scatter_obs_vs_grid_precip_accum_{year}.png")
                    plot_scatter_obs_vs_grid_single(
                        csv_cmp_year, "precip", "accum", out_sc_yr,
                        title=f"CHIRPS Acumulado — Observado vs Rejilla Satelital — {year}"
                    )
                    res.generated_plots.append(out_sc_yr)

            if req.export_csv:
                out_csv = os.path.join(out_maps_dir, f"acumulado_observado_estaciones_{year}.csv")
                stations_obs_year.to_csv(out_csv, index=False)
                res.generated_csvs.append(out_csv)

        # Construir CSV global de estaciones a partir de todos los años evaluados
        csv_pattern = os.path.join(out_maps_dir, "*cmp_estaciones*.csv")
        csv_files = sorted(glob.glob(csv_pattern))
        df_glob = None

        if csv_files:
            global_csv = os.path.join(global_dir, "global_cmp_estaciones_precip_accum.csv")
            build_global_station_csv(csv_files, global_csv)
            res.generated_csvs.append(global_csv)

            if os.path.exists(global_csv):
                df_glob = pd.read_csv(global_csv)
                if "grid_corr" in df_glob.columns and "grid_raw" in df_glob.columns:
                    df_glob["delta_grid"] = df_glob["grid_corr"] - df_glob["grid_raw"]
                if "err_corr" in df_glob.columns:
                    df_glob["residual_corr"] = df_glob["err_corr"]

        if deltas_for_global:
            delta_global = xr.concat(deltas_for_global, dim="time").mean("time")
            out_png_delta_field_global = os.path.join(global_dir, "delta_grid_field_precip_accum_GLOBAL.png")
            plot_delta_grid_field(
                None, None, dem, out_png_delta_field_global,
                "CHIRPS Acumulado — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — GLOBAL",
                extent=extent_plot, units="mm", delta_override=delta_global,
                stations_df=df_glob,
                show_labels=req.show_labels
            )
            res.generated_maps.append(out_png_delta_field_global)

        # Evaluación estadística global para CHIRPS
        if req.eval_stats and csv_files:
            if cancel_check and cancel_check():
                cancel_msg = "🛑 Proceso cancelado antes del cálculo global de métricas."
                res.execution_logs.append(_log_msg(cancel_msg))
                res.error_message = cancel_msg
                res.success = False
                return res

            eval_msg = "Calculando métricas estadísticas globales y gráficos diagnósticos..."
            if cb:
                cb(0.92, eval_msg)
            res.execution_logs.append(_log_msg(eval_msg))

            if df_glob is not None:
                if "delta_grid" in df_glob.columns:
                    out_png_delta_st_glob = os.path.join(global_dir, "delta_grid_stations_precip_accum_GLOBAL.png")
                    plot_delta_grid_at_stations(
                        df_glob, dem, out_png_delta_st_glob,
                        "CHIRPS Acumulado — Diferencia en estaciones — GLOBAL",
                        extent=extent_plot, units="mm", show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_png_delta_st_glob)

                if "residual_corr" in df_glob.columns:
                    out_png_resid_st_glob = os.path.join(global_dir, "residual_corr_stations_precip_accum_GLOBAL.png")
                    plot_residual_corr_at_stations_with_dem(
                        df_glob, dem, out_png_resid_st_glob,
                        "CHIRPS Acumulado — Residuo (Corr − Obs) en estaciones — GLOBAL",
                        extent=extent_plot, units="mm", show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_png_resid_st_glob)

            global_improve_csv = os.path.join(global_dir, "improvement_stations_precip_accum_RMSE.csv")
            build_station_improvement_csv(csv_files, "precip", "accum", global_improve_csv, metric="rmse")
            res.generated_csvs.append(global_improve_csv)
            df_imp_global = pd.read_csv(global_improve_csv)

            out_map_imp_global = os.path.join(global_dir, "improvement_RMSEpct_stations_precip_accum_GLOBAL.png")
            plot_improvement_at_stations_with_dem(
                df_imp_global, dem, out_map_imp_global,
                "CHIRPS Acumulado — Mejora vs estaciones — GLOBAL",
                extent=extent_plot, show_labels=req.show_labels
            )
            res.generated_maps.append(out_map_imp_global)

            df_metrics, metrics_csv = compute_annual_metrics_from_csv(csv_files, "precip", "accum", global_dir)
            if metrics_csv:
                res.generated_csvs.append(metrics_csv)
            res.metrics_df = df_metrics

            png_rmse = plot_rmse_bars(df_metrics, "precip", "accum", global_dir)
            res.generated_plots.append(png_rmse)

            png_kge = plot_kge_components(df_metrics, "precip", "accum", global_dir)
            if png_kge:
                res.generated_plots.append(png_kge)

            png_box = plot_boxplot_errors(csv_files, "precip", "accum", global_dir)
            if png_box:
                res.generated_plots.append(png_box)

            png_sc = plot_scatter_obs_vs_grid(
                csv_files, "precip", "accum", global_dir,
                title="CHIRPS Acumulado — Observado vs Rejilla Satelital — GLOBAL"
            )
            if png_sc:
                res.generated_plots.append(png_sc)

            df_rank = compute_station_metrics_global(csv_files, "precip", "accum")
            rank_csv = os.path.join(global_dir, "ranking_stations_global_precip_accum.csv")
            df_rank.to_csv(rank_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(rank_csv)
            res.rankings_df = df_rank

        # Climatología DOY 1–365 por Estación
        try:
            generate_doy_climatology_for_stations(
                df_obs_long, req, res, base_eval_dir,
                progress=cb, cancel_check=cancel_check,
                pct_start=0.94, pct_end=0.99,
            )
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Advertencia en generación DOY anual: {e}"))

        fin_msg = "Análisis de CHIRPS completado exitosamente."
        if cb:
            cb(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res


class ChirtsService:
    """Servicio de orquestación para análisis y visualización de CHIRTS (temperatura)."""

    def run(
        self,
        req: AnalysisRequest,
        progress_callback: ProgressCallback = None,
        progress: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> AnalysisResult:
        cb = progress_callback or progress
        res = AnalysisResult(output_dir=req.out_dir, request=req)
        try:
            init_msg = "Inicializando análisis CHIRTS y cargando datos..."
            if cb:
                cb(0.02, init_msg)
            res.execution_logs.append(_log_msg(init_msg))

            value_name = f"{req.var}_station"
            meta, df_obs_long = parse_cdt_csv(req.csv_path, value_name)
            df_obs_long["date"] = pd.to_datetime(df_obs_long["date"], format="%Y%m%d")

            # Enrutamiento según modo
            if req.mode == ProcessingMode.DAILY_EVAL:
                return self._run_daily_eval(req, df_obs_long, res, cb, cancel_check=cancel_check)
            elif req.mode == ProcessingMode.DAILY:
                return self._run_daily(req, df_obs_long, res, cb, cancel_check=cancel_check)
            elif req.mode == ProcessingMode.PERIOD:
                return self._run_period(req, df_obs_long, res, cb, cancel_check=cancel_check)
            else:
                return self._run_annual(req, df_obs_long, res, cb, cancel_check=cancel_check)

        except Exception as e:
            err_msg = f"ERROR: {str(e)}"
            res.success = False
            res.error_message = str(e)
            res.execution_logs.append(_log_msg(err_msg))
            return res

    def _run_daily_eval(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        if progress:
            progress(0.05, f"Iniciando evaluación diaria multianual para {req.var}...")
        res.execution_logs.append(_log_msg(f"Iniciando evaluación diaria multianual ({req.var})..."))

        years = sorted(df_obs_long["year"].unique())
        out_dir = os.path.join(req.out_dir, req.var, "daily_eval")
        os.makedirs(out_dir, exist_ok=True)

        success = generate_doy_climatology_for_stations(
            df_obs_long=df_obs_long,
            req=req,
            res=res,
            out_clim_dir=out_dir,
            progress=progress,
            cancel_check=cancel_check,
            pct_start=0.10,
            pct_end=0.85,
        )
        if not success and res.error_message:
            return res

        daily_csvs = [c for c in res.generated_csvs if f"daily_timeseries_{req.var}_" in os.path.basename(c)]
        if not daily_csvs:
            res.error_message = "No se generó la serie diaria consolidada."
            res.success = False
            return res

        df_daily = pd.read_csv(daily_csvs[0])
        if "year" not in df_daily.columns:
            df_daily["year"] = pd.to_datetime(df_daily["date"].astype(str), format="%Y%m%d").dt.year

        summary_station = res.summary_station_df
        if summary_station is not None:
            rank_csv = os.path.join(out_dir, f"ranking_stations_{req.var}_daily_eval.csv")
            summary_station.to_csv(rank_csv, index=False, float_format="%.4f")
            if rank_csv not in res.generated_csvs:
                res.generated_csvs.append(rank_csv)

        # Métricas anuales a partir de la serie diaria multianual
        annual_rows = []
        for y in years:
            df_y = df_daily[df_daily["year"] == y]
            if not df_y.empty:
                m_y = compute_all_station_metrics(
                    df_y["obs"].values, df_y["raw"].values, df_y["corr"].values,
                    is_precip=False
                )
                m_y["year"] = int(y)
                annual_rows.append(m_y)
        if annual_rows:
            df_annual = pd.DataFrame(annual_rows)
            if "year" in df_annual.columns:
                cols = ["year"] + [c for c in df_annual.columns if c != "year"]
                df_annual = df_annual[cols]
            metrics_annual_csv = os.path.join(out_dir, f"metrics_annual_{req.var}_daily_eval.csv")
            df_annual.to_csv(metrics_annual_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(metrics_annual_csv)
            res.metrics_df = df_annual

            png_rmse = plot_rmse_bars(df_annual, req.var, "daily_eval", out_dir)
            res.generated_plots.append(png_rmse)

            png_kge = plot_kge_components(df_annual, req.var, "daily_eval", out_dir)
            if png_kge:
                res.generated_plots.append(png_kge)
        else:
            res.metrics_df = summary_global

        # Gráficos diagnósticos en estaciones (Boxplot y Scatter global de la serie)
        out_box = os.path.join(out_dir, f"boxplot_errors_{req.var}_daily_eval.png")
        plot_boxplot_errors_single(df_daily, req.var, "daily_eval", out_box)
        res.generated_plots.append(out_box)

        out_sc = os.path.join(out_dir, f"scatter_obs_vs_grid_{req.var}_daily_eval.png")
        plot_scatter_obs_vs_grid_single(df_daily, req.var, "daily_eval", out_sc)
        res.generated_plots.append(out_sc)

        # Generar scatter plots y boxplots por período/año para estaciones en temperatura
        is_period_mode = (
            req.mode == ProcessingMode.PERIOD
            or (hasattr(req, "period_type") and req.period_type in [PeriodType.SEASON, PeriodType.MONTHS])
        )
        p_type_arg = req.period_type.value if hasattr(req.period_type, "value") else str(getattr(req, "period_type", "annual"))

        for y in years:
            if is_period_mode:
                try:
                    dates_y = get_dates_for_period(year=y, period_type=p_type_arg, season=req.season, months=req.months)
                    df_slice = df_daily[df_daily["date"].astype(str).str.replace("-", "").isin(dates_y)]
                    if req.period_type == PeriodType.SEASON:
                        label = f"{req.season.lower()}_{y}"
                        title_label = make_period_title("season", y, season=req.season)
                    else:
                        m_list = req.months if isinstance(req.months, (list, tuple)) else [req.months]
                        m_names = [MONTH_NAMES_ES[int(m)].lower() for m in m_list]
                        label = f"{'-'.join(m_names)}_{y}"
                        title_label = make_period_title("months", y, months=m_list)
                except Exception:
                    df_slice = df_daily[df_daily["year"] == y]
                    label = f"{y}"
                    title_label = f"Año {y}"
            else:
                df_slice = df_daily[df_daily["year"] == y]
                label = f"{y}"
                title_label = f"Año {y}"

            if df_slice.empty:
                continue

            for stat_name in ["mean", "max", "min"]:
                if stat_name == "mean":
                    df_st_agg = df_slice.groupby(["station_id", "lon", "lat"]).agg({"obs": "mean", "raw": "mean", "corr": "mean"}).reset_index()
                elif stat_name == "max":
                    df_st_agg = df_slice.groupby(["station_id", "lon", "lat"]).agg({"obs": "max", "raw": "max", "corr": "max"}).reset_index()
                else:
                    df_st_agg = df_slice.groupby(["station_id", "lon", "lat"]).agg({"obs": "min", "raw": "min", "corr": "min"}).reset_index()

                out_sc_p = os.path.join(out_dir, f"scatter_obs_vs_grid_{req.var}_{stat_name}_{label}.png")
                plot_scatter_obs_vs_grid_single(
                    df_st_agg, req.var, stat_name, out_sc_p,
                    title=f"CHIRTS {req.var.upper()} {stat_name.capitalize()} — Observado vs Rejilla — {title_label}"
                )
                if out_sc_p not in res.generated_plots:
                    res.generated_plots.append(out_sc_p)

                out_box_p = os.path.join(out_dir, f"boxplot_errors_{req.var}_{stat_name}_{label}.png")
                plot_boxplot_errors_single(df_st_agg, req.var, stat_name, out_box_p)
                if out_box_p not in res.generated_plots:
                    res.generated_plots.append(out_box_p)

        # Mapa de mejora en estaciones sobre DEM
        dem = load_dem_dataset(req.dem_path) if req.dem_path else None

        imp_rows = []
        for (sid, lat, lon), g in df_daily.groupby(["station_id", "lat", "lon"]):
            o = g["obs"].values
            r = g["raw"].values
            c = g["corr"].values
            m = np.isfinite(o) & np.isfinite(r) & np.isfinite(c)
            if np.sum(m) >= 2:
                rmse_r = float(np.sqrt(np.mean((r[m] - o[m])**2)))
                rmse_c = float(np.sqrt(np.mean((c[m] - o[m])**2)))
                delta_rmse = rmse_r - rmse_c
                den = max(rmse_r, rmse_c, 1e-6)
                imp_pct = 100.0 * delta_rmse / den
                imp_rows.append({
                    "station_id": sid,
                    "lat": lat,
                    "lon": lon,
                    "RMSE_raw": rmse_r,
                    "RMSE_corr": rmse_c,
                    "delta_RMSE": delta_rmse,
                    "improvement_RMSE_pct": imp_pct,
                    "improvement_pct": imp_pct,
                })
        if imp_rows:
            df_imp = pd.DataFrame(imp_rows)
            imp_csv = os.path.join(out_dir, f"improvement_stations_{req.var}_daily_eval_RMSE.csv")
            df_imp.to_csv(imp_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(imp_csv)

            out_map_imp = os.path.join(out_dir, f"improvement_RMSEpct_stations_{req.var}_daily_eval.png")
            extent_plot = req.extent or (
                float(df_daily["lon"].min()) - 0.2, float(df_daily["lon"].max()) + 0.2,
                float(df_daily["lat"].min()) - 0.2, float(df_daily["lat"].max()) + 0.2
            )
            plot_improvement_at_stations_with_dem(
                df_imp, dem, out_map_imp,
                f"{req.var.upper()} — Mejora vs estaciones (Serie Diaria Multianual)",
                extent=extent_plot, show_labels=req.show_labels
            )
            res.generated_maps.append(out_map_imp)

        fin_msg = "Evaluación diaria multianual completada exitosamente."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res

    def _run_daily(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        date = req.date_str
        day_msg = f"Procesando mapa diario para fecha {date} ({req.var})..."
        if progress:
            progress(0.10, day_msg)
        res.execution_logs.append(_log_msg(day_msg))

        dem = load_dem_dataset(req.dem_path)
        da_raw = load_daily_chirts_raw(req.dir_original, date, req.prefix_original)
        da_corr = load_daily_chirts_corr(req.dir_merged, date, prefix=req.var)

        target_date = pd.to_datetime(date, format="%Y-%m-%d")
        df_day = df_obs_long[df_obs_long["date"] == target_date].copy()
        df_day = df_day.rename(columns={f"{req.var}_station": "obs"})
        stations_obs_day = df_day[["station_id", "lon", "lat", "elev", "obs"]]

        extent_plot = req.extent or (
            float(da_raw.lon.min()), float(da_raw.lon.max()),
            float(da_raw.lat.min()), float(da_raw.lat.max())
        )

        out_maps_dir = os.path.join(req.out_dir, req.var, "daily")
        os.makedirs(out_maps_dir, exist_ok=True)

        out_png = os.path.join(out_maps_dir, f"{req.var}_daily_{date}.png")
        plot_side_by_side(
            da_left=da_raw, da_right=da_corr, dem=dem, year=date, var=req.var,
            stat="daily", stations_obs_year=stations_obs_day, out_png=out_png, extent=extent_plot,
            show_labels=req.show_labels,
        )
        res.generated_maps.append(out_png)

        csv_path = os.path.join(out_maps_dir, f"{req.var}_daily_{date}_cmp_estaciones.csv")
        export_cmp_csv(stations_obs_day, da_raw, da_corr, date, req.var, "daily", csv_path)
        res.generated_csvs.append(csv_path)

        eval_daily_dir = os.path.join(req.out_dir, req.var, "eval", "daily", str(date))
        os.makedirs(eval_daily_dir, exist_ok=True)

        # Diagnósticos
        df_cmp = pd.read_csv(csv_path)
        stations_delta_df = pd.DataFrame({"lat": df_cmp["lat"], "lon": df_cmp["lon"], "delta_grid": df_cmp["grid_corr"] - df_cmp["grid_raw"]})

        out_png_delta_field = os.path.join(eval_daily_dir, f"delta_grid_field_{req.var}_daily_{date}.png")
        plot_delta_grid_field(
            da_raw=da_raw, da_corr=da_corr, dem=dem, out_png=out_png_delta_field,
            title=f"{req.var.upper()} — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — {date}",
            extent=extent_plot,
            stations_df=stations_delta_df,
            show_labels=req.show_labels,
        )
        res.generated_maps.append(out_png_delta_field)
        out_png_delta_st = os.path.join(eval_daily_dir, f"delta_grid_stations_{req.var}_daily_{date}.png")
        plot_delta_grid_at_stations(stations_delta_df, dem, out_png_delta_st, f"{req.var.upper()} — Diferencia en estaciones — {date}", extent=extent_plot, show_labels=req.show_labels)
        res.generated_maps.append(out_png_delta_st)

        obs_col = f"{req.var}_daily_obs" if f"{req.var}_daily_obs" in df_cmp.columns else df_cmp.columns[3]
        stations_resid_df = pd.DataFrame({"lat": df_cmp["lat"], "lon": df_cmp["lon"], "residual_corr": df_cmp["grid_corr"] - df_cmp[obs_col]})
        out_png_resid_st = os.path.join(eval_daily_dir, f"residual_corr_stations_{req.var}_daily_{date}.png")
        plot_residual_corr_at_stations_with_dem(stations_resid_df, dem, out_png_resid_st, f"{req.var.upper()} — Residuo (Corr − Obs) en estaciones — {date}", extent=extent_plot, show_labels=req.show_labels)
        res.generated_maps.append(out_png_resid_st)

        shutil.copy(csv_path, eval_daily_dir)

        # Métricas, rankings y gráficos estadísticos para la fecha diaria
        try:
            obs = df_cmp[obs_col].values.astype(float)
            raw = df_cmp["grid_raw"].values.astype(float)
            corr = df_cmp["grid_corr"].values.astype(float)

            m_dict = compute_all_station_metrics(obs, raw, corr, is_precip=False)
            m_dict["date"] = str(date)
            df_metrics = pd.DataFrame([m_dict])
            metrics_csv = os.path.join(eval_daily_dir, f"metrics_daily_{req.var}_{date}.csv")
            df_metrics.to_csv(metrics_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(metrics_csv)
            res.metrics_df = df_metrics

            df_rank = compute_station_metrics_from_csv(csv_path, req.var, "daily")
            rank_csv = os.path.join(eval_daily_dir, f"ranking_stations_daily_{req.var}_{date}.csv")
            df_rank.to_csv(rank_csv, index=False, float_format="%.4f")
            res.generated_csvs.append(rank_csv)
            res.rankings_df = df_rank

            daily_improve_csv = os.path.join(eval_daily_dir, f"improvement_stations_{req.var}_daily_{date}_RMSE.csv")
            build_station_improvement_csv([csv_path], req.var, "daily", daily_improve_csv, metric="rmse")
            res.generated_csvs.append(daily_improve_csv)
            df_imp = pd.read_csv(daily_improve_csv)

            out_map_imp = os.path.join(eval_daily_dir, f"improvement_RMSEpct_stations_{req.var}_daily_{date}.png")
            plot_improvement_at_stations_with_dem(
                df_imp, dem, out_map_imp,
                f"{req.var.upper()} — Mejora vs estaciones — {date}",
                extent=extent_plot, show_labels=req.show_labels
            )
            res.generated_maps.append(out_map_imp)

            out_box = os.path.join(eval_daily_dir, f"boxplot_errors_{req.var}_daily_{date}.png")
            plot_boxplot_errors_single(df_cmp, req.var, "daily", out_box)
            res.generated_plots.append(out_box)

            out_sc = os.path.join(eval_daily_dir, f"scatter_obs_vs_grid_{req.var}_daily_{date}.png")
            plot_scatter_obs_vs_grid_single(df_cmp, req.var, "daily", out_sc)
            res.generated_plots.append(out_sc)
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Advertencia en generación de estadísticos diarios: {e}"))

        fin_msg = f"Procesamiento diario para {date} completado."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res

    def _run_period(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        dem = load_dem_dataset(req.dem_path)
        stats_to_run = ["mean", "max", "min"] if req.stat == StatType.ALL else [req.stat.value]
        yini = req.yini or 1991
        yend = req.yend or 2020
        years = list(range(yini, yend + 1))

        periods = []
        if req.period_type == PeriodType.SEASON:
            periods = list(SEASONS.keys()) if req.all_seasons else [req.season]
        else:
            periods = [req.months]

        total_steps = len(years) * len(periods) * len(stats_to_run)
        step_idx = 0

        for year in years:
            for p in periods:
                if cancel_check and cancel_check():
                    cancel_msg = f"🛑 Proceso cancelado por el usuario en período {year}."
                    res.execution_logs.append(_log_msg(cancel_msg))
                    res.error_message = cancel_msg
                    res.success = False
                    if progress:
                        progress(1.0, cancel_msg)
                    return res

                if req.period_type == PeriodType.SEASON:
                    season = p
                    dates = get_dates_for_period(year, "season", season=season)
                    label = f"{season}_{year}"
                    title_label = make_period_title("season", year, season=season)
                else:
                    if isinstance(p, int):
                        months = [p]
                    elif isinstance(p, (list, tuple)):
                        months = list(p)
                    else:
                        months = [5, 6, 7]
                    dates = get_dates_for_period(year, "months", months=months)
                    months_names = [MONTH_NAMES_ES[m].lower() for m in months]
                    label = f"{'-'.join(months_names)}_{year}"
                    title_label = make_period_title("months", year, months=months)

                if not dates:
                    continue

                for stat_name in stats_to_run:
                    step_idx += 1
                    pct = 0.05 + 0.90 * (step_idx / max(total_steps, 1))
                    step_msg = f"Procesando período {req.var.upper()} {label} ({stat_name})..."
                    if progress:
                        progress(pct, step_msg)
                    res.execution_logs.append(_log_msg(step_msg))

                    da_raw = load_period_stat_raw(req.dir_original, dates, req.prefix_original, stat_name)
                    da_corr = load_period_stat_corr(req.dir_merged, dates, req.var, stat_name)
                    stations_obs = period_station_stat(df_obs_long, dates, req.var, stat_name)

                    extent_plot = req.extent or (
                        float(da_raw.lon.min()), float(da_raw.lon.max()),
                        float(da_raw.lat.min()), float(da_raw.lat.max())
                    )

                    out_dir = os.path.join(req.out_dir, req.var, "period", stat_name)
                    os.makedirs(out_dir, exist_ok=True)
                    out_png = os.path.join(out_dir, f"{req.var}_{stat_name}_{label}.png")
                    plot_side_by_side(
                        da_left=da_raw, da_right=da_corr, dem=dem, year=title_label,
                        var=req.var, stat=stat_name, stations_obs_year=stations_obs, out_png=out_png, extent=extent_plot,
                        show_labels=req.show_labels,
                    )
                    res.generated_maps.append(out_png)

                    csv_path = os.path.join(out_dir, f"{req.var}_{stat_name}_{label}_cmp_estaciones.csv")
                    export_cmp_csv(stations_obs, da_raw, da_corr, label, req.var, stat_name, csv_path)
                    res.generated_csvs.append(csv_path)

                    eval_period_dir = os.path.join(req.out_dir, req.var, "eval", "period", stat_name, label)
                    os.makedirs(eval_period_dir, exist_ok=True)

                    out_png_delta_field = os.path.join(eval_period_dir, f"delta_grid_field_{req.var}_{stat_name}_{label}.png")
                    plot_delta_grid_field(
                        da_raw, da_corr, dem, out_png_delta_field,
                        f"{req.var.upper()} {stat_name} — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — {title_label}",
                        extent=extent_plot, stations_df=stations_obs, show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_png_delta_field)

                    if os.path.exists(csv_path):
                        df_cmp_p = pd.read_csv(csv_path)
                        if "grid_corr" in df_cmp_p.columns and "grid_raw" in df_cmp_p.columns:
                            df_cmp_p["delta_grid"] = df_cmp_p["grid_corr"] - df_cmp_p["grid_raw"]
                            out_png_delta_st = os.path.join(eval_period_dir, f"delta_grid_stations_{req.var}_{stat_name}_{label}.png")
                            plot_delta_grid_at_stations(
                                df_cmp_p, dem, out_png_delta_st,
                                f"{req.var.upper()} {stat_name} — Diferencia en estaciones — {title_label}",
                                extent=extent_plot, show_labels=req.show_labels
                            )
                            res.generated_maps.append(out_png_delta_st)

                        if "err_corr" in df_cmp_p.columns:
                            df_cmp_p["residual_corr"] = df_cmp_p["err_corr"]
                            out_png_resid_st = os.path.join(eval_period_dir, f"residual_corr_stations_{req.var}_{stat_name}_{label}.png")
                            plot_residual_corr_at_stations_with_dem(
                                df_cmp_p, dem, out_png_resid_st,
                                f"{req.var.upper()} {stat_name} — Residuo (Corr − Obs) en estaciones — {title_label}",
                                extent=extent_plot, show_labels=req.show_labels
                            )
                            res.generated_maps.append(out_png_resid_st)

                    period_improve_csv = os.path.join(eval_period_dir, f"improvement_stations_{req.var}_{stat_name}_{label}_RMSE.csv")
                    build_station_improvement_csv([csv_path], req.var, stat_name, period_improve_csv, metric="rmse")
                    res.generated_csvs.append(period_improve_csv)

                    df_imp = pd.read_csv(period_improve_csv)
                    out_map_imp_period = os.path.join(eval_period_dir, f"improvement_RMSEpct_stations_{req.var}_{stat_name}_{label}.png")
                    plot_improvement_at_stations_with_dem(
                        df_imp, dem, out_map_imp_period,
                        f"{req.var.upper()} {stat_name} — Mejora de RMSE [%] — {title_label}",
                        extent=extent_plot, show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_map_imp_period)

                    out_box_rmse = os.path.join(eval_period_dir, f"boxplot_RMSE_stations_{req.var}_{stat_name}_{label}.png")
                    plot_boxplot_rmse_by_station(df_imp, req.var, stat_name, label, out_box_rmse)
                    res.generated_plots.append(out_box_rmse)

                    out_box_imp = os.path.join(eval_period_dir, f"boxplot_improvement_RMSEpct_stations_{req.var}_{stat_name}_{label}.png")
                    plot_boxplot_improvement_pct_by_station(df_imp, req.var, stat_name, label, out_box_imp)
                    res.generated_plots.append(out_box_imp)

                    out_sc_rmse = os.path.join(eval_period_dir, f"scatter_RMSE_raw_vs_corr_{req.var}_{stat_name}_{label}.png")
                    plot_scatter_rmse_raw_vs_corr(df_imp, req.var, stat_name, label, out_sc_rmse)
                    res.generated_plots.append(out_sc_rmse)

                    out_box_err = os.path.join(eval_period_dir, f"boxplot_errors_{req.var}_{stat_name}_{label}.png")
                    plot_boxplot_errors_single(csv_path, req.var, stat_name, out_box_err)
                    res.generated_plots.append(out_box_err)

                    out_sc_obs = os.path.join(eval_period_dir, f"scatter_obs_vs_grid_{req.var}_{stat_name}_{label}.png")
                    plot_scatter_obs_vs_grid_single(
                        csv_path, req.var, stat_name, out_sc_obs,
                        title=f"CHIRTS {req.var.upper()} {stat_name.capitalize()} — Observado vs Rejilla — {title_label}"
                    )
                    res.generated_plots.append(out_sc_obs)

        # Resumen global y rankings para todos los períodos evaluados
        all_period_csvs = [c for c in res.generated_csvs if "cmp_estaciones" in c]
        if all_period_csvs:
            try:
                base_stat = stats_to_run[0]
                period_base_eval_dir = os.path.join(req.out_dir, req.var, "eval", "period", base_stat)
                df_metrics, metrics_csv = compute_annual_metrics_from_csv(all_period_csvs, req.var, base_stat, period_base_eval_dir)
                if metrics_csv:
                    res.generated_csvs.append(metrics_csv)
                res.metrics_df = df_metrics

                png_sc_glob = plot_scatter_obs_vs_grid(
                    all_period_csvs, req.var, base_stat, period_base_eval_dir,
                    title=f"CHIRTS {req.var.upper()} {base_stat.capitalize()} — Observado vs Rejilla — Resumen Global ({len(all_period_csvs)} Períodos)"
                )
                if png_sc_glob:
                    res.generated_plots.append(png_sc_glob)

                png_box_glob = plot_boxplot_errors(all_period_csvs, req.var, base_stat, period_base_eval_dir)
                if png_box_glob:
                    res.generated_plots.append(png_box_glob)

                df_rank = compute_station_metrics_global(all_period_csvs, req.var, base_stat)
                rank_csv = os.path.join(period_base_eval_dir, f"ranking_stations_period_{req.var}_{base_stat}.csv")
                df_rank.to_csv(rank_csv, index=False, float_format="%.4f")
                res.generated_csvs.append(rank_csv)
                res.rankings_df = df_rank
            except Exception as e:
                res.execution_logs.append(_log_msg(f"Advertencia en métricas globales de períodos: {e}"))

        # Climatología DOY 1–365 por Estación
        try:
            base_stat = stats_to_run[0] if stats_to_run else "mean"
            period_base_eval_dir = os.path.join(req.out_dir, req.var, "eval", "period", base_stat)
            generate_doy_climatology_for_stations(
                df_obs_long, req, res, period_base_eval_dir,
                progress=progress, cancel_check=cancel_check,
                pct_start=0.92, pct_end=0.99,
            )
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Advertencia en generación DOY períodos: {e}"))

        fin_msg = f"Análisis de períodos de CHIRTS ({req.var}) completado exitosamente."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res

    def _run_annual(
        self, req: AnalysisRequest, df_obs_long: pd.DataFrame, res: AnalysisResult, progress: ProgressCallback, cancel_check: CancelCheck = None
    ) -> AnalysisResult:
        if progress:
            progress(0.05, f"Iniciando evaluación anual para CHIRTS ({req.var})...")
        res.execution_logs.append(_log_msg(f"Iniciando evaluación anual (CHIRTS {req.var})..."))

        yini = req.yini or 1991
        yend = req.yend or 2020
        years = list(range(yini, yend + 1))
        stats_to_run = [req.stat.value] if (req.stat and req.stat != StatType.ALL) else ["mean", "max", "min"]

        total_steps = len(stats_to_run) * len(years)
        step_idx = 0
        extent_plot = None

        dem = None
        if req.dem_path and os.path.exists(req.dem_path):
            try:
                dem = load_dem_dataset(req.dem_path)
            except Exception:
                dem = None

        for stat_name in stats_to_run:
            out_maps_dir = os.path.join(req.out_dir, req.var, stat_name)
            global_dir = os.path.join(req.out_dir, req.var, "eval", "annual", stat_name)
            os.makedirs(out_maps_dir, exist_ok=True)
            os.makedirs(global_dir, exist_ok=True)

            deltas_for_global = []

            for year in years:
                if cancel_check and cancel_check():
                    cancel_msg = f"🛑 Proceso cancelado por el usuario en año {year}."
                    res.execution_logs.append(_log_msg(cancel_msg))
                    res.error_message = cancel_msg
                    res.success = False
                    if progress:
                        progress(1.0, cancel_msg)
                    return res

                step_idx += 1
                pct = 0.05 + 0.85 * (step_idx / max(total_steps, 1))
                step_msg = f"Procesando {req.var.upper()} {stat_name} para el año {year}..."
                if progress:
                    progress(pct, step_msg)
                res.execution_logs.append(_log_msg(step_msg))

                da_raw = load_annual_chirts_raw(req.dir_original, year, req.prefix_original, stat=stat_name)
                da_corr = load_annual_chirts_corr(req.dir_merged, year, prefix=req.var, stat=stat_name)

                stations_obs_year = annual_station_stat(df_obs_long, year, req.var, stat_name)

                extent_plot = req.extent or (
                    float(da_raw.lon.min()), float(da_raw.lon.max()),
                    float(da_raw.lat.min()), float(da_raw.lat.max())
                )

                out_png_map = os.path.join(out_maps_dir, f"{req.var}_{stat_name}_anual_{year}.png")
                plot_side_by_side(
                    da_left=da_raw, da_right=da_corr, dem=dem, year=year,
                    var=req.var, stat=stat_name, stations_obs_year=stations_obs_year, out_png=out_png_map, extent=extent_plot,
                    show_labels=req.show_labels,
                )
                res.generated_maps.append(out_png_map)

                csv_cmp_year = os.path.join(out_maps_dir, f"{req.var}_{stat_name}_anual_{year}_cmp_estaciones.csv")
                export_cmp_csv(stations_obs_year, da_raw, da_corr, year, req.var, stat_name, csv_cmp_year)
                res.generated_csvs.append(csv_cmp_year)

                delta_yr = da_corr - da_raw
                deltas_for_global.append(delta_yr)

                year_dir = os.path.join(global_dir, str(year))
                os.makedirs(year_dir, exist_ok=True)

                out_png_delta_field = os.path.join(year_dir, f"delta_grid_field_{req.var}_{stat_name}_{year}.png")
                plot_delta_grid_field(
                    da_raw, da_corr, dem, out_png_delta_field,
                    f"{req.var.upper()} {stat_name.capitalize()} — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — {year}",
                    extent=extent_plot, stations_df=stations_obs_year,
                    show_labels=req.show_labels
                )
                res.generated_maps.append(out_png_delta_field)

                if os.path.exists(csv_cmp_year):
                    df_cmp_yr = pd.read_csv(csv_cmp_year)
                    if "grid_corr" in df_cmp_yr.columns and "grid_raw" in df_cmp_yr.columns:
                        df_cmp_yr["delta_grid"] = df_cmp_yr["grid_corr"] - df_cmp_yr["grid_raw"]
                        out_png_delta_st = os.path.join(year_dir, f"delta_grid_stations_{req.var}_{stat_name}_{year}.png")
                        plot_delta_grid_at_stations(
                            df_cmp_yr, dem, out_png_delta_st,
                            f"{req.var.upper()} {stat_name.capitalize()} — Diferencia en estaciones — {year}",
                            extent=extent_plot, show_labels=req.show_labels
                        )
                        res.generated_maps.append(out_png_delta_st)

                    if "err_corr" in df_cmp_yr.columns:
                        df_cmp_yr["residual_corr"] = df_cmp_yr["err_corr"]
                        out_png_resid_st = os.path.join(year_dir, f"residual_corr_stations_{req.var}_{stat_name}_{year}.png")
                        plot_residual_corr_at_stations_with_dem(
                            df_cmp_yr, dem, out_png_resid_st,
                            f"{req.var.upper()} {stat_name.capitalize()} — Residuo (Corr − Obs) en estaciones — {year}",
                            extent=extent_plot, show_labels=req.show_labels
                        )
                        res.generated_maps.append(out_png_resid_st)

                        out_box_yr = os.path.join(year_dir, f"boxplot_errors_{req.var}_{stat_name}_{year}.png")
                        plot_boxplot_errors_single(csv_cmp_year, req.var, stat_name, out_box_yr)
                        res.generated_plots.append(out_box_yr)

                        out_sc_yr = os.path.join(year_dir, f"scatter_obs_vs_grid_{req.var}_{stat_name}_{year}.png")
                        plot_scatter_obs_vs_grid_single(
                            csv_cmp_year, req.var, stat_name, out_sc_yr,
                            title=f"CHIRTS {req.var.upper()} {stat_name.capitalize()} — Observado vs Rejilla — {year}"
                        )
                        res.generated_plots.append(out_sc_yr)

            # Construir CSV global de estaciones a partir de todos los años evaluados
            csv_pattern = os.path.join(out_maps_dir, f"{req.var}_{stat_name}_anual*cmp_estaciones*.csv")
            csv_files = sorted(glob.glob(csv_pattern))
            df_glob = None

            if csv_files:
                global_csv = os.path.join(global_dir, f"global_cmp_estaciones_{req.var}_{stat_name}.csv")
                build_global_station_csv(csv_files, global_csv)
                res.generated_csvs.append(global_csv)

                if os.path.exists(global_csv):
                    df_glob = pd.read_csv(global_csv)
                    if "grid_corr" in df_glob.columns and "grid_raw" in df_glob.columns:
                        df_glob["delta_grid"] = df_glob["grid_corr"] - df_glob["grid_raw"]
                    if "err_corr" in df_glob.columns:
                        df_glob["residual_corr"] = df_glob["err_corr"]

            if deltas_for_global:
                delta_global = xr.concat(deltas_for_global, dim="time").mean("time")
                out_png_delta_field_global = os.path.join(global_dir, f"delta_grid_field_{req.var}_{stat_name}_GLOBAL.png")
                plot_delta_grid_field(
                    None, None, dem, out_png_delta_field_global,
                    f"{req.var.upper()} {stat_name.capitalize()} — Diferencia espacial (ΔGRID = GRID_corr - GRID_original) — GLOBAL",
                    extent=extent_plot, delta_override=delta_global,
                    stations_df=df_glob,
                    show_labels=req.show_labels
                )
                res.generated_maps.append(out_png_delta_field_global)

            if req.eval_stats and csv_files:
                eval_msg = f"Calculando evaluación estadística anual ({req.var} {stat_name})..."
                if progress:
                    progress(pct, eval_msg)
                res.execution_logs.append(_log_msg(eval_msg))

                if df_glob is not None:
                    if "delta_grid" in df_glob.columns:
                        out_png_delta_st_glob = os.path.join(global_dir, f"delta_grid_stations_{req.var}_{stat_name}_GLOBAL.png")
                        plot_delta_grid_at_stations(
                            df_glob, dem, out_png_delta_st_glob,
                            f"{req.var.upper()} {stat_name.capitalize()} — Diferencia en estaciones — GLOBAL",
                            extent=extent_plot, show_labels=req.show_labels
                        )
                        res.generated_maps.append(out_png_delta_st_glob)

                    if "residual_corr" in df_glob.columns:
                        out_png_resid_st_glob = os.path.join(global_dir, f"residual_corr_stations_{req.var}_{stat_name}_GLOBAL.png")
                        plot_residual_corr_at_stations_with_dem(
                            df_glob, dem, out_png_resid_st_glob,
                            f"{req.var.upper()} {stat_name.capitalize()} — Residuo (Corr − Obs) en estaciones — GLOBAL",
                            extent=extent_plot, show_labels=req.show_labels
                        )
                        res.generated_maps.append(out_png_resid_st_glob)

                    global_improve_csv = os.path.join(global_dir, f"improvement_stations_{req.var}_{stat_name}_RMSE.csv")
                    build_station_improvement_csv(csv_files, req.var, stat_name, global_improve_csv, metric="rmse")
                    res.generated_csvs.append(global_improve_csv)
                    df_imp_global = pd.read_csv(global_improve_csv)

                    out_map_imp_global = os.path.join(global_dir, f"improvement_RMSEpct_stations_{req.var}_{stat_name}_GLOBAL.png")
                    plot_improvement_at_stations_with_dem(
                        df_imp_global, dem, out_map_imp_global,
                        f"{req.var.upper()} {stat_name.capitalize()} — Mejora vs estaciones — GLOBAL",
                        extent=extent_plot, show_labels=req.show_labels
                    )
                    res.generated_maps.append(out_map_imp_global)

                    df_metrics, metrics_csv = compute_annual_metrics_from_csv(csv_files, req.var, stat_name, global_dir)
                    res.generated_csvs.append(metrics_csv)
                    res.metrics_df = df_metrics

                    png_rmse = plot_rmse_bars(df_metrics, req.var, stat_name, global_dir)
                    res.generated_plots.append(png_rmse)

                    png_kge = plot_kge_components(df_metrics, req.var, stat_name, global_dir)
                    if png_kge:
                        res.generated_plots.append(png_kge)

                    png_box = plot_boxplot_errors(csv_files, req.var, stat_name, global_dir)
                    if png_box:
                        res.generated_plots.append(png_box)

                    png_sc = plot_scatter_obs_vs_grid(
                        csv_files, req.var, stat_name, global_dir,
                        title=f"CHIRTS {req.var.upper()} {stat_name.capitalize()} — Observado vs Rejilla — GLOBAL"
                    )
                    if png_sc:
                        res.generated_plots.append(png_sc)

                    df_rank_global = compute_station_metrics_global(csv_files, req.var, stat_name)
                    rank_global_csv = os.path.join(global_dir, f"ranking_stations_global_{req.var}_{stat_name}.csv")
                    df_rank_global.to_csv(rank_global_csv, index=False, float_format="%.4f")
                    res.generated_csvs.append(rank_global_csv)
                    res.rankings_df = df_rank_global

        # Climatología DOY 1–365 por Estación
        try:
            base_stat = stats_to_run[0] if stats_to_run else "mean"
            base_eval_dir = os.path.join(req.out_dir, req.var, "eval", "annual", base_stat)
            generate_doy_climatology_for_stations(
                df_obs_long, req, res, base_eval_dir,
                progress=progress, cancel_check=cancel_check,
                pct_start=0.94, pct_end=0.99,
            )
        except Exception as e:
            res.execution_logs.append(_log_msg(f"Advertencia en generación DOY anual: {e}"))

        fin_msg = "Análisis anual completado exitosamente."
        if progress:
            progress(1.0, fin_msg)
        res.execution_logs.append(_log_msg(fin_msg))
        res.success = True
        return res


def write_execution_status(out_dir: str, data: Dict) -> None:
    """Escribe el estado de ejecución y metadatos de integridad en disco."""
    try:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "execution_status.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def read_execution_status(out_dir: str) -> Optional[Dict]:
    """Lee el estado de ejecución previo desde disco si existe."""
    path = os.path.join(out_dir, "execution_status.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class AnalysisRunner:
    """Punto de entrada unificado para ejecutar cualquier solicitud de análisis."""

    def __init__(self):
        self.chirps_service = ChirpsService()
        self.chirts_service = ChirtsService()

    def run(
        self,
        req: AnalysisRequest,
        progress_callback: ProgressCallback = None,
        progress: ProgressCallback = None,
        cancel_check: CancelCheck = None,
    ) -> AnalysisResult:
        cb = progress_callback or progress
        val_res = validate_analysis_request(req)
        if not val_res.is_valid:
            res = AnalysisResult(success=False, is_completed=False, output_dir=req.out_dir)
            res.error_message = "\n".join(val_res.errors)
            res.execution_logs.extend([_log_msg(f"Error de validación: {e}") for e in val_res.errors])
            return res

        # 1. Registrar flag inicial de ejecución INCONCLUSA en disco
        status_info = {
            "status": "INCOMPLETE",
            "started_at": datetime.datetime.now().isoformat(),
            "completed_at": None,
            "product": req.product.value,
            "var": req.var,
            "mode": req.mode.value,
            "stat": req.stat.value if req.stat else None,
            "yini": req.yini,
            "yend": req.yend,
            "date_str": req.date_str,
            "season": req.season,
            "months": req.months,
            "eval_stats": req.eval_stats,
            "error": None,
        }
        write_execution_status(req.out_dir, status_info)

        # 2. Ejecutar procesamiento del servicio correspondiente
        if req.product == ProductType.CHIRPS:
            res = self.chirps_service.run(req, progress_callback=cb, cancel_check=cancel_check)
        else:
            res = self.chirts_service.run(req, progress_callback=cb, cancel_check=cancel_check)

        # 3. Actualizar flag final en disco según resultado
        if res.success:
            status_info["status"] = "COMPLETED"
            status_info["completed_at"] = datetime.datetime.now().isoformat()
            status_info["generated_maps_count"] = len(res.generated_maps)
            status_info["generated_plots_count"] = len(res.generated_plots)
            status_info["generated_csvs_count"] = len(res.generated_csvs)
            res.is_completed = True
            res.completion_metadata = status_info
        else:
            status_info["status"] = "INCOMPLETE"
            status_info["error"] = res.error_message
            res.is_completed = False
            res.completion_metadata = status_info

        write_execution_status(req.out_dir, status_info)
        return res


def detect_existing_results(out_dir: str, req: Optional[AnalysisRequest] = None) -> Optional[AnalysisResult]:
    """
    Inspecciona recursivamente el directorio de salida (out_dir) para detectar si existen
    productos generados previamente (mapas PNG, gráficos estadísticos, CSVs de métricas, rankings, etc.).
    Verifica además el flag de integridad (execution_status.json) para reportar si la ejecución fue completada
    o quedó inconclusa.
    """
    if not os.path.exists(out_dir):
        return None

    png_files = sorted(glob.glob(os.path.join(out_dir, "**", "*.png"), recursive=True))
    csv_files = sorted(glob.glob(os.path.join(out_dir, "**", "*.csv"), recursive=True))

    if not png_files and not csv_files:
        return None

    # Leer flag de integridad de ejecución
    status_meta = read_execution_status(out_dir)
    if status_meta is not None:
        is_completed = (status_meta.get("status") == "COMPLETED")
    else:
        is_completed = True

    res = AnalysisResult(
        success=True,
        is_completed=is_completed,
        completion_metadata=status_meta or {},
        output_dir=out_dir,
        request=req,
    )

    # Clasificar PNGs entre mapas y gráficos estadísticos
    for p in png_files:
        bname = os.path.basename(p).lower()
        if any(keyword in bname for keyword in ["improvement", "delta_grid", "residual_corr"]):
            res.generated_maps.append(p)
        elif any(keyword in bname for keyword in ["boxplot", "scatter", "rmse", "kge", "clim_doy", "climatology_doy", "bars"]):
            res.generated_plots.append(p)
            # Detectar gráficos DOY por estación
            doy_match = re.search(r"clim(?:atology)?_doy_.*station_(.+?)\.png", os.path.basename(p))
            if doy_match:
                st_id = doy_match.group(1)
                if st_id not in res.doy_stations:
                    res.doy_stations.append(st_id)
                if st_id not in res.doy_plots_by_station:
                    res.doy_plots_by_station[st_id] = {}
                if "tripanel" in bname:
                    res.doy_plots_by_station[st_id]["tripanel"] = p
                elif "mean" in bname:
                    res.doy_plots_by_station[st_id]["mean"] = p
                elif "max" in bname:
                    res.doy_plots_by_station[st_id]["max"] = p
                elif "min" in bname:
                    res.doy_plots_by_station[st_id]["min"] = p
                else:
                    res.doy_plots_by_station[st_id]["simple"] = p
        else:
            res.generated_maps.append(p)

    res.generated_csvs = csv_files

    # Cargar DataFrames de métricas y rankings si existen en disco
    for c in csv_files:
        bname = os.path.basename(c).lower()
        if "summary_daily_global" in bname and res.summary_global_df is None:
            try:
                res.summary_global_df = pd.read_csv(c)
            except Exception:
                pass
        elif "summary_daily_by_station" in bname and res.summary_station_df is None:
            try:
                res.summary_station_df = pd.read_csv(c)
            except Exception:
                pass
        elif "metrics" in bname and res.metrics_df is None:
            try:
                res.metrics_df = pd.read_csv(c)
            except Exception:
                pass
        elif "ranking" in bname and res.rankings_df is None:
            try:
                res.rankings_df = pd.read_csv(c)
            except Exception:
                pass
        elif "improvement_stations" in bname and res.rankings_df is None:
            try:
                res.rankings_df = pd.read_csv(c)
            except Exception:
                pass

    if res.metrics_df is None and res.summary_global_df is not None:
        res.metrics_df = res.summary_global_df
    if res.rankings_df is None and res.summary_station_df is not None:
        res.rankings_df = res.summary_station_df

    status_str = "COMPLETADA" if is_completed else "INCONCLUSA / PARCIAL"
    res.execution_logs.append(
        _log_msg(f"Se detectaron resultados previos ({status_str}) en '{out_dir}': "
        f"{len(res.generated_maps)} mapas, {len(res.generated_plots)} gráficos, {len(res.generated_csvs)} archivos CSV.")
    )
    return res


def _remove_readonly(func, path, exc_info):
    """Manejador de error para shutil.rmtree en Windows que desbloquea archivos de solo lectura."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def clear_existing_results(out_dir: str) -> None:
    """
    Elimina los archivos generados (*.png, *.csv, *.html y subcarpetas) dentro de out_dir
    para permitir un recálculo limpio desde cero, resolviendo permisos y bloqueos de Windows.
    """
    if not os.path.exists(out_dir):
        return

    # Forzar recolección de basura para cerrar handles de matplotlib y xarray
    gc.collect()

    for item in os.listdir(out_dir):
        item_path = os.path.join(out_dir, item)
        try:
            if os.path.isdir(item_path):
                # Desbloquear archivos recursivamente
                for root, dirs, files in os.walk(item_path, topdown=False):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        try:
                            os.chmod(fpath, stat.S_IWRITE)
                            os.remove(fpath)
                        except Exception:
                            pass
                    for dname in dirs:
                        dpath = os.path.join(root, dname)
                        try:
                            os.chmod(dpath, stat.S_IWRITE)
                            os.rmdir(dpath)
                        except Exception:
                            pass
                try:
                    os.chmod(item_path, stat.S_IWRITE)
                    shutil.rmtree(item_path, onerror=_remove_readonly)
                except Exception:
                    if os.path.exists(item_path):
                        try:
                            os.rmdir(item_path)
                        except Exception:
                            pass
            elif os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in [".png", ".csv", ".html", ".txt", ".json", ".log"]:
                    try:
                        os.chmod(item_path, stat.S_IWRITE)
                        os.remove(item_path)
                    except Exception:
                        pass
        except Exception as e:
            # Continuar silenciosamente
            pass
