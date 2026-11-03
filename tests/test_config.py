import os
import unittest
from pathlib import Path
from unittest import mock

from llm_workbench.config import EnvironmentConfig, EnvironmentConfigError, get_env_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class EnvironmentConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        get_env_config.cache_clear()
        self.addCleanup(get_env_config.cache_clear)

    def load_config(self, db_path: str) -> EnvironmentConfig:
        # environment variables take precedence over `.env`
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": " test-key ", "DB_PATH": db_path}):
            return get_env_config()

    def test_relative_db_path_is_resolved_against_the_project_root(self) -> None:
        config = self.load_config("data/database.db")

        self.assertEqual(config.db_path, PROJECT_ROOT / "data" / "database.db")
        self.assertEqual(config.openrouter_api_key, "test-key")

    def test_absolute_db_path_is_used_as_is(self) -> None:
        # the Docker image relies on this to keep the database in its volume
        self.assertEqual(self.load_config("/data/database.db").db_path, Path("/data/database.db"))

    def test_blank_values_are_reported_as_missing(self) -> None:
        with self.assertRaisesRegex(EnvironmentConfigError, "DB_PATH"):
            self.load_config("  ")


if __name__ == "__main__":
    unittest.main()
