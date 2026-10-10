import re
import sys
import time

from bs4 import BeautifulSoup
from playwright.sync_api import (
    sync_playwright,
)

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

                context = browser.new_context(
                    locale="ja-JP",
                    viewport={
                        "width": 1440,
                        "height": 1000,
                    },
                )

                page = context.new_page()

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

                if status is not None and status >= 400:
                    raise RuntimeError(
                        f"CHINTAI returned HTTP {status}"
                    )

                page.wait_for_timeout(
                    1500
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
                    "CHINTAI browser fetch failed. "
                    f"Retry {attempt}/"
                    f"{max_retries} "
                    f"in {delay}s: {e}"
                ),
                file=sys.stderr,
            )

            time.sleep(delay)

    raise RuntimeError(
        (
            "CHINTAI browser fetch failed after "
            f"{max_retries} attempts: "
            f"{last_error}"
        )
    )

def parse_yen(value):
    if not value:
        return None

    value = value.strip()

    if value in {
        "--",
        "-",
    }:
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

    match = re.search(
        r"([\d.]+)\s*ヶ月",
        value,
    )

    if match:
        return {
            "months":
                float(match.group(1))
        }

    return None


def normalize_text(soup):
    return re.sub(
        r"\s+",
        " ",
        soup.get_text(
            " ",
            strip=True,
        ),
    )


def extract_listing_id(url):
    match = re.search(
        r"/detail/bk-([^/]+)/?",
        url,
    )

    if not match:
        return None

    return match.group(1)


def search(pattern, text):
    match = re.search(
        pattern,
        text,
    )

    if not match:
        return None

    return match.group(1).strip()


def parse_structure(text):
    if "鉄骨鉄筋コンクリート" in text:
        return "SRC"

    if "鉄筋コンクリート" in text:
        return "RC"

    if (
        "鉄骨造" in text
        or "軽量鉄骨" in text
    ):
        return "STEEL"

    if "木造" in text:
        return "WOOD"

    return None


def parse_orientation(value):
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


def parse_primary_station(text):
    match = re.search(
        r"交通\s+"
        r"([^/]+)/"
        r"([^駅\s]+駅)"
        r"\s+徒歩(\d+)分",
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
            match.group(2)
            .replace("駅", ""),

        "station_walk_minutes":
            int(match.group(3)),
    }


def crawl_chintai_url(url):
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
            f"Could not extract CHINTAI ID: {url}"
        )

    heading = soup.find("h1")

    property_name = (
        heading.get_text(
            " ",
            strip=True,
        )
        if heading
        else f"CHINTAI {listing_id}"
    )

    rent_raw = search(
        r"家賃\s+([\d.]+万円)",
        text,
    )

    management_raw = search(
        r"管理費等\s+([\d,]+円)",
        text,
    )

    rent = parse_yen(
        rent_raw
    )

    management_fee = parse_yen(
        management_raw
    )

    monthly_total = None

    if rent is not None:
        monthly_total = (
            rent
            + (management_fee or 0)
        )

    layout = search(
        r"間取り\s+([0-9A-Za-z]+)",
        text,
    )

    area_raw = search(
        r"専有面積\s+([\d.]+)m²",
        text,
    )

    area_m2 = (
        float(area_raw)
        if area_raw
        else None
    )

    age_raw = search(
        r"築年\s+.+?\(築(\d+)年\)",
        text,
    )

    building_age = (
        int(age_raw)
        if age_raw
        else 0
        if "1年未満" in text
        else None
    )

    orientation_raw = search(
        r"方位\s+(南東|南西|北東|北西|南|北|東|西)",
        text,
    )

    floor_raw = search(
        r"物件階層\s+([^ ]+階)/",
        text,
    )

    floor_number = None

    if floor_raw:
        floor_match = re.search(
            r"(\d+)階",
            floor_raw,
        )

        if floor_match:
            floor_number = int(
                floor_match.group(1)
            )

    address = search(
        r"住所\s+(.+?)"
        r"地図で物件の周辺環境",
        text,
    )

    station = parse_primary_station(
        text
    )

    facilities = extract_facilities(
        {},
        {
            "facility_text": text,
        },
    )

    room = {
        "source":
            "chintai",

        "source_listing_id":
            listing_id,

        "source_url":
            url,

        "property":
            property_name,

        "room":
            f"CHINTAI {listing_id}",

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
            parse_orientation(
                orientation_raw
            ),

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

        "shisya":
            None,

        "danchi":
            None,

        "shikibetu":
            None,

        "area_code":
            None,

        "foreigner_friendly": {
            "score": 40,
            "status": "unknown",
            "evidence": [],
            "notes":
                "No explicit foreigner acceptance "
                "verified from CHINTAI listing.",
        },

        "initial_cost": {
            "estimated_total": None,
            "estimate_only": True,
            "source": "chintai",
        },
    }

    room.update(
        facilities
    )

    return room