"""
location_storage.py - SQLite-backed saved location persistence.

Stores named single-point locations for quick map jumps and teleport actions.
"""

import os
import sqlite3
from dataclasses import dataclass

from src.utils.logger import logger


@dataclass
class SavedLocationInfo:
    """A saved single-point location."""

    id: int
    name: str
    latitude: float
    longitude: float
    created_at: str


class LocationStorage:
    """CRUD operations for saved locations backed by SQLite."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            db_dir = os.path.join(app_data, "iFakeGPS")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "routes.db")

        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS saved_locations (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        name       TEXT    NOT NULL,
                        latitude   REAL    NOT NULL,
                        longitude  REAL    NOT NULL,
                        created_at TEXT    NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
            logger.info(f"[LocationStorage] DB ready at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"[LocationStorage] Failed to init schema: {e}")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def save(self, name: str, latitude: float, longitude: float) -> int:
        """Save a location. Returns the new row id."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO saved_locations (name, latitude, longitude)
                VALUES (?, ?, ?)
                """,
                (name, latitude, longitude),
            )
            row_id = cursor.lastrowid
        logger.info(f"[LocationStorage] Saved location '{name}' (id={row_id})")
        return row_id

    def list_all(self) -> list[SavedLocationInfo]:
        """Return all saved locations, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, latitude, longitude, created_at
                FROM saved_locations
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [
            SavedLocationInfo(
                id=row_id,
                name=name,
                latitude=latitude,
                longitude=longitude,
                created_at=created_at,
            )
            for row_id, name, latitude, longitude, created_at in rows
        ]

    def delete(self, location_id: int) -> None:
        """Delete a saved location by id."""
        with self._connect() as conn:
            conn.execute("DELETE FROM saved_locations WHERE id = ?", (location_id,))
        logger.info(f"[LocationStorage] Deleted location id={location_id}")
