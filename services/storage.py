import hashlib
import json
import sqlite3

from datetime import (
    datetime,
    timezone,
)

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


# ============================================================
# Utilities
# ============================================================

def utc_now():
    return (
        datetime.now(
            timezone.utc
        )
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


# ============================================================
# Schema helpers
# ============================================================

def column_exists(
    conn,
    table_name,
    column_name,
):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        row["name"] == column_name
        for row in rows
    )


# ============================================================
# Database initialization
# ============================================================

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

                listing_fingerprint TEXT,

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


            CREATE TABLE IF NOT EXISTS notification_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                event_key TEXT NOT NULL UNIQUE,

                listing_id TEXT NOT NULL,
                crawl_run_id INTEGER,

                event_type TEXT NOT NULL,

                created_at TEXT NOT NULL,
                delivered_at TEXT,

                message TEXT NOT NULL,

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


            CREATE INDEX IF NOT EXISTS
                idx_notification_pending
            ON notification_events(
                delivered_at
            );
            """
        )

        # Migration for an older database.
        if not column_exists(
            conn,
            "listings",
            "listing_fingerprint",
        ):
            conn.execute(
                """
                ALTER TABLE listings
                ADD COLUMN listing_fingerprint TEXT
                """
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_listings_fingerprint
            ON listings(
                listing_fingerprint
            )
            """
        )


# ============================================================
# Listing identity
# ============================================================

def make_listing_id(room):
    source = (
        room.get("source")
        or "unknown"
    )

    source_listing_id = (
        room.get(
            "source_listing_id"
        )
    )

    # Private portals such as SUUMO.
    if source_listing_id:
        return (
            f"{source}:"
            f"{source_listing_id}"
        )

    # UR identity.
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


def make_listing_fingerprint(room):
    """
    Generate probable physical-unit identity.

    UR already has reliable building / room IDs, so UR units
    must never be merged purely because their attributes match.

    Private portals can advertise the same unit multiple times,
    so their fingerprint uses physical/listing attributes.
    """

    source = (
        str(
            room.get("source")
            or "unknown"
        )
        .strip()
        .lower()
    )

    # --------------------------------------------------------
    # UR
    # --------------------------------------------------------

    if source == "ur":
        property_key = (
            room.get(
                "property_key"
            )
        )

        if not property_key:
            property_key = (
                f"{room.get('shisya') or ''}_"
                f"{room.get('danchi') or ''}_"
                f"{room.get('shikibetu') or ''}"
            )

        room_name = (
            str(
                room.get("room")
                or ""
            )
            .strip()
            .lower()
        )

        raw = (
            f"ur|"
            f"{property_key}|"
            f"{room_name}"
        )

        return hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()[:20]

    # --------------------------------------------------------
    # Private sources
    # --------------------------------------------------------

    station = (
        str(
            room.get(
                "primary_station"
            )
            or ""
        )
        .strip()
        .lower()
        .replace("駅", "")
    )

    address = (
        str(
            room.get(
                "address"
            )
            or ""
        )
        .strip()
        .lower()
        .replace(" ", "")
        .replace("　", "")
    )

    layout = (
        str(
            room.get(
                "layout"
            )
            or ""
        )
        .strip()
        .upper()
    )

    area = (
        room.get(
            "area_m2"
        )
    )

    if isinstance(
        area,
        (int, float),
    ):
        area = round(
            float(area),
            2,
        )

    floor_number = (
        room.get(
            "floor_number"
        )
    )

    # Incoming Hermes listings may only have floor.
    if floor_number is None:
        floor_value = (
            room.get("floor")
        )

        if isinstance(
            floor_value,
            int,
        ):
            floor_number = floor_value

    parts = [
        address,
        station,

        str(
            room.get(
                "station_walk_minutes"
            )
            or ""
        ),

        str(
            room.get(
                "rent"
            )
            or ""
        ),

        str(
            room.get(
                "management_fee"
            )
            or ""
        ),

        layout,

        str(
            area
            or ""
        ),

        str(
            floor_number
            or ""
        ),
    ]

    raw = "|".join(
        parts
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:20]


# ============================================================
# Crawl runs
# ============================================================

def start_crawl_run(
    areas_requested,
):
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
                utc_now(),
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


# ============================================================
# Listing persistence
# ============================================================

