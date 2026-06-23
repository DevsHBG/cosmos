"""Performance sampler: a background thread that records host/process metrics.

Independent of executions — it builds a time series of CPU/RAM/disk that the
unified query can cross with the activity tables by timestamp ("RAM was high 3-4pm,
what ran then?"). Sampling is best-effort; a failed sample is logged to stderr and
never stops the loop.
"""

from __future__ import annotations

import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

import psutil

from pulsar.logger.config import get_logger_settings
from pulsar.logger.records import PerformanceLog
from pulsar.logger.service import LoggerService

#: Disk whose usage is reported (the volume the process runs on).
_DISK_ANCHOR = Path.cwd().anchor or "/"


class PerformanceSampler:
    """Samples host/process resources on an interval and emits ``PerformanceLog``s."""

    def __init__(self, logger: LoggerService, interval_s: float | None = None) -> None:
        self._log = logger
        self._interval = interval_s or get_logger_settings().sampler_interval_s
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._process = psutil.Process()
        self._prev_io: int | None = None

    def sample_once(self) -> PerformanceLog:
        """Take a single sample, emit it, and return it."""
        io = psutil.disk_io_counters()
        io_total = (io.read_bytes + io.write_bytes) if io is not None else None
        disk_io_mb = (
            (io_total - self._prev_io) / 1e6
            if io_total is not None and self._prev_io is not None
            else 0.0
        )
        self._prev_io = io_total

        record = PerformanceLog(
            ts=datetime.now(UTC),
            source="host",
            cpu_pct=psutil.cpu_percent(interval=None),
            rss_mb=self._process.memory_info().rss / 1e6,
            mem_pct=psutil.virtual_memory().percent,
            disk_pct=psutil.disk_usage(_DISK_ANCHOR).percent,
            disk_io_mb=disk_io_mb,
        )
        self._log.emit(record)
        return record

    def start(self) -> None:
        """Take an immediate sample, then keep sampling on the interval."""
        self._stopping.clear()
        try:
            self.sample_once()  # one sample up front so the series is never empty
        except Exception as exc:  # best-effort: never block startup on a sample
            print(f"[logger] performance sample failed: {exc!r}", file=sys.stderr)
        self._thread = threading.Thread(target=self._run, name="logger-sampler", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stopping.wait(self._interval):
            try:
                self.sample_once()
            except Exception as exc:  # best-effort: keep the loop alive on a bad sample
                print(f"[logger] performance sample failed: {exc!r}", file=sys.stderr)

    def stop(self) -> None:
        """Signal the loop to stop and join the thread."""
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
