"""Dispatch backtest runs synchronously or in a background thread."""

from __future__ import annotations

import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


def dispatch_run(run_id: int) -> None:
    from apps.backtests.tasks import execute_run

    if getattr(settings, "BACKTEST_RUN_ASYNC", True):
        def _worker() -> None:
            try:
                execute_run(run_id)
            except Exception:
                logger.exception("Backtest run %s failed", run_id)

        threading.Thread(
            target=_worker,
            daemon=True,
            name=f"backtest-{run_id}",
        ).start()
        return
    execute_run(run_id)
