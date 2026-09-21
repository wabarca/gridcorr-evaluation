# -*- coding: utf-8 -*-
"""
Tests for background TaskManager and TaskState execution.
"""

import pytest
from src.application.models import (
    AnalysisRequest,
    ProductType,
    ProcessingMode,
    StatType,
)
from src.application.task_manager import TaskManager, TaskStatus, TaskState


def test_task_state_progression():
    req = AnalysisRequest(
        product=ProductType.CHIRPS,
        var="precip",
        mode=ProcessingMode.ANNUAL,
        stat=StatType.ACCUM,
        csv_path="dummy.csv",
        dir_original="dummy_raw",
        dir_merged="dummy_corr",
        out_dir="dummy_out",
        yini=1991,
        yend=1991,
    )
    state = TaskState("test-123", req)
    assert state.status == TaskStatus.RUNNING
    assert state.progress == 0.0
    assert len(state.logs) >= 1

    state.update_progress(0.45, "Procesando año 1991...")
    assert state.progress == 0.45
    assert state.current_message == "Procesando año 1991..."
    assert any("Procesando año 1991" in log for log in state.logs)

    snap = state.get_snapshot()
    assert snap["task_id"] == "test-123"
    assert snap["progress"] == 0.45

    state.request_cancel()
    assert state.is_cancel_requested() is True


def test_task_manager_singleton():
    tm1 = TaskManager()
    tm2 = TaskManager()
    assert tm1 is tm2
