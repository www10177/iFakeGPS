import json
from dataclasses import asdict
from pathlib import Path

from src.core.models import MotionSettings


class MotionSettingsStore:
    """Load/save route motion realism settings from a small JSON file."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> MotionSettings:
        if not self.path.exists():
            return MotionSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return MotionSettings()
        return MotionSettings(**{**asdict(MotionSettings()), **data})

    def save(self, settings: MotionSettings):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(settings), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
