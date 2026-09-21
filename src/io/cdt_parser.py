# -*- coding: utf-8 -*-
"""
Parser for station observations in CDT (Climate Data Tool) CSV format.
"""

import re
from typing import Optional, Tuple
import numpy as np
import pandas as pd

from ..config.constants import FILL_VALUE


def parse_cdt_csv(
    csv_path: str, value_name: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Lee un archivo CSV de estaciones en formato CDT y lo convierte a formato largo (tidy).

    Estructura esperada del archivo CDT:
    - Fila 1: IDs de estaciones (primer elemento encabezado/nombre de columna)
    - Fila 2: Longitudes
    - Fila 3: Latitudes
    - Fila 4: Elevaciones
    - Filas siguientes: Fecha (YYYYMMDD) + valores diarios observados por estación

    Parámetros
    ----------
    csv_path : str
        Ruta al archivo CSV en formato CDT.
    value_name : str, opcional
        Nombre de la columna de valores observados en el DataFrame resultante.
        Si es None, se usa por defecto 'precip_station'.

    Retorna
    -------
    meta : pandas.DataFrame
        Metadatos de estaciones con columnas: ['station_id', 'lon', 'lat', 'elev'].
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columnas:
        ['date', 'station_id', <value_name>, 'lon', 'lat', 'elev', 'year'].
    """
    if value_name is None:
        value_name = "precip_station"

    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    if len(lines) < 5:
        raise ValueError("CSV muy corto: se requieren al menos 5 líneas (metadatos + datos).")

    stations_raw = [s.strip() for s in lines[0].split(",")]
    lons_raw = [s.strip() for s in lines[1].split(",")]
    lats_raw = [s.strip() for s in lines[2].split(",")]
    elvs_raw = [s.strip() for s in lines[3].split(",")]

    station_ids = stations_raw[1:]
    lons = [float(x) if x not in ("", "NA", "-99", "-99.0") else np.nan for x in lons_raw[1:]]
    lats = [float(x) if x not in ("", "NA", "-99", "-99.0") else np.nan for x in lats_raw[1:]]
    elevs = [float(x) if x not in ("", "NA", "-99", "-99.0") else np.nan for x in elvs_raw[1:]]

    n = len(station_ids)
    if not (n == len(lons) == len(lats) == len(elevs)):
        raise ValueError("Los metadatos no cuadran en número de elementos (IDs, lon, lat, elev).")

    date_pat = re.compile(r"^\d{8}$")
    data_rows = []

    for row in lines[4:]:
        if not row.strip():
            continue
        parts = [p.strip() for p in row.split(",")]
        date_str = parts[0]
        if not date_pat.match(date_str):
            continue

        vals = []
        for x in parts[1 : 1 + n]:
            if x in ("", "NA"):
                vals.append(np.nan)
            else:
                try:
                    v = float(x)
                    if v == FILL_VALUE:
                        v = np.nan
                    vals.append(v)
                except Exception:
                    vals.append(np.nan)

        data_rows.append([date_str] + vals)

    df_obs = pd.DataFrame(data_rows, columns=["date"] + station_ids)
    meta = pd.DataFrame(
        {"station_id": station_ids, "lon": lons, "lat": lats, "elev": elevs}
    )

    df_obs_long = df_obs.melt(
        id_vars="date", var_name="station_id", value_name=value_name
    )
    df_obs_long = df_obs_long.merge(meta, on="station_id", how="left")
    df_obs_long["year"] = df_obs_long["date"].str.slice(0, 4).astype(int)

    return meta, df_obs_long
