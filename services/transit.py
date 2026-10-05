import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(
    "/workspace/apartment-agent"
)

CACHE_PATH = (
    BASE_DIR
    / "data"
    / "transit_cache.json"
)


EKISPERT_URL = (
    "https://api.ekispert.jp/"
    "v1/json/search/course/plain"
)


STATIC_COMMUTES = {
    "青葉台": {
        "destination":
            "Futako-Tamagawa",

        "train_minutes":
            23,

        "transfers":
            0,

        "direct":
            True,

        "source":
            "static_fallback",
    },

    "鴨居": {
        "destination":
            "Futako-Tamagawa",

        "train_minutes":
            43,

        "transfers":
            1,

        "direct":
            False,

        "source":
            "static_fallback",
    },
}


MEMORY_CACHE = {}


def load_cache():
    if MEMORY_CACHE:
        return MEMORY_CACHE

    if not CACHE_PATH.exists():
        return MEMORY_CACHE

    try:
        with open(
            CACHE_PATH,
            "r",
            encoding="utf-8",
        ) as f:
            MEMORY_CACHE.update(
                json.load(f)
            )

    except Exception:
        pass

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


def normalize_destination(
    destination,
):
    mapping = {
        "Futako-Tamagawa":
            "二子玉川",
    }

    return mapping.get(
        destination,
        destination,
    )


def parse_course_response(data):
    result_set = data.get(
        "ResultSet",
        {},
    )

    courses = result_set.get(
        "Course"
    )

    if not courses:
        return None

    if isinstance(
        courses,
        dict,
    ):
        courses = [
            courses
        ]

    best = None

    for course in courses:
        route = course.get(
            "Route",
            {},
        )

        if not route:
            continue

        try:
            onboard = int(
                route.get(
                    "timeOnBoard",
                    0,
                )
            )

            other = int(
                route.get(
                    "timeOther",
                    0,
                )
            )

            walk = int(
                route.get(
                    "timeWalk",
                    0,
                )
            )

            transfers = int(
                route.get(
                    "transferCount",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        total = (
            onboard
            + other
            + walk
        )

        candidate = {
            "train_minutes":
                total,

            "transfers":
                transfers,

            "direct":
                transfers == 0,

            "source":
                "ekispert",
        }

        if (
            best is None
            or candidate[
                "train_minutes"
            ]
            < best[
                "train_minutes"
            ]
        ):
            best = candidate

    return best


def query_ekispert(
    origin,
    destination,
):
    api_key = os.getenv(
        "EKISPERT_API_KEY"
    )

    if not api_key:
        return None

    params = {
        "key":
            api_key,

        "from":
            origin,

        "to":
            normalize_destination(
                destination
            ),
    }

    url = (
        EKISPERT_URL
        + "?"
        + urllib.parse.urlencode(
            params
        )
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept":
                "application/json",
            "User-Agent":
                "apartment-agent/1.0",
        },
    )

    try:
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

        return parse_course_response(
            json.loads(raw)
        )

    except Exception:
        return None


def get_transit_route(
    origin,
    destination,
):
    if not origin:
        return None

    cache = load_cache()

    key = (
        f"{origin}:"
        f"{destination}"
    )

    if key in cache:
        return cache[key]

    # Prefer real API.
    result = query_ekispert(
        origin,
        destination,
    )

    # Safe fallback while no API key
    # or API isn't available.
    if result is None:
        fallback = (
            STATIC_COMMUTES.get(
                origin
            )
        )

        if fallback:
            result = dict(
                fallback
            )

    if result:
        cache[key] = result

        save_cache()

    return result
