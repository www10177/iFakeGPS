"""
i18n.py — Internationalization module for iFakeGPS.

Supports runtime language switching between English and Traditional Chinese.
Language is auto-detected from the OS locale at startup.

Usage:
    from src.ui.i18n import t, set_lang, get_lang, LANGUAGES

    label.configure(text=t("app_title"))
    set_lang("zh_TW")
"""

import locale

# ---------------------------------------------------------------------------
# String tables
# ---------------------------------------------------------------------------

_STRINGS: dict[str, dict[str, str]] = {}

_STRINGS["en"] = {
    # --- Window ---
    "app_title": "iFakeGPS - iOS Location Simulator",
    # --- Sidebar header ---
    "sidebar_title": "📍 iFakeGPS",
    "sidebar_subtitle": "iOS 17+ Location Simulator",
    # --- Developer Mode ---
    "dev_mode_label": "Dev Mode:",
    "dev_status_unknown": "⚪ Unknown",
    "dev_check_btn": "Check Status",
    "dev_enable_btn": "Enable Dev Mode",
    "dev_status_enabled": "🟢 Enabled",
    "dev_status_disabled": "🔴 Disabled",
    "dev_status_error": "⚠️ Could not check",
    # --- Device Selection ---
    "device_selection": "Device Selection",
    "no_devices": "No devices found.\nStart tunneld first:\npymobiledevice3 remote tunneld",
    "no_devices_admin": "No devices found.\n\nPlease ensure USB is connected and Developer Mode is enabled.\nIf problems persist, try running as Administrator.",
    "conn_not_connected": "⭕ Not Connected",
    "conn_failed": "🔴 Connection Failed",
    "btn_disconnect": "Disconnect",
    "status_scanning": "🔍 Scanning for devices...",
    "status_found_devices": "Found {count} device(s). Click to connect.",
    "status_no_devices": "⚠️ No devices found. Check connection and Developer Mode.",
    "status_connecting": "Connecting to {name}...",
    "status_connected": "Connected to {name}. Ready to simulate location.",
    "status_conn_failed": "Connection failed. Check tunneld status.",
    "status_disconnected": "Disconnected from device.",
    # --- Connection Error Dialog ---
    "dialog_conn_failed_title": "Connection Failed",
    "dialog_conn_failed_msg": (
        "Failed to connect to the device.\n\n"
        "Make sure:\n"
        "1. Developer Mode is enabled on device\n"
        "2. tunneld is running (try restarting as admin if it fails)\n"
        "3. Device is connected via USB or same Wi-Fi\n"
        "4. Trust this computer on your device"
    ),
    # --- Mode ---
    "mode_label": "🎯 Mode",
    "mode_single": "Single Point",
    "mode_route": "Route Walking",
    "mode_navigation": "Navigation (Roads)",
    # --- Route Walking ---
    "route_walking": "Route Walking",
    "speed_label": "Walking Speed:",
    "noise_label": "Speed Noise:",
    "btn_calc_route": "🗺 Calc Route",
    "btn_start": "▶ Start",
    "btn_pause": "⏸ Pause",
    "btn_stop": "⏹ Stop",
    "btn_delete_route": "🗑 Delete",
    "chk_loop": "Loop route continuously",
    "btn_clear_route": "🗑 Clear Route",
    "route_info": "Points: {points} | Distance: {distance}",
    # --- Route Storage ---
    "route_storage_title": "📂 Saved Routes",
    "btn_save_route": "💾 Save",
    "btn_load_route": "📂 Load",
    "btn_import_gpx": "📥 Import GPX",
    "btn_export_gpx": "📤 Export GPX",
    "dialog_save_title": "Save Route",
    "dialog_save_msg": "Enter a name for this route:",
    "dialog_load_title": "Load Route",
    "dialog_load_msg": "Select a route to load (Double-click or use Load button, Right-click or use Delete button to delete):",
    "dialog_saved_title": "Saved",
    "dialog_saved_msg": "Route '{name}' successfully saved.",
    "dialog_info_title": "Info",
    "dialog_no_routes_msg": "No saved routes found.",
    "dialog_delete_title": "Delete",
    "dialog_delete_confirm_msg": "Delete '{name}'?",
    "marker_start": "Start",
    "marker_end": "End",
    "marker_point": "P{index}",
    "status_route_loaded": "Loaded route: {name}",
    "dialog_exported_title": "Exported",
    "dialog_exported_msg": "Saved to {path}",
    "dialog_gpx_error_title": "GPX Error",
    "dialog_gpx_error_msg": "Failed to import GPX:\n{error}",
    "status_gpx_loaded": "GPX Loaded: {name} ({points} pts)",
    # --- Settings (Routing) ---
    "settings_routing_title": "⚙ Routing Provider",
    "tab_storage": "Storage",
    "tab_routing": "Routing",
    "provider_osrm": "OSRM (Demo, Free)",
    "provider_ors": "OpenRouteService",
    "api_key_placeholder": "ORS API Key",
    "btn_apply": "Apply",
    # --- Quick Panel ---
    "quick_panel_title": "Quick Access",
    "tab_places": "Places",
    "tab_routes": "Routes",
    "placeholder_location_name": "Place name",
    "btn_save_location": "Save Place",
    "btn_cancel_save_location": "Cancel Selection",
    "btn_pick_location_on_map": "Pick on Map",
    "btn_use_current_position": "Use Current GPS",
    "location_panel_hint": "Enter coordinates directly, pick a place on the map, or use the current simulated GPS position.",
    "empty_locations": "No saved places yet.",
    "default_location_name": "Place {lat}, {lon}",
    "status_location_saved": "Saved place: {name}",
    "status_select_saved_location": "Click the place on the map that you want to save.",
    "status_location_coordinates_filled": "Coordinates ready: {lat}, {lon}",
    "status_location_save_cancelled": "Place save cancelled.",
    "status_location_selected": "Selected place: {name}",
    "status_no_current_position": "No current simulated position yet.",
    "status_jumped_current_position": "Map centered on current position.",
    "status_follow_enabled": "Map follow enabled.",
    "status_follow_disabled": "Map follow disabled.",
    "dialog_delete_location_title": "Delete Place",
    "dialog_delete_location_confirm_msg": "Delete place '{name}'?",
    "btn_jump": "Jump",
    "btn_teleport_short": "Set",
    "btn_delete_short": "Delete",
    "btn_refresh": "Refresh",
    "route_row_meta": "{points} pts - {created}",
    "tip_jump_current_position": "Jump to the current simulated position",
    "tip_follow_current_position": "Lock/unlock map follow during navigation",
    "tip_place_jump": "Jump map to this place",
    "tip_place_teleport": "Set GPS to this place",
    "tip_place_navigate": "Plan a route from current position to this place",
    "tip_place_delete": "Delete this place",
    "marker_save_place": "Save this place?",
    "dialog_confirm_save_location_title": "Save Place",
    "dialog_confirm_save_location_msg": "Save this selected place?\n\nLatitude: {lat}\nLongitude: {lon}",
    "dialog_confirm_save_current_location_msg": "Save the current simulated GPS position?\n\nLatitude: {lat}\nLongitude: {lon}",
    # --- Manual Coordinates ---
    "manual_coords": "📍 Manual Coordinates",
    "label_lat": "Latitude:",
    "label_lon": "Longitude:",
    "btn_teleport": "✈ Teleport",
    "btn_enable_wireless": "Enable Wireless Mode",
    "status_wireless_enabling": "Enabling wireless mode...",
    "status_wireless_enabled": "Wireless mode enabled! Unplug the USB and click 'Connect' again to use wireless mode.",
    "status_wireless_failed": "Failed to enable wireless mode. Ensure USB is connected.",
    "dialog_wireless_title": "Enable Wireless Mode",
    "dialog_wireless_msg": (
        "This will enable wireless connectivity for your iPhone.\n\n"
        "1. Ensure USB is currently connected.\n"
        "2. Once enabled, unplug the cable and click the connect button to reconnect.\n"
        "3. Ensure phone and computer are on the SAME Wi-Fi.\n\n"
        "Proceed now?"
    ),
    "tip_wireless": "Once enabled, the device will appear automatically over Wi-Fi (no cable needed).",
    "btn_clear_location": "🔄 Clear Simulated Location",
    "btn_show_logs": "Log",
    "log_viewer_title": "iFakeGPS Logs",
    "btn_refresh_log": "Refresh",
    "log_empty": "No log entries yet.",
    # --- Info label ---
    "info_tunneld": "💡 Start tunneld first (as admin):\npymobiledevice3 remote tunneld",
    # --- Status bar ---
    "status_ready": "Ready. Click on the map to set location or add route points.",
    "status_single_mode": "Single Point Mode: Click map to teleport.",
    "status_route_mode": "Route Mode: Click map to add waypoints.",
    "status_nav_mode": "Navigation Mode: Click map to add destinations.",
    "status_calculating_route": "⏳ Calculating route via API...",
    "status_calc_failed": "❌ Route calculation failed: {error}",
    "status_calc_success": "✅ Route calculated. Ready to walk.",
    "dialog_routing_error_title": "Routing Error",
    "status_point_added": "Added point {index} at {lat}, {lon} (right-click to remove)",
    "status_point_removed": "Removed point. {count} points remaining.",
    "status_walking": "🚶 Walking route...",
    "status_resumed": "▶ Resumed walking...",
    "status_paused": "⏸ Paused. Press ▶ to continue from here.",
    "status_not_walking": "Not currently walking.",
    "status_walk_stopped": "⏹ Walking stopped.",
    "status_walk_complete": "✅ Route walk completed!",
    "status_walk_paused_disconnected": "⚠️ Device disconnected. Walking paused.",
    "notify_walk_complete_title": "iFakeGPS",
    "notify_walk_complete_body": "Route walk completed! All waypoints have been visited.",
    "notify_device_disconnected_title": "iFakeGPS",
    "notify_device_disconnected_body": "Current device disconnected. Walking has been paused.",
    "status_route_cleared": "Route cleared.",
    "status_setting_location": "Setting location to {lat}, {lon}...",
    "status_location_set": "✅ Location set to {lat}, {lon}",
    "status_location_failed": "❌ Failed to set location. Check connection.",
    "status_teleport_cancelled": "Teleport cancelled.",
    "status_clearing_location": "Clearing location simulation...",
    "status_location_cleared": "✅ Location simulation cleared.",
    "status_location_clear_failed": "❌ Failed to clear location.",
    "status_opened_log_viewer": "Opened log viewer.",
    "status_device_not_connected": "⚠️ Device not connected. Connect first.",
    "status_navigation_from_current": "Planning route from current position to {name}...",
    # --- Tunneld status ---
    "status_checking_tunneld": "🔄 Checking tunneld service...",
    "status_tunneld_found": "✅ Tunneld found! Scanning devices...",
    "status_starting_tunneld": "🔄 Starting tunneld (admin mode)...",
    "status_tunneld_started": "✅ Tunneld started! Scanning devices...",
    "status_tunneld_failed": "⚠️ Failed to start tunneld. Check for errors.",
    "status_tunneld_need_admin": "⚠️ Run as Administrator to auto-start tunneld.",
    "status_tunneld_detected": "✅ Tunneld detected! Scanning devices...",
    "status_tunneld_stopped": "⚠️ tunneld stopped unexpectedly",
    # --- Teleport confirmation ---
    "marker_teleport_here": "📍 Teleport here?",
    "dialog_confirm_teleport_title": "Confirm Teleport",
    "dialog_confirm_teleport_msg": "Teleport to this location?\n\nLatitude: {lat}\nLongitude: {lon}",
    "marker_current_location": "📍 Current Location",
    # --- Dialogs ---
    "dialog_not_connected_title": "Not Connected",
    "dialog_not_connected_msg": "Please connect to a device first.",
    "dialog_current_position_required_title": "Current Position Required",
    "dialog_current_position_required_msg": (
        "Please set your current position first using Single Point teleport."
    ),
    "dialog_invalid_route_title": "Invalid Route",
    "dialog_invalid_route_msg": "Please add at least 2 points to the route.",
    "dialog_invalid_coords_title": "Invalid Coordinates",
    "dialog_invalid_coords_msg": "Please enter valid latitude (-90 to 90) and longitude (-180 to 180).",
    "dialog_log_open_failed_title": "Cannot Open Logs",
    "dialog_log_open_failed_msg": "Failed to open logs:\n{error}",
    "dialog_walk_disconnected_title": "Device Disconnected",
    "dialog_walk_disconnected_msg": (
        "Current device was disconnected.\n\n"
        "Route walking has been paused automatically.\n"
        "Reconnect the device, then press Start to resume."
    ),
    "dialog_notify_reg_title": "Enable Windows Notifications",
    "dialog_notify_reg_msg": (
        "Windows notification identity is not registered yet.\n\n"
        "Register now to improve toast popup reliability and sound?\n"
        "(You only need to do this once.)"
    ),
    "dialog_notify_reg_done_title": "Registration Completed",
    "dialog_notify_reg_done_msg": (
        "Windows notification identity has been registered.\n"
        "Please restart iFakeGPS for best results."
    ),
    "dialog_notify_reg_failed_title": "Registration Failed",
    "dialog_notify_reg_failed_msg": (
        "Failed to register Windows notification identity.\n"
        "You can continue, but toast popup may be unreliable."
    ),
    "dialog_update_available_title": "Update Available",
    "dialog_update_changelog_empty": "(No changelog content provided)",
    "dialog_update_available_msg": (
        "A new version is available.\n\n"
        "Current: {current}\n"
        "Latest: {latest}\n\n"
        "Latest changelog:\n"
        "{changelog}\n\n"
        "Download URL:\n"
        "{url}\n\n"
        "Open the release page now?"
    ),
    "dialog_update_available_msg_auto": (
        "A new version is available.\n\n"
        "Current: {current}\n"
        "Latest: {latest}\n\n"
        "Latest changelog:\n"
        "{changelog}\n\n"
        "Download and install it now? The app will restart automatically."
    ),
    "update_progress_title": "Updating",
    "update_progress_downloading": "Downloading new version... {pct}%",
    "update_progress_preparing": "Download complete. Restarting to apply...",
    "update_failed_title": "Update Failed",
    "update_failed_msg": (
        "Could not download the update:\n{error}\n\n"
        "Open the release page to download it manually?"
    ),
    # --- Device screen preview (burst capture) ---
    "tip_device_preview": "Show device screen preview",
    "preview_window_title": "Device Screen Preview",
    "preview_not_connected": "Connect to a device first.",
    "preview_status_waiting": "Capturing device screen...",
    "preview_status_error": "Cannot capture screen: {error}",
    "preview_rate_label": "Refresh:",
    "preview_rate_slow": "Slow",
    "preview_rate_mid": "Medium",
    "preview_rate_fast": "Fast",
    "dialog_enable_dev_title": "Enable Developer Mode",
    "dialog_enable_dev_msg": (
        "This command will trigger 'Enable Developer Mode' on the connected device.\n\n"
        "The device will need to RESTART.\n"
        "After restart, unlock the device and tap 'Turn On' in the alert.\n\n"
        "Do you want to proceed?"
    ),
    "dialog_dev_step1": "Triggering Developer Menu...\nPlease wait...",
    # --- Dev Mode Guide ---
    "guide_title": "How to Enable Developer Mode",
    "guide_heading": "📱 Enable iOS Developer Mode",
    "guide_step1_title": "1. Open Settings",
    "guide_step1_desc": "Go to Settings on your iPhone/iPad.",
    "guide_step2_title": "2. Privacy & Security",
    "guide_step2_desc": "Tap 'Privacy & Security'.",
    "guide_step3_title": "3. Developer Mode",
    "guide_step3_desc": "Scroll to the bottom, find 'Developer Mode'.",
    "guide_step4_title": "4. Turn On",
    "guide_step4_desc": "Enter and turn on the toggle. The system will ask to restart.",
    "guide_step5_title": "5. Confirm",
    "guide_step5_desc": "After restarting, unlock and tap 'Turn On', enter your passcode.",
    "guide_step6_title": "6. Connect",
    "guide_step6_desc": "Connect to computer via USB and tap 'Trust'.",
    "guide_btn_manual": "📖 Open Full Manual",
    "guide_btn_close": "Got it",
    # --- Tooltip: Speed ---
    "tip_speed": (
        "Movement speed (km/h)\n\n"
        "🚶 Walking          4 – 6 km/h\n"
        "🚲 Cycling         15 – 25 km/h\n"
        "🛵 Scooter         40 – 80 km/h\n"
        "🚗 Driving         60 – 120 km/h\n"
        "🚄 Train / HSR    100 – 350 km/h\n"
        "✈️ Airplane       800 – 900 km/h"
    ),
    # --- Tooltip: Noise ---
    "tip_noise": (
        "Speed randomness (noise)\n\n"
        "Simulates natural speed variation during movement.\n"
        "Set to 0%  → constant speed\n"
        "Set to 20% → speed varies within ±20%\n"
        "Example: 5 km/h + 20% noise:\n"
        "  Actual speed range ≈ 4 – 6 km/h"
    ),
    # --- Language selector ---
    "lang_label": "🌐 Language:",
}

