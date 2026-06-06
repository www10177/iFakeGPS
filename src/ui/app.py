import os
import sys
import threading
import time
import webbrowser
from enum import Enum
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from src.core import update_checker
from src.core.device_manager import DeviceManager
from src.core.location_storage import LocationStorage, SavedLocationInfo
from src.core.models import DeviceInfo, RoutePoint
from src.core.route_storage import RouteStorage, SavedRouteInfo
from src.core.route_walker import RouteWalker
from src.core.routing import RoutingError, RoutingService
from src.core.tunnel_manager import TunneldManager
from src.ui.caching_map_view import CachingTileMapView
from src.ui.i18n import LANGUAGES, get_lang, set_lang, t
from src.ui.tooltip import ToolTip, add_tooltip_button
from src.utils.logger import get_log_dir, logger


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
            if getattr(sys, "frozen", False):
                application_path = sys._MEIPASS
            else:
                application_path = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )

            icon_path = os.path.join(application_path, "app.ico")
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
        # Note: RouteWalker constructor signature changed in our new core implementation
        # Reviewing core/route_walker.py: __init__(self, device_manager, update_callback, completion_callback=None)
        # So we pass callbacks in constructor now, simplified from property setters.

        # Setup Database paths (shared by map cache and route storage)
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        self.cache_dir = os.path.join(local_app_data, "iFakeGPS", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.db_path = os.path.join(self.cache_dir, "map_cache.db")

        # Initialize Routing & Storage
        self.route_storage = RouteStorage(os.path.join(self.cache_dir, "routes.db"))
        self.location_storage = LocationStorage(os.path.join(self.cache_dir, "routes.db"))
        self.routing_service = RoutingService()

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

        # Build UI
        self._create_ui()

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
                if getattr(sys, "frozen", False):
                    base_path = sys._MEIPASS
                else:
                    # We are in src/ui/app.py, project root is two levels up
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    base_path = os.path.abspath(os.path.join(current_dir, "..", ".."))

                manual_path = os.path.join(base_path, "docs", "USER_MANUAL_ZH.md")

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
        self.dev_status_indicator.configure(text="🔄 Checking...", text_color="orange")
        self.update()  # Force update

        def run_check():
            status = self.device_manager.check_developer_mode()
            self.after(0, lambda: self._update_dev_mode_ui(status))

        threading.Thread(target=run_check, daemon=True).start()

    def _update_dev_mode_ui(self, enabled: Optional[bool]):
        """Update the Developer Mode UI based on status."""
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
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 10))

        # Developer Mode Status Section
        dev_mode_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        dev_mode_frame.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="ew")
        dev_mode_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            dev_mode_frame,
            text=t("dev_mode_label"),
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.dev_status_indicator = ctk.CTkLabel(
            dev_mode_frame, text=t("dev_status_unknown"), font=ctk.CTkFont(size=12)
        )
        self.dev_status_indicator.grid(row=0, column=1, sticky="e")

        self.dev_check_btn = ctk.CTkButton(
            dev_mode_frame,
            text=t("dev_check_btn"),
            width=80,
            height=24,
            font=ctk.CTkFont(size=11),
            command=self._check_dev_mode,
        )
        self.dev_check_btn.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky="ew")

        self.dev_enable_btn = ctk.CTkButton(
            dev_mode_frame,
            text=t("dev_enable_btn"),
            width=80,
            height=24,
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=ctk.CTkFont(size=11),
            command=self._enable_dev_mode_flow,
        )
        self.dev_enable_btn.grid(
            row=2, column=0, columnspan=2, pady=(5, 0), sticky="ew"
        )
        self.dev_enable_btn.grid_remove()  # Hidden by default

        # Device selection section
        device_frame = ctk.CTkFrame(sidebar)
        device_frame.grid(row=4, column=0, padx=15, pady=10, sticky="ew")

        device_header = ctk.CTkFrame(device_frame, fg_color="transparent")
        device_header.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
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
        self.conn_status.grid(row=2, column=0, padx=10, pady=(5, 10))

        # Disconnect button
        self.disconnect_btn = ctk.CTkButton(
            device_frame,
            text=t("btn_disconnect"),
            command=self._disconnect_device,
            fg_color="#6b7280",
            hover_color="#4b5563",
            height=28,
        )
        self.disconnect_btn.grid(row=3, column=0, padx=10, pady=(0, 5), sticky="ew")

        # Wireless button
        self.enable_wireless_btn = ctk.CTkButton(
            device_frame,
            text=t("btn_enable_wireless"),
            command=self._enable_wireless_flow,
            fg_color="#374151",
            hover_color="#4b5563",
            height=28,
        )
        self.enable_wireless_btn.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew")
        add_tooltip_button(device_frame, text=t("tip_wireless")).grid(row=4, column=0, padx=(0, 10), sticky="e")

        # Mode selection
        mode_frame = ctk.CTkFrame(sidebar)
        mode_frame.grid(row=5, column=0, padx=15, pady=10, sticky="ew")

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
        self.route_frame.grid(row=6, column=0, padx=15, pady=5, sticky="ew")

        self.lbl_route = ctk.CTkLabel(
            self.route_frame,
            text=t("route_walking"),
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.lbl_route.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w"
        )

        # Speed slider — label row with tooltip icon
        speed_label_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        speed_label_frame.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.lbl_speed = ctk.CTkLabel(speed_label_frame, text=t("speed_label"))
        self.lbl_speed.pack(side="left")

        self._speed_tip_icon = add_tooltip_button(
            speed_label_frame, text=t("tip_speed")
        )
        self._speed_tip_icon.pack(side="left", padx=(2, 0))

        speed_val_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        speed_val_frame.grid(row=1, column=1, padx=10, pady=5, sticky="e")

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
            row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.speed_slider.set(20)
        self.route_walker.set_speed(20.0)

        # Speed noise slider — label row with tooltip icon
        noise_label_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        noise_label_frame.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.lbl_noise = ctk.CTkLabel(noise_label_frame, text=t("noise_label"))
        self.lbl_noise.pack(side="left")

        self._noise_tip_icon = add_tooltip_button(
            noise_label_frame, text=t("tip_noise")
        )
        self._noise_tip_icon.pack(side="left", padx=(2, 0))

        self.noise_value_label = ctk.CTkLabel(self.route_frame, text="10%")
        self.noise_value_label.grid(row=3, column=1, padx=10, pady=5, sticky="e")

        self.noise_slider = ctk.CTkSlider(
            self.route_frame,
            from_=0,
            to=50,
            number_of_steps=50,
            command=self._on_noise_change,
        )
        self.noise_slider.grid(
            row=4, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.noise_slider.set(10)
        self.route_walker.set_speed_noise(10.0)

        self.route_frame.grid_columnconfigure(0, weight=1)
        self.route_frame.grid_columnconfigure(1, weight=1)

        # Route info
        self.route_info = ctk.CTkLabel(
            self.route_frame,
            text=t("route_info", points=0, distance="0 m"),
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.route_info.grid(row=5, column=0, columnspan=2, padx=10, pady=5)

        # Route planning buttons
        route_plan_btn_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        route_plan_btn_frame.grid(
            row=6, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
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
            row=7, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
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
            row=8, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w"
        )

        # Coordinates section
        self.coord_frame = ctk.CTkFrame(sidebar)
        self.coord_frame.grid(row=7, column=0, padx=15, pady=5, sticky="ew")

        self.lbl_manual = ctk.CTkLabel(
            self.coord_frame,
            text=t("manual_coords"),
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.lbl_manual.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(5, 5), sticky="w"
        )

        self.lbl_lat = ctk.CTkLabel(
            self.coord_frame, text=t("label_lat"), font=ctk.CTkFont(size=11)
        )
        self.lbl_lat.grid(row=1, column=0, padx=10, pady=2, sticky="w")

        self.lat_entry = ctk.CTkEntry(
            self.coord_frame, placeholder_text="37.7749", height=24
        )
        self.lat_entry.grid(row=1, column=1, padx=10, pady=2, sticky="ew")

        self.lbl_lon = ctk.CTkLabel(
            self.coord_frame, text=t("label_lon"), font=ctk.CTkFont(size=11)
        )
        self.lbl_lon.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.lon_entry = ctk.CTkEntry(
            self.coord_frame, placeholder_text="-122.4194", height=24
        )
        self.lon_entry.grid(row=2, column=1, padx=10, pady=2, sticky="ew")

        self.coord_frame.grid_columnconfigure(1, weight=1)

        self.btn_teleport = ctk.CTkButton(
            self.coord_frame,
            text=t("btn_teleport"),
            command=self._set_manual_location,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
        )
        self.btn_teleport.grid(
            row=3, column=0, columnspan=2, padx=10, pady=10, sticky="ew"
        )

        # Global clear-location button (always visible across modes)
        self.clear_location_btn = ctk.CTkButton(
            sidebar,
            text=t("btn_clear_location"),
            command=self._clear_location,
            fg_color="#6b7280",
            hover_color="#4b5563",
            height=30,
        )
        self.clear_location_btn.grid(
            row=8, column=0, padx=15, pady=(5, 5), sticky="ew"
        )

        # Open logs folder button
        self.open_logs_btn = ctk.CTkButton(
            sidebar,
            text=t("btn_open_logs"),
            command=self._open_logs_folder,
            fg_color="#374151",
            hover_color="#4b5563",
            height=30,
        )
        self.open_logs_btn.grid(row=9, column=0, padx=15, pady=(0, 5), sticky="ew")

        # Info label at bottom
        info_label = ctk.CTkLabel(
            sidebar,
            text=t("info_tunneld"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        )
        self.info_label = info_label
        info_label.grid(row=11, column=0, padx=15, pady=(20, 5), sticky="sw")

        # Language selector
        lang_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        lang_frame.grid(row=12, column=0, padx=15, pady=(0, 15), sticky="sw")

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
        tab.grid_rowconfigure(3, weight=1)

        self.place_name_entry = ctk.CTkEntry(
            tab, placeholder_text=t("placeholder_location_name"), height=30
        )
        self.place_name_entry.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")

        location_actions = ctk.CTkFrame(tab, fg_color="transparent")
        location_actions.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        location_actions.grid_columnconfigure((0, 1), weight=1)

        self.btn_save_location = ctk.CTkButton(
            location_actions,
            text=t("btn_save_location"),
            command=self._toggle_saved_location_selection,
            height=30,
        )
        self.btn_save_location.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_save_current_position = ctk.CTkButton(
            location_actions,
            text=t("btn_save_current_position"),
            command=self._save_current_simulated_location,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
        )
        self.btn_save_current_position.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self.location_hint_label = ctk.CTkLabel(
            tab,
            text=t("location_panel_hint"),
            text_color="gray",
            font=ctk.CTkFont(size=11),
            justify="left",
            wraplength=270,
        )
        self.location_hint_label.grid(row=2, column=0, padx=8, pady=(2, 8), sticky="ew")

        self.locations_list_frame = ctk.CTkScrollableFrame(tab, fg_color="#111827")
        self.locations_list_frame.grid(row=3, column=0, padx=8, pady=4, sticky="nsew")
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

        # Set Google Maps as default tile server
        self.map_widget.set_tile_server(
            "https://mt1.google.com/vt/lyrs=m&hl=zh-TW&x={x}&y={y}&z={z}",
            max_zoom=19,
        )

        # Set default position (Taipei as fallback)
        self.map_widget.set_position(25.032192, 121.469360)
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
        if hasattr(self, "dev_check_btn"):
            self.dev_check_btn.configure(text=t("dev_check_btn"))
        if hasattr(self, "dev_enable_btn"):
            self.dev_enable_btn.configure(text=t("dev_enable_btn"))

        # Mode
        if hasattr(self, "single_radio"):
            self.single_radio.configure(text=t("mode_single"))
        if hasattr(self, "nav_radio"):
            self.nav_radio.configure(text=t("mode_navigation"))
        if hasattr(self, "lbl_route"):
            self.lbl_route.configure(text=t("route_walking"))
        if hasattr(self, "lbl_speed"):
            self.lbl_speed.configure(text=t("speed_label"))
        if hasattr(self, "lbl_noise"):
            self.lbl_noise.configure(text=t("noise_label"))

        # Tooltip icons — update their ToolTip text
        if hasattr(self, "_speed_tip_icon"):
            from src.ui.tooltip import ToolTip

            ToolTip(self._speed_tip_icon, text=t("tip_speed"))
        if hasattr(self, "_noise_tip_icon"):
            from src.ui.tooltip import ToolTip

            ToolTip(self._noise_tip_icon, text=t("tip_noise"))

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
            self.btn_save_location.configure(
                text=(
                    t("btn_cancel_save_location")
                    if self.is_selecting_saved_location
                    else t("btn_save_location")
                )
            )
        if hasattr(self, "btn_save_current_position"):
            self.btn_save_current_position.configure(text=t("btn_save_current_position"))
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
        if hasattr(self, "open_logs_btn"):
            self.open_logs_btn.configure(text=t("btn_open_logs"))

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
        self.after(1000, self._check_dev_mode)

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
            self._confirm_save_selected_location(lat, lon)
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
        num_points = len(self.route_points)
        total_distance = 0

        # Note: We need a distance calculator helper or use RouteWalker's static one if we made it static
        # But in new structure RouteWalker._haversine_distance is internal.
        # Let's add a helper here or make it static in RouteWalker?
        # RouteWalker in new core has _haversine_distance as private method.
        # I'll duplicate the simple math here to avoid tight coupling or access privates.

        def haversine(lat1, lon1, lat2, lon2):
            import math

            R = 6371000  # meters
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = (
                math.sin(dphi / 2) ** 2
                + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            )
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        for i in range(len(self.route_points) - 1):
            p1 = self.route_points[i]
            p2 = self.route_points[i + 1]
            total_distance += haversine(
                p1.latitude, p1.longitude, p2.latitude, p2.longitude
            )

        if total_distance >= 1000:
            distance_str = f"{total_distance / 1000:.2f} km"
        else:
            distance_str = f"{total_distance:.0f} m"

        self.route_info.configure(text=t("route_info", points=num_points, distance=distance_str))

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

    def _apply_routing_settings(self):
        """Update routing service config."""
        self.routing_service = RoutingService(provider="osrm")

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
            lat = float(self.lat_entry.get().strip())
            lon = float(self.lon_entry.get().strip())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            return lat, lon
        except ValueError:
            messagebox.showerror(
                t("dialog_invalid_coords_title"),
                t("dialog_invalid_coords_msg"),
            )
            return None

    def _get_place_name(self, lat: float, lon: float) -> str:
        name = self.place_name_entry.get().strip()
        if name:
            return name
        return t("default_location_name", lat=f"{lat:.4f}", lon=f"{lon:.4f}")

    def _save_location(self, lat: float, lon: float):
        name = self._get_place_name(lat, lon)
        self.location_storage.save(name, lat, lon)
        self.place_name_entry.delete(0, "end")
        self._refresh_saved_locations()
        self.status_label.configure(text=t("status_location_saved", name=name))

    def _toggle_saved_location_selection(self):
        if self.is_selecting_saved_location:
            self.status_label.configure(text=t("status_location_save_cancelled"))
            self._set_saved_location_selection_mode(False)
        else:
            self._set_saved_location_selection_mode(True)

    def _set_saved_location_selection_mode(self, enabled: bool):
        self.is_selecting_saved_location = enabled
        if enabled:
            self.status_label.configure(text=t("status_select_saved_location"))
            if hasattr(self, "btn_save_location"):
                self.btn_save_location.configure(text=t("btn_cancel_save_location"))
            return

        if self.save_location_preview_marker:
            self.save_location_preview_marker.delete()
            self.save_location_preview_marker = None
        if hasattr(self, "btn_save_location"):
            self.btn_save_location.configure(text=t("btn_save_location"))

    def _confirm_save_selected_location(self, lat: float, lon: float):
        if self.save_location_preview_marker:
            self.save_location_preview_marker.delete()

        self.save_location_preview_marker = self.map_widget.set_marker(
            lat,
            lon,
            text=t("marker_save_place"),
            marker_color_circle="#10b981",
            marker_color_outside="#047857",
        )

        should_save = messagebox.askyesno(
            t("dialog_confirm_save_location_title"),
            t(
                "dialog_confirm_save_location_msg",
                lat=f"{lat:.6f}",
                lon=f"{lon:.6f}",
            ),
            icon="question",
        )

        if should_save:
            self._save_location(lat, lon)
        else:
            self.status_label.configure(text=t("status_location_save_cancelled"))

        self._set_saved_location_selection_mode(False)

    def _save_current_simulated_location(self):
        if self.current_simulated_position is None:
            self.status_label.configure(text=t("status_no_current_position"))
            messagebox.showinfo(
                t("dialog_current_position_required_title"),
                t("dialog_current_position_required_msg"),
            )
            return
        lat, lon = self.current_simulated_position
        if not messagebox.askyesno(
            t("dialog_confirm_save_location_title"),
            t(
                "dialog_confirm_save_current_location_msg",
                lat=f"{lat:.6f}",
                lon=f"{lon:.6f}",
            ),
            icon="question",
        ):
            self.status_label.configure(text=t("status_location_save_cancelled"))
            return
        self._save_location(lat, lon)

    def _save_current_location(self):
        coords = self._get_entered_coordinates()
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

    def _load_route_dialog(self):
        routes = self.route_storage.list_all()
        if not routes:
            messagebox.showinfo(t("dialog_info_title"), t("dialog_no_routes_msg"))
            return

        # Use CTkToplevel to keep dark-theme text/background readable.
        import tkinter as tk

        top = ctk.CTkToplevel(self)
        top.title(t("dialog_load_title"))
        top.geometry("460x340")
        top.configure(fg_color="#0f172a")
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(
            top,
            text=t("dialog_load_msg"),
            text_color="#e5e7eb",
            justify="left",
            wraplength=420,
        ).pack(padx=10, pady=(10, 6), anchor="w")

        listbox = tk.Listbox(
            top,
            font=("Segoe UI", 12),
            bg="#020617",
            fg="#f8fafc",
            selectbackground="#0ea5e9",
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground="#1e293b",
            highlightcolor="#38bdf8",
            relief="flat",
            borderwidth=0,
            activestyle="none",
        )
        listbox.pack(fill="both", expand=True, padx=10, pady=6)

        for r in routes:
            listbox.insert(
                "end", f"{r.name} ({r.point_count} pts) - {r.created_at[:16]}"
            )

        def on_load():
            sel = listbox.curselection()
            if not sel:
                return
            route_id = routes[sel[0]].id
            name, points = self.route_storage.load(route_id)
            self._load_route_points(name, points)
            top.destroy()

        def on_delete(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if messagebox.askyesno(
                t("dialog_delete_title"),
                t("dialog_delete_confirm_msg", name=routes[idx].name),
            ):
                self.route_storage.delete(routes[idx].id)
                listbox.delete(idx)
                routes.pop(idx)
                self._refresh_saved_routes()

        btn_frm = ctk.CTkFrame(top, fg_color="transparent")
        btn_frm.pack(pady=10)
        ctk.CTkButton(btn_frm, text=t("btn_load_route"), command=on_load).pack(
            side="left", padx=5
        )
        ctk.CTkButton(btn_frm, text=t("btn_delete_route"), command=on_delete).pack(
            side="left", padx=5
        )

        listbox.bind("<Double-Button-1>", lambda e: on_load())
        listbox.bind("<Button-3>", on_delete)

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
        self.focus_set()

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
        self.start_walk_btn.configure(state="normal")
        self.pause_walk_btn.configure(state="disabled")
        self.stop_walk_btn.configure(state="disabled")

    def _set_manual_location(self):
        """Set location from manual coordinates."""
        try:
            lat = float(self.lat_entry.get().strip())
            lon = float(self.lon_entry.get().strip())

            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError("Invalid coordinate range")

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
            self.status_label.configure(text=t("status_location_cleared"))
            if self.current_position_marker:
                self.current_position_marker.delete()
                self.current_position_marker = None
        else:
            self.status_label.configure(text=t("status_location_clear_failed"))

    def _open_logs_folder(self):
        """Open the log directory for troubleshooting."""
        try:
            log_dir = str(get_log_dir())
            if sys.platform == "win32":
                os.startfile(log_dir)
            else:
                import subprocess

                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, log_dir])
            self.status_label.configure(text=t("status_opened_logs", path=log_dir))
        except Exception as e:
            logger.error("Failed to open log folder: %s", e, exc_info=True)
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

    def _search_location(self, event=None):
        """Search for a location using Nominatim geocoding."""
        query = self.search_entry.get().strip()
        if not query:
            return

        self.status_label.configure(text=f"Searching for: {query}...")
        self.update()

        def search():
            try:
                import requests

                # Use Nominatim with proper User-Agent (required by OSM)
                version = update_checker.get_current_version()
                headers = {"User-Agent": f"iFakeGPS/{version} (iOS Location Simulator)"}
                params = {"q": query, "format": "json", "limit": 1}

                response = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    headers=headers,
                    params=params,
                    timeout=10,
                )

                if response.status_code == 200:
                    results = response.json()
                    if results:
                        lat = float(results[0]["lat"])
                        lon = float(results[0]["lon"])
                        display_name = results[0].get("display_name", query)

                        # Update map on main thread
                        self.after(
                            0, lambda: self._on_search_result(lat, lon, display_name)
                        )
                    else:
                        self.after(
                            0,
                            lambda: self.status_label.configure(
                                text=f"Location not found: {query}"
                            ),
                        )
                else:
                    self.after(
                        0,
                        lambda: self.status_label.configure(
                            text=f"Search failed: HTTP {response.status_code}"
                        ),
                    )

            except Exception as e:
                logger.error(f"Search error: {e}")
                self.after(
                    0,
                    lambda: self.status_label.configure(text=f"Search error: {query}"),
                )

        threading.Thread(target=search, daemon=True).start()

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
                ),
            )

        threading.Thread(target=run_check, daemon=True).start()

    def _show_update_prompt(
        self,
        current_version: str,
        latest_version: str,
        release_url: str,
        changelog: str,
    ):
        """Show update prompt with latest changelog and release link."""
        message = t(
            "dialog_update_available_msg",
            current=current_version,
            latest=latest_version,
            url=release_url,
            changelog=changelog or t("dialog_update_changelog_empty"),
        )
        should_open = messagebox.askyesno(
            t("dialog_update_available_title"),
            message,
        )
        if should_open:
            webbrowser.open(release_url)

    def _on_search_result(self, lat: float, lon: float, display_name: str):
        """Handle search result on main thread."""
        self.map_widget.set_position(lat, lon)
        self.map_widget.set_zoom(15)
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, f"{lat:.6f}")
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, f"{lon:.6f}")

        # Truncate display name if too long
        if len(display_name) > 50:
            display_name = display_name[:47] + "..."
        self.status_label.configure(text=f"📍 {display_name}")

    def _change_map_type(self, map_type: str):
        """Change the map tile source."""
        if map_type == "OpenStreetMap":
            self.map_widget.set_tile_server(
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            )
        elif map_type == "Google normal":
            self.map_widget.set_tile_server(
                "https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga",
                max_zoom=22,
            )
        elif map_type == "Google satellite":
            self.map_widget.set_tile_server(
                "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
                max_zoom=22,
            )

    def _on_close(self):
        """Handle window close."""
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
