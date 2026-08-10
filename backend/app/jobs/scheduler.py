"""
APScheduler setup and FastAPI lifespan integration — Phase 6.

Builds an AsyncIOScheduler with 5 daily cron jobs:
    Morning briefing:     11:00 UTC daily  (07:00 US Eastern)
    Important dates:      12:00 UTC daily  (08:00 US Eastern)
    Conflict alerts:      13:00 UTC daily  (09:00 US Eastern)
    Free evening check:   20:00 UTC daily  (16:00 US Eastern)
    Evening briefing:     22:00 UTC daily  (18:00 US Eastern)

Per-family timezone scheduling is deferred to Phase 9. Job functions accept
timezone_str so Phase 9 requires only scheduler registration changes.

All jobs:
- Fetch fresh family IDs from DB on each execution
- Run independently per family
- Never raise — errors are logged and swallowed

Usage (FastAPI lifespan):
    from app.jobs.scheduler import build_scheduler, start_scheduler, stop_scheduler

    @asynccontextmanager
    async def lifespan(app):
        scheduler = build_scheduler(db_admin=get_supabase_admin())
        start_scheduler(scheduler)
        yield
        stop_scheduler(scheduler)

See plan: plans/phase-6-proactive-intelligence.md § Scheduler Initialization
"""

from __future__ import annotations

import logging
from datetime import timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)
UTC = timezone.utc

# Default timezone for all family members until Phase 9 per-family support
_DEFAULT_TIMEZONE = "America/New_York"


def _get_all_family_ids(db_admin) -> list[str]:
    """
    Fetch all family IDs from the families table synchronously.
    Returns an empty list on error.
    """
    try:
        result = db_admin.table("families").select("id").execute()
        return [row["id"] for row in (result.data or [])]
    except Exception as exc:
        log.error("scheduler: failed to fetch family IDs err=%s", exc)
        return []


async def _run_morning_briefing_all_families(db_admin) -> None:
    """Run morning briefing job for every active family."""
    from app.jobs.morning_briefing import run_morning_briefing
    from app.providers.llm.openrouter import get_llm_provider
    from app.agents.data_fetcher import FamilyDataFetcher
    from app.agents.organizer import OrganizerAgent
    from app.config import get_settings
    from app.db.supabase import get_supabase

    settings = get_settings()
    llm = get_llm_provider()
    model = settings.openrouter_model_organizer or settings.openrouter_model_manager
    db = get_supabase()

    for family_id in _get_all_family_ids(db_admin):
        try:
            fetcher = FamilyDataFetcher(db=db, db_admin=db_admin)
            organizer = OrganizerAgent(data_fetcher=fetcher, llm=llm, model=model)
            await run_morning_briefing(family_id, _DEFAULT_TIMEZONE, db_admin, organizer)
        except Exception as exc:
            log.error("scheduler: morning_briefing failed family=%s err=%s", family_id, exc)


async def _run_important_dates_all_families(db_admin) -> None:
    """Run important dates alert job for every active family."""
    from app.jobs.important_dates import run_important_date_alerts

    for family_id in _get_all_family_ids(db_admin):
        try:
            await run_important_date_alerts(family_id, db_admin)
        except Exception as exc:
            log.error("scheduler: important_dates failed family=%s err=%s", family_id, exc)


async def _run_conflict_alerts_all_families(db_admin) -> None:
    """Run conflict alerts job for every active family."""
    from app.jobs.conflict_alerts import run_conflict_alerts

    for family_id in _get_all_family_ids(db_admin):
        try:
            await run_conflict_alerts(family_id, db_admin)
        except Exception as exc:
            log.error("scheduler: conflict_alerts failed family=%s err=%s", family_id, exc)


async def _run_free_evening_all_families(db_admin) -> None:
    """Run free-evening check for every active family."""
    from app.jobs.free_evening import run_free_evening_check
    from app.providers.llm.openrouter import get_llm_provider
    from app.agents.data_fetcher import FamilyDataFetcher
    from app.agents.chef import ChefAgent
    from app.config import get_settings
    from app.db.supabase import get_supabase

    settings = get_settings()
    llm = get_llm_provider()
    model = settings.openrouter_model_chef or settings.openrouter_model_manager
    db = get_supabase()

    for family_id in _get_all_family_ids(db_admin):
        try:
            fetcher = FamilyDataFetcher(db=db, db_admin=db_admin)
            chef = ChefAgent(data_fetcher=fetcher, llm=llm, model=model)
            await run_free_evening_check(family_id, _DEFAULT_TIMEZONE, db_admin, db, chef)
        except Exception as exc:
            log.error("scheduler: free_evening failed family=%s err=%s", family_id, exc)


