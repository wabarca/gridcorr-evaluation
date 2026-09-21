# -*- coding: utf-8 -*-
"""
Tests for scientific metrics calculations (Bias, MAE, RMSE, Pearson R, Rankings).
"""

import numpy as np
import pandas as pd
import pytest

from src.core.metrics import (
    compute_metrics,
    summarize_daily_global,
    summarize_daily_by_station,
)


def test_compute_metrics_exact_values():
    obs = np.array([20.0, 22.0, 24.0, 26.0])
    grid = np.array([21.0, 21.0, 26.0, 24.0])

    # diff = [+1, -1, +2, -2]
    # bias = (+1 - 1 + 2 - 2) / 4 = 0.0
    # mae = (1 + 1 + 2 + 2) / 4 = 6/4 = 1.5
    # rmse = sqrt((1 + 1 + 4 + 4) / 4) = sqrt(10/4) = sqrt(2.5) ≈ 1.58113883

    bias, mae, rmse = compute_metrics(obs, grid)

    assert np.isclose(bias, 0.0)
    assert np.isclose(mae, 1.5)
    assert np.isclose(rmse, np.sqrt(2.5))


def test_compute_metrics_with_nans():
    obs = np.array([20.0, 22.0, np.nan, 26.0])
    grid = np.array([21.0, np.nan, 26.0, 24.0])

    # Valid pairs: index 0: (20, 21) -> diff = +1
    #              index 3: (26, 24) -> diff = -2
    # bias = (1 - 2)/2 = -0.5
    # mae = (1 + 2)/2 = 1.5
    # rmse = sqrt((1 + 4)/2) = sqrt(2.5)

    bias, mae, rmse = compute_metrics(obs, grid)

    assert np.isclose(bias, -0.5)
    assert np.isclose(mae, 1.5)
    assert np.isclose(rmse, np.sqrt(2.5))


def test_summarize_daily_global():
    df_daily = pd.DataFrame({
        "obs": [20.0, 25.0, 30.0],
        "raw": [22.0, 28.0, 34.0],   # diff: [+2, +3, +4] -> bias=3.0, mae=3.0, rmse=sqrt(29/3)
        "corr": [21.0, 25.5, 30.5],  # diff: [+1, +0.5, +0.5] -> bias=2/3, mae=2/3, rmse=sqrt(1.5/3)
    })

    summary = summarize_daily_global(df_daily, var="tmax")

    assert len(summary) == 1
    assert summary["var"].iloc[0] == "tmax"
    assert summary["Bias_raw"].iloc[0] == 3.0
    assert summary["Delta_RMSE"].iloc[0] > 0  # Corrige el error reduciendo RMSE


def test_summarize_daily_by_station():
    df_daily = pd.DataFrame({
        "station_id": ["ST1", "ST1", "ST2", "ST2"],
        "obs": [20.0, 22.0, 30.0, 32.0],
        "raw": [24.0, 26.0, 31.0, 33.0],   # ST1 diffs +4, ST2 diffs +1
        "corr": [21.0, 23.0, 30.0, 32.0],  # ST1 diffs +1, ST2 diffs 0
    })

    summary = summarize_daily_by_station(df_daily)

    assert len(summary) == 2
    assert "Improvement_RMSE_pct" in summary.columns

    st1 = summary[summary["station_id"] == "ST1"].iloc[0]
    assert np.isclose(st1["RMSE_raw"], 4.0)
    assert np.isclose(st1["RMSE_corr"], 1.0)
    assert np.isclose(st1["Delta_RMSE"], 3.0)
    assert np.isclose(st1["Improvement_RMSE_pct"], 75.0)  # (4-1)/4 = 75%
