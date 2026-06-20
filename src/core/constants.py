"""Centralized constants — the single source of truth for addresses, map
configuration and external identifiers that were previously scattered (and
sometimes hardcoded multiple times) across modules."""

# --- tunneld (pymobiledevice3 RSD tunnel) ---
TUNNELD_PORT = 49151
TUNNELD_URL = f"http://127.0.0.1:{TUNNELD_PORT}/"

# --- GitHub (update checks + release downloads) ---
GITHUB_REPO = "www10177/iFakeGPS"

# --- Map defaults ---
# Taipei — fallback when Windows geolocation is unavailable.
DEFAULT_MAP_POSITION = (25.032192, 121.469360)
# Capped to avoid 404 tile stalls at very high zoom on Google tiles.
MAP_MAX_ZOOM = 19

# Tile providers. The default (Google normal) is what the map boots with.
TILE_SERVERS = {
    "OpenStreetMap": {
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "max_zoom": 19,
    },
    "Google normal": {
        "url": "https://mt1.google.com/vt/lyrs=m&hl=zh-TW&x={x}&y={y}&z={z}",
        "max_zoom": MAP_MAX_ZOOM,
    },
    "Google satellite": {
        "url": "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
        "max_zoom": 22,
    },
}
DEFAULT_TILE_SERVER = "Google normal"
