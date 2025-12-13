#!/usr/bin/env python3
"""
iFakeGPS - A GUI application for simulating GPS location on iOS devices (iOS 17+)
Uses pymobiledevice3 for device communication and location simulation.
Requires running tunneld service for device discovery.
"""

import asyncio
import logging
import math
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from tkinter import messagebox
from typing import List, Optional

import customtkinter as ctk
import tkintermapview

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AppMode(Enum):
    SINGLE_POINT = "single"
    ROUTE = "route"


@dataclass
class DeviceInfo:
    """Represents an iOS device"""

    udid: str
    name: str
    product_type: str
    ios_version: str
    rsd_address: str
    rsd_port: int

    def display_name(self) -> str:
        return f"{self.name} ({self.product_type} - iOS {self.ios_version})"


@dataclass
class RoutePoint:
    """Represents a point on the route"""

    latitude: float
    longitude: float
    marker: Optional[object] = None


class TunneldManager:
    """
    Manages the tunneld service for iOS 17+ device connections.
    Automatically starts tunneld if not running.
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._output_thread: Optional[threading.Thread] = None
        self.on_device_detected: Optional[callable] = None
        self.on_status_change: Optional[callable] = None

    @staticmethod
    def is_admin() -> bool:
        """Check if running with administrator privileges."""
        try:
            if sys.platform == "win32":
                import ctypes

                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                import os

                return os.geteuid() == 0
        except Exception:
            return False

    def is_tunneld_running(self) -> bool:
        """Check if tunneld is already running by trying to connect to its API."""
        try:
            import requests

            # The tunneld API uses / (root) endpoint, not /list-tunnels
            response = requests.get("http://127.0.0.1:49151/", timeout=1)
            return response.status_code == 200
        except Exception:
            return False

    def start(self) -> bool:
        """Start the tunneld service."""
        if self.is_tunneld_running():
            logger.info("tunneld is already running")
            self.running = True
            return True

        try:
            # Start tunneld as a subprocess
            # Note: This may require admin privileges
            python_exec = sys.executable

            # Create the process with CREATE_NEW_CONSOLE flag on Windows to avoid blocking
            if sys.platform == "win32":
                # On Windows, we need to run with proper privileges
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                self.process = subprocess.Popen(
                    [python_exec, "-m", "pymobiledevice3", "remote", "tunneld"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self.process = subprocess.Popen(
                    [python_exec, "-m", "pymobiledevice3", "remote", "tunneld"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            self.running = True
            logger.info("Started tunneld service")

            # Start output monitoring thread
            self._output_thread = threading.Thread(
                target=self._monitor_output, daemon=True
            )
            self._output_thread.start()

            # Wait a moment for tunneld to initialize
            time.sleep(2)

            return True

        except Exception as e:
            logger.error(f"Failed to start tunneld: {e}")
            self.running = False
            return False

    def _monitor_output(self):
        """Monitor tunneld output for device connections."""
        if not self.process:
            return

        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    decoded = line.decode("utf-8", errors="ignore").strip()
                    logger.debug(f"tunneld: {decoded}")

                    # Check for device connection events
                    if (
                        "tunnel created" in decoded.lower()
                        or "device" in decoded.lower()
                    ):
                        if self.on_device_detected:
                            self.on_device_detected()
        except Exception as e:
            logger.warning(f"tunneld output monitor error: {e}")

        self.running = False
        if self.on_status_change:
            self.on_status_change(False)

    def stop(self):
        """Stop the tunneld service."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.running = False
        logger.info("Stopped tunneld service")

    def restart(self) -> bool:
        """Restart the tunneld service."""
        self.stop()
        time.sleep(1)
        return self.start()


