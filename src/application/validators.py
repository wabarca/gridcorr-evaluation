# -*- coding: utf-8 -*-
"""
Input validation layer for analysis requests.
"""

import os
import glob
import re
from datetime import datetime
from typing import Optional

from .models import AnalysisRequest, ValidationResult, ProductType, ProcessingMode, PeriodType
from ..config.constants import SEASONS


def validate_analysis_request(req: AnalysisRequest) -> ValidationResult:
    """
    Valida exhaustivamente una solicitud de análisis antes de su ejecución.
    """
    res = ValidationResult(is_valid=True)

    # 1. Validación de CSV de estaciones
    if not req.csv_path:
        res.add_error("Debe especificar la ruta al archivo CSV de estaciones en formato CDT.")
    elif not os.path.exists(req.csv_path):
        res.add_error(f"El archivo CSV de estaciones no existe: '{req.csv_path}'")
    else:
        try:
            with open(req.csv_path, "r", encoding="utf-8") as f:
                header_lines = [f.readline().strip() for _ in range(5)]
            if len(header_lines) < 5 or any(not line for line in header_lines[:4]):
                res.add_error(
                    "El archivo CSV no cumple con el formato CDT requerido (mínimo 4 filas de metadatos + datos)."
                )
        except Exception as e:
            res.add_error(f"Error al leer el archivo CSV de estaciones: {str(e)}")

    # 2. Validación de directorio original
    if not req.dir_original:
        res.add_error("Debe especificar el directorio con archivos NetCDF originales.")
    elif not os.path.isdir(req.dir_original):
        res.add_error(f"El directorio original no existe o no es una carpeta válida: '{req.dir_original}'")
    else:
        nc_files = glob.glob(os.path.join(req.dir_original, "*.nc"))
        if not nc_files:
            res.add_warning(f"No se encontraron archivos .nc en el directorio original: '{req.dir_original}'")

    # 3. Validación de directorio corregido
    if not req.dir_merged:
        res.add_error("Debe especificar el directorio con archivos NetCDF corregidos.")
    elif not os.path.isdir(req.dir_merged):
        res.add_error(f"El directorio corregido no existe o no es una carpeta válida: '{req.dir_merged}'")
    else:
        nc_files = glob.glob(os.path.join(req.dir_merged, "*.nc"))
        if not nc_files:
            res.add_warning(f"No se encontraron archivos .nc en el directorio corregido: '{req.dir_merged}'")

    # 4. Validación de DEM (Obligatorio para CHIRTS)
    if req.product == ProductType.CHIRTS:
        if not req.dem_path:
            res.add_error("Debe especificar la ruta al archivo DEM en NetCDF para el relieve sombreado de temperatura.")
        elif not os.path.exists(req.dem_path):
            res.add_error(f"El archivo DEM no existe: '{req.dem_path}'")

    # 5. Validación según el modo de procesamiento
    if req.mode == ProcessingMode.DAILY:
        if not req.date_str:
            res.add_error("El parámetro 'date_str' (YYYY-MM-DD) es obligatorio en modo diario (DAILY).")
        else:
            try:
                datetime.strptime(req.date_str, "%Y-%m-%d")
            except ValueError:
                res.add_error(f"Formato de fecha inválido para modo diario: '{req.date_str}'. Use 'YYYY-MM-DD'.")

    elif req.mode in [ProcessingMode.ANNUAL, ProcessingMode.PERIOD]:
        if req.yini is None or req.yend is None:
            res.add_error("Debe especificar los años inicial y final ('yini' y 'yend').")
        elif req.yini > req.yend:
            res.add_error(f"El año inicial ({req.yini}) no puede ser mayor que el año final ({req.yend}).")

        if req.mode == ProcessingMode.PERIOD:
            if req.period_type is None:
                res.add_error("En modo 'period' debe especificar 'period_type' ('season' o 'months').")
            elif req.period_type == PeriodType.SEASON:
                if not req.all_seasons and (not req.season or req.season not in SEASONS):
                    res.add_error(
                        f"Temporada inválida o no seleccionada: '{req.season}'. Opciones: {list(SEASONS.keys())} o active 'all_seasons'."
                    )
            elif req.period_type == PeriodType.MONTHS:
                if not req.months:
                    res.add_error("Debe especificar al menos un mes (1–12) en modo period_type='months'.")
                else:
                    invalid_months = [m for m in req.months if not (1 <= m <= 12)]
                    if invalid_months:
                        res.add_error(f"Meses inválidos encontrados: {invalid_months}. Deben estar en el rango 1 a 12.")

    # 6. Validación de extent geográfico si fue suministrado
    if req.extent is not None:
        if len(req.extent) != 4:
            res.add_error("La extensión espacial (extent) debe ser una tupla de 4 valores (xmin, xmax, ymin, ymax).")
        else:
            xmin, xmax, ymin, ymax = req.extent
            if xmin >= xmax:
                res.add_error(f"Longitud mínima ({xmin}) debe ser menor que longitud máxima ({xmax}).")
            if ymin >= ymax:
                res.add_error(f"Latitud mínima ({ymin}) debe ser menor que latitud máxima ({ymax}).")

    return res
