# -*- coding: utf-8 -*-
"""
Spatial aggregation, station extraction, and hillshade calculations.
"""

import os
import glob
from typing import Optional, Tuple
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import LightSource

from ..config.constants import FILL_VALUE
from ..io.netcdf_loader import rename_coords_latlon


def load_annual_temp_stat(
    data_dir: str, year: int, prefix: str, varname: str, stat: str
) -> xr.DataArray:
    """
    Carga archivos NetCDF diarios de un año y calcula el estadístico solicitado.

    Patrón de búsqueda: <prefix><year>*.nc.

    Parámetros
    ----------
    data_dir : str
        Directorio con los NetCDF diarios.
    year : int
        Año a procesar.
    prefix : str
        Prefijo de los archivos (ej. 'temp_', 'tmax_mrg_').
    varname : str
        Nombre de la variable.
    stat : str
        'mean', 'max' o 'min'.

    Retorna
    -------
    xarray.DataArray
        Campo anual con el estadístico calculado.
    """
    glob_pat = os.path.join(data_dir, f"{prefix}{year}*.nc")
    files = sorted(glob.glob(glob_pat))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos con patrón: {glob_pat}")

    das = []
    for fp in files:
        ds = xr.open_dataset(fp)
        v = varname if varname in ds else list(ds.data_vars)[0]
        da = rename_coords_latlon(ds[v])

        if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
            da = da.squeeze("time", drop=True)

        da = da.where(da != FILL_VALUE)
        das.append(da)
        ds.close()

    da_all = xr.concat(das, dim="time")

    if stat == "mean":
        return da_all.mean("time", skipna=True)
    elif stat == "max":
        return da_all.max("time", skipna=True)
    elif stat == "min":
        return da_all.min("time", skipna=True)
    else:
        raise ValueError(f"Estadístico inválido: {stat}. Debe ser 'mean', 'max' o 'min'.")


def annual_station_stat(
    df_obs_long: pd.DataFrame, year: int, stat: str, value_name: str
) -> pd.DataFrame:
    """
    Calcula un estadístico anual de observaciones por estación para temperatura.
    """
    sub = df_obs_long[df_obs_long["year"] == year].copy()

    if stat == "mean":
        g = sub.groupby("station_id", as_index=False)[value_name].mean()
    elif stat == "max":
        g = sub.groupby("station_id", as_index=False)[value_name].max()
    elif stat == "min":
        g = sub.groupby("station_id", as_index=False)[value_name].min()
    else:
        raise ValueError(f"Estadístico inválido: {stat}")

    g = g.rename(columns={value_name: "obs"})
    st = sub[["station_id", "lon", "lat", "elev"]].drop_duplicates()
    out = g.merge(st, on="station_id", how="left")
    return out[["station_id", "lon", "lat", "elev", "obs"]]


def load_daily_sum_for_year(
    data_dir: str, year: int, pattern_prefix: str, varname: str = "precip"
) -> xr.DataArray:
    """
    Carga archivos NetCDF diarios de precipitación de un año y calcula la suma acumulada anual.

    Preserva la lógica de conteo de días válidos y reemplazo por NaN donde valid_count == 0.
    """
    glob_pat = os.path.join(data_dir, f"{pattern_prefix}{year}*.nc")
    files = sorted(glob.glob(glob_pat))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos con patrón: {glob_pat}")

    annual_sum = None
    valid_count = None

    for fp in files:
        ds = xr.open_dataset(fp)
        v = varname if varname in ds else (list(ds.data_vars)[0] if ds.data_vars else None)
        if v is None:
            ds.close()
            continue

        da = rename_coords_latlon(ds[v])

        if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
            da = da.squeeze("time", drop=True)

        da = da.where(da != FILL_VALUE)

        # Contador de días válidos (1 si no NaN, 0 si NaN)
        day_valid = xr.where(np.isnan(da), 0, 1)

        if annual_sum is None:
            annual_sum = da.fillna(0)
            valid_count = day_valid
        else:
            annual_sum, da_al = xr.align(annual_sum, da, join="outer")
            valid_count, day_valid_al = xr.align(valid_count, day_valid, join="outer")

            annual_sum = annual_sum.fillna(0) + da_al.fillna(0)
            valid_count = valid_count.fillna(0) + day_valid_al.fillna(0)

        ds.close()

    if annual_sum is None:
        raise RuntimeError(f"No se pudo construir suma anual en {data_dir} ({year}).")

    annual_sum = annual_sum.where(valid_count > 0)
    return annual_sum


def annual_station_accum(df_obs_long: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Calcula la suma acumulada anual observada por estación para precipitación.
    """
    col = "precip_station" if "precip_station" in df_obs_long.columns else df_obs_long.columns[2]
    sub = df_obs_long[df_obs_long["year"] == year].copy()
    acc = sub.groupby("station_id", as_index=False)[col].sum(min_count=1)
    acc = acc.rename(columns={col: "accum_obs"})
    st = sub[["station_id", "lon", "lat", "elev"]].drop_duplicates()
    out = acc.merge(st, on="station_id", how="left")
    return out[["station_id", "lon", "lat", "elev", "accum_obs"]]


def extract_nearest_station_values(
    da: xr.DataArray, stations_df: pd.DataFrame, method: str = "nearest"
) -> np.ndarray:
    """
    Extrae los valores de un DataArray en las coordenadas de las estaciones dadas.

    Parámetros
    ----------
    da : xr.DataArray
        Campo en rejilla.
    stations_df : pd.DataFrame
        DataFrame con coordenadas 'lon' y 'lat'.
    method : str, default 'nearest'
        Método de extracción: 'nearest' o 'linear' / 'bilinear'.
    """
    da = rename_coords_latlon(da)
    lons = xr.DataArray(stations_df["lon"].values, dims="points")
    lats = xr.DataArray(stations_df["lat"].values, dims="points")

    interp_m = "linear" if method.lower() in ["linear", "bilinear"] else "nearest"
    try:
        if interp_m == "linear":
            vals = da.interp(lon=lons, lat=lats, method="linear").values
        else:
            vals = da.sel(lon=lons, lat=lats, method="nearest").values
    except Exception:
        vals = np.full(len(stations_df), np.nan)
    return vals


def calculate_hillshade(
    dem: xr.DataArray, azdeg: float = 315.0, altdeg: float = 45.0, vert_exag: float = 1.0
) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    """
    Calcula el sombreado de relieve (hillshade) a partir de un DEM.
    """
    dem = rename_coords_latlon(dem)
    ls = LightSource(azdeg=azdeg, altdeg=altdeg)
    hs = ls.hillshade(dem.values, vert_exag=vert_exag, dx=1, dy=1)
    hs_masked = np.where(dem.values > 0, hs, np.nan)
    extent = (
        float(dem.lon.min()),
        float(dem.lon.max()),
        float(dem.lat.min()),
        float(dem.lat.max()),
    )
    return hs_masked, extent
