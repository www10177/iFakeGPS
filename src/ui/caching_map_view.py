"""
CachingTileMapView
==================
A drop-in subclass of TkinterMapView that adds **write-through disk caching**.

tkintermapview's `database_path` parameter is read-only at runtime - it only
reads tiles from the DB but never writes freshly-downloaded tiles back.

This subclass fixes that by:
  1. Overriding `request_image()` to intercept network-downloaded tiles.
  2. Encoding the raw PNG bytes and placing them in a thread-safe write queue.
  3. A single background writer thread drains the queue into SQLite using
     WAL journal mode (safe for concurrent reads from the parent's 25 threads).

After the first browse of an area, all subsequent launches load those tiles
instantly from disk without any network round-trips.

DB schema is identical to tkintermapview's OfflineLoader so the offline
pre-loading tool remains compatible.
"""

import io
import queue
import sqlite3
import threading

import PIL
import requests
import tkintermapview
from PIL import Image, ImageTk

from src.utils.logger import logger


class CachingTileMapView(tkintermapview.TkinterMapView):
    """TkinterMapView with automatic write-through SQLite tile caching."""

    def __init__(self, *args, db_path: str | None = None, **kwargs):
        # Pass database_path to the parent so its 25 download threads can READ
        # from the DB on startup (tiles already cached in a previous session).
        if db_path:
            kwargs["database_path"] = db_path

        super().__init__(*args, **kwargs)

        self._db_path = db_path

        # Queue of (zoom, x, y, server_url, png_bytes) to write asynchronously
        self._write_queue: queue.Queue = queue.Queue(maxsize=2000)

        # Track keys already confirmed to be in DB to avoid redundant INSERT attempts
        self._db_known: set = set()

        if db_path:
            self._init_db_schema()
            self._writer_thread = threading.Thread(
                target=self._write_worker,
                daemon=True,
                name="TileCache-Writer",
            )
            self._writer_thread.start()
            logger.info(f"[CachingTileMapView] Write-through cache active → {db_path}")

    # ------------------------------------------------------------------
    # DB initialisation
    # ------------------------------------------------------------------

    def _init_db_schema(self):
        """Create tables if they don't exist and set WAL mode."""
        try:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS server (
                    url      VARCHAR(300) PRIMARY KEY NOT NULL,
                    max_zoom INTEGER      NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tiles (
                    zoom       INTEGER      NOT NULL,
                    x          INTEGER      NOT NULL,
                    y          INTEGER      NOT NULL,
                    server     VARCHAR(300) NOT NULL,
                    tile_image BLOB         NOT NULL,
                    CONSTRAINT pk_tiles PRIMARY KEY (zoom, x, y, server)
                );
                """
            )
            conn.commit()
            conn.close()
            logger.info("[CachingTileMapView] DB schema initialised.")
        except sqlite3.Error as e:
            logger.error(f"[CachingTileMapView] Failed to init DB schema: {e}")

    # ------------------------------------------------------------------
    # Background write worker
    # ------------------------------------------------------------------

    def _write_worker(self):
        """
        Single writer thread that drains the write queue into SQLite.
        Uses WAL mode so the 25 reader threads opened by the parent are never blocked.
        """
        try:
            conn = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "PRAGMA synchronous=NORMAL"
            )  # Faster than FULL, still safe with WAL
            cursor = conn.cursor()

            # Ensure the server row exists for the current tile server
            # (do it lazily on first write)
            server_registered = False

            while True:
                try:
                    item = self._write_queue.get(timeout=2.0)
                except queue.Empty:
                    continue

                zoom, x, y, server_url, png_bytes = item

                try:
                    if not server_registered:
                        cursor.execute(
                            "INSERT OR IGNORE INTO server (url, max_zoom) VALUES (?, ?)",
                            (server_url, self.max_zoom),
                        )
                        server_registered = True

                    cursor.execute(
                        "INSERT OR IGNORE INTO tiles (zoom, x, y, server, tile_image) VALUES (?, ?, ?, ?, ?)",
                        (zoom, x, y, server_url, png_bytes),
                    )
                    conn.commit()
                    self._db_known.add((zoom, x, y, server_url))

                except sqlite3.Error as e:
                    logger.warning(
                        f"[CachingTileMapView] Write error for ({zoom},{x},{y}): {e}"
                    )
                finally:
                    self._write_queue.task_done()

        except Exception as e:
            logger.error(f"[CachingTileMapView] Writer thread crashed: {e}")

    # ------------------------------------------------------------------
    # Overridden request_image — adds write-back on network download
    # ------------------------------------------------------------------

    def request_image(
        self, zoom: int, x: int, y: int, db_cursor=None
    ) -> ImageTk.PhotoImage:
        """
        Identical logic to the parent, but after a successful network download
        the raw PNG bytes are queued for asynchronous write to the local DB.
        """

        # 1. Check memory cache first (fastest path — avoids DB + network)
        mem_cached = self.tile_image_cache.get(f"{zoom}{x}{y}")
        if mem_cached:
            return mem_cached

        # 2. Check SQLite DB (tiles from previous sessions)
        if db_cursor is not None:
            try:
                db_cursor.execute(
                    "SELECT t.tile_image FROM tiles t WHERE t.zoom=? AND t.x=? AND t.y=? AND t.server=?;",
                    (zoom, x, y, self.tile_server),
                )
                result = db_cursor.fetchone()

                if result is not None:
                    image = Image.open(io.BytesIO(result[0]))
                    image_tk = ImageTk.PhotoImage(image)
                    self.tile_image_cache[f"{zoom}{x}{y}"] = image_tk
                    # Mark as known so we skip the write-back enqueue later
                    self._db_known.add((zoom, x, y, self.tile_server))
                    return image_tk

                elif self.use_database_only:
                    return self.empty_tile_image

            except sqlite3.OperationalError:
                if self.use_database_only:
                    return self.empty_tile_image

            except Exception:
                return self.empty_tile_image

        # 3. Download from network (tile not in DB or DB not configured)
        try:
            url = (
                self.tile_server.replace("{x}", str(x))
                .replace("{y}", str(y))
                .replace("{z}", str(zoom))
            )
            response = requests.get(
                url, stream=True, headers={"User-Agent": "TkinterMapView"}
            )

            # Read the full raw bytes so we can BOTH display and cache them
            raw_bytes = response.content
            image = Image.open(io.BytesIO(raw_bytes))

            # Handle optional overlay tile server
            if self.overlay_tile_server is not None:
                overlay_url = (
                    self.overlay_tile_server.replace("{x}", str(x))
                    .replace("{y}", str(y))
                    .replace("{z}", str(zoom))
                )
                image_overlay = Image.open(
                    requests.get(
                        overlay_url,
                        stream=True,
                        headers={"User-Agent": "TkinterMapView"},
                    ).raw
                )
                image = image.convert("RGBA")
                image_overlay = image_overlay.convert("RGBA")
                if image_overlay.size != (self.tile_size, self.tile_size):
                    image_overlay = image_overlay.resize(
                        (self.tile_size, self.tile_size), Image.LANCZOS
                    )
                image.paste(image_overlay, (0, 0), image_overlay)

                # Re-encode composited image for storage
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                raw_bytes = buf.getvalue()

            if not self.running:
                return self.empty_tile_image

            image_tk = ImageTk.PhotoImage(image)
            self.tile_image_cache[f"{zoom}{x}{y}"] = image_tk

            # --- Write-through: enqueue for background DB persist ---
            if self._db_path and (zoom, x, y, self.tile_server) not in self._db_known:
                try:
                    self._write_queue.put_nowait(
                        (zoom, x, y, self.tile_server, raw_bytes)
                    )
                except queue.Full:
                    pass  # Queue is full (burst scenario) - skip this tile, no problem

            return image_tk

        except PIL.UnidentifiedImageError:
            self.tile_image_cache[f"{zoom}{x}{y}"] = self.empty_tile_image
            return self.empty_tile_image

        except requests.exceptions.ConnectionError:
            return self.empty_tile_image

        except Exception:
            return self.empty_tile_image
