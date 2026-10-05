import html
import re
import time
import urllib.request


CACHE = {}


def build_property_url(room):
    shisya = room.get(
        "shisya"
    )

    danchi = room.get(
        "danchi"
    )

    shikibetu = room.get(
        "shikibetu"
    )

    if shikibetu is None:
        shikibetu = "0"

    if not shisya or not danchi:
        return None

    return (
        "https://www.ur-net.go.jp/"
        "chintai/kanto/kanagawa/"
        f"{shisya}_{danchi}{shikibetu}.html"
    )


def fetch_html(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120 Safari/537.36"
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
        },
    )

    last_error = None

    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:

                return (
                    response
                    .read()
                    .decode(
                        "utf-8",
                        errors="replace",
                    )
                )

        except Exception as e:
            last_error = e

            if attempt < 2:
                time.sleep(2)

    raise last_error


def html_to_text(raw_html):
    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        raw_html,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"</(?:td|th|tr|div|p|li|dt|dd|h[1-6])>",
        "\n",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    text = html.unescape(
        text
    )

    lines = []

    for line in text.splitlines():
        line = re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        if line:
            lines.append(
                line
            )

    return "\n".join(
        lines
    )


def find_value_after_label(
    text,
    label,
):
    lines = text.splitlines()

    for index, line in enumerate(
        lines
    ):
        if line == label:
            if (
                index + 1
                < len(lines)
            ):
                return lines[
                    index + 1
                ]

        if line.startswith(label):
            value = line[
                len(label):
            ].strip()

            if value:
                return value

    return None


def parse_age_range(value):
    if not value:
        return {
            "min": None,
            "max": None,
            "estimate": None,
        }

    numbers = [
        int(number)
        for number in re.findall(
            r"\d+",
            value,
        )
    ]

    if not numbers:
        return {
            "min": None,
            "max": None,
            "estimate": None,
        }

    if len(numbers) == 1:
        minimum = numbers[0]
        maximum = numbers[0]

    else:
        minimum = min(
            numbers
        )

        maximum = max(
            numbers
        )

    estimate = round(
        (
            minimum
            + maximum
        )
        / 2
    )

    return {
        "min":
            minimum,

        "max":
            maximum,

        "estimate":
            estimate,
    }


def normalize_structure(value):
    if not value:
        return None

    if (
        "鉄骨鉄筋コンクリート"
        in value
    ):
        return "SRC"

    if (
        "鉄筋コンクリート"
        in value
    ):
        return "RC"

    if "鉄骨" in value:
        return "STEEL"

    if "木造" in value:
        return "WOOD"

    return value


def parse_property_detail(
    raw_html,
):
    text = html_to_text(
        raw_html
    )

    structure_raw = (
        find_value_after_label(
            text,
            "構造",
        )
    )

    age_raw = (
        find_value_after_label(
            text,
            "管理年数",
        )
    )

    address = (
        find_value_after_label(
            text,
            "住所",
        )
    )

    ages = parse_age_range(
        age_raw
    )

    return {
        "structure":
            normalize_structure(
                structure_raw
            ),

        "structure_raw":
            structure_raw,

        "building_age_min_years":
            ages["min"],

        "building_age_max_years":
            ages["max"],

        "building_age_estimate_years":
            ages["estimate"],

        "management_age_raw":
            age_raw,

        "address":
            address,
    }


def fetch_property_detail(room):
    property_key = (
        f'{room.get("shisya")}_'
        f'{room.get("danchi")}'
    )

    if property_key in CACHE:
        return CACHE[
            property_key
        ]

    url = build_property_url(
        room
    )

    if not url:
        return {}

    raw_html = fetch_html(
        url
    )

    detail = parse_property_detail(
        raw_html
    )

    detail[
        "property_url"
    ] = url

    CACHE[
        property_key
    ] = detail

    return detail


def enrich_ur_property(room):
    if room.get(
        "source"
    ) != "ur":
        return room

    try:
        detail = (
            fetch_property_detail(
                room
            )
        )

    except Exception as e:
        room[
            "property_enrichment_error"
        ] = str(e)

        return room

    for key, value in (
        detail.items()
    ):
        if value is not None:
            room[key] = value

    return room