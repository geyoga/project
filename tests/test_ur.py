import unittest
from unittest import mock

from crawlers.ur import (
    crawl_area,
    crawl_areas,
    extract_properties,
    normalize_room,
    parse_area,
    parse_yen,
)
from services import ur_property
from services.commute import enrich_commute


PROPERTY = {
    "shisya": "40",
    "danchi": "145",
    "shikibetu": "0",
    "danchiNm": "西菅田",
}

ROOM = {
    "roomNmMain": "5-6号棟",
    "roomNmSub": "502号室",
    "rent": "78,700円",
    "commonfee": "5,200円",
    "type": "3DK",
    "floorspace": "53.00m2",
    "floor": "5階",
}


class UrCrawlerTests(unittest.TestCase):
    def test_parses_numeric_values(self):
        self.assertEqual(parse_yen("¥78,700"), 78700)
        self.assertIsNone(parse_yen("-"))
        self.assertEqual(parse_area("53.00m2"), 53.0)
        self.assertIsNone(parse_area("-"))

    def test_normalizes_room(self):
        room = normalize_room(PROPERTY, ROOM)

        self.assertEqual(
            room["source_url"],
            "https://www.ur-net.go.jp/chintai/sp/kanto/kanagawa/40_1450_room.html",
        )
        self.assertEqual(room["room"], "5-6号棟 502号室")
        self.assertEqual(room["monthly_total"], 83900)
        self.assertEqual(room["area_m2"], 53.0)

    def test_handles_malformed_api_values(self):
        self.assertEqual(extract_properties({"result": [PROPERTY]}), [PROPERTY])
        self.assertEqual(extract_properties({"result": []}), [])
        self.assertEqual(normalize_room(None, None)["monthly_total"], None)

        with mock.patch(
            "crawlers.ur.fetch_area",
            return_value=[dict(PROPERTY, room=[ROOM, "invalid"]), "invalid"],
        ):
            rooms = crawl_area("102")

        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["area_code"], "102")

    def test_multiple_areas_keep_partial_results(self):
        with mock.patch(
            "crawlers.ur.crawl_area",
            side_effect=[[{"area_code": "102"}], OSError("unavailable")],
        ):
            rooms, errors = crawl_areas(["102", "113"])

        self.assertEqual(rooms, [{"area_code": "102"}])
        self.assertEqual(errors, [{"area_code": "113", "error": "unavailable"}])


class UrPropertyTests(unittest.TestCase):
    HTML = """
    <html><body>
      <table>
        <tr><th>構造</th><td>鉄筋コンクリート造</td></tr>
        <tr><th>管理年数</th><td>築10年～築20年</td></tr>
        <tr><th>住所</th><td>神奈川県横浜市</td></tr>
      </table>
    </body></html>
    """

    def setUp(self):
        ur_property.CACHE.clear()

    def tearDown(self):
        ur_property.CACHE.clear()

    def test_parses_property_detail(self):
        detail = ur_property.parse_property_detail(self.HTML)

        self.assertEqual(detail["structure"], "RC")
        self.assertEqual(detail["building_age_min_years"], 10)
        self.assertEqual(detail["building_age_max_years"], 20)
        self.assertEqual(detail["building_age_estimate_years"], 15)
        self.assertEqual(detail["address"], "神奈川県横浜市")

    def test_parses_ur_map_coordinates(self):
        self.assertEqual(
            ur_property.parse_map_coordinates(
                '<input class="js-lat-data" value="35.4365812" />'
                '<input class="js-lng-data" value="139.4712707" />'
            ),
            {"latitude": 35.4365812, "longitude": 139.4712707},
        )

    def test_parses_ur_access_options(self):
        detail = ur_property.parse_property_detail("""
        <table><tr><th>交通</th><td>相鉄本線「大和」駅バス15～20分 徒歩1～5分<br>小田急江ノ島線「高座渋谷」駅 徒歩13～20分</td></tr></table>
        """)
        self.assertEqual(detail["access_options"][0]["station"], "大和")
        self.assertEqual(detail["access_options"][0]["bus_minutes"], 15)
        self.assertEqual(detail["access_options"][1]["walk_minutes_max"], 20)

    def test_local_commute_uses_best_ur_access_option(self):
        room = enrich_commute({"access_options": [
            {"station": "大和", "bus_minutes": 15, "walk_minutes": 1},
            {"station": "高座渋谷", "walk_minutes": 13},
        ]}, "Futako-Tamagawa")
        self.assertEqual(room["primary_station"], "大和")
        self.assertEqual(room["total_commute_minutes"], 69)
        self.assertEqual(room["commute_destination"], "Rakuten Crimson House")
        self.assertEqual(room["commute_source"], "local_station_table")

    def test_enrichment_uses_cache_and_preserves_non_ur(self):
        room = {"source": "ur", "shisya": "40", "danchi": "145", "shikibetu": "0"}
        with mock.patch("services.ur_property.fetch_html", return_value=self.HTML) as fetch:
            first = ur_property.enrich_ur_property(room)
            second = ur_property.enrich_ur_property({**room})

        self.assertEqual(first["structure"], "RC")
        self.assertEqual(second["address"], "神奈川県横浜市")
        self.assertEqual(fetch.call_count, 2)

    def test_enrichment_records_network_errors(self):
        room = {"source": "ur", "shisya": "40", "danchi": "145", "shikibetu": "0"}
        with mock.patch("services.ur_property.fetch_html", side_effect=OSError("offline")):
            result = ur_property.enrich_ur_property(room)

        self.assertEqual(result["property_enrichment_error"], "offline")


if __name__ == "__main__":
    unittest.main()
