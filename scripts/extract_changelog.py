from __future__ import annotations

import re
import sys
from pathlib import Path

HEADER_RE = re.compile(r"^## \[(?P<version>[^\]]+)\](?:\s*-\s*.*)?$")


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("v")


def extract_section(changelog_text: str, tag: str) -> str | None:
    lines = changelog_text.splitlines()
    target = normalize_tag(tag)

    start_idx = None
    end_idx = None

    for idx, line in enumerate(lines):
        match = HEADER_RE.match(line.strip())
        if not match:
            continue

        version = normalize_tag(match.group("version"))
        if start_idx is None and version == target:
            start_idx = idx + 1
            continue

        if start_idx is not None:
            end_idx = idx
            break

    if start_idx is None:
        return None

    if end_idx is None:
        end_idx = len(lines)

    section = "\n".join(lines[start_idx:end_idx]).strip()
    return section or None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/extract_changelog.py <tag>", file=sys.stderr)
        return 2

    tag = sys.argv[1]
    changelog_path = Path("CHANGELOG.md")
    output_path = Path("release_notes.md")

    if not changelog_path.exists():
        print("ERROR: CHANGELOG.md not found.", file=sys.stderr)
        return 1

    changelog_text = changelog_path.read_text(encoding="utf-8")
    section = extract_section(changelog_text, tag)

    if not section:
        print(
            f"ERROR: Could not find changelog section for tag '{tag}'. "
            "Expected: ## [<tag>] or ## [v<tag>] in CHANGELOG.md.",
            file=sys.stderr,
        )
        return 1

    notes = f"## Changelog\n\n{section}\n"
    output_path.write_text(notes, encoding="utf-8")
    print(f"Wrote release notes to {output_path} for tag {tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
