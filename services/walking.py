import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path("/workspace/apartment-agent")

CACHE_PATH = (
    BASE_DIR
    / "data"
    / "walking_cache.json"
)

VALHALLA_URL = (
    "https://valhalla1.openstreetmap.de/route"
)

CLIENT_ID = "personal-apartment-agent"

MEMORY_CACHE = {}


def load_cache():
    if MEMORY_CACHE:
        return MEMORY_CACHE

    if not CACHE_PATH.exists():
        MEMORY_CACHE.update({})
        return MEMORY_CACHE

    try:
        with open(
            CACHE_PATH,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        MEMORY_CACHE.update(data)

    except Exception:
        MEMORY_CACHE.update({})

    return MEMORY_CACHE


def save_cache():
    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        CACHE_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            MEMORY_CACHE,
            f,
            ensure_ascii=False,
            indent=2,
        )


def coordinate_key(
    origin_lat,
    origin_lon,
    dest_lat,
    dest_lon,
):
    return (
        f"{origin_lat:.6f},"
        f"{origin_lon:.6f}:"
        f"{dest_lat:.6f},"
        f"{dest_lon:.6f}"
    )


def fetch_walking_route(
    origin_lat,
    origin_lon,
    dest_lat,
    dest_lon,
):
    payload = {
        "locations": [
            {
                "lat": origin_lat,
                "lon": origin_lon,
            },
            {
                "lat": dest_lat,
                "lon": dest_lon,
            },
        ],
        "costing": "pedestrian",
        "units": "kilometers",
        "directions_options": {
            "units": "kilometers",
        },
    }

    params = urllib.parse.urlencode(
        {
            "json": json.dumps(
                payload,
                separators=(",", ":"),
            )
        }
    )

    url = (
        VALHALLA_URL
        + "?"
        + params
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "apartment-agent/1.0"
            ),
            "X-Client-Id":
                CLIENT_ID,
            "Accept":
                "application/json",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        raw = (
            response
            .read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

    return json.loads(raw)


def walking_route(
    origin_lat,
    origin_lon,
    dest_lat,
    dest_lon,
):
    cache = load_cache()

    key = coordinate_key(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
    )

    if key in cache:
        return cache[key]

    try:
        response = fetch_walking_route(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
        )

        trip = response.get(
            "trip",
            {},
        )

        summary = trip.get(
            "summary",
            {},
        )

        length_km = summary.get(
            "length"
        )

        time_seconds = summary.get(
            "time"
        )

        if (
            length_km is None
            or time_seconds is None
        ):
            return None

        result = {
            "distance_m": round(
                float(length_km)
                * 1000
            ),

            "walking_minutes": round(
                float(time_seconds)
                / 60
            ),

            "routing_source":
                "Valhalla/OpenStreetMap",
        }

        cache[key] = result

        save_cache()

        # Be polite to public demo.
        time.sleep(0.2)

        return result

    except Exception:
        return None
