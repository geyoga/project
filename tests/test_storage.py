import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services import storage


class StorageTests(unittest.TestCase):
    def test_listing_lifecycle_uses_temporary_database(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(storage, "DB_PATH", Path(directory) / "test.db"):
                storage.initialize_database()
                run_id = storage.start_crawl_run(1)
                room = {
                    "source": "ur",
                    "shisya": "40",
                    "danchi": "145",
                    "shikibetu": "0",
                    "room": "502号室",
                    "property": "西菅田",
                    "source_url": "https://example.test/ur",
                    "rent": 80000,
                    "management_fee": 5000,
                    "monthly_total": 85000,
                    "layout": "3DK",
                    "area_m2": 53.0,
                    "floor": "5階",
                    "score": 75,
                }
                changes = storage.save_observed_listings(run_id, [room])
                self.assertEqual(changes[0]["type"], "new")
                self.assertEqual(len(storage.get_pending_notifications()), 0)

                removed = storage.save_observed_listings(run_id, [], True)
                self.assertEqual(removed[0]["type"], "removed")


if __name__ == "__main__":
    unittest.main()
