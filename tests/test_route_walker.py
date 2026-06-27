import unittest
from unittest import mock

from src.core.models import RoutePoint
from src.core.route_walker import RouteWalker


class _FakeDeviceManager:
    def set_location(self, lat, lon):
        return True


class RouteWalkerTests(unittest.TestCase):
    def make_walker(self):
        return RouteWalker(
            device_manager=_FakeDeviceManager(),
            update_callback=lambda lat, lon: None,
        )

    def test_random_stop_settings_are_clamped_and_enabled(self):
        walker = self.make_walker()

        walker.set_random_stop_settings(
            enabled=True,
            interval_m=0,
            duration_min_s=12,
            duration_max_s=5,
        )

        self.assertTrue(walker.random_stop_enabled)
        self.assertEqual(walker.random_stop_interval_m, 1.0)
        self.assertEqual(walker.random_stop_min_s, 12.0)
        self.assertEqual(walker.random_stop_max_s, 12.0)

    def test_random_stop_starts_after_distance_budget_is_reached(self):
        walker = self.make_walker()
        walker.set_random_stop_settings(True, 100, 5, 10)

        with mock.patch(
            "src.core.route_walker.random.uniform", side_effect=[1.0, 7.5, 1.1]
        ):
            walker._schedule_next_random_stop()
            started = walker._advance_random_stop_trigger(0.05)
            self.assertFalse(started)
            started = walker._advance_random_stop_trigger(0.05)

        self.assertTrue(started)
        self.assertTrue(walker._random_stop_active)
        self.assertAlmostEqual(walker._random_stop_remaining_s, 7.5)

    def test_random_stop_countdown_reaches_zero_and_clears(self):
        walker = self.make_walker()
        walker._random_stop_active = True
        walker._random_stop_remaining_s = 2.0

        self.assertTrue(walker._tick_random_stop(0.5))
        self.assertAlmostEqual(walker._random_stop_remaining_s, 1.5)
        self.assertFalse(walker._tick_random_stop(1.5))
        self.assertEqual(walker._random_stop_remaining_s, 0.0)
        self.assertFalse(walker._random_stop_active)

    def test_progress_snapshot_reports_random_stop_state(self):
        walker = self.make_walker()
        walker.points = [
            RoutePoint(latitude=25.0, longitude=121.0),
            RoutePoint(latitude=25.0, longitude=121.01),
        ]
        walker._random_stop_active = True
        walker._random_stop_remaining_s = 9.0

        snapshot = walker.get_progress_snapshot()

        self.assertTrue(snapshot["random_stop_active"])
        self.assertEqual(snapshot["random_stop_remaining_s"], 9.0)

    def test_displacement_noise_returns_original_point_when_disabled(self):
        walker = self.make_walker()

        lat, lon = walker._apply_displacement_noise(25.0, 121.0, 0.01)

        self.assertEqual((lat, lon), (25.0, 121.0))

    def test_displacement_noise_stays_within_radius(self):
        from src.core.route_summary import haversine_distance_m

        walker = self.make_walker()
        walker.set_displacement_noise_settings(True, 3.0)

        with mock.patch("src.core.route_walker.random.uniform", side_effect=[2.0, 0.5, 2.0, 0.5]):
            lat, lon = walker._apply_displacement_noise(25.0, 121.0, 0.01)

        self.assertLessEqual(haversine_distance_m(25.0, 121.0, lat, lon), 3.05)


if __name__ == "__main__":
    unittest.main()
