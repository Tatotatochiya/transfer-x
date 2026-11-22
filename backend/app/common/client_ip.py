"""The address of the person making a request, behind a proxy or not.

Each proxy appends the address it received the request from to
X-Forwarded-For, so only the last `trusted_proxy_hops` entries were written
by proxies we trust. The entry just inside them is the client; anything to
its left came from the client itself and is not believed.
"""

from fastapi import Request

from app.config import settings


def client_ip(request: Request, hops: int | None = None) -> str | None:
    hops = settings.trusted_proxy_hops if hops is None else hops
    if hops > 0:
        entries = [e.strip() for e in ",".join(request.headers.getlist("x-forwarded-for")).split(",") if e.strip()]
        if entries:
            return entries[-hops] if len(entries) >= hops else entries[0]
    return request.client.host if request.client else None
