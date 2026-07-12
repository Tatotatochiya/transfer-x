import logging
from contextlib import asynccontextmanager

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


async def _loan_expiry_job() -> None:
    """M9: notify clubs when a completed loan's loan_end date has passed."""
    from app.deals.service import check_loan_expirations

    async with AsyncSessionLocal() as db:
        try:
            async with db.begin():
                count = await check_loan_expirations(db)
            if count:
                logger.info("Notified %d expired loan(s)", count)
        except Exception:
            logger.exception("Error in loan expiry job")


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
    # Startup
    _scheduler.add_job(_close_expired_sales_job, "interval", minutes=1, id="close_expired_sales")
    _scheduler.add_job(_expire_stale_offers_job, "interval", minutes=5, id="expire_stale_offers")
    _scheduler.add_job(_notify_upcoming_events_job, "interval", hours=1, id="notify_upcoming_events")
    _scheduler.add_job(_enrichment_sync_job, "interval", hours=24, id="enrichment_sync")
    # Registered after enrichment_sync so the daily recompute runs on fresher stats.
    _scheduler.add_job(_valuation_compute_job, "interval", hours=24, id="valuation_compute")
    _scheduler.add_job(_client_alerts_job, "interval", hours=6, id="client_alerts")
    _scheduler.add_job(_approval_expiry_job, "interval", hours=24, id="approval_expiry")
    _scheduler.add_job(_expire_mandates_job, "interval", hours=24, id="expire_mandates")
    _scheduler.add_job(_deal_sla_job, "interval", hours=24, id="deal_sla")
    _scheduler.add_job(_loan_expiry_job, "interval", hours=24, id="loan_expiry")
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
