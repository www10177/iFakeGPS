# Motion Settings Random Stop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace inline noise controls with a motion-settings popup and add route-only random auto-resume stops.

**Architecture:** Extend `RouteWalker` with explicit random-stop configuration and snapshot state, cover that logic with unit tests, then update `iFakeGPSApp` to expose a popup editor that writes into the existing walker/settings flow. Keep ETA updates driven by the route summary refresh path.

**Tech Stack:** Python, unittest, customtkinter

---

### Task 1: Walker random-stop logic

**Files:**
- Modify: `src/core/route_walker.py`
- Test: `tests/test_route_walker.py`

- [ ] Add failing tests for random-stop scheduling and active wait countdown.
- [ ] Run `uv run python -m unittest tests.test_route_walker -v` and verify failure.
- [ ] Implement minimal walker support for random stops.
- [ ] Re-run `uv run python -m unittest tests.test_route_walker -v` and verify pass.

### Task 2: App motion settings UI logic

**Files:**
- Modify: `src/ui/app.py`
- Modify: `src/ui/i18n.py`
- Modify: `tests/test_app_route_ui.py`

- [ ] Add failing tests for applying motion settings and summary text behavior.
- [ ] Replace inline noise row with motion-settings button and device-preview pairing.
- [ ] Add popup panel and wire settings into walker / summary refresh.

### Task 3: Verification

**Files:**
- Modify: `src/core/route_walker.py`
- Modify: `src/ui/app.py`
- Modify: `src/ui/i18n.py`
- Test: `tests/test_route_walker.py`
- Test: `tests/test_app_route_ui.py`

- [ ] Run `uv run python -m unittest tests.test_route_walker tests.test_app_route_ui tests.test_route_summary tests.test_coordinate_inputs -v`.
- [ ] Run `uv run python -m py_compile src/core/route_walker.py src/ui/app.py src/ui/i18n.py tests/test_route_walker.py tests/test_app_route_ui.py`.
