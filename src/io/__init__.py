"""
Data Input/Output layer for CDT CSV and NetCDF files.
"""

from .cdt_parser import parse_cdt_csv
from .netcdf_loader import (
    rename_coords_latlon,
    load_daily_chirts_raw,
    load_daily_chirts_corr,
    load_dem_dataset,
    find_matching_netcdf_files,
)
from .exporters import (
    export_cmp_csv,
    build_global_station_csv,
    build_station_improvement_csv,
)

__all__ = [
    "parse_cdt_csv",
    "rename_coords_latlon",
    "load_daily_chirts_raw",
    "load_daily_chirts_corr",
    "load_dem_dataset",
    "find_matching_netcdf_files",
    "export_cmp_csv",
    "build_global_station_csv",
    "build_station_improvement_csv",
]
