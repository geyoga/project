import re
import sys
import time

from bs4 import BeautifulSoup

from services.facilities import (
    extract_facilities,
)

USER_AGENT = (
    "Mozilla/5.0 "
    "(Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/136.0 Safari/537.36"
)

max_retries=4
base_delay_seconds=3

from playwright.sync_api import (
    sync_playwright,
)

def fetch_page(
    url,
    max_retries=3,
):
    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                )

                page = browser.new_page(
                    viewport={
                        "width": 1440,
                        "height": 1000,
                    },
                    locale="ja-JP",
                )

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=45000,
                )

                status = (
                    response.status
                    if response
                    else None
                )

                if status == 503:
                    browser.close()

                    raise RuntimeError(
                        "SUUMO returned HTTP 503"
                    )

                page.wait_for_timeout(
                    2000
                )

                html = page.content()

                browser.close()

                return html

        except Exception as e:
            last_error = e

            if attempt >= max_retries:
                break

            delay = (
                3
                * (2 ** (attempt - 1))
            )

            print(
                (
                    "SUUMO browser fetch failed. "
                    f"Retry {attempt}/"
                    f"{max_retries} "
                    f"in {delay}s: {e}"
                ),
                file=sys.stderr,
            )

            time.sleep(delay)

    raise RuntimeError(
        (
            "SUUMO browser fetch failed after "
            f"{max_retries} attempts: "
            f"{last_error}"
        )
    )

def parse_yen(value):
    if not value:
        return None

    value = value.strip()

    if value == "-":
        return 0

    match = re.search(
        r"([\d.]+)\s*万円",
        value,
    )

    if match:
        return int(
            float(match.group(1))
            * 10000
        )

    match = re.search(
        r"([\d,]+)\s*円",
        value,
    )

    if match:
        return int(
            match.group(1)
            .replace(",", "")
        )

    return None


def extract_listing_id(url):
    match = re.search(
        r"jnc_(\d+)",
        url,
    )

    if not match:
        return None

    return match.group(1)


def normalize_text(soup):
    return re.sub(
        r"\s+",
        " ",
        soup.get_text(
            " ",
            strip=True,
        ),
    )


def search(pattern, text):
    match = re.search(
        pattern,
        text,
    )

    if not match:
        return None

    return match.group(1).strip()


def parse_primary_station(text):
    match = re.search(
        r"([^/\s]+(?:線|ライン))/"
        r"([^/\s]+?)駅\s*歩(\d+)分",
        text,
    )

    if not match:
        return {
            "train_line": None,
            "primary_station": None,
            "station_walk_minutes": None,
        }

    return {
        "train_line":
            match.group(1),

        "primary_station":
            match.group(2),

        "station_walk_minutes":
            int(match.group(3)),
    }


def parse_structure(text):
    mappings = [
        (
            r"(鉄骨鉄筋コンクリート|SRC造)",
            "SRC",
        ),
        (
            r"(鉄筋コンクリート|RC造)",
            "RC",
        ),
        (
            r"(軽量鉄骨|鉄骨造)",
            "STEEL",
        ),
        (
            r"(木造)",
            "WOOD",
        ),
    ]

    for pattern, value in mappings:
        if re.search(pattern, text):
            return value

    return None


def parse_orientation(text):
    value = search(
        r"向き\s+"
        r"(南東|南西|北東|北西|南|北|東|西)"
        r"\s+建物種別",
        text,
    )

    mapping = {
        "南": "south",
        "南東": "southeast",
        "南西": "southwest",
        "東": "east",
        "西": "west",
        "北": "north",
        "北東": "northeast",
        "北西": "northwest",
    }

    return mapping.get(value)


def crawl_suumo_url(url):
    html = fetch_page(url)

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    text = normalize_text(soup)

    listing_id = extract_listing_id(
        url
    )

    if not listing_id:
        raise ValueError(
            f"Could not extract SUUMO ID: {url}"
        )

    heading = soup.find("h1")

    property_name = (
        heading.get_text(
            " ",
            strip=True,
        )
        if heading
        else f"SUUMO {listing_id}"
    )

    # --------------------------------------------------
    # Rent / management fee
    # --------------------------------------------------

    price_match = re.search(
        r"([\d.]+万円)"
        r"\s+管理費・共益費:\s*"
        r"([\d,]+円|-)",
        text,
    )

    rent = None
    management_fee = None

    if price_match:
        rent = parse_yen(
            price_match.group(1)
        )

        management_fee = parse_yen(
            price_match.group(2)
        )

    monthly_total = None

    if rent is not None:
        monthly_total = (
            rent
            + (management_fee or 0)
        )

    # --------------------------------------------------
    # Basic property information
    # --------------------------------------------------

    address = search(
        r"所在地\s+(.+?)\s+駅徒歩",
        text,
    )

    layout = search(
        r"間取り\s+([0-9A-Za-z]+)"
        r"\s+専有面積",
        text,
    )

    area_raw = search(
        r"専有面積\s+([\d.]+)"
        r"\s*m",
        text,
    )

    area_m2 = (
        float(area_raw)
        if area_raw
        else None
    )

    floor_raw = search(
        r"築年数\s+.+?"
        r"\s+階\s+([^ ]+階)",
        text,
    )

    floor_number = None

    if floor_raw:
        match = re.search(
            r"(\d+)階",
            floor_raw,
        )

        if match:
            floor_number = int(
                match.group(1)
            )

    age_match = re.search(
        r"築年数\s+築(\d+)年",
        text,
    )

    building_age = (
        int(age_match.group(1))
        if age_match
        else 0
        if "築年数 新築" in text
        else None
    )

    building_type = search(
        r"建物種別\s+(\S+)",
        text,
    )

    station = parse_primary_station(
        text
    )

    # Reuse our existing explicit-keyword
    # facility detector.
    facilities = extract_facilities(
        {},
        {
            "facility_text": text,
        },
    )

    room = {
        "source":
            "suumo",

        "source_listing_id":
            listing_id,

        "source_url":
            url,

        "property":
            property_name,

        # SUUMO URL identifies this exact listing,
        # even when room number is not exposed.
        "room":
            f"SUUMO {listing_id}",

        "rent":
            rent,

        "management_fee":
            management_fee,

        "monthly_total":
            monthly_total,

        "layout":
            layout,

        "area_m2":
            area_m2,

        "floor":
            floor_raw,

        "floor_number":
            floor_number,

        "address":
            address,

        "building_age_estimate_years":
            building_age,

        "structure":
            parse_structure(text),

        "orientation":
            parse_orientation(text),

        "building_type":
            building_type,

        "primary_station":
            station[
                "primary_station"
            ],

        "station_walk_minutes":
            station[
                "station_walk_minutes"
            ],

        "train_line":
            station[
                "train_line"
            ],

        "access_type":
            "walk",

        # UR-only identifiers don't apply.
        "shisya":
            None,

        "danchi":
            None,

        "shikibetu":
            None,

        "area_code":
            None,

        # Private listing status is unknown
        # unless explicitly verified.
        "foreigner_friendly": {
            "score": 40,
            "status": "unknown",
            "evidence": [],
            "notes":
                "No explicit foreigner acceptance "
                "verified from listing.",
        },

        # Do NOT reuse UR move-in cost assumptions.
        "initial_cost": {
            "estimated_total": None,
            "estimate_only": True,
            "source": "unknown",
        },
    }

    # Merge explicit facility fields.
    room.update(
        facilities
    )

    return room