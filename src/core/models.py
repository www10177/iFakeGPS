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

    def display_name(self) -> str:
        return f"{self.name} ({self.product_type} - iOS {self.ios_version})"
