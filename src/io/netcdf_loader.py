# -*- coding: utf-8 -*-
"""
NetCDF loading and coordinate normalization utilities.
"""

import os
import glob
from typing import List, Optional
import xarray as xr

from ..config.constants import FILL_VALUE


def rename_coords_latlon(da: xr.DataArray) -> xr.DataArray:
    """
    Normaliza los nombres de coordenadas espaciales de un DataArray a 'lon' y 'lat'.

    Detecta variaciones comunes como 'longitude', 'long', 'x' y 'latitude', 'y'.

    Parámetros
    ----------
    da : xarray.DataArray
        DataArray de entrada.

    Retorna
    -------
    xarray.DataArray
        DataArray con dimensiones/coordenadas normalizadas a 'lon' y 'lat'.
    """
    coord_map = {}
    for cn in list(da.coords):
        low = cn.lower()
        if low in ["longitude", "long", "lon", "x"]:
            coord_map[cn] = "lon"
        elif low in ["latitude", "lat", "y"]:
            coord_map[cn] = "lat"
    if coord_map:
        da = da.rename(coord_map)
    return da


def load_daily_chirts_raw(
    dir_chirts: str, date_str: str, prefix: str = "temp_"
) -> xr.DataArray:
    """
    Carga un archivo diario de producto grillado original (CHIRTS/CHIRPS) en NetCDF.

    Busca un archivo con patrón <prefix>YYYYMMDD.nc dentro de `dir_chirts`
    o utiliza coincidencia inteligente por fecha si el prefijo difiere.

    Parámetros
    ----------
    dir_chirts : str
        Directorio donde residen los NetCDFs originales.
    date_str : str
        Fecha en formato 'YYYY-MM-DD' o 'YYYYMMDD'.
    prefix : str, opcional
        Prefijo del nombre de archivo (por defecto 'temp_').

    Retorna
    -------
    xarray.DataArray
        Campo grillado diario con coordenadas normalizadas.
    """
    ymd = str(date_str).replace("-", "")
    fname = f"{prefix}{ymd}.nc"
    path = os.path.join(dir_chirts, fname)

    if not os.path.exists(path):
        # 1. Intentar búsqueda con glob usando el prefijo dado
        matches = glob.glob(os.path.join(dir_chirts, f"{prefix}{ymd}*.nc"))
        if not matches:
            # 2. Búsqueda inteligente: buscar cualquier archivo que contenga la fecha ymd
            matches = glob.glob(os.path.join(dir_chirts, f"*{ymd}*.nc"))
        if matches:
            path = matches[0]
        else:
            raise FileNotFoundError(f"No se encontró archivo diario original para fecha {date_str} en '{dir_chirts}' (patrones probados: '{fname}', '*{ymd}*.nc')")

    ds = xr.open_dataset(path)
    da = list(ds.data_vars.values())[0]
    da = rename_coords_latlon(da)
    da = da.where(da != FILL_VALUE)

    if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
        da = da.squeeze("time", drop=True)

    return da


def load_daily_chirts_corr(
    dir_merged: str, date_str: str, prefix: Optional[str] = None
) -> xr.DataArray:
    """
    Carga un archivo diario de producto grillado corregido en formato NetCDF.

    Busca automáticamente un archivo con patrón '*_mrg_YYYYMMDD.nc' o `<prefix>_mrg_YYYYMMDD.nc`.

    Parámetros
    ----------
    dir_merged : str
        Directorio con los NetCDFs corregidos.
    date_str : str
        Fecha en formato 'YYYY-MM-DD' o 'YYYYMMDD'.
    prefix : str, opcional
        Prefijo opcional para limitar la búsqueda (ej. 'tmax', 'precip').

    Retorna
    -------
    xarray.DataArray
        Campo grillado diario corregido con coordenadas normalizadas.
    """
    ymd = str(date_str).replace("-", "")
    if prefix:
        pattern = os.path.join(dir_merged, f"{prefix}_mrg_{ymd}*.nc")
    else:
        pattern = os.path.join(dir_merged, f"*_mrg_{ymd}*.nc")

    files = sorted(glob.glob(pattern))

    if not files:
        # Fallback de búsqueda para archivos corregidos que contengan mrg y fecha
        files = sorted(glob.glob(os.path.join(dir_merged, f"*mrg*{ymd}*.nc")))
        if not files:
            files = sorted(glob.glob(os.path.join(dir_merged, f"*{ymd}*.nc")))

    if len(files) == 0:
        raise FileNotFoundError(f"No se encontró archivo corregido con patrón: {pattern} en {dir_merged}")
    if len(files) > 1 and prefix:
        exact = [f for f in files if f"{prefix}_mrg_{ymd}" in os.path.basename(f)]
        if len(exact) == 1:
            files = exact

    path = files[0]
    ds = xr.open_dataset(path)
    da = list(ds.data_vars.values())[0]
    da = rename_coords_latlon(da)
    da = da.where(da != FILL_VALUE)

    if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
        da = da.squeeze("time", drop=True)

    return da


def load_dem_dataset(dem_path: str) -> xr.DataArray:
    """
    Carga un modelo digital de elevación (DEM) en NetCDF y normaliza sus coordenadas.

    Parámetros
    ----------
    dem_path : str
        Ruta al archivo NetCDF del DEM.

    Retorna
    -------
    xarray.DataArray
        DataArray 2D de elevación con coordenadas 'lon' y 'lat'.
    """
    if not os.path.exists(dem_path):
        raise FileNotFoundError(f"No existe el archivo DEM especificado: {dem_path}")

    ds = xr.open_dataset(dem_path)
    da = list(ds.data_vars.values())[0]
    da = rename_coords_latlon(da)

    if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
        da = da.squeeze("time", drop=True)

    return da


def find_matching_netcdf_files(
    directory: str, pattern_prefix: str, year: Optional[int] = None
) -> List[str]:
    """
    Busca archivos NetCDF que coincidan con un prefijo y opcionalmente un año.
    """
    if year is not None:
        glob_pat = os.path.join(directory, f"{pattern_prefix}{year}*.nc")
    else:
        glob_pat = os.path.join(directory, f"{pattern_prefix}*.nc")
    return sorted(glob.glob(glob_pat))
