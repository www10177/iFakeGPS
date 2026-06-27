import unittest

from src.core.models import RoutePoint


class RouteSummaryTests(unittest.TestCase):
    def test_estimate_route_from_single_segment_uses_speed(self):
        from src.core.route_summary import summarize_route

        summary = summarize_route(
            [
                RoutePoint(latitude=25.0, longitude=121.0),
                RoutePoint(latitude=25.0, longitude=121.01),
            ],
            speed_kmh=20.0,
        )

        self.assertEqual(summary.point_count, 2)
        self.assertEqual(len(summary.segments), 1)
        self.assertGreater(summary.total_distance_m, 900)
        self.assertLess(summary.total_distance_m, 1100)
        self.assertAlmostEqual(
            summary.total_duration_s,
            summary.total_distance_m / 1000 / 20.0 * 3600.0,
            delta=1.0,
        )

    def test_estimate_route_from_origin_and_one_target(self):
        from src.core.route_summary import summarize_route

        summary = summarize_route(
            [RoutePoint(latitude=25.0, longitude=121.01)],
            speed_kmh=5.0,
            origin=(25.0, 121.0),
        )

        self.assertEqual(summary.point_count, 1)
        self.assertEqual(len(summary.segments), 1)
        self.assertGreater(summary.total_duration_s, 600)

    def test_estimate_route_for_multiple_segments_adds_totals(self):
        from src.core.route_summary import summarize_route

        summary = summarize_route(
            [
                RoutePoint(latitude=25.0, longitude=121.0),
                RoutePoint(latitude=25.0, longitude=121.01),
                RoutePoint(latitude=25.01, longitude=121.01),
            ],
            speed_kmh=20.0,
        )

        self.assertEqual(len(summary.segments), 2)
        self.assertAlmostEqual(
            summary.total_distance_m,
            sum(segment.distance_m for segment in summary.segments),
            delta=0.01,
        )
        self.assertAlmostEqual(
            summary.total_duration_s,
            sum(segment.duration_s for segment in summary.segments),
            delta=0.01,
        )

    def test_estimate_remaining_route_from_current_position(self):
        from src.core.route_summary import summarize_remaining_route

        points = [
            RoutePoint(latitude=25.0, longitude=121.0),
            RoutePoint(latitude=25.0, longitude=121.01),
            RoutePoint(latitude=25.01, longitude=121.01),
        ]

        summary = summarize_remaining_route(
            points,
            speed_kmh=20.0,
            current_position=(25.0, 121.005),
            next_point_index=1,
        )

        self.assertEqual(len(summary.segments), 2)
        self.assertGreater(summary.total_distance_m, 1000)
        self.assertLess(summary.total_distance_m, 2000)

    def test_estimate_remaining_route_returns_empty_when_no_next_point(self):
        from src.core.route_summary import choose_primary_summary, summarize_remaining_route

        points = [
            RoutePoint(latitude=25.0, longitude=121.0),
            RoutePoint(latitude=25.0, longitude=121.01),
        ]

        summary = summarize_remaining_route(
            points,
            speed_kmh=20.0,
            current_position=(25.0, 121.01),
            next_point_index=2,
        )

        self.assertEqual(len(summary.segments), 0)
        self.assertEqual(summary.total_distance_m, 0)
        chosen = choose_primary_summary(
            total_summary=self._make_summary(distance_m=1000, duration_s=600),
            remaining_summary=summary,
        )
        self.assertEqual(chosen.total_distance_m, 0)

    def test_speed_is_clamped_to_positive_value(self):
        from src.core.route_summary import summarize_route

        summary = summarize_route(
            [
                RoutePoint(latitude=25.0, longitude=121.0),
                RoutePoint(latitude=25.0, longitude=121.001),
            ],
            speed_kmh=0.0,
        )

        self.assertGreater(summary.total_duration_s, 0)

    def test_formats_distance_and_duration_strings(self):
        from src.core.route_summary import format_distance, format_duration

        self.assertEqual(format_distance(82), "82 m")
        self.assertEqual(format_distance(1250), "1.25 km")
        self.assertEqual(format_duration(45), "<1 min")
        self.assertEqual(format_duration(8 * 60), "8 min")
        self.assertEqual(format_duration(66 * 60), "1h 6m")

    def _make_summary(self, distance_m: float, duration_s: float):
        from src.core.route_summary import RouteSummary, SegmentSummary

        return RouteSummary(
            point_count=2,
            segments=[SegmentSummary(distance_m=distance_m, duration_s=duration_s)],
            total_distance_m=distance_m,
            total_duration_s=duration_s,
        )


if __name__ == "__main__":
    unittest.main()
