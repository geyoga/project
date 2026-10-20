import unittest

from domain.listings import calculate_score, passes_hard_filters


PROFILE = {
    "preferred_monthly_max": 100000,
    "absolute_monthly_max": 120000,
    "minimum_area_m2": 35,
    "minimum_layout": "2DK",
    "maximum_station_walk_minutes": 15,
    "maximum_commute_minutes": 60,
}


class ScoringTests(unittest.TestCase):
    def test_hard_filter_rejects_over_budget(self):
        room = {"monthly_total": 120001, "area_m2": 50, "layout": "3DK"}
        self.assertFalse(passes_hard_filters(room, PROFILE))

    def test_score_is_stable_and_has_breakdown(self):
        room = {
            "monthly_total": 90000,
            "area_m2": 50,
            "layout": "3DK",
            "floor_number": 2,
            "building_age_estimate_years": 10,
            "total_commute_minutes": 40,
        }
        score = calculate_score(room, PROFILE)
        self.assertEqual(score, 73.3)
        self.assertIn("budget", room["score_breakdown"])


if __name__ == "__main__":
    unittest.main()
