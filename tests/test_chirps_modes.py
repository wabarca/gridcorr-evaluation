# -*- coding: utf-8 -*-
"""
Tests for CHIRPS modes (daily, period, daily_eval) and precipitation maps.
"""

import os
import tempfile
import numpy as np
import pandas as pd
import xarray as xr
import pytest

from src.application.models import (
    AnalysisRequest,
    ProductType,
    ProcessingMode,
    StatType,
    PeriodType,
)
from src.application.services import ChirpsService
from src.visualization.maps import plot_side_by_side
from src.core.climatology import load_period_stat_raw, load_period_stat_corr, period_station_stat


def test_chirps_period_stat_accum():
    # Verify period_station_stat supports accum
    dates_ymd = ["19910501", "19910502"]
    df_obs_long = pd.DataFrame({
        "date": ["19910501", "19910502", "19910601"],
        "station_id": ["ST1", "ST1", "ST1"],
        "lon": [-89.0, -89.0, -89.0],
        "lat": [13.5, 13.5, 13.5],
        "elev": [100, 100, 100],
        "precip_station": [10.0, 15.0, 50.0],
    })
    res_accum = period_station_stat(df_obs_long, dates_ymd, "precip", "accum")
    assert len(res_accum) == 1
    assert res_accum.iloc[0]["obs"] == 25.0

    res_mean = period_station_stat(df_obs_long, dates_ymd, "precip", "mean")
    assert res_mean.iloc[0]["obs"] == 12.5


def test_plot_side_by_side_precip_with_dem(tmp_path):
    # Test precipitation side by side map generation with DEM relief
    lons = np.linspace(-90.0, -88.0, 20)
    lats = np.linspace(13.0, 14.5, 15)

    data_left = np.random.uniform(0, 100, (15, 20))
    data_right = data_left * 0.9

    da_left = xr.DataArray(data_left, coords=[("lat", lats), ("lon", lons)])
    da_right = xr.DataArray(data_right, coords=[("lat", lats), ("lon", lons)])
    da_dem = xr.DataArray(np.random.uniform(0, 2000, (15, 20)), coords=[("lat", lats), ("lon", lons)])

    stations_df = pd.DataFrame({
        "station_id": ["S1", "S2"],
        "lon": [-89.5, -88.5],
        "lat": [13.8, 14.0],
        "obs": [45.0, 80.0],
    })

    out_png = str(tmp_path / "test_precip_map.png")
    res_png = plot_side_by_side(
        da_left=da_left,
        da_right=da_right,
        dem=da_dem,
        year="1991-05-01",
        stations_obs_year=stations_df,
        out_png=out_png,
        var="precip",
        stat="daily",
        extent=(-90.2, -87.8, 12.9, 14.6),
    )
    assert os.path.exists(res_png)
    assert os.path.getsize(res_png) > 1000


def test_detect_existing_results_loads_metrics_and_rankings(tmp_path):
    from src.application.services import detect_existing_results

    out_dir = str(tmp_path / "eval_out")
    os.makedirs(out_dir, exist_ok=True)

    # Crear archivos simulados
    df_metrics = pd.DataFrame({
        "year": [1991, 1992],
        "RMSE_raw": [45.2, 40.1],
        "RMSE_corr": [22.1, 19.5],
        "KGE_raw": [0.45, 0.50],
        "KGE_corr": [0.82, 0.85],
        "POD_raw": [0.65, 0.70],
        "POD_corr": [0.88, 0.90],
    })
    metrics_csv = os.path.join(out_dir, "metrics_annual_precip_daily_eval.csv")
    df_metrics.to_csv(metrics_csv, index=False)

    df_rank = pd.DataFrame({
        "station_id": ["ST1", "ST2"],
        "Delta_RMSE": [15.2, 10.1],
        "Improvement_RMSE_pct": [35.0, 25.0],
        "POD_corr": [0.90, 0.85],
    })
    rank_csv = os.path.join(out_dir, "ranking_stations_precip_daily_eval.csv")
    df_rank.to_csv(rank_csv, index=False)

    # Simular PNGs de boxplot, scatter e improvement
    for fname in ["boxplot_errors_precip_daily_eval.png", "scatter_obs_vs_grid_precip_daily_eval.png", "improvement_RMSEpct_stations_precip_daily_eval.png"]:
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(b"fake image data")

    res = detect_existing_results(out_dir)
    assert res is not None
    assert res.metrics_df is not None
    assert len(res.metrics_df) == 2
    assert "POD_corr" in res.metrics_df.columns
    assert res.rankings_df is not None
    assert len(res.rankings_df) == 2
    assert len(res.generated_plots) >= 2
    assert len(res.generated_maps) >= 1


