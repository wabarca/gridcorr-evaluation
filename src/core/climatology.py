# -*- coding: utf-8 -*-
"""
Climatology calculations: periods, seasons, daily series, and DOY climatologies.
"""

import os
from typing import List, Optional
import numpy as np
import pandas as pd
import xarray as xr

from ..config.constants import SEASONS, MONTH_NAMES_ES
from ..io.netcdf_loader import (
    load_daily_chirts_raw,
    load_daily_chirts_corr,
    rename_coords_latlon,
)


def get_dates_for_period(
    year: int,
    period_type: str,
    season: Optional[str] = None,
    months: Optional[List[int]] = None,
) -> List[str]:
    """
    Genera una lista de fechas diarias (YYYYMMDD) para un período definido.

    Soporta:
    - 'season': usa las definiciones en SEASONS (ej. DJFM cruzando de año).
    - 'months': usa una lista explícita de meses dentro del mismo año.
    """
    dates = []

    if period_type == "season":
        if season not in SEASONS:
            raise ValueError(f"Temporada inválida: {season}. Opciones: {list(SEASONS.keys())}")
        cfg = SEASONS[season]
        months_list = cfg["months"]
        cross = cfg["cross_year"]

        for m in months_list:
            if cross and m == 12:
                y = year - 1
            else:
                y = year
            dates.extend(
                pd.date_range(
                    start=f"{y}-{m:02d}-01",
                    end=pd.Timestamp(f"{y}-{m:02d}-01") + pd.offsets.MonthEnd(1),
                    freq="D",
                )
            )

    elif period_type == "months":
        if not months:
            raise ValueError("Se requiere una lista de meses para period_type='months'.")
        for m in months:
            dates.extend(
                pd.date_range(
                    start=f"{year}-{m:02d}-01",
                    end=pd.Timestamp(f"{year}-{m:02d}-01") + pd.offsets.MonthEnd(1),
                    freq="D",
                )
            )

    return [d.strftime("%Y%m%d") for d in dates]


def make_period_title(
    period_type: str,
    year: int,
    season: Optional[str] = None,
    months: Optional[List[int]] = None,
) -> str:
    """
    Construye un título legible en español para un período temporal.
    """
    if period_type == "season":
        cfg = SEASONS[season]
        months_list = cfg["months"]
        cross = cfg["cross_year"]

        if cross:
            first_month = months_list[0]
            last_month = months_list[-1]
            start_year = year - 1
            end_year = year
        else:
            first_month = months_list[0]
            last_month = months_list[-1]
            start_year = year
            end_year = year

        start_label = f"{MONTH_NAMES_ES[first_month]} {start_year}"
        end_label = f"{MONTH_NAMES_ES[last_month]} {end_year}"

        return f"{season} {year} ({start_label} – {end_label})"

    elif period_type == "months":
        first_month = months[0]
        last_month = months[-1]

        start_label = f"{MONTH_NAMES_ES[first_month]} {year}"
        end_label = f"{MONTH_NAMES_ES[last_month]} {year}"

        months_str = "-".join(str(m) for m in months)

        if len(months) == 1:
            return f"{MONTH_NAMES_ES[first_month]} {year}"
        else:
            return f"Meses {months_str} {year} ({start_label} – {end_label})"

    return str(year)


def load_period_stat_raw(
    dir_chirts: str, dates_ymd: List[str], prefix_chirts: str, stat: str
) -> xr.DataArray:
    """
    Carga campos diarios de producto original para un período y calcula el estadístico temporal.
    """
    das = []
    for ymd in dates_ymd:
        try:
            da = load_daily_chirts_raw(dir_chirts, ymd, prefix_chirts)
            da = rename_coords_latlon(da)
            das.append(da)
        except (FileNotFoundError, OSError):
            continue

    if not das:
        raise FileNotFoundError(f"No se encontraron archivos diarios en '{dir_chirts}' para las fechas solicitadas.")

    da_stack = xr.concat(das, dim="time")
    if stat in ["mean", "avg"]:
        return da_stack.mean("time", skipna=True)
    elif stat in ["accum", "sum", "tot"]:
        return da_stack.sum("time", min_count=1)
    elif stat == "max":
        return da_stack.max("time", skipna=True)
    elif stat == "min":
        return da_stack.min("time", skipna=True)
    else:
        raise ValueError(f"Estadístico inválido: {stat}")


