import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from receptionist.api.rate_limit import RateLimitMiddleware


def _scope(path: str = "/api/v1/ping", api_key: str | None = "k1", host: str = "10.0.0.1"):
    headers = []
    if api_key:
        headers.append((b"x-api-key", api_key.encode()))
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": (host, 12345),
        "server": ("test", 80),
    }


def _build(max_requests=2, window_seconds=60, clock=None, identity_host="10.0.0.1"):
    clock = clock or (lambda: 0.0)
    middleware = RateLimitMiddleware(
        app=object(),
        max_requests=max_requests,
        window_seconds=window_seconds,
        clock=clock,
    )

    async def call_next(request):
        return JSONResponse({"ok": True})

    async def hit(path="/api/v1/ping", api_key="k1", host=identity_host):
        return await middleware.dispatch(Request(_scope(path, api_key, host)), call_next)

    return middleware, hit


@pytest.mark.asyncio
async def test_allows_up_to_the_limit():
    _, hit = _build(max_requests=2)
    assert (await hit()).status_code == 200
    assert (await hit()).status_code == 200


@pytest.mark.asyncio
async def test_over_limit_returns_429_with_retry_after():
    _, hit = _build(max_requests=2)
    await hit()
    await hit()
    response = await hit()
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1
    body = json.loads(bytes(response.body))
    assert body["detail"] == "Rate limit exceeded"
    assert body["retry_after_seconds"] >= 1
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_window_resets_when_it_expires():
    now = [0.0]
    _, hit = _build(max_requests=1, window_seconds=60, clock=lambda: now[0])
    assert (await hit()).status_code == 200
    assert (await hit()).status_code == 429
    now[0] += 61
    assert (await hit()).status_code == 200


@pytest.mark.asyncio
async def test_buckets_are_isolated_per_api_key():
    _, hit = _build(max_requests=1)
    assert (await hit(api_key="tenant_a")).status_code == 200
    assert (await hit(api_key="tenant_a")).status_code == 429
    assert (await hit(api_key="tenant_b")).status_code == 200


@pytest.mark.asyncio
async def test_requests_without_key_share_client_ip_bucket():
    _, hit = _build(max_requests=1)
    assert (await hit(api_key=None, host="10.0.0.9")).status_code == 200
    assert (await hit(api_key=None, host="10.0.0.9")).status_code == 429
    assert (await hit(api_key=None, host="10.0.0.7")).status_code == 200


@pytest.mark.asyncio
async def test_health_and_non_api_paths_are_not_limited():
    _, hit = _build(max_requests=1)
    for _ in range(5):
        assert (await hit(path="/health", api_key=None)).status_code == 200


@pytest.mark.asyncio
async def test_zero_limit_disables_enforcement():
    _, hit = _build(max_requests=0)
    for _ in range(5):
        assert (await hit()).status_code == 200


@pytest.mark.asyncio
async def test_idle_buckets_are_pruned():
    middleware, _ = _build(max_requests=1, window_seconds=60, clock=lambda: 1000.0)
    for i in range(2100):
        middleware.requests[f"ip:10.0.0.{i}"] = [0.0]
    middleware._prune(60)
    assert len(middleware.requests) <= 2048


@pytest.mark.asyncio
async def test_over_limit_is_a_response_not_an_exception():
    """Regression: exhausting the budget must not surface as a 500."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)

    @app.get("/api/v1/ping")
    async def ping():
        return {"ok": True}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-API-Key": "unit-key"}
        first = await client.get("/api/v1/ping", headers=headers)
        second = await client.get("/api/v1/ping", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert second.json()["detail"] == "Rate limit exceeded"
