import itertools
import math
import random
import threading
import time
from collections.abc import Callable
from typing import Optional

from src.core.device_manager import DeviceManager
from src.core.models import RoutePoint
from src.utils.logger import logger

# Monotonically-increasing counter used to give each walk run a unique ID.
_gen_counter = itertools.count(1)


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
        batch_completion_callback: Optional[Callable[[], None]] = None,
        disconnect_callback: Optional[Callable[[], None]] = None,
    ):
        self.device_manager = device_manager
        self.update_callback = update_callback
        self.completion_callback = completion_callback
        self.batch_completion_callback = batch_completion_callback
        self.disconnect_callback = disconnect_callback
        self.points: list[RoutePoint] = []
        self.is_walking = False
        self.is_paused = False
        self.stop_requested = False
        self.speed_kmh = 20.0  # Default speed
        self.speed_noise_pct = 0.1  # Percentage of noise to add to speed (0.0 - 1.0)
        self.loop = False
        self.thread: Optional[threading.Thread] = None
        # Generation ID: incremented on every start() / stop() so that a
        # lingering old thread can detect it is stale and skip its finally block.
        self._walk_gen: int = 0

        # Pause/resume synchronisation
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially (set = "go ahead")

        # Resume state: track where we left off
        self._dispatched_index: int = 0
        self._resume_segment_index: int = 0  # which segment to continue from
        self._resume_covered_dist: float = 0.0  # how far into that segment (km)
        self._last_batch_completed_index: int = -1
        self._disconnect_event_sent: bool = False

        # Random temporary stop state
        self.random_stop_enabled = False
        self.random_stop_interval_m = 150.0
        self.random_stop_min_s = 5.0
        self.random_stop_max_s = 20.0
        self._random_stop_active = False
        self._random_stop_remaining_s = 0.0
        self._distance_since_random_stop_km = 0.0
        self._next_random_stop_distance_km = float("inf")
        self.displacement_noise_enabled = False
        self.displacement_radius_m = 3.0
        self._displacement_offset_north_m = 0.0
        self._displacement_offset_east_m = 0.0
        self._displacement_target_north_m = 0.0
        self._displacement_target_east_m = 0.0
        self._distance_since_displacement_target_km = 0.0

    def set_route(self, points: list[RoutePoint]):
        """Set the route points to walk.

        Stores a *live reference* to the list so that points appended by the
        UI after walking has started are automatically picked up at the tail
        of the current run (Append-only / dynamic route).
        """
        self.points = points  # live reference, NOT a copy

    def set_speed(self, speed_kmh: float):
        """Set walking speed in km/h."""
        self.speed_kmh = max(0.1, speed_kmh)

    def set_speed_noise(self, noise_pct: float):
        """Set speed noise percentage (0-100)."""
        self.speed_noise_pct = max(0.0, min(100.0, noise_pct)) / 100.0

    def set_loop(self, loop: bool):
        """Set whether to loop the route."""
        self.loop = loop

    def set_random_stop_settings(
        self,
        enabled: bool,
        interval_m: float,
        duration_min_s: float,
        duration_max_s: float,
    ):
        """Configure random temporary stop behavior for route walking."""
        self.random_stop_enabled = bool(enabled)
        self.random_stop_interval_m = max(1.0, float(interval_m))
        self.random_stop_min_s = max(1.0, float(duration_min_s))
        self.random_stop_max_s = max(self.random_stop_min_s, float(duration_max_s))
        self._distance_since_random_stop_km = 0.0
        self._random_stop_active = False
        self._random_stop_remaining_s = 0.0
        self._schedule_next_random_stop()

    def set_displacement_noise_settings(self, enabled: bool, radius_m: float):
        """Configure smooth in-circle displacement noise around route points."""
        self.displacement_noise_enabled = bool(enabled)
        self.displacement_radius_m = max(0.0, float(radius_m))
        self._displacement_offset_north_m = 0.0
        self._displacement_offset_east_m = 0.0
        self._displacement_target_north_m = 0.0
        self._displacement_target_east_m = 0.0
        self._distance_since_displacement_target_km = 0.0

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

        # Signal any currently-running thread to stop (non-blocking — no join).
        self.stop_requested = True
        self._pause_event.set()  # Unblock a paused thread so it can exit

        # Bump the generation BEFORE resetting state.  The old thread's
        # finally block will see a different gen and won't touch is_walking.
        self._walk_gen = next(_gen_counter)
        my_gen = self._walk_gen

        # Reset state for a fresh start
        self.stop_requested = False
        self.is_paused = False
        self._resume_segment_index = 0
        self._resume_covered_dist = 0.0
        self._dispatched_index = 0  # next point index to start a segment FROM
        self._last_batch_completed_index = -1
        self._disconnect_event_sent = False
        self._distance_since_random_stop_km = 0.0
        self._random_stop_active = False
        self._random_stop_remaining_s = 0.0
        self._schedule_next_random_stop()
        self._distance_since_displacement_target_km = 0.0
        self._displacement_offset_north_m = 0.0
        self._displacement_offset_east_m = 0.0
        self._displacement_target_north_m = 0.0
        self._displacement_target_east_m = 0.0

        self.is_walking = True
        self.thread = threading.Thread(
            target=self._walk_loop, args=(my_gen,), daemon=True
        )
        self.thread.start()

    def stop(self):
        """Signal the walker to stop immediately (non-blocking — no thread join)."""
        # Bump generation first so the thread's finally won't overwrite our reset.
        self._walk_gen = next(_gen_counter)
        self.stop_requested = True
        self._pause_event.set()  # Unblock if paused so thread can exit
        self.is_walking = False
        self.is_paused = False
        self._resume_segment_index = 0
        self._resume_covered_dist = 0.0
        self._dispatched_index = 0
        self._last_batch_completed_index = -1
        self._disconnect_event_sent = False
        self._distance_since_random_stop_km = 0.0
        self._random_stop_active = False
        self._random_stop_remaining_s = 0.0
        self._next_random_stop_distance_km = float("inf")
        self._distance_since_displacement_target_km = 0.0
        self._displacement_offset_north_m = 0.0
        self._displacement_offset_east_m = 0.0
        self._displacement_target_north_m = 0.0
        self._displacement_target_east_m = 0.0
        logger.info("RouteWalker stop signalled")

    def _walk_loop(self, my_gen: int):
        """Main walking loop – owns exactly one generation token (my_gen).

        Append-only dynamic route:
          self.points is a *live reference* to the UI's route list.
          After each segment we re-check len(self.points) so that any points
          appended by the user mid-walk are automatically walked at the tail.
        """
        logger.info(
            f"Walk gen={my_gen} started. Speed: {self.speed_kmh} km/h, Loop: {self.loop}"
        )

        try:
            while not self.stop_requested:
                # --- Handle the single-point edge case ---
                if len(self.points) == 1 and self._dispatched_index == 0:
                    pt = self.points[0]
                    self.device_manager.set_location(pt.latitude, pt.longitude)
                    self.update_callback(pt.latitude, pt.longitude)
                    time.sleep(1)
                    if not self.loop:
                        break
                    continue

                if len(self.points) < 2:
                    # Nothing to walk yet; wait a bit and retry
                    time.sleep(0.2)
                    continue

                # --- Walk every pending segment ---
                # _dispatched_index is the index of the point we are currently
                # AT (i.e. the start of the next segment to walk).
                # Resume support: _resume_segment_index may push us further in.
                i = max(self._dispatched_index, self._resume_segment_index)

                while not self.stop_requested:
                    # Dynamically read the live list length each iteration
                    if i >= len(self.points) - 1:
                        # No more segments available right now
                        break

                    self._resume_segment_index = i
                    start_pt = self.points[i]
                    end_pt = self.points[i + 1]
                    segment_completed = self._walk_segment(start_pt, end_pt)
                    if not segment_completed:
                        # Do not advance head index if segment could not complete
                        # (e.g. paused/disconnected/stop requested).
                        break

                    # Segment done — advance the head pointer
                    self._resume_covered_dist = 0.0
                    i += 1
                    self._dispatched_index = i

                if self.stop_requested:
                    break
                if self.is_paused:
                    # Paused (including disconnect-triggered pause): keep waiting.
                    time.sleep(0.2)
                    continue

                # All current segments are done.
                if self.loop:
                    # Loop: restart from the beginning
                    self._dispatched_index = 0
                    self._resume_segment_index = 0
                    self._resume_covered_dist = 0.0
                    logger.info(f"Walk gen={my_gen} looping back to start")
                else:
                    # We completed the currently available route batch.
                    # Fire exactly once per consumed head index so UI can notify.
                    if (
                        self.batch_completion_callback
                        and self._dispatched_index > 0
                        and self._dispatched_index != self._last_batch_completed_index
                    ):
                        self._last_batch_completed_index = self._dispatched_index
                        self.batch_completion_callback()

                    # Non-loop: stay idle but keep watching for new appended points.
                    # We park here until either stop() is called or a new point
                    # is appended (len grows beyond _dispatched_index).
                    while not self.stop_requested:
                        if len(self.points) > self._dispatched_index + 1:
                            # New point(s) appended — resume from current head
                            logger.info(
                                f"Walk gen={my_gen}: new point(s) detected, continuing"
                            )
                            break
                        time.sleep(0.3)

        except Exception as e:
            logger.error(f"Walk gen={my_gen} error: {e}")
        finally:
            # Only update shared state if we are still the active generation.
            # If start() or stop() was called after us, _walk_gen was already
            # bumped and is_walking was already set correctly — don't touch it.
            if self._walk_gen == my_gen:
                self.is_walking = False
                if self.completion_callback and not self.stop_requested:
                    self.completion_callback()
            logger.info(f"Walk gen={my_gen} finished")

    def _walk_segment(self, start: RoutePoint, end: RoutePoint) -> bool:
        """Walk between two route points with interpolation and pause support."""
        dist_km = self._haversine_distance(
            start.latitude, start.longitude, end.latitude, end.longitude
        )

        if dist_km == 0:
            return True

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
                return False

            if self._random_stop_active:
                fraction = covered_dist / total_dist
                hold_lat = start.latitude + (end.latitude - start.latitude) * fraction
                hold_lon = start.longitude + (end.longitude - start.longitude) * fraction
                self.update_callback(hold_lat, hold_lon)
                time.sleep(update_interval)
                self._tick_random_stop(update_interval)
                continue

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
            new_lat, new_lon = self._apply_displacement_noise(
                new_lat, new_lon, step_dist
            )

            # 6. Send location update
            if not self.device_manager.set_location(new_lat, new_lon):
                # Device disconnected or location update failed: auto-pause walker.
                self._pause_event.clear()
                self.is_paused = True
                if self.disconnect_callback and not self._disconnect_event_sent:
                    self._disconnect_event_sent = True
                    self.disconnect_callback()
                logger.warning("RouteWalker paused due to device disconnection")
                return False

            # Any successful location update clears one-shot disconnect notification lock.
            self._disconnect_event_sent = False
            self.update_callback(new_lat, new_lon)
            self._advance_random_stop_trigger(step_dist)

            time.sleep(update_interval)

        return True

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

    def _schedule_next_random_stop(self):
        if not self.random_stop_enabled:
            self._next_random_stop_distance_km = float("inf")
            return

        avg_interval_km = self.random_stop_interval_m / 1000.0
        multiplier = random.uniform(0.7, 1.3)
        self._next_random_stop_distance_km = avg_interval_km * multiplier

    def _advance_random_stop_trigger(self, step_dist_km: float) -> bool:
        if (
            not self.random_stop_enabled
            or self._random_stop_active
            or self._next_random_stop_distance_km == float("inf")
        ):
            return False

        self._distance_since_random_stop_km += step_dist_km
        if self._distance_since_random_stop_km < self._next_random_stop_distance_km:
            return False

        self._distance_since_random_stop_km = 0.0
        self._random_stop_active = True
        self._random_stop_remaining_s = random.uniform(
            self.random_stop_min_s, self.random_stop_max_s
        )
        self._schedule_next_random_stop()
        return True

    def _tick_random_stop(self, elapsed_s: float) -> bool:
        if not self._random_stop_active:
            return False

        self._random_stop_remaining_s = max(
            0.0, self._random_stop_remaining_s - elapsed_s
        )
        if self._random_stop_remaining_s == 0.0:
            self._random_stop_active = False
            return False
        return True

    def _apply_displacement_noise(
        self, latitude: float, longitude: float, step_dist_km: float
    ) -> tuple[float, float]:
        if not self.displacement_noise_enabled or self.displacement_radius_m <= 0:
            return latitude, longitude

        self._distance_since_displacement_target_km += step_dist_km
        refresh_distance_km = max(self.displacement_radius_m * 1.5, 1.0) / 1000.0
        if (
            self._distance_since_displacement_target_km >= refresh_distance_km
            or (
                self._displacement_target_north_m == 0.0
                and self._displacement_target_east_m == 0.0
                and self._displacement_offset_north_m == 0.0
                and self._displacement_offset_east_m == 0.0
            )
        ):
            self._distance_since_displacement_target_km = 0.0
            self._sample_displacement_target()

        step_dist_m = step_dist_km * 1000.0
        alpha = min(0.35, max(0.08, step_dist_m / max(self.displacement_radius_m, 1.0)))
        self._displacement_offset_north_m += (
            self._displacement_target_north_m - self._displacement_offset_north_m
        ) * alpha
        self._displacement_offset_east_m += (
            self._displacement_target_east_m - self._displacement_offset_east_m
        ) * alpha

        offset_norm = math.hypot(
            self._displacement_offset_north_m, self._displacement_offset_east_m
        )
        if offset_norm > self.displacement_radius_m:
            scale = self.displacement_radius_m / offset_norm
            self._displacement_offset_north_m *= scale
            self._displacement_offset_east_m *= scale

        return self._offset_lat_lon(
            latitude,
            longitude,
            self._displacement_offset_north_m,
            self._displacement_offset_east_m,
        )

    def _sample_displacement_target(self):
        radius = random.uniform(0.0, self.displacement_radius_m)
        angle = random.uniform(0.0, math.tau)
        self._displacement_target_north_m = math.cos(angle) * radius
        self._displacement_target_east_m = math.sin(angle) * radius

    def _offset_lat_lon(
        self, latitude: float, longitude: float, north_m: float, east_m: float
    ) -> tuple[float, float]:
        lat_delta = north_m / 111320.0
        lon_scale = max(0.000001, math.cos(math.radians(latitude)) * 111320.0)
        lon_delta = east_m / lon_scale
        return latitude + lat_delta, longitude + lon_delta

    def get_progress_snapshot(self) -> dict[str, int | float | bool]:
        """Return lightweight progress state for UI summaries."""
        return {
            "is_walking": self.is_walking,
            "is_paused": self.is_paused,
            "dispatched_index": self._dispatched_index,
            "resume_segment_index": self._resume_segment_index,
            "resume_covered_dist_km": self._resume_covered_dist,
            "random_stop_active": self._random_stop_active,
            "random_stop_remaining_s": self._random_stop_remaining_s,
        }
