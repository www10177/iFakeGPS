import math
import random
import threading
import time
from typing import Callable, List, Optional

from src.core.device_manager import DeviceManager
from src.core.models import RoutePoint
from src.utils.logger import logger


class RouteWalker:
    """
    Handles walking along a route of points with realistic speed and movement.
    Supports pause/resume from the exact position mid-segment.
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        update_callback: Callable[[float, float], None],
        completion_callback: Optional[Callable[[], None]] = None,
    ):
        self.device_manager = device_manager
        self.update_callback = update_callback
        self.completion_callback = completion_callback
        self.points: List[RoutePoint] = []
        self.is_walking = False
        self.is_paused = False
        self.stop_requested = False
        self.speed_kmh = 5.0  # Default speed
        self.speed_noise_pct = 0.0  # Percentage of noise to add to speed (0.0 - 1.0)
        self.loop = False
        self.thread: Optional[threading.Thread] = None

        # Pause/resume synchronisation
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially (set = "go ahead")

        # Resume state: track where we left off
        self._resume_segment_index: int = 0  # which segment to continue from
        self._resume_covered_dist: float = 0.0  # how far into that segment (km)

    def set_route(self, points: List[RoutePoint]):
        """Set the route points to walk."""
        self.points = points

    def set_speed(self, speed_kmh: float):
        """Set walking speed in km/h."""
        self.speed_kmh = max(0.1, speed_kmh)

    def set_speed_noise(self, noise_pct: float):
        """Set speed noise percentage (0-100)."""
        self.speed_noise_pct = max(0.0, min(100.0, noise_pct)) / 100.0

    def set_loop(self, loop: bool):
        """Set whether to loop the route."""
        self.loop = loop

    def pause(self):
        """Pause walking at the current position. Resume with resume()."""
        if self.is_walking and not self.is_paused:
            self._pause_event.clear()  # Block the walk loop
            self.is_paused = True
            logger.info("RouteWalker paused")

    def resume(self):
        """Resume walking from where it was paused."""
        if self.is_walking and self.is_paused:
            self._pause_event.set()  # Unblock the walk loop
            self.is_paused = False
            logger.info("RouteWalker resumed")

    def start(self):
        """Start walking the route from the beginning."""
        if len(self.points) < 1:
            return

        if self.is_walking:
            self.stop()

        # Reset state for a fresh start
        self.stop_requested = False
        self.is_paused = False
        self._pause_event.set()  # Ensure not paused
        self._resume_segment_index = 0
        self._resume_covered_dist = 0.0

        self.is_walking = True
        self.thread = threading.Thread(target=self._walk_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop walking and reset position state."""
        self.stop_requested = True
        self._pause_event.set()  # Unblock if paused so thread can exit
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.is_walking = False
        self.is_paused = False
        self._resume_segment_index = 0
        self._resume_covered_dist = 0.0

    def _walk_loop(self):
        """Main walking loop - supports resuming from a saved segment + progress."""
        logger.info(f"Starting walk. Speed: {self.speed_kmh} km/h, Loop: {self.loop}")

        try:
            while not self.stop_requested:
                points_to_walk = list(self.points)
                if len(points_to_walk) < 1:
                    break

                # If only one point, just teleport there
                if len(points_to_walk) == 1:
                    pt = points_to_walk[0]
                    self.device_manager.set_location(pt.latitude, pt.longitude)
                    self.update_callback(pt.latitude, pt.longitude)
                    time.sleep(1)
                    if not self.loop:
                        break
                    continue

                # Walk through segments, starting from saved resume index
                start_idx = self._resume_segment_index
                for i in range(start_idx, len(points_to_walk) - 1):
                    if self.stop_requested:
                        break

                    self._resume_segment_index = i
                    start_pt = points_to_walk[i]
                    end_pt = points_to_walk[i + 1]
                    self._walk_segment(start_pt, end_pt)
                    # After a segment finishes, clear the intra-segment progress
                    self._resume_covered_dist = 0.0

                # Reset segment index for next loop iteration (if looping)
                self._resume_segment_index = 0
                self._resume_covered_dist = 0.0

                if not self.loop or self.stop_requested:
                    break
        except Exception as e:
            logger.error(f"Error in walk loop: {e}")
        finally:
            self.is_walking = False
            if self.completion_callback and not self.stop_requested:
                self.completion_callback()
            logger.info("Walk finished/stopped")

    def _walk_segment(self, start: RoutePoint, end: RoutePoint):
        """Walk between two route points with interpolation and pause support."""
        dist_km = self._haversine_distance(
            start.latitude, start.longitude, end.latitude, end.longitude
        )

        if dist_km == 0:
            return

        # Update frequency: 2Hz (every 0.5s) is responsive enough for USB
        update_interval = 0.5

        total_dist = dist_km
        # Resume intra-segment progress if we paused mid-segment
        covered_dist = self._resume_covered_dist

        while covered_dist < total_dist:
            # --- Pause checkpoint ---
            # If paused, _pause_event is cleared. wait() blocks here until resume() sets it.
            self._pause_event.wait()

            if self.stop_requested:
                break

            # 1. Determine speed for this step
            step_speed = self.speed_kmh
            if self.speed_noise_pct > 0:
                noise = (
                    (random.random() * 2 - 1) * self.speed_noise_pct * self.speed_kmh
                )
                step_speed = max(0.1, step_speed + noise)

            # 2. Calculate distance for this time step
            step_dist = step_speed * (update_interval / 3600)

            # 3. Update covered distance
            covered_dist += step_dist
            if covered_dist > total_dist:
                covered_dist = total_dist

            # 4. Save progress for potential pause/resume
            self._resume_covered_dist = covered_dist

            # 5. Interpolate new coordinate
            fraction = covered_dist / total_dist
            new_lat = start.latitude + (end.latitude - start.latitude) * fraction
            new_lon = start.longitude + (end.longitude - start.longitude) * fraction

            # 6. Send location update
            self.device_manager.set_location(new_lat, new_lon)
            self.update_callback(new_lat, new_lon)

            time.sleep(update_interval)

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate haversine distance between two points in km."""
        R = 6371  # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
