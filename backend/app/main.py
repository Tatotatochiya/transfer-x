import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin import router as admin_router
from app.ai import router as ai_router
from app.analytics import router as analytics_router
from app.ws import router as ws_router
from app.auth import router as auth_router
from app.clubs import router as clubs_router
from app.config import settings
from app.database import AsyncSessionLocal
from app.deals import router as deals_router
from app.deals import room_router as deal_room_router
from app.loans import router as loans_router
from app.notifications import router as notifications_router
from app.offers import router as offers_router
from app.players import router as players_router
from app.routers import health, search as search_router
from app.sales import router as sales_router
from app.scouting import router as scouting_router
from app.stats import router as stats_router
from app.vendor import router as vendor_router
from app.world import router as world_router
from app.fixtures import router as fixtures_router
from app.transfer_window import router as transfer_window_router
from app.mandates import router as mandates_router
from app.agents import router as agents_router
from app.agents import negotiation_messages_router
from app.audit import router as audit_router
from app.verification import router as verification_router
from app.valuation import router as valuation_router
from app.approvals import router as approvals_router
from app.dashboard import router as dashboard_router

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


async def _close_expired_sales_job() -> None:
    from app.sales.service import close_expired_sales

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await close_expired_sales(db)
            if count:
                logger.info("Expired %d sales", count)
        except Exception:
            logger.exception("Error in close_expired_sales job")


async def _expire_stale_offers_job() -> None:
    from app.offers.service import expire_stale_offers

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await expire_stale_offers(db)
            if count:
                logger.info("Expired %d offers", count)
        except Exception:
            logger.exception("Error in expire_stale_offers job")


async def _notify_upcoming_events_job() -> None:
    from app.notifications.service import notify_upcoming_events

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                await notify_upcoming_events(db)
        except Exception:
            logger.exception("Error in notify_upcoming_events job")


async def _enrichment_sync_job() -> None:
    """TRA-67: daily sync of player valuations and wage data from external providers."""
    from app.enrichment.sync import sync_all_players

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                await sync_all_players(db)
        except Exception:
            logger.exception("Error in enrichment sync job")


async def _loan_lifecycle_job() -> None:
    """Return loans that have reached their end date, and warn on those about
    to. Without this a loan has no way to end on its own — which is why the
    loan UI was held back until this shipped."""
    from app.loans import service as loans_service

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                result = await loans_service.process_due_loans(db)
            if result["returned"] or result["ending_soon_warned"]:
                logger.info(
                    "Loan lifecycle: %s returned, %s warned",
                    result["returned"], result["ending_soon_warned"],
                )
        except Exception:
            logger.exception("Error in loan lifecycle job")


async def _valuation_compute_job() -> None:
    """TRA-91: daily recompute of every player's fair-value model valuation."""
    from app.valuation.service import compute_all_valuations

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                counts = await compute_all_valuations(db)
            logger.info(
                "Valuation compute complete: %d updated, %d skipped (ineligible), %d errors",
                counts["updated"], counts["skipped_ineligible"], counts["errors"],
            )
        except Exception:
            logger.exception("Error in valuation compute job")


async def _approval_expiry_job() -> None:
    """Phase 5 (club-team-roles): expire stale pending approvals and notify requesters."""
    from app.approvals.service import expire_stale_approvals

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await expire_stale_approvals(db)
            if count:
                logger.info("Expired %d stale approvals", count)
        except Exception:
            logger.exception("Error in approval expiry job")


async def _expire_mandates_job() -> None:
    """Expire mandates past their end_date (item 11 gap fix)."""
    from app.mandates.service import expire_mandates

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await expire_mandates(db)
            if count:
                logger.info("Expired %d mandates", count)
        except Exception:
            logger.exception("Error in expire_mandates job")


async def _deal_sla_job() -> None:
    """Flag deals stuck PENDING_COMPLETION past their SLA deadline (item 5 gap fix)."""
    from app.deals.service import check_deal_sla_breaches

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await check_deal_sla_breaches(db)
            if count:
                logger.info("Flagged %d deal(s) as SLA-breached", count)
        except Exception:
            logger.exception("Error in deal SLA job")


async def _client_alerts_job() -> None:
    """TRA-134: scan agent rosters for contract-expiry, valuation-change, and club-interest alerts."""
    from app.mandates.alerts_service import check_and_create_alerts

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await check_and_create_alerts(db)
            if count:
                logger.info("Created %d client alerts", count)
        except Exception:
            logger.exception("Error in client alerts job")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup. Each interval job gets an explicit next_run_time so the first
    # execution fires promptly after startup rather than at now + interval.
    # Without this a 24h job never runs unless the process survives 24 unbroken
    # hours, which effectively means never in development (constant restarts)
    # and unreliably in production (any deploy or crash resets the clock).
    _scheduler.add_job(
        _close_expired_sales_job, "interval", minutes=1, id="close_expired_sales",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=3),
    )
    _scheduler.add_job(
        _expire_stale_offers_job, "interval", minutes=5, id="expire_stale_offers",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=3),
    )
    _scheduler.add_job(
        _notify_upcoming_events_job, "interval", hours=1, id="notify_upcoming_events",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    _scheduler.add_job(
        _enrichment_sync_job, "interval", hours=24, id="enrichment_sync",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    # Registered after enrichment_sync so the daily recompute runs on fresher stats.
    _scheduler.add_job(
        _valuation_compute_job, "interval", hours=24, id="valuation_compute",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=15),
    )
    _scheduler.add_job(
        _client_alerts_job, "interval", hours=6, id="client_alerts",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    _scheduler.add_job(
        _approval_expiry_job, "interval", hours=24, id="approval_expiry",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    _scheduler.add_job(
        _expire_mandates_job, "interval", hours=24, id="expire_mandates",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    _scheduler.add_job(
        _deal_sla_job, "interval", hours=24, id="deal_sla",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    _scheduler.add_job(
        _loan_lifecycle_job, "interval", hours=24, id="loan_lifecycle",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    _scheduler.start()
    logger.info("APScheduler started")
    yield
    # Shutdown
    _scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


app = FastAPI(
    title="TransferX API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────────────


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Not found"})


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(search_router.router)
app.include_router(auth_router.router, prefix="/auth")
app.include_router(clubs_router.router, prefix="/clubs")
app.include_router(players_router.router, prefix="/players")
app.include_router(sales_router.router, prefix="")
app.include_router(offers_router.router, prefix="")
app.include_router(deals_router.router, prefix="")
app.include_router(deal_room_router.router, prefix="")
app.include_router(loans_router.router, prefix="")
app.include_router(scouting_router.router)
app.include_router(notifications_router.router)
app.include_router(stats_router.router)
app.include_router(vendor_router.router)
app.include_router(world_router.router)
app.include_router(admin_router.router)
app.include_router(analytics_router.router)
app.include_router(fixtures_router.router)
app.include_router(transfer_window_router.router)
app.include_router(ws_router.router)
app.include_router(ai_router)
app.include_router(mandates_router.router, prefix="/mandates")
app.include_router(agents_router.router, prefix="/agents")
app.include_router(negotiation_messages_router.router, prefix="")
app.include_router(audit_router.router, prefix="")
app.include_router(verification_router.router, prefix="")
app.include_router(valuation_router.router, prefix="/valuation")
app.include_router(approvals_router.router, prefix="")
app.include_router(dashboard_router.router, prefix="")
