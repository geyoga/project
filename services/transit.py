import json
import os
import tempfile
import urllib.parse
import urllib.request
from config import DATA_DIR


CACHE_PATH = DATA_DIR / "transit_cache.json"


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

# Conservative, manually reviewed estimates in minutes from station platforms
# to Futako-Tamagawa. UR access time is added separately.
LOCAL_COMMUTES = {
    "青葉台": (23, 0, True),
    "鴨居": (43, 1, False),
    "大和": (48, 1, False),
    "高座渋谷": (52, 1, False),
    "いずみ中央": (54, 1, False),
    "片倉町": (40, 2, False), "横浜": (39, 1, False),
    "鶴川": (41, 1, False), "玉川学園前": (46, 1, False), "柿生": (45, 1, False), "こどもの国": (35, 1, False),
    "小田急相模原": (49, 1, False), "古淵": (51, 2, False), "日吉": (27, 1, False), "日吉本町": (30, 1, False), "綱島": (33, 1, False),
    "二俣川": (48, 2, False), "東戸塚": (54, 2, False), "鶴ヶ峰": (51, 2, False), "生田": (34, 1, False), "溝の口": (4, 0, True),
    "たまプラーザ": (9, 0, True), "あざみ野": (12, 0, True), "新百合ヶ丘": (38, 1, False), "百合ヶ丘": (38, 1, False),
    "厚木": (58, 1, False), "海老名": (58, 1, False), "本厚木": (62, 1, False), "さがみ野": (59, 2, False), "南林間": (55, 1, False), "座間": (57, 1, False),
    "天王町": (47, 2, False), "保土ケ谷": (49, 2, False), "西横浜": (49, 2, False), "都筑ふれあいの丘": (25, 1, False), "江田": (15, 0, True), "センター南": (22, 1, False),
    "橋本": (60, 2, False), "多摩境": (66, 2, False), "相模大野": (43, 1, False), "中央林間": (35, 0, True), "戸塚": (58, 2, False), "舞岡": (53, 2, False), "下永谷": (55, 2, False),
    "大口": (47, 2, False), "鶴見": (50, 2, False), "妙蓮寺": (37, 1, False), "十日市場": (36, 1, False), "中山": (35, 1, False), "仲町台": (27, 1, False), "東林間": (45, 1, False), "町田": (46, 1, False),
    "元町・中華街": (47, 1, False), "桜木町": (45, 2, False), "根岸": (55, 2, False), "山手": (53, 2, False),
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

    fd, temporary = tempfile.mkstemp(
        dir=CACHE_PATH.parent,
        prefix=".transit_cache.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                MEMORY_CACHE,
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(temporary, CACHE_PATH)
    except Exception:
        os.unlink(temporary)
        raise


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


def get_local_route(station, destination):
    route = LOCAL_COMMUTES.get(station)
    if not route or destination != "Futako-Tamagawa":
        return None
    train_minutes, transfers, direct = route
    return {
        "train_minutes": train_minutes,
        "transfers": transfers,
        "direct": direct,
        "source": "local_station_table",
    }
