import re


TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "y",
    "あり",
    "有",
    "有り",
    "○",
}


FALSE_VALUES = {
    "0",
    "false",
    "no",
    "n",
    "なし",
    "無",
    "無し",
    "×",
}


def normalize_text(value):
    if value is None:
        return ""

    return str(value).strip()


def flatten_data(
    value,
    prefix="",
):
    """
    Convert nested dictionaries/lists into searchable
    key/value text without assuming UR's exact schema.
    """

    items = []

    if isinstance(value, dict):
        for key, child in value.items():
            path = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            items.extend(
                flatten_data(
                    child,
                    path,
                )
            )

    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = (
                f"{prefix}[{index}]"
            )

            items.extend(
                flatten_data(
                    child,
                    path,
                )
            )

    else:
        items.append(
            (
                prefix,
                normalize_text(value),
            )
        )

    return items


def make_search_text(
    property_data,
    room_data,
):
    """
    Create text used only for positive feature detection.
    """

    flattened = (
        flatten_data(
            property_data,
            "property",
        )
        + flatten_data(
            room_data,
            "room",
        )
    )

    text = "\n".join(
        f"{key}={value}"
        for key, value
        in flattened
    )

    return text


def contains_any(
    text,
    keywords,
):
    return any(
        keyword in text
        for keyword in keywords
    )


def detect_boolean(
    text,
    positive_keywords,
):
    """
    Conservative detection.

    Returns:
        True  -> explicitly detected
        None  -> not enough evidence

    We intentionally don't return False simply
    because a keyword was absent.
    """

    if contains_any(
        text,
        positive_keywords,
    ):
        return True

    return None


def detect_orientation(text):
    patterns = [
        (
            "south",
            [
                "南向き",
                "南向",
                "南面",
            ],
        ),
        (
            "east",
            [
                "東向き",
                "東向",
                "東面",
            ],
        ),
        (
            "west",
            [
                "西向き",
                "西向",
                "西面",
            ],
        ),
        (
            "north",
            [
                "北向き",
                "北向",
                "北面",
            ],
        ),
    ]

    for orientation, keywords in patterns:
        if contains_any(
            text,
            keywords,
        ):
            return orientation

    return None


def detect_gas_type(text):
    if contains_any(
        text,
        [
            "都市ガス",
            "city gas",
        ],
    ):
        return "city_gas"

    if contains_any(
        text,
        [
            "プロパン",
            "LPガス",
            "ＬＰガス",
            "lpg",
        ],
    ):
        return "propane"

    if contains_any(
        text,
        [
            "オール電化",
            "all electric",
        ],
    ):
        return "all_electric"

    return None


def detect_internet_type(text):
    if contains_any(
        text,
        [
            "光配線",
            "FTTH",
            "ftth",
        ],
    ):
        return "ftth"

    if contains_any(
        text,
        [
            "VDSL",
            "vdsl",
        ],
    ):
        return "vdsl"

    if contains_any(
        text,
        [
            "住棟内LAN",
            "LAN方式",
        ],
    ):
        return "lan"

    if contains_any(
        text,
        [
            "CATVインターネット",
            "CATV",
        ],
    ):
        return "catv"

    if contains_any(
        text,
        [
            "インターネット接続可",
            "インターネット対応",
        ],
    ):
        return "available"

    return None


def detect_storage(text):
    storage = {
        "available": None,
        "walk_in_closet": None,
        "shoe_box": None,
        "shoe_walk_in_closet": None,
        "trunk_room": None,
        "oshiire": None,
    }

    storage[
        "walk_in_closet"
    ] = detect_boolean(
        text,
        [
            "ウォークインクローゼット",
            "WIC",
        ],
    )

    storage[
        "shoe_walk_in_closet"
    ] = detect_boolean(
        text,
        [
            "シューズウォークインクローゼット",
            "SIC",
        ],
    )

    storage[
        "shoe_box"
    ] = detect_boolean(
        text,
        [
            "シューズボックス",
            "玄関収納",
        ],
    )

    storage[
        "trunk_room"
    ] = detect_boolean(
        text,
        [
            "トランクルーム",
        ],
    )

    storage[
        "oshiire"
    ] = detect_boolean(
        text,
        [
            "押入",
            "押し入れ",
        ],
    )

    generic_storage = detect_boolean(
        text,
        [
            "全居室収納",
            "収納（物入）",
            "収納あり",
            "収納有",
        ],
    )

    positive_values = [
        generic_storage,
        storage["walk_in_closet"],
        storage["shoe_box"],
        storage[
            "shoe_walk_in_closet"
        ],
        storage["trunk_room"],
        storage["oshiire"],
    ]

    if any(
        value is True
        for value
        in positive_values
    ):
        storage[
            "available"
        ] = True

    return storage


def extract_facilities(
    property_data,
    room_data,
):
    text = make_search_text(
        property_data,
        room_data,
    )

    storage = detect_storage(
        text
    )

    internet_type = (
        detect_internet_type(
            text
        )
    )

    facilities = {
        "orientation":
            detect_orientation(
                text
            ),

        "elevator":
            detect_boolean(
                text,
                [
                    "エレベーター",
                ],
            ),

        "balcony":
            detect_boolean(
                text,
                [
                    "バルコニー",
                    "ベランダ",
                ],
            ),

        "storage":
            storage,

        "bath_toilet_separate":
            detect_boolean(
                text,
                [
                    "バス・トイレ別",
                    "バストイレ別",
                    "浴室・トイレ別",
                ],
            ),

        "washing_machine_inside":
            detect_boolean(
                text,
                [
                    "洗濯機置場（室内）",
                    "洗濯機置場(室内)",
                    "室内洗濯機置場",
                    "室内洗濯機置き場",
                ],
            ),

        # Heated bidet / washlet
        "bidet":
            detect_boolean(
                text,
                [
                    "温水洗浄便座",
                    "ウォシュレット",
                    "洗浄便座",
                ],
            ),

        "air_conditioner":
            detect_boolean(
                text,
                [
                    "エアコン",
                ],
            ),

        "bike_parking":
            detect_boolean(
                text,
                [
                    "駐輪場",
                    "自転車置場",
                    "自転車置き場",
                ],
            ),

        "bathroom_dryer":
            detect_boolean(
                text,
                [
                    "浴室換気乾燥機",
                    "浴室乾燥機",
                ],
            ),

        "reheating_bath":
            detect_boolean(
                text,
                [
                    "追い焚き",
                    "追焚",
                ],
            ),

        "independent_washbasin":
            detect_boolean(
                text,
                [
                    "洗面所独立",
                    "独立洗面",
                    "洗面化粧台",
                ],
            ),

        "monitor_intercom":
            detect_boolean(
                text,
                [
                    "モニター付きインターホン",
                    "モニター付インターホン",
                    "モニター付ドアホン",
                ],
            ),

        "delivery_box":
            detect_boolean(
                text,
                [
                    "宅配ボックス",
                ],
            ),

        "gas_type":
            detect_gas_type(
                text
            ),

        "internet_type":
            internet_type,

        "internet_available":
            (
                True
                if internet_type
                is not None
                else None
            ),

        "ftth":
            (
                True
                if internet_type
                == "ftth"
                else None
            ),

        "source":
            "ur_api",

        "confidence":
            "explicit_only",
    }

    return facilities
