"""Job runs, run logs, error tracking and request health
(docs/feature_spec/scheduled-data-refresh.md)."""

# Monitoring writes in its own sessions. Tests point this at their engine's
# sessionmaker, so nothing reaches the real database.
session_factory = None

# Which process is writing: "api" (the web app) or "worker" (stats-worker).
service = "api"


def sessions():
    if session_factory is not None:
        return session_factory
    from app.database import AsyncSessionLocal

    return AsyncSessionLocal
