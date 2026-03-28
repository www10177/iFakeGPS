# Changelog

All notable changes to this project will be documented in this file.

Release section format (required for CI release parsing):

```md
## [1.4.0] - 2026-03-28

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

Notes:
- Tag `v1.4.0` and `1.4.0` both map to section `[1.4.0]`.
- CI will fail release creation if the matching version section is missing.

## [Unreleased]

### Added
- **Navigation Mode**: Added a new mode (`navigation`) which uses OSRM (or OpenRouteService, via settings) to plot actual road paths between waypoints.
- **Saved Routes**: Added a new UI block in the sidebar to save, load, delete, import, and export GPS tracks (.gpx). Routes are persisted in the local SQLite cache database.
- **Walk Notification**: The app now utilizes modern Windows Toast Notifications (falling back to simple dialogs) to silently inform the user when a simulated walk has reached the final destination.

### Changed
- **Dynamic Append-only Route**: The route walker now holds a live reference to the UI's waypoint list instead of a snapshot taken at start time. New flags/waypoints added on the map while walking is active are automatically appended to the end of the current route and walked in sequence — no restart required. In non-loop mode the walker idles after exhausting all current waypoints and resumes as soon as new ones are added.

## [1.3.0] - 2026-03-07

### Added
- **i18n Support**: Full internationalization with English and Traditional Chinese, including auto-detection of the OS language.
- **Map Tile Caching**: Added local SQLite-based tile caching (`CachingTileMapView`) to drastically reduce map loading times and bandwidth.
- **Interactive Tooltips**: Added instant-hover tooltips for complex UI parameters like speed and noise.
- **Route Controls**: Added the ability to `Pause` and `Resume` a simulated route walk.
- **Advanced Speed Control**: Upgraded the speed slider to support a wider range (0 to 1000 km/h) and bidirectional text entry.

### Fixed
- **Tooltip Crash**: Fixed a CTkLabel background color crash that occurred when rendering tooltips in CustomTkinter.

## [1.1.0] - 2026-03-06

### Added
- **UI Rewrite**: Completely overhauled the User Interface using `CustomTkinter` for a modern and responsive experience.
- **Map Integration**: Added visual map integration with `tkintermapview` along with device controls.
- **Location Controls**: Implemented comprehensive location simulation control segments.
- **Developer Disk Image**: Added auto-mount mechanism for iOS Developer Disk Images.
- **In-App Guide**: Introduced an up-to-date Chinese documentation for iOS Developer Mode enablement alongside a built-in guide.
- **Developer Mode Check**: Added functionality to check Developer Mode status directly in the UI.
- **App Icon**: Pinned application icon for `PyInstaller` standalone builds.
- **i18n**: Added a full Traditional Chinese README file (`README_zh-TW.md`).

### Changed
- **Architecture Refactor**: Restructured the project into a modular `src` directory layout.
- **Build Scripts**: Updated the setup and `pyinstaller` scripts for console visibility and to include new dependencies.
- **Documentation**: Revamped the English `README.md` to prioritize standalone binaries for end-users, moving developer build notes into a separate guide.

### Fixed
- Improved inner `tunneld` execution and error logging for frozen (PyInstaller) bundles.
