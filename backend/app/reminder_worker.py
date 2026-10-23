"""Run separately: python -m app.reminder_worker [--once] [--interval 30]."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime

from app.config import get_settings
from app.database import SessionLocal, engine
from app.reminders import run_due_reminders


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver StudyVault examination reminders")
    parser.add_argument("--once", action="store_true", help="Run one tick for cron/Task Scheduler")
    parser.add_argument(
        "--interval", type=int, default=30, help="Seconds between standalone worker ticks"
    )
    parser.add_argument("--now", help="An aware ISO timestamp; only allowed in ENVIRONMENT=test")
    args = parser.parse_args()
    if args.interval < 1:
        parser.error("--interval must be positive")
    now = None
    if args.now:
        if get_settings().environment != "test" or not args.once:
            parser.error("--now requires ENVIRONMENT=test and --once")
        try:
            now = datetime.fromisoformat(args.now)
        except ValueError:
            parser.error("--now must be an ISO timestamp")
        if now.tzinfo is None:
            parser.error("--now must include a UTC offset")
    try:
        while True:
            try:
                print(json.dumps(run_due_reminders(SessionLocal, now=now)), flush=True)
            except Exception:
                if args.once:
                    raise
                logging.exception("Reminder tick failed; the next tick will retry")
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
