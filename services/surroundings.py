import json
import math
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from services.walking import (
    walking_route,
)

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

CACHE_PATH = (
    BASE_DIR
    / "data"
    / "surroundings_cache.json"
)

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

OVERPASS_URL = (
    "https://overpass-api.de/api/interpreter"
)

SEARCH_RADIUS_M = 3000


USER_AGENT = os.getenv(
    "APARTMENT_AGENT_USER_AGENT",
    "apartment-agent/1.0 "
    "(personal apartment research)",
)


_last_nominatim_request = 0.0


# ============================================================
# CACHE
# ============================================================


def load_cache():
    if not CACHE_PATH.exists():
        return {}

    try:
        with open(
            CACHE_PATH,
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    except Exception:
        return {}


def save_cache(cache):
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
            cache,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# HTTP
# ============================================================


def http_get_json(
    url,
    timeout=30,
):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                USER_AGENT,

            "Accept":
                "application/json",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:

        raw = (
            response
            .read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

    return json.loads(
        raw
    )


def http_post_json(
    url,
    data,
    timeout=45,
):
    body = urllib.parse.urlencode(
        {
            "data": data,
        }
    ).encode(
        "utf-8"
    )

    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent":
                USER_AGENT,

            "Content-Type":
                "application/"
                "x-www-form-urlencoded",

            "Accept":
                "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:

        raw = (
            response
            .read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

    return json.loads(
        raw
    )


# ============================================================
# GEOCODING
# ============================================================


def wait_for_nominatim():
    global _last_nominatim_request

    elapsed = (
        time.time()
        - _last_nominatim_request
    )

    if elapsed < 1.1:
        time.sleep(
            1.1 - elapsed
        )

    _last_nominatim_request = (
        time.time()
    )


def geocode_query(query):
    wait_for_nominatim()

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "jp",
    }

    url = (
        NOMINATIM_URL
        + "?"
        + urllib.parse.urlencode(
            params
        )
    )

    results = http_get_json(
        url
    )

    if not results:
        return None

    result = results[0]

    return {
        "latitude":
            float(
                result["lat"]
            ),

        "longitude":
            float(
                result["lon"]
            ),

        "display_name":
            result.get(
                "display_name"
            ),
    }


def geocode_room(room):
    address = room.get(
        "address"
    )

    property_name = room.get(
        "property"
    )

    # First try the full address.
    if address:
        result = geocode_query(
            address
        )

        if result:
            return result

    # Fallback:
    # property name + prefecture.
    if property_name:
        result = geocode_query(
            f"{property_name} 神奈川県 日本"
        )

        if result:
            return result

    return None


# ============================================================
# DISTANCE
# ============================================================


def haversine_distance_m(
    lat1,
    lon1,
    lat2,
    lon2,
):
    earth_radius = 6371000

    phi1 = math.radians(
        lat1
    )

    phi2 = math.radians(
        lat2
    )

    delta_phi = math.radians(
        lat2 - lat1
    )

    delta_lambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(
            delta_phi / 2
        ) ** 2

        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(
            delta_lambda / 2
        ) ** 2
    )

    c = (
        2
        * math.atan2(
            math.sqrt(a),
            math.sqrt(
                1 - a
            ),
        )
    )

    return round(
        earth_radius * c
    )


# ============================================================
# OVERPASS
# ============================================================


def build_overpass_query(
    latitude,
    longitude,
):
    radius = SEARCH_RADIUS_M

    return f"""
[out:json][timeout:30];
(
  nwr(around:{radius},{latitude},{longitude})
    ["shop"="supermarket"];

  nwr(around:{radius},{latitude},{longitude})
    ["shop"="convenience"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="kindergarten"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="childcare"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="school"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="clinic"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="doctors"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="hospital"];

  nwr(around:{radius},{latitude},{longitude})
    ["amenity"="pharmacy"];

  nwr(around:{radius},{latitude},{longitude})
    ["leisure"="park"];
);
out center tags;
"""


def fetch_nearby_places(
    latitude,
    longitude,
):
    query = build_overpass_query(
        latitude,
        longitude,
    )

    result = http_post_json(
        OVERPASS_URL,
        query,
    )

    return result.get(
        "elements",
        [],
    )


# ============================================================
# OSM NORMALIZATION
# ============================================================


def element_coordinates(element):
    if (
        "lat" in element
        and "lon" in element
    ):
        return (
            float(
                element["lat"]
            ),
            float(
                element["lon"]
            ),
        )

    center = element.get(
        "center"
    )

    if center:
        if (
            "lat" in center
            and "lon" in center
        ):
            return (
                float(
                    center["lat"]
                ),
                float(
                    center["lon"]
                ),
            )

    return (
        None,
        None,
    )


def place_name(tags):
    return (
        tags.get(
            "name"
        )
        or tags.get(
            "name:ja"
        )
        or tags.get(
            "name:en"
        )
        or tags.get(
            "brand"
        )
        or "Unnamed"
    )


def is_elementary_school(
    name,
    tags,
):
    normalized = (
        name.lower()
        if name
        else ""
    )

    if "小学校" in name:
        return True

    if "elementary" in normalized:
        return True

    if "primary" in normalized:
        return True

    isced = tags.get(
        "isced:level",
        "",
    )

    if (
        "1" in str(isced)
    ):
        return True

    return False


def is_pediatric(
    name,
    tags,
):
    if "小児" in name:
        return True

    speciality = (
        tags.get(
            "healthcare:speciality",
            ""
        )
        or ""
    ).lower()

    if (
        "paediatrics"
        in speciality
        or "pediatrics"
        in speciality
        or "paediatric"
        in speciality
        or "pediatric"
        in speciality
    ):
        return True

    return False


def classify_element(
    element,
):
    tags = element.get(
        "tags",
        {},
    )

    name = place_name(
        tags
    )

    shop = tags.get(
        "shop"
    )

    amenity = tags.get(
        "amenity"
    )

    leisure = tags.get(
        "leisure"
    )

    categories = []

    if shop == "supermarket":
        categories.append(
            "supermarket"
        )

    if shop == "convenience":
        categories.append(
            "convenience_store"
        )

    if amenity in (
        "kindergarten",
        "childcare",
    ):
        categories.append(
            "daycare"
        )

    if amenity == "school":
        if is_elementary_school(
            name,
            tags,
        ):
            categories.append(
                "elementary_school"
            )

    if amenity in (
        "clinic",
        "doctors",
    ):
        categories.append(
            "clinic"
        )

        if is_pediatric(
            name,
            tags,
        ):
            categories.append(
                "pediatric_clinic"
            )

    if amenity == "hospital":
        categories.append(
            "hospital"
        )

        if is_pediatric(
            name,
            tags,
        ):
            categories.append(
                "pediatric_clinic"
            )

    if amenity == "pharmacy":
        categories.append(
            "pharmacy"
        )

    if leisure == "park":
        categories.append(
            "park"
        )

    return categories


# ============================================================
# NEAREST
# ============================================================


def empty_surroundings():
    categories = [
        "supermarket",
        "convenience_store",
        "daycare",
        "elementary_school",
        "clinic",
        "pediatric_clinic",
        "hospital",
        "park",
        "pharmacy",
    ]

    return {
        category: {
            "name": None,

            "straight_line_distance_m":
                None,

            "walking_distance_m":
                None,

            "walking_minutes":
                None,

            "latitude":
                None,

            "longitude":
                None,

            "routing_source":
                None,
        }
        for category
        in categories
    }


def build_surroundings(
    origin_lat,
    origin_lon,
    elements,
):
    surroundings = (
        empty_surroundings()
    )

    for element in elements:
        latitude, longitude = (
            element_coordinates(
                element
            )
        )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        tags = element.get(
            "tags",
            {},
        )

        name = place_name(
            tags
        )

        straight_distance = (
            haversine_distance_m(
                origin_lat,
                origin_lon,
                latitude,
                longitude,
            )
        )

        categories = (
            classify_element(
                element
            )
        )

        for category in categories:
            current = surroundings[
                category
            ]

            current_distance = (
                current.get(
                    "straight_line_distance_m"
                )
            )

            if (
                current_distance is None
                or straight_distance
                < current_distance
            ):
                surroundings[
                    category
                ] = {
                    "name":
                        name,

                    "straight_line_distance_m":
                        straight_distance,

                    "latitude":
                        latitude,

                    "longitude":
                        longitude,
                }

    # Now calculate actual pedestrian routes
    # only for the nearest POI in each category.
    #
    # This keeps requests very low.

    for (
        category,
        item,
    ) in surroundings.items():

        latitude = item.get(
            "latitude"
        )

        longitude = item.get(
            "longitude"
        )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        route = walking_route(
            origin_lat,
            origin_lon,
            latitude,
            longitude,
        )

        if route:
            item[
                "walking_distance_m"
            ] = route.get(
                "distance_m"
            )

            item[
                "walking_minutes"
            ] = route.get(
                "walking_minutes"
            )

            item[
                "routing_source"
            ] = route.get(
                "routing_source"
            )

        else:
            item[
                "walking_distance_m"
            ] = None

            item[
                "walking_minutes"
            ] = None

    return surroundings


# ============================================================
# PUBLIC ENRICHMENT
# ============================================================


def enrich_surroundings(room):
    property_key = room.get(
        "property_key"
    )

    if not property_key:
        return room

    cache = load_cache()

    cached = cache.get(
        property_key
    )

    if cached:
        room[
            "coordinates"
        ] = cached.get(
            "coordinates"
        )

        room[
            "surroundings"
        ] = cached.get(
            "surroundings",
            {},
        )

        room[
            "surroundings_source"
        ] = (
            "OpenStreetMap"
        )

        room[
            "surroundings_distance_type"
        ] = (
            "straight_line"
        )

        return room

    geocode = geocode_room(
        room
    )

    if not geocode:
        room[
            "surroundings_error"
        ] = (
            "Could not geocode property"
        )

        return room

    latitude = geocode[
        "latitude"
    ]

    longitude = geocode[
        "longitude"
    ]

    try:
        elements = fetch_nearby_places(
            latitude,
            longitude,
        )

    except Exception as e:
        room[
            "surroundings_error"
        ] = str(e)

        return room

    surroundings = (
        build_surroundings(
            latitude,
            longitude,
            elements,
        )
    )

    coordinates = {
        "latitude":
            latitude,

        "longitude":
            longitude,

        "geocoded_name":
            geocode.get(
                "display_name"
            ),
    }

    cache[
        property_key
    ] = {
        "coordinates":
            coordinates,

        "surroundings":
            surroundings,
    }

    save_cache(
        cache
    )

    room[
        "coordinates"
    ] = coordinates

    room[
        "surroundings"
    ] = surroundings

    room[
        "surroundings_source"
    ] = (
        "OpenStreetMap"
    )

    room[
        "surroundings_attribution"
    ] = (
        "© OpenStreetMap contributors"
    )

    room[
        "surroundings_distance_type"
    ] = (
        "straight_line"
    )

    return room
