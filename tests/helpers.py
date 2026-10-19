import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llm_workbench.config import get_env_config
from llm_workbench.db.connection import init_db


class TemporaryDatabaseTestCase(unittest.TestCase):
    # every test gets its own empty database file, the local `.env` database is never touched

    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        # environment variables take precedence over `.env`
        environment = mock.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key", "DB_PATH": str(Path(temp_dir.name) / "test.db")},
        )
        environment.start()
        self.addCleanup(environment.stop)

        # the config and the schema creation are cached per process, so they have to pick up the new path
        self._clear_caches()
        self.addCleanup(self._clear_caches)

    @staticmethod
    def _clear_caches() -> None:
        get_env_config.cache_clear()
        init_db.cache_clear()
