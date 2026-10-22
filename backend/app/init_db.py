import asyncio
import logging
import time

from . import storage
from .db import Base, engine

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("init_db")


async def init_tables():
    for attempt in range(30):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            log.info("tables ready")
            return
        except Exception as exc:
            log.warning("db not ready (%s), retry %s", exc, attempt + 1)
            await asyncio.sleep(2)
    raise SystemExit("database is unavailable")


def init_bucket():
    for attempt in range(30):
        try:
            storage.ensure_bucket()
            log.info("bucket ready")
            return
        except Exception as exc:
            log.warning("minio not ready (%s), retry %s", exc, attempt + 1)
            time.sleep(2)
    raise SystemExit("minio is unavailable")


if __name__ == "__main__":
    asyncio.run(init_tables())
    init_bucket()