def load_period_stat_corr(
    dir_merged: str, dates_ymd: List[str], var: str, stat: str
) -> xr.DataArray:
    """
    Carga campos diarios de producto corregido para un período y calcula el estadístico temporal.
    """
    das = []
    for ymd in dates_ymd:
        try:
            da = load_daily_chirts_corr(dir_merged, ymd, prefix=var)
            da = rename_coords_latlon(da)
            das.append(da)
        except (FileNotFoundError, OSError):
            continue

    if not das:
        raise FileNotFoundError(f"No se encontraron archivos corregidos en '{dir_merged}' para las fechas solicitadas.")

    da_stack = xr.concat(das, dim="time")
    if stat in ["mean", "avg"]:
        return da_stack.mean("time", skipna=True)
    elif stat in ["accum", "sum", "tot"]:
        return da_stack.sum("time", min_count=1)
    elif stat == "max":
        return da_stack.max("time", skipna=True)
    elif stat == "min":
        return da_stack.min("time", skipna=True)
    else:
        raise ValueError(f"Estadístico inválido: {stat}")


def period_station_stat(
    df_obs_long: pd.DataFrame, dates_ymd: List[str], var: str, stat: str
) -> pd.DataFrame:
    """
    Calcula un estadístico de observaciones por estación para un período dado.
    """
    dfp = df_obs_long[df_obs_long["date"].astype(str).str.replace("-", "").isin(dates_ymd)]

    obs_col = f"{var}_station" if f"{var}_station" in dfp.columns else dfp.columns[2]

    if stat in ["mean", "avg"]:
        s = dfp.groupby("station_id")[obs_col].mean()
    elif stat in ["accum", "sum", "tot"]:
        s = dfp.groupby("station_id")[obs_col].sum()
    elif stat == "max":
        s = dfp.groupby("station_id")[obs_col].max()
    elif stat == "min":
        s = dfp.groupby("station_id")[obs_col].min()
    else:
        raise ValueError(f"Estadístico inválido: {stat}")

    out = s.reset_index().rename(columns={obs_col: "obs"})
    meta = df_obs_long[["station_id", "lon", "lat", "elev"]].drop_duplicates()
    out = out.merge(meta, on="station_id", how="left")
    return out


def build_daily_timeseries(
    df_obs_long: pd.DataFrame,
    dir_chirts: str,
    dir_merged: str,
    var: str,
    prefix_chirts: str,
) -> pd.DataFrame:
    """
    Construye una serie diaria de comparación en estaciones entre observaciones y grillas.
    """
    records = []
    df = df_obs_long.copy()

    obs_col = f"{var}_station" if f"{var}_station" in df.columns else df.columns[2]

    for date_key, g in df.groupby("date"):
        if isinstance(date_key, pd.Timestamp):
            ymd = date_key.strftime("%Y%m%d")
        else:
            ymd = str(date_key).replace("-", "")

        try:
            da_raw = load_daily_chirts_raw(dir_chirts, ymd, prefix_chirts)
            da_corr = load_daily_chirts_corr(dir_merged, ymd, prefix=var)

            da_raw = rename_coords_latlon(da_raw)
            da_corr = rename_coords_latlon(da_corr)

            lons = xr.DataArray(g["lon"].values, dims="points")
            lats = xr.DataArray(g["lat"].values, dims="points")

            try:
                raw_vals = da_raw.sel(lon=lons, lat=lats, method="nearest").values
            except Exception:
                raw_vals = np.full(len(g), np.nan)

            try:
                corr_vals = da_corr.sel(lon=lons, lat=lats, method="nearest").values
            except Exception:
                corr_vals = np.full(len(g), np.nan)
        except Exception:
            raw_vals = np.full(len(g), np.nan)
            corr_vals = np.full(len(g), np.nan)

        for i, (_, r) in enumerate(g.iterrows()):
            records.append(
                {
                    "date": ymd,
                    "station_id": r["station_id"],
                    "lon": r["lon"],
                    "lat": r["lat"],
                    "elev": r["elev"],
                    "obs": r[obs_col],
                    "raw": raw_vals[i],
                    "corr": corr_vals[i],
                }
            )

    df_daily = pd.DataFrame.from_records(records)
    return df_daily