def save_listing(
    conn,
    run_id,
    room,
):
    listing_id = (
        make_listing_id(
            room
        )
    )

    listing_fingerprint = (
        make_listing_fingerprint(
            room
        )
    )

    # Attach it to the in-memory room so alerts can use it.
    room[
        "listing_fingerprint"
    ] = listing_fingerprint

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

    # --------------------------------------------------------
    # New listing
    # --------------------------------------------------------

    if existing is None:
        change = {
            "type":
                "new",

            "listing_id":
                listing_id,

            "listing_fingerprint":
                listing_fingerprint,
        }

        conn.execute(
            """
            INSERT INTO listings (
                listing_id,
                listing_fingerprint,

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
                ?, ?,
                ?, ?, ?,
                ?,
                ?, ?, ?, ?,
                ?, ?,
                1,
                ?, ?, ?,
                ?, ?, ?,
                ?,
                ?
            )
            """,
            (
                listing_id,
                listing_fingerprint,

                room.get(
                    "source"
                ),

                room.get(
                    "property"
                ),

                room.get(
                    "room"
                ),

                room.get(
                    "source_url"
                ),

                room.get(
                    "shisya"
                ),

                room.get(
                    "danchi"
                ),

                room.get(
                    "shikibetu"
                ),

                room.get(
                    "area_code"
                ),

                now,
                now,

                room.get(
                    "rent"
                ),

                room.get(
                    "management_fee"
                ),

                room.get(
                    "monthly_total"
                ),

                room.get(
                    "layout"
                ),

                room.get(
                    "area_m2"
                ),

                room.get(
                    "floor"
                ),

                room.get(
                    "score"
                ),

                json.dumps(
                    room,
                    ensure_ascii=False,
                ),
            ),
        )

    # --------------------------------------------------------
    # Existing listing
    # --------------------------------------------------------

    else:
        previous_total = (
            existing[
                "monthly_total"
            ]
        )

        current_total = (
            room.get(
                "monthly_total"
            )
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

                "listing_fingerprint":
                    listing_fingerprint,

                "previous_monthly_total":
                    previous_total,

                "monthly_total":
                    current_total,
            }

        elif not existing[
            "active"
        ]:
            change = {
                "type":
                    "returned",

                "listing_id":
                    listing_id,

                "listing_fingerprint":
                    listing_fingerprint,
            }

        conn.execute(
            """
            UPDATE listings

            SET
                listing_fingerprint = ?,

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
                listing_fingerprint,

                room.get(
                    "property"
                ),

                room.get(
                    "room"
                ),

                room.get(
                    "source_url"
                ),

                now,

                room.get(
                    "rent"
                ),

                room.get(
                    "management_fee"
                ),

                room.get(
                    "monthly_total"
                ),

                room.get(
                    "layout"
                ),

                room.get(
                    "area_m2"
                ),

                room.get(
                    "floor"
                ),

                room.get(
                    "score"
                ),

                json.dumps(
                    room,
                    ensure_ascii=False,
                ),

                listing_id,
            ),
        )

    # --------------------------------------------------------
    # Snapshot
    # --------------------------------------------------------

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

            room.get(
                "rent"
            ),

            room.get(
                "management_fee"
            ),

            room.get(
                "monthly_total"
            ),

            room.get(
                "layout"
            ),

            room.get(
                "area_m2"
            ),

            room.get(
                "floor"
            ),

            room.get(
                "score"
            ),

            json.dumps(
                room,
                ensure_ascii=False,
            ),
        ),
    )

    # IMPORTANT:
    # save_observed_listings expects EXACTLY TWO values.
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
                SELECT
                    listing_id

                FROM listings

                WHERE active = 1
                """
            ).fetchall()

            for row in active_rows:
                listing_id = (
                    row[
                        "listing_id"
                    ]
                )

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


# ============================================================
# Notification queue
# ============================================================

def make_notification_event_key(
    notification,
    run_id,
):
    event_type = (
        notification.get(
            "type"
        )
    )

    listing_id = (
        notification.get(
            "listing_id"
        )
    )

    if event_type == "new":
        return (
            f"new:"
            f"{listing_id}"
        )

    if event_type == "price_changed":
        message = (
            notification.get(
                "message",
                "",
            )
        )

        digest = hashlib.sha256(
            message.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        return (
            f"price_changed:"
            f"{listing_id}:"
            f"{digest}"
        )

    if event_type == "returned":
        return (
            f"returned:"
            f"{listing_id}:"
            f"{run_id}"
        )

    return (
        f"{event_type}:"
        f"{listing_id}:"
        f"{run_id}"
    )


def enqueue_notifications(
    run_id,
    notifications,
):
    inserted = 0

    with connect() as conn:
        for notification in notifications:
            event_key = (
                make_notification_event_key(
                    notification,
                    run_id,
                )
            )

            cursor = conn.execute(
                """
                INSERT OR IGNORE
                INTO notification_events (
                    event_key,
                    listing_id,
                    crawl_run_id,
                    event_type,
                    created_at,
                    message
                )

                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_key,

                    notification.get(
                        "listing_id"
                    ),

                    run_id,

                    notification.get(
                        "type"
                    ),

                    utc_now(),

                    notification.get(
                        "message"
                    ),
                ),
            )

            if cursor.rowcount > 0:
                inserted += 1

    return inserted


def get_pending_notifications():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                event_key,
                listing_id,
                event_type,
                created_at,
                message

            FROM notification_events

            WHERE delivered_at IS NULL

            ORDER BY id ASC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


def mark_notifications_delivered(
    notification_ids,
):
    if not notification_ids:
        return 0

    delivered_at = utc_now()

    placeholders = ",".join(
        "?"
        for _ in notification_ids
    )

    query = f"""
        UPDATE notification_events

        SET delivered_at = ?

        WHERE id IN ({placeholders})
        AND delivered_at IS NULL
    """

    values = [
        delivered_at,
        *notification_ids,
    ]

    with connect() as conn:
        cursor = conn.execute(
            query,
            values,
        )

        return cursor.rowcount