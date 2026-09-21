# -*- coding: utf-8 -*-
"""
Exporting utilities for station comparisons, metrics, and summary tables.
"""

import os
from typing import List, Optional
import numpy as np
import pandas as pd
import xarray as xr


def export_cmp_csv(
    stations_obs_year: pd.DataFrame,
    da_raw: xr.DataArray,
    da_corr: xr.DataArray,
    year: str | int,
    var: str,
    stat: str,
    out_csv: str,
    method: str = "nearest",
) -> str:
    """
    Exporta un CSV de comparación por estación entre observaciones y valores en grilla más cercana (o interpolada).

    Para cada estación, extrae el valor de CHIRTS/CHIRPS original y corregido en la
    rejilla (nearest o bilinear/linear), y calcula:
      - obs
      - grid_raw, grid_corr
      - err_raw, err_corr
      - abs_err_raw, abs_err_corr
      - rel_err_raw_pct, rel_err_corr_pct

    Parámetros
    ----------
    stations_obs_year : pandas.DataFrame
        DataFrame con información de estaciones y observaciones.
    da_raw : xarray.DataArray
        Campo original.
    da_corr : xarray.DataArray
        Campo corregido.
    year : str or int
        Año o etiqueta temporal.
    var : str
        Variable ('tmax', 'tmin', 'precip').
    stat : str
        Estadístico ('mean', 'max', 'min', 'daily').
    out_csv : str
        Ruta del archivo CSV a guardar.
    method : str, default 'nearest'
        Método de extracción: 'nearest' o 'linear' / 'bilinear'.

    Retorna
    -------
    str
        Ruta del archivo CSV generado.
    """
    rows = []
    interp_m = "linear" if method.lower() in ["linear", "bilinear"] else "nearest"

    for _, row in stations_obs_year.iterrows():
        st = row["station_id"]
        lat = row["lat"]
        lon = row["lon"]

        obs_col = None
        if "obs" in row.index:
            obs_col = "obs"
        elif f"{var}_{stat}" in row.index:
            obs_col = f"{var}_{stat}"
        elif f"{var}_station" in row.index:
            obs_col = f"{var}_station"
        else:
            candidates = [c for c in row.index if c.startswith(f"{var}_")]
            if len(candidates) == 1:
                obs_col = candidates[0]
            elif "accum_obs" in row.index:
                obs_col = "accum_obs"
            else:
                raise KeyError(
                    f"No se pudo determinar la columna de observación para {var}. "
                    f"Columnas disponibles: {list(row.index)}"
                )

        obs = row[obs_col]

        try:
            if interp_m == "linear":
                raw_val = da_raw.interp(lat=lat, lon=lon, method="linear").values.item()
            else:
                raw_val = da_raw.sel(lat=lat, lon=lon, method="nearest").values.item()
        except Exception:
            raw_val = np.nan

        try:
            if interp_m == "linear":
                corr_val = da_corr.interp(lat=lat, lon=lon, method="linear").values.item()
            else:
                corr_val = da_corr.sel(lat=lat, lon=lon, method="nearest").values.item()
        except Exception:
            corr_val = np.nan

        err_raw = raw_val - obs if np.isfinite(raw_val) and np.isfinite(obs) else np.nan
        err_corr = corr_val - obs if np.isfinite(corr_val) and np.isfinite(obs) else np.nan

        abs_err_raw = np.abs(err_raw) if np.isfinite(err_raw) else np.nan
        abs_err_corr = np.abs(err_corr) if np.isfinite(err_corr) else np.nan

        if np.isfinite(obs) and obs != 0:
            rel_err_raw_pct = 100.0 * abs_err_raw / np.abs(obs)
            rel_err_corr_pct = 100.0 * abs_err_corr / np.abs(obs)
        else:
            rel_err_raw_pct = np.nan
            rel_err_corr_pct = np.nan

        rows.append(
            {
                "station_id": st,
                "lat": lat,
                "lon": lon,
                f"{var}_{stat}_obs": obs,
                "grid_raw": raw_val,
                "grid_corr": corr_val,
                "err_raw": err_raw,
                "err_corr": err_corr,
                "abs_err_raw": abs_err_raw,
                "abs_err_corr": abs_err_corr,
                "rel_err_raw_pct": rel_err_raw_pct,
                "rel_err_corr_pct": rel_err_corr_pct,
            }
        )

    df_out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_out.to_csv(out_csv, index=False, float_format="%.4f")
    return out_csv


def build_station_improvement_csv(
    csv_files: List[str],
    var: str,
    stat: str,
    out_csv: str,
    metric: str = "rmse",
) -> str:
    """
    Construye un CSV de mejora por estación a partir de archivos de comparación diarios o anuales.
    """
    dfs = [pd.read_csv(c) for c in csv_files]
    df_all = pd.concat(dfs, ignore_index=True)

    obs_col = f"{var}_{stat}_obs"
    if obs_col not in df_all.columns:
        raise ValueError(f"No se encontró la columna {obs_col} en los CSVs de entrada.")

    rows = []
    for (sid, lat, lon), g in df_all.groupby(
        ["station_id", "lat", "lon"], as_index=False
    ):
        obs = g[obs_col].astype(float).values
        raw = g["grid_raw"].astype(float).values
        corr = g["grid_corr"].astype(float).values

        m = np.isfinite(obs) & np.isfinite(raw) & np.isfinite(corr)
        if not np.any(m):
            continue

        obs = obs[m]
        raw = raw[m]
        corr = corr[m]
        err_raw = raw - obs
        err_corr = corr - obs

        if metric.lower() == "rmse":
            met_raw = np.sqrt(np.mean(err_raw**2))
            met_corr = np.sqrt(np.mean(err_corr**2))
            label = "RMSE"
        elif metric.lower() == "mae":
            met_raw = np.mean(np.abs(err_raw))
            met_corr = np.mean(np.abs(err_corr))
            label = "MAE"
        else:
            raise ValueError("metric debe ser 'rmse' o 'mae'")

        delta = met_raw - met_corr
        eps = 1e-6
        den = max(met_raw, met_corr, eps)

        if np.isfinite(den):
            improvement_pct = 100.0 * delta / den
        else:
            improvement_pct = np.nan

        rows.append(
            {
                "station_id": sid,
                "lat": lat,
                "lon": lon,
                f"{label}_raw": met_raw,
                f"{label}_corr": met_corr,
                f"delta_{label}": delta,
                f"improvement_{label}_pct": improvement_pct,
                "improvement_pct": improvement_pct,
            }
        )

    df_out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_out.to_csv(out_csv, index=False, float_format="%.4f")
    return out_csv


def build_global_station_csv(csv_files: List[str], out_csv: str) -> str:
    """
    Construye un CSV global por estación promediando métricas en el tiempo.
    """
    dfs = [pd.read_csv(c) for c in csv_files]
    df_all = pd.concat(dfs, ignore_index=True)

    grp = df_all.groupby(["station_id", "lat", "lon"], as_index=False).mean(
        numeric_only=True
    )

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    grp.to_csv(out_csv, index=False, float_format="%.4f")
    return out_csv
