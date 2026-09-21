"""
Scientific Core module: metrics, spatial processing, and climatology algorithms.
"""

from .metrics import (
    compute_metrics,
    summarize_daily_global,
    summarize_daily_by_station,
    compute_annual_metrics_from_csv,
    compute_station_metrics_from_csv,
    compute_station_metrics_global,
)
from .spatial import (
    load_annual_temp_stat,
    annual_station_stat,
    load_daily_sum_for_year,
    annual_station_accum,
    extract_nearest_station_values,
    calculate_hillshade,
)
from .climatology import (
    get_dates_for_period,
    make_period_title,
    load_period_stat_raw,
    load_period_stat_corr,
    period_station_stat,
    compute_climatology_doy_by_station,
)

__all__ = [
    "compute_metrics",
    "summarize_daily_global",
    "summarize_daily_by_station",
    "compute_annual_metrics_from_csv",
    "compute_station_metrics_from_csv",
    "compute_station_metrics_global",
    "load_annual_temp_stat",
    "annual_station_stat",
    "load_daily_sum_for_year",
    "annual_station_accum",
    "extract_nearest_station_values",
    "calculate_hillshade",
    "get_dates_for_period",
    "make_period_title",
    "load_period_stat_raw",
    "load_period_stat_corr",
    "period_station_stat",
    "compute_climatology_doy_by_station",
]
