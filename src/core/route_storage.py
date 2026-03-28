"""
route_storage.py – SQLite-backed saved route persistence.

Stores named routes in a local database so users can save, load,
and manage their favourite paths.
"""

import json
import os
import sqlite3
from dataclasses import dataclass

import gpxpy
import gpxpy.gpx

from src.core.models import RoutePoint
from src.utils.logger import logger


@dataclass
class SavedRouteInfo:
    """Lightweight summary of a saved route (no heavy point data)."""

    id: int
    name: str
    point_count: int
    created_at: str


class RouteStorage:
    """CRUD operations for saved routes backed by SQLite."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            db_dir = os.path.join(app_data, "iFakeGPS")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "routes.db")

        self.db_path = db_path
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS saved_routes (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        name       TEXT    NOT NULL,
                        created_at TEXT    NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT    NOT NULL DEFAULT (datetime('now')),
                        points     TEXT    NOT NULL
                    )
                    """
                )
            logger.info(f"[RouteStorage] DB ready at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"[RouteStorage] Failed to init schema: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    @staticmethod
    def _points_to_json(points: list[RoutePoint]) -> str:
        return json.dumps(
            [{"lat": p.latitude, "lon": p.longitude} for p in points],
            ensure_ascii=False,
        )

    @staticmethod
    def _json_to_points(raw: str) -> list[RoutePoint]:
        data = json.loads(raw)
        return [RoutePoint(latitude=d["lat"], longitude=d["lon"]) for d in data]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, name: str, points: list[RoutePoint]) -> int:
        """Save a route. Returns the new row id."""
        pts_json = self._points_to_json(points)
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO saved_routes (name, points) VALUES (?, ?)",
                (name, pts_json),
            )
            row_id = cursor.lastrowid
        logger.info(
            f"[RouteStorage] Saved route '{name}' (id={row_id}, {len(points)} pts)"
        )
        return row_id

    def load(self, route_id: int) -> tuple[str, list[RoutePoint]]:
        """Load a route by id. Returns (name, points)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name, points FROM saved_routes WHERE id = ?",
                (route_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Route id={route_id} not found")
        return row[0], self._json_to_points(row[1])

    def list_all(self) -> list[SavedRouteInfo]:
        """Return lightweight info for every saved route."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, points, created_at FROM saved_routes ORDER BY created_at DESC"
            ).fetchall()
        result = []
        for row_id, name, pts_json, created in rows:
            count = len(json.loads(pts_json))
            result.append(
                SavedRouteInfo(
                    id=row_id, name=name, point_count=count, created_at=created
                )
            )
        return result

    def delete(self, route_id: int) -> None:
        """Delete a saved route by id."""
        with self._connect() as conn:
            conn.execute("DELETE FROM saved_routes WHERE id = ?", (route_id,))
        logger.info(f"[RouteStorage] Deleted route id={route_id}")

    def rename(self, route_id: int, new_name: str) -> None:
        """Rename a saved route."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE saved_routes SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (new_name, route_id),
            )
        logger.info(f"[RouteStorage] Renamed route id={route_id} → '{new_name}'")

    # ------------------------------------------------------------------
    # GPX Import / Export
    # ------------------------------------------------------------------

    def export_gpx(self, route_id: int, file_path: str) -> None:
        """Export a saved route to a GPX file."""
        name, points = self.load(route_id)

        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_track.name = name
        gpx.tracks.append(gpx_track)

        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        for pt in points:
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(latitude=pt.latitude, longitude=pt.longitude)
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(gpx.to_xml())

        logger.info(f"[RouteStorage] Exported route id={route_id} to {file_path}")

    def import_gpx(
        self, file_path: str, save_to_db: bool = True
    ) -> tuple[int | None, str, list[RoutePoint]]:
        """
        Import a route from a GPX file.
        Returns: (new_route_id, name, points)
        """
        with open(file_path, encoding="utf-8") as f:
            gpx = gpxpy.parse(f)

        points = []
        # Try finding points in tracks
        for track in gpx.tracks:
            for segment in track.segments:
                for pt in segment.points:
                    points.append(
                        RoutePoint(latitude=pt.latitude, longitude=pt.longitude)
                    )

        # If no tracks, fallback to routes
        if not points:
            for route_obj in gpx.routes:
                for pt in route_obj.points:
                    points.append(
                        RoutePoint(latitude=pt.latitude, longitude=pt.longitude)
                    )

        if not points:
            # Fallback to waypoints
            for wp in gpx.waypoints:
                points.append(RoutePoint(latitude=wp.latitude, longitude=wp.longitude))

        if not points:
            raise ValueError(f"No usable track/route/waypoints found in {file_path}")

        # Use the first track/route name, or the filename
        name = os.path.splitext(os.path.basename(file_path))[0]
        if gpx.tracks and gpx.tracks[0].name:
            name = gpx.tracks[0].name
        elif gpx.routes and gpx.routes[0].name:
            name = gpx.routes[0].name

        route_id = None
        if save_to_db:
            route_id = self.save(name, points)

        logger.info(f"[RouteStorage] Imported GPX '{name}' with {len(points)} points")
        return route_id, name, points
