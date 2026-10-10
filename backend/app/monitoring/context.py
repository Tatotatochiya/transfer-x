"""What request an error happened in: method, path (never the query),
request id and user id. The middleware puts a dict in the context var and
the auth dependency adds the user to it."""
import contextvars
import uuid

request_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("request_ctx", default=None)


def set_user(user_id: uuid.UUID) -> None:
    ctx = request_ctx.get()
    if ctx is not None:
        ctx["user_id"] = str(user_id)


def current() -> dict | None:
    ctx = request_ctx.get()
    return dict(ctx) if ctx else None
