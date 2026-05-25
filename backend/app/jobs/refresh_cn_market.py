from __future__ import annotations

import asyncio
import logging

from app.cache.sqlite import SQLiteCache
from app.clients.seesea import SeeSeaClient
from app.config import settings
from app.scheduler import _refresh_cn_market

logger = logging.getLogger(__name__)


async def refresh_once() -> int:
    cache = SQLiteCache(settings.cache_db_path)
    await cache.init()

    seesea = SeeSeaClient(enable_stock_sdk_fallback=True)
    try:
        response = await _refresh_cn_market(seesea, cache)
        if response is None:
            logger.warning("cn-market-job: refresh produced no cacheable data")
            return 1
        logger.info(
            "cn-market-job: refreshed (%d indices, %d stocks, stale=%s)",
            len(response.indices),
            len(response.stocks),
            response.stale,
        )
        return 0
    finally:
        await seesea.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(asyncio.run(refresh_once()))


if __name__ == "__main__":
    main()
