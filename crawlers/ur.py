import html
import json
import re
import time
import urllib.parse
import urllib.request
from services.facilities import (
    extract_facilities,
)


API_URL = (
    "https://chintai.r6.ur-net.go.jp/"
    "chintai/api/bukken/result/"
    "bukken_result/"
)


def parse_yen(value):
    if value is None:
        return None

    value = html.unescape(str(value))

    digits = re.sub(
        r"[^\d]",
        "",
        value,
    )

    if not digits:
        return None

    return int(digits)


def parse_area(value):
    if value is None:
        return None

    value = html.unescape(str(value))

    match = re.search(
        r"(\d+(?:\.\d+)?)",
        value,
    )

    if not match:
        return None

    return float(
        match.group(1)
    )


def build_source_url(property_data):
    shisya = property_data.get(
        "shisya"
    )

    danchi = property_data.get(
        "danchi"
    )

    shikibetu = property_data.get(
        "shikibetu"
    )

    if shikibetu is None:
        shikibetu = "0"

    if not shisya or not danchi:
        return None

    return (
        "https://www.ur-net.go.jp/"
        "chintai/sp/kanto/kanagawa/"
        f"{shisya}_{danchi}{shikibetu}"
        "_room.html"
    )


def fetch_area(
    area_code,
    prefecture_code="14",
):
    payload = {
        "mode": "area",
        "skcs": str(area_code),
        "block": "kanto",
        "tdfk": str(prefecture_code),
        "rireki_tdfk": str(
            prefecture_code
        ),
        "orderByField": "0",
        "pageSize": "100",
        "pageIndex": "0",
        "shisya": "",
        "danchi": "",
        "shikibetu": "",
        "pageIndexRoom": "0",
        "sp": "",
    }

    body = urllib.parse.urlencode(
        payload
    ).encode(
        "utf-8"
    )

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120 Safari/537.36"
            ),
            "Content-Type": (
                "application/"
                "x-www-form-urlencoded; "
                "charset=UTF-8"
            ),
            "Accept": (
                "application/json, "
                "text/javascript, "
                "*/*; q=0.01"
            ),
            "Origin": (
                "https://www.ur-net.go.jp"
            ),
            "Referer": (
                "https://www.ur-net.go.jp/"
                "chintai/kanto/kanagawa/"
                f"area/{area_code}.html"
            ),
            "X-Requested-With": (
                "XMLHttpRequest"
            ),
        },
        method="POST",
    )

    last_error = None

    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                request,
                timeout=45,
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

        except Exception as e:
            last_error = e

            if attempt < 2:
                time.sleep(2)

    raise last_error


def extract_properties(response):
    if isinstance(
        response,
        list,
    ):
        return response

    if not isinstance(
        response,
        dict,
    ):
        return []

    possible_keys = [
        "result",
        "data",
        "bukken",
        "properties",
    ]

    for key in possible_keys:
        value = response.get(key)

        if isinstance(
            value,
            list,
        ):
            return value

    for value in response.values():
        if (
            isinstance(
                value,
                list,
            )
            and value
            and isinstance(
                value[0],
                dict,
            )
        ):
            return value

    return []


def normalize_room(
    property_data,
    room,
):
    rent = parse_yen(
        room.get("rent")
        or room.get(
            "rent_normal"
        )
    )

    management_fee = (
        parse_yen(
            room.get(
                "commonfee"
            )
        )
        or 0
    )

    monthly_total = None

    if rent is not None:
        monthly_total = (
            rent
            + management_fee
        )

    room_name_parts = [
        room.get(
            "roomNmMain"
        ),
        room.get(
            "roomNmSub"
        ),
    ]

    room_name = " ".join(
        str(part)
        for part
        in room_name_parts
        if part
    )

    facilities = extract_facilities(
        property_data,
        room,
    )

    return {
        "source":
            "ur",

        "source_url":
            build_source_url(
                property_data
            ),

        "property":
            property_data.get(
                "danchiNm"
            ),

        "room":
            room_name,

        "rent":
            rent,

        "management_fee":
            management_fee,

        "monthly_total":
            monthly_total,

        "layout":
            room.get(
                "type"
            ),

        "area_m2":
            parse_area(
                room.get(
                    "floorspace"
                )
            ),

        "floor":
            room.get(
                "floor"
            ),

        "shisya":
            property_data.get(
                "shisya"
            ),

        "danchi":
            property_data.get(
                "danchi"
            ),

        "shikibetu":
            property_data.get(
                "shikibetu"
            ),

        # ------------------------------------
        # Facilities detected from UR payload
        # ------------------------------------

        "orientation":
            facilities.get(
                "orientation"
            ),

        "elevator":
            facilities.get(
                "elevator"
            ),

        "balcony":
            facilities.get(
                "balcony"
            ),

        "storage":
            facilities.get(
                "storage"
            ),

        "bath_toilet_separate":
            facilities.get(
                "bath_toilet_separate"
            ),

        "washing_machine_inside":
            facilities.get(
                "washing_machine_inside"
            ),

        "bidet":
            facilities.get(
                "bidet"
            ),

        "air_conditioner":
            facilities.get(
                "air_conditioner"
            ),

        "bike_parking":
            facilities.get(
                "bike_parking"
            ),

        "bathroom_dryer":
            facilities.get(
                "bathroom_dryer"
            ),

        "reheating_bath":
            facilities.get(
                "reheating_bath"
            ),

        "independent_washbasin":
            facilities.get(
                "independent_washbasin"
            ),

        "monitor_intercom":
            facilities.get(
                "monitor_intercom"
            ),

        "delivery_box":
            facilities.get(
                "delivery_box"
            ),

        "gas_type":
            facilities.get(
                "gas_type"
            ),

        "internet_type":
            facilities.get(
                "internet_type"
            ),

        "internet_available":
            facilities.get(
                "internet_available"
            ),

        "ftth":
            facilities.get(
                "ftth"
            ),

        "facility_detection":
            {
                "source":
                    facilities.get(
                        "source"
                    ),

                "confidence":
                    facilities.get(
                        "confidence"
                    ),
            },
    }


def crawl_area(area_code):
    response = fetch_area(
        area_code
    )

    properties = extract_properties(
        response
    )

    rooms = []

    for property_data in properties:
        property_rooms = (
            property_data.get(
                "room"
            )
            or []
        )

        if not isinstance(
            property_rooms,
            list,
        ):
            continue

        for room in property_rooms:
            normalized = normalize_room(
                property_data,
                room,
            )

            normalized[
                "area_code"
            ] = str(
                area_code
            )

            rooms.append(
                normalized
            )

    return rooms