from dataclasses import dataclass
from typing import Optional


@dataclass
class RoutePoint:
    """Represents a point on the route"""

    latitude: float
    longitude: float
    marker: Optional[object] = None


@dataclass
class DeviceInfo:
    """Represents an iOS device"""

    udid: str
    name: str
    product_type: str
    ios_version: str
    rsd_address: str
    rsd_port: int
    interface: Optional[str] = None  # e.g., "usb" or "wifi"

    def display_name(self) -> str:
        icon = "🔌" if self.interface == "usb" else "📶"
        interface_str = f" [{self.interface.upper()}]" if self.interface else ""
        return f"{icon} {self.name} ({self.product_type} - iOS {self.ios_version}){interface_str}"


@dataclass(eq=True)
class MotionSettings:
    """Persisted motion realism settings for route walking."""

    noise_pct: float = 10.0
    random_stop_enabled: bool = False
    random_stop_interval_m: float = 150.0
    random_stop_min_s: float = 5.0
    random_stop_max_s: float = 20.0
    displacement_noise_enabled: bool = False
    displacement_radius_m: float = 3.0
