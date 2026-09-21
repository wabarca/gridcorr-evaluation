# -*- coding: utf-8 -*-
"""
Application settings and environment configuration.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppSettings:
    """Central configuration for application runtime."""
    default_output_dir: str = os.getenv("CHIRPTS_OUT_DIR", "./salidas")
    max_workers: int = int(os.getenv("CHIRPTS_MAX_WORKERS", "4"))
    dpi_maps: int = int(os.getenv("CHIRPTS_DPI_MAPS", "200"))
    dpi_plots: int = int(os.getenv("CHIRPTS_DPI_PLOTS", "160"))
    enable_cache: bool = True
    temp_dir: Optional[str] = None


settings = AppSettings()
