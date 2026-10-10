import json
from pathlib import Path


BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

INCOMING_DIR = (
    BASE_DIR
    / "data"
    / "incoming"
)


REQUIRED_FIELDS = {
    "source",
    "source_listing_id",
    "source_url",
    "property",
    "rent",
    "management_fee",
    "monthly_total",
    "layout",
    "area_m2",
    "floor",
    "address",
    "primary_station",
    "station_walk_minutes",
    "building_age_estimate_years",
    "structure",
    "orientation",
}


def validate_listing(data):
    missing = (
        REQUIRED_FIELDS
        - set(data.keys())
    )

    if missing:
        raise ValueError(
            "Missing fields: "
            + ", ".join(
                sorted(missing)
            )
        )

    source = data.get("source")

    if source not in {
        "suumo",
        "chintai",
    }:
        raise ValueError(
            f"Unsupported source: {source}"
        )

    if not data.get(
        "source_listing_id"
    ):
        raise ValueError(
            "source_listing_id is required"
        )

    if not data.get(
        "source_url"
    ):
        raise ValueError(
            "source_url is required"
        )


def normalize_listing(data):
    room = dict(data)

    floor = room.get("floor")

    if isinstance(
        floor,
        int,
    ):
        room["floor_number"] = floor
        room["floor"] = (
            f"{floor}階"
        )

    elif isinstance(
        floor,
        str,
    ):
        digits = "".join(
            c
            for c in floor
            if c.isdigit()
        )

        room["floor_number"] = (
            int(digits)
            if digits
            else None
        )

    else:
        room["floor_number"] = None

    room.setdefault(
        "access_type",
        "walk",
    )

    room.setdefault(
        "train_line",
        None,
    )

    room.setdefault(
        "shisya",
        None,
    )

    room.setdefault(
        "danchi",
        None,
    )

    room.setdefault(
        "shikibetu",
        None,
    )

    room.setdefault(
        "area_code",
        None,
    )

    room.setdefault(
        "facilities",
        {},
    )

    room.setdefault(
        "foreigner_friendly",
        {
            "score": 40,
            "status": "unknown",
            "evidence": [],
            "notes":
                "No explicit foreigner acceptance "
                "verified.",
        },
    )

    room.setdefault(
        "initial_cost",
        {
            "estimated_total": None,
            "estimate_only": True,
            "source":
                room.get("source"),
        },
    )

    return room


def load_incoming_listings():
    INCOMING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    listings = []
    errors = []

    for path in sorted(
        INCOMING_DIR.glob(
            "*.json"
        )
    ):
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            validate_listing(
                data
            )

            room = normalize_listing(
                data
            )

            room[
                "_incoming_file"
            ] = str(path)

            listings.append(
                room
            )

        except Exception as e:
            errors.append(
                {
                    "file":
                        str(path),

                    "error":
                        str(e),
                }
            )

    return (
        listings,
        errors,
    )