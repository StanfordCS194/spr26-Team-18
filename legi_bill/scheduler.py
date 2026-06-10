"""
APScheduler integration — runs the nightly bill pipeline inside the FastAPI process.

The scheduler fires at 02:00 UTC daily. The FastAPI lifespan in api.py starts and
stops it so no orphaned threads are left when the server exits.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_job() -> None:
    from .config import load_config
    from .storage import init_db
    from .pipeline import run_nightly_pipeline

    log.info("Nightly pipeline starting (scheduled)…")
    try:
        cfg = load_config()
        conn = init_db(cfg["db_path"])
        stats = run_nightly_pipeline(cfg, conn)
        log.info("Nightly pipeline finished: %s", stats)
    except Exception:
        log.exception("Nightly pipeline raised an unhandled exception")


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_job,
        trigger=CronTrigger(hour=2, minute=0),
        id="nightly_bill_pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    log.info("APScheduler started — nightly pipeline fires at 02:00 UTC.")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("APScheduler stopped.")
    _scheduler = None


def trigger_now() -> None:
    """Fire the pipeline immediately (used by the manual API endpoint)."""
    if _scheduler and _scheduler.running:
        _scheduler.add_job(
            _run_job,
            id="manual_pipeline_run",
            replace_existing=True,
        )
    else:
        _run_job()
