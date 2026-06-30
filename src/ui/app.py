import io
import os
import sys
import threading
import time
import tkinter as tk
import webbrowser
from enum import Enum
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from src.core import update_checker, updater
from src.core.constants import (
    DEFAULT_MAP_POSITION,
    DEFAULT_TILE_SERVER,
    TILE_SERVERS,
)
from src.core.device_manager import DeviceManager
from src.core.location_storage import LocationStorage, SavedLocationInfo
from src.core.models import DeviceInfo, MotionSettings, RoutePoint
from src.core.motion_settings_store import MotionSettingsStore
from src.core.route_summary import (
    RouteSummary,
    choose_primary_summary,
    format_distance,
    format_duration,
    summarize_remaining_route,
    summarize_route,
)
from src.core.route_storage import RouteStorage, SavedRouteInfo
from src.core.route_walker import RouteWalker
from src.core.routing import RoutingError, RoutingService
from src.core.screenshot_service import ScreenshotService
from src.core.tunnel_manager import TunneldManager
from src.ui.caching_map_view import CachingTileMapView
from src.ui.coordinate_inputs import (
    parse_coordinate_pair,
    parse_optional_coordinate_pair,
)
from src.ui.i18n import LANGUAGES, get_lang, set_lang, t
from src.ui.tooltip import ToolTip, add_tooltip_button
from src.utils.logger import get_log_file_path, logger
from src.utils.paths import get_app_data_dir, get_cache_dir, resource_path


class AppMode(Enum):
    SINGLE_POINT = "single"
    ROUTE = "route"
    NAVIGATION = "navigation"


ICON_FONT_FAMILY = "Segoe MDL2 Assets"
ICON_CENTER = "\uE81E"
ICON_LOCK = "\uE72E"
ICON_UNLOCK = "\uE785"
ICON_AIRPLANE = "\uE709"
ICON_DELETE = "\uE74D"
ICON_NAVIGATE = "\uE8B8"


