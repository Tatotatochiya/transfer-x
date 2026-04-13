"""Async HTTP client for API-Football (api-sports.io v3)."""
import asyncio
import httpx

VENDOR = "api_sports_v3"


class ApiFootballError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class ApiFootballClient:
    def __init__(self, api_key: str, base_url: str = "https://v3.football.api-sports.io"):
        self.base_url = base_url.rstrip("/")
        self._headers = {"x-apisports-key": api_key}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """GET with exponential-backoff retry on 429 and 5xx."""
        delays = [1.0, 2.0, 4.0]
        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(len(delays) + 1):
                resp = await client.get(
                    f"{self.base_url}{path}",
                    headers=self._headers,
                    params=params or {},
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_exc = ApiFootballError(resp.text, resp.status_code)
                    if attempt < len(delays):
                        await asyncio.sleep(delays[attempt])
                        continue
                raise ApiFootballError(resp.text, resp.status_code)
        raise last_exc or ApiFootballError("Max retries exceeded")

    async def get_player_stats(self, player_id: int, season: int, league_id: int) -> dict:
        return await self._get("/players", {"id": player_id, "season": season, "league": league_id})

    async def get_league_teams(self, league_id: int, season: int) -> dict:
        return await self._get("/teams", {"league": league_id, "season": season})

    async def get_league_players(self, league_id: int, season: int, page: int = 1) -> dict:
        return await self._get("/players", {"league": league_id, "season": season, "page": page})

    async def get_team_players(self, team_id: int, season: int, page: int = 1) -> dict:
        return await self._get("/players", {"team": team_id, "season": season, "page": page})

    async def get_player_transfers(self, vendor_player_id: int) -> dict:
        return await self._get("/transfers", {"player": vendor_player_id})

    async def get_player_sidelined(self, vendor_player_id: int) -> dict:
        return await self._get("/sidelined", {"player": vendor_player_id})
