# -*- coding: utf-8 -*-
"""
Scientific regression tests ensuring mathematical and numerical equivalence.
"""

import numpy as np
import pandas as pd
import pytest

from src.core.metrics import compute_metrics
from src.core.climatology import get_dates_for_period, make_period_title, compute_climatology_doy_by_station
from src.core.spatial import annual_station_accum, annual_station_stat
import tempfile
import os


def test_scientific_metrics_regression():
    """
    Verifica que las fórmulas científicas devuelvan resultados idénticos
    a la formulación analítica de referencia con tolerancia cero.
    """
    rng = np.random.default_rng(2026)
    obs = rng.normal(25.0, 5.0, size=1000)
    grid_raw = obs + rng.normal(2.0, 1.5, size=1000)   # Sesgo positivo
    grid_corr = obs + rng.normal(0.0, 0.5, size=1000)  # Sesgo nulo, menor dispersión

    bias_raw, mae_raw, rmse_raw = compute_metrics(obs, grid_raw)
    bias_corr, mae_corr, rmse_corr = compute_metrics(obs, grid_corr)

    # Verificación de fórmulas
    expected_bias_raw = np.mean(grid_raw - obs)
    expected_mae_raw = np.mean(np.abs(grid_raw - obs))
    expected_rmse_raw = np.sqrt(np.mean((grid_raw - obs) ** 2))

    np.testing.assert_allclose(bias_raw, expected_bias_raw, rtol=1e-10)
    np.testing.assert_allclose(mae_raw, expected_mae_raw, rtol=1e-10)
    np.testing.assert_allclose(rmse_raw, expected_rmse_raw, rtol=1e-10)

    # Mejora de RMSE
    delta_rmse = rmse_raw - rmse_corr
    improvement_pct = 100.0 * delta_rmse / rmse_raw

    assert delta_rmse > 0
    assert improvement_pct > 0


def test_doy_climatology_regression():
    """
    Verifica que la climatología DOY calcule medias, máximos, mínimos y desvest
    exactas para cada día del año.
    """
    dates = pd.date_range("1991-01-01", "1993-12-31", freq="D")
    df_series = pd.DataFrame({
        "date": dates.strftime("%Y%m%d"),
        "obs": np.full(len(dates), 20.0),
        "raw": np.full(len(dates), 22.0),
        "corr": np.full(len(dates), 20.5),
    })

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f_st:
        df_series.to_csv(f_st.name, index=False)
        st_path = f_st.name

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f_clim:
        clim_path = f_clim.name

    try:
        compute_climatology_doy_by_station(st_path, var="tmax", out_csv=clim_path, drop_feb29=True)
        df_clim = pd.read_csv(clim_path)

        # Debe tener exactamente 365 días
        assert len(df_clim) == 365
        assert list(df_clim["doy"]) == list(range(1, 366))

        # Valores constantes deben tener std=0 y min=max=mean
        np.testing.assert_allclose(df_clim["obs_mean"], 20.0)
        np.testing.assert_allclose(df_clim["obs_max"], 20.0)
        np.testing.assert_allclose(df_clim["obs_min"], 20.0)
        np.testing.assert_allclose(df_clim["obs_std"], 0.0)

        np.testing.assert_allclose(df_clim["raw_mean"], 22.0)
        np.testing.assert_allclose(df_clim["corr_mean"], 20.5)

    finally:
        if os.path.exists(st_path):
            os.remove(st_path)
        if os.path.exists(clim_path):
            os.remove(clim_path)


def test_period_dates_generation():
    """
    Verifica que el generador de fechas de temporadas maneje correctamente
    el cruce de año en DJFM (Diciembre del año anterior + Enero, Febrero, Marzo del año actual).
    """
    dates_djfm_1995 = get_dates_for_period(1995, "season", season="DJFM")
    assert dates_djfm_1995[0] == "19941201"  # Inicia en dic 1994
    assert dates_djfm_1995[-1] == "19950331" # Termina en mar 1995

    # Temporada dentro del mismo año (MJJ: Mayo, Junio, Julio)
    dates_mjj_1995 = get_dates_for_period(1995, "season", season="MJJ")
    assert dates_mjj_1995[0] == "19950501"
    assert dates_mjj_1995[-1] == "19950731"


def test_delta_grid_field_with_stations_overlay(tmp_path):
    """
    Verifica que plot_delta_grid_field genere el mapa de diferencia continua con estaciones superpuestas.
    """
    import xarray as xr
    from src.visualization.maps import plot_delta_grid_field

    lats = np.linspace(13.0, 14.5, 10)
    lons = np.linspace(-90.0, -87.5, 10)

    da_raw = xr.DataArray(np.full((10, 10), 20.0), dims=["lat", "lon"], coords={"lat": lats, "lon": lons})
    da_corr = xr.DataArray(np.full((10, 10), 22.5), dims=["lat", "lon"], coords={"lat": lats, "lon": lons})
    dem = xr.DataArray(np.full((10, 10), 500.0), dims=["lat", "lon"], coords={"lat": lats, "lon": lons})

    stations_df = pd.DataFrame({
        "station_id": ["ST1", "ST2"],
        "lat": [13.5, 14.0],
        "lon": [-89.0, -88.5],
        "delta_grid": [2.5, 2.5]
    })

    out_png = str(tmp_path / "delta_grid_test.png")
    res = plot_delta_grid_field(
        da_raw=da_raw,
        da_corr=da_corr,
        dem=dem,
        out_png=out_png,
        title="Test Delta Grid with Stations",
        stations_df=stations_df,
        units="°C"
    )

    assert os.path.exists(res)
    assert os.path.getsize(res) > 1000


def test_adaptive_labeling_logic():
    """
    Verifica la lógica adaptativa _should_show_labels para escalas de país vs regional.
    """
    from src.visualization.maps import _should_show_labels

    extent_sv = (-90.15, -87.55, 13.15, 14.45)
    extent_ca = (-92.3, -77.1, 7.1, 18.5)

    # 1. Dataset tipo país (El Salvador ~14 estaciones)
    # En extent de país (<= 5.0°) -> Muestra etiquetas
    df_country = pd.DataFrame({"lon": np.linspace(-89.5, -88.0, 14), "lat": np.linspace(13.3, 14.2, 14), "obs": 1500})
    assert _should_show_labels(df_country, extent_sv) is True

    # En extent regional / Centroamérica (> 5.0°) -> NUNCA muestra etiquetas
    assert _should_show_labels(df_country, extent_ca) is False

    # 2. Dataset regional en dominio regional amplio (>5.0°) -> Desactiva etiquetas
    df_ca_dense = pd.DataFrame({
        "lon": np.linspace(-91.0, -78.0, 45),
        "lat": np.linspace(8.0, 17.0, 45),
        "obs": np.random.uniform(1000, 2000, 45),
    })
    assert _should_show_labels(df_ca_dense, extent_ca) is False
    assert _should_show_labels(df_ca_dense, extent_ca, show_labels=True) is False

    # 3. Forzado explícito por usuario en escala país
    assert _should_show_labels(df_country, extent_sv, show_labels=True) is True
    assert _should_show_labels(df_country, extent_sv, show_labels=False) is False
    assert _should_show_labels(None, extent_sv) is False



