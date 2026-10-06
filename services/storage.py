import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DB_PATH = (
    BASE_DIR
    / "data"
    / "apartments.db"
)


def utc_now():
    return (
        datetime.now(timezone.utc)
        .isoformat()
    )


def connect():
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA journal_mode=WAL"
    )

    connection.execute(
        "PRAGMA foreign_keys=ON"
    )

    return connection


def initialize_database():
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crawl_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,

                areas_requested INTEGER DEFAULT 0,
                areas_failed INTEGER DEFAULT 0,

                rooms_found INTEGER DEFAULT 0,
                rooms_matching INTEGER DEFAULT 0,

                error_json TEXT
            );


            CREATE TABLE IF NOT EXISTS listings (
                listing_id TEXT PRIMARY KEY,

                source TEXT NOT NULL,

                property_name TEXT,
                room_name TEXT,

                source_url TEXT,

                shisya TEXT,
                danchi TEXT,
                shikibetu TEXT,
                area_code TEXT,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,

                active INTEGER NOT NULL DEFAULT 1,

                rent INTEGER,
                management_fee INTEGER,
                monthly_total INTEGER,

                layout TEXT,
                area_m2 REAL,
                floor TEXT,

                score REAL,

                latest_json TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS listing_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                listing_id TEXT NOT NULL,
                crawl_run_id INTEGER NOT NULL,

                captured_at TEXT NOT NULL,

                rent INTEGER,
                management_fee INTEGER,
                monthly_total INTEGER,

                layout TEXT,
                area_m2 REAL,
                floor TEXT,

                score REAL,

                snapshot_json TEXT NOT NULL,

                FOREIGN KEY(listing_id)
                    REFERENCES listings(listing_id),

                FOREIGN KEY(crawl_run_id)
                    REFERENCES crawl_runs(id)
            );


            CREATE INDEX IF NOT EXISTS
                idx_listings_active
            ON listings(active);


            CREATE INDEX IF NOT EXISTS
                idx_listings_score
            ON listings(score);


            CREATE INDEX IF NOT EXISTS
                idx_snapshots_listing
            ON listing_snapshots(
                listing_id,
                captured_at
            );
            """
        )


def make_listing_id(room):
    source = (
        room.get("source")
        or "unknown"
    )

    shisya = (
        room.get("shisya")
        or ""
    )

    danchi = (
        room.get("danchi")
        or ""
    )

    shikibetu = (
        room.get("shikibetu")
        or ""
    )

    room_name = (
        room.get("room")
        or ""
    )

    return (
        f"{source}:"
        f"{shisya}:"
        f"{danchi}:"
        f"{shikibetu}:"
        f"{room_name}"
    )


def start_crawl_run(
    areas_requested,
):
    started_at = utc_now()

    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO crawl_runs (
                started_at,
                areas_requested
            )
            VALUES (?, ?)
            """,
            (
                started_at,
                areas_requested,
            ),
        )

        return cursor.lastrowid


def finish_crawl_run(
    run_id,
    areas_failed,
    rooms_found,
    rooms_matching,
    crawl_errors,
):
    with connect() as conn:
        conn.execute(
            """
            UPDATE crawl_runs

            SET
                finished_at = ?,
                areas_failed = ?,
                rooms_found = ?,
                rooms_matching = ?,
                error_json = ?

            WHERE id = ?
            """,
            (
                utc_now(),
                areas_failed,
                rooms_found,
                rooms_matching,
                json.dumps(
                    crawl_errors,
                    ensure_ascii=False,
                ),
                run_id,
            ),
        )


