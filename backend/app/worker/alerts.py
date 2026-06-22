"""Alert-delivery worker entrypoint.

Run daily on a schedule (EventBridge → ECS RunTask in prod; see
`infra/stacks/backend_stack.py`). Loads every user's data, sends due
renewal/trial/missed-payment emails, and records what was sent so nothing is
sent twice. Detection + delivery logic lives in `services/notifications.py`;
this module is just the runnable shell.

    python -m app.worker.alerts
"""

import asyncio
import logging

from app.core.db import SessionLocal
from app.services.notifications import run_all_alerts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.worker.alerts")


async def main() -> None:
    async with SessionLocal() as db:
        total = await run_all_alerts(db)
    logger.info("Alert run complete; %d notification(s) sent", total)


if __name__ == "__main__":
    asyncio.run(main())
