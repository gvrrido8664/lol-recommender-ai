import asyncio
import time
import httpx
from backend.config import API_KEY

_limiter_lock = asyncio.Lock()
_short_window: list[float] = []
_long_window: list[float] = []
SHORT_MAX = 18
LONG_MAX = 90
SHORT_PERIOD = 1.1
LONG_PERIOD = 121.0
_cooldown_until = 0.0

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
    return _client


async def _wait_for_slot():
    global _cooldown_until
    now = time.monotonic()
    if now < _cooldown_until:
        await asyncio.sleep(_cooldown_until - now)
        now = time.monotonic()

    async with _limiter_lock:
        _short_window[:] = [t for t in _short_window if now - t < SHORT_PERIOD]
        _long_window[:] = [t for t in _long_window if now - t < LONG_PERIOD]

        short_wait = 0.0
        long_wait = 0.0
        if len(_short_window) >= SHORT_MAX:
            short_wait = _short_window[0] + SHORT_PERIOD - now + 0.05
        if len(_long_window) >= LONG_MAX:
            long_wait = _long_window[0] + LONG_PERIOD - now + 0.05

        wait = max(short_wait, long_wait, _cooldown_until - now, 0)
        if wait > 0:
            await asyncio.sleep(wait)
            now = time.monotonic()
            _short_window[:] = [t for t in _short_window if now - t < SHORT_PERIOD]
            _long_window[:] = [t for t in _long_window if now - t < LONG_PERIOD]

        _short_window.append(now)
        _long_window.append(now)


async def riot_get(url: str, cache: dict | None = None, cache_ttl: int = 300) -> dict | None:
    global _cooldown_until
    if not API_KEY:
        return None

    cache_key = url if cache is not None else None
    if cache_key and cache_key in cache:
        entry = cache[cache_key]
        if time.time() - entry["ts"] < cache_ttl:
            return entry["data"]

    await _wait_for_slot()
    client = await _get_client()

    try:
        resp = await client.get(url, headers={"X-Riot-Token": API_KEY})
        if resp.status_code == 200:
            data = resp.json()
            if cache_key and cache is not None:
                cache[cache_key] = {"data": data, "ts": time.time()}
            return data
        elif resp.status_code == 429:
            retry_after = _parse_retry_after(resp)
            _cooldown_until = time.monotonic() + retry_after
        elif resp.status_code in (401, 403):
            _cooldown_until = time.monotonic() + 600
    except Exception:
        pass
    return None


def _parse_retry_after(resp) -> float:
    try:
        return float(resp.headers.get("Retry-After", "10"))
    except (TypeError, ValueError):
        return 10.0


def reset_limiter():
    """Reinicia el rate limiter (para tests)."""
    global _short_window, _long_window, _cooldown_until
    _short_window.clear()
    _long_window.clear()
    _cooldown_until = 0.0
