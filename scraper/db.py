import os
from datetime import date
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PgConnection


def get_connection() -> PgConnection:
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url)


def upsert_listing(conn: PgConnection, listing: dict[str, Any]) -> str:
    """Insert or update a listing. Returns 'new', 'price_change', or 'unchanged'."""
    # CTE captures the pre-upsert price so RETURNING can detect changes.
    # RETURNING listings.price would be the post-update value, not the old one.
    sql = """
        WITH prev AS (
            SELECT price FROM listings WHERE id = %(id)s
        )
        INSERT INTO listings (
            id, property_type, search_area, location, bedrooms,
            price, price_per_sqm, size_sqm, condition, url,
            first_seen, last_seen, is_active
        ) VALUES (
            %(id)s, %(property_type)s, %(search_area)s, %(location)s, %(bedrooms)s,
            %(price)s, %(price_per_sqm)s, %(size_sqm)s, %(condition)s, %(url)s,
            CURRENT_DATE, CURRENT_DATE, TRUE
        )
        ON CONFLICT (id) DO UPDATE SET
            price        = EXCLUDED.price,
            price_per_sqm = EXCLUDED.price_per_sqm,
            size_sqm     = EXCLUDED.size_sqm,
            location     = EXCLUDED.location,
            bedrooms     = EXCLUDED.bedrooms,
            condition    = EXCLUDED.condition,
            last_seen    = CURRENT_DATE,
            is_active    = TRUE
        RETURNING
            (xmax = 0) AS is_insert,
            (SELECT price FROM prev) AS old_price
    """
    with conn.cursor() as cur:
        cur.execute(sql, listing)
        row = cur.fetchone()
        if row is None:
            return "unchanged"
        is_insert, old_price = row
        if is_insert:
            return "new"
        if old_price != listing.get("price"):
            return "price_change"
        return "unchanged"


def record_snapshot(
    conn: PgConnection, listing_id: str, price: int | None, scraped_at: date
) -> None:
    sql = """
        INSERT INTO price_snapshots (listing_id, scraped_at, price)
        VALUES (%s, %s, %s)
        ON CONFLICT (listing_id, scraped_at) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.execute(sql, (listing_id, scraped_at, price))


def mark_delisted(
    conn: PgConnection, area: str, prop_type: str, seen_ids: set[str]
) -> int:
    """Set is_active=FALSE for listings not seen this run. Returns count updated."""
    if seen_ids:
        sql = """
            UPDATE listings
            SET is_active = FALSE
            WHERE search_area = %s
              AND property_type = %s
              AND is_active = TRUE
              AND id != ALL(%s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (area, prop_type, list(seen_ids)))
            return cur.rowcount
    else:
        sql = """
            UPDATE listings
            SET is_active = FALSE
            WHERE search_area = %s
              AND property_type = %s
              AND is_active = TRUE
        """
        with conn.cursor() as cur:
            cur.execute(sql, (area, prop_type))
            return cur.rowcount


def log_scrape_run(conn: PgConnection, run_data: dict[str, Any]) -> int:
    """Insert scrape run record. Returns new run id."""
    sql = """
        INSERT INTO scrape_runs (
            started_at, completed_at, total_listings,
            new_listings, price_changes, errors
        ) VALUES (
            %(started_at)s, %(completed_at)s, %(total_listings)s,
            %(new_listings)s, %(price_changes)s, %(errors)s
        )
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, run_data)
        row = cur.fetchone()
        return row[0] if row else -1
