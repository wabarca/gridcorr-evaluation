# -*- coding: utf-8 -*-
"""
Tests for CDT CSV parser.
"""

import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from src.io.cdt_parser import parse_cdt_csv


def test_parse_cdt_csv_valid():
    sample_content = (
        "Date,Station1,Station2\n"
        "Lon,-89.1,-88.5\n"
        "Lat,13.7,13.9\n"
        "Elev,650,420\n"
        "19910101,25.4,30.1\n"
        "19910102,26.0,-99\n"
        "19910103,NA,28.5\n"
    )

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
        f.write(sample_content)
        temp_path = f.name

    try:
        meta, df_long = parse_cdt_csv(temp_path, value_name="tmax_station")

        # Verificar metadatos
        assert len(meta) == 2
        assert list(meta["station_id"]) == ["Station1", "Station2"]
        assert meta.loc[meta["station_id"] == "Station1", "lon"].values[0] == -89.1
        assert meta.loc[meta["station_id"] == "Station1", "elev"].values[0] == 650.0

        # Verificar DataFrame largo
        assert len(df_long) == 6  # 3 fechas * 2 estaciones
        assert "tmax_station" in df_long.columns
        assert "year" in df_long.columns
        assert df_long["year"].iloc[0] == 1991

        # Verificar tratamiento de -99 y NA como np.nan
        st1_vals = df_long[df_long["station_id"] == "Station1"].sort_values("date")["tmax_station"].values
        st2_vals = df_long[df_long["station_id"] == "Station2"].sort_values("date")["tmax_station"].values

        assert st1_vals[0] == 25.4
        assert st1_vals[1] == 26.0
        assert np.isnan(st1_vals[2])

        assert st2_vals[0] == 30.1
        assert np.isnan(st2_vals[1])
        assert st2_vals[2] == 28.5

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_parse_cdt_csv_short_file_raises():
    short_content = "Date,St1\nLon,-89\nLat,13\n"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
        f.write(short_content)
        temp_path = f.name

    try:
        with pytest.raises(ValueError, match="CSV muy corto"):
            parse_cdt_csv(temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