def save_listing(
    conn,
    run_id,
    room,
):
    listing_id = make_listing_id(
        room
    )

    now = utc_now()

    existing = conn.execute(
        """
        SELECT *
        FROM listings
        WHERE listing_id = ?
        """,
        (
            listing_id,
        ),
    ).fetchone()

    change = None

    if existing is None:
        change = {
            "type": "new",
            "listing_id": listing_id,
        }

        conn.execute(
            """
            INSERT INTO listings (
                listing_id,

                source,
                property_name,
                room_name,

                source_url,

                shisya,
                danchi,
                shikibetu,
                area_code,

                first_seen_at,
                last_seen_at,

                active,

                rent,
                management_fee,
                monthly_total,

                layout,
                area_m2,
                floor,

                score,

                latest_json
            )

            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, 1,
                ?, ?, ?, ?, ?,
                ?, ?, ?
            )
            """,
            (
                listing_id,

                room.get("source"),
                room.get("property"),
                room.get("room"),

                room.get("source_url"),

                room.get("shisya"),
                room.get("danchi"),
                room.get("shikibetu"),
                room.get("area_code"),

                now,
                now,

                room.get("rent"),
                room.get(
                    "management_fee"
                ),
                room.get(
                    "monthly_total"
                ),

                room.get("layout"),
                room.get("area_m2"),
                room.get("floor"),

                room.get("score"),

                json.dumps(
                    room,
                    ensure_ascii=False,
                ),
            ),
        )

    else:
        previous_total = (
            existing[
                "monthly_total"
            ]
        )

        current_total = room.get(
            "monthly_total"
        )

        if (
            previous_total
            != current_total
        ):
            change = {
                "type":
                    "price_changed",

                "listing_id":
                    listing_id,

                "previous_monthly_total":
                    previous_total,

                "monthly_total":
                    current_total,
            }

        elif not existing["active"]:
            change = {
                "type": "returned",
                "listing_id": listing_id,
            }

        conn.execute(
            """
            UPDATE listings

            SET
                property_name = ?,
                room_name = ?,
                source_url = ?,

                last_seen_at = ?,
                active = 1,

                rent = ?,
                management_fee = ?,
                monthly_total = ?,

                layout = ?,
                area_m2 = ?,
                floor = ?,

                score = ?,

                latest_json = ?

            WHERE listing_id = ?
            """,
            (
                room.get("property"),
                room.get("room"),
                room.get(
                    "source_url"
                ),

                now,

                room.get("rent"),
                room.get(
                    "management_fee"
                ),
                room.get(
                    "monthly_total"
                ),

                room.get("layout"),
                room.get("area_m2"),
                room.get("floor"),

                room.get("score"),

                json.dumps(
                    room,
                    ensure_ascii=False,
                ),

                listing_id,
            ),
        )

    conn.execute(
        """
        INSERT INTO listing_snapshots (
            listing_id,
            crawl_run_id,
            captured_at,

            rent,
            management_fee,
            monthly_total,

            layout,
            area_m2,
            floor,

            score,

            snapshot_json
        )

        VALUES (
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?
        )
        """,
        (
            listing_id,
            run_id,
            now,

            room.get("rent"),
            room.get(
                "management_fee"
            ),
            room.get(
                "monthly_total"
            ),

            room.get("layout"),
            room.get("area_m2"),
            room.get("floor"),

            room.get("score"),

            json.dumps(
                room,
                ensure_ascii=False,
            ),
        ),
    )

    return (
        listing_id,
        change,
    )


def save_observed_listings(
    run_id,
    rooms,
    mark_missing_inactive=True,
):
    seen_ids = set()

    changes = []

    with connect() as conn:
        for room in rooms:
            listing_id, change = (
                save_listing(
                    conn,
                    run_id,
                    room,
                )
            )

            seen_ids.add(
                listing_id
            )

            if change:
                changes.append(
                    change
                )

        if mark_missing_inactive:
            active_rows = conn.execute(
                """
                SELECT listing_id

                FROM listings

                WHERE active = 1
                """
            ).fetchall()

            for row in active_rows:
                listing_id = row[
                    "listing_id"
                ]

                if (
                    listing_id
                    in seen_ids
                ):
                    continue

                conn.execute(
                    """
                    UPDATE listings

                    SET active = 0

                    WHERE listing_id = ?
                    """,
                    (
                        listing_id,
                    ),
                )

                changes.append(
                    {
                        "type":
                            "removed",

                        "listing_id":
                            listing_id,
                    }
                )

    return changes