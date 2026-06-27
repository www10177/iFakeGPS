# Motion Settings Random Stop Design

## Goal

Replace the inline speed-noise controls with a single motion-settings entry point, and add route-only random temporary stops that auto-resume after a configurable duration range.

## Scope

- Replace the current speed-noise row with a button that opens a motion-settings panel.
- Place that button on the left half of a two-column row in the route section.
- Move the existing device-screen button to the right half of that same row.
- Keep speed presets and speed slider on the main route panel.
- Move speed-noise controls into the popup panel.
- Add random temporary stop settings:
  - enabled toggle
  - average stop interval by distance
  - stop duration min/max seconds
- Only affect route walking / navigation auto movement.
- Random stops pause location updates and auto-resume; they do not require manual resume.
- Remaining ETA should include active random-stop wait time.

## Logic

- RouteWalker owns random-stop state and scheduling.
- Stop scheduling is distance-based, not time-based.
- After each stop (or start), the walker samples the next stop distance around the configured average interval so behavior feels less mechanical.
- While a random stop is active, the walker keeps the route session alive but does not advance coordinates.

## Testing

- Add walker logic tests for scheduling and active stop countdown.
- Add app-level UI logic tests for applying motion settings to existing controls/walker state.
