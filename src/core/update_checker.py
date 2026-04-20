import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from src.utils.logger import logger

GITHUB_REPO = "www10177/iFakeGPS"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass
class ReleaseInfo:
    tag_name: str
    html_url: str
    body: str

    @property
    def version(self) -> str:
        return normalize_version(self.tag_name)


def normalize_version(text: str) -> str:
    return text.strip().lstrip("vV")


def parse_version_tuple(version: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", normalize_version(version))
    if not nums:
        return (0,)
    return tuple(int(x) for x in nums)


def is_newer_version(latest: str, current: str) -> bool:
    latest_t = parse_version_tuple(latest)
    current_t = parse_version_tuple(current)
    max_len = max(len(latest_t), len(current_t))
    latest_t += (0,) * (max_len - len(latest_t))
    current_t += (0,) * (max_len - len(current_t))
    return latest_t > current_t


def _read_version_from_changelog() -> Optional[str]:
    try:
        root = Path(__file__).resolve().parents[2]
        changelog = root / "CHANGELOG.md"
        if not changelog.exists():
            return None
        for line in changelog.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^## \[([^\]]+)\]", line.strip())
            if not m:
                continue
            v = m.group(1).strip()
            if v.lower() == "unreleased":
                continue
            return normalize_version(v)
    except Exception as e:
        logger.debug("Failed to read version from CHANGELOG: %s", e)
    return None


def get_current_version() -> str:
    try:
        return normalize_version(importlib.metadata.version("ifakegps"))
    except Exception:
        pass

    v = _read_version_from_changelog()
    if v:
        return v
    return "0.0.0"


def fetch_latest_release(timeout_sec: int = 6) -> Optional[ReleaseInfo]:
    try:
        resp = requests.get(
            LATEST_RELEASE_API,
            headers={"User-Agent": "iFakeGPS Update Checker"},
            timeout=timeout_sec,
        )
        if resp.status_code != 200:
            logger.info("Update check skipped: GitHub API status=%s", resp.status_code)
            return None
        data = resp.json()
        tag_name = str(data.get("tag_name", "")).strip()
        html_url = str(data.get("html_url", "")).strip()
        body = str(data.get("body", "") or "").strip()
        if not tag_name or not html_url:
            return None
        return ReleaseInfo(tag_name=tag_name, html_url=html_url, body=body)
    except Exception as e:
        logger.info("Update check failed: %s", e)
        return None


def summarize_changelog(body: str, max_lines: int = 16, max_chars: int = 1200) -> str:
    cleaned = body.replace("\r\n", "\n").strip()
    if not cleaned:
        return ""
    lines = [ln for ln in cleaned.split("\n") if ln.strip()]
    lines = lines[:max_lines]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text