_STRINGS["zh_TW"] = {
    # --- Window ---
    "app_title": "iFakeGPS - iOS 定位模擬器",
    # --- Sidebar header ---
    "sidebar_title": "📍 iFakeGPS",
    "sidebar_subtitle": "iOS 17+ 定位模擬器",
    # --- Developer Mode ---
    "dev_mode_label": "開發者模式：",
    "dev_status_unknown": "⚪ 未知",
    "dev_check_btn": "檢查狀態",
    "dev_enable_btn": "啟用開發者模式",
    "dev_status_enabled": "🟢 已啟用",
    "dev_status_disabled": "🔴 未啟用",
    "dev_status_error": "⚠️ 無法檢查",
    # --- Device Selection ---
    "device_selection": "裝置選擇",
    "no_devices": "找不到裝置。\n請先啟動 tunneld：\npymobiledevice3 remote tunneld",
    "no_devices_admin": "找不到裝置。\n\n請確認 USB 已連接並開啟開發者模式。\n若仍有問題，請嘗試以系統管理員身分重新啟動。",
    "conn_not_connected": "⭕ 未連線",
    "conn_failed": "🔴 連線失敗",
    "btn_disconnect": "中斷連線",
    "status_scanning": "🔍 正在掃描裝置...",
    "status_found_devices": "找到 {count} 個裝置，點擊以連線。",
    "status_no_devices": "⚠️ 找不到裝置。請確認連線並開啟開發者模式。",
    "status_connecting": "正在連線到 {name}...",
    "status_connected": "已連線到 {name}，可以開始模擬定位。",
    "status_conn_failed": "連線失敗，請檢查 tunneld 狀態。",
    "status_disconnected": "已中断連線。",
    # --- Connection Error Dialog ---
    "dialog_conn_failed_title": "連線失敗",
    "dialog_conn_failed_msg": (
        "無法連線到裝置。\n\n"
        "請確認：\n"
        "1. 裝置已開啟開發者模式\n"
        "2. tunneld 正在執行（若失敗請嘗試以管理員身分重啟）\n"
        "3. 裝置已透過 USB 或同一個 Wi-Fi 連接\n"
        "4. 在裝置上點擊「信任這部電腦」"
    ),
    # --- Mode ---
    "mode_label": "🎯 模式",
    "mode_single": "單點定位",
    "mode_route": "路線模式",
    "mode_navigation": "導航模式（道路）",
    # --- Route Walking ---
    "route_walking": "路線行走",
    "speed_label": "移動速度：",
    "noise_label": "速度噪音：",
    "btn_calc_route": "🗺 規劃路線",
    "btn_start": "▶ 開始",
    "btn_pause": "⏸ 暫停",
    "btn_stop": "⏹ 停止",
    "btn_delete_route": "🗑 刪除",
    "chk_loop": "循環路線",
    "btn_clear_route": "🗑 清除路線",
    "route_info": "路點：{points} | 距離：{distance}",
    # --- Route Storage ---
    "route_storage_title": "📂 路線管理",
    "btn_save_route": "💾 儲存",
    "btn_load_route": "📂 載入",
    "btn_import_gpx": "📥 匯入",
    "btn_export_gpx": "📤 匯出",
    "dialog_save_title": "儲存路線",
    "dialog_save_msg": "請輸入路線名稱：",
    "dialog_load_title": "載入路線",
    "dialog_load_msg": "請選擇要載入的路線（可雙擊或按「載入」；可右鍵或按「刪除」）：",
    "dialog_saved_title": "已儲存",
    "dialog_saved_msg": "路線「{name}」儲存成功。",
    "dialog_info_title": "提示",
    "dialog_no_routes_msg": "目前沒有已儲存的路線。",
    "dialog_delete_title": "刪除路線",
    "dialog_delete_confirm_msg": "要刪除「{name}」嗎？",
    "marker_start": "起點",
    "marker_end": "終點",
    "marker_point": "點 {index}",
    "status_route_loaded": "已載入路線：{name}",
    "dialog_exported_title": "已匯出",
    "dialog_exported_msg": "已儲存到 {path}",
    "dialog_gpx_error_title": "GPX 錯誤",
    "dialog_gpx_error_msg": "匯入 GPX 失敗：\n{error}",
    "status_gpx_loaded": "GPX 已載入：{name}（{points} 點）",
    # --- Settings (Routing) ---
    "settings_routing_title": "⚙ 導航引擎",
    "tab_storage": "路線儲存",
    "tab_routing": "導航設定",
    "provider_osrm": "OSRM (公共免費)",
    "provider_ors": "OpenRouteService",
    "api_key_placeholder": "ORS API Key",
    "btn_apply": "套用",
    # --- Quick Panel ---
    "quick_panel_title": "快速存取",
    "tab_places": "地點",
    "tab_routes": "路線",
    "placeholder_location_name": "地點名稱",
    "btn_save_location": "儲存地點",
    "btn_cancel_save_location": "取消選取",
    "btn_pick_location_on_map": "地圖選取",
    "btn_use_current_position": "使用目前 GPS",
    "location_panel_hint": "可直接輸入座標、從地圖選取，或使用目前模擬中的 GPS 位置。",
    "empty_locations": "尚未儲存任何地點。",
    "default_location_name": "地點 {lat}, {lon}",
    "status_location_saved": "已儲存地點：{name}",
    "status_select_saved_location": "請在地圖上點選要儲存的地點。",
    "status_location_coordinates_filled": "座標已填入：{lat}, {lon}",
    "status_location_save_cancelled": "已取消儲存地點。",
    "status_location_selected": "已選擇地點：{name}",
    "status_no_current_position": "目前還沒有模擬中的位置。",
    "status_jumped_current_position": "地圖已跳轉到目前位置。",
    "status_follow_enabled": "已開啟地圖跟隨。",
    "status_follow_disabled": "已關閉地圖跟隨。",
    "dialog_delete_location_title": "刪除地點",
    "dialog_delete_location_confirm_msg": "要刪除地點「{name}」嗎？",
    "btn_jump": "跳轉",
    "btn_teleport_short": "設定",
    "btn_delete_short": "刪除",
    "btn_refresh": "刷新",
    "route_row_meta": "{points} 點 - {created}",
    "tip_jump_current_position": "跳轉到目前模擬位置",
    "tip_follow_current_position": "鎖定/解除導航時的地圖跟隨",
    "tip_place_jump": "將地圖跳轉到此地點",
    "tip_place_teleport": "將 GPS 設定到此地點",
    "tip_place_navigate": "從目前位置規劃導航到此地點",
    "tip_place_delete": "刪除此地點",
    "marker_save_place": "要儲存這裡嗎？",
    "dialog_confirm_save_location_title": "儲存地點",
    "dialog_confirm_save_location_msg": "要儲存這個選取的地點嗎？\n\n緯度：{lat}\n經度：{lon}",
    "dialog_confirm_save_current_location_msg": "要儲存目前模擬中的 GPS 位置嗎？\n\n緯度：{lat}\n經度：{lon}",
    # --- Manual Coordinates ---
    "manual_coords": "📍 手動座標",
    "label_lat": "緯度：",
    "label_lon": "經度：",
    "btn_teleport": "✈ 瞬間移動",
    "btn_enable_wireless": "開啟無線模式",
    "status_wireless_enabling": "正在開啟無線模式...",
    "status_wireless_enabled": "無線模式已開啟！請拔掉 USB 後，重新點擊「連線」按鈕即可使用無線模式。",
    "status_wireless_failed": "開啟無線模式失敗，請確保已連接 USB。",
    "dialog_wireless_title": "開啟無線模式",
    "dialog_wireless_msg": (
        "此操作將開啟 iPhone 的無線連線功能。\n\n"
        "1. 請確保目前已連接 USB。\n"
        "2. 開啟後，請拔掉傳輸線，並點擊連線按鈕重新連線。\n"
        "3. 請確保手機與電腦在「同一個 Wi-Fi」下。\n\n"
        "是否現在開啟？"
    ),
    "tip_wireless": "開啟後，只要在同一個 Wi-Fi 下，下次不需插線即可自動連線。",
    "btn_clear_location": "🔄 清除模擬定位",
    "btn_show_logs": "Log",
    "log_viewer_title": "iFakeGPS Logs",
    "btn_refresh_log": "重新整理",
    "log_empty": "目前沒有 Log 內容。",
    # --- Info label ---
    "info_tunneld": "💡 請先以管理員身分啟動 tunneld：\npymobiledevice3 remote tunneld",
    # --- Status bar ---
    "status_ready": "就緒。點擊地圖以設定位置或新增路線點。",
    "status_single_mode": "單點模式：點擊地圖以瞬間移動到該位置。",
    "status_route_mode": "路線模式：點擊地圖以新增路線點。",
    "status_nav_mode": "導航模式：點擊地圖以新增目的地。",
    "status_calculating_route": "⏳ 正在透過 API 規劃路線...",
    "status_calc_failed": "❌ 路線規劃失敗：{error}",
    "status_calc_success": "✅ 路線規劃完成，可以開始導航。",
    "dialog_routing_error_title": "導航錯誤",
    "status_point_added": "已新增第 {index} 點：{lat}, {lon}（可右鍵刪除）",
    "status_point_removed": "已刪除路點，目前剩 {count} 點。",
    "status_walking": "🚶 路線行走中...",
    "status_resumed": "▶ 已繼續行走...",
    "status_paused": "⏸ 已暫停。按 ▶ 從目前位置繼續。",
    "status_not_walking": "目前未在行走。",
    "status_walk_stopped": "⏹ 行走已停止。",
    "status_walk_complete": "✅ 路線行走完成！",
    "status_walk_paused_disconnected": "⚠️ 裝置已斷線，行走已暫停。",
    "notify_walk_complete_title": "iFakeGPS",
    "notify_walk_complete_body": "路線行走已完成！所有路點均已到達。",
    "notify_device_disconnected_title": "iFakeGPS",
    "notify_device_disconnected_body": "目前的裝置已斷線，行走已自動暫停。",
    "status_route_cleared": "路線已清除。",
    "status_setting_location": "正在設定位置到 {lat}, {lon}...",
    "status_location_set": "✅ 位置已設定到 {lat}, {lon}",
    "status_location_failed": "❌ 設定位置失敗，請檢查連線。",
    "status_teleport_cancelled": "已取消瞬間移動。",
    "status_clearing_location": "正在清除模擬定位...",
    "status_location_cleared": "✅ 模擬定位已清除。",
    "status_location_clear_failed": "❌ 清除定位失敗。",
    "status_opened_log_viewer": "已開啟 Log 視窗。",
    "status_device_not_connected": "⚠️ 裝置未連線，請先連線。",
    "status_navigation_from_current": "正在從目前位置規劃到「{name}」的路線...",
    # --- Tunneld status ---
    "status_checking_tunneld": "🔄 正在檢查 tunneld 服務...",
    "status_tunneld_found": "✅ 已偵測到 tunneld！正在掃描裝置...",
    "status_starting_tunneld": "🔄 正在啟動 tunneld（管理員模式）...",
    "status_tunneld_started": "✅ tunneld 已啟動！正在掃描裝置...",
    "status_tunneld_failed": "⚠️ 啟動 tunneld 失敗，請檢查錯誤。",
    "status_tunneld_need_admin": "⚠️ 需要以系統管理員身分執行以自動啟動 tunneld。",
    "status_tunneld_detected": "✅ 已偵測到 tunneld！正在掃描裝置...",
    "status_tunneld_stopped": "⚠️ tunneld 意外停止",
    # --- Teleport confirmation ---
    "marker_teleport_here": "📍 瞬移到這裡？",
    "dialog_confirm_teleport_title": "確認瞬間移動",
    "dialog_confirm_teleport_msg": "要瞬間移動到此位置嗎？\n\n緯度：{lat}\n經度：{lon}",
    "marker_current_location": "📍 目前位置",
    # --- Dialogs ---
    "dialog_not_connected_title": "未連線",
    "dialog_not_connected_msg": "請先連線到裝置。",
    "dialog_current_position_required_title": "需要目前位置",
    "dialog_current_position_required_msg": "請先透過單點定位瞬間移動，設定目前位置。",
    "dialog_invalid_route_title": "路線無效",
    "dialog_invalid_route_msg": "請至少新增 2 個路線點。",
    "dialog_invalid_coords_title": "座標無效",
    "dialog_invalid_coords_msg": "請輸入有效的緯度（-90 到 90）和經度（-180 到 180）。",
    "dialog_log_open_failed_title": "無法開啟 Log",
    "dialog_log_open_failed_msg": "開啟 Log 失敗：\n{error}",
    "dialog_walk_disconnected_title": "裝置已斷線",
    "dialog_walk_disconnected_msg": (
        "目前的裝置已斷線。\n\n"
        "路線移動已自動暫停。\n"
        "請重新連線後按「開始」繼續。"
    ),
    "dialog_notify_reg_title": "啟用 Windows 通知",
    "dialog_notify_reg_msg": (
        "尚未註冊 Windows 通知身分。\n\n"
        "是否現在註冊，以提高通知彈出與聲音的成功率？\n"
        "（只需設定一次）"
    ),
    "dialog_notify_reg_done_title": "註冊完成",
    "dialog_notify_reg_done_msg": (
        "已完成 Windows 通知身分註冊。\n"
        "建議重新啟動 iFakeGPS 以獲得最佳效果。"
    ),
    "dialog_notify_reg_failed_title": "註冊失敗",
    "dialog_notify_reg_failed_msg": (
        "Windows 通知身分註冊失敗。\n"
        "你仍可繼續使用，但通知彈出可能不穩定。"
    ),
    "dialog_update_available_title": "有可用更新",
    "dialog_update_changelog_empty": "（此版本未提供更新內容）",
    "dialog_update_available_msg": (
        "偵測到新版本。\n\n"
        "目前版本：{current}\n"
        "最新版本：{latest}\n\n"
        "最新版本更新內容：\n"
        "{changelog}\n\n"
        "下載網址：\n"
        "{url}\n\n"
        "是否現在開啟下載頁面？"
    ),
    "dialog_update_available_msg_auto": (
        "偵測到新版本。\n\n"
        "目前版本：{current}\n"
        "最新版本：{latest}\n\n"
        "最新版本更新內容：\n"
        "{changelog}\n\n"
        "是否現在下載並安裝？完成後將自動重新啟動。"
    ),
    "update_progress_title": "更新中",
    "update_progress_downloading": "正在下載新版本... {pct}%",
    "update_progress_preparing": "下載完成，正在重新啟動以套用更新...",
    "update_failed_title": "更新失敗",
    "update_failed_msg": (
        "無法下載更新：\n{error}\n\n"
        "是否開啟下載頁面手動下載？"
    ),
    # --- 裝置畫面預覽（連拍）---
    "tip_device_preview": "顯示裝置畫面預覽",
    "preview_window_title": "裝置畫面預覽",
    "preview_not_connected": "請先連接裝置。",
    "preview_status_waiting": "正在擷取裝置畫面...",
    "preview_status_error": "無法擷取畫面：{error}",
    "preview_rate_label": "更新頻率：",
    "preview_rate_slow": "慢",
    "preview_rate_mid": "中",
    "preview_rate_fast": "快",
    "dialog_enable_dev_title": "啟用開發者模式",
    "dialog_enable_dev_msg": (
        "此操作將在已連接的裝置上觸發「啟用開發者模式」。\n\n"
        "裝置需要重新啟動。\n"
        "重啟後解鎖裝置，並在提示中點選「開啟」。\n\n"
        "要繼續嗎？"
    ),
    "dialog_dev_step1": "正在觸發開發者選單...\n請稍候...",
    # --- Dev Mode Guide ---
    "guide_title": "如何開啟開發者模式",
    "guide_heading": "📱 開啟 iOS 開發者模式",
    "guide_step1_title": "1. 進入設定",
    "guide_step1_desc": "進入 iPhone/iPad 的「設定」。",
    "guide_step2_title": "2. 隱私權與安全性",
    "guide_step2_desc": "點選「隱私權與安全性」。",
    "guide_step3_title": "3. 開發者模式",
    "guide_step3_desc": "滑動到最底部，找到「開發者模式」。",
    "guide_step4_title": "4. 開啟開關",
    "guide_step4_desc": "進入並將開關打開。系統會要求重新啟動。",
    "guide_step5_title": "5. 確認開啟",
    "guide_step5_desc": "重啟後解鎖，點選「開啟」並輸入密碼。",
    "guide_step6_title": "6. 連接電腦",
    "guide_step6_desc": "使用 USB 連接電腦，並點選「信任」。",
    "guide_btn_manual": "📖 打開完整說明書",
    "guide_btn_close": "我知道了",
    # --- Tooltip: Speed ---
    "tip_speed": (
        "移動速度（km/h）\n\n"
        "🚶 步行           4 – 6 km/h\n"
        "🚲 腳踏車        15 – 25 km/h\n"
        "🛵 機車          40 – 80 km/h\n"
        "🚗 開車          60 – 120 km/h\n"
        "🚄 高鐵 / 火車   100 – 350 km/h\n"
        "✈️ 飛機         800 – 900 km/h"
    ),
    # --- Tooltip: Noise ---
    "tip_noise": (
        "速度隨機擾動幅度\n\n"
        "模擬真實移動時速度的自然變化。\n"
        "設為 0%  → 完全固定速度\n"
        "設為 20% → 速度在 ±20% 範圍內隨機波動\n"
        "例如設 5 km/h + 20% 噪音：\n"
        "  實際速度區間約 4 – 6 km/h"
    ),
    # --- Language selector ---
    "lang_label": "🌐 語言：",
}

# ---------------------------------------------------------------------------
# Supported languages (display name → code)
# ---------------------------------------------------------------------------
LANGUAGES = {
    "English": "en",
    "繁體中文": "zh_TW",
}

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

_current_lang: str = "en"


def _detect_system_lang() -> str:
    """Auto-detect language from OS locale. Default to English."""
    try:
        system_locale = locale.getdefaultlocale()[0] or ""
        if system_locale.startswith("zh"):
            return "zh_TW"
    except Exception:
        pass
    return "en"


def set_lang(lang_code: str) -> None:
    """Set the current language. Use 'en' or 'zh_TW'."""
    global _current_lang
    if lang_code in _STRINGS:
        _current_lang = lang_code
    else:
        _current_lang = "en"


def get_lang() -> str:
    """Return the current language code."""
    return _current_lang


def t(key: str, **kwargs) -> str:
    """
    Translate a string key to the current language.

    Supports format placeholders:
        t("status_found_devices", count=3)
        → "Found 3 device(s). Click to connect."
    """
    table = _STRINGS.get(_current_lang, _STRINGS["en"])
    text = table.get(key) or _STRINGS["en"].get(key, f"[{key}]")
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


# Auto-detect on import
set_lang(_detect_system_lang())
