"""Worker entrypoint — APScheduler + Postgres advisory locks (§3.1, §9.1).

Real ingestion jobs (GFS, ECMWF, GDACS, clustering, alert generation,
retention) are added phase by phase; this scaffold just proves the worker
container boots, can reach Postgres, and runs a scheduled loop.
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
log = logging.getLogger("worker")


async def heartbeat() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("heartbeat ok")


async def main() -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(heartbeat, "interval", seconds=60, id="heartbeat", next_run_time=None)
    scheduler.start()
    log.info("worker started")
    await heartbeat()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