def test_scatter_and_boxplot_generation(tmp_path):
    from src.visualization.plots import (
        plot_scatter_obs_vs_grid,
        plot_scatter_obs_vs_grid_single,
        plot_boxplot_errors,
        plot_boxplot_errors_single,
    )

    out_dir = str(tmp_path / "plots_test")
    os.makedirs(out_dir, exist_ok=True)

    # Test single CSV with typical columns
    csv_path1 = os.path.join(out_dir, "precip_accum_anual_1998_cmp_estaciones.csv")
    df_cmp = pd.DataFrame({
        "station_id": ["ST1", "ST2", "ST3", "ST4"],
        "precip_accum_obs": [1500.0, 1800.0, 2200.0, 950.0],
        "grid_raw": [1400.0, 1900.0, 2100.0, 1000.0],
        "grid_corr": [1480.0, 1820.0, 2180.0, 960.0],
        "err_raw": [-100.0, 100.0, -100.0, 50.0],
        "err_corr": [-20.0, 20.0, -20.0, 10.0],
    })
    df_cmp.to_csv(csv_path1, index=False)

    csv_path2 = os.path.join(out_dir, "precip_accum_anual_1999_cmp_estaciones.csv")
    df_cmp2 = pd.DataFrame({
        "station_id": ["ST1", "ST2", "ST3", "ST4"],
        "precip_accum_obs": [1600.0, 1750.0, 2300.0, 1100.0],
        "grid_raw": [1500.0, 1850.0, 2200.0, 1150.0],
        "grid_corr": [1590.0, 1760.0, 2290.0, 1110.0],
        "err_raw": [-100.0, 100.0, -100.0, 50.0],
        "err_corr": [-10.0, 10.0, -10.0, 10.0],
    })
    df_cmp2.to_csv(csv_path2, index=False)

    # 1. Single scatter
    sc_single = os.path.join(out_dir, "scatter_single.png")
    plot_scatter_obs_vs_grid_single(csv_path1, "precip", "accum", sc_single)
    assert os.path.exists(sc_single)
    assert os.path.getsize(sc_single) > 1000

    # 2. Single boxplot
    box_single = os.path.join(out_dir, "box_single.png")
    plot_boxplot_errors_single(csv_path1, "precip", "accum", box_single)
    assert os.path.exists(box_single)
    assert os.path.getsize(box_single) > 1000

    # 3. Global scatter
    sc_glob = plot_scatter_obs_vs_grid([csv_path1, csv_path2], "precip", "accum", out_dir)
    assert sc_glob is not None
    assert os.path.exists(sc_glob)
    assert os.path.getsize(sc_glob) > 1000

    # 4. Global boxplot
    box_glob = plot_boxplot_errors([csv_path1, csv_path2], "precip", "accum", out_dir)
    assert box_glob is not None
    assert os.path.exists(box_glob)
    assert os.path.getsize(box_glob) > 1000


