from __future__ import annotations

import math
from dataclasses import dataclass

from src.core.models import RoutePoint


@dataclass(frozen=True)
class SegmentSummary:
    distance_m: float
    duration_s: float


@dataclass(frozen=True)
class RouteSummary:
    point_count: int
    segments: list[SegmentSummary]
    total_distance_m: float
    total_duration_s: float


def summarize_route(
    points: list[RoutePoint],
    speed_kmh: float,
    origin: tuple[float, float] | None = None,
) -> RouteSummary:
    route_points = list(points)
    if len(route_points) == 1 and origin is not None:
        route_points = [
            RoutePoint(latitude=origin[0], longitude=origin[1]),
            route_points[0],
        ]

    safe_speed_kmh = max(0.1, float(speed_kmh))
    segments: list[SegmentSummary] = []

    for index in range(len(route_points) - 1):
        start = route_points[index]
        end = route_points[index + 1]
        distance_m = haversine_distance_m(
            start.latitude,
            start.longitude,
            end.latitude,
            end.longitude,
        )
        duration_s = distance_m / 1000.0 / safe_speed_kmh * 3600.0
        segments.append(SegmentSummary(distance_m=distance_m, duration_s=duration_s))

    total_distance_m = sum(segment.distance_m for segment in segments)
    total_duration_s = sum(segment.duration_s for segment in segments)
    return RouteSummary(
        point_count=len(points),
        segments=segments,
        total_distance_m=total_distance_m,
        total_duration_s=total_duration_s,
    )


def summarize_remaining_route(
    points: list[RoutePoint],
    speed_kmh: float,
    current_position: tuple[float, float],
    next_point_index: int,
) -> RouteSummary:
    if next_point_index >= len(points):
        return RouteSummary(
            point_count=len(points),
            segments=[],
            total_distance_m=0.0,
            total_duration_s=0.0,
        )

    remaining_points = [
        RoutePoint(latitude=current_position[0], longitude=current_position[1]),
        *points[next_point_index:],
    ]
    return summarize_route(remaining_points, speed_kmh)


def choose_primary_summary(
    total_summary: RouteSummary,
    remaining_summary: RouteSummary | None,
) -> RouteSummary:
    if remaining_summary is not None:
        return remaining_summary
    return total_summary


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def format_distance(distance_m: float) -> str:
    if distance_m >= 1000:
        return f"{distance_m / 1000:.2f} km"
    return f"{distance_m:.0f} m"


def format_duration(duration_s: float) -> str:
    if duration_s < 60:
        return "<1 min"

    total_minutes = int(round(duration_s / 60.0))
    if total_minutes < 60:
        return f"{total_minutes} min"

    hours, minutes = divmod(total_minutes, 60)
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"
