"""Watch meso.watch for popular items suddenly listed far below their usual price.

A "deal" is a listing for a popular item (seen in many listings recently) whose
price is at least DISCOUNT below that item's median price over the lookback window.

Run continuously:   python watcher.py --interval 300
Run once (cron):    python watcher.py --once
Alerts go to stdout, plus a Discord webhook if DISCORD_WEBHOOK_URL is set.
"""
import argparse
import json
import os
import sqlite3
import statistics
import time
import urllib.request
from dataclasses import dataclass

DB_PATH = os.environ.get("MESO_WATCH_DB", os.path.join(os.path.dirname(__file__), "history.db"))
LOOKBACK_DAYS = float(os.environ.get("LOOKBACK_DAYS", 7))
MIN_LISTINGS = int(os.environ.get("MIN_LISTINGS", 20))  # how many listings make an item "popular"
DISCOUNT = float(os.environ.get("DISCOUNT", 0.30))  # 0.30 = at least 30% under median
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


@dataclass
class Listing:
    listing_id: str
    item: str
    price: int
    server: str = ""
    url: str = ""


def fetch_listings() -> list[Listing]:
    # TODO: implement once meso.watch is reachable from this environment and its
    # page/API shape is known.
    raise NotImplementedError("meso.watch reader not written yet")


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS observations (
            listing_id TEXT, item TEXT, server TEXT, price INTEGER, seen_at REAL,
            PRIMARY KEY (listing_id, price)
        );
        CREATE INDEX IF NOT EXISTS obs_item ON observations (item, server, seen_at);
        CREATE TABLE IF NOT EXISTS alerted (listing_id TEXT, price INTEGER, PRIMARY KEY (listing_id, price));
        """
    )
    return db


def find_deals(db: sqlite3.Connection, listings: list[Listing], now: float) -> list[tuple[Listing, float, int]]:
    """Return (listing, median, sample_size) for each new deal, then record the listings."""
    since = now - LOOKBACK_DAYS * 86400
    deals = []
    for l in listings:
        prices = [
            p for (p,) in db.execute(
                "SELECT price FROM observations WHERE item = ? AND server = ? AND seen_at >= ? AND listing_id != ?",
                (l.item, l.server, since, l.listing_id),
            )
        ]
        if len(prices) < MIN_LISTINGS:
            continue
        median = statistics.median(prices)
        if l.price > median * (1 - DISCOUNT):
            continue
        if db.execute("SELECT 1 FROM alerted WHERE listing_id = ? AND price = ?", (l.listing_id, l.price)).fetchone():
            continue
        db.execute("INSERT INTO alerted VALUES (?, ?)", (l.listing_id, l.price))
        deals.append((l, median, len(prices)))
    db.executemany(
        "INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?)",
        [(l.listing_id, l.item, l.server, l.price, now) for l in listings],
    )
    db.commit()
    return deals


def alert(listing: Listing, median: float, sample: int) -> None:
    pct = 100 * (1 - listing.price / median)
    msg = (
        f"DEAL: {listing.item}{f' [{listing.server}]' if listing.server else ''} "
        f"at {listing.price:,} mesos, {pct:.0f}% under the {LOOKBACK_DAYS:g}-day median of "
        f"{median:,.0f} ({sample} listings) {listing.url}"
    ).strip()
    print(msg, flush=True)
    if DISCORD_WEBHOOK_URL:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=json.dumps({"content": msg}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except OSError as e:
            print(f"Discord alert failed: {e}", flush=True)


def run_once(db: sqlite3.Connection) -> None:
    for listing, median, sample in find_deals(db, fetch_listings(), time.time()):
        alert(listing, median, sample)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true", help="check once and exit")
    ap.add_argument("--interval", type=int, default=300, help="seconds between checks")
    args = ap.parse_args()
    db = connect()
    while True:
        try:
            run_once(db)
        except Exception as e:  # keep watching through transient site errors
            print(f"check failed: {e}", flush=True)
            if args.once:
                raise
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
