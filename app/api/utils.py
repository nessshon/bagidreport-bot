import asyncio
import logging
import typing as t

logger = logging.getLogger(__name__)


async def api_retry(
    coro_factory: t.Callable[[], t.Awaitable[t.Any]],
    max_attempts: int = 3,
    backoff: float = 1.0,
) -> t.Any:
    last_err: t.Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except Exception as e:
            last_err = e
            logger.warning(
                "API attempt %d/%d failed: %s",
                attempt,
                max_attempts,
                e,
            )
            if attempt < max_attempts:
                await asyncio.sleep(backoff * attempt)
    assert last_err is not None
    raise last_err
