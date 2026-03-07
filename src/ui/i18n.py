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
from typing import Dict

# ---------------------------------------------------------------------------
# String tables
# ---------------------------------------------------------------------------

_STRINGS: Dict[str, Dict[str, str]] = {}

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
    "no_devices_admin": "No devices found.\n\nPlease restart the application\nas Administrator to enable connectivity!",
    "conn_not_connected": "⭕ Not Connected",
    "conn_failed": "🔴 Connection Failed",
    "btn_disconnect": "Disconnect",
    "status_scanning": "🔍 Scanning for devices...",
    "status_found_devices": "Found {count} device(s). Click to connect.",
    "status_no_devices": "⚠️ No connected devices found. Please run as Administrator.",
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
        "2. tunneld is running: pymobiledevice3 remote tunneld\n"
        "3. Device is connected via USB\n"
        "4. Run tunneld as Administrator/root"
    ),
    # --- Mode ---
    "mode_label": "🎯 Mode",
    "mode_single": "Single Point",
    "mode_route": "Route Mode",
    # --- Route Walking ---
    "route_walking": "Route Walking",
    "speed_label": "Walking Speed:",
    "noise_label": "Speed Noise:",
    "btn_start": "▶ Start",
    "btn_pause": "⏸ Pause",
    "btn_stop": "⏹ Stop",
    "chk_loop": "Loop route continuously",
    "btn_clear_route": "🗑 Clear Route",
    "route_info": "Points: {points} | Distance: {distance}",
    # --- Manual Coordinates ---
    "manual_coords": "📍 Manual Coordinates",
    "label_lat": "Latitude:",
    "label_lon": "Longitude:",
    "btn_teleport": "✈ Teleport",
    "btn_clear_location": "🔄 Clear Simulated Location",
    # --- Info label ---
    "info_tunneld": "💡 Start tunneld first (as admin):\npymobiledevice3 remote tunneld",
    # --- Status bar ---
    "status_ready": "Ready. Click on the map to set location or add route points.",
    "status_single_mode": "Single Point Mode: Click on the map to teleport to that location.",
    "status_route_mode": "Route Mode: Click on the map to add waypoints for walking.",
    "status_walking": "🚶 Walking route...",
    "status_resumed": "▶ Resumed walking...",
    "status_paused": "⏸ Paused. Press ▶ to continue from here.",
    "status_not_walking": "Not currently walking.",
    "status_walk_stopped": "⏹ Walking stopped.",
    "status_walk_complete": "✅ Route walk completed!",
    "status_route_cleared": "Route cleared.",
    "status_setting_location": "Setting location to {lat}, {lon}...",
    "status_location_set": "✅ Location set to {lat}, {lon}",
    "status_location_failed": "❌ Failed to set location. Check connection.",
    "status_teleport_cancelled": "Teleport cancelled.",
    "status_clearing_location": "Clearing location simulation...",
    "status_location_cleared": "✅ Location simulation cleared.",
    "status_location_clear_failed": "❌ Failed to clear location.",
    "status_device_not_connected": "⚠️ Device not connected. Connect first.",
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
    "dialog_invalid_route_title": "Invalid Route",
    "dialog_invalid_route_msg": "Please add at least 2 points to the route.",
    "dialog_invalid_coords_title": "Invalid Coordinates",
    "dialog_invalid_coords_msg": "Please enter valid latitude (-90 to 90) and longitude (-180 to 180).",
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
    "no_devices_admin": "找不到裝置。\n\n請以系統管理員身分\n重新啟動應用程式！",
    "conn_not_connected": "⭕ 未連線",
    "conn_failed": "🔴 連線失敗",
    "btn_disconnect": "中斷連線",
    "status_scanning": "🔍 正在掃描裝置...",
    "status_found_devices": "找到 {count} 個裝置，點擊以連線。",
    "status_no_devices": "⚠️ 找不到已連接的裝置，請以系統管理員身分執行。",
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
        "2. tunneld 正在執行：pymobiledevice3 remote tunneld\n"
        "3. 裝置已透過 USB 連接\n"
        "4. 以系統管理員身分執行 tunneld"
    ),
    # --- Mode ---
    "mode_label": "🎯 模式",
    "mode_single": "單點定位",
    "mode_route": "路線模式",
    # --- Route Walking ---
    "route_walking": "路線行走",
    "speed_label": "移動速度：",
    "noise_label": "速度噪音：",
    "btn_start": "▶ 開始",
    "btn_pause": "⏸ 暫停",
    "btn_stop": "⏹ 停止",
    "chk_loop": "循環路線",
    "btn_clear_route": "🗑 清除路線",
    "route_info": "路點：{points} | 距離：{distance}",
    # --- Manual Coordinates ---
    "manual_coords": "📍 手動座標",
    "label_lat": "緯度：",
    "label_lon": "經度：",
    "btn_teleport": "✈ 瞬間移動",
    "btn_clear_location": "🔄 清除模擬定位",
    # --- Info label ---
    "info_tunneld": "💡 請先以管理員身分啟動 tunneld：\npymobiledevice3 remote tunneld",
    # --- Status bar ---
    "status_ready": "就緒。點擊地圖以設定位置或新增路線點。",
    "status_single_mode": "單點模式：點擊地圖以瞬間移動到該位置。",
    "status_route_mode": "路線模式：點擊地圖以新增路線點。",
    "status_walking": "🚶 路線行走中...",
    "status_resumed": "▶ 已繼續行走...",
    "status_paused": "⏸ 已暫停。按 ▶ 從目前位置繼續。",
    "status_not_walking": "目前未在行走。",
    "status_walk_stopped": "⏹ 行走已停止。",
    "status_walk_complete": "✅ 路線行走完成！",
    "status_route_cleared": "路線已清除。",
    "status_setting_location": "正在設定位置到 {lat}, {lon}...",
    "status_location_set": "✅ 位置已設定到 {lat}, {lon}",
    "status_location_failed": "❌ 設定位置失敗，請檢查連線。",
    "status_teleport_cancelled": "已取消瞬間移動。",
    "status_clearing_location": "正在清除模擬定位...",
    "status_location_cleared": "✅ 模擬定位已清除。",
    "status_location_clear_failed": "❌ 清除定位失敗。",
    "status_device_not_connected": "⚠️ 裝置未連線，請先連線。",
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
    "dialog_invalid_route_title": "路線無效",
    "dialog_invalid_route_msg": "請至少新增 2 個路線點。",
    "dialog_invalid_coords_title": "座標無效",
    "dialog_invalid_coords_msg": "請輸入有效的緯度（-90 到 90）和經度（-180 到 180）。",
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
