# -*- coding: utf-8 -*-
"""
Mapas de acumulados anuales: CHIRPS vs CHIRPS corregido (lado a lado) con
puntos de estaciones (VALORES OBSERVADOS desde el CSV) y escala de colores global.

Wrapper de compatibilidad CLI que utiliza el Scientific Core y la Application Layer.
Autor: William Abarca (Gerencia de Meteorología, Observatorio de Amenazas y Recursos Naturales, MARN)
"""

import sys
import os
import argparse

# Asegurar que el directorio raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.application.models import AnalysisRequest, ProductType
from src.application.services import AnalysisRunner


def main():
    ap = argparse.ArgumentParser(
        description="Mapas anuales CHIRPS vs CHIRPS-corregido con puntos observados (CSV) y escala global."
    )
    ap.add_argument(
        "--csv", required=True, help="Ruta al CSV CDT (estaciones y datos diarios)."
    )
    ap.add_argument(
        "--dir-chirps",
        required=True,
        help="Carpeta NetCDF CHIRPS (precip_YYYYMMDD.nc).",
    )
    ap.add_argument(
        "--dir-merged",
        required=True,
        help="Carpeta NetCDF CHIRPS corregido (precip_mrg_YYYYMMDD.nc).",
    )
    ap.add_argument(
        "--out",
        default="./salidas",
        help="Carpeta base de salida (se usará <out>/mapas_anuales).",
    )
    ap.add_argument("--yini", type=int, default=1991, help="Año inicial (incluido).")
    ap.add_argument("--yend", type=int, default=2020, help="Año final (incluido).")
    ap.add_argument(
        "--extent",
        nargs=4,
        type=float,
        metavar=("xmin", "xmax", "ymin", "ymax"),
        help="Extensión del mapa (lon_min lon_max lat_min lat_max).",
    )
    ap.add_argument(
        "--export-csv",
        action="store_true",
        help="Exporta CSV con acumulados observados por estación (por año).",
    )
    args = ap.parse_args()

    req = AnalysisRequest(
        product=ProductType.CHIRPS,
        csv_path=args.csv,
        dir_original=args.dir_chirps,
        dir_merged=args.dir_merged,
        out_dir=args.out,
        yini=args.yini,
        yend=args.yend,
        extent=tuple(args.extent) if args.extent else None,
        export_csv=args.export_csv,
    )

    def print_progress(pct: float, msg: str):
        print(f"[{pct*100:5.1f}%] {msg}")

    runner = AnalysisRunner()
    result = runner.run(req, progress_callback=print_progress)

    if not result.success:
        print(f"Error: {result.error_message}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"✓ Proceso finalizado exitosamente. Mapas guardados en: {result.output_dir}")


if __name__ == "__main__":
    main()
