REQUIRED_CANONICAL_FIELDS = (
    "source",
    "source_url",
    "property",
    "rent",
    "management_fee",
    "monthly_total",
    "layout",
    "area_m2",
    "floor",
)


def validate_listing(listing):
    missing = [key for key in REQUIRED_CANONICAL_FIELDS if key not in listing]
    if missing:
        raise ValueError("Missing canonical fields: " + ", ".join(missing))
    if listing.get("source") not in {"ur", "suumo", "chintai"}:
        raise ValueError(f"Unsupported source: {listing.get('source')}")
    return True


def normalize_listing(listing):
    room = dict(listing)
    floor = room.get("floor")
    if isinstance(floor, int):
        room["floor_number"] = floor
        room["floor"] = f"{floor}階"
    elif isinstance(floor, str):
        digits = "".join(char for char in floor if char.isdigit())
        room["floor_number"] = int(digits) if digits else None
    else:
        room["floor_number"] = None
    room.setdefault("access_type", "walk")
    room.setdefault("facilities", {})
    return room
