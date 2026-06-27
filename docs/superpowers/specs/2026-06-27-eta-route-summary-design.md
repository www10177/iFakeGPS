# ETA Route Summary Design

## Goal

Add ETA and distance summaries to iFakeGPS so users can see estimated time cost for a target destination or an applied multi-point route, using the existing speed field as the source of truth.

## Scope

- Reuse the current speed entry and slider.
- Add three quick presets above the speed controls: walking, biking, driving.
- Show total distance and estimated total time for the current route.
- Show per-segment distance and ETA for multi-segment routes.
- Recalculate immediately whenever route points or speed change.
- Do not call any external map API for ETA math. Estimation is always `distance / speed`.
- When a route has already been expanded by OSRM/ORS, use the resulting dense route points so the estimate follows the actual planned path length.

## Architecture

Create a small `src/core` helper module that summarizes route points into:

- per-segment distances
- per-segment estimated durations
- total distance
- total duration
- formatted display strings for UI use

`src/ui/app.py` will call this helper from the existing route update and speed change flows. The UI remains the rendering layer; the new core helper owns the math.

## UX

- Presets:
  - Walking: 5 km/h
  - Biking: 20 km/h
  - Driving: 60 km/h
- Preset buttons write their value into the existing speed slider and entry.
- The route summary remains in the route panel below the speed/noise controls.
- Single-line summary shows points, total distance, and total ETA.
- A second label shows segment breakdown:
  - If there are no segments, show a short idle hint.
  - If there is one segment, show that segment.
  - If there are multiple segments, show each segment on its own line.

## Data Rules

- Use haversine distance consistently in one shared helper.
- Output distance in meters for short segments and kilometers otherwise.
- Output ETA in minutes for short trips and hour+minute style for longer trips.
- Clamp speed to a small positive value in the core helper to avoid division by zero.

## Testing

- Add unit tests for:
  - haversine-based segment totals
  - single-segment ETA math
  - multi-segment total math
  - speed clamping behavior
  - formatting behavior for short and longer trips

## Files

- Add: `src/core/route_summary.py`
- Add: `tests/test_route_summary.py`
- Modify: `src/ui/app.py`
- Modify: `src/ui/i18n.py`
