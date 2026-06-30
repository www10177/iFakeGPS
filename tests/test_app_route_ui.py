import unittest
from unittest.mock import MagicMock, patch

from src.core.models import RoutePoint
from src.core.route_summary import RouteSummary, SegmentSummary
from src.ui.app import iFakeGPSApp


class _DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _DummySlider:
    def __init__(self, value=0.0):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _DummyLabel:
    def __init__(self):
        self.text = None

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


class _DummyWalker:
    def __init__(self, snapshot=None):
        self.speed = None
        self.speed_noise = None
        self.random_stop_settings = None
        self.displacement_noise_settings = None
        self.snapshot = snapshot or {
            "is_walking": False,
            "is_paused": False,
            "resume_segment_index": 0,
            "random_stop_active": False,
            "random_stop_remaining_s": 0.0,
        }

    def set_speed(self, speed):
        self.speed = speed

    def set_speed_noise(self, noise_pct):
        self.speed_noise = noise_pct

    def set_random_stop_settings(self, enabled, interval_m, duration_min_s, duration_max_s):
        self.random_stop_settings = (
            enabled,
            interval_m,
            duration_min_s,
            duration_max_s,
        )

    def set_displacement_noise_settings(self, enabled, radius_m):
        self.displacement_noise_settings = (enabled, radius_m)

    def get_progress_snapshot(self):
        return self.snapshot


class AppRouteUiTests(unittest.TestCase):
    def test_apply_speed_preset_updates_existing_controls(self):
        app = object.__new__(iFakeGPSApp)
        app.speed_slider = _DummySlider()
        app.speed_entry_var = _DummyVar("20.0")
        app.route_walker = _DummyWalker()
        app._update_route_info = MagicMock()
        app.focus_set = MagicMock()

        app._apply_speed_preset(60.0)

        self.assertEqual(app.speed_slider.get(), 60.0)
        self.assertEqual(app.speed_entry_var.get(), "60.0")
        self.assertEqual(app.route_walker.speed, 60.0)
        app._update_route_info.assert_called_once()
        app.focus_set.assert_called_once()

    def test_get_remaining_route_summary_uses_current_position_while_walking(self):
        app = object.__new__(iFakeGPSApp)
        app.current_simulated_position = (25.0, 121.005)
        app.route_points = [
            RoutePoint(latitude=25.0, longitude=121.0),
            RoutePoint(latitude=25.0, longitude=121.01),
            RoutePoint(latitude=25.01, longitude=121.01),
        ]
        app.route_walker = _DummyWalker(
            snapshot={
                "is_walking": True,
                "is_paused": False,
                "resume_segment_index": 0,
            }
        )

        summary = app._get_remaining_route_summary(20.0)

        self.assertIsNotNone(summary)
        self.assertGreater(summary.total_distance_m, 1000)
        self.assertLess(summary.total_distance_m, 2000)

    def test_update_route_info_prefers_remaining_summary_for_primary_label(self):
        app = object.__new__(iFakeGPSApp)
        app.current_simulated_position = (25.0, 121.005)
        app.route_points = [
            RoutePoint(latitude=25.0, longitude=121.0),
            RoutePoint(latitude=25.0, longitude=121.01),
        ]
        app.route_info = _DummyLabel()
        app.route_segments_info = _DummyLabel()
        app._get_current_speed_kmh = MagicMock(return_value=20.0)

        total_summary = RouteSummary(
            point_count=2,
            segments=[SegmentSummary(distance_m=2000.0, duration_s=600.0)],
            total_distance_m=2000.0,
            total_duration_s=600.0,
        )
        remaining_summary = RouteSummary(
            point_count=2,
            segments=[SegmentSummary(distance_m=500.0, duration_s=150.0)],
            total_distance_m=500.0,
            total_duration_s=150.0,
        )

        with (
            patch("src.ui.app.summarize_route", return_value=total_summary),
            patch("src.ui.app.iFakeGPSApp._get_remaining_route_summary", return_value=remaining_summary),
        ):
            app._update_route_info()

        self.assertIn("500 m", app.route_info.text)
        self.assertIn("2 min", app.route_info.text)
        self.assertIn("2.00 km", app.route_segments_info.text)
        self.assertIn("10 min", app.route_segments_info.text)

    def test_apply_motion_settings_updates_walker_and_refreshes_summary(self):
        app = object.__new__(iFakeGPSApp)
        app.route_walker = _DummyWalker()
        app._update_route_info = MagicMock()
        app.motion_settings_store = MagicMock()

        app._apply_motion_settings(
            noise_pct=15.0,
            random_stop_enabled=True,
            random_stop_interval_m=180.0,
            random_stop_min_s=5.0,
            random_stop_max_s=12.0,
            displacement_noise_enabled=True,
            displacement_radius_m=3.0,
        )

        self.assertEqual(app.route_walker.speed_noise, 15.0)
        self.assertEqual(
            app.route_walker.random_stop_settings,
            (True, 180.0, 5.0, 12.0),
        )
        self.assertEqual(app.route_walker.displacement_noise_settings, (True, 3.0))
        app._update_route_info.assert_called_once()
        app.motion_settings_store.save.assert_called_once()

    def test_try_apply_motion_settings_values_saves_valid_live_changes(self):
        app = object.__new__(iFakeGPSApp)
        app.route_walker = _DummyWalker()
        app._update_route_info = MagicMock()
        app.motion_settings_store = MagicMock()

        applied = app._try_apply_motion_settings_values(
            noise_pct=18.0,
            random_stop_enabled=True,
            random_stop_interval_text="200",
            random_stop_min_text="4",
            random_stop_max_text="9",
            displacement_noise_enabled=True,
            displacement_radius_text="2.5",
        )

        self.assertTrue(applied)
        self.assertEqual(
            app.route_walker.random_stop_settings,
            (True, 200.0, 4.0, 9.0),
        )
        self.assertEqual(app.route_walker.displacement_noise_settings, (True, 2.5))
        app.motion_settings_store.save.assert_called_once()

    def test_try_apply_motion_settings_values_ignores_invalid_live_changes(self):
        app = object.__new__(iFakeGPSApp)
        app.route_walker = _DummyWalker()
        app._update_route_info = MagicMock()
        app.motion_settings_store = MagicMock()

        applied = app._try_apply_motion_settings_values(
            noise_pct=18.0,
            random_stop_enabled=True,
            random_stop_interval_text="oops",
            random_stop_min_text="4",
            random_stop_max_text="9",
            displacement_noise_enabled=True,
            displacement_radius_text="2.5",
        )

        self.assertFalse(applied)
        self.assertIsNone(app.route_walker.random_stop_settings)
        app.motion_settings_store.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
