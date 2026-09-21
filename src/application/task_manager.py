# -*- coding: utf-8 -*-
"""
Thread-safe background Task Manager and State for decoupled execution in Streamlit.
Allows long-running scientific analyses to execute in a background thread without
blocking Streamlit's event loop or causing WebSocket disconnects.
"""

import threading
import time
import datetime
import uuid
import traceback
from enum import Enum
from typing import Optional, List, Dict, Any

from .models import AnalysisRequest, AnalysisResult
from .services import AnalysisRunner, clear_existing_results


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskState:
    """Thread-safe representation of an active or recent analysis task."""

    def __init__(self, task_id: str, request: AnalysisRequest):
        self.task_id: str = task_id
        self.request: AnalysisRequest = request
        self.status: TaskStatus = TaskStatus.RUNNING
        self.progress: float = 0.0
        self.current_message: str = "Iniciando análisis..."
        self.logs: List[str] = []
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.result: Optional[AnalysisResult] = None
        self.error: Optional[str] = None
        self._cancel_requested: bool = False
        self._lock: threading.Lock = threading.Lock()

        # Registro inicial
        self._add_log_internal("Tarea inicializada en segundo plano.")

    def _add_log_internal(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]

    def update_progress(self, pct: float, msg: str) -> None:
        """Callback thread-safe para actualizar progreso y mensaje."""
        with self._lock:
            if self._cancel_requested:
                return
            self.progress = min(max(pct, 0.0), 1.0)
            self.current_message = msg
            self._add_log_internal(msg)

    def add_log(self, msg: str) -> None:
        """Agrega un mensaje de registro thread-safe."""
        with self._lock:
            self._add_log_internal(msg)

    def request_cancel(self) -> None:
        """Solicita la cancelación de la tarea."""
        with self._lock:
            self._cancel_requested = True
            self.current_message = "Cancelación solicitada por el usuario..."
            self._add_log_internal("🛑 Solicitud de cancelación recibida.")

    def is_cancel_requested(self) -> bool:
        """Comprueba si se solicitó cancelar la tarea."""
        with self._lock:
            return self._cancel_requested

    def complete(self, result: AnalysisResult) -> None:
        """Marca la tarea como completada exitosamente."""
        with self._lock:
            self.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            self.progress = 1.0
            self.end_time = time.time()
            self.result = result
            if not result.success:
                self.error = result.error_message or "Error desconocido durante la ejecución."
                self._add_log_internal(f"❌ Finalizado con error: {self.error}")
            else:
                self._add_log_internal("✅ Tarea completada con éxito.")

    def fail(self, error_msg: str) -> None:
        """Marca la tarea como fallida."""
        with self._lock:
            self.status = TaskStatus.FAILED
            self.end_time = time.time()
            self.error = error_msg
            self._add_log_internal(f"❌ Error crítico: {error_msg}")

    def cancel(self) -> None:
        """Marca la tarea como cancelada."""
        with self._lock:
            self.status = TaskStatus.CANCELLED
            self.end_time = time.time()
            self._add_log_internal("⚠️ Tarea detenida/cancelada.")

    @property
    def elapsed_seconds(self) -> float:
        """Tiempo transcurrido en segundos."""
        if self.end_time is not None:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def get_snapshot(self) -> Dict[str, Any]:
        """Obtiene una instantánea consistente del estado de la tarea."""
        with self._lock:
            return {
                "task_id": self.task_id,
                "status": self.status,
                "progress": self.progress,
                "current_message": self.current_message,
                "logs": list(self.logs),
                "start_time": self.start_time,
                "end_time": self.end_time,
                "elapsed_seconds": self.elapsed_seconds,
                "result": self.result,
                "error": self.error,
                "cancel_requested": self._cancel_requested,
            }


class TaskManager:
    """Gestor singleton para orquestar ejecuciones no bloqueantes en segundo plano."""

    _instance: Optional["TaskManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "TaskManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TaskManager, cls).__new__(cls)
                cls._instance._active_task = None
                cls._instance._manager_lock = threading.Lock()
            return cls._instance

    def get_active_task(self) -> Optional[TaskState]:
        """Retorna la tarea actualmente activa o más reciente."""
        with self._manager_lock:
            return self._active_task

    def start_task(self, req: AnalysisRequest, clear_first: bool = False) -> TaskState:
        """Inicia una nueva tarea de análisis en un hilo independiente en segundo plano."""
        with self._manager_lock:
            if self._active_task is not None and self._active_task.status == TaskStatus.RUNNING:
                return self._active_task

            task_id = str(uuid.uuid4())[:8]
            task_state = TaskState(task_id, req)
            self._active_task = task_state

            worker_thread = threading.Thread(
                target=self._run_worker,
                args=(task_state, req, clear_first),
                name=f"Worker-Analysis-{task_id}",
                daemon=True,
            )
            worker_thread.start()
            return task_state

    def _run_worker(self, task_state: TaskState, req: AnalysisRequest, clear_first: bool) -> None:
        """Función ejecutada por el hilo secundario en background."""
        try:
            if clear_first:
                task_state.update_progress(0.01, f"Limpiando directorio de salida: {req.out_dir}...")
                clear_existing_results(req.out_dir)

            runner = AnalysisRunner()
            result = runner.run(
                req=req,
                progress_callback=task_state.update_progress,
                cancel_check=task_state.is_cancel_requested,
            )

            if task_state.is_cancel_requested():
                task_state.cancel()
            else:
                task_state.complete(result)

        except Exception as e:
            tb = traceback.format_exc()
            task_state.fail(f"{str(e)}\n\n{tb}")

    def cancel_active_task(self) -> None:
        """Solicita cancelar la tarea activa."""
        with self._manager_lock:
            if self._active_task is not None and self._active_task.status == TaskStatus.RUNNING:
                self._active_task.request_cancel()

    def clear_active_task(self, force: bool = False) -> None:
        """Limpia la referencia de la tarea activa una vez procesada."""
        with self._manager_lock:
            if force or (self._active_task is not None and self._active_task.status != TaskStatus.RUNNING):
                self._active_task = None


task_manager = TaskManager()
