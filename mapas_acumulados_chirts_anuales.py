# -*- coding: utf-8 -*-
"""
===============================================================================
Evaluación y visualización de CHIRTS vs CHIRTS Corregido
===============================================================================

Autor:        William Abarca
Contacto:     abarca.will@gmail.com
Afiliación:   Gerencia de Meteorología, Observatorio de Amenazas y Recursos Naturales, MARN
Versión:      2.0 (Refactorizado con arquitectura modular y Scientific Core)
Licencia:     GNU General Public License v3.0 (GPL-3.0)

Wrapper de compatibilidad CLI que utiliza el Scientific Core y la Application Layer.
"""

import sys
import os
import argparse

# Asegurar que el directorio raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.application.models import (
    AnalysisRequest,
    ProductType,
    ProcessingMode,
    StatType,
    PeriodType,
)
from src.application.services import AnalysisRunner
from src.config.constants import SEASONS


def main():
    ap = argparse.ArgumentParser(
        description="Mapas anuales CHIRTS vs CHIRTS-corregido (estilo CHIRPS) con relieve y estaciones."
    )
    ap.add_argument("--csv", required=True, help="Archivo CDT con observaciones en estaciones.")
    ap.add_argument("--dir-chirts", required=True, help="Directorio con NetCDF diarios/anuales de CHIRTS original.")
    ap.add_argument("--prefix-chirts", default="temp_", help="Prefijo de archivos CHIRTS originales (default: 'temp_').")
    ap.add_argument("--dir-merged", required=True, help="Directorio con NetCDF de CHIRTS corregido.")
    ap.add_argument("--var", choices=["tmax", "tmin"], required=True, help="Variable a procesar ('tmax' o 'tmin').")
    ap.add_argument("--stat", choices=["mean", "max", "min", "all"], required=True, help="Estadístico ('mean', 'max', 'min', 'all').")
    ap.add_argument("--dem", required=True, help="NetCDF con el modelo digital de elevación (DEM).")
    ap.add_argument("--out", default="./salidas", help="Directorio base de salida.")
    ap.add_argument("--yini", type=int, help="Año inicial para modos annual/period.")
    ap.add_argument("--yend", type=int, help="Año final para modos annual/period.")
    ap.add_argument("--extent", nargs=4, type=float, metavar=("xmin", "xmax", "ymin", "ymax"), help="Extensión geográfica.")
    ap.add_argument(
        "--mode", choices=["annual", "daily", "daily-eval", "period"], default="annual",
        help="Modo de operación ('annual', 'daily', 'daily-eval', 'period')."
    )
    ap.add_argument("--period-type", choices=["season", "months"], help="Tipo de período para modo period.")
    ap.add_argument("--season", choices=list(SEASONS.keys()), help="Temporada (DJFM, A, MJJ, ASO, N).")
    ap.add_argument("--months", help="Lista de meses (ej: 5,6,7) para modo period.")
    ap.add_argument("--all-seasons", action="store_true", help="Procesa todas las temporadas definidas.")
    ap.add_argument(
        "--eval", action="store_true", help="Genera gráficos y tablas de evaluación estadística."
    )
    ap.add_argument("--date", help="Fecha para modo daily: YYYY-MM-DD.")

    args = ap.parse_args()

    months_list = [int(m) for m in args.months.split(",")] if getattr(args, "months", None) else None
    period_type_enum = PeriodType(args.period_type) if getattr(args, "period_type", None) else None

    req = AnalysisRequest(
        product=ProductType.CHIRTS,
        csv_path=args.csv,
        dir_original=args.dir_chirts,
        prefix_original=args.prefix_chirts,
        dir_merged=args.dir_merged,
        var=args.var,
        stat=StatType(args.stat),
        dem_path=args.dem,
        out_dir=args.out,
        yini=args.yini,
        yend=args.yend,
        extent=tuple(args.extent) if args.extent else None,
        mode=ProcessingMode(args.mode),
        period_type=period_type_enum,
        season=args.season,
        all_seasons=args.all_seasons,
        months=months_list,
        eval_stats=args.eval,
        date_str=args.date,
    )

    def print_progress(pct: float, msg: str):
        print(f"[{pct*100:5.1f}%] {msg}")

    runner = AnalysisRunner()
    result = runner.run(req, progress_callback=print_progress)

    if not result.success:
        print(f"Error: {result.error_message}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n✓ Proceso finalizado exitosamente. Salidas guardadas en: {result.output_dir}")


if __name__ == "__main__":
    main()
