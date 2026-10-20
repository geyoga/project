import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

import run


class CliTests(unittest.TestCase):
    @mock.patch("run.initialize_database")
    @mock.patch("run.start_crawl_run", return_value=1)
    @mock.patch("run.load_property_metadata", return_value={})
    @mock.patch("run.load_profile", return_value={"ur_area_codes": []})
    @mock.patch("run.get_pending_notifications", return_value=[])
    @mock.patch("run.parse_args", return_value=SimpleNamespace(
        alerts_only=True,
        mark_alerts_delivered=None,
    ))
    def test_alerts_only_with_no_areas(self, *_):
        output = io.StringIO()
        with redirect_stdout(output):
            run.main()

        self.assertEqual(output.getvalue().strip(), "NO_ALERTS")


if __name__ == "__main__":
    unittest.main()
