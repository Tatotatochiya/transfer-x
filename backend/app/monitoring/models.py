"""Job runs, their logs, grouped errors and per-minute request figures
(docs/feature_spec/scheduled-data-refresh.md, migration 0100). Platform
admins only; each table has a retention period (monitoring/retention.py)."""
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.database import Base


class JobRun(Base):
    """One run of a job: a worker refresh (and each of its steps), a manual
    run, or an in-app scheduler job."""
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)  # cron | manual | scheduler
    service: Mapped[str] = mapped_column(String(20), nullable=False)  # api | worker
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class JobRunLog(Base):
    """A log line written during a run (INFO and above, at most 5,000 a run)."""
    __tablename__ = "job_run_logs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    logger: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)


class ErrorIssue(Base):
    """Warnings and errors grouped by fingerprint."""
    __tablename__ = "error_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    service: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # api | worker | web
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    logger: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open", index=True)  # open | resolved | ignored
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hourly: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # "2026-10-10T14" → count, last 24 hours


class ErrorEvent(Base):
    """One occurrence of an issue (the newest 20 are kept per issue)."""
    __tablename__ = "error_events"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("error_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class RequestMinute(Base):
    """Requests to one endpoint in one minute, from one web process."""
    __tablename__ = "request_minutes"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    minute: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    route: Mapped[str] = mapped_column(String(200), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    errors: Mapped[int] = mapped_column(Integer, nullable=False)  # 5xx
    p50_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    p95_ms: Mapped[int] = mapped_column(Integer, nullable=False)
