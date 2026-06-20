# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **The full development guide lives in [AGENTS.md](AGENTS.md) — read it first.**
> It is the single source of truth for architecture, packaging, tunneld internals,
> Developer Mode flow, and the CI-parsed release/changelog rules. This file only
> repeats the few commands you reach for most.

@AGENTS.md

## Quick reference

```bash
uv run python scripts/run.py                          # Run the app from source (dev)
uv run python -m unittest discover -s tests           # Run all tests
uv run python -m unittest tests.test_update_checker   # Run one test module
uv run ruff check .                                   # Lint
scripts/pack.bat                                      # Build the Windows exe (from iFakeGPS.spec)
```

- Always use **`uv`**, never `pip`.
- `iFakeGPS.spec` is the single source of truth for the build — both `scripts/pack.bat`
  and CI use it. Change the spec, not CLI flags.
- App data (map cache, saved routes/locations, logs) lives under `%LOCALAPPDATA%\iFakeGPS\`.
