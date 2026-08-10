"""
Unit tests for backend/app/jobs/scheduler.py

Tests verify:
- build_scheduler() constructs without error
- Exactly 5 jobs are registered
- All job IDs are unique
- Each expected job ID is registered
- Scheduler does not start automatically on import
- start_scheduler/stop_scheduler lifecycle works (via FastAPI lifespan mock)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.jobs.scheduler import build_scheduler, start_scheduler, stop_scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_admin():
    return MagicMock()


# ---------------------------------------------------------------------------
# T1 — scheduler builds without error
# ---------------------------------------------------------------------------

def test_scheduler_builds_without_error():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    assert scheduler is not None


# ---------------------------------------------------------------------------
# T2 — scheduler has exactly 5 jobs registered
# ---------------------------------------------------------------------------

def test_scheduler_has_five_jobs_registered():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 5


# ---------------------------------------------------------------------------
# T3 — all job IDs are unique
# ---------------------------------------------------------------------------

def test_all_job_ids_are_unique():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert len(job_ids) == len(set(job_ids))


# ---------------------------------------------------------------------------
# T4 — morning briefing job is registered
# ---------------------------------------------------------------------------

def test_morning_briefing_job_is_registered():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "morning_briefing" in job_ids


# ---------------------------------------------------------------------------
# T5 — evening briefing job is registered
# ---------------------------------------------------------------------------

def test_evening_briefing_job_is_registered():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "evening_briefing" in job_ids


# ---------------------------------------------------------------------------
# T6 — important dates job is registered
# ---------------------------------------------------------------------------

def test_important_dates_job_is_registered():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "important_dates" in job_ids


# ---------------------------------------------------------------------------
# T7 — conflict alerts job is registered
# ---------------------------------------------------------------------------

def test_conflict_alerts_job_is_registered():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "conflict_alerts" in job_ids


# ---------------------------------------------------------------------------
# T8 — free evening job is registered
# ---------------------------------------------------------------------------

def test_free_evening_job_is_registered():
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "free_evening" in job_ids


# ---------------------------------------------------------------------------
# T9 — scheduler does not start automatically on import
# ---------------------------------------------------------------------------

def test_scheduler_does_not_start_automatically_on_import():
    """
    Importing build_scheduler must not start any scheduler.
    build_scheduler() returns a not-yet-started scheduler.
    """
    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)
    assert not scheduler.running


# ---------------------------------------------------------------------------
# T10 — lifespan starts and stops scheduler
# ---------------------------------------------------------------------------

def test_lifespan_starts_and_stops_scheduler():
    """
    Verify start_scheduler() starts the scheduler and
    stop_scheduler() stops it cleanly.

    APScheduler's AsyncIOScheduler needs an event loop to start/stop.
    We use asyncio.run() to provide one.
    """
    import asyncio

    db_admin = _make_db_admin()
    scheduler = build_scheduler(db_admin=db_admin)

    # Before start
    assert not scheduler.running

    async def _lifecycle():
        start_scheduler(scheduler)
        assert scheduler.running
        stop_scheduler(scheduler)
        # AsyncIOScheduler completes shutdown on next event loop tick
        await asyncio.sleep(0)
        assert not scheduler.running

    asyncio.run(_lifecycle())
