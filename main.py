import logging
import psycopg2
import requests
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from scraper.config import AREAS, PROPERTY_TYPES
from scraper.db import (
    get_connection,
    log_scrape_run,
    mark_delisted,
    record_snapshot,
    upsert_listing,
)
from scraper.fetcher import get_page
from scraper.parser import extract_listings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

MAX_PAGES = 100


def scrape() -> None:
    conn = get_connection()
    started_at = datetime.now(timezone.utc)
    today = date.today()

    total_listings = 0
    new_listings = 0
    price_changes = 0
    errors = 0

    try:
        for area_slug, area_name in AREAS.items():
            for prop_type in PROPERTY_TYPES:
                seen_ids: set[str] = set()
                combo_had_error = False
                log.info("Scraping %s / %s", area_name, prop_type)

                for page in range(1, MAX_PAGES + 1):
                    try:
                        html = get_page(area_slug, prop_type, page)
                    except (requests.RequestException, RuntimeError) as exc:
                        log.error("Fetch error %s/%s page %d: %s", area_name, prop_type, page, exc)
                        errors += 1
                        combo_had_error = True
                        break

                    listings = extract_listings(html)
                    if not listings:
                        log.info("  Page %d empty — stopping pagination", page)
                        break

                    try:
                        for listing in listings:
                            listing["property_type"] = prop_type
                            listing["search_area"] = area_name
                            status = upsert_listing(conn, listing)
                            record_snapshot(conn, listing["id"], listing.get("price"), today)
                            seen_ids.add(listing["id"])
                            total_listings += 1
                            if status == "new":
                                new_listings += 1
                            elif status == "price_change":
                                price_changes += 1
                        conn.commit()
                    except psycopg2.Error as exc:
                        log.error("DB error %s/%s page %d: %s", area_name, prop_type, page, exc)
                        conn.rollback()
                        errors += 1
                        combo_had_error = True
                else:
                    log.warning(
                        "MAX_PAGES (%d) hit for %s/%s — listings may be truncated",
                        MAX_PAGES,
                        area_name,
                        prop_type,
                    )

                if not combo_had_error:
                    try:
                        delisted = mark_delisted(conn, area_name, prop_type, seen_ids)
                        conn.commit()
                        if delisted:
                            log.info("  Marked %d listing(s) as delisted", delisted)
                    except psycopg2.Error as exc:
                        log.error("Delist error %s/%s: %s", area_name, prop_type, exc)
                        conn.rollback()
                        errors += 1

        completed_at = datetime.now(timezone.utc)
        run_id = -1
        try:
            run_id = log_scrape_run(
                conn,
                {
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "total_listings": total_listings,
                    "new_listings": new_listings,
                    "price_changes": price_changes,
                    "errors": errors,
                },
            )
            conn.commit()
        except psycopg2.Error as exc:
            log.error("Failed to log scrape run: %s", exc)
            conn.rollback()

    finally:
        conn.close()

    log.info(
        "Run #%d complete — %d total, %d new, %d price changes, %d errors",
        run_id,
        total_listings,
        new_listings,
        price_changes,
        errors,
    )


if __name__ == "__main__":
    scrape()
