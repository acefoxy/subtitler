from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from subtitler.config import AppConfig, SyncMode


class AppConfigTests(unittest.TestCase):
    def test_runtime_defaults_prefer_high_quality_and_gpu(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = AppConfig.from_env()

        self.assertEqual(config.sync_mode, SyncMode.HIGH_QUALITY)
        self.assertTrue(config.prefer_gpu)


if __name__ == "__main__":
    unittest.main()