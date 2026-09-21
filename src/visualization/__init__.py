"""
Visualization layer for Cartopy maps and statistical plots.
"""

from .maps import (
    plot_side_by_side,
    plot_delta_grid_field,
    plot_delta_grid_at_stations,
    plot_residual_corr_at_stations_with_dem,
    plot_improvement_at_stations_with_dem,
)
from .plots import (
    plot_rmse_bars,
    plot_boxplot_errors,
    plot_boxplot_errors_single,
    plot_boxplot_rmse_by_station,
    plot_boxplot_improvement_pct_by_station,
    plot_scatter_obs_vs_grid,
    plot_scatter_obs_vs_grid_single,
    plot_scatter_rmse_raw_vs_corr,
    plot_scatter_rmse_vs_improvement,
    plot_climatology_doy_station,
    plot_climatology_doy_station_tripanel,
)

__all__ = [
    "plot_side_by_side",
    "plot_delta_grid_field",
    "plot_delta_grid_at_stations",
    "plot_residual_corr_at_stations_with_dem",
    "plot_improvement_at_stations_with_dem",
    "plot_rmse_bars",
    "plot_boxplot_errors",
    "plot_boxplot_errors_single",
    "plot_boxplot_rmse_by_station",
    "plot_boxplot_improvement_pct_by_station",
    "plot_scatter_obs_vs_grid",
    "plot_scatter_obs_vs_grid_single",
    "plot_scatter_rmse_raw_vs_corr",
    "plot_scatter_rmse_vs_improvement",
    "plot_climatology_doy_station",
    "plot_climatology_doy_station_tripanel",
]
