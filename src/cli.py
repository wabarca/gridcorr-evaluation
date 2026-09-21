# -*- coding: utf-8 -*-
"""
Unified Command Line Interface for CHIRPS & CHIRTS evaluations.
"""

import sys
import argparse
from typing import List, Optional

from .application.models import (
    AnalysisRequest,
    ProductType,
    ProcessingMode,
    StatType,
    PeriodType,
)
from .application.services import AnalysisRunner
from .config.constants import SEASONS


def parse_args_and_run(argv: Optional[List[str]] = None) -> int:
    """Parsea argumentos de línea de comandos y ejecuta el análisis unificado."""
    parser = argparse.ArgumentParser(
        description="CHIRPS & CHIRTS Climate Grids Evaluation Toolkit CLI"
    )
    subparsers = parser.add_subparsers(dest="product", help="Producto a evaluar (chirts / chirps)")

    # 1. Subparser para CHIRTS
    p_chirts = subparsers.add_parser("chirts", help="Evaluación de temperatura CHIRTS")
    p_chirts.add_argument("--csv", required=True, help="Ruta al CSV CDT con estaciones y observaciones.")
    p_chirts.add_argument("--dir-chirts", required=True, help="Directorio con NetCDF diarios originales.")
    p_chirts.add_argument("--prefix-chirts", default="temp_", help="Prefijo de archivos originales (default: 'temp_').")
    p_chirts.add_argument("--dir-merged", required=True, help="Directorio con NetCDF diarios corregidos.")
    p_chirts.add_argument("--var", choices=["tmax", "tmin"], required=True, help="Variable a evaluar.")
    p_chirts.add_argument("--stat", choices=["mean", "max", "min", "all"], default="mean", help="Estadístico temporal.")
    p_chirts.add_argument("--dem", required=True, help="NetCDF con el modelo digital de elevación (DEM).")
    p_chirts.add_argument("--out", default="./salidas", help="Directorio base de salida.")
    p_chirts.add_argument("--yini", type=int, default=1991, help="Año inicial.")
    p_chirts.add_argument("--yend", type=int, default=2020, help="Año final.")
    p_chirts.add_argument("--extent", nargs=4, type=float, metavar=("xmin", "xmax", "ymin", "ymax"), help="Extensión espacial.")
    p_chirts.add_argument("--mode", choices=["annual", "daily", "daily-eval", "period"], default="annual", help="Modo de operación.")
    p_chirts.add_argument("--period-type", choices=["season", "months"], help="Tipo de período para modo period.")
    p_chirts.add_argument("--season", choices=list(SEASONS.keys()), help="Temporada climática.")
    p_chirts.add_argument("--months", help="Lista de meses separados por comas (ej. 5,6,7).")
    p_chirts.add_argument("--all-seasons", action="store_true", help="Procesa todas las temporadas definidas.")
    p_chirts.add_argument("--eval", action="store_true", help="Genera gráficos y tablas de evaluación estadística.")
    p_chirts.add_argument("--date", help="Fecha específica para modo daily (YYYY-MM-DD).")

    # 2. Subparser para CHIRPS
    p_chirps = subparsers.add_parser("chirps", help="Evaluación de precipitación CHIRPS")
    p_chirps.add_argument("--csv", required=True, help="Ruta al CSV CDT con estaciones y observaciones.")
    p_chirps.add_argument("--dir-chirps", required=True, help="Directorio con NetCDF diarios originales.")
    p_chirps.add_argument("--dir-merged", required=True, help="Directorio con NetCDF diarios corregidos.")
    p_chirps.add_argument("--out", default="./salidas", help="Directorio base de salida.")
    p_chirps.add_argument("--yini", type=int, default=1991, help="Año inicial.")
    p_chirps.add_argument("--yend", type=int, default=2020, help="Año final.")
    p_chirps.add_argument("--extent", nargs=4, type=float, metavar=("xmin", "xmax", "ymin", "ymax"), help="Extensión espacial.")
    p_chirps.add_argument("--export-csv", action="store_true", help="Exporta CSV con acumulados observados.")

    args = parser.parse_args(argv)

    if not args.product:
        parser.print_help()
        return 1

    if args.product == "chirps":
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
    else:
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

    def console_progress(pct: float, msg: str):
        print(f"[{pct*100:5.1f}%] {msg}")

    runner = AnalysisRunner()
    result = runner.run(req, progress_callback=console_progress)

    if result.success:
        print("\n✅ Proceso completado exitosamente.")
        print(f"📁 Directorio de salida: {result.output_dir}")
        print(f"🗺️ Mapas generados: {len(result.generated_maps)}")
        print(f"📊 Gráficos generados: {len(result.generated_plots)}")
        print(f"📄 CSVs generados: {len(result.generated_csvs)}")
        return 0
    else:
        print(f"\n❌ ERROR: {result.error_message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(parse_args_and_run())
