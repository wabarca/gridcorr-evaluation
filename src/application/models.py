# -*- coding: utf-8 -*-
"""
Application layer data structures, enums, and request/result models.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import pandas as pd


class ProductType(str, Enum):
    """Tipo de producto climático a evaluar."""
    CHIRPS = "chirps"  # Precipitación
    CHIRTS = "chirts"  # Temperatura


class ProcessingMode(str, Enum):
    """Modo de procesamiento del análisis."""
    ANNUAL = "annual"          # Mapas por año con estadísticos
    DAILY = "daily"            # Evaluación para una fecha puntual
    DAILY_EVAL = "daily-eval"  # Evaluación diaria completa multianual
    PERIOD = "period"          # Temporadas o meses específicos


class StatType(str, Enum):
    """Estadístico de agregación temporal."""
    MEAN = "mean"
    MAX = "max"
    MIN = "min"
    ALL = "all"
    ACCUM = "accum"


class PeriodType(str, Enum):
    """Tipo de período en modo period."""
    SEASON = "season"
    MONTHS = "months"


@dataclass
class ValidationResult:
    """Resultado de la validación previa de una solicitud de análisis."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.is_valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


@dataclass
class AnalysisRequest:
    """
    Especificación completa y tipada de una solicitud de análisis.
    """
    product: ProductType = ProductType.CHIRTS
    csv_path: str = ""
    dir_original: str = ""
    dir_merged: str = ""
    out_dir: str = "./salidas"

    # CHIRTS específicos
    var: str = "tmax"  # 'tmax' o 'tmin'
    stat: StatType = StatType.MEAN
    dem_path: Optional[str] = None
    prefix_original: str = "temp_"

    # Modos y filtros temporales
    mode: ProcessingMode = ProcessingMode.ANNUAL
    yini: Optional[int] = 1991
    yend: Optional[int] = 2020
    date_str: Optional[str] = None  # Para modo daily ('YYYY-MM-DD')

    # Modo period
    period_type: Optional[PeriodType] = None
    season: Optional[str] = None
    all_seasons: bool = False
    months: Optional[List[int]] = None  # Ej. [5, 6, 7]

    # Opciones de evaluación y visualización
    eval_stats: bool = True
    export_csv: bool = True
    extent: Optional[Tuple[float, float, float, float]] = None  # (xmin, xmax, ymin, ymax)
    
    # Nuevas opciones avanzadas
    selected_metrics: List[str] = field(default_factory=lambda: ["bias", "mae", "rmse", "r", "pbias", "kge", "nse", "d1"])
    rain_threshold: float = 1.0  # Umbral para métricas categóricas en mm
    color_theme: str = "pastel"   # 'pastel', 'scientific', 'classic'
    show_labels: Optional[bool] = None  # None = Auto, True = Siempre, False = Nunca
    label_mode: str = "auto"  # 'auto', 'always', 'never'


@dataclass
class AnalysisResult:
    """
    Resultado estructurado tras la ejecución del análisis.
    """
    success: bool = True
    error_message: Optional[str] = None
    execution_logs: List[str] = field(default_factory=list)
    output_dir: str = ""

    # Archivos generados categorizados
    generated_maps: List[str] = field(default_factory=list)
    generated_plots: List[str] = field(default_factory=list)
    generated_csvs: List[str] = field(default_factory=list)

    # Resultados tabulares cargados en memoria para visualización inmediata en GUI
    metrics_df: Optional[pd.DataFrame] = None
    summary_global_df: Optional[pd.DataFrame] = None
    summary_station_df: Optional[pd.DataFrame] = None
    rankings_df: Optional[pd.DataFrame] = None
    contingency_df: Optional[pd.DataFrame] = None
    doy_stations: List[str] = field(default_factory=list)
    doy_plots_by_station: Dict[str, Dict[str, str]] = field(default_factory=dict)
    request: Optional[AnalysisRequest] = None
    is_completed: bool = True
    completion_metadata: Dict[str, Any] = field(default_factory=dict)
