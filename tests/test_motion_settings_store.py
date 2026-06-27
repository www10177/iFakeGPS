import tempfile
import unittest
from pathlib import Path

from src.core.models import MotionSettings


class MotionSettingsStoreTests(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        from src.core.motion_settings_store import MotionSettingsStore

        with tempfile.TemporaryDirectory() as tmp:
            store = MotionSettingsStore(Path(tmp) / "motion_settings.json")
            settings = MotionSettings(
                noise_pct=12.0,
                random_stop_enabled=True,
                random_stop_interval_m=180.0,
                random_stop_min_s=4.0,
                random_stop_max_s=11.0,
                displacement_noise_enabled=True,
                displacement_radius_m=3.5,
            )

            store.save(settings)
            loaded = store.load()

        self.assertEqual(loaded, settings)

    def test_load_returns_defaults_when_missing(self):
        from src.core.motion_settings_store import MotionSettingsStore

        with tempfile.TemporaryDirectory() as tmp:
            store = MotionSettingsStore(Path(tmp) / "missing.json")
            loaded = store.load()

        self.assertEqual(loaded, MotionSettings())


if __name__ == "__main__":
    unittest.main()
