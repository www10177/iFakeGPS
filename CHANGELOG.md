# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **裝置畫面預覽（連拍）**：新增可自由拖曳/縮放的浮動視窗，透過 USB 連續擷取 iOS 裝置畫面（約 1–2 fps，可調整更新頻率），方便對齊遊戲內地圖與模擬位置，不必一直在手機與電腦間切換。使用獨立的 DVT 連線，不影響定位模擬。
- **應用程式內自動更新**：偵測到新版時可直接在程式內一鍵下載並安裝，下載過程顯示進度，完成後自動重新啟動，不再需要手動到下載頁覆蓋檔案。非打包執行（從原始碼執行）時仍維持開啟下載頁的行為。

### Fixed
- **更新時的檔案鎖死問題**：修正關閉程式後 tunneld 背景子行程殘留、鎖住 `iFakeGPS.exe` 導致無法覆蓋更新（過去需重開機）的問題。關閉時改為終結整棵 tunneld 行程樹，並清除佔用 tunneld 連接埠的殘留行程。

## [1.6.3] - 2026-06-19

### Added
- **Log 檢視視窗**：左下角語言選單旁新增 Log 按鈕，可在需要時開啟最近的應用程式 Log，預設啟動時不再依賴外部 Console 視窗查看狀態。
- **地點座標輸入**：右側「快速存取」的地點儲存支援直接輸入經緯度，並可從地圖選取或目前模擬 GPS 自動填入同一組欄位。

### Changed
- **地點儲存預覽一致化**：手動輸入完整有效座標後，地圖會自動跳轉到該位置並顯示「儲存這裡」預覽標記，與地圖選取流程一致。
- **介面精簡**：移除主畫面上的「開發者模式」區塊，降低連線問題排查時的誤導。
- **座標欄位清晰度**：移除經緯度輸入框中的範例數字提示，避免使用者誤以為欄位已有實際輸入值。
- **發行版啟動體驗**：PyInstaller 打包設定改為視窗模式，避免啟動 GUI 時額外顯示 Console 視窗。

### Fixed
- **自動更新版本判斷**：修正 frozen EXE 讀取目前版本不穩定的問題，並在打包設定中加入 `CHANGELOG.md` 與專案 metadata，讓 GitHub Release 更新檢查可正確比對版本。

## [1.6.2] - 2026-06-06

### Changed
- **地點儲存流程優化**：新增「選取地點儲存」模式，按下後會提示使用者在地圖上選取要儲存的地點，並在確認後才寫入儲存清單，避免誤存目前模擬位置。
- **目前 GPS 快速儲存**：新增「儲存目前 GPS」入口，讓使用者可以明確儲存目前模擬中的位置。

## [1.6.1] - 2026-05-16

### Added
- **地點導航快捷鍵**：右側「地點」清單新增導航按鈕，可從目前模擬位置直接規劃到已儲存地點的路線。

### Fixed
- **目前位置提示**：若尚未設定目前模擬位置就嘗試從地點導航，會提示使用者先透過單點定位設定目前位置，避免產生無效路線。

## [1.6.0] - 2026-05-02

### Added
- **快速存取面板 (Quick Access Panel)**：在地圖右側新增管理面板，支援儲存常用地點與管理歷史路線。
- **地點儲存功能**：支援將目前點擊的位置或模擬位置儲存為常用地點，並可快速跳轉或直接傳送（Teleport）。
- **地圖工具列**：地圖右上角新增工具列，包含「跳轉到目前位置」與「地圖跟隨模式」開關。
- **裝置清單視覺優化**：裝置卡片現在會顯示更詳細的資訊（iOS 版本、產品型號），並優化了連線介面圖示。

### Changed
- **路徑規劃優化**：預設路徑規劃服務整合為 OSRM，簡化設定流程。
- **視窗佈局調整**：預設視窗寬度增加至 1500，以提供更寬廣的地圖與管理視野。
- **提示框 (ToolTip) 優化**：改進提示框的顯示位置計算邏輯，現在會更準確地跟隨滑鼠游標。

### Fixed
- **速度輸入限制**：修正速度輸入框與滑桿的連動上限，確保數值範圍一致。

## [1.5.1] - 2026-04-22

### Added
- **連線介面顯示 (Connection Interface)**：裝置清單現在會顯示連線類型（🔌 USB 或 📶 WIFI），並支援同時顯示多重路徑，讓使用者明確知道目前的連線方式。

### Changed
- **無線模式 UX 優化**：
    - 成功開啟無線模式後，系統會自動中斷目前的 USB Tunnel 並重置 UI，引導使用者拔除線材後重新點擊「連線」以切換至無線通道。
    - 更新 i18n 指示文字，明確告知無線模式的後續操作流程。
- **提示訊息優化**：調整「以管理員身分執行」的警告強度，優先提示檢查 USB 連線與開發者模式狀態，減少對使用者的誤導。

### Fixed
- **斷線 UI 同步**：修正模擬行走中偵測到斷線時，左側連線狀態標籤未同步更新的問題。

## [1.5.0] - 2026-04-22

### Added
- **無線連線模式 (Wireless Mode)**：新增對 iPhone Wi-Fi 連線的支援。現在可以透過 USB 開啟無線功能，之後只要在同一個 Wi-Fi 下即可免插線進行定位模擬。
- **自動檢查更新 (Update Checker)**：App 啟動時會自動與 GitHub 最新 Release 進行比對，偵測到新版本時會彈出對話框顯示更新內容與下載連結。

### Changed
- **響應式 UI 優化 (Responsive UI)**：
    - 將左側側邊欄改為可捲動容器 (`CTkScrollableFrame`)，解決在小螢幕或低解析度環境下功能按鈕被裁切的問題。
    - 調降最小視窗尺寸至 `960x640`，並優化預設視窗佈局，提升在 13 吋筆電上的使用體驗。
- **版本號同步顯示**：視窗標題現在會自動顯示目前的 App 版本號。

### Fixed
- **專案換行符號規範化**：新增 `.gitattributes` 檔案，確保跨平台開發時程式碼格式一致，解決 Windows 換行符號導致的 Git 衝突問題。

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
