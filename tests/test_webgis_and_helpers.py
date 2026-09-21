# -*- coding: utf-8 -*-
"""
Tests for WebGIS raster conversion and helper utilities.
"""

import base64
import numpy as np
import pytest

from src.gui.components.webgis_viewer import (
    raster_to_base64_png,
    BASEMAPS,
    COLORMAPS,
)


def test_raster_to_base64_png_valid():
    """
    Verifica que la conversión de matriz 2D a PNG en base64 genere una cadena válida.
    """
    # Matriz 2D de prueba con valores continuos y NaNs
    data = np.array([
        [10.0, 20.0, np.nan],
        [15.0, 25.0, 30.0],
        [12.0, 18.0, 22.0]
    ], dtype=float)

    b64_str = raster_to_base64_png(data, cmap_name="RdYlBu_r", vmin=10.0, vmax=30.0, opacity=0.8)

    assert isinstance(b64_str, str)
    assert len(b64_str) > 50

    # Decodificar y verificar cabecera PNG
    raw_bytes = base64.b64decode(b64_str)
    assert raw_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_raster_to_base64_png_all_colormaps():
    """
    Verifica que la función funcione correctamente con todas las paletas configuradas.
    """
    data = np.random.uniform(0, 50, size=(10, 10))

    for cmap in COLORMAPS:
        b64_str = raster_to_base64_png(data, cmap_name=cmap, vmin=0.0, vmax=50.0, opacity=0.7)
        assert isinstance(b64_str, str)
        assert len(b64_str) > 0


def test_basemaps_structure():
    """
    Verifica que todos los mapas base configurados contengan URL y atribución.
    """
    assert len(BASEMAPS) >= 3
    for name, info in BASEMAPS.items():
        assert "url" in info
        assert "attribution" in info
        assert info["url"].startswith("http")


def test_webgis_annual_temp_stat_loader(tmp_path):
    """
    Verifica que load_annual_temp_stat cargue correctamente con el prefijo adecuado.
    """
    import xarray as xr
    import pandas as pd
    from src.core.spatial import load_annual_temp_stat

    dir_nc = tmp_path / "raw"
    dir_nc.mkdir()

    # Crear 2 NetCDFs sintéticos con prefijo temp_
    for d in ["19910101", "19910102"]:
        da = xr.DataArray(
            np.ones((5, 5)) * 25.0,
            dims=["lat", "lon"],
            coords={"lat": np.linspace(13, 14, 5), "lon": np.linspace(-89, -88, 5)}
        )
        ds = xr.Dataset({"temp": da})
        ds.to_netcdf(dir_nc / f"temp_{d}.nc")

    da_res = load_annual_temp_stat(
        data_dir=str(dir_nc),
        year=1991,
        prefix="temp_",
        varname="temp",
        stat="mean"
    )
    assert da_res is not None
    assert da_res.shape == (5, 5)
    assert np.allclose(da_res.values, 25.0)


def test_detect_and_clear_existing_results(tmp_path):
    """
    Verifica que detect_existing_results encuentre mapas y métricas existentes y clear_existing_results los limpie.
    """
    from src.application.services import detect_existing_results, clear_existing_results
    import pandas as pd

    out_dir = tmp_path / "salidas_test"
    out_dir.mkdir()

    # Inicialmente vacío
    assert detect_existing_results(str(out_dir)) is None

    # Crear subcarpetas con PNGs y CSVs
    maps_dir = out_dir / "tmax" / "mean"
    maps_dir.mkdir(parents=True)
    (maps_dir / "tmax_mean_anual_1991.png").write_text("dummy image", encoding="utf-8")
    (maps_dir / "boxplot_RMSE_stations.png").write_text("dummy plot", encoding="utf-8")

    global_dir = out_dir / "tmax" / "eval" / "annual" / "mean" / "global"
    global_dir.mkdir(parents=True)
    df_metrics = pd.DataFrame({"stat": ["mean"], "RMSE_raw": [1.5], "RMSE_corr": [0.8]})
    df_metrics.to_csv(global_dir / "metrics_annual_tmax_mean.csv", index=False)

    # Detectar resultados existentes
    res = detect_existing_results(str(out_dir))
    assert res is not None
    assert res.success is True
    assert len(res.generated_maps) == 1
    assert len(res.generated_plots) == 1
    assert len(res.generated_csvs) == 1
    assert res.metrics_df is not None
    assert "RMSE_corr" in res.metrics_df.columns

    # Limpiar resultados
    clear_existing_results(str(out_dir))
    assert detect_existing_results(str(out_dir)) is None


def test_clear_existing_results_handles_readonly(tmp_path):
    """
    Verifica que clear_existing_results elimine archivos incluso si tienen el atributo de solo lectura (Windows).
    """
    import stat
    import os
    from src.application.services import clear_existing_results

    out_dir = tmp_path / "salidas_readonly"
    out_dir.mkdir()
    sub_dir = out_dir / "subdir"
    sub_dir.mkdir()
    f_path = sub_dir / "test_file.csv"
    f_path.write_text("a,b\n1,2", encoding="utf-8")

    # Marcar como solo lectura
    os.chmod(str(f_path), stat.S_IREAD)
    os.chmod(str(sub_dir), stat.S_IREAD)

    clear_existing_results(str(out_dir))
    assert not os.path.exists(str(f_path))


def test_cancellation_mechanism():
    """
    Verifica que el callback cancel_check detenga inmediatamente el procesamiento de servicios.
    """
    from src.application.services import AnalysisRunner
    from src.application.models import AnalysisRequest, ProductType

    runner = AnalysisRunner()
    req = AnalysisRequest(product=ProductType.CHIRPS, csv_path="dummy.csv")

    # Si cancel_check retorna True de inmediato
    cancel_flag = True
    res = runner.run(req, cancel_check=lambda: cancel_flag)
    assert res.success is False
    assert res.error_message is not None
    assert len(res.execution_logs) > 0


def test_execution_status_flag(tmp_path):
    """
    Verifica que el flag de estado de ejecución distinga entre ejecuciones completadas e inconclusas.
    """
    from src.application.services import (
        write_execution_status,
        read_execution_status,
        detect_existing_results,
    )

    out_dir = tmp_path / "test_status"
    out_dir.mkdir()

    # Caso 1: Archivos generados con flag INCOMPLETE
    (out_dir / "map_test.png").write_text("dummy", encoding="utf-8")
    write_execution_status(str(out_dir), {"status": "INCOMPLETE", "error": "Proceso interrumpido"})

    res_incomp = detect_existing_results(str(out_dir))
    assert res_incomp is not None
    assert res_incomp.is_completed is False
    assert res_incomp.completion_metadata.get("status") == "INCOMPLETE"

    # Caso 2: Actualización a COMPLETED
    write_execution_status(str(out_dir), {"status": "COMPLETED", "completed_at": "2026-09-16T23:00:00"})
    res_comp = detect_existing_results(str(out_dir))
    assert res_comp is not None
    assert res_comp.is_completed is True
    assert res_comp.completion_metadata.get("status") == "COMPLETED"



