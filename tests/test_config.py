import importlib
import os
import tempfile
import unittest
from pathlib import Path


class ConfigTests(unittest.TestCase):
    def test_default_paths_are_project_relative(self):
        import config

        self.assertEqual(config.PROJECT_DIR.name, "apartment-agent")
        self.assertEqual(config.DATA_DIR, config.PROJECT_DIR / "data")
        self.assertEqual(config.DB_PATH, config.DATA_DIR / "apartments.db")

    def test_data_directory_can_be_overridden(self):
        import config

        with tempfile.TemporaryDirectory() as directory:
            original = os.environ.get("APARTMENT_AGENT_DATA_DIR")
            os.environ["APARTMENT_AGENT_DATA_DIR"] = directory
            try:
                config = importlib.reload(config)
                self.assertEqual(config.DATA_DIR, Path(directory))
                self.assertEqual(config.DB_PATH, Path(directory) / "apartments.db")
            finally:
                if original is None:
                    os.environ.pop("APARTMENT_AGENT_DATA_DIR", None)
                else:
                    os.environ["APARTMENT_AGENT_DATA_DIR"] = original
                importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
