# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.4.2] - 2026-04-20

### Added
- **Windows 通知註冊自動化**：啟動時自動檢查並註冊 `AppUserModelID`（`iFakeGPS`），提升 Windows Toast 通知可用性與穩定度。
- **雙通道通知**：路線完成與裝置斷線事件，除了 Windows 通知外，會同步顯示 App 內確認彈窗，使用者可按「確定」關閉。
- **持久化 Log**：新增 `%LOCALAPPDATA%\\iFakeGPS\\logs\\ifakegps.log`（含輪替），並提供側邊欄「開啟 Log 資料夾」快速入口。

### Changed
- **關閉自動清除定位**：關閉 iFakeGPS 視窗時，若裝置仍連線，會先自動嘗試清除模擬定位再退出。
- **清除按鈕跨模式可見**：將「清除模擬定位」改為側邊欄獨立按鈕，在單點、路線、導航模式都可直接使用。
- **通知策略更新**：Windows Toast 改為優先嘗試預設 notifier，失敗時改用 `explicit_app_id=iFakeGPS` 路徑送出。

### Fixed
- **斷線誤判完成**：修正裝置斷線時仍可能觸發「路線完成」通知的問題。
- **斷線自動暫停**：當目前連線裝置中斷，路線模擬會立即自動暫停，避免持續推進錯誤狀態。

## [1.4.1] - 2026-03-28

### Changed
- **載入路線視窗可讀性改善**：改為使用 `CTkToplevel`，並調整提示文字與清單色彩對比（深底亮字與高對比選取色），修正文字在視窗中難以辨識的問題。
- **預設速度調整**：路線行走預設速度從 `5 km/h` 調整為 `20 km/h`（含 UI 預設值與 `RouteWalker` 預設值）。
- **預設 Noise 調整**：速度噪音預設從 `0%` 調整為 `10%`（含 UI 預設值與 `RouteWalker` 預設值）。

### Fixed
- **行走初始化一致性**：修正開始行走時的 `RouteWalker.start()` 呼叫流程，改為先設定路線與 loop，再啟動 walker。
- **啟動行走例外**：修正 `TypeError: RouteWalker.start() got an unexpected keyword argument 'loop'`。
- **重複通知問題**：移除路線完成後重複觸發的桌面通知呼叫。
- **重複 noise handler**：移除重複定義的 `_on_noise_change`，統一使用 `set_speed_noise`。

## [1.4.0] - 2026-03-28

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
