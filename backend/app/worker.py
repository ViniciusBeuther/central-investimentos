"""Background worker: refreshes quotes automatically while the B3 market is open.

Runs as the `worker` service in docker-compose (started by `docker compose up -d`).

Schedule (Brasília time, Monday to Friday): every 30 minutes from 10:00 to 18:00, plus one
run at 18:30 to catch the closing price. That is about 17 runs x 21 assets per day, roughly
8,000 requests a month, well inside the free plan's 15,000. Holidays are not special-cased:
a run on a closed day gets the same quote time as before, which is stored only once.

Brazil has had no daylight saving time since 2019, so Brasília time is a fixed UTC-3 and
no timezone database is needed.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import psycopg

from app.quotes import refresh

BRASILIA = timezone(timedelta(hours=-3))
INTERVAL = timedelta(minutes=30)
OPEN_FROM, OPEN_UNTIL = (10, 0), (18, 0)
CLOSING_RUN = (18, 30)


def is_market_window(now: datetime) -> bool:
    """True while a refresh should happen: weekdays 10:00-18:00, plus the 18:30 closing run."""
    local = now.astimezone(BRASILIA)
    if local.weekday() >= 5:
        return False
    clock = (local.hour, local.minute)
    return OPEN_FROM <= clock <= OPEN_UNTIL or CLOSING_RUN <= clock < (18, 40)


def due(now: datetime, last_fetch: datetime | None) -> bool:
    """Run when inside the window and the last fetch is older than the interval."""
    if not is_market_window(now):
        return False
    return last_fetch is None or now - last_fetch >= INTERVAL - timedelta(seconds=30)


def log(message: str) -> None:
    print(f"{datetime.now(BRASILIA):%Y-%m-%d %H:%M} {message}", flush=True)


def main() -> None:
    token = os.environ.get("BRAPI_TOKEN") or None
    if not token:
        log("BRAPI_TOKEN is not set: the worker will not fetch quotes. Set it in .env and restart.")
    log("worker started")
    while True:
        try:
            if token:
                with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                    last_fetch = conn.execute("SELECT max(fetched_at) FROM quotes").fetchone()[0]
                    if due(datetime.now(timezone.utc), last_fetch):
                        quotes, failures = refresh(conn, token=token)
                        log(f"quotes refreshed: {len(quotes)} ok, {len(failures)} failed {failures or ''}")
        except Exception as error:  # keep the loop alive; the next tick retries
            log(f"refresh error: {error}")
        time.sleep(60)


if __name__ == "__main__":
    main()
