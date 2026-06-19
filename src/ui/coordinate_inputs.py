def parse_coordinate_pair(latitude_text: str, longitude_text: str) -> tuple[float, float]:
    lat = float(latitude_text.strip())
    lon = float(longitude_text.strip())
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordinate out of range")
    return lat, lon


def parse_optional_coordinate_pair(
    latitude_text: str, longitude_text: str
) -> tuple[float, float] | None:
    if not latitude_text.strip() or not longitude_text.strip():
        return None
    return parse_coordinate_pair(latitude_text, longitude_text)
