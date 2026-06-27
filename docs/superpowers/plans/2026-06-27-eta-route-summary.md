# ETA Route Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add route ETA summaries and speed preset buttons using the existing speed control as the single source of truth.

**Architecture:** Introduce a small pure-Python route summary helper in `src/core` for distance and duration math, cover it with unit tests, and have `src/ui/app.py` render the returned summary strings. Preset buttons only update the existing speed entry, slider, and walker speed, then trigger the same summary refresh path.

**Tech Stack:** Python, unittest, customtkinter

---

### Task 1: Core route summary helper

**Files:**
- Create: `src/core/route_summary.py`
- Test: `tests/test_route_summary.py`

- [ ] Write failing tests for segment math and formatting.
- [ ] Run `uv run python -m unittest tests.test_route_summary -v` and verify failure.
- [ ] Implement minimal summary helper.
- [ ] Re-run `uv run python -m unittest tests.test_route_summary -v` and verify pass.

### Task 2: UI summary rendering

**Files:**
- Modify: `src/ui/app.py`
- Modify: `src/ui/i18n.py`
- Test: `tests/test_route_summary.py`

- [ ] Add i18n strings for presets and ETA labels.
- [ ] Add preset buttons above the speed controls.
- [ ] Add a second route summary label for segment details.
- [ ] Refresh summary from route updates and speed changes.

### Task 3: Verification

**Files:**
- Modify: `src/core/route_summary.py`
- Modify: `src/ui/app.py`
- Modify: `src/ui/i18n.py`
- Test: `tests/test_route_summary.py`

- [ ] Run focused tests with `uv run python -m unittest tests.test_route_summary tests.test_coordinate_inputs -v`.
- [ ] Sanity-check syntax with `uv run python -m py_compile src/core/route_summary.py src/ui/app.py src/ui/i18n.py`.