class DeviceManager:
    """
    Manages iOS device connection and location simulation using pymobiledevice3.
    Supports iOS 17+ via the RSD tunnel mechanism.
    """

    def __init__(self):
        self.service_provider = None
        self.connected = False
        self.current_device: Optional[DeviceInfo] = None
        self._lock = threading.Lock()
        # Keep DVT service alive to prevent location reset
        self._dvt_service = None
        self._location_sim = None

    @staticmethod
    def discover_devices() -> List[DeviceInfo]:
        """
        Discover connected iOS devices via tunneld.
        Returns a list of DeviceInfo objects.
        """
        devices = []
        try:
            import requests
            from pymobiledevice3.lockdown import create_using_usbmux

            # Try to get devices from tunneld HTTP API (root endpoint /)
            try:
                response = requests.get("http://127.0.0.1:49151/", timeout=2)
                if response.status_code == 200:
                    tunnels_data = response.json()
                    # Response format: {UDID: [{tunnel-address, tunnel-port, interface}, ...]}
                    for udid, tunnel_list in tunnels_data.items():
                        if not tunnel_list:
                            continue
                        # Use the first tunnel for each device
                        tunnel_info = (
                            tunnel_list[0]
                            if isinstance(tunnel_list, list)
                            else tunnel_list
                        )
                        try:
                            rsd_address = tunnel_info.get("tunnel-address", "")
                            rsd_port = tunnel_info.get("tunnel-port", 0)

                            if rsd_address and rsd_port:
                                # Try to get device name from lockdown
                                device_name = f"iOS Device ({udid[:8]}...)"
                                product_type = "Unknown"
                                ios_version = "17+"

                                try:
                                    lockdown = create_using_usbmux(serial=udid)
                                    device_name = (
                                        lockdown.display_name
                                        or lockdown.get_value(key="DeviceName")
                                        or device_name
                                    )
                                    product_type = lockdown.product_type or product_type
                                    ios_version = (
                                        lockdown.product_version or ios_version
                                    )
                                    lockdown.close()
                                except Exception:
                                    # If lockdown fails, use defaults
                                    pass

                                device_info = DeviceInfo(
                                    udid=udid,
                                    name=device_name,
                                    product_type=product_type,
                                    ios_version=ios_version,
                                    rsd_address=rsd_address,
                                    rsd_port=rsd_port,
                                )
                                devices.append(device_info)
                                logger.info(
                                    f"Found device: {device_name} ({product_type} - iOS {ios_version})"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to parse tunnel info: {e}")
            except requests.exceptions.ConnectionError:
                logger.warning("tunneld HTTP API not available on port 49151")
            except Exception as e:
                logger.warning(f"Failed to get devices from tunneld API: {e}")

        except ImportError as e:
            logger.warning(f"pymobiledevice3.tunneld import issue: {e}")
        except Exception as e:
            logger.error(f"Failed to discover devices: {e}")

        return devices

    @staticmethod
    def discover_devices_via_browse() -> List[DeviceInfo]:
        """
        Alternative discovery using usbmux to find connected devices.
        Gets device name from lockdown and checks for tunnel availability.
        """
        devices = []
        try:
            import requests
            from pymobiledevice3.lockdown import create_using_usbmux
            from pymobiledevice3.usbmux import list_devices

            # Get list of USB-connected devices
            usb_devices = list_devices()

            # Try to get device info for each
            for usb_dev in usb_devices:
                try:
                    # Get device info from lockdown
                    device_name = "iOS Device"
                    product_type = "Unknown"
                    ios_version = "17+"

                    try:
                        lockdown = create_using_usbmux(serial=usb_dev.serial)
                        device_name = (
                            lockdown.display_name
                            or lockdown.get_value(key="DeviceName")
                            or "iOS Device"
                        )
                        product_type = lockdown.product_type or "Unknown"
                        ios_version = lockdown.product_version or "17+"
                        lockdown.close()
                    except Exception as e:
                        logger.warning(
                            f"Could not get lockdown info for {usb_dev.serial[:8]}: {e}"
                        )

                    # Try to get tunnel from tunneld API (root endpoint /)
                    rsd_address = ""
                    rsd_port = 0
                    try:
                        response = requests.get("http://127.0.0.1:49151/", timeout=2)
                        if response.status_code == 200:
                            tunnels = response.json()
                            # Response format: {UDID: [{tunnel-address, tunnel-port, interface}, ...]}
                            if usb_dev.serial in tunnels:
                                tunnel_list = tunnels[usb_dev.serial]
                                if tunnel_list:
                                    tunnel_info = (
                                        tunnel_list[0]
                                        if isinstance(tunnel_list, list)
                                        else tunnel_list
                                    )
                                    rsd_address = tunnel_info.get("tunnel-address", "")
                                    rsd_port = tunnel_info.get("tunnel-port", 0)
                    except Exception:
                        pass

                    # Only add device if we have valid RSD address
                    if rsd_address and rsd_port:
                        device_info = DeviceInfo(
                            udid=usb_dev.serial,
                            name=device_name,
                            product_type=product_type,
                            ios_version=ios_version,
                            rsd_address=rsd_address,
                            rsd_port=rsd_port,
                        )
                        devices.append(device_info)
                        logger.info(
                            f"Found device: {device_name} ({product_type} - iOS {ios_version})"
                        )
                    else:
                        logger.warning(
                            f"Device {device_name} found but no tunnel available. "
                            "Start tunneld with admin privileges: "
                            "run start_tunneld.bat as Administrator"
                        )

                except Exception as e:
                    logger.warning(f"Failed to process USB device: {e}")

        except Exception as e:
            logger.error(f"Failed to browse devices: {e}")

        return devices

    def connect_to_device(self, device: DeviceInfo) -> bool:
        """
        Connect to a specific iOS device via RSD tunnel.
        """
        try:
            from pymobiledevice3.remote.remote_service_discovery import (
                RemoteServiceDiscoveryService,
            )

            with self._lock:
                # Disconnect if already connected
                if self.service_provider:
                    try:
                        # Handle async close
                        close_result = self.service_provider.close()
                        if asyncio.iscoroutine(close_result):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(close_result)
                            finally:
                                loop.close()
                    except Exception:
                        pass
                    self.service_provider = None

                # Create RSD connection
                self.service_provider = RemoteServiceDiscoveryService(
                    (device.rsd_address, device.rsd_port)
                )

                # Handle async connect - create new event loop for this thread
                connect_result = self.service_provider.connect()
                if asyncio.iscoroutine(connect_result):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(connect_result)
                    finally:
                        loop.close()

                self.current_device = device
                self.connected = True
                logger.info(f"Connected to device: {device.display_name()}")
                return True

        except Exception as e:
            logger.error(f"Failed to connect to device: {e}")
            self.connected = False
            self.current_device = None
            return False

    def connect_via_rsd(self, host: str, port: int) -> bool:
        """
        Connect to iOS device via RSD tunnel manually.
        """
        try:
            from pymobiledevice3.remote.remote_service_discovery import (
                RemoteServiceDiscoveryService,
            )

            with self._lock:
                # Disconnect if already connected
                if self.service_provider:
                    try:
                        close_result = self.service_provider.close()
                        if asyncio.iscoroutine(close_result):
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(close_result)
                            finally:
                                loop.close()
                    except Exception:
                        pass
                    self.service_provider = None

                # Create RSD connection
                self.service_provider = RemoteServiceDiscoveryService((host, port))

                # Handle async connect
                connect_result = self.service_provider.connect()
                if asyncio.iscoroutine(connect_result):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(connect_result)
                    finally:
                        loop.close()

                # Try to get device info
                try:
                    self.current_device = DeviceInfo(
                        udid=self.service_provider.udid or "Unknown",
                        name=getattr(self.service_provider, "name", None)
                        or "iOS Device",
                        product_type=getattr(
                            self.service_provider, "product_type", None
                        )
                        or "Unknown",
                        ios_version=getattr(
                            self.service_provider, "product_version", None
                        )
                        or "Unknown",
                        rsd_address=host,
                        rsd_port=port,
                    )
                except Exception:
                    self.current_device = DeviceInfo(
                        udid="Unknown",
                        name="iOS Device",
                        product_type="Unknown",
                        ios_version="17+",
                        rsd_address=host,
                        rsd_port=port,
                    )

                self.connected = True
                logger.info(f"Connected to device via RSD at {host}:{port}")
                return True

        except Exception as e:
            logger.error(f"Failed to connect via RSD: {e}")
            self.connected = False
            self.current_device = None
            return False

    def set_location(self, latitude: float, longitude: float) -> bool:
        """
        Set the simulated GPS location on the device.
        """
        try:
            from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import (
                DvtSecureSocketProxyService,
            )
            from pymobiledevice3.services.dvt.instruments.location_simulation import (
                LocationSimulation,
            )

            with self._lock:
                if not self.connected or self.service_provider is None:
                    logger.error("Device not connected")
                    return False

                # Create or reuse DVT service to keep location simulation alive
                if self._dvt_service is None:
                    self._dvt_service = DvtSecureSocketProxyService(
                        self.service_provider
                    )
                    self._dvt_service.__enter__()
                    self._location_sim = LocationSimulation(self._dvt_service)
                    logger.info(
                        "Created persistent DVT connection for location simulation"
                    )

                self._location_sim.set(latitude, longitude)
                logger.info(f"Location set to: {latitude}, {longitude}")
                return True

        except Exception as e:
            logger.error(f"Failed to set location: {e}")
            # Reset DVT service on error so it can be recreated
            self._close_dvt_service()
            return False

    def _close_dvt_service(self):
        """Close the DVT service if open."""
        if self._dvt_service is not None:
            try:
                self._dvt_service.__exit__(None, None, None)
            except Exception:
                pass
            self._dvt_service = None
            self._location_sim = None

    def clear_location(self) -> bool:
        """
        Clear the simulated location.
        """
        try:
            with self._lock:
                if not self.connected or self.service_provider is None:
                    logger.error("Device not connected")
                    return False

                # Use existing location sim if available
                if self._location_sim is not None:
                    self._location_sim.clear()
                    logger.info("Location simulation cleared")
                    # Close the DVT service since we're done
                    self._close_dvt_service()
                    return True
                else:
                    # No active location sim, nothing to clear
                    logger.info("No active location simulation to clear")
                    return True

        except Exception as e:
            logger.error(f"Failed to clear location: {e}")
            self._close_dvt_service()
            return False

    def disconnect(self):
        """Disconnect from the device."""
        with self._lock:
            # Close DVT service first
            self._close_dvt_service()

            if self.service_provider:
                try:
                    close_result = self.service_provider.close()
                    if asyncio.iscoroutine(close_result):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(close_result)
                        finally:
                            loop.close()
                except Exception:
                    pass
                self.service_provider = None
            self.connected = False
            self.current_device = None
            logger.info("Disconnected from device")


class RouteWalker:
    """
    Handles walking along a route by interpolating between waypoints.
    """

    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.route: list[RoutePoint] = []
        self.walking = False
        self.paused = False
        self.current_index = 0
        self.current_position: Optional[tuple[float, float]] = None
        self.speed_mps = 1.4  # Default walking speed in meters per second (5 km/h)
        self.noise_percent = 0  # Speed noise as percentage (0-50)
        self._walk_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.on_position_update: Optional[callable] = None
        self.on_walk_complete: Optional[callable] = None

    def set_route(self, points: list[RoutePoint]):
        """Set the route to walk."""
        self.route = points
        self.current_index = 0
        if points:
            self.current_position = (points[0].latitude, points[0].longitude)

    def set_speed(self, speed_mps: float):
        """Set walking speed in meters per second."""
        self.speed_mps = max(0.1, min(speed_mps, 100))  # Clamp between 0.1 and 100 m/s

    def set_noise(self, noise_percent: float):
        """Set speed noise as percentage (0-50)."""
        self.noise_percent = max(0, min(noise_percent, 50))

    def get_current_speed(self) -> float:
        """Get current speed with optional noise applied."""
        import random

        if self.noise_percent > 0:
            noise_factor = 1 + (random.uniform(-1, 1) * self.noise_percent / 100)
            return self.speed_mps * noise_factor
        return self.speed_mps

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points in meters."""
        R = 6371000  # Earth's radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @staticmethod
    def interpolate_position(
        lat1: float, lon1: float, lat2: float, lon2: float, fraction: float
    ) -> tuple[float, float]:
        """Linear interpolation between two positions."""
        return (lat1 + (lat2 - lat1) * fraction, lon1 + (lon2 - lon1) * fraction)

    def start_walking(self, loop: bool = False):
        """Start walking the route."""
        if not self.route or len(self.route) < 2:
            logger.warning("Route must have at least 2 points")
            return

        self._stop_event.clear()
        self.walking = True
        self.paused = False

        self._walk_thread = threading.Thread(
            target=self._walk_route, args=(loop,), daemon=True
        )
        self._walk_thread.start()

    def _walk_route(self, loop: bool):
        """Internal method to walk the route."""
        update_interval = 0.5  # Update position every 0.5 seconds

        while not self._stop_event.is_set():
            if self.paused:
                time.sleep(0.1)
                continue

            if self.current_index >= len(self.route) - 1:
                if loop:
                    self.current_index = 0
                else:
                    self.walking = False
                    if self.on_walk_complete:
                        self.on_walk_complete()
                    break

            start_point = self.route[self.current_index]
            end_point = self.route[self.current_index + 1]

            distance = self.haversine_distance(
                start_point.latitude,
                start_point.longitude,
                end_point.latitude,
                end_point.longitude,
            )

            if distance < 0.1:  # Skip very short segments
                self.current_index += 1
                continue

            # Walk this segment with dynamic speed updates
            distance_traveled = 0.0

            while distance_traveled < distance:
                if self._stop_event.is_set():
                    break

                while self.paused and not self._stop_event.is_set():
                    time.sleep(0.1)

                if self._stop_event.is_set():
                    break

                # Calculate current position based on distance traveled
                fraction = distance_traveled / distance
                lat, lon = self.interpolate_position(
                    start_point.latitude,
                    start_point.longitude,
                    end_point.latitude,
                    end_point.longitude,
                    fraction,
                )

                self.current_position = (lat, lon)

                # Update device location
                self.device_manager.set_location(lat, lon)

                # Notify UI
                if self.on_position_update:
                    self.on_position_update(lat, lon)

                time.sleep(update_interval)

                # Use current speed with noise (dynamically updated from slider)
                distance_traveled += self.get_current_speed() * update_interval

            self.current_index += 1

        self.walking = False
        logger.info("Walking stopped")

    def pause(self):
        """Pause walking."""
        self.paused = True

    def resume(self):
        """Resume walking."""
        self.paused = False

    def stop(self):
        """Stop walking completely."""
        self._stop_event.set()
        self.walking = False
        self.paused = False
        if self._walk_thread:
            self._walk_thread.join(timeout=2)


class iFakeGPSApp(ctk.CTk):
    """
    Main application window for iFakeGPS.
    """

    def __init__(self):
        super().__init__()

        # Configure window
        self.title("iFakeGPS - iOS Location Simulator")
        self.geometry("1400x900")
        self.minsize(1200, 700)

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize tunneld manager
        self.tunneld_manager = TunneldManager()
        self.tunneld_manager.on_device_detected = self._on_tunneld_device_detected
        self.tunneld_manager.on_status_change = self._on_tunneld_status_change

        # Initialize managers
        self.device_manager = DeviceManager()
        self.route_walker = RouteWalker(self.device_manager)
        self.route_walker.on_position_update = self._on_position_update
        self.route_walker.on_walk_complete = self._on_walk_complete

        # State
        self.mode = AppMode.SINGLE_POINT
        self.route_points: list[RoutePoint] = []
        self.route_path = None  # Map path object
        self.current_position_marker = None
        self.discovered_devices: List[DeviceInfo] = []

        # Build UI
        self._create_ui()

        # Bind events
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-start tunneld and discover devices on startup
        self.after(500, self._start_tunneld_and_discover)

    def _create_ui(self):
        """Create the main UI layout."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create left sidebar
        self._create_sidebar()

        # Create main map area
        self._create_map_area()

        # Create bottom status bar
        self._create_status_bar()

    def _create_sidebar(self):
        """Create the left sidebar with controls."""
        sidebar = ctk.CTkFrame(self, width=350, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_rowconfigure(10, weight=1)

        # App title
        title_label = ctk.CTkLabel(
            sidebar, text="📍 iFakeGPS", font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 5))

        subtitle_label = ctk.CTkLabel(
            sidebar,
            text="iOS 17+ Location Simulator",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15))

        # Device selection section
        device_frame = ctk.CTkFrame(sidebar)
        device_frame.grid(row=2, column=0, padx=15, pady=10, sticky="ew")

        device_header = ctk.CTkFrame(device_frame, fg_color="transparent")
        device_header.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        device_header.grid_columnconfigure(0, weight=1)

        device_label = ctk.CTkLabel(
            device_header,
            text="📱 Device Selection",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        device_label.grid(row=0, column=0, sticky="w")

        self.refresh_btn = ctk.CTkButton(
            device_header,
            text="🔄",
            command=self._refresh_devices,
            width=35,
            height=28,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.refresh_btn.grid(row=0, column=1, padx=(5, 0))

        # Device list
        self.device_listbox_frame = ctk.CTkScrollableFrame(
            device_frame, height=120, fg_color="#1f2937"
        )
        self.device_listbox_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.device_listbox_frame.grid_columnconfigure(0, weight=1)

        # Placeholder for no devices
        self.no_devices_label = ctk.CTkLabel(
            self.device_listbox_frame,
            text="No devices found.\nStart tunneld first:\npymobiledevice3 remote tunneld",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="center",
        )
        self.no_devices_label.grid(row=0, column=0, padx=10, pady=20)

        # Connection status
        self.conn_status = ctk.CTkLabel(
            device_frame,
            text="⭕ Not Connected",
            font=ctk.CTkFont(size=12),
            text_color="#ef4444",
        )
        self.conn_status.grid(row=2, column=0, padx=10, pady=(5, 10))

        # Disconnect button
        self.disconnect_btn = ctk.CTkButton(
            device_frame,
            text="Disconnect",
            command=self._disconnect_device,
            fg_color="#6b7280",
            hover_color="#4b5563",
            height=28,
        )
        self.disconnect_btn.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Mode selection
        mode_frame = ctk.CTkFrame(sidebar)
        mode_frame.grid(row=3, column=0, padx=15, pady=10, sticky="ew")

        mode_label = ctk.CTkLabel(
            mode_frame, text="🎯 Mode", font=ctk.CTkFont(size=16, weight="bold")
        )
        mode_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.mode_var = ctk.StringVar(value="single")

        single_radio = ctk.CTkRadioButton(
            mode_frame,
            text="Single Point (Click to teleport)",
            variable=self.mode_var,
            value="single",
            command=self._on_mode_change,
        )
        single_radio.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        route_radio = ctk.CTkRadioButton(
            mode_frame,
            text="Route Mode (Click to add points)",
            variable=self.mode_var,
            value="route",
            command=self._on_mode_change,
        )
        route_radio.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="w")

        # Route controls
        self.route_frame = ctk.CTkFrame(sidebar)
        self.route_frame.grid(row=4, column=0, padx=15, pady=10, sticky="ew")

        route_label = ctk.CTkLabel(
            self.route_frame,
            text="🚶 Route Walking",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        route_label.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w"
        )

        # Speed slider
        speed_label = ctk.CTkLabel(self.route_frame, text="Walking Speed:")
        speed_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.speed_value_label = ctk.CTkLabel(self.route_frame, text="5.0 km/h")
        self.speed_value_label.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        self.speed_slider = ctk.CTkSlider(
            self.route_frame,
            from_=1,
            to=50,
            number_of_steps=49,
            command=self._on_speed_change,
        )
        self.speed_slider.grid(
            row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.speed_slider.set(5)

        # Speed noise slider (randomness)
        noise_label = ctk.CTkLabel(self.route_frame, text="Speed Noise:")
        noise_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.noise_value_label = ctk.CTkLabel(self.route_frame, text="0%")
        self.noise_value_label.grid(row=3, column=1, padx=10, pady=5, sticky="e")

        self.noise_slider = ctk.CTkSlider(
            self.route_frame,
            from_=0,
            to=50,
            number_of_steps=50,
            command=self._on_noise_change,
        )
        self.noise_slider.grid(
            row=4, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.noise_slider.set(0)

        self.route_frame.grid_columnconfigure(0, weight=1)
        self.route_frame.grid_columnconfigure(1, weight=1)

        # Route info
        self.route_info = ctk.CTkLabel(
            self.route_frame,
            text="Points: 0 | Distance: 0 m",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.route_info.grid(row=5, column=0, columnspan=2, padx=10, pady=5)

        # Route buttons
        route_btn_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        route_btn_frame.grid(
            row=6, column=0, columnspan=2, padx=10, pady=10, sticky="ew"
        )

        self.start_walk_btn = ctk.CTkButton(
            route_btn_frame,
            text="▶ Start",
            command=self._start_walking,
            fg_color="#10b981",
            hover_color="#059669",
            width=80,
        )
        self.start_walk_btn.pack(side="left", expand=True, fill="x", padx=2)

        self.pause_walk_btn = ctk.CTkButton(
            route_btn_frame,
            text="⏸ Pause",
            command=self._pause_walking,
            fg_color="#f59e0b",
            hover_color="#d97706",
            width=80,
        )
        self.pause_walk_btn.pack(side="left", expand=True, fill="x", padx=2)

        self.stop_walk_btn = ctk.CTkButton(
            route_btn_frame,
            text="⏹ Stop",
            command=self._stop_walking,
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=80,
        )
        self.stop_walk_btn.pack(side="left", expand=True, fill="x", padx=2)

        # Loop checkbox
        self.loop_var = ctk.BooleanVar(value=False)
        loop_check = ctk.CTkCheckBox(
            self.route_frame, text="Loop route continuously", variable=self.loop_var
        )
        loop_check.grid(
            row=7, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w"
        )

        # Clear route button
        self.clear_route_btn = ctk.CTkButton(
            self.route_frame,
            text="🗑 Clear Route",
            command=self._clear_route,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.clear_route_btn.grid(
            row=8, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew"
        )

        # Coordinates section
        coord_frame = ctk.CTkFrame(sidebar)
        coord_frame.grid(row=5, column=0, padx=15, pady=10, sticky="ew")

        coord_label = ctk.CTkLabel(
            coord_frame,
            text="📍 Manual Coordinates",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        coord_label.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w"
        )

        lat_label = ctk.CTkLabel(coord_frame, text="Latitude:")
        lat_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.lat_entry = ctk.CTkEntry(coord_frame, placeholder_text="37.7749")
        self.lat_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        lon_label = ctk.CTkLabel(coord_frame, text="Longitude:")
        lon_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.lon_entry = ctk.CTkEntry(coord_frame, placeholder_text="-122.4194")
        self.lon_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        coord_frame.grid_columnconfigure(1, weight=1)

        self.set_location_btn = ctk.CTkButton(
            coord_frame,
            text="📍 Set Location",
            command=self._set_manual_location,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
        )
        self.set_location_btn.grid(
            row=3, column=0, columnspan=2, padx=10, pady=10, sticky="ew"
        )

        # Clear location button
        self.clear_location_btn = ctk.CTkButton(
            coord_frame,
            text="🔄 Clear Simulated Location",
            command=self._clear_location,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.clear_location_btn.grid(
            row=4, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew"
        )

        # Spacer
        spacer = ctk.CTkLabel(sidebar, text="")
        spacer.grid(row=10, column=0, sticky="nsew")

        # Info label at bottom
        info_label = ctk.CTkLabel(
            sidebar,
            text="💡 Start tunneld first (as admin):\npymobiledevice3 remote tunneld",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        )
        info_label.grid(row=11, column=0, padx=15, pady=(5, 15), sticky="sw")

    def _create_map_area(self):
        """Create the main map area."""
        map_frame = ctk.CTkFrame(self, corner_radius=10)
        map_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)

        # Create map widget
        self.map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=10)
        self.map_widget.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Set default position (Taipei)
        self.map_widget.set_position(25.032192, 121.469360)
        self.map_widget.set_zoom(13)

        # Bind click event
        self.map_widget.add_left_click_map_command(self._on_map_click)

        # Map controls
        map_controls = ctk.CTkFrame(map_frame, fg_color="transparent")
        map_controls.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        # Search entry
        self.search_entry = ctk.CTkEntry(
            map_controls, placeholder_text="Search location...", width=300
        )
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<Return>", self._search_location)

        search_btn = ctk.CTkButton(
            map_controls, text="🔍 Search", command=self._search_location, width=100
        )
        search_btn.pack(side="left", padx=(0, 20))

        # Zoom controls
        zoom_out_btn = ctk.CTkButton(
            map_controls,
            text="−",
            command=lambda: self.map_widget.set_zoom(self.map_widget.zoom - 1),
            width=40,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        zoom_out_btn.pack(side="right", padx=2)

        zoom_in_btn = ctk.CTkButton(
            map_controls,
            text="+",
            command=lambda: self.map_widget.set_zoom(self.map_widget.zoom + 1),
            width=40,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        zoom_in_btn.pack(side="right", padx=2)

        # Map type selector
        map_type_menu = ctk.CTkOptionMenu(
            map_controls,
            values=["OpenStreetMap", "Google normal", "Google satellite"],
            command=self._change_map_type,
            width=150,
        )
        map_type_menu.pack(side="right", padx=10)

    def _create_status_bar(self):
        """Create the bottom status bar."""
        status_frame = ctk.CTkFrame(self, height=40, corner_radius=0)
        status_frame.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready. Click on the map to set location or add route points.",
            font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(side="left", padx=15, pady=10)

        self.coords_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=12, family="Consolas"),
            text_color="gray",
        )
        self.coords_label.pack(side="right", padx=15, pady=10)

    def _start_tunneld_and_discover(self):
        """Check for tunneld service and discover devices."""
        self.status_label.configure(text="🔄 Checking tunneld service...")
        self.update()

        def start_and_discover():
            # Check if tunneld is already running
            tunneld_running = self.tunneld_manager.is_tunneld_running()

            if tunneld_running:
                self.tunneld_manager.running = True
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text="✅ Tunneld found! Scanning devices..."
                    ),
                )
            else:
                # Check if we're running as admin
                if self.tunneld_manager.is_admin():
                    # We have admin privileges - start tunneld automatically
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text="🔄 Starting tunneld (admin mode)..."
                        ),
                    )
                    success = self.tunneld_manager.start()
                    if success:
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text="✅ Tunneld started! Scanning devices..."
                            ),
                        )
                        # Wait for tunneld to initialize
                        time.sleep(3)
                    else:
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text="⚠️ Failed to start tunneld. Check for errors."
                            ),
                        )
                else:
                    # Not admin - prompt user
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text="⚠️ Run as Administrator to auto-start tunneld, or run start_tunneld.bat"
                        ),
                    )
                    # Wait and check if user started it manually
                    time.sleep(2)
                    if self.tunneld_manager.is_tunneld_running():
                        self.tunneld_manager.running = True
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text="✅ Tunneld detected! Scanning devices..."
                            ),
                        )

            # Discover devices
            devices = self.device_manager.discover_devices()
            if not devices:
                devices = self.device_manager.discover_devices_via_browse()
            self.after(0, lambda: self._update_device_list(devices))

        threading.Thread(target=start_and_discover, daemon=True).start()

    def _on_tunneld_device_detected(self):
        """Called when tunneld detects a new device connection."""
        # Refresh device list
        self.after(0, self._refresh_devices)

    def _on_tunneld_status_change(self, running: bool):
        """Called when tunneld status changes."""
        if not running:
            self.after(
                0,
                lambda: self.status_label.configure(
                    text="⚠️ tunneld stopped unexpectedly"
                ),
            )

    def _refresh_devices(self):
        """Refresh the list of available devices."""
        self.status_label.configure(text="🔍 Scanning for devices...")
        self.update()

        def discover():
            devices = self.device_manager.discover_devices()
            if not devices:
                # Try alternative discovery
                devices = self.device_manager.discover_devices_via_browse()
            self.after(0, lambda: self._update_device_list(devices))

        threading.Thread(target=discover, daemon=True).start()

    def _update_device_list(self, devices: List[DeviceInfo]):
        """Update the device list in the UI."""
        self.discovered_devices = devices

        # Clear existing widgets
        for widget in self.device_listbox_frame.winfo_children():
            widget.destroy()

        if not devices:
            self.no_devices_label = ctk.CTkLabel(
                self.device_listbox_frame,
                text="No devices with tunnels found.\n\n"
                "Run start_tunneld.bat\nas Administrator first!",
                font=ctk.CTkFont(size=12),
                text_color="orange",
                justify="center",
            )
            self.no_devices_label.grid(row=0, column=0, padx=10, pady=20)
            self.status_label.configure(
                text="⚠️ No tunnels found. Run start_tunneld.bat as Administrator."
            )
        else:
            for i, device in enumerate(devices):
                device_btn = ctk.CTkButton(
                    self.device_listbox_frame,
                    text=device.display_name(),
                    command=lambda d=device: self._connect_to_device(d),
                    fg_color="#1e3a5f"
                    if not self._is_device_connected(device)
                    else "#10b981",
                    hover_color="#2563eb",
                    anchor="w",
                    height=40,
                )
                device_btn.grid(row=i, column=0, padx=5, pady=2, sticky="ew")

            self.status_label.configure(
                text=f"Found {len(devices)} device(s). Click to connect."
            )

    def _is_device_connected(self, device: DeviceInfo) -> bool:
        """Check if a device is currently connected."""
        if self.device_manager.current_device:
            return self.device_manager.current_device.udid == device.udid
        return False

    def _connect_to_device(self, device: DeviceInfo):
        """Connect to a selected device."""
        self.status_label.configure(text=f"Connecting to {device.name}...")
        self.update()

        def connect():
            success = self.device_manager.connect_to_device(device)
            self.after(0, lambda: self._update_connection_status(success, device))

        threading.Thread(target=connect, daemon=True).start()

    def _connect_manual(self):
        """Connect to device using manual RSD host/port."""
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()

        if not host or not port_str:
            messagebox.showerror("Error", "Please enter RSD host and port.")
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "Port must be a number")
            return

        self.status_label.configure(text="Connecting via RSD...")
        self.update()

        def connect():
            success = self.device_manager.connect_via_rsd(host, port)
            self.after(0, lambda: self._update_connection_status(success))

        threading.Thread(target=connect, daemon=True).start()

    def _disconnect_device(self):
        """Disconnect from the current device."""
        self.device_manager.disconnect()
        self.conn_status.configure(text="⭕ Not Connected", text_color="#ef4444")
        self.status_label.configure(text="Disconnected from device.")
        self._refresh_devices()

    def _update_connection_status(self, success: bool, device: DeviceInfo = None):
        """Update UI after connection attempt."""
        if success:
            device_name = (
                device.name
                if device
                else (
                    self.device_manager.current_device.name
                    if self.device_manager.current_device
                    else "Device"
                )
            )
            self.conn_status.configure(text=f"🟢 {device_name}", text_color="#10b981")
            self.status_label.configure(
                text=f"Connected to {device_name}. Ready to simulate location."
            )
            # Refresh device list to show connected state
            self._update_device_list(self.discovered_devices)
        else:
            self.conn_status.configure(
                text="🔴 Connection Failed", text_color="#ef4444"
            )
            self.status_label.configure(text="Connection failed. Check tunneld status.")
            messagebox.showerror(
                "Connection Failed",
                "Failed to connect to the device.\n\n"
                "Make sure:\n"
                "1. Developer Mode is enabled on device\n"
                "2. tunneld is running: pymobiledevice3 remote tunneld\n"
                "3. Device is connected via USB\n"
                "4. Run tunneld as Administrator/root",
            )

    def _on_mode_change(self):
        """Handle mode change."""
        self.mode = (
            AppMode.SINGLE_POINT if self.mode_var.get() == "single" else AppMode.ROUTE
        )

        if self.mode == AppMode.SINGLE_POINT:
            self.status_label.configure(
                text="Single Point Mode: Click on the map to teleport to that location."
            )
        else:
            self.status_label.configure(
                text="Route Mode: Click on the map to add waypoints for walking."
            )

    def _on_map_click(self, coords):
        """Handle map click."""
        lat, lon = coords

        # Update coordinate display
        self.coords_label.configure(text=f"Clicked: {lat:.6f}, {lon:.6f}")
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, f"{lat:.6f}")
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, f"{lon:.6f}")

        if self.mode == AppMode.SINGLE_POINT:
            # Single point mode - show confirmation before teleporting
            self._pending_teleport = (lat, lon)
            self._show_teleport_confirmation(lat, lon)
        else:
            # Route mode - add waypoint
            self._add_route_point(lat, lon)

    def _show_teleport_confirmation(self, lat: float, lon: float):
        """Show a confirmation dialog before teleporting."""
        # Show a preview marker
        if hasattr(self, "_preview_marker") and self._preview_marker:
            self._preview_marker.delete()

        self._preview_marker = self.map_widget.set_marker(
            lat,
            lon,
            text="📍 Teleport here?",
            marker_color_circle="#f59e0b",
            marker_color_outside="#d97706",
        )

        # Ask for confirmation
        result = messagebox.askyesno(
            "Confirm Teleport",
            f"Teleport to this location?\n\nLatitude: {lat:.6f}\nLongitude: {lon:.6f}",
            icon="question",
        )

        # Remove preview marker
        if hasattr(self, "_preview_marker") and self._preview_marker:
            self._preview_marker.delete()
            self._preview_marker = None

        if result:
            # User confirmed - teleport
            self._set_location_at(lat, lon)
        else:
            # User cancelled
            self.status_label.configure(text="Teleport cancelled.")

    def _set_location_at(self, lat: float, lon: float):
        """Set the GPS location at the given coordinates."""
        if not self.device_manager.connected:
            self.status_label.configure(text="⚠️ Device not connected. Connect first.")
            messagebox.showwarning("Not Connected", "Please connect to a device first.")
            return

        # Clear existing marker
        if self.current_position_marker:
            self.current_position_marker.delete()

        # Add new marker
        self.current_position_marker = self.map_widget.set_marker(
            lat,
            lon,
            text="📍 Current Location",
            marker_color_circle="#ef4444",
            marker_color_outside="#b91c1c",
        )

        # Set location on device
        def set_loc():
            success = self.device_manager.set_location(lat, lon)
            self.after(0, lambda: self._on_location_set(success, lat, lon))

        threading.Thread(target=set_loc, daemon=True).start()
        self.status_label.configure(text=f"Setting location to {lat:.6f}, {lon:.6f}...")

    def _on_location_set(self, success: bool, lat: float, lon: float):
        """Called after location is set."""
        if success:
            self.status_label.configure(text=f"✅ Location set to {lat:.6f}, {lon:.6f}")
        else:
            self.status_label.configure(
                text="❌ Failed to set location. Check connection."
            )

    def _add_route_point(self, lat: float, lon: float):
        """Add a point to the route."""
        point_index = len(self.route_points)

        # Create marker
        marker = self.map_widget.set_marker(
            lat,
            lon,
            text=f"Point {point_index + 1}",
            marker_color_circle="#3b82f6",
            marker_color_outside="#1e40af",
        )

        point = RoutePoint(latitude=lat, longitude=lon, marker=marker)
        self.route_points.append(point)

        # Bind right-click to remove this point
        # Store the point reference for the callback
        def on_marker_right_click(event, pt=point):
            self._remove_route_point(pt)

        # Try to bind right-click to the marker's canvas items
        try:
            if hasattr(marker, "canvas_marker_icon"):
                marker.canvas_marker_icon.bind("<Button-3>", on_marker_right_click)
            if hasattr(marker, "canvas_text"):
                marker.canvas_text.bind("<Button-3>", on_marker_right_click)
        except Exception:
            pass  # Marker binding not supported in this version

        # Update route path on map
        self._update_route_path()

        # Update route info
        self._update_route_info()

        self.status_label.configure(
            text=f"Added point {len(self.route_points)} at {lat:.6f}, {lon:.6f} (right-click to remove)"
        )

    def _remove_route_point(self, point: RoutePoint):
        """Remove a point from the route."""
        if point in self.route_points:
            # Remove marker from map
            if point.marker:
                point.marker.delete()

            # Remove from list
            self.route_points.remove(point)

            # Renumber remaining markers
            for i, pt in enumerate(self.route_points):
                if pt.marker:
                    pt.marker.set_text(f"Point {i + 1}")

            # Update path and info
            self._update_route_path()
            self._update_route_info()

            self.status_label.configure(
                text=f"Removed point. {len(self.route_points)} points remaining."
            )

    def _update_route_path(self):
        """Update the route path visualization on the map."""
        # Remove existing path
        if self.route_path:
            self.route_path.delete()
            self.route_path = None

        if len(self.route_points) >= 2:
            path_coords = [(p.latitude, p.longitude) for p in self.route_points]
            self.route_path = self.map_widget.set_path(
                path_coords, color="#3b82f6", width=3
            )

    def _update_route_info(self):
        """Update route information display."""
        num_points = len(self.route_points)
        total_distance = 0

        for i in range(len(self.route_points) - 1):
            p1 = self.route_points[i]
            p2 = self.route_points[i + 1]
            total_distance += RouteWalker.haversine_distance(
                p1.latitude, p1.longitude, p2.latitude, p2.longitude
            )

        if total_distance >= 1000:
            distance_str = f"{total_distance / 1000:.2f} km"
        else:
            distance_str = f"{total_distance:.0f} m"

        self.route_info.configure(
            text=f"Points: {num_points} | Distance: {distance_str}"
        )

    def _clear_route(self):
        """Clear the current route."""
        # Stop walking if active
        self.route_walker.stop()

        # Remove markers
        for point in self.route_points:
            if point.marker:
                point.marker.delete()

        # Remove path
        if self.route_path:
            self.route_path.delete()
            self.route_path = None

        self.route_points = []
        self._update_route_info()
        self.status_label.configure(text="Route cleared.")

    def _on_speed_change(self, value):
        """Handle speed slider change."""
        speed_kmh = float(value)
        speed_mps = speed_kmh / 3.6

        self.speed_value_label.configure(text=f"{speed_kmh:.1f} km/h")
        self.route_walker.set_speed(speed_mps)

    def _on_noise_change(self, value):
        """Handle noise slider change."""
        noise_percent = float(value)
        self.noise_value_label.configure(text=f"{noise_percent:.0f}%")
        self.route_walker.set_noise(noise_percent)

    def _start_walking(self):
        """Start walking the route."""
        if not self.device_manager.connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first.")
            return

        if len(self.route_points) < 2:
            messagebox.showwarning(
                "Invalid Route", "Please add at least 2 points to the route."
            )
            return

        if self.route_walker.walking:
            if self.route_walker.paused:
                self.route_walker.resume()
                self.status_label.configure(text="▶ Resumed walking...")
            return

        # Set route
        self.route_walker.set_route(self.route_points)

        # Start walking
        self.route_walker.start_walking(loop=self.loop_var.get())
        self.status_label.configure(text="🚶 Walking route...")

    def _pause_walking(self):
        """Pause walking."""
        if self.route_walker.walking:
            self.route_walker.pause()
            self.status_label.configure(text="⏸ Walking paused.")

    def _stop_walking(self):
        """Stop walking."""
        self.route_walker.stop()

        # Remove current position marker
        if self.current_position_marker:
            self.current_position_marker.delete()
            self.current_position_marker = None

        self.status_label.configure(text="⏹ Walking stopped.")

    def _on_position_update(self, lat: float, lon: float):
        """Called when walking position updates."""

        def update():
            # Update or create position marker
            if self.current_position_marker:
                self.current_position_marker.delete()

            self.current_position_marker = self.map_widget.set_marker(
                lat,
                lon,
                text="🚶",
                marker_color_circle="#10b981",
                marker_color_outside="#059669",
            )

            self.coords_label.configure(text=f"Walking: {lat:.6f}, {lon:.6f}")

        self.after(0, update)

    def _on_walk_complete(self):
        """Called when walking is complete."""

        def update():
            self.status_label.configure(text="✅ Route walk completed!")

        self.after(0, update)

    def _set_manual_location(self):
        """Set location from manual coordinates."""
        try:
            lat = float(self.lat_entry.get().strip())
            lon = float(self.lon_entry.get().strip())

            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError("Invalid coordinate range")

            # Center map on location
            self.map_widget.set_position(lat, lon)

            # Set location
            self._set_location_at(lat, lon)

        except ValueError as e:
            messagebox.showerror(
                "Invalid Coordinates",
                "Please enter valid latitude (-90 to 90) and longitude (-180 to 180).",
            )

    def _clear_location(self):
        """Clear the simulated location."""
        if not self.device_manager.connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first.")
            return

        def clear_loc():
            success = self.device_manager.clear_location()
            self.after(0, lambda: self._on_location_cleared(success))

        threading.Thread(target=clear_loc, daemon=True).start()
        self.status_label.configure(text="Clearing location simulation...")

    def _on_location_cleared(self, success: bool):
        """Called after location is cleared."""
        if success:
            self.status_label.configure(text="✅ Location simulation cleared.")
            if self.current_position_marker:
                self.current_position_marker.delete()
                self.current_position_marker = None
        else:
            self.status_label.configure(text="❌ Failed to clear location.")

    def _search_location(self, event=None):
        """Search for a location using Nominatim geocoding."""
        query = self.search_entry.get().strip()
        if not query:
            return

        self.status_label.configure(text=f"Searching for: {query}...")
        self.update()

        def search():
            try:
                import requests

                # Use Nominatim with proper User-Agent (required by OSM)
                headers = {"User-Agent": "iFakeGPS/1.0 (iOS Location Simulator)"}
                params = {"q": query, "format": "json", "limit": 1}

                response = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    headers=headers,
                    params=params,
                    timeout=10,
                )

                if response.status_code == 200:
                    results = response.json()
                    if results:
                        lat = float(results[0]["lat"])
                        lon = float(results[0]["lon"])
                        display_name = results[0].get("display_name", query)

                        # Update map on main thread
                        self.after(
                            0, lambda: self._on_search_result(lat, lon, display_name)
                        )
                    else:
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text=f"Location not found: {query}"
                            ),
                        )
                else:
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text=f"Search failed: HTTP {response.status_code}"
                        ),
                    )

            except Exception as e:
                logger.error(f"Search error: {e}")
                self.after(
                    0,
                    lambda: self.status_label.configure(text=f"Search error: {query}"),
                )

        threading.Thread(target=search, daemon=True).start()

    def _on_search_result(self, lat: float, lon: float, display_name: str):
        """Handle search result on main thread."""
        self.map_widget.set_position(lat, lon)
        self.map_widget.set_zoom(15)
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, f"{lat:.6f}")
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, f"{lon:.6f}")

        # Truncate display name if too long
        if len(display_name) > 50:
            display_name = display_name[:47] + "..."
        self.status_label.configure(text=f"📍 {display_name}")

    def _change_map_type(self, map_type: str):
        """Change the map tile source."""
        if map_type == "OpenStreetMap":
            self.map_widget.set_tile_server(
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            )
        elif map_type == "Google normal":
            self.map_widget.set_tile_server(
                "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
                max_zoom=22,
            )
        elif map_type == "Google satellite":
            self.map_widget.set_tile_server(
                "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
                max_zoom=22,
            )

    def _on_close(self):
        """Handle window close."""
        # Stop walking
        self.route_walker.stop()

        # Disconnect device
        self.device_manager.disconnect()

        # Stop tunneld if we started it
        if self.tunneld_manager.process:
            self.tunneld_manager.stop()

        # Destroy window
        self.destroy()


def main():
    """Main entry point."""
    app = iFakeGPSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
