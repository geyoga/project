import json
import re
import sys

from pathlib import Path


BASE_DIR = Path(
    "/workspace/apartment-agent"
)

CONFIG_PATH = (
    BASE_DIR
    / "config"
    / "search_profile.json"
)

PROPERTY_METADATA_PATH = (
    BASE_DIR
    / "data"
    / "property_metadata.json"
)


sys.path.insert(
    0,
    str(BASE_DIR),
)


from crawlers.ur import crawl_area
from services.commute import enrich_commute
from services.ur_property import (
    enrich_ur_property,
)
from services.surroundings import (
    enrich_surroundings,
)


# ============================================================
# LOADERS
# ============================================================


def load_profile():
    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def load_property_metadata():
    if not (
        PROPERTY_METADATA_PATH
        .exists()
    ):
        return {}

    with open(
        PROPERTY_METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================
# BASIC PARSING
# ============================================================


def parse_floor_number(floor):
    if not floor:
        return None

    match = re.search(
        r"(\d+)",
        str(floor),
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


def layout_score(layout):
    if not layout:
        return 0

    scores = {
        "1LDK": 1,
        "2DK": 2,
        "2LDK": 3,
        "3DK": 4,
        "3LDK": 5,
        "4DK": 6,
        "4LDK": 7,
    }

    return scores.get(
        layout,
        0,
    )


# ============================================================
# METADATA ENRICHMENT
# ============================================================
def score_orientation(room):
    orientation = room.get(
        "orientation"
    )

    if orientation is None:
        return 50

    scores = {
        "south": 100,
        "east": 80,
        "west": 60,
        "north": 40,
    }

    return scores.get(
        orientation,
        50,
    )

def score_elevator(room):
    elevator = room.get(
        "elevator"
    )

    floor = room.get(
        "floor_number"
    )

    if elevator is None:
        return 50

    if floor is None:
        return (
            75
            if elevator
            else 50
        )

    if floor <= 3:
        return (
            75
            if elevator
            else 65
        )

    if floor >= 4:
        return (
            100
            if elevator
            else 20
        )

    return 50

def score_bike_parking(room):
    value = room.get(
        "bike_parking"
    )

    if value is True:
        return 100

    if value is False:
        return 30

    return 50

def score_gas(room):
    gas_type = room.get(
        "gas_type"
    )

    if gas_type is None:
        return 50

    scores = {
        "city_gas": 100,
        "all_electric": 85,
        "propane": 40,
    }

    return scores.get(
        gas_type,
        50,
    )

def use_metadata_if_missing(
    room,
    key,
    metadata_value,
):
    if (
        room.get(key) is None
        and metadata_value
        is not None
    ):
        room[key] = (
            metadata_value
        )

def enrich_room(
    room,
    metadata,
):
    property_key = (
        f'{room.get("shisya")}_'
        f'{room.get("danchi")}'
    )

    property_data = metadata.get(
        property_key,
        {},
    )

    room[
        "property_key"
    ] = property_key

    room[
        "primary_station"
    ] = property_data.get(
        "primary_station"
    )

    room[
        "access_type"
    ] = property_data.get(
        "access_type"
    )

    room[
        "bus_minutes"
    ] = property_data.get(
        "bus_minutes"
    )

    room[
        "station_walk_minutes"
    ] = property_data.get(
        "walk_minutes"
    )

    room[
        "train_line"
    ] = property_data.get(
        "train_line"
    )

    use_metadata_if_missing(
        room,
        "orientation",
        property_data.get(
            "orientation"
        ),
    )

    use_metadata_if_missing(
        room,
        "elevator",
        property_data.get(
            "elevator"
        ),
    )

    use_metadata_if_missing(
        room,
        "balcony",
        property_data.get(
            "balcony"
        ),
    )

    use_metadata_if_missing(
        room,
        "bath_toilet_separate",
        property_data.get(
            "bath_toilet_separate"
        ),
    )

    use_metadata_if_missing(
        room,
        "washing_machine_inside",
        property_data.get(
            "washing_machine_inside"
        ),
    )

    use_metadata_if_missing(
        room,
        "bidet",
        property_data.get(
            "bidet"
        ),
    )

    use_metadata_if_missing(
        room,
        "gas_type",
        property_data.get(
            "gas_type"
        ),
    )

    use_metadata_if_missing(
        room,
        "bike_parking",
        property_data.get(
            "bike_parking"
        ),
    )

    room[
        "surroundings"
    ] = property_data.get(
        "surroundings",
        {},
    )

    room[
        "floor_number"
    ] = parse_floor_number(
        room.get(
            "floor"
        )
    )

    if not room.get(
        "storage"
    ):
        room["storage"] = (
            property_data.get(
                "storage"
            )
            or {}
        )

    return room


# ============================================================
# FOREIGNER FRIENDLINESS
# ============================================================


def enrich_foreigner_friendly(
    room,
):
    source = room.get(
        "source"
    )

    if source == "ur":
        room[
            "foreigner_friendly"
        ] = {
            "score": 100,

            "status": "high",

            "evidence": [
                (
                    "foreign_nationals_"
                    "explicitly_accepted"
                ),
                (
                    "no_guarantor_"
                    "required"
                ),
                (
                    "english_guidance_"
                    "available"
                ),
            ],

            "notes": (
                "Applicant still needs "
                "to satisfy applicable "
                "UR residence-status "
                "and income requirements."
            ),
        }

        return room

    room[
        "foreigner_friendly"
    ] = {
        "score": 40,

        "status": "unknown",

        "evidence": [],

        "notes": (
            "Foreigner acceptance "
            "has not been verified."
        ),
    }

    return room


# ============================================================
# INITIAL COST
# ============================================================


def estimate_ur_initial_cost(
    room,
    profile,
):
    rent = room.get(
        "rent"
    )

    management_fee = (
        room.get(
            "management_fee"
        )
        or 0
    )

    if rent is None:
        return None

    monthly_total = (
        rent
        + management_fee
    )

    config = profile.get(
        "initial_cost",
        {},
    )

    proration_ratio = config.get(
        "ur_move_in_proration_ratio",
        0.5,
    )

    deposit = (
        rent
        * 2
    )

    key_money = 0
    agency_fee = 0
    guarantor_fee = 0

    estimated_prorated = round(
        monthly_total
        * proration_ratio
    )

    estimated_total = (
        deposit
        + estimated_prorated
    )

    estimated_min = round(
        deposit
        + (
            monthly_total
            / 30
        )
    )

    estimated_max = (
        deposit
        + monthly_total
    )

    return {
        "deposit":
            deposit,

        "deposit_months":
            2,

        "key_money":
            key_money,

        "agency_fee":
            agency_fee,

        "guarantor_fee":
            guarantor_fee,

        "estimated_prorated_rent_and_fee":
            estimated_prorated,

        "estimated_total":
            estimated_total,

        "estimated_min":
            estimated_min,

        "estimated_max":
            estimated_max,

        "currency":
            "JPY",

        "estimate_only":
            True,
    }


def enrich_initial_cost(
    room,
    profile,
):
    if (
        room.get("source")
        == "ur"
    ):
        room[
            "initial_cost"
        ] = estimate_ur_initial_cost(
            room,
            profile,
        )

    else:
        room[
            "initial_cost"
        ] = None

    return room


# ============================================================
# HARD FILTERS
# ============================================================


def passes_hard_filters(
    room,
    profile,
):
    reasons = []

    monthly_total = room.get(
        "monthly_total"
    )

    area = room.get(
        "area_m2"
    )

    layout = room.get(
        "layout"
    )

    station_walk = room.get(
        "station_walk_minutes"
    )

    commute = room.get(
        "total_commute_minutes"
    )

    # Budget

    if monthly_total is None:
        reasons.append(
            "monthly total missing"
        )

    elif (
        monthly_total
        > profile[
            "absolute_monthly_max"
        ]
    ):
        reasons.append(
            f"monthly_total "
            f"{monthly_total} > "
            f'{profile["absolute_monthly_max"]}'
        )

    # Area

    if area is None:
        reasons.append(
            "area missing"
        )

    elif (
        area
        < profile[
            "minimum_area_m2"
        ]
    ):
        reasons.append(
            f"area {area} < "
            f'{profile["minimum_area_m2"]}'
        )

    # Layout

    minimum_layout = (
        layout_score(
            profile[
                "minimum_layout"
            ]
        )
    )

    if (
        layout_score(
            layout
        )
        < minimum_layout
    ):
        reasons.append(
            f"layout {layout} below "
            f'{profile["minimum_layout"]}'
        )

    # Walk to station

    if (
        station_walk is not None
        and station_walk
        > profile[
            "maximum_station_walk_minutes"
        ]
    ):
        reasons.append(
            f"walk "
            f"{station_walk} > "
            f'{profile["maximum_station_walk_minutes"]}'
        )

    # Commute

    if (
        commute is not None
        and commute
        > profile[
            "maximum_commute_minutes"
        ]
    ):
        reasons.append(
            f"commute "
            f"{commute} > "
            f'{profile["maximum_commute_minutes"]}'
        )

    if reasons:
        print(
            f'REJECTED: '
            f'{room.get("property")} '
            f'{room.get("room")} -> '
            + ", ".join(
                reasons
            ),
            file=sys.stderr,
        )

        return False

    return True


# ============================================================
# SCORE: BUDGET
# ============================================================


def score_budget(
    room,
    profile,
):
    monthly_total = room.get(
        "monthly_total"
    )

    if monthly_total is None:
        return 0

    preferred = profile[
        "preferred_monthly_max"
    ]

    absolute = profile[
        "absolute_monthly_max"
    ]

    if monthly_total <= preferred:
        bonus = min(
            25,
            (
                preferred
                - monthly_total
            )
            / 1000,
        )

        return min(
            100,
            75 + bonus,
        )

    if monthly_total >= absolute:
        return 20

    difference = (
        monthly_total
        - preferred
    )

    range_size = (
        absolute
        - preferred
    )

    ratio = (
        difference
        / range_size
    )

    return max(
        20,
        75
        - (
            ratio
            * 55
        ),
    )


# ============================================================
# SCORE: COMMUTE
# ============================================================


def score_commute(room):
    commute = room.get(
        "total_commute_minutes"
    )

    if commute is None:
        return 45

    if commute <= 30:
        score = 100

    elif commute <= 35:
        score = 95

    elif commute <= 40:
        score = 88

    elif commute <= 45:
        score = 80

    elif commute <= 50:
        score = 70

    elif commute <= 55:
        score = 60

    elif commute <= 60:
        score = 45

    else:
        score = 10

    transfers = room.get(
        "transfers"
    )

    if transfers == 0:
        score += 5

    elif transfers == 1:
        score -= 5

    elif (
        transfers is not None
        and transfers >= 2
    ):
        score -= 15

    if (
        room.get(
            "access_type"
        )
        == "bus"
    ):
        score -= 5

    return max(
        0,
        min(
            score,
            100,
        ),
    )


# ============================================================
# SCORE: SPACE
# ============================================================


def score_space(
    room,
    profile,
):
    area = room.get(
        "area_m2"
    )

    if area is None:
        return 0

    minimum = profile[
        "minimum_area_m2"
    ]

    if area < minimum:
        return 0

    score = (
        60
        + (
            area
            - minimum
        )
        * 1.5
    )

    return min(
        100,
        score,
    )


# ============================================================
# SCORE: LAYOUT
# ============================================================


def score_layout(room):
    layout = room.get(
        "layout"
    )

    scores = {
        "1LDK": 55,
        "2DK": 70,
        "2LDK": 90,
        "3DK": 90,
        "3LDK": 100,
        "4DK": 95,
        "4LDK": 95,
    }

    return scores.get(
        layout,
        40,
    )


# ============================================================
# SCORE: FLOOR
#
# Preference:
#
# 2F > 3F > 1F > 4F+
# ============================================================


def score_floor(room):
    floor = room.get(
        "floor_number"
    )

    if floor is None:
        return 50

    if floor == 2:
        return 100

    if floor == 3:
        return 85

    if floor == 1:
        return 70

    if floor == 4:
        return 55

    if floor == 5:
        return 45

    if floor >= 6:
        return 40

    return 50


# ============================================================
# SCORE: BUILDING AGE
# ============================================================


def score_building_age(
    room,
    profile,
):
    age = room.get(
        "building_age_estimate_years"
    )

    if age is None:
        return 50

    if age <= 5:
        return 100

    if age <= 10:
        return 95

    if age <= 15:
        return 88

    if age <= 20:
        return 80

    if age <= 25:
        return 65

    if age <= 30:
        return 55

    if age <= 40:
        return 35

    return 20


# ============================================================
# SCORE: STRUCTURE
# ============================================================


def score_structure(room):
    structure = room.get(
        "structure"
    )

    if not structure:
        return 50

    normalized = (
        str(structure)
        .upper()
        .strip()
    )

    if (
        "SRC"
        in normalized
    ):
        return 100

    if (
        "RC"
        in normalized
    ):
        return 95

    if (
        "STEEL"
        in normalized
    ):
        return 65

    if (
        "WOOD"
        in normalized
    ):
        return 25

    return 50


# ============================================================
# SCORE: SURROUNDINGS
# ============================================================


def distance_score(
    distance,
    excellent,
    good,
    acceptable,
):
    if distance is None:
        return None

    if distance <= excellent:
        return 100

    if distance <= good:
        return 80

    if distance <= acceptable:
        return 55

    return 25


def walking_time_score(
    minutes,
    excellent,
    good,
    acceptable,
):
    if minutes is None:
        return None

    if minutes <= excellent:
        return 100

    if minutes <= good:
        return 80

    if minutes <= acceptable:
        return 55

    return 25


def score_surroundings(room):
    surroundings = room.get(
        "surroundings"
    )

    if not surroundings:
        return 50

    definitions = {
        "supermarket": {
            "minutes": (
                5,
                10,
                15,
            ),
            "weight": 2.0,
        },

        "convenience_store": {
            "minutes": (
                3,
                6,
                10,
            ),
            "weight": 0.5,
        },

        "daycare": {
            "minutes": (
                5,
                10,
                15,
            ),
            "weight": 2.0,
        },

        "elementary_school": {
            "minutes": (
                8,
                12,
                20,
            ),
            "weight": 0.8,
        },

        "clinic": {
            "minutes": (
                8,
                12,
                20,
            ),
            "weight": 1.0,
        },

        "pediatric_clinic": {
            "minutes": (
                8,
                12,
                20,
            ),
            "weight": 2.0,
        },

        "hospital": {
            "minutes": (
                15,
                25,
                35,
            ),
            "weight": 1.0,
        },

        "park": {
            "minutes": (
                5,
                10,
                15,
            ),
            "weight": 1.2,
        },

        "pharmacy": {
            "minutes": (
                5,
                10,
                15,
            ),
            "weight": 0.8,
        },
    }

    weighted_total = 0
    total_weight = 0

    for (
        category,
        config,
    ) in definitions.items():

        item = surroundings.get(
            category,
            {},
        )

        if not isinstance(
            item,
            dict,
        ):
            continue

        walking_minutes = item.get(
            "walking_minutes"
        )

        result = walking_time_score(
            walking_minutes,
            *config[
                "minutes"
            ],
        )

        if result is None:
            continue

        weight = config[
            "weight"
        ]

        weighted_total += (
            result
            * weight
        )

        total_weight += weight

    if total_weight == 0:
        return 50

    return (
        weighted_total
        / total_weight
    )


# ============================================================
# SCORE: INITIAL COST
# ============================================================


def score_initial_cost(room):
    initial_cost = room.get(
        "initial_cost"
    )

    if not initial_cost:
        return 50

    total = initial_cost.get(
        "estimated_total"
    )

    if total is None:
        return 50

    if total <= 200000:
        return 100

    if total <= 250000:
        return 90

    if total <= 300000:
        return 80

    if total <= 350000:
        return 70

    if total <= 400000:
        return 60

    if total <= 500000:
        return 40

    return 20


# ============================================================
# SCORE: FOREIGNER FRIENDLY
# ============================================================


def score_foreigner_friendly(
    room,
):
    data = room.get(
        "foreigner_friendly"
    )

    if not data:
        return 40

    return data.get(
        "score",
        40,
    )

# ============================================================
# SCORE: FACILITIES
# ============================================================


def score_facilities(room):
    score = 50

    # Bath and toilet separated
    if (
        room.get(
            "bath_toilet_separate"
        )
        is True
    ):
        score += 8

    # Heated bidet / washlet
    if (
        room.get(
            "bidet"
        )
        is True
    ):
        score += 8

    # Indoor washing machine space
    if (
        room.get(
            "washing_machine_inside"
        )
        is True
    ):
        score += 7

    # Balcony
    if (
        room.get(
            "balcony"
        )
        is True
    ):
        score += 4

    # Storage
    storage = (
        room.get(
            "storage"
        )
        or {}
    )

    if (
        storage.get(
            "available"
        )
        is True
    ):
        score += 5

    if (
        storage.get(
            "walk_in_closet"
        )
        is True
    ):
        score += 3

    # Independent washbasin
    if (
        room.get(
            "independent_washbasin"
        )
        is True
    ):
        score += 5

    # Air conditioner
    if (
        room.get(
            "air_conditioner"
        )
        is True
    ):
        score += 3

    # Bathroom dryer
    if (
        room.get(
            "bathroom_dryer"
        )
        is True
    ):
        score += 3

    # Bath reheating
    if (
        room.get(
            "reheating_bath"
        )
        is True
    ):
        score += 2

    # Monitor intercom
    if (
        room.get(
            "monitor_intercom"
        )
        is True
    ):
        score += 2

    # Internet
    if (
        room.get(
            "internet_available"
        )
        is True
    ):
        score += 2

    # Fiber connection
    if (
        room.get(
            "ftth"
        )
        is True
    ):
        score += 2

    return min(
        score,
        100,
    )


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_score(
    room,
    profile,
):
    components = {
        "budget": score_budget(
            room,
            profile,
        ),

        "commute": score_commute(
            room
        ),

        "space": score_space(
            room,
            profile,
        ),

        "layout": score_layout(
            room
        ),

        "floor": score_floor(
            room
        ),

        "building_age": score_building_age(
            room,
            profile,
        ),

        "structure": score_structure(
            room
        ),

        "facilities": score_facilities(
            room
        ),

        "orientation": score_orientation(
            room
        ),

        "elevator": score_elevator(
            room
        ),

        "bike_parking": score_bike_parking(
            room
        ),

        "gas": score_gas(
            room
        ),

        "surroundings": score_surroundings(
            room
        ),

        "initial_cost": score_initial_cost(
            room
        ),

        "foreigner_friendly":
            score_foreigner_friendly(
                room
            ),
    }

    weights = {
        "budget": 0.15,
        "commute": 0.18,

        "space": 0.07,
        "layout": 0.06,
        "floor": 0.06,

        "building_age": 0.09,
        "structure": 0.05,

        "facilities": 0.08,
        "orientation": 0.03,
        "elevator": 0.03,
        "bike_parking": 0.02,
        "gas": 0.02,

        "surroundings": 0.07,

        "initial_cost": 0.04,

        "foreigner_friendly": 0.05,
    }

    total = 0

    for key, value in components.items():
        total += (
            value
            * weights[key]
        )

    room[
        "score_breakdown"
    ] = {
        key: round(
            value,
            1,
        )
        for key, value
        in components.items()
    }

    return round(
        total,
        1,
    )


# ============================================================
# MAIN
# ============================================================


def main():
    profile = load_profile()

    property_metadata = (
        load_property_metadata()
    )

    area_codes = profile.get(
        "ur_area_codes",
        [],
    )

    if not area_codes:
        print(
            json.dumps(
                {
                    "error":
                        "No UR area codes configured",

                    "detail":
                        "Add ur_area_codes to "
                        "config/search_profile.json",
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return

    all_rooms = []
    crawl_errors = []

    # --------------------------------------------------------
    # Crawl
    # --------------------------------------------------------

    for area_code in area_codes:
        try:
            rooms = crawl_area(
                area_code
            )

            all_rooms.extend(
                rooms
            )

        except Exception as e:
            crawl_errors.append(
                {
                    "area_code":
                        area_code,

                    "error":
                        str(e),
                }
            )

    # --------------------------------------------------------
    # Enrich + filter + rank
    # --------------------------------------------------------

    matches = []

    for room in all_rooms:
        room = enrich_room(
            room,
            property_metadata,
        )

        room = enrich_ur_property(
            room
        )

        room = enrich_surroundings(
            room
        )

        room = enrich_commute(
            room,
            profile[
                "destination"
            ],
        )

        room = enrich_initial_cost(
            room,
            profile,
        )

        room = (
            enrich_foreigner_friendly(
                room
            )
        )

        if not passes_hard_filters(
            room,
            profile,
        ):
            continue

        room[
            "score"
        ] = calculate_score(
            room,
            profile,
        )

        matches.append(
            room
        )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    matches.sort(
        key=lambda x: (
            -x["score"],
            x["monthly_total"],
            -x["area_m2"],
        )
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    output = {
        "profile":
            profile,

        "stats": {
            "areas_requested":
                len(area_codes),

            "areas_failed":
                len(crawl_errors),

            "rooms_found":
                len(all_rooms),

            "rooms_matching":
                len(matches),
        },

        "crawl_errors":
            crawl_errors,

        "matches":
            matches,
    }

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()