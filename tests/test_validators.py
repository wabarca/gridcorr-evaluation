# -*- coding: utf-8 -*-
"""
Tests for application request validators.
"""

import os
import tempfile
import pytest

from src.application.models import (
    AnalysisRequest,
    ProductType,
    ProcessingMode,
    PeriodType,
)
from src.application.validators import validate_analysis_request


def test_validator_detects_missing_csv():
    req = AnalysisRequest(
        product=ProductType.CHIRPS,
        csv_path="/ruta/inexistente/estaciones.csv",
        dir_original="/ruta/inexistente/orig",
        dir_merged="/ruta/inexistente/mrg",
    )

    res = validate_analysis_request(req)
    assert not res.is_valid
    assert any("El archivo CSV de estaciones no existe" in err for err in res.errors)


def test_validator_detects_missing_dem_for_chirts():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f_csv:
        f_csv.write("Date,S1\nLon,-89\nLat,13\nElev,500\n19910101,25\n")
        csv_p = f_csv.name

    with tempfile.TemporaryDirectory() as d_orig, tempfile.TemporaryDirectory() as d_mrg:
        try:
            req = AnalysisRequest(
                product=ProductType.CHIRTS,
                csv_path=csv_p,
                dir_original=d_orig,
                dir_merged=d_mrg,
                dem_path="/ruta/inexistente/dem.nc",
            )
            res = validate_analysis_request(req)
            assert not res.is_valid
            assert any("DEM no existe" in err for err in res.errors)
        finally:
            if os.path.exists(csv_p):
                os.remove(csv_p)


def test_validator_detects_invalid_daily_date():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as f_csv:
        f_csv.write("Date,S1\nLon,-89\nLat,13\nElev,500\n19910101,25\n")
        csv_p = f_csv.name

    with tempfile.TemporaryDirectory() as d_orig, tempfile.TemporaryDirectory() as d_mrg:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".nc") as f_dem:
            dem_p = f_dem.name

        try:
            req = AnalysisRequest(
                product=ProductType.CHIRTS,
                mode=ProcessingMode.DAILY,
                date_str="fecha-invalida",
                csv_path=csv_p,
                dir_original=d_orig,
                dir_merged=d_mrg,
                dem_path=dem_p,
            )
            res = validate_analysis_request(req)
            assert not res.is_valid
            assert any("Formato de fecha inválido" in err for err in res.errors)
        finally:
            if os.path.exists(csv_p):
                os.remove(csv_p)
            if os.path.exists(dem_p):
                os.remove(dem_p)
