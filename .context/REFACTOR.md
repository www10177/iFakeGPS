# iFakeGPS 重構計畫

> 建立於 2026-06-20。三個 subagent 平行 review 的綜合結論 + 計畫。
> 目標:在加入「裝置畫面偽連拍(burst-capture)」前,把架構理乾淨。

## 診斷摘要(交叉驗證)

**好消息 — 地基是好的**
- 分層乾淨:`core` / `ui` / `utils` 沒有任何反向 import(無 core→ui)。三個 agent 一致確認。
- tunneld 殺行程樹的修正正確、必要。

**主要亂源**
1. **`app.py` 是 god object**(2913 行、~70 method),且有業務邏輯外洩到 UI:
   - GPS haversine(1674)、地理編碼 HTTP(2677)、GPX 序列化(2339)、winsdk 定位 asyncio(1007)、路徑/MEIPASS 計算、DB 路徑建構。
2. **`DeviceManager` 也是 god object**(連線 + 模擬定位 + 4 個 lockdown 工具 + dev-mode),且 `RouteWalker` 綁死具體 `DeviceManager`。**這是 burst-capture 的頭號阻礙**:新的 ScreenshotService 需要共用 `service_provider` 連線。
3. **約 250 行死碼**(已驗證,只有定義無呼叫):`_search_location`/`_on_search_result`(search_entry 從未建立)、`_change_map_type`、`_load_route_dialog`、`_apply_routing_settings`、`_save_current_simulated_location`、`_confirm_save_selected_location`。
4. **重複**:
   - appdata 路徑**三處各寫一套、且用了兩種根目錄**(`logger.py` 用 LOCALAPPDATA = 正解;兩個 storage 預設用 APPDATA;app.py 用 LOCALAPPDATA/cache)。
   - frozen/resource 路徑邏輯 4 份各自實作。
   - storage 鷹架(_connect/_init_schema/WAL)兩檔近乎雷同。
   - UDID 解析在 device_manager 複製 4 次(330/352/375/408)。
   - marker 渲染、座標欄位填值在多處複製。
5. **常數散落**:tunneld port `49151` 在 device_manager 硬寫 3 次;tile server URL、max_zoom、預設台北座標、timeout 各處 inline。
6. **靜默吞例外**:device_manager 有 5 個 `except: pass`(84/165/212/276/320)— 重構前最危險,失敗會隱形。另 `auto_mount_developer_disk_image` 失敗卻 `return True`(430)。
7. **`routes.db` 命名謊言**:app.py:106-107 讓 LocationStorage 與 RouteStorage 指向同一個 `routes.db`(table 不同所以目前沒撞,但會誤導)。
8. **models 外洩**:`RoutePoint.marker: object`(UI handle)、`DeviceInfo.display_name()` 內嵌 emoji。
9. **測試太薄**:只有 coordinate/update 有測;core 的 device/tunneld/walker/routing/storage 全無測 → 重構無安全網。

## 範圍決策(2026-06-20)
使用者選擇:**「整理乾淨,不過度拆分」**。因此本次**只做** Phase 0 + 精選的低風險清理,**不做** UI 面板大拆解、**不**把 DeviceManager 拆成多類別、**不**引入 LocationSink protocol。burst-capture 所需的連線存取,只要 DeviceManager 乾淨暴露既有 `service_provider`。search 死碼:直接刪除。

實際執行清單:
- [x] 刪除 ~250 行死碼(含 search)
- [x] `constants.py` 集中 port / tile servers / zoom / 預設座標 / repo slug
- [x] `utils` 加 `resource_path()` / `is_frozen()`;統一 appdata 路徑;修 routes.db 命名謊言
- [x] device_manager:補 5 個靜默 except 的 log、修 auto_mount return、抽 `_resolve_target_udid()`、用 TUNNELD_PORT 常數
- [x] app.py:抽重複的 marker 渲染 / 座標欄位填值小 helper(不做面板級拆解)
- [x] 補少量 characterization 測試當安全網
- [ ] (不做)Phase 2 UI 拆解、DeviceManager 多類別拆分、BaseSqliteStore

## 計畫(分階段,可逐階段交付)

### Phase 0 — 安全網 + 速效清理(低風險、高槓桿)
- [ ] 刪除已驗證的 ~250 行死碼(**search 例外:見下方決策**)。
- [ ] 為 `device_manager` 裝置清單解析、`routing` 內插補點加 characterization 測試(用既有 FakeResponse 模式)。
- [ ] 把 device_manager 的 5 個靜默 except 補上 log;修 `auto_mount` 的 return False。

### Phase 1 — 核心接縫(直接解鎖 burst-capture)
- [ ] 新增 `src/core/constants.py`:TUNNELD_PORT/URL、TILE_SERVERS、MAP_MAX_ZOOM、DEFAULT_MAP_POSITION、GITHUB_REPO。
- [ ] 新增 `resource_path()` / `is_frozen()`(放 utils)+ 統一 appdata 路徑為 `get_app_data_dir()`;修掉 routes.db 命名謊言。
- [ ] 拆 `DeviceManager` → `DeviceConnection`(擁有 RSD service_provider + async helper)+ `LocationSimulator`(DVT + set/clear)。
- [ ] 定義 `LocationSink` Protocol(單一 `set_location`),`RouteWalker` 改依賴它。
- [ ] ⇒ 之後 `ScreenshotService(service_provider)` 可直接接上,不必重寫連線/async。

### Phase 2 — UI 拆解(較大,分批)
- [ ] `run_async(work, on_success, on_error)` helper 取代 13 處手刻 thread+after。
- [ ] 色票/常數集中(取代滿地 hex)。
- [ ] 抽出面板:`SavedLocationsPanel`、`SavedRoutesPanel`(最低風險)→ `MapPanel` → `DeviceConnectionController`、`RouteController`、`UpdateController`。
- [ ] 以 per-panel i18n 註冊取代 `_update_ui_text` 的 115 行 hasattr 牆。

### Phase 3 — 核心清理(可與 Phase 2 平行)
- [ ] `BaseSqliteStore` 合併兩個 storage 鷹架;把 `SavedRouteInfo`/`SavedLocationInfo` 移進 models。
- [ ] `_haversine_distance` 改 static/free;抽 `geo.py` 純函式(可單測)。
- [ ] `DeviceManager`/連線 加 atexit/context-manager teardown(對稱 tunneld)。
- [ ] 把 `DeviceInfo.display_name()` 的 emoji 格式移到 UI formatter。

## 必須在重構中保留的脆弱點(risk notes)
- `_on_close` 關閉順序(清位置→停 walker→斷線→停 tunneld→destroy);auto-updater 靠它解鎖 exe。
- frozen `sys._MEIPASS` 的 icon 與手冊雙分支 + os.path.exists fallback。
- Tk 執行緒契約:所有 worker 透過 `self.after(0,...)` 回主緒;walker callback 不可直接碰 widget。
- lambda 預設參數綁值(避免 late-binding / except-var 清除)。
- 共用同一個 routes.db 連線(若拆面板,別開兩條)。
- `_navigate_to_saved_location` 跨叢集編排(saved→route→routing)是最難解的耦合,保留為 app 層協調呼叫。

## 待決策
- **search 功能**:目前是壞的死碼(UI 沒有 search box)。要(a)直接刪除,還是(b)重新接上一個搜尋框?README 有宣傳此功能。
- gpxpy 確認**有在用**,不可移除(修正 agent 的誤判)。
