"""HTTP retry with exponential backoff for BMS connectors."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

import httpx

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Any],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    retry_on: tuple = (408, 429, 500, 502, 503, 504),
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in retry_on or attempt == max_attempts - 1:
                raise
            last_exc = exc
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt == max_attempts - 1:
                raise
            last_exc = exc
        await asyncio.sleep(base_delay * (2**attempt))
    if last_exc:
        raise last_exc
    raise RuntimeError("retry exhausted")