class iFakeGPSApp(ctk.CTk):
    """
    Main application window for iFakeGPS.
    """

    def __init__(self):
        super().__init__()
        self._icon_path = None

        # Configure window
        self._update_window_title()
        self.geometry("1500x850")
        self.minsize(960, 640)

        # Set icon
        try:
            icon_path = resource_path("app.ico")
            if os.path.exists(icon_path):
                self._icon_path = icon_path
                self.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Failed to set icon: {e}")

        self._check_windows_notification_registration()

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize tunneld manager
        self.tunneld_manager = TunneldManager()
        self.tunneld_manager.on_device_detected = self._on_tunneld_device_detected
        self.tunneld_manager.on_status_change = self._on_tunneld_status_change

        # Initialize managers
        self.device_manager = DeviceManager()
        self.route_walker = RouteWalker(
            self.device_manager,
            update_callback=self._on_walk_step,
            completion_callback=self._on_walk_session_end,
            batch_completion_callback=self._on_walk_batch_complete,
            disconnect_callback=self._on_walk_device_disconnected,
        )
        # Setup database paths under the per-user cache dir.
        self.cache_dir = str(get_cache_dir())
        self.db_path = os.path.join(self.cache_dir, "map_cache.db")

        # Saved routes and saved locations share one SQLite file (distinct tables).
        # The file is named "routes.db" for historical reasons / backward compat —
        # do not rename it or existing users lose their saved data.
        store_db = os.path.join(self.cache_dir, "routes.db")
        self.route_storage = RouteStorage(store_db)
        self.location_storage = LocationStorage(store_db)
        self.routing_service = RoutingService()
        self.motion_settings_store = MotionSettingsStore(
            get_app_data_dir() / "motion_settings.json"
        )
        self.motion_settings = self.motion_settings_store.load()

        # State
        self.mode = AppMode.SINGLE_POINT
        self.route_points: list[RoutePoint] = []
        self.route_path = None  # Map path object
        self.current_position_marker = None
        self.current_simulated_position: tuple[float, float] | None = None
        self.is_selecting_saved_location = False
        self.save_location_preview_marker = None
        self.follow_current_position = True
        self.discovered_devices: list[DeviceInfo] = []
        self.right_panel_visible = True
        self.motion_noise_pct = self.motion_settings.noise_pct
        self.random_stop_enabled = self.motion_settings.random_stop_enabled
        self.random_stop_interval_m = self.motion_settings.random_stop_interval_m
        self.random_stop_min_s = self.motion_settings.random_stop_min_s
        self.random_stop_max_s = self.motion_settings.random_stop_max_s
        self.displacement_noise_enabled = self.motion_settings.displacement_noise_enabled
        self.displacement_radius_m = self.motion_settings.displacement_radius_m
        self._motion_settings_window: Optional[ctk.CTkToplevel] = None

        # Device-screen preview (burst capture) state
        self._screenshot_service = ScreenshotService(self.device_manager)
        self._preview_window: Optional[ctk.CTkToplevel] = None
        self._preview_stop_event: Optional[threading.Event] = None
        self._preview_image_label = None
        self._preview_status_label = None
        self._preview_ctk_image = None  # keep a ref so Tk doesn't GC the frame
        self._preview_interval = 0.7  # seconds between frames (~1.5 fps)
        self._preview_visible = True  # paused when the window is minimized

        # Build UI
        self._create_ui()
        self._apply_motion_settings(
            noise_pct=self.motion_noise_pct,
            random_stop_enabled=self.random_stop_enabled,
            random_stop_interval_m=self.random_stop_interval_m,
            random_stop_min_s=self.random_stop_min_s,
            random_stop_max_s=self.random_stop_max_s,
            displacement_noise_enabled=self.displacement_noise_enabled,
            displacement_radius_m=self.displacement_radius_m,
        )

        # Bind events
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-start tunneld and discover devices on startup
        self.after(500, self._start_tunneld_and_discover)
        # Non-blocking update check
        self.after(1200, self._check_for_updates_on_startup)

    def _show_dev_mode_guide(self):
        """Show the Developer Mode guide window."""
        guide = ctk.CTkToplevel(self)
        guide.title(t("guide_title"))
        guide.geometry("500x700")

        # Make modal
        guide.transient(self)
        guide.grab_set()

        # Content
        scroll = ctk.CTkScrollableFrame(guide)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        title = ctk.CTkLabel(
            scroll,
            text=t("guide_heading"),
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.pack(pady=(10, 20))

        steps = [
            (t("guide_step1_title"), t("guide_step1_desc")),
            (t("guide_step2_title"), t("guide_step2_desc")),
            (t("guide_step3_title"), t("guide_step3_desc")),
            (t("guide_step4_title"), t("guide_step4_desc")),
            (t("guide_step5_title"), t("guide_step5_desc")),
            (t("guide_step6_title"), t("guide_step6_desc")),
        ]

        for step_title, step_desc in steps:
            step_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            step_frame.pack(fill="x", pady=10)

            title_lbl = ctk.CTkLabel(
                step_frame,
                text=step_title,
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            )
            title_lbl.pack(fill="x")

            d = ctk.CTkLabel(
                step_frame,
                text=step_desc,
                font=ctk.CTkFont(size=14),
                anchor="w",
                justify="left",
            )
            d.pack(fill="x", padx=10)

        # Button to open full manual
        def open_manual():
            try:
                manual_path = resource_path("docs", "USER_MANUAL_ZH.md")

                if not os.path.exists(manual_path):
                    # Fallback check
                    manual_path = os.path.abspath("docs/USER_MANUAL_ZH.md")

                if sys.platform == "win32":
                    os.startfile(manual_path)
                else:
                    import subprocess

                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, manual_path])
            except Exception as e:
                messagebox.showerror("Error", f"Cannot open manual: {e}")

        manual_btn = ctk.CTkButton(
            scroll, text=t("guide_btn_manual"), command=open_manual
        )
        manual_btn.pack(pady=20)

        close_btn = ctk.CTkButton(
            scroll,
            text=t("guide_btn_close"),
            command=guide.destroy,
            fg_color="transparent",
            border_width=1,
        )
        close_btn.pack(pady=(0, 20))

    def _check_dev_mode(self):
        """Check developer mode status."""
        if not hasattr(self, "dev_status_indicator"):
            return
        self.dev_status_indicator.configure(text="🔄 Checking...", text_color="orange")
        self.update()  # Force update

        def run_check():
            status = self.device_manager.check_developer_mode()
            self.after(0, lambda: self._update_dev_mode_ui(status))

        threading.Thread(target=run_check, daemon=True).start()

    def _update_dev_mode_ui(self, enabled: Optional[bool]):
        """Update the Developer Mode UI based on status."""
        if not hasattr(self, "dev_status_indicator"):
            return
        if enabled is True:
            self.dev_status_indicator.configure(
                text=t("dev_status_enabled"), text_color="#22c55e"
            )
            self.dev_enable_btn.grid_remove()
        elif enabled is False:
            self.dev_status_indicator.configure(
                text=t("dev_status_disabled"), text_color="#ef4444"
            )
            self.dev_enable_btn.grid()
        else:
            self.dev_status_indicator.configure(
                text=t("dev_status_unknown"), text_color="gray"
            )
            self.dev_enable_btn.grid_remove()

    def _enable_dev_mode_flow(self):
        """Trigger the flow to enable developer mode."""
        if not messagebox.askyesno(
            t("dialog_enable_dev_title"),
            t("dialog_enable_dev_msg"),
        ):
            return

        def run_enable():
            # 1. Trigger Auto Mount (to reveal the menu)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Step 1/2", "Triggering Developer Menu...\nPlease wait..."
                ),
            )
            self.device_manager.auto_mount_developer_disk_image()

            # 2. Trigger Enable Command (to start the process on phone)
            success = self.device_manager.enable_developer_mode()

            # 3. Show Guide immediately
            self.after(0, self._show_dev_mode_guide)

            if success:
                # Optionally verify check status later
                self.after(10000, self._check_dev_mode)

        threading.Thread(target=run_enable, daemon=True).start()

    def _enable_wireless_flow(self):
        """Trigger the flow to enable wireless connection."""
        if not messagebox.askyesno(
            t("dialog_wireless_title"),
            t("dialog_wireless_msg"),
        ):
            return

        self.status_label.configure(text=t("status_wireless_enabling"))
        self.update()

        def run_enable():
            success = self.device_manager.enable_wireless_connection()
            if success:
                self.after(
                    0,
                    lambda: self.status_label.configure(text=t("status_wireless_enabled")),
                )
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        t("dialog_wireless_title"), t("status_wireless_enabled")
                    ),
                )
                # After enabling wireless, the current USB tunnel might become invalid or
                # user is instructed to unplug. Reset UI to disconnected state.
                self.after(0, self._disconnect_device)
            else:
                self.after(
                    0,
                    lambda: self.status_label.configure(text=t("status_wireless_failed")),
                )
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        t("dialog_wireless_title"), t("status_wireless_failed")
                    ),
                )

        threading.Thread(target=run_enable, daemon=True).start()

    def _create_ui(self):
        """Create the main UI layout."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Create left sidebar
        self._create_sidebar()

        # Create main map area
        self._create_map_area()

        # Create right management panel
        self._create_right_panel()

        # Create bottom status bar
        self._create_status_bar()

        # Set initial visibility after all components are created
        self._on_mode_change()

    def _create_sidebar(self):
        """Create the left sidebar with controls."""
        # Use a scrollable frame for the sidebar to support small screens
        sidebar = ctk.CTkScrollableFrame(self, width=330, corner_radius=0, label_text="")
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)

        # App title
        title_label = ctk.CTkLabel(
            sidebar, text=t("sidebar_title"), font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 5))

        subtitle_label = ctk.CTkLabel(
            sidebar,
            text=t("sidebar_subtitle"),
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 12))

        # Device selection section
        device_frame = ctk.CTkFrame(sidebar)
        device_frame.grid(row=3, column=0, padx=15, pady=(6, 8), sticky="ew")

        device_header = ctk.CTkFrame(device_frame, fg_color="transparent")
        device_header.grid(row=0, column=0, padx=10, pady=(10, 6), sticky="ew")
        device_header.grid_columnconfigure(0, weight=1)

        # Store label ref for update
        self.lbl_device_control = ctk.CTkLabel(
            device_header,
            text=t("device_selection"),
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.lbl_device_control.grid(row=0, column=0, sticky="w")

        self.refresh_btn = ctk.CTkButton(
            device_header,
            text="🔄",
            command=self._refresh_devices,
            width=35,
            height=28,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.refresh_btn.grid(row=0, column=1, padx=(5, 0))

        # Device list
        self.device_listbox_frame = ctk.CTkScrollableFrame(
            device_frame, height=120, fg_color="#1f2937"
        )
        self.device_listbox_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.device_listbox_frame.grid_columnconfigure(0, weight=1)

        # Placeholder for no devices
        self.no_devices_label = ctk.CTkLabel(
            self.device_listbox_frame,
            text=t("no_devices"),
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="center",
        )
        self.no_devices_label.grid(row=0, column=0, padx=10, pady=20)

        # Connection status
        self.conn_status = ctk.CTkLabel(
            device_frame,
            text=t("conn_not_connected"),
            font=ctk.CTkFont(size=12),
            text_color="#ef4444",
        )
        self.conn_status.grid(row=2, column=0, padx=10, pady=(6, 10))

        # Disconnect button
        self.disconnect_btn = ctk.CTkButton(
            device_frame,
            text=t("btn_disconnect"),
            command=self._disconnect_device,
            fg_color="#6b7280",
            hover_color="#4b5563",
            height=28,
        )
        self.disconnect_btn.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Mode selection
        mode_frame = ctk.CTkFrame(sidebar)
        mode_frame.grid(row=4, column=0, padx=15, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(
            mode_frame, text=t("mode_label"), font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.mode_var = ctk.StringVar(value="single")

        self.single_radio = ctk.CTkRadioButton(
            mode_frame,
            text=t("mode_single"),
            variable=self.mode_var,
            value="single",
            command=self._on_mode_change,
        )
        self.single_radio.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        self.nav_radio = ctk.CTkRadioButton(
            mode_frame,
            text=t("mode_navigation"),
            variable=self.mode_var,
            value="navigation",
            command=self._on_mode_change,
        )
        self.nav_radio.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="w")

        # Route controls
        self.route_frame = ctk.CTkFrame(sidebar)
        self.route_frame.grid(row=5, column=0, padx=15, pady=(0, 8), sticky="ew")

        self.lbl_route = ctk.CTkLabel(
            self.route_frame,
            text=t("route_walking"),
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.lbl_route.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w"
        )

        preset_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        preset_frame.grid(
            row=1, column=0, columnspan=2, padx=10, pady=(0, 4), sticky="ew"
        )
        preset_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_speed_preset_walk = ctk.CTkButton(
            preset_frame,
            text=t("btn_speed_preset_walk"),
            height=28,
            command=lambda: self._apply_speed_preset(5.0),
        )
        self.btn_speed_preset_walk.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_speed_preset_bike = ctk.CTkButton(
            preset_frame,
            text=t("btn_speed_preset_bike"),
            height=28,
            command=lambda: self._apply_speed_preset(20.0),
        )
        self.btn_speed_preset_bike.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_speed_preset_drive = ctk.CTkButton(
            preset_frame,
            text=t("btn_speed_preset_drive"),
            height=28,
            command=lambda: self._apply_speed_preset(60.0),
        )
        self.btn_speed_preset_drive.grid(row=0, column=2, padx=(4, 0), sticky="ew")

        # Speed slider — label row with tooltip icon
        speed_label_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        speed_label_frame.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.lbl_speed = ctk.CTkLabel(speed_label_frame, text=t("speed_label"))
        self.lbl_speed.pack(side="left")

        self._speed_tip_icon = add_tooltip_button(
            speed_label_frame, text=t("tip_speed")
        )
        self._speed_tip_icon.pack(side="left", padx=(2, 0))

        speed_val_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        speed_val_frame.grid(row=2, column=1, padx=10, pady=5, sticky="e")

        self.speed_entry_var = ctk.StringVar(value="20.0")
        self.speed_entry = ctk.CTkEntry(
            speed_val_frame,
            textvariable=self.speed_entry_var,
            width=50,
            height=24,
            font=ctk.CTkFont(size=12),
            justify="right",
        )
        self.speed_entry.pack(side="left", padx=(0, 5))
        self.speed_entry.bind("<Return>", self._on_speed_entry_change)
        self.speed_entry.bind("<FocusOut>", self._on_speed_entry_change)

        ctk.CTkLabel(speed_val_frame, text="km/h", font=ctk.CTkFont(size=12)).pack(
            side="left"
        )

        self.speed_slider = ctk.CTkSlider(
            self.route_frame,
            from_=0,
            to=110,
            number_of_steps=110,
            command=self._on_speed_slider_change,
        )
        self.speed_slider.grid(
            row=3, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.speed_slider.set(20)
        self.route_walker.set_speed(20.0)

        motion_action_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        motion_action_frame.grid(
            row=4, column=0, columnspan=2, padx=10, pady=6, sticky="ew"
        )
        motion_action_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_motion_settings = ctk.CTkButton(
            motion_action_frame,
            text=t("btn_motion_settings"),
            command=self._open_motion_settings,
            fg_color="#374151",
            hover_color="#4b5563",
            height=28,
        )
        self.btn_motion_settings.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_device_preview = ctk.CTkButton(
            motion_action_frame,
            text=f"📱  {t('btn_device_preview')}",
            command=self._open_device_preview,
            fg_color="#374151",
            hover_color="#4b5563",
            height=28,
        )
        self.btn_device_preview.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self.route_frame.grid_columnconfigure(0, weight=1)
        self.route_frame.grid_columnconfigure(1, weight=1)

        # Route info
        self.route_info = ctk.CTkLabel(
            self.route_frame,
            text=t("route_info", points=0, distance="0 m", eta=t("route_eta_empty")),
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.route_info.grid(
            row=5, column=0, columnspan=2, padx=10, pady=(6, 2), sticky="w"
        )
        self.route_segments_info = ctk.CTkLabel(
            self.route_frame,
            text=t("route_remaining_empty"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
            anchor="w",
        )
        self.route_segments_info.grid(
            row=6, column=0, columnspan=2, padx=10, pady=(0, 6), sticky="ew"
        )

        # Route planning buttons
        route_plan_btn_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        route_plan_btn_frame.grid(
            row=7, column=0, columnspan=2, padx=10, pady=(4, 5), sticky="ew"
        )
        route_plan_btn_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_calc_route = self.calc_route_btn = ctk.CTkButton(
            route_plan_btn_frame,
            text=t("btn_calc_route"),
            command=self._calculate_navigation_route,
            fg_color="#3b82f6",
            hover_color="#2563eb",
        )
        self.calc_route_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.clear_route_btn = ctk.CTkButton(
            route_plan_btn_frame,
            text=t("btn_clear_route"),
            command=self._clear_route,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.clear_route_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Route walking buttons
        route_btn_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        route_btn_frame.grid(
            row=8, column=0, columnspan=2, padx=10, pady=(4, 5), sticky="ew"
        )

        # Note: We need to assign these to self for update_ui_text
        self.btn_start_walk = self.start_walk_btn = ctk.CTkButton(
            route_btn_frame,
            text=t("btn_start"),
            command=self._start_walking,
            fg_color="#10b981",
            hover_color="#059669",
            width=80,
        )
        self.start_walk_btn.pack(side="left", expand=True, fill="x", padx=1)

        self.pause_walk_btn = ctk.CTkButton(
            route_btn_frame,
            text=t("btn_pause"),
            command=self._pause_walking,
            fg_color="#f59e0b",
            hover_color="#d97706",
            width=80,
        )
        self.pause_walk_btn.pack(side="left", expand=True, fill="x", padx=2)

        self.stop_walk_btn = ctk.CTkButton(
            route_btn_frame,
            text=t("btn_stop"),
            command=self._stop_walking,
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=80,
        )
        self.stop_walk_btn.pack(side="left", expand=True, fill="x", padx=2)

        # Loop checkbox
        self.loop_var = ctk.BooleanVar(value=False)
        self.chk_loop = ctk.CTkCheckBox(
            self.route_frame, text=t("chk_loop"), variable=self.loop_var
        )
        self.chk_loop.grid(
            row=9, column=0, columnspan=2, padx=10, pady=(2, 10), sticky="w"
        )

        # Coordinates section
        self.coord_frame = ctk.CTkFrame(sidebar)
        self.coord_frame.grid(row=6, column=0, padx=15, pady=(0, 8), sticky="ew")

        self.lbl_manual = ctk.CTkLabel(
            self.coord_frame,
            text=t("manual_coords"),
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_manual.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 6), sticky="w"
        )

        self.lbl_lat = ctk.CTkLabel(
            self.coord_frame, text=t("label_lat"), font=ctk.CTkFont(size=11)
        )
        self.lbl_lat.grid(row=1, column=0, padx=10, pady=(2, 3), sticky="w")

        self.lat_entry = ctk.CTkEntry(self.coord_frame, height=24)
        self.lat_entry.grid(row=1, column=1, padx=10, pady=(2, 3), sticky="ew")

        self.lbl_lon = ctk.CTkLabel(
            self.coord_frame, text=t("label_lon"), font=ctk.CTkFont(size=11)
        )
        self.lbl_lon.grid(row=2, column=0, padx=10, pady=(3, 4), sticky="w")

        self.lon_entry = ctk.CTkEntry(self.coord_frame, height=24)
        self.lon_entry.grid(row=2, column=1, padx=10, pady=(3, 4), sticky="ew")

        self.coord_frame.grid_columnconfigure(1, weight=1)

        self.btn_teleport = ctk.CTkButton(
            self.coord_frame,
            text=t("btn_teleport"),
            command=self._set_manual_location,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
        )
        self.btn_teleport.grid(
            row=3, column=0, columnspan=2, padx=10, pady=(10, 8), sticky="ew"
        )

        # Global clear-location button (always visible across modes)
        self.clear_location_btn = ctk.CTkButton(
            self.coord_frame,
            text=t("btn_clear_location"),
            command=self._clear_location,
            fg_color="#6b7280",
            hover_color="#4b5563",
            height=30,
        )
        self.clear_location_btn.grid(
            row=4, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew"
        )

        # Info label at bottom
        info_label = ctk.CTkLabel(
            sidebar,
            text=t("info_tunneld"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        )
        self.info_label = info_label
        info_label.grid(row=9, column=0, padx=15, pady=(20, 5), sticky="sw")
        

        # Language selector
        lang_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        lang_frame.grid(row=10, column=0, padx=15, pady=(0, 14), sticky="sw")

        self.lang_label = ctk.CTkLabel(
            lang_frame, text=t("lang_label"), font=ctk.CTkFont(size=11)
        )
        self.lang_label.pack(side="left")

        # Build display-name list and find current selection
        lang_names = list(LANGUAGES.keys())
        current_name = next(
            (name for name, code in LANGUAGES.items() if code == get_lang()),
            lang_names[0],
        )
        self.lang_combo = ctk.CTkOptionMenu(
            lang_frame,
            values=lang_names,
            command=self._on_lang_change,
            width=100,
            height=24,
            font=ctk.CTkFont(size=11),
        )
        self.lang_combo.set(current_name)
        self.lang_combo.pack(side="left", padx=(5, 0))

        self.log_viewer_btn = ctk.CTkButton(
            lang_frame,
            text=t("btn_show_logs"),
            command=self._show_log_viewer,
            width=36,
            height=24,
            fg_color="#374151",
            hover_color="#4b5563",
            font=ctk.CTkFont(size=11),
        )
        self.log_viewer_btn.pack(side="left", padx=(6, 0))

    def _create_right_panel(self):
        """Create the foldable right panel for saved places and routes."""
        self.right_panel = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.right_panel.grid(row=0, column=2, rowspan=2, sticky="nsew")
        self.right_panel.grid_propagate(False)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)

        self.right_panel_collapsed = ctk.CTkFrame(self, width=44, corner_radius=0)
        self.right_panel_collapsed.grid_propagate(False)
        self.right_panel_collapsed.grid_columnconfigure(0, weight=1)
        self.right_panel_collapsed.grid_rowconfigure(0, weight=1)
        self.btn_expand_right_panel = ctk.CTkButton(
            self.right_panel_collapsed,
            text="‹",
            width=32,
            command=self._toggle_right_panel,
        )
        self.btn_expand_right_panel.grid(row=0, column=0, padx=6, pady=15, sticky="n")
        self.right_panel_collapsed.grid_remove()

        panel_header = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        panel_header.grid(row=0, column=0, padx=12, pady=(15, 5), sticky="ew")
        panel_header.grid_columnconfigure(0, weight=1)

        self.right_panel_title = ctk.CTkLabel(
            panel_header,
            text=t("quick_panel_title"),
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self.right_panel_title.grid(row=0, column=0, sticky="w")

        self.btn_collapse_right_panel = ctk.CTkButton(
            panel_header,
            text="›",
            width=32,
            command=self._toggle_right_panel,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.btn_collapse_right_panel.grid(row=0, column=1, padx=(8, 0), sticky="e")

        self.quick_tabview = ctk.CTkTabview(self.right_panel)
        self.quick_tabview.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self._places_tab_name = t("tab_places")
        self._routes_tab_name = t("tab_routes")
        self.quick_tabview.add(self._places_tab_name)
        self.quick_tabview.add(self._routes_tab_name)

        self._build_places_tab(self.quick_tabview.tab(self._places_tab_name))
        self._build_routes_tab(self.quick_tabview.tab(self._routes_tab_name))
        self._refresh_saved_locations()
        self._refresh_saved_routes()

    def _build_places_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(5, weight=1)

        self.place_name_entry = ctk.CTkEntry(
            tab, placeholder_text=t("placeholder_location_name"), height=30
        )
        self.place_name_entry.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")

        place_coords = ctk.CTkFrame(tab, fg_color="transparent")
        place_coords.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        place_coords.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(
            place_coords, text=t("label_lat"), font=ctk.CTkFont(size=11)
        ).grid(row=0, column=0, padx=(0, 4), sticky="w")
        self.place_lat_entry = ctk.CTkEntry(place_coords, height=28)
        self.place_lat_entry.grid(row=0, column=1, padx=(0, 8), sticky="ew")
        self.place_lat_entry.bind("<Return>", self._on_place_coordinate_entry_change)
        self.place_lat_entry.bind("<FocusOut>", self._on_place_coordinate_entry_change)

        ctk.CTkLabel(
            place_coords, text=t("label_lon"), font=ctk.CTkFont(size=11)
        ).grid(row=0, column=2, padx=(0, 4), sticky="w")
        self.place_lon_entry = ctk.CTkEntry(place_coords, height=28)
        self.place_lon_entry.grid(row=0, column=3, sticky="ew")
        self.place_lon_entry.bind("<Return>", self._on_place_coordinate_entry_change)
        self.place_lon_entry.bind("<FocusOut>", self._on_place_coordinate_entry_change)

        location_actions = ctk.CTkFrame(tab, fg_color="transparent")
        location_actions.grid(row=2, column=0, padx=8, pady=4, sticky="ew")
        location_actions.grid_columnconfigure((0, 1), weight=1)

        self.btn_pick_location_on_map = ctk.CTkButton(
            location_actions,
            text=t("btn_pick_location_on_map"),
            command=self._toggle_saved_location_selection,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.btn_pick_location_on_map.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_use_current_position = ctk.CTkButton(
            location_actions,
            text=t("btn_use_current_position"),
            command=self._fill_place_coordinates_from_current_position,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.btn_use_current_position.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self.btn_save_location = ctk.CTkButton(
            tab,
            text=t("btn_save_location"),
            command=self._save_current_location,
            height=30,
        )
        self.btn_save_location.grid(row=3, column=0, padx=8, pady=4, sticky="ew")

        self.location_hint_label = ctk.CTkLabel(
            tab,
            text=t("location_panel_hint"),
            text_color="gray",
            font=ctk.CTkFont(size=11),
            justify="left",
            wraplength=270,
        )
        self.location_hint_label.grid(row=4, column=0, padx=8, pady=(2, 8), sticky="ew")

        self.locations_list_frame = ctk.CTkScrollableFrame(tab, fg_color="#111827")
        self.locations_list_frame.grid(row=5, column=0, padx=8, pady=4, sticky="nsew")
        self.locations_list_frame.grid_columnconfigure(0, weight=1)

    def _build_routes_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        route_actions = ctk.CTkFrame(tab, fg_color="transparent")
        route_actions.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        route_actions.grid_columnconfigure((0, 1), weight=1)

        self.btn_save_route = ctk.CTkButton(
            route_actions,
            text=t("btn_save_route"),
            command=self._save_route_dialog,
            height=30,
        )
        self.btn_save_route.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_import_gpx = ctk.CTkButton(
            route_actions,
            text=t("btn_import_gpx"),
            command=self._import_gpx_dialog,
            height=30,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.btn_import_gpx.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        route_actions_2 = ctk.CTkFrame(tab, fg_color="transparent")
        route_actions_2.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        route_actions_2.grid_columnconfigure((0, 1), weight=1)

        self.btn_export_gpx = ctk.CTkButton(
            route_actions_2,
            text=t("btn_export_gpx"),
            command=self._export_gpx_dialog,
            height=30,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.btn_export_gpx.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_refresh_routes = ctk.CTkButton(
            route_actions_2,
            text=t("btn_refresh"),
            command=self._refresh_saved_routes,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.btn_refresh_routes.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self.routes_list_frame = ctk.CTkScrollableFrame(tab, fg_color="#111827")
        self.routes_list_frame.grid(row=2, column=0, padx=8, pady=4, sticky="nsew")
        self.routes_list_frame.grid_columnconfigure(0, weight=1)

    def _toggle_right_panel(self):
        self.right_panel_visible = not self.right_panel_visible
        if self.right_panel_visible:
            self.right_panel_collapsed.grid_remove()
            self.right_panel.grid(row=0, column=2, rowspan=2, sticky="nsew")
        else:
            self.right_panel.grid_remove()
            self.right_panel_collapsed.grid(row=0, column=2, rowspan=2, sticky="nsew")

    def _create_map_area(self):
        """Create the main map area."""
        map_frame = ctk.CTkFrame(self, corner_radius=10)
        map_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)

        # map_cache.db path is already established in self.db_path

        # Create map widget using write-through caching subclass.
        # Tiles downloaded from the network are automatically saved to the local SQLite DB
        # so subsequent launches load them instantly without re-downloading.
        self.map_widget = CachingTileMapView(
            map_frame,
            corner_radius=10,
            use_database_only=False,
            db_path=self.db_path,
        )
        self.map_widget.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Set the default tile server (see constants.TILE_SERVERS)
        default_tiles = TILE_SERVERS[DEFAULT_TILE_SERVER]
        self.map_widget.set_tile_server(
            default_tiles["url"],
            max_zoom=default_tiles["max_zoom"],
        )

        # Set default position (see constants.DEFAULT_MAP_POSITION — Taipei fallback)
        self.map_widget.set_position(*DEFAULT_MAP_POSITION)
        self.map_widget.set_zoom(13)

        # Try to get real location from IP
        self._set_default_location()

        # Bind click event
        self.map_widget.add_left_click_map_command(self._on_map_click)

        map_toolbar = ctk.CTkFrame(map_frame, fg_color="#111827", corner_radius=8)
        map_toolbar.grid(row=0, column=0, padx=14, pady=14, sticky="ne")

        self.btn_jump_current_position = ctk.CTkButton(
            map_toolbar,
            text=ICON_CENTER,
            font=ctk.CTkFont(family=ICON_FONT_FAMILY, size=16),
            width=34,
            height=30,
            command=self._jump_to_current_position,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.btn_jump_current_position.grid(row=0, column=0, padx=(6, 3), pady=6)
        ToolTip(self.btn_jump_current_position, text=t("tip_jump_current_position"))

        self.btn_follow_current_position = ctk.CTkButton(
            map_toolbar,
            text=ICON_LOCK,
            font=ctk.CTkFont(family=ICON_FONT_FAMILY, size=16),
            width=34,
            height=30,
            command=self._toggle_follow_current_position,
        )
        self.btn_follow_current_position.grid(row=0, column=1, padx=(3, 6), pady=6)
        ToolTip(self.btn_follow_current_position, text=t("tip_follow_current_position"))
        self._update_follow_button_state()

    def _set_default_location(self):
        """Try to set map position based on Windows Location API, with IP fallback."""

        def fetch_location():
            # Method 1: Try Windows API (winsdk)
            found_location = False
            try:
                import asyncio

                from winsdk.windows.devices.geolocation import Geolocator

                async def get_pos():
                    locator = Geolocator()
                    # Request access? Windows handles prompt.
                    # Timeout after 10 seconds?
                    # Note: get_geoposition_async has (maximum_age, timeout) overloads in C#,
                    # but Python projection binds default or all.
                    # We'll just await standard call.
                    pos = await locator.get_geoposition_async()
                    return (
                        pos.coordinate.point.position.latitude,
                        pos.coordinate.point.position.longitude,
                    )

                # Run async call in this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # logger.info("Requesting Windows Location...")
                lat, lon = loop.run_until_complete(get_pos())
                loop.close()

                if lat and lon:
                    logger.info(f"Detected Windows Location: {lat}, {lon}")
                    self.after(0, lambda: self.map_widget.set_position(lat, lon))
                    self.after(0, lambda: self.map_widget.set_zoom(15))
                    found_location = True
            except Exception as e:
                logger.warning(f"Windows Location API failed: {e}")

            if found_location:
                return

            logger.warning("Windows Location API failed. Using default location.")

        threading.Thread(target=fetch_location, daemon=True).start()

    def _jump_to_current_position(self):
        """Center the map on the current simulated GPS position."""
        if self.current_simulated_position is None:
            self.status_label.configure(text=t("status_no_current_position"))
            return
        lat, lon = self.current_simulated_position
        self.map_widget.set_position(lat, lon)
        self.map_widget.set_zoom(15)
        self.status_label.configure(text=t("status_jumped_current_position"))

    def _toggle_follow_current_position(self):
        """Toggle whether navigation updates keep the map centered."""
        self.follow_current_position = not self.follow_current_position
        self._update_follow_button_state()
        status_key = (
            "status_follow_enabled"
            if self.follow_current_position
            else "status_follow_disabled"
        )
        self.status_label.configure(text=t(status_key))

    def _update_follow_button_state(self):
        if not hasattr(self, "btn_follow_current_position"):
            return
        if self.follow_current_position:
            self.btn_follow_current_position.configure(
                text=ICON_LOCK,
                fg_color="#10b981",
                hover_color="#059669",
            )
        else:
            self.btn_follow_current_position.configure(
                text=ICON_UNLOCK,
                fg_color="#374151",
                hover_color="#4b5563",
            )

    def _create_status_bar(self):
        """Create the bottom status bar."""
        status_frame = ctk.CTkFrame(self, height=40, corner_radius=0)
        status_frame.grid(row=1, column=1, sticky="ew", padx=15, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text=t("status_ready"),
            font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(side="left", padx=15, pady=10)

        self.coords_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=12, family="Consolas"),
            text_color="gray",
        )
        self.coords_label.pack(side="right", padx=15, pady=10)

    # ------------------------------------------------------------------
    # Language switching
    # ------------------------------------------------------------------

    def _on_lang_change(self, display_name: str):
        """Called when the user picks a language from the dropdown."""
        code = LANGUAGES.get(display_name, "en")
        if code == get_lang():
            return
        set_lang(code)
        self._update_ui_text()

    def _update_window_title(self):
        """Update window title with app name and current version."""
        version = update_checker.get_current_version()
        self.title(f"{t('app_title')} v{version}")

    def _update_ui_text(self):
        """Refresh all visible widget text to reflect the current language."""
        # Window title
        self._update_window_title()

        # Sidebar labels
        if hasattr(self, "lbl_device_control"):
            self.lbl_device_control.configure(text=t("device_selection"))
        if hasattr(self, "conn_status"):
            # Only update if currently showing the default "Not Connected" state
            if not self.device_manager.connected:
                self.conn_status.configure(text=t("conn_not_connected"))
        if hasattr(self, "disconnect_btn"):
            self.disconnect_btn.configure(text=t("btn_disconnect"))
        if hasattr(self, "btn_device_preview"):
            self.btn_device_preview.configure(text=f"📱  {t('btn_device_preview')}")
        # Mode
        if hasattr(self, "single_radio"):
            self.single_radio.configure(text=t("mode_single"))
        if hasattr(self, "nav_radio"):
            self.nav_radio.configure(text=t("mode_navigation"))
        if hasattr(self, "lbl_route"):
            self.lbl_route.configure(text=t("route_walking"))
        if hasattr(self, "lbl_speed"):
            self.lbl_speed.configure(text=t("speed_label"))
        if hasattr(self, "btn_speed_preset_walk"):
            self.btn_speed_preset_walk.configure(text=t("btn_speed_preset_walk"))
        if hasattr(self, "btn_speed_preset_bike"):
            self.btn_speed_preset_bike.configure(text=t("btn_speed_preset_bike"))
        if hasattr(self, "btn_speed_preset_drive"):
            self.btn_speed_preset_drive.configure(text=t("btn_speed_preset_drive"))
        if hasattr(self, "btn_motion_settings"):
            self.btn_motion_settings.configure(text=t("btn_motion_settings"))

        # Tooltip icons — update their ToolTip text
        if hasattr(self, "_speed_tip_icon"):
            from src.ui.tooltip import ToolTip

            ToolTip(self._speed_tip_icon, text=t("tip_speed"))

        # Route buttons
        if hasattr(self, "start_walk_btn"):
            self.start_walk_btn.configure(text=t("btn_start"))
        if hasattr(self, "pause_walk_btn"):
            self.pause_walk_btn.configure(text=t("btn_pause"))
        if hasattr(self, "stop_walk_btn"):
            self.stop_walk_btn.configure(text=t("btn_stop"))
        if hasattr(self, "chk_loop"):
            self.chk_loop.configure(text=t("chk_loop"))
        if hasattr(self, "clear_route_btn"):
            self.clear_route_btn.configure(text=t("btn_clear_route"))
        if hasattr(self, "btn_calc_route"):
            self.btn_calc_route.configure(text=t("btn_calc_route"))
        if hasattr(self, "right_panel_title"):
            self.right_panel_title.configure(text=t("quick_panel_title"))
        if hasattr(self, "place_name_entry"):
            self.place_name_entry.configure(placeholder_text=t("placeholder_location_name"))
        if hasattr(self, "btn_save_location"):
            self.btn_save_location.configure(text=t("btn_save_location"))
        if hasattr(self, "btn_pick_location_on_map"):
            self.btn_pick_location_on_map.configure(
                text=(
                    t("btn_cancel_save_location")
                    if self.is_selecting_saved_location
                    else t("btn_pick_location_on_map")
                )
            )
        if hasattr(self, "btn_use_current_position"):
            self.btn_use_current_position.configure(text=t("btn_use_current_position"))
        if hasattr(self, "location_hint_label"):
            self.location_hint_label.configure(text=t("location_panel_hint"))
        if hasattr(self, "btn_jump_current_position"):
            ToolTip(self.btn_jump_current_position, text=t("tip_jump_current_position"))
        if hasattr(self, "btn_follow_current_position"):
            ToolTip(
                self.btn_follow_current_position,
                text=t("tip_follow_current_position"),
            )
        if hasattr(self, "btn_save_route"):
            self.btn_save_route.configure(text=t("btn_save_route"))
        if hasattr(self, "btn_load_route"):
            self.btn_load_route.configure(text=t("btn_load_route"))
        if hasattr(self, "btn_import_gpx"):
            self.btn_import_gpx.configure(text=t("btn_import_gpx"))
        if hasattr(self, "btn_export_gpx"):
            self.btn_export_gpx.configure(text=t("btn_export_gpx"))
        if hasattr(self, "btn_refresh_routes"):
            self.btn_refresh_routes.configure(text=t("btn_refresh"))
        if hasattr(self, "locations_list_frame"):
            self._refresh_saved_locations()
        if hasattr(self, "routes_list_frame"):
            self._refresh_saved_routes()

        # Manual coords
        if hasattr(self, "lbl_manual"):
            self.lbl_manual.configure(text=t("manual_coords"))
        if hasattr(self, "lbl_lat"):
            self.lbl_lat.configure(text=t("label_lat"))
        if hasattr(self, "lbl_lon"):
            self.lbl_lon.configure(text=t("label_lon"))
        if hasattr(self, "btn_teleport"):
            self.btn_teleport.configure(text=t("btn_teleport"))
        if hasattr(self, "clear_location_btn"):
            self.clear_location_btn.configure(text=t("btn_clear_location"))
        if hasattr(self, "log_viewer_btn"):
            self.log_viewer_btn.configure(text=t("btn_show_logs"))

        # Info label
        if hasattr(self, "info_label"):
            self.info_label.configure(text=t("info_tunneld"))

        # Language label
        if hasattr(self, "lang_label"):
            self.lang_label.configure(text=t("lang_label"))

        # Status bar
        if hasattr(self, "status_label"):
            self.status_label.configure(text=t("status_ready"))
        if hasattr(self, "route_info"):
            self._update_route_info()

    def _start_tunneld_and_discover(self):
        """Check for tunneld service and discover devices."""
        self.status_label.configure(text=t("status_checking_tunneld"))
        self.update()

        def start_and_discover():
            # Check if tunneld is already running
            tunneld_running = self.tunneld_manager.is_tunneld_running()

            if tunneld_running:
                self.tunneld_manager.running = True
                self.after(
                    0,
                    lambda: self.status_label.configure(text=t("status_tunneld_found")),
                )
            else:
                # Check if we're running as admin
                if self.tunneld_manager.is_admin():
                    # We have admin privileges - start tunneld automatically
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text=t("status_starting_tunneld")
                        ),
                    )
                    success = self.tunneld_manager.start()
                    if success:
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text=t("status_tunneld_started")
                            ),
                        )
                        # Wait for tunneld to initialize
                        time.sleep(3)
                    else:
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text=t("status_tunneld_failed")
                            ),
                        )
                else:
                    # Not admin - prompt user
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text=t("status_tunneld_need_admin")
                        ),
                    )
                    # Wait and check if user started it manually
                    time.sleep(2)
                    if self.tunneld_manager.is_tunneld_running():
                        self.tunneld_manager.running = True
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text=t("status_tunneld_detected")
                            ),
                        )

            # Discover devices
            devices = self.device_manager.discover_devices()
            if not devices:
                devices = self.device_manager.discover_devices_via_browse()
            self.after(0, lambda: self._update_device_list(devices))

        threading.Thread(target=start_and_discover, daemon=True).start()

    def _on_tunneld_device_detected(self):
        """Called when tunneld detects a new device connection."""
        # Refresh device list
        self.after(0, self._refresh_devices)
        # Check dev mode
        # Developer Mode controls are intentionally not shown in the main UI.

    def _on_tunneld_status_change(self, running: bool):
        """Called when tunneld status changes."""
        if not running:
            self.after(
                0,
                lambda: self.status_label.configure(text=t("status_tunneld_stopped")),
            )

    def _refresh_devices(self):
        """Refresh the list of available devices."""
        self.status_label.configure(text=t("status_scanning"))
        self.update()

        def discover():
            devices = self.device_manager.discover_devices()
            if not devices:
                # Try alternative discovery
                devices = self.device_manager.discover_devices_via_browse()
            self.after(0, lambda: self._update_device_list(devices))

        threading.Thread(target=discover, daemon=True).start()

    def _update_device_list(self, devices: list[DeviceInfo]):
        """Update the device list in the UI."""
        self.discovered_devices = devices

        # Clear existing widgets
        for widget in self.device_listbox_frame.winfo_children():
            widget.destroy()

        if not devices:
            self.no_devices_label = ctk.CTkLabel(
                self.device_listbox_frame,
                text=t("no_devices_admin"),
                font=ctk.CTkFont(size=12),
                text_color="orange",
                justify="center",
            )
            self.no_devices_label.grid(row=0, column=0, padx=10, pady=20)
            self.status_label.configure(text=t("status_no_devices"))
        else:
            for i, device in enumerate(devices):
                self._create_device_row(self.device_listbox_frame, i, device)

            self.status_label.configure(
                text=t("status_found_devices", count=len(devices))
            )

    def _create_device_row(self, parent, row: int, device: DeviceInfo):
        connected = self._is_device_connected(device)
        row_frame = ctk.CTkFrame(
            parent,
            fg_color="#10b981" if connected else "#1e3a5f",
            cursor="hand2",
        )
        row_frame.grid(row=row, column=0, padx=5, pady=3, sticky="ew")
        row_frame.grid_columnconfigure(0, weight=1)

        interface = (device.interface or "").upper()
        interface_text = interface if interface else "--"

        name_label = ctk.CTkLabel(
            row_frame,
            text=self._shorten_device_name(device.name),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, padx=(10, 6), pady=(7, 0), sticky="ew")

        badge = ctk.CTkLabel(
            row_frame,
            text=interface_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#dbeafe",
            fg_color="#0f172a",
            corner_radius=6,
            width=42,
        )
        badge.grid(row=0, column=1, padx=(0, 8), pady=(7, 0), sticky="e")

        meta_label = ctk.CTkLabel(
            row_frame,
            text=f"{device.product_type} · iOS {device.ios_version}",
            font=ctk.CTkFont(size=11),
            text_color="#d1d5db",
            anchor="w",
        )
        meta_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 7), sticky="ew")

        for widget in (row_frame, name_label, badge, meta_label):
            widget.bind("<Button-1>", lambda _event, d=device: self._connect_to_device(d))

    @staticmethod
    def _shorten_device_name(name: str, max_chars: int = 24) -> str:
        if len(name) <= max_chars:
            return name
        return name[: max_chars - 1] + "…"

    def _is_device_connected(self, device: DeviceInfo) -> bool:
        """Check if a device is currently connected."""
        if self.device_manager.current_device:
            return self.device_manager.current_device.udid == device.udid
        return False

    def _connect_to_device(self, device: DeviceInfo):
        """Connect to a selected device."""
        self.status_label.configure(text=t("status_connecting", name=device.name))
        self.update()

        def connect():
            success = self.device_manager.connect_to_device(device)
            self.after(0, lambda: self._update_connection_status(success, device))

        threading.Thread(target=connect, daemon=True).start()

    def _disconnect_device(self):
        """Disconnect from the current device."""
        self.device_manager.disconnect()
        self.conn_status.configure(text=t("conn_not_connected"), text_color="#ef4444")
        self.status_label.configure(text=t("status_disconnected"))
        self._refresh_devices()

    def _update_connection_status(self, success: bool, device: DeviceInfo = None):
        """Update UI after connection attempt."""
        if success:
            device_name = (
                device.name
                if device
                else (
                    self.device_manager.current_device.name
                    if self.device_manager.current_device
                    else "Device"
                )
            )
            self.conn_status.configure(text=f"🟢 {device_name}", text_color="#10b981")
            self.status_label.configure(text=t("status_connected", name=device_name))
            # Refresh device list to show connected state
            self._update_device_list(self.discovered_devices)
        else:
            self.conn_status.configure(text=t("conn_failed"), text_color="#ef4444")
            self.status_label.configure(text=t("status_conn_failed"))
            messagebox.showerror(
                t("dialog_conn_failed_title"),
                t("dialog_conn_failed_msg"),
            )

    def _on_mode_change(self):
        """Handle mode change."""
        mode_str = self.mode_var.get()
        if mode_str == "single":
            self.mode = AppMode.SINGLE_POINT
        else:
            self.mode = AppMode.NAVIGATION

        if self.mode == AppMode.SINGLE_POINT:
            if hasattr(self, "route_frame"):
                self.route_frame.grid_remove()
            if hasattr(self, "coord_frame"):
                self.coord_frame.grid()
            self.status_label.configure(text=t("status_single_mode"))
        else:
            if hasattr(self, "coord_frame"):
                self.coord_frame.grid_remove()
            if hasattr(self, "route_frame"):
                self.route_frame.grid()
            self.status_label.configure(text=t("status_nav_mode"))

    def _on_map_click(self, coords):
        """Handle map click."""
        lat, lon = coords

        # Update coordinate display
        self.coords_label.configure(text=f"Clicked: {lat:.6f}, {lon:.6f}")
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, f"{lat:.6f}")
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, f"{lon:.6f}")

        if self.is_selecting_saved_location:
            self._use_selected_location_for_place(lat, lon)
            return

        if self.mode == AppMode.SINGLE_POINT:
            # Single point mode - show confirmation before teleporting
            self._pending_teleport = (lat, lon)
            self._show_teleport_confirmation(lat, lon)
        else:
            # Route and Navigation mode - add waypoint
            self._add_route_point(lat, lon)

    def _show_teleport_confirmation(self, lat: float, lon: float):
        """Show a confirmation dialog before teleporting."""
        # Show a preview marker
        if hasattr(self, "_preview_marker") and self._preview_marker:
            self._preview_marker.delete()

        self._preview_marker = self.map_widget.set_marker(
            lat,
            lon,
            text=t("marker_teleport_here"),
            marker_color_circle="#f59e0b",
            marker_color_outside="#d97706",
        )

        # Ask for confirmation
        result = messagebox.askyesno(
            t("dialog_confirm_teleport_title"),
            t("dialog_confirm_teleport_msg", lat=f"{lat:.6f}", lon=f"{lon:.6f}"),
            icon="question",
        )

        # Remove preview marker
        if hasattr(self, "_preview_marker") and self._preview_marker:
            self._preview_marker.delete()
            self._preview_marker = None

        if result:
            # User confirmed - teleport
            self._set_location_at(lat, lon)
        else:
            # User cancelled
            self.status_label.configure(text=t("status_teleport_cancelled"))

    def _set_location_at(self, lat: float, lon: float):
        """Set the GPS location at the given coordinates."""
        if not self.device_manager.connected:
            self.status_label.configure(text=t("status_device_not_connected"))
            messagebox.showwarning(
                t("dialog_not_connected_title"), t("dialog_not_connected_msg")
            )
            return

        # Clear existing marker
        if self.current_position_marker:
            self.current_position_marker.delete()

        # Add new marker
        self.current_position_marker = self.map_widget.set_marker(
            lat,
            lon,
            text=t("marker_current_location"),
            marker_color_circle="#ef4444",
            marker_color_outside="#b91c1c",
        )

        # Set location on device
        def set_loc():
            success = self.device_manager.set_location(lat, lon)
            self.after(0, lambda: self._on_location_set(success, lat, lon))

        threading.Thread(target=set_loc, daemon=True).start()
        self.status_label.configure(
            text=t("status_setting_location", lat=f"{lat:.6f}", lon=f"{lon:.6f}")
        )

    def _on_location_set(self, success: bool, lat: float, lon: float):
        """Called after location is set."""
        if success:
            self.current_simulated_position = (lat, lon)
            self._update_route_info()
            self.status_label.configure(
                text=t("status_location_set", lat=f"{lat:.6f}", lon=f"{lon:.6f}")
            )
        else:
            self.status_label.configure(text=t("status_location_failed"))

    def _add_route_point(self, lat: float, lon: float):
        """Add a point to the route."""
        point_index = len(self.route_points)

        # Create marker
        marker = self.map_widget.set_marker(
            lat,
            lon,
            text=f"Point {point_index + 1}",
            marker_color_circle="#3b82f6",
            marker_color_outside="#1e40af",
        )

        point = RoutePoint(latitude=lat, longitude=lon, marker=marker)
        self.route_points.append(point)

        # Bind right-click to remove this point
        def on_marker_right_click(event, pt=point):
            self._remove_route_point(pt)

        # Try to bind right-click to the marker's canvas items
        try:
            if hasattr(marker, "canvas_marker_icon"):
                marker.canvas_marker_icon.bind("<Button-3>", on_marker_right_click)
            if hasattr(marker, "canvas_text"):
                marker.canvas_text.bind("<Button-3>", on_marker_right_click)
        except Exception:
            pass  # Marker binding not supported in this version

        # Update route path on map
        self._update_route_path()

        # Update route info
        self._update_route_info()

        self.status_label.configure(
            text=t(
                "status_point_added",
                index=len(self.route_points),
                lat=f"{lat:.6f}",
                lon=f"{lon:.6f}",
            )
        )

    def _remove_route_point(self, point: RoutePoint):
        """Remove a point from the route."""
        if point in self.route_points:
            # Remove marker from map
            if point.marker:
                point.marker.delete()

            # Remove from list
            self.route_points.remove(point)

            # Renumber remaining markers
            for i, pt in enumerate(self.route_points):
                if pt.marker:
                    pt.marker.set_text(f"Point {i + 1}")

            # Update path and info
            self._update_route_path()
            self._update_route_info()

            self.status_label.configure(
                text=t("status_point_removed", count=len(self.route_points))
            )

    def _update_route_path(self):
        """Update the route path visualization on the map."""
        # Remove existing path
        if self.route_path:
            self.route_path.delete()
            self.route_path = None

        if len(self.route_points) >= 2:
            path_coords = [(p.latitude, p.longitude) for p in self.route_points]
            self.route_path = self.map_widget.set_path(
                path_coords, color="#3b82f6", width=3
            )

    def _update_route_info(self):
        """Update route information display."""
        speed_kmh = self._get_current_speed_kmh()
        origin = self.current_simulated_position if len(self.route_points) == 1 else None
        total_summary = summarize_route(self.route_points, speed_kmh, origin=origin)
        remaining_summary = self._get_remaining_route_summary(speed_kmh)
        primary_summary = choose_primary_summary(total_summary, remaining_summary)

        self.route_info.configure(
            text=t(
                "route_info",
                points=total_summary.point_count,
                distance=format_distance(primary_summary.total_distance_m),
                eta=(
                    format_duration(primary_summary.total_duration_s)
                    if primary_summary.segments or remaining_summary is not None
                    else t("route_eta_empty")
                ),
            )
        )

        if remaining_summary is None:
            self.route_segments_info.configure(text=t("route_remaining_empty"))
            return

        if not remaining_summary.segments:
            self.route_segments_info.configure(text=t("route_remaining_done"))
            return

        self.route_segments_info.configure(text=t("route_total_info", distance=format_distance(total_summary.total_distance_m), eta=format_duration(total_summary.total_duration_s)))

    def _clear_route(self):
        """Clear the current route."""
        # Stop walking if active
        self.route_walker.stop()

        # Remove markers
        for point in self.route_points:
            if point.marker:
                point.marker.delete()

        # Remove path
        if self.route_path:
            self.route_path.delete()
            self.route_path = None

        self.route_points = []
        self._update_route_info()
        self.status_label.configure(text=t("status_route_cleared"))

    def _on_speed_slider_change(self, value):
        """Handle speed slider change."""
        speed_kmh = float(value)
        self.speed_entry_var.set(f"{speed_kmh:.1f}")
        self.route_walker.set_speed(speed_kmh)
        self._update_route_info()

    def _calculate_navigation_route(self):
        """Fetch route from OSRM/ORS using the added markers."""
        if len(self.route_points) < 2:
            messagebox.showinfo(
                t("dialog_invalid_route_title"),
                t("dialog_invalid_route_msg"),
            )
            return

        self.status_label.configure(text=t("status_calculating_route"))

        # We need the user-placed waypoints as tuples
        waypoints = [(p.latitude, p.longitude) for p in self.route_points]

        def fetch_task():
            try:
                # OSRM/ORS returns a dense list of RoutePoints following roads
                dense_points = self.routing_service.get_route(
                    waypoints, profile="driving"
                )
                self.after(0, lambda: self._on_navigation_route_success(dense_points))
            except RoutingError as e:
                self.after(0, lambda msg=str(e): self._on_navigation_route_fail(msg))
            except Exception as e:
                self.after(
                    0,
                    lambda msg=f"Unexpected error: {e}": self._on_navigation_route_fail(
                        msg
                    ),
                )

        threading.Thread(target=fetch_task, daemon=True).start()

    def _on_navigation_route_success(self, dense_points: list[RoutePoint]):
        """Replace the current route points with the calculated dense road path."""
        # 1. Clear old markers (or we can keep them visually, but let's replace them for walk logic)
        for p in self.route_points:
            if p.marker:
                p.marker.delete()

        self.route_points = []

        # 2. Add start/end marker for visual cue, but the path is dense
        if dense_points:
            dense_points[0].marker = self.map_widget.set_marker(
                dense_points[0].latitude,
                dense_points[0].longitude,
                text=t("marker_start"),
                marker_color_circle="#10b981",
            )
            dense_points[-1].marker = self.map_widget.set_marker(
                dense_points[-1].latitude,
                dense_points[-1].longitude,
                text=t("marker_end"),
                marker_color_circle="#ef4444",
            )

        self.route_points = dense_points
        self._update_route_path()
        self._update_route_info()
        self.status_label.configure(text=t("status_calc_success"))

    def _on_navigation_route_fail(self, msg: str):
        self.status_label.configure(text=t("status_calc_failed", error=msg))
        messagebox.showerror(t("dialog_routing_error_title"), msg)

    # -------------------------------------------------------------
    # Right Panel: Saved Locations and Routes
    # -------------------------------------------------------------

    def _clear_widget_children(self, widget):
        for child in widget.winfo_children():
            child.destroy()

    def _get_entered_coordinates(self) -> tuple[float, float] | None:
        try:
            return parse_coordinate_pair(self.lat_entry.get(), self.lon_entry.get())
        except ValueError:
            messagebox.showerror(
                t("dialog_invalid_coords_title"),
                t("dialog_invalid_coords_msg"),
            )
            return None

    def _get_place_coordinates(self) -> tuple[float, float] | None:
        try:
            return parse_coordinate_pair(
                self.place_lat_entry.get(), self.place_lon_entry.get()
            )
        except ValueError:
            messagebox.showerror(
                t("dialog_invalid_coords_title"),
                t("dialog_invalid_coords_msg"),
            )
            return None

    def _set_place_coordinate_entries(self, lat: float, lon: float):
        self.place_lat_entry.delete(0, "end")
        self.place_lat_entry.insert(0, f"{lat:.6f}")
        self.place_lon_entry.delete(0, "end")
        self.place_lon_entry.insert(0, f"{lon:.6f}")

    def _show_save_location_preview_marker(self, lat: float, lon: float):
        if self.save_location_preview_marker:
            self.save_location_preview_marker.delete()
        self.save_location_preview_marker = self.map_widget.set_marker(
            lat,
            lon,
            text=t("marker_save_place"),
            marker_color_circle="#10b981",
            marker_color_outside="#047857",
        )

    def _preview_place_coordinates(self, lat: float, lon: float):
        self.map_widget.set_position(lat, lon)
        self.map_widget.set_zoom(15)
        self._show_save_location_preview_marker(lat, lon)
        self.status_label.configure(
            text=t(
                "status_location_coordinates_filled",
                lat=f"{lat:.6f}",
                lon=f"{lon:.6f}",
            )
        )

    def _on_place_coordinate_entry_change(self, event=None):
        try:
            coords = parse_optional_coordinate_pair(
                self.place_lat_entry.get(), self.place_lon_entry.get()
            )
        except ValueError:
            messagebox.showerror(
                t("dialog_invalid_coords_title"),
                t("dialog_invalid_coords_msg"),
            )
            return

        if coords is None:
            return

        lat, lon = coords
        self._preview_place_coordinates(lat, lon)

    def _use_selected_location_for_place(self, lat: float, lon: float):
        self._set_place_coordinate_entries(lat, lon)
        self._preview_place_coordinates(lat, lon)
        self._set_saved_location_selection_mode(False, clear_preview=False)

    def _fill_place_coordinates_from_current_position(self):
        if self.current_simulated_position is None:
            self.status_label.configure(text=t("status_no_current_position"))
            messagebox.showinfo(
                t("dialog_current_position_required_title"),
                t("dialog_current_position_required_msg"),
            )
            return
        lat, lon = self.current_simulated_position
        self._set_place_coordinate_entries(lat, lon)
        self._preview_place_coordinates(lat, lon)

    def _get_place_name(self, lat: float, lon: float) -> str:
        name = self.place_name_entry.get().strip()
        if name:
            return name
        return t("default_location_name", lat=f"{lat:.4f}", lon=f"{lon:.4f}")

    def _save_location(self, lat: float, lon: float):
        name = self._get_place_name(lat, lon)
        self.location_storage.save(name, lat, lon)
        self.place_name_entry.delete(0, "end")
        self.place_lat_entry.delete(0, "end")
        self.place_lon_entry.delete(0, "end")
        if self.save_location_preview_marker:
            self.save_location_preview_marker.delete()
            self.save_location_preview_marker = None
        self._refresh_saved_locations()
        self.status_label.configure(text=t("status_location_saved", name=name))

    def _toggle_saved_location_selection(self):
        if self.is_selecting_saved_location:
            self.status_label.configure(text=t("status_location_save_cancelled"))
            self._set_saved_location_selection_mode(False)
        else:
            self._set_saved_location_selection_mode(True)

    def _set_saved_location_selection_mode(
        self, enabled: bool, clear_preview: bool = True
    ):
        self.is_selecting_saved_location = enabled
        if enabled:
            self.status_label.configure(text=t("status_select_saved_location"))
            if hasattr(self, "btn_pick_location_on_map"):
                self.btn_pick_location_on_map.configure(
                    text=t("btn_cancel_save_location")
                )
            return

        if clear_preview and self.save_location_preview_marker:
            self.save_location_preview_marker.delete()
            self.save_location_preview_marker = None
        if hasattr(self, "btn_pick_location_on_map"):
            self.btn_pick_location_on_map.configure(text=t("btn_pick_location_on_map"))

    def _save_current_location(self):
        coords = self._get_place_coordinates()
        if coords is None:
            return
        lat, lon = coords
        self._save_location(lat, lon)

    def _refresh_saved_locations(self):
        if not hasattr(self, "locations_list_frame"):
            return
        self._clear_widget_children(self.locations_list_frame)
        locations = self.location_storage.list_all()
        if not locations:
            ctk.CTkLabel(
                self.locations_list_frame,
                text=t("empty_locations"),
                text_color="gray",
                justify="center",
            ).grid(row=0, column=0, padx=10, pady=20, sticky="ew")
            return

        for row, location in enumerate(locations):
            self._create_location_row(self.locations_list_frame, row, location)

    def _create_location_row(self, parent, row: int, location: SavedLocationInfo):
        item = ctk.CTkFrame(parent, fg_color="#1f2937")
        item.grid(row=row, column=0, padx=4, pady=4, sticky="ew")
        item.grid_columnconfigure(0, weight=1)

        name_label = ctk.CTkLabel(
            item,
            text=location.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, columnspan=3, padx=8, pady=(8, 0), sticky="ew")

        coord_label = ctk.CTkLabel(
            item,
            text=f"{location.latitude:.6f}, {location.longitude:.6f}",
            font=ctk.CTkFont(size=11, family="Consolas"),
            text_color="gray",
            anchor="w",
        )
        coord_label.grid(row=1, column=0, columnspan=3, padx=8, pady=(0, 6), sticky="ew")

        actions = ctk.CTkFrame(item, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=3, padx=8, pady=(0, 8), sticky="ew")
        actions.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="place_actions")

        jump_btn = ctk.CTkButton(
            actions,
            text=ICON_CENTER,
            font=ctk.CTkFont(family=ICON_FONT_FAMILY, size=15),
            height=28,
            width=44,
            command=lambda loc=location: self._jump_to_saved_location(loc),
            fg_color="#374151",
            hover_color="#4b5563",
        )
        jump_btn.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        ToolTip(jump_btn, text=t("tip_place_jump"))

        teleport_btn = ctk.CTkButton(
            actions,
            text=ICON_AIRPLANE,
            font=ctk.CTkFont(family=ICON_FONT_FAMILY, size=15),
            height=28,
            width=44,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            command=lambda loc=location: self._teleport_saved_location(loc),
        )
        teleport_btn.grid(row=0, column=1, padx=3, sticky="ew")
        ToolTip(teleport_btn, text=t("tip_place_teleport"))

        navigate_btn = ctk.CTkButton(
            actions,
            text=ICON_NAVIGATE,
            font=ctk.CTkFont(family=ICON_FONT_FAMILY, size=15),
            height=28,
            width=44,
            fg_color="#0ea5e9",
            hover_color="#0284c7",
            command=lambda loc=location: self._navigate_to_saved_location(loc),
        )
        navigate_btn.grid(row=0, column=2, padx=3, sticky="ew")
        ToolTip(navigate_btn, text=t("tip_place_navigate"))

        delete_btn = ctk.CTkButton(
            actions,
            text=ICON_DELETE,
            font=ctk.CTkFont(family=ICON_FONT_FAMILY, size=15),
            height=28,
            width=44,
            fg_color="#6b7280",
            hover_color="#4b5563",
            command=lambda loc=location: self._delete_saved_location(loc),
        )
        delete_btn.grid(row=0, column=3, padx=(3, 0), sticky="ew")
        ToolTip(delete_btn, text=t("tip_place_delete"))

    def _jump_to_saved_location(self, location: SavedLocationInfo):
        self.map_widget.set_position(location.latitude, location.longitude)
        self.map_widget.set_zoom(15)
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, f"{location.latitude:.6f}")
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, f"{location.longitude:.6f}")
        self.status_label.configure(text=t("status_location_selected", name=location.name))

    def _teleport_saved_location(self, location: SavedLocationInfo):
        self._jump_to_saved_location(location)
        self._set_location_at(location.latitude, location.longitude)

    def _navigate_to_saved_location(self, location: SavedLocationInfo):
        if self.current_simulated_position is None:
            self.status_label.configure(text=t("status_no_current_position"))
            messagebox.showinfo(
                t("dialog_current_position_required_title"),
                t("dialog_current_position_required_msg"),
            )
            return

        start_lat, start_lon = self.current_simulated_position
        self.mode_var.set("navigation")
        self._on_mode_change()
        self._clear_route()
        self._add_route_point(start_lat, start_lon)
        self._add_route_point(location.latitude, location.longitude)
        self.status_label.configure(
            text=t("status_navigation_from_current", name=location.name)
        )
        self._calculate_navigation_route()

    def _delete_saved_location(self, location: SavedLocationInfo):
        if messagebox.askyesno(
            t("dialog_delete_location_title"),
            t("dialog_delete_location_confirm_msg", name=location.name),
        ):
            self.location_storage.delete(location.id)
            self._refresh_saved_locations()

    def _refresh_saved_routes(self):
        if not hasattr(self, "routes_list_frame"):
            return
        self._clear_widget_children(self.routes_list_frame)
        routes = self.route_storage.list_all()
        if not routes:
            ctk.CTkLabel(
                self.routes_list_frame,
                text=t("dialog_no_routes_msg"),
                text_color="gray",
                justify="center",
            ).grid(row=0, column=0, padx=10, pady=20, sticky="ew")
            return

        for row, route in enumerate(routes):
            self._create_route_row(self.routes_list_frame, row, route)

    def _create_route_row(self, parent, row: int, route: SavedRouteInfo):
        item = ctk.CTkFrame(parent, fg_color="#1f2937")
        item.grid(row=row, column=0, padx=4, pady=4, sticky="ew")
        item.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            item,
            text=route.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 0), sticky="ew")

        ctk.CTkLabel(
            item,
            text=t(
                "route_row_meta",
                points=route.point_count,
                created=route.created_at[:16],
            ),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")

        ctk.CTkButton(
            item,
            text=t("btn_load_route"),
            height=26,
            command=lambda route_id=route.id: self._load_route_by_id(route_id),
        ).grid(row=2, column=0, padx=(8, 3), pady=(0, 8), sticky="ew")

        ctk.CTkButton(
            item,
            text=t("btn_delete_short"),
            height=26,
            width=64,
            fg_color="#6b7280",
            hover_color="#4b5563",
            command=lambda r=route: self._delete_saved_route(r),
        ).grid(row=2, column=1, padx=(3, 8), pady=(0, 8), sticky="ew")

    def _load_route_by_id(self, route_id: int):
        name, points = self.route_storage.load(route_id)
        self._load_route_points(name, points)

    def _load_route_points(self, name: str, points: list[RoutePoint]):
        self._clear_route()

        # Put them on map. Large calculated routes only get start/end markers.
        if len(points) > 50:
            points[0].marker = self.map_widget.set_marker(
                points[0].latitude,
                points[0].longitude,
                text=t("marker_start"),
                marker_color_circle="#10b981",
            )
            points[-1].marker = self.map_widget.set_marker(
                points[-1].latitude,
                points[-1].longitude,
                text=t("marker_end"),
                marker_color_circle="#ef4444",
            )
        else:
            for i, p in enumerate(points):
                p.marker = self.map_widget.set_marker(
                    p.latitude,
                    p.longitude,
                    text=t("marker_point", index=i + 1),
                    marker_color_circle="#3b82f6",
                )

        self.route_points = points
        self._update_route_path()
        self._update_route_info()

        if points:
            self.map_widget.set_position(points[0].latitude, points[0].longitude)

        self.status_label.configure(text=t("status_route_loaded", name=name))

    def _delete_saved_route(self, route: SavedRouteInfo):
        if messagebox.askyesno(
            t("dialog_delete_title"),
            t("dialog_delete_confirm_msg", name=route.name),
        ):
            self.route_storage.delete(route.id)
            self._refresh_saved_routes()

    # -------------------------------------------------------------
    # Route Storage and GPX
    # -------------------------------------------------------------

    def _save_route_dialog(self):
        if not self.route_points:
            return
        name = ctk.CTkInputDialog(
            text=t("dialog_save_msg"), title=t("dialog_save_title")
        ).get_input()
        if name:
            self.route_storage.save(name, self.route_points)
            self._refresh_saved_routes()
            messagebox.showinfo(
                t("dialog_saved_title"),
                t("dialog_saved_msg", name=name),
            )

    def _export_gpx_dialog(self):
        if not self.route_points:
            return
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(
            defaultextension=".gpx", filetypes=[("GPX Files", "*.gpx")]
        )
        if path:
            import gpxpy.gpx

            gpx = gpxpy.gpx.GPX()
            gpx_track = gpxpy.gpx.GPXTrack(name="Exported Route")
            gpx.tracks.append(gpx_track)
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)
            for p in self.route_points:
                gpx_segment.points.append(
                    gpxpy.gpx.GPXTrackPoint(p.latitude, p.longitude)
                )
            with open(path, "w", encoding="utf-8") as f:
                f.write(gpx.to_xml())
            messagebox.showinfo(
                t("dialog_exported_title"),
                t("dialog_exported_msg", path=path),
            )

    def _import_gpx_dialog(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(filetypes=[("GPX Files", "*.gpx")])
        if path:
            try:
                # Use the new helper which also parses
                _, name, points = self.route_storage.import_gpx(path, save_to_db=False)
                self._clear_route()

                if len(points) > 50:
                    points[0].marker = self.map_widget.set_marker(
                        points[0].latitude,
                        points[0].longitude,
                        text=t("marker_start"),
                        marker_color_circle="#10b981",
                    )
                    points[-1].marker = self.map_widget.set_marker(
                        points[-1].latitude,
                        points[-1].longitude,
                        text=t("marker_end"),
                        marker_color_circle="#ef4444",
                    )
                else:
                    for i, p in enumerate(points):
                        p.marker = self.map_widget.set_marker(
                            p.latitude,
                            p.longitude,
                            text=t("marker_point", index=i + 1),
                            marker_color_circle="#3b82f6",
                        )

                self.route_points = points
                self._update_route_path()
                self._update_route_info()
                if points:
                    self.map_widget.set_position(
                        points[0].latitude, points[0].longitude
                    )
                self.status_label.configure(
                    text=t("status_gpx_loaded", name=name, points=len(points))
                )
            except Exception as e:
                messagebox.showerror(
                    t("dialog_gpx_error_title"),
                    t("dialog_gpx_error_msg", error=e),
                )

    def _on_speed_entry_change(self, event=None):
        """Handle speed entry change."""
        try:
            val = float(self.speed_entry_var.get())
            if val < 0:
                val = 0.0
            self.speed_slider.set(min(val, 110.0))
            self.route_walker.set_speed(val)
            self.speed_entry_var.set(f"{val:.1f}")
        except ValueError:
            self.speed_entry_var.set(f"{self.speed_slider.get():.1f}")
        self._update_route_info()
        self.focus_set()

    def _apply_speed_preset(self, speed_kmh: float):
        """Apply a preset to the existing speed controls."""
        self.speed_slider.set(speed_kmh)
        self.speed_entry_var.set(f"{speed_kmh:.1f}")
        self.route_walker.set_speed(speed_kmh)
        self._update_route_info()
        self.focus_set()

    def _get_current_speed_kmh(self) -> float:
        """Read the current speed from the UI, falling back to the slider value."""
        try:
            return max(0.0, float(self.speed_entry_var.get()))
        except ValueError:
            return float(self.speed_slider.get())

    def _apply_motion_settings(
        self,
        noise_pct: float,
        random_stop_enabled: bool,
        random_stop_interval_m: float,
        random_stop_min_s: float,
        random_stop_max_s: float,
        displacement_noise_enabled: bool,
        displacement_radius_m: float,
    ):
        """Apply motion realism settings to UI state and the route walker."""
        self.motion_noise_pct = max(0.0, min(50.0, float(noise_pct)))
        self.random_stop_enabled = bool(random_stop_enabled)
        self.random_stop_interval_m = max(1.0, float(random_stop_interval_m))
        self.random_stop_min_s = max(1.0, float(random_stop_min_s))
        self.random_stop_max_s = max(
            self.random_stop_min_s, float(random_stop_max_s)
        )
        self.displacement_noise_enabled = bool(displacement_noise_enabled)
        self.displacement_radius_m = max(0.0, float(displacement_radius_m))
        self.route_walker.set_speed_noise(self.motion_noise_pct)
        self.route_walker.set_random_stop_settings(
            self.random_stop_enabled,
            self.random_stop_interval_m,
            self.random_stop_min_s,
            self.random_stop_max_s,
        )
        self.route_walker.set_displacement_noise_settings(
            self.displacement_noise_enabled,
            self.displacement_radius_m,
        )
        self.motion_settings = MotionSettings(
            noise_pct=self.motion_noise_pct,
            random_stop_enabled=self.random_stop_enabled,
            random_stop_interval_m=self.random_stop_interval_m,
            random_stop_min_s=self.random_stop_min_s,
            random_stop_max_s=self.random_stop_max_s,
            displacement_noise_enabled=self.displacement_noise_enabled,
            displacement_radius_m=self.displacement_radius_m,
        )
        motion_settings_store = self.__dict__.get("motion_settings_store")
        if motion_settings_store is not None:
            motion_settings_store.save(self.motion_settings)
        self._update_route_info()

    def _try_apply_motion_settings_values(
        self,
        noise_pct: float,
        random_stop_enabled: bool,
        random_stop_interval_text: str,
        random_stop_min_text: str,
        random_stop_max_text: str,
        displacement_noise_enabled: bool,
        displacement_radius_text: str,
    ) -> bool:
        """Try to persist motion settings from popup control values."""
        try:
            self._apply_motion_settings(
                noise_pct=float(noise_pct),
                random_stop_enabled=bool(random_stop_enabled),
                random_stop_interval_m=float(random_stop_interval_text),
                random_stop_min_s=float(random_stop_min_text),
                random_stop_max_s=float(random_stop_max_text),
                displacement_noise_enabled=bool(displacement_noise_enabled),
                displacement_radius_m=float(displacement_radius_text),
            )
        except ValueError:
            return False
        return True

    def _open_motion_settings(self):
        """Open a small popup to edit speed noise and random stop settings."""
        if self._motion_settings_window and self._motion_settings_window.winfo_exists():
            self._motion_settings_window.focus()
            return

        win = ctk.CTkToplevel(self)
        win.title(t("motion_settings_title"))
        win.geometry("380x320")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        self._motion_settings_window = win

        noise_var = ctk.DoubleVar(value=self.motion_noise_pct)
        enabled_var = ctk.BooleanVar(value=self.random_stop_enabled)
        interval_var = ctk.StringVar(value=f"{self.random_stop_interval_m:.0f}")
        min_var = ctk.StringVar(value=f"{self.random_stop_min_s:.0f}")
        max_var = ctk.StringVar(value=f"{self.random_stop_max_s:.0f}")
        displacement_enabled_var = ctk.BooleanVar(value=self.displacement_noise_enabled)
        displacement_radius_var = ctk.StringVar(value=f"{self.displacement_radius_m:.1f}")

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=14)
        body.grid_columnconfigure(1, weight=1)

        noise_label_frame = ctk.CTkFrame(body, fg_color="transparent")
        noise_label_frame.grid(row=0, column=0, sticky="w", pady=(0, 6))
        ctk.CTkLabel(noise_label_frame, text=t("motion_noise_label")).pack(side="left")
        add_tooltip_button(noise_label_frame, text=t("motion_noise_help")).pack(
            side="left", padx=(4, 0)
        )
        noise_value = ctk.CTkLabel(body, text=f"{self.motion_noise_pct:.0f}%")
        noise_value.grid(row=0, column=1, sticky="e", pady=(0, 6))

        def sync_motion_settings_live():
            return self._try_apply_motion_settings_values(
                noise_pct=noise_var.get(),
                random_stop_enabled=enabled_var.get(),
                random_stop_interval_text=interval_var.get(),
                random_stop_min_text=min_var.get(),
                random_stop_max_text=max_var.get(),
                displacement_noise_enabled=displacement_enabled_var.get(),
                displacement_radius_text=displacement_radius_var.get(),
            )

        def on_noise_change(value):
            noise_value.configure(text=f"{float(value):.0f}%")
            sync_motion_settings_live()

        noise_slider = ctk.CTkSlider(
            body,
            from_=0,
            to=50,
            number_of_steps=50,
            variable=noise_var,
            command=on_noise_change,
        )
        noise_slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        random_stop_row = ctk.CTkFrame(body, fg_color="transparent")
        random_stop_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))
        random_stop_switch = ctk.CTkSwitch(
            random_stop_row,
            text=t("motion_random_stop_label"),
            variable=enabled_var,
            onvalue=True,
            offvalue=False,
        )
        random_stop_switch.pack(side="left")
        add_tooltip_button(
            random_stop_row, text=t("motion_random_stop_help")
        ).pack(side="left", padx=(4, 0))

        interval_label_frame = ctk.CTkFrame(body, fg_color="transparent")
        interval_label_frame.grid(row=3, column=0, sticky="w", pady=4)
        ctk.CTkLabel(interval_label_frame, text=t("motion_stop_interval_label")).pack(
            side="left"
        )
        add_tooltip_button(
            interval_label_frame, text=t("motion_stop_interval_help")
        ).pack(side="left", padx=(4, 0))
        interval_entry = ctk.CTkEntry(body, textvariable=interval_var, width=90)
        interval_entry.grid(row=3, column=1, sticky="e", pady=4)

        min_label_frame = ctk.CTkFrame(body, fg_color="transparent")
        min_label_frame.grid(row=4, column=0, sticky="w", pady=4)
        ctk.CTkLabel(min_label_frame, text=t("motion_stop_min_label")).pack(side="left")
        add_tooltip_button(min_label_frame, text=t("motion_stop_min_help")).pack(
            side="left", padx=(4, 0)
        )
        min_entry = ctk.CTkEntry(body, textvariable=min_var, width=90)
        min_entry.grid(row=4, column=1, sticky="e", pady=4)

        max_label_frame = ctk.CTkFrame(body, fg_color="transparent")
        max_label_frame.grid(row=5, column=0, sticky="w", pady=4)
        ctk.CTkLabel(max_label_frame, text=t("motion_stop_max_label")).pack(side="left")
        add_tooltip_button(max_label_frame, text=t("motion_stop_max_help")).pack(
            side="left", padx=(4, 0)
        )
        max_entry = ctk.CTkEntry(body, textvariable=max_var, width=90)
        max_entry.grid(row=5, column=1, sticky="e", pady=4)

        displacement_row = ctk.CTkFrame(body, fg_color="transparent")
        displacement_row.grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(10, 8)
        )
        displacement_switch = ctk.CTkSwitch(
            displacement_row,
            text=t("motion_displacement_label"),
            variable=displacement_enabled_var,
            onvalue=True,
            offvalue=False,
        )
        displacement_switch.pack(side="left")
        add_tooltip_button(
            displacement_row, text=t("motion_displacement_help")
        ).pack(side="left", padx=(4, 0))

        displacement_label_frame = ctk.CTkFrame(body, fg_color="transparent")
        displacement_label_frame.grid(row=7, column=0, sticky="w", pady=4)
        ctk.CTkLabel(
            displacement_label_frame, text=t("motion_displacement_radius_label")
        ).pack(side="left")
        add_tooltip_button(
            displacement_label_frame, text=t("motion_displacement_radius_help")
        ).pack(side="left", padx=(4, 0))
        displacement_entry = ctk.CTkEntry(
            body, textvariable=displacement_radius_var, width=90
        )
        displacement_entry.grid(row=7, column=1, sticky="e", pady=4)

        dependent_widgets = [interval_entry, min_entry, max_entry]

        def sync_enabled_state():
            state = "normal" if enabled_var.get() else "disabled"
            for widget in dependent_widgets:
                widget.configure(state=state)

        def on_random_stop_toggle():
            sync_enabled_state()
            sync_motion_settings_live()

        random_stop_switch.configure(command=on_random_stop_toggle)
        sync_enabled_state()

        def sync_displacement_state():
            displacement_entry.configure(
                state="normal" if displacement_enabled_var.get() else "disabled"
            )

        def on_displacement_toggle():
            sync_displacement_state()
            sync_motion_settings_live()

        displacement_switch.configure(command=on_displacement_toggle)
        sync_displacement_state()

        def bind_live_apply(entry: ctk.CTkEntry):
            entry.bind("<FocusOut>", lambda event: sync_motion_settings_live(), add="+")
            entry.bind("<Return>", lambda event: sync_motion_settings_live(), add="+")

        for entry in (interval_entry, min_entry, max_entry, displacement_entry):
            bind_live_apply(entry)

        footer = ctk.CTkFrame(win, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(0, 14))
        footer.grid_columnconfigure((0, 1), weight=1)

        def close_window():
            sync_motion_settings_live()
            if self._motion_settings_window:
                self._motion_settings_window.destroy()
                self._motion_settings_window = None

        def save_settings():
            if not sync_motion_settings_live():
                messagebox.showerror(
                    t("motion_settings_invalid_title"),
                    t("motion_settings_invalid_msg"),
                )
                return
            close_window()

        ctk.CTkButton(
            footer,
            text=t("btn_cancel"),
            command=close_window,
            fg_color="#6b7280",
            hover_color="#4b5563",
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            footer,
            text=t("btn_apply"),
            command=save_settings,
        ).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        win.protocol("WM_DELETE_WINDOW", close_window)

    def _get_remaining_route_summary(self, speed_kmh: float):
        """Estimate remaining route distance/time from the current simulated position."""
        if self.current_simulated_position is None or not self.route_points:
            return None

        if len(self.route_points) == 1:
            return summarize_route(
                self.route_points,
                speed_kmh,
                origin=self.current_simulated_position,
            )

        progress = self.route_walker.get_progress_snapshot()
        if bool(progress["is_walking"]) or bool(progress["is_paused"]):
            next_point_index = int(progress["resume_segment_index"]) + 1
            summary = summarize_remaining_route(
                self.route_points,
                speed_kmh,
                self.current_simulated_position,
                next_point_index,
            )
            remaining_wait_s = float(progress.get("random_stop_remaining_s", 0.0))
            if remaining_wait_s > 0:
                summary = RouteSummary(
                    point_count=summary.point_count,
                    segments=summary.segments,
                    total_distance_m=summary.total_distance_m,
                    total_duration_s=summary.total_duration_s + remaining_wait_s,
                )
            return summary

        return None

    def _on_noise_change(self, value):
        """Handle noise slider change."""
        noise_percent = float(value)
        self.noise_value_label.configure(text=f"{noise_percent:.0f}%")
        self.route_walker.set_speed_noise(noise_percent)

    def _start_walking(self):
        """Start or resume walking the route."""
        if len(self.route_points) < 2:
            return

        if self.route_walker.is_walking and not self.route_walker.is_paused:
            return

        # Initialize the walker with current UI state if not active
        if not self.route_walker.is_walking:
            self.route_walker.set_route(self.route_points)
            self.route_walker.set_loop(self.loop_var.get())
            self.route_walker.start()
            self.status_label.configure(text=t("status_walking"))
        elif self.route_walker.is_paused:
            self.route_walker.resume()
            self.status_label.configure(text=t("status_resumed"))

        # Update button states
        self.start_walk_btn.configure(state="disabled")
        self.pause_walk_btn.configure(state="normal")
        self.stop_walk_btn.configure(state="normal")

    def _pause_walking(self):
        """Pause the active route walk."""
        if self.route_walker.is_walking and not self.route_walker.is_paused:
            self.route_walker.pause()
            self.status_label.configure(text=t("status_paused"))

            # Update button states
            self.start_walk_btn.configure(state="normal")
            self.pause_walk_btn.configure(state="disabled")

    def _stop_walking(self):
        """Stop walking the route completely."""
        self.route_walker.stop()
        self.status_label.configure(text=t("status_walk_stopped"))

        # Reset walker state visually (optional, depending on desired UX)
        # Here we just re-enable Start and disable Pause/Stop
        self.start_walk_btn.configure(state="normal")
        self.pause_walk_btn.configure(state="disabled")
        self.stop_walk_btn.configure(state="disabled")

    def _on_walk_step(self, lat: float, lon: float):
        """Callback from RouteWalker when location is updated."""
        # This is typically called from a background thread, but Tkinter allows
        # Some basic variable updates. We use after() where safe.
        self.after(0, lambda: self._update_walk_ui(lat, lon))

    def _update_walk_ui(self, lat: float, lon: float):
        """Safely update UI with new walk coordinates."""
        self.current_simulated_position = (lat, lon)
        self._update_route_info()
        # Update current position marker
        if self.current_position_marker:
            self.current_position_marker.set_position(lat, lon)
        else:
            self.current_position_marker = self.map_widget.set_marker(
                lat,
                lon,
                text=t("marker_current_location"),
                marker_color_circle="#ef4444",
                marker_color_outside="#b91c1c",
            )
        if self.follow_current_position:
            self.map_widget.set_position(lat, lon)

    def _on_walk_batch_complete(self):
        """Callback when current route batch is consumed (append-only still active)."""
        self.after(0, self._handle_walk_batch_complete_ui)

    def _handle_walk_batch_complete_ui(self):
        """Show completion status/notification each time current batch finishes."""
        self._update_route_info()
        self.status_label.configure(text=t("status_walk_complete"))

        # Use notifier utility to show a Windows toast notification
        import src.utils.notifier as notifier

        notifier.notify(
            title=t("notify_walk_complete_title"),
            message=t("notify_walk_complete_body"),
        )
        messagebox.showinfo(
            t("notify_walk_complete_title"),
            t("notify_walk_complete_body"),
        )

    def _on_walk_device_disconnected(self):
        """Callback when walker auto-pauses due to device disconnection."""
        self.after(0, self._handle_walk_device_disconnected_ui)

    def _handle_walk_device_disconnected_ui(self):
        """Notify user and keep controls in paused state after disconnect."""
        self.status_label.configure(text=t("status_walk_paused_disconnected"))
        self.start_walk_btn.configure(state="normal")
        self.pause_walk_btn.configure(state="disabled")
        self.stop_walk_btn.configure(state="normal")

        # Reset global connection state
        self._disconnect_device()

        import src.utils.notifier as notifier

        notifier.notify(
            title=t("notify_device_disconnected_title"),
            message=t("notify_device_disconnected_body"),
        )
        messagebox.showwarning(
            t("dialog_walk_disconnected_title"),
            t("dialog_walk_disconnected_msg"),
        )

    def _on_walk_session_end(self):
        """Callback when walker session/thread actually ends."""
        self.after(0, self._handle_walk_session_end_ui)

    def _handle_walk_session_end_ui(self):
        """Reset controls when a walk session is fully stopped."""
        self._update_route_info()
        self.start_walk_btn.configure(state="normal")
        self.pause_walk_btn.configure(state="disabled")
        self.stop_walk_btn.configure(state="disabled")

    def _set_manual_location(self):
        """Set location from manual coordinates."""
        try:
            lat, lon = parse_coordinate_pair(self.lat_entry.get(), self.lon_entry.get())

            # Center map on location
            self.map_widget.set_position(lat, lon)

            # Set location
            self._set_location_at(lat, lon)

        except ValueError:
            messagebox.showerror(
                t("dialog_invalid_coords_title"),
                t("dialog_invalid_coords_msg"),
            )

    def _clear_location(self):
        """Clear the simulated location."""
        if not self.device_manager.connected:
            messagebox.showwarning(
                t("dialog_not_connected_title"), t("dialog_not_connected_msg")
            )
            return

        def clear_loc():
            success = self.device_manager.clear_location()
            self.after(0, lambda: self._on_location_cleared(success))

        threading.Thread(target=clear_loc, daemon=True).start()
        self.status_label.configure(text=t("status_clearing_location"))

    def _on_location_cleared(self, success: bool):
        """Called after location is cleared."""
        if success:
            self.current_simulated_position = None
            self._update_route_info()
            self.status_label.configure(text=t("status_location_cleared"))
            if self.current_position_marker:
                self.current_position_marker.delete()
                self.current_position_marker = None
        else:
            self.status_label.configure(text=t("status_location_clear_failed"))

    def _show_log_viewer(self):
        """Show recent application log output in a small GUI window."""
        try:
            log_window = ctk.CTkToplevel(self)
            log_window.title(t("log_viewer_title"))
            log_window.geometry("900x520")
            log_window.transient(self)

            log_window.grid_columnconfigure(0, weight=1)
            log_window.grid_rowconfigure(0, weight=1)

            textbox = ctk.CTkTextbox(
                log_window,
                font=ctk.CTkFont(family="Consolas", size=11),
                wrap="none",
            )
            textbox.grid(row=0, column=0, padx=10, pady=(10, 6), sticky="nsew")

            actions = ctk.CTkFrame(log_window, fg_color="transparent")
            actions.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
            actions.grid_columnconfigure(0, weight=1)

            def load_log():
                path = get_log_file_path()
                if not path.exists():
                    content = t("log_empty")
                else:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                    content = "\n".join(lines[-500:]) or t("log_empty")
                textbox.configure(state="normal")
                textbox.delete("1.0", "end")
                textbox.insert("1.0", content)
                textbox.see("end")
                textbox.configure(state="disabled")

            refresh_btn = ctk.CTkButton(
                actions,
                text=t("btn_refresh_log"),
                command=load_log,
                width=110,
                height=28,
                fg_color="#374151",
                hover_color="#4b5563",
            )
            refresh_btn.grid(row=0, column=1, sticky="e")

            load_log()
            self.status_label.configure(text=t("status_opened_log_viewer"))
        except Exception as e:
            logger.error("Failed to open log viewer: %s", e, exc_info=True)
            messagebox.showerror(
                t("dialog_log_open_failed_title"),
                t("dialog_log_open_failed_msg", error=e),
            )

    def _check_windows_notification_registration(self):
        """Auto-register Windows AppUserModelID if missing (silent mode)."""
        if sys.platform != "win32":
            return

        try:
            import src.utils.notifier as notifier

            if notifier.is_windows_app_id_registered():
                logger.debug("Windows AppUserModelID already registered.")
                return

            ok = notifier.register_windows_app_id(icon_path=self._icon_path)
            if ok:
                logger.info(
                    "Windows AppUserModelID registered automatically at startup."
                )
            else:
                logger.warning(
                    "Windows AppUserModelID auto-registration failed; toast may be less reliable."
                )
        except Exception as e:
            logger.warning("Notification registration check failed: %s", e)

    def _check_for_updates_on_startup(self):
        """Check latest GitHub release and prompt user to open download page."""

        def run_check():
            latest = update_checker.fetch_latest_release()
            if not latest:
                return

            current_version = update_checker.get_current_version()
            if not update_checker.is_newer_version(latest.version, current_version):
                return

            changelog = update_checker.summarize_changelog(latest.body)
            self.after(
                0,
                lambda: self._show_update_prompt(
                    current_version=current_version,
                    latest_version=latest.version,
                    release_url=latest.html_url,
                    changelog=changelog,
                    asset_url=latest.asset_url,
                    asset_size=latest.asset_size,
                ),
            )

        threading.Thread(target=run_check, daemon=True).start()

    def _show_update_prompt(
        self,
        current_version: str,
        latest_version: str,
        release_url: str,
        changelog: str,
        asset_url: Optional[str] = None,
        asset_size: int = 0,
    ):
        """Prompt the user. On the frozen exe with a downloadable asset, offer a
        one-click in-app update; otherwise fall back to opening the release page."""
        changelog_text = changelog or t("dialog_update_changelog_empty")

        if updater.is_supported() and asset_url:
            message = t(
                "dialog_update_available_msg_auto",
                current=current_version,
                latest=latest_version,
                changelog=changelog_text,
            )
            if messagebox.askyesno(t("dialog_update_available_title"), message):
                self._start_auto_update(asset_url, asset_size, release_url)
            return

        # Fallback: just open the release page for a manual download.
        message = t(
            "dialog_update_available_msg",
            current=current_version,
            latest=latest_version,
            url=release_url,
            changelog=changelog_text,
        )
        if messagebox.askyesno(t("dialog_update_available_title"), message):
            webbrowser.open(release_url)

    def _start_auto_update(self, asset_url: str, asset_size: int, release_url: str):
        """Download the new exe with a progress dialog, then hand off to the
        swap helper and close the app so it can replace the locked exe."""
        win = ctk.CTkToplevel(self)
        win.title(t("update_progress_title"))
        win.geometry("440x150")
        win.transient(self)
        win.grab_set()
        # Block the close button while the download is in progress.
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        label = ctk.CTkLabel(win, text=t("update_progress_downloading", pct=0))
        label.pack(padx=20, pady=(28, 12))
        bar = ctk.CTkProgressBar(win, width=380)
        bar.set(0)
        bar.pack(padx=20, pady=4)

        def on_progress(written: int, total: int):
            pct = int(written * 100 / total) if total else 0
            self.after(0, lambda: self._update_progress_ui(bar, label, pct))

        def worker():
            try:
                path = updater.download_update(
                    asset_url, expected_size=asset_size, progress_cb=on_progress
                )
            except Exception as e:
                logger.error("Auto-update download failed: %s", e, exc_info=True)
                # bind err by value: the except-scoped `e` is cleared after the block
                self.after(0, lambda err=e: self._auto_update_failed(win, err, release_url))
                return
            self.after(0, lambda: self._auto_update_ready(win, label, path, release_url))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress_ui(self, bar, label, pct: int):
        try:
            bar.set(max(0.0, min(1.0, pct / 100)))
            label.configure(text=t("update_progress_downloading", pct=pct))
        except Exception:
            pass

    def _auto_update_failed(self, win, error, release_url: str):
        try:
            win.destroy()
        except Exception:
            pass
        if messagebox.askyesno(
            t("update_failed_title"), t("update_failed_msg", error=error)
        ):
            webbrowser.open(release_url)

    def _auto_update_ready(self, win, label, new_exe_path: str, release_url: str):
        try:
            label.configure(text=t("update_progress_preparing"))
            self.update_idletasks()
        except Exception:
            pass
        try:
            updater.apply_update_and_exit(new_exe_path)
        except Exception as e:
            logger.error("Failed to launch update helper: %s", e, exc_info=True)
            self._auto_update_failed(win, e, release_url)
            return
        # Close cleanly so tunneld/device handles are released and the helper can
        # overwrite the now-unlocked exe, then relaunch.
        self._on_close()

    # -------------------------------------------------------------
    # Device screen preview (pseudo-realtime burst capture)
    # -------------------------------------------------------------

    @staticmethod
    def _fit_size(img_w: int, img_h: int, box_w: int, box_h: int) -> tuple[int, int]:
        """Scale (img_w, img_h) to fit within (box_w, box_h), preserving aspect."""
        if img_w <= 0 or img_h <= 0:
            return (box_w, box_h)
        scale = min(box_w / img_w, box_h / img_h)
        return (max(1, int(img_w * scale)), max(1, int(img_h * scale)))

    def _open_device_preview(self):
        """Open (or focus) the floating device-screen preview window."""
        if not self.device_manager.connected:
            messagebox.showinfo(t("preview_window_title"), t("preview_not_connected"))
            return

        # Already open → just bring it forward.
        if self._preview_window is not None and self._preview_window.winfo_exists():
            self._preview_window.lift()
            self._preview_window.focus_force()
            return

        win = ctk.CTkToplevel(self)
        win.title(t("preview_window_title"))
        win.geometry("380x760")
        win.minsize(240, 360)
        win.configure(fg_color="#0f172a")
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)

        # Plain tk.Label + ImageTk shows the frame at exact pixel size — CTkImage
        # would re-scale by the HiDPI factor and overflow/clip the window.
        self._preview_image_label = tk.Label(win, bg="#020617", bd=0)
        self._preview_image_label.grid(
            row=0, column=0, sticky="nsew", padx=8, pady=(8, 4)
        )

        controls = ctk.CTkFrame(win, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        controls.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(controls, text=t("preview_rate_label")).grid(
            row=0, column=0, padx=(0, 6)
        )
        rate = ctk.CTkSegmentedButton(
            controls,
            values=[
                t("preview_rate_slow"),
                t("preview_rate_mid"),
                t("preview_rate_fast"),
            ],
            command=self._on_preview_rate_change,
        )
        rate.set(t("preview_rate_mid"))
        rate.grid(row=0, column=1, sticky="ew")

        self._preview_status_label = ctk.CTkLabel(
            win, text=t("preview_status_waiting"), text_color="#94a3b8"
        )
        self._preview_status_label.grid(
            row=2, column=0, sticky="ew", padx=8, pady=(0, 8)
        )

        self._preview_window = win
        self._preview_stop_event = threading.Event()
        self._preview_visible = True
        win.protocol("WM_DELETE_WINDOW", self._close_device_preview)
        # Pause capture while minimized (no point burning USB/CPU when hidden).
        win.bind("<Unmap>", lambda e: e.widget is win and setattr(self, "_preview_visible", False))
        win.bind("<Map>", lambda e: e.widget is win and setattr(self, "_preview_visible", True))

        threading.Thread(
            target=self._preview_loop, args=(self._preview_stop_event,), daemon=True
        ).start()

    def _on_preview_rate_change(self, value: str):
        mapping = {
            t("preview_rate_slow"): 1.5,
            t("preview_rate_mid"): 0.7,
            t("preview_rate_fast"): 0.3,
        }
        self._preview_interval = mapping.get(value, 0.7)

    def _preview_loop(self, stop_event: threading.Event):
        """Background worker: grab → decode → post to UI, until stopped.

        Decoding (the heavy part) happens here off the UI thread; the resize to
        the live window size happens on the UI thread (it needs the real widget
        pixels). Capture is skipped while the window is minimized.
        """
        from PIL import Image

        errors = 0
        while not stop_event.is_set():
            if not self._preview_visible:
                stop_event.wait(0.3)
                continue
            try:
                png = self._screenshot_service.capture_png()
                errors = 0
                img = Image.open(io.BytesIO(png))
                img.load()
                self.after(0, lambda im=img: self._update_preview_image(im))
            except Exception as e:
                errors += 1
                msg = str(e)
                self.after(0, lambda m=msg: self._set_preview_status(m))
                # Back off on repeated failures (device locked / disconnected).
                stop_event.wait(min(3.0, 0.5 * errors))
            stop_event.wait(self._preview_interval)

    def _update_preview_image(self, pil_image):
        from PIL import ImageTk

        win = self._preview_window
        label = self._preview_image_label
        if win is None or not win.winfo_exists() or label is None:
            return

        # Fit to the label's REAL pixel size (ImageTk shows 1:1, no HiDPI scaling).
        avail_w = label.winfo_width()
        avail_h = label.winfo_height()
        if avail_w < 50 or avail_h < 50:  # not realized yet → estimate from window
            avail_w = max(win.winfo_width() - 24, 100)
            avail_h = max(win.winfo_height() - 96, 100)
        w, h = self._fit_size(pil_image.width, pil_image.height, avail_w, avail_h)

        self._preview_ctk_image = ImageTk.PhotoImage(pil_image.resize((w, h)))
        label.configure(image=self._preview_ctk_image)
        if self._preview_status_label is not None:
            self._preview_status_label.configure(text="")

    def _set_preview_status(self, error: str):
        if (
            self._preview_status_label is not None
            and self._preview_status_label.winfo_exists()
        ):
            self._preview_status_label.configure(
                text=t("preview_status_error", error=error)
            )

    def _close_device_preview(self):
        """Stop the capture loop and release the preview window/connection."""
        if self._preview_stop_event is not None:
            self._preview_stop_event.set()
        self._preview_stop_event = None
        try:
            self._screenshot_service.close()
        except Exception as e:
            logger.debug("Error closing screenshot service: %s", e)
        if self._preview_window is not None:
            try:
                self._preview_window.destroy()
            except Exception:
                pass
        self._preview_window = None
        self._preview_image_label = None
        self._preview_status_label = None
        self._preview_ctk_image = None

    def _on_close(self):
        """Handle window close."""
        # Stop the device preview first so its DVT channel is released.
        self._close_device_preview()

        # Try to clear simulated location before disconnect/exit.
        # Keep this quiet to avoid interrupting shutdown with dialogs.
        if self.device_manager and self.device_manager.connected:
            try:
                self.device_manager.clear_location()
            except Exception as e:
                logger.warning(f"Failed to clear simulated location on exit: {e}")

        # Stop walking
        if self.route_walker:
            self.route_walker.stop()

        # Disconnect device
        if self.device_manager:
            self.device_manager.disconnect()

        # Stop tunneld if we started it
        if self.tunneld_manager:
            self.tunneld_manager.stop()

        # Destroy window
        self.destroy()