def test_generate_doy_climatology_for_stations(tmp_path):
    from src.application.services import generate_doy_climatology_for_stations
    from src.application.models import AnalysisRequest, AnalysisResult, ProductType, ProcessingMode

    out_dir = str(tmp_path / "eval_doy")
    orig_dir = str(tmp_path / "orig")
    merged_dir = str(tmp_path / "merged")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(orig_dir, exist_ok=True)
    os.makedirs(merged_dir, exist_ok=True)

    # Crear netcdfs diarios simulados
    lons = np.linspace(-90.0, -88.0, 5)
    lats = np.linspace(13.0, 14.5, 5)
    for ymd in ["19910501", "19910502", "19920501"]:
        da_r = xr.DataArray(np.full((5, 5), 10.0), coords=[("lat", lats), ("lon", lons)], name="precip")
        da_c = xr.DataArray(np.full((5, 5), 12.0), coords=[("lat", lats), ("lon", lons)], name="precip")
        da_r.to_netcdf(os.path.join(orig_dir, f"precip_{ymd}.nc"))
        da_c.to_netcdf(os.path.join(merged_dir, f"precip_{ymd}.nc"))

    df_obs = pd.DataFrame({
        "date": ["19910501", "19910502", "19920501"],
        "year": [1991, 1991, 1992],
        "station_id": ["ST1", "ST1", "ST1"],
        "lon": [-89.0, -89.0, -89.0],
        "lat": [13.5, 13.5, 13.5],
        "elev": [100, 100, 100],
        "precip_station": [8.0, 15.0, 11.0],
    })

    req = AnalysisRequest(
        product=ProductType.CHIRPS,
        mode=ProcessingMode.ANNUAL,
        csv_path="fake.csv",
        dir_original=orig_dir,
        dir_merged=merged_dir,
        prefix_original="precip_",
        out_dir=out_dir,
        var="precip",
        yini=1991,
        yend=1992,
    )
    res = AnalysisResult(output_dir=out_dir, request=req)

    success = generate_doy_climatology_for_stations(df_obs, req, res, out_dir)
    assert success is True
    assert "ST1" in res.doy_stations
    assert "ST1" in res.doy_plots_by_station
    assert "tripanel" in res.doy_plots_by_station["ST1"]
    assert "mean" in res.doy_plots_by_station["ST1"]
    assert "max" in res.doy_plots_by_station["ST1"]
    assert os.path.exists(res.doy_plots_by_station["ST1"]["tripanel"])


def test_generate_doy_climatology_period_modes(tmp_path):
    from src.application.services import generate_doy_climatology_for_stations
    from src.application.models import AnalysisRequest, AnalysisResult, ProductType, ProcessingMode

    out_dir = str(tmp_path / "eval_doy_period")
    orig_dir = str(tmp_path / "orig")
    merged_dir = str(tmp_path / "merged")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(orig_dir, exist_ok=True)
    os.makedirs(merged_dir, exist_ok=True)

    lons = np.linspace(-90.0, -88.0, 5)
    lats = np.linspace(13.0, 14.5, 5)
    for ymd in ["19910501", "19910502"]:
        da_r = xr.DataArray(np.full((5, 5), 10.0), coords=[("lat", lats), ("lon", lons)], name="precip")
        da_c = xr.DataArray(np.full((5, 5), 12.0), coords=[("lat", lats), ("lon", lons)], name="precip")
        da_r.to_netcdf(os.path.join(orig_dir, f"precip_{ymd}.nc"))
        da_c.to_netcdf(os.path.join(merged_dir, f"precip_{ymd}.nc"))

    df_obs = pd.DataFrame({
        "date": ["19910501", "19910502"],
        "year": [1991, 1991],
        "station_id": ["ST1", "ST1"],
        "lon": [-89.0, -89.0],
        "lat": [13.5, 13.5],
        "elev": [100, 100],
        "precip_station": [8.0, 15.0],
    })

    # Test Modo Mes (Mayo)
    req_month = AnalysisRequest(
        product=ProductType.CHIRPS,
        mode=ProcessingMode.PERIOD,
        period_type="months",
        months=[5],
        csv_path="fake.csv",
        dir_original=orig_dir,
        dir_merged=merged_dir,
        prefix_original="precip_",
        out_dir=out_dir,
        var="precip",
        yini=1991,
        yend=1991,
    )
    res_month = AnalysisResult(output_dir=out_dir, request=req_month)
    success_m = generate_doy_climatology_for_stations(df_obs, req_month, res_month, out_dir)
    assert success_m is True
    assert "ST1" in res_month.doy_stations
    assert os.path.exists(res_month.doy_plots_by_station["ST1"]["tripanel"])