def process_year_worker(args: tuple) -> pd.DataFrame:
    """
    Worker para procesamiento paralelo de un año o período de serie diaria.
    Soporta argumentos tradicionales (year, df_obs_long, ...) y dataframes pre-filtrados.
    """
    if len(args) == 6:
        year, df_obs_long, dir_chirts, dir_merged, var, prefix_chirts = args
        df_year = df_obs_long
    elif len(args) == 5:
        df_year, dir_chirts, dir_merged, var, prefix_chirts = args
    else:
        raise ValueError(f"Argumentos inválidos para process_year_worker: {len(args)}")

    if df_year is None or df_year.empty:
        return pd.DataFrame()

    return build_daily_timeseries(
        df_obs_long=df_year,
        dir_chirts=dir_chirts,
        dir_merged=dir_merged,
        var=var,
        prefix_chirts=prefix_chirts,
    )


def compute_climatology_doy_by_station(
    csv_station: str,
    var: str,
    out_csv: str,
    drop_feb29: bool = True,
    months_order: Optional[List[int]] = None,
) -> str:
    """
    Calcula el ciclo anual o estacional climatológico diario para una estación.
    Soporta series anuales completas (DOY 1–365), meses individuales, agrupaciones de meses
    y temporadas climáticas (incluyendo cruce de año como DJFM).
    """
    df = pd.read_csv(csv_station)
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")

    obs_col = "obs"
    raw_col = "raw"
    corr_col = "corr"

    for c in ["date", obs_col, raw_col, corr_col]:
        if c not in df.columns:
            raise ValueError(f"Falta columna requerida '{c}' en {csv_station}.")

    if drop_feb29:
        df = df[~((df["date"].dt.month == 2) & (df["date"].dt.day == 29))].copy()

    df["month"] = df["date"].dt.month
    df["day"] = df["date"].dt.day

    # Determinar el orden cronológico de meses
    if months_order:
        active_months = [m for m in months_order if m in df["month"].unique()]
    else:
        # Meses presentes en orden natural
        active_months = sorted(df["month"].unique())

    # Agrupar cronológicamente por mes y día
    rows = []
    seq_day = 1

    for m in active_months:
        df_m = df[df["month"] == m]
        days_in_m = sorted(df_m["day"].unique())

        for d in days_in_m:
            g = df_m[df_m["day"] == d]
            m_name = MONTH_NAMES_ES.get(m, f"M{m}")[:3]
            date_label = f"{d:02d}-{m_name}"

            row = {
                "doy": seq_day,
                "month": int(m),
                "day": int(d),
                "date_label": date_label,
            }

            for label, col in zip(["obs", "raw", "corr"], [obs_col, raw_col, corr_col]):
                vals = g[col].astype(float).values
                vals = vals[np.isfinite(vals)]

                if len(vals) == 0:
                    row[f"{label}_mean"] = np.nan
                    row[f"{label}_max"] = np.nan
                    row[f"{label}_min"] = np.nan
                    row[f"{label}_std"] = np.nan
                else:
                    row[f"{label}_mean"] = float(np.nanmean(vals))
                    row[f"{label}_max"] = float(np.nanmax(vals))
                    row[f"{label}_min"] = float(np.nanmin(vals))
                    row[f"{label}_std"] = float(np.nanstd(vals))

            rows.append(row)
            seq_day += 1

    df_out = pd.DataFrame(rows).sort_values("doy").reset_index(drop=True)

    # Calcular acumulación progresiva (cumsum) para la curva acumulada
    for label in ["obs", "raw", "corr"]:
        mean_col = f"{label}_mean"
        accum_col = f"{label}_accum"
        if mean_col in df_out.columns:
            df_out[accum_col] = df_out[mean_col].fillna(0.0).cumsum()

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_out.to_csv(out_csv, index=False, float_format="%.4f")
    return out_csv
