from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


@dataclass(slots=True)
class TaskResult:
    """Outcome shared by all background tasks crossing into the UI thread."""

    value: object = None
    error: str = ""
    succeeded: bool | None = None

    @property
    def ok(self) -> bool:
        if self.succeeded is not None:
            return self.succeeded
        return not self.error


class _TaskSignals(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)


class BackgroundTask(QRunnable):
    """Run a callable without leaking worker exceptions into Qt's thread pool."""

    def __init__(self, work: Callable[[Callable[[int], None]], object]) -> None:
        super().__init__()
        self.work = work
        self.signals = _TaskSignals()

    def run(self) -> None:
        try:
            result = self.work(self.signals.progress.emit)
            outcome = TaskResult(value=result)
        except Exception as exc:
            outcome = TaskResult(error=str(exc), succeeded=False)
        self.signals.finished.emit(outcome)


class BackgroundTaskRunner:
    """Small submission boundary that keeps task wiring consistent in the UI."""

    def __init__(self, pool: QThreadPool | None = None) -> None:
        self.pool = pool if pool is not None else QThreadPool.globalInstance()

    def start(
        self,
        work: Callable[[Callable[[int], None]], object],
        finished: Callable[[TaskResult], None],
        progress: Callable[[int], None] | None = None,
    ) -> BackgroundTask:
        task = BackgroundTask(work)
        task.signals.finished.connect(finished)
        if progress is not None:
            task.signals.progress.connect(progress)
        self.pool.start(task)
        return task