async def _run_evening_briefing_all_families(db_admin) -> None:
    """Run evening briefing job for every active family."""
    from app.jobs.evening_briefing import run_evening_briefing
    from app.providers.llm.openrouter import get_llm_provider
    from app.agents.data_fetcher import FamilyDataFetcher
    from app.agents.organizer import OrganizerAgent
    from app.agents.chef import ChefAgent
    from app.config import get_settings
    from app.db.supabase import get_supabase

    settings = get_settings()
    llm = get_llm_provider()
    model_org = settings.openrouter_model_organizer or settings.openrouter_model_manager
    model_chef = settings.openrouter_model_chef or settings.openrouter_model_manager
    db = get_supabase()

    for family_id in _get_all_family_ids(db_admin):
        try:
            fetcher = FamilyDataFetcher(db=db, db_admin=db_admin)
            organizer = OrganizerAgent(data_fetcher=fetcher, llm=llm, model=model_org)
            chef = ChefAgent(data_fetcher=fetcher, llm=llm, model=model_chef)
            await run_evening_briefing(family_id, _DEFAULT_TIMEZONE, db_admin, organizer, chef)
        except Exception as exc:
            log.error("scheduler: evening_briefing failed family=%s err=%s", family_id, exc)


def build_scheduler(db_admin) -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns a configured (not yet started) AsyncIOScheduler.
    All cron times are UTC. Does NOT start the scheduler — call start_scheduler().

    Args:
        db_admin: Service-role Supabase client, passed to all job runners.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Morning briefing — 11:00 UTC daily
    scheduler.add_job(
        _run_morning_briefing_all_families,
        trigger=CronTrigger(hour=11, minute=0, timezone="UTC"),
        id="morning_briefing",
        name="Morning Briefing",
        args=[db_admin],
        replace_existing=True,
        max_instances=1,
    )

    # Important dates — 12:00 UTC daily
    scheduler.add_job(
        _run_important_dates_all_families,
        trigger=CronTrigger(hour=12, minute=0, timezone="UTC"),
        id="important_dates",
        name="Important Dates Alerts",
        args=[db_admin],
        replace_existing=True,
        max_instances=1,
    )

    # Conflict alerts — 13:00 UTC daily
    scheduler.add_job(
        _run_conflict_alerts_all_families,
        trigger=CronTrigger(hour=13, minute=0, timezone="UTC"),
        id="conflict_alerts",
        name="Conflict Alerts",
        args=[db_admin],
        replace_existing=True,
        max_instances=1,
    )

    # Free evening check — 20:00 UTC daily
    scheduler.add_job(
        _run_free_evening_all_families,
        trigger=CronTrigger(hour=20, minute=0, timezone="UTC"),
        id="free_evening",
        name="Free Evening Check",
        args=[db_admin],
        replace_existing=True,
        max_instances=1,
    )

    # Evening briefing — 22:00 UTC daily
    scheduler.add_job(
        _run_evening_briefing_all_families,
        trigger=CronTrigger(hour=22, minute=0, timezone="UTC"),
        id="evening_briefing",
        name="Evening Briefing",
        args=[db_admin],
        replace_existing=True,
        max_instances=1,
    )

    log.info("scheduler: built with 5 jobs registered")
    return scheduler


def start_scheduler(scheduler: AsyncIOScheduler) -> None:
    """
    Start the scheduler.

    Called from FastAPI lifespan startup. Safe to call only once.
    Logs but does not raise if already running.
    """
    if scheduler.running:
        log.warning("scheduler: already running — start_scheduler called twice")
        return
    scheduler.start()
    log.info("scheduler: started — 5 jobs active")


def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    """
    Gracefully shut down the scheduler.

    Called from FastAPI lifespan shutdown. Uses wait=False for
    AsyncIOScheduler (async context — the event loop processes cleanup
    on the next tick). Safe to call if not running.
    """
    if not scheduler.running:
        return
    scheduler.shutdown(wait=False)
    log.info("scheduler: shutdown requested")
