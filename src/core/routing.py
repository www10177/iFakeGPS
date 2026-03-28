"""
routing.py – Road-following route planner using OSRM.

Uses the OSRM public API by default to compute a driving route that
follows actual roads between two points.  The result is a list of
RoutePoint objects ready for RouteWalker.

The base URL can be overridden to point at a self-hosted OSRM instance
or an OpenRouteService endpoint.
"""

import requests

from src.core.models import RoutePoint
from src.utils.logger import logger

# Default API endpoints
_DEFAULT_OSRM_URL = "https://router.project-osrm.org"
_DEFAULT_ORS_URL = "https://api.openrouteservice.org"


class RoutingService:
    """Compute road-following routes via OSRM or OpenRouteService APIs."""

    def __init__(
        self,
        provider: str = "osrm",
        base_url: str = "",
        api_key: str = "",
        timeout: float = 15.0,
    ):
        """
        Initialize the routing service.

        Parameters
        ----------
        provider : "osrm" or "ors"
        base_url : Custom endpoint (if empty, defaults to the provider's public map API)
        api_key  : Required for ORS public API; ignored for OSRM
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.timeout = timeout

        if not base_url:
            self.base_url = (
                _DEFAULT_ORS_URL if self.provider == "ors" else _DEFAULT_OSRM_URL
            )
        else:
            self.base_url = base_url.rstrip("/")

    def get_route(
        self,
        waypoints: list[tuple[float, float]],
        profile: str = "driving",
    ) -> list[RoutePoint]:
        """
        Query the active routing provider for a route hitting all *waypoints* in order.

        Parameters
        ----------
        waypoints : list of (latitude, longitude)
        profile   : "driving", "walking", or "cycling" (maps to provider specifics internally)
        """
        if len(waypoints) < 2:
            return [RoutePoint(latitude=lat, longitude=lon) for lat, lon in waypoints]

        if self.provider == "ors":
            return self._get_route_ors(waypoints, profile)
        else:
            return self._get_route_osrm(waypoints, profile)

    def _get_route_osrm(
        self, waypoints: list[tuple[float, float]], profile: str
    ) -> list[RoutePoint]:
        # OSRM expects lon,lat joined by semicolons
        coords = ";".join(f"{lon},{lat}" for lat, lon in waypoints)
        url = f"{self.base_url}/route/v1/{profile}/{coords}"
        params = {
            "overview": "full",
            "geometries": "polyline",
        }

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RoutingError(f"OSRM request failed: {exc}") from exc

        if data.get("code") != "Ok":
            msg = data.get("message", data.get("code", "Unknown error"))
            raise RoutingError(f"OSRM error: {msg}")

        routes = data.get("routes", [])
        if not routes:
            raise RoutingError("OSRM returned no routes")

        geometry = routes[0].get("geometry", "")
        if not geometry:
            raise RoutingError("OSRM returned empty geometry")

        coords_list = decode_polyline(geometry)
        logger.info(
            f"OSRM Routing: {len(coords_list)} points, "
            f"distance={routes[0].get('distance', 0):.0f}m"
        )
        return [RoutePoint(latitude=lat, longitude=lon) for lat, lon in coords_list]

    def _get_route_ors(
        self, waypoints: list[tuple[float, float]], profile: str
    ) -> list[RoutePoint]:
        # ORS profile mapping
        ors_profile = "driving-car"
        if profile == "walking":
            ors_profile = "foot-walking"
        elif profile == "cycling":
            ors_profile = "cycling-regular"

        url = f"{self.base_url}/v2/directions/{ors_profile}/geojson"
        headers = {
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.api_key:
            headers["Authorization"] = self.api_key

        # ORS expects [lon, lat]
        payload = {"coordinates": [[lon, lat] for lat, lon in waypoints]}

        try:
            resp = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            if resp.status_code in (401, 403):
                raise RoutingError("ORS error: Invalid or missing API key.")
            elif resp.status_code == 429:
                raise RoutingError("ORS error: Rate limit exceeded.")
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise RoutingError(f"ORS request failed: {exc}") from exc

        if "error" in data:
            err = data["error"]
            err_msg = err.get("message", str(err))
            raise RoutingError(f"ORS error: {err_msg}")

        features = data.get("features", [])
        if not features:
            raise RoutingError("ORS returned no routes")

        # GeoJSON LineString coordinates are [lon, lat]
        coords_list = features[0].get("geometry", {}).get("coordinates", [])
        logger.info(f"ORS Routing: {len(coords_list)} points")
        # Convert [lon, lat] back to RoutePoint(lat, lon)
        return [RoutePoint(latitude=lat, longitude=lon) for lon, lat in coords_list]


class RoutingError(Exception):
    """Raised when route computation fails."""


# ---------------------------------------------------------------------------
# Polyline decoder  (Google Encoded Polyline Algorithm)
# ---------------------------------------------------------------------------


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """
    Decode a Google-encoded polyline string into a list of (lat, lon) tuples.

    Reference: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    result: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)

    while index < length:
        # Decode latitude
        shift = 0
        value = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            value |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(value >> 1) if (value & 1) else (value >> 1)
        lat += dlat

        # Decode longitude
        shift = 0
        value = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            value |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(value >> 1) if (value & 1) else (value >> 1)
        lng += dlng

        result.append((lat / 1e5, lng / 1e5))

    return result
