import unittest
from unittest import mock

from crawlers.ur import (
    crawl_area,
    crawl_areas,
    extract_properties,
    normalize_room,
    parse_area,
    parse_yen,
    room_is_available,
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
        self.assertEqual(room["renovation_status"], "not_marked_by_ur")

    def test_detects_ur_renovation_design(self):
        room = normalize_room(PROPERTY, dict(ROOM, id="002050502", roomLinkSp="/room?JKSS=002050502", design=[{"デザイン_HTML": "renovation"}]))
        self.assertEqual(room["renovation_status"], "renovated")
        self.assertIsNone(room["renovation_start"])
        self.assertEqual(room["ur_room_id"], "002050502")
        self.assertEqual(room["source_url"], "https://www.ur-net.go.jp/room?JKSS=002050502")

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

    def test_filters_rooms_missing_from_ur_detail_api(self):
        with mock.patch("crawlers.ur.crawl_area", return_value=[{"ur_room_id": "1"}, {"ur_room_id": "2"}]), mock.patch(
            "crawlers.ur.room_is_available", side_effect=[True, False]
        ):
            rooms, errors = crawl_areas(["102"])
        self.assertEqual(rooms, [{"ur_room_id": "1"}])
        self.assertEqual(errors, [])

    @mock.patch("crawlers.ur.urllib.request.urlopen")
    def test_rejects_empty_or_wrong_room_detail(self, urlopen):
        room = {"ur_room_id": "1", "shisya": "40", "danchi": "1"}
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b"[]"
        self.assertFalse(room_is_available(room))
        response.read.return_value = b'[{"id":"2"}]'
        self.assertFalse(room_is_available(room))


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

    def test_property_rows_do_not_leak_neighbouring_values(self):
        detail = ur_property.parse_property_detail("""
        <table><tr><th><p>構造</p></th><td>鉄筋コンクリート造</td></tr>
        <tr><th>管理年数</th><td>築10年</td></tr><tr><th>住所</th><td>横浜市</td></tr>
        <tr><th>駐車場</th><td>・駐車場などを見る</td></tr></table>
        """)
        self.assertEqual(detail["structure"], "RC")
        self.assertEqual(detail["management_age_raw"], "築10年")

    def test_parses_renovation_date_formats(self):
        self.assertEqual(ur_property.renovation_start("リノベーション実施：2022年3月"), "2022-03")
        self.assertEqual(ur_property.renovation_start("リフォーム（2021/11）"), "2021-11")

    @mock.patch("services.ur_property.fetch_room_renovation", return_value="2026-07")
    @mock.patch("services.ur_property.fetch_property_detail", return_value={})
    def test_enriches_renovated_room_date(self, _property, _room):
        room = ur_property.enrich_ur_property({
            "source": "ur", "renovation_status": "renovated", "ur_room_id": "1"
        })
        self.assertEqual(room["renovation_start"], "2026-07")

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
