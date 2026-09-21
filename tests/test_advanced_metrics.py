# -*- coding: utf-8 -*-
"""
Unit and validation tests for advanced climatological metrics (KGE, NSE, PBIAS, Willmott d1, POD, FAR, CSI, FBI).
"""

import numpy as np
import pytest

from src.core.metrics import (
    compute_metrics,
    compute_kge,
    compute_nse,
    compute_pbias,
    compute_willmott_d1,
    compute_rain_detection_metrics,
    compute_quantiles_metrics,
    compute_all_station_metrics,
)


def test_kge_ideal_case():
    """
    Verifica que KGE retorne 1.0 para un modelo perfecto (r=1, alpha=1, beta=1).
    """
    obs = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    sim = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

    kge, r, alpha, beta = compute_kge(obs, sim)
    assert pytest.approx(kge, abs=1e-4) == 1.0
    assert pytest.approx(r, abs=1e-4) == 1.0
    assert pytest.approx(alpha, abs=1e-4) == 1.0
    assert pytest.approx(beta, abs=1e-4) == 1.0


def test_kge_degraded_case():
    """
    Verifica que KGE penalice sesgos en media y dispersión.
    """
    obs = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    sim = np.array([20.0, 40.0, 60.0, 80.0, 100.0])  # r=1, alpha=2, beta=2

    kge, r, alpha, beta = compute_kge(obs, sim)
    assert pytest.approx(r, abs=1e-4) == 1.0
    assert pytest.approx(alpha, abs=1e-4) == 2.0
    assert pytest.approx(beta, abs=1e-4) == 2.0
    # KGE = 1 - sqrt((1-1)^2 + (2-1)^2 + (2-1)^2) = 1 - sqrt(2) ≈ -0.4142
    assert pytest.approx(kge, abs=1e-4) == 1.0 - np.sqrt(2)


def test_nse_ideal_and_degraded():
    """
    Verifica que NSE retorne 1.0 para modelo perfecto y <0 para modelo pobre.
    """
    obs = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    sim_perfect = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    assert pytest.approx(compute_nse(obs, sim_perfect), abs=1e-4) == 1.0

    # Modelo con error mayor que la varianza observada
    sim_bad = np.array([100.0, -50.0, 200.0, -100.0, 300.0])
    assert compute_nse(obs, sim_bad) < 0.0


def test_pbias():
    """
    Verifica cálculo del sesgo porcentual relativo (PBIAS).
    """
    obs = np.array([100.0, 200.0])  # Suma = 300
    sim = np.array([110.0, 220.0])  # Suma = 330, diff = 30 -> +10%
    assert pytest.approx(compute_pbias(obs, sim), abs=1e-4) == 10.0


def test_willmott_d1():
    """
    Verifica cálculo del índice de concordancia modificado de Willmott (d1).
    """
    obs = np.array([10.0, 20.0, 30.0, 40.0])
    sim = np.array([10.0, 20.0, 30.0, 40.0])
    assert pytest.approx(compute_willmott_d1(obs, sim), abs=1e-4) == 1.0


def test_rain_detection_contingency():
    """
    Verifica matriz de contingencia y métricas categóricas (POD, FAR, CSI, FBI).
    """
    obs = np.array([0.0, 5.0, 10.0, 0.0, 15.0])  # Lluvia en idx 1, 2, 4 (3 días)
    sim = np.array([0.0, 8.0, 0.0, 12.0, 20.0])  # Lluvia en idx 1, 3, 4 (3 días)
    # th = 1.0 mm:
    # idx 0: obs=0, sim=0 -> Correct Negative (C)
    # idx 1: obs=5, sim=8 -> Hit (H)
    # idx 2: obs=10, sim=0 -> Miss (M)
    # idx 3: obs=0, sim=12 -> False Alarm (F)
    # idx 4: obs=15, sim=20 -> Hit (H)
    # Total: H=2, M=1, F=1, C=1
    res = compute_rain_detection_metrics(obs, sim, threshold=1.0)
    assert res["Hits"] == 2
    assert res["Misses"] == 1
    assert res["FalseAlarms"] == 1
    assert res["CorrectNegatives"] == 1

    # POD = H / (H + M) = 2 / (2 + 1) = 2/3
    assert pytest.approx(res["POD"], abs=1e-4) == 2.0 / 3.0
    # FAR = F / (H + F) = 1 / (2 + 1) = 1/3
    assert pytest.approx(res["FAR"], abs=1e-4) == 1.0 / 3.0
    # CSI = H / (H + M + F) = 2 / 4 = 0.5
    assert pytest.approx(res["CSI"], abs=1e-4) == 0.5
    # FBI = (H + F) / (H + M) = 3 / 3 = 1.0
    assert pytest.approx(res["FBI"], abs=1e-4) == 1.0


def test_quantiles_metrics():
    """
    Verifica cálculo de cuantiles extremos (P90, P95, P99).
    """
    obs = np.linspace(1, 100, 100)
    sim = np.linspace(2, 101, 100)
    q_dict = compute_quantiles_metrics(obs, sim, quantiles=(0.90, 0.95))
    assert "P90_obs" in q_dict
    assert "P90_grid" in q_dict
    assert "Delta_P90" in q_dict
    assert pytest.approx(q_dict["Delta_P90"], abs=1e-3) == 1.0


def test_all_station_metrics_integration():
    """
    Verifica la función integrada compute_all_station_metrics.
    """
    obs = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    raw = np.array([14.0, 24.0, 35.0, 46.0, 58.0])
    corr = np.array([11.0, 21.0, 30.5, 41.0, 50.5])

    res = compute_all_station_metrics(obs, raw, corr, is_precip=True)
    assert res["Delta_RMSE"] > 0  # Corr mejoró RMSE
    assert res["Improvement_RMSE_pct"] > 0
    assert "KGE_raw" in res
    assert "KGE_corr" in res
    assert "POD_raw" in res


def test_min_valid_samples_threshold():
    """
    Verifica que series con menos muestras válidas que min_valid_samples retornen NaN en KGE, NSE y d1.
    """
    obs = np.array([10.0, 20.0])
    sim = np.array([11.0, 21.0])

    assert np.isnan(compute_nse(obs, sim, min_valid_samples=3))
    assert np.isnan(compute_willmott_d1(obs, sim, min_valid_samples=3))
    kge, r, a, b = compute_kge(obs, sim, min_valid_samples=3)
    assert np.isnan(kge)


def test_spatial_interpolation_methods():
    """
    Verifica que extract_nearest_station_values soporte nearest y linear/bilinear.
    """
    import xarray as xr
    import pandas as pd
    from src.core.spatial import extract_nearest_station_values

    lats = np.array([10.0, 20.0])
    lons = np.array([-90.0, -80.0])
    data = np.array([[100.0, 200.0], [300.0, 400.0]])
    da = xr.DataArray(data, coords={"lat": lats, "lon": lons}, dims=["lat", "lon"])

    st_df = pd.DataFrame({
        "station_id": ["S1"],
        "lat": [15.0],
        "lon": [-85.0]
    })

    val_near = extract_nearest_station_values(da, st_df, method="nearest")
    val_lin = extract_nearest_station_values(da, st_df, method="linear")

    assert np.isfinite(val_near[0])
    assert pytest.approx(val_lin[0], abs=1e-4) == 250.0
