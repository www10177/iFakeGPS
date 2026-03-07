import os
import sys
import threading
import time
from enum import Enum
from tkinter import messagebox
from typing import List, Optional, Tuple

import customtkinter as ctk

from src.core.device_manager import DeviceManager
from src.core.models import DeviceInfo, RoutePoint
from src.core.route_walker import RouteWalker
from src.core.tunnel_manager import TunneldManager
from src.ui.caching_map_view import CachingTileMapView
from src.ui.i18n import LANGUAGES, get_lang, set_lang, t
from src.ui.tooltip import add_tooltip_button
from src.utils.logger import logger


class AppMode(Enum):
    SINGLE_POINT = "single"
    ROUTE = "route"


class iFakeGPSApp(ctk.CTk):
    """
    Main application window for iFakeGPS.
    """

    def __init__(self):
        super().__init__()

        # Configure window
        self.title(t("app_title"))
        self.geometry("1400x900")
        self.minsize(1200, 700)

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
                self.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Failed to set icon: {e}")

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
            update_callback=self._on_position_update,
            completion_callback=self._on_walk_complete,
        )
        # Note: RouteWalker constructor signature changed in our new core implementation
        # Reviewing core/route_walker.py: __init__(self, device_manager, update_callback, completion_callback=None)
        # So we pass callbacks in constructor now, simplified from property setters.

        # State
        self.mode = AppMode.SINGLE_POINT
        self.route_points: list[RoutePoint] = []
        self.route_path = None  # Map path object
        self.current_position_marker = None
        self.discovered_devices: List[DeviceInfo] = []

        # Build UI
        self._create_ui()

        # Bind events
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-start tunneld and discover devices on startup
        self.after(500, self._start_tunneld_and_discover)

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

    def _create_ui(self):
        """Create the main UI layout."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create left sidebar
        self._create_sidebar()

        # Create main map area
        self._create_map_area()

        # Create bottom status bar
        self._create_status_bar()

        # Set initial visibility after all components are created
        self._on_mode_change()

    def _create_sidebar(self):
        """Create the left sidebar with controls."""
        sidebar = ctk.CTkFrame(self, width=350, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_rowconfigure(10, weight=1)

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
        self.disconnect_btn.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Mode selection
        mode_frame = ctk.CTkFrame(sidebar)
        mode_frame.grid(row=5, column=0, padx=15, pady=10, sticky="ew")

        ctk.CTkLabel(
            mode_frame, text=t("mode_label"), font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.mode_var = ctk.StringVar(value="single")

        single_radio = ctk.CTkRadioButton(
            mode_frame,
            text=t("mode_single"),
            variable=self.mode_var,
            value="single",
            command=self._on_mode_change,
        )
        single_radio.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        route_radio = ctk.CTkRadioButton(
            mode_frame,
            text=t("mode_route"),
            variable=self.mode_var,
            value="route",
            command=self._on_mode_change,
        )
        route_radio.grid(row=2, column=0, padx=20, pady=(5, 10), sticky="w")

        # Route controls
        self.route_frame = ctk.CTkFrame(sidebar)
        self.route_frame.grid(row=6, column=0, padx=15, pady=10, sticky="ew")

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

        self.speed_entry_var = ctk.StringVar(value="5.0")
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
            to=1000,
            number_of_steps=1000,
            command=self._on_speed_slider_change,
        )
        self.speed_slider.grid(
            row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.speed_slider.set(5)

        # Speed noise slider — label row with tooltip icon
        noise_label_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        noise_label_frame.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.lbl_noise = ctk.CTkLabel(noise_label_frame, text=t("noise_label"))
        self.lbl_noise.pack(side="left")

        self._noise_tip_icon = add_tooltip_button(
            noise_label_frame, text=t("tip_noise")
        )
        self._noise_tip_icon.pack(side="left", padx=(2, 0))

        self.noise_value_label = ctk.CTkLabel(self.route_frame, text="0%")
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
        self.noise_slider.set(0)

        self.route_frame.grid_columnconfigure(0, weight=1)
        self.route_frame.grid_columnconfigure(1, weight=1)

        # Route info
        self.route_info = ctk.CTkLabel(
            self.route_frame,
            text="Points: 0 | Distance: 0 m",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.route_info.grid(row=5, column=0, columnspan=2, padx=10, pady=5)

        # Route buttons
        route_btn_frame = ctk.CTkFrame(self.route_frame, fg_color="transparent")
        route_btn_frame.grid(
            row=6, column=0, columnspan=2, padx=10, pady=10, sticky="ew"
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
        self.start_walk_btn.pack(side="left", expand=True, fill="x", padx=2)

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
            row=7, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w"
        )

        # Clear route button
        self.clear_route_btn = ctk.CTkButton(
            self.route_frame,
            text=t("btn_clear_route"),
            command=self._clear_route,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.clear_route_btn.grid(
            row=8, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew"
        )

        # Coordinates section
        self.coord_frame = ctk.CTkFrame(sidebar)
        self.coord_frame.grid(row=7, column=0, padx=15, pady=10, sticky="ew")

        self.lbl_manual = ctk.CTkLabel(
            self.coord_frame,
            text=t("manual_coords"),
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.lbl_manual.grid(
            row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w"
        )

        self.lbl_lat = ctk.CTkLabel(self.coord_frame, text=t("label_lat"))
        self.lbl_lat.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.lat_entry = ctk.CTkEntry(self.coord_frame, placeholder_text="37.7749")
        self.lat_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.lbl_lon = ctk.CTkLabel(self.coord_frame, text=t("label_lon"))
        self.lbl_lon.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.lon_entry = ctk.CTkEntry(self.coord_frame, placeholder_text="-122.4194")
        self.lon_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

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

        # Clear location button
        self.clear_location_btn = ctk.CTkButton(
            self.coord_frame,
            text=t("btn_clear_location"),
            command=self._clear_location,
            fg_color="#6b7280",
            hover_color="#4b5563",
        )
        self.clear_location_btn.grid(
            row=4, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew"
        )

        # Spacer
        spacer = ctk.CTkLabel(sidebar, text="")
        spacer.grid(row=10, column=0, sticky="nsew")

        # Info label at bottom
        info_label = ctk.CTkLabel(
            sidebar,
            text=t("info_tunneld"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        )
        self.info_label = info_label
        info_label.grid(row=11, column=0, padx=15, pady=(5, 5), sticky="sw")

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

    def _create_map_area(self):
        """Create the main map area."""
        map_frame = ctk.CTkFrame(self, corner_radius=10)
        map_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(0, weight=1)

        # Set up a dedicated directory in the user's AppData for database caching
        import os

        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        cache_dir = os.path.join(local_app_data, "iFakeGPS", "cache")
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, "map_cache.db")

        # Create map widget using write-through caching subclass.
        # Tiles downloaded from the network are automatically saved to the local SQLite DB
        # so subsequent launches load them instantly without re-downloading.
        self.map_widget = CachingTileMapView(
            map_frame,
            corner_radius=10,
            use_database_only=False,
            db_path=db_path,
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

        # Map controls (Simplified as per user request)
        # Search, Zoom, and Type selection removed.
        map_controls = ctk.CTkFrame(map_frame, fg_color="transparent")
        # map_controls.grid(row=1, column=0, padx=10, pady=10, sticky="ew") # Nothing to show currently

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

    def _update_ui_text(self):
        """Refresh all visible widget text to reflect the current language."""
        # Window title
        self.title(t("app_title"))

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
        # Note: radio buttons keep internal values but we update display text
        # This is tricky with CTkRadioButton — we'd need to recreate them.
        # For now, static labels that we CAN update:
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

        # Info label
        if hasattr(self, "info_label"):
            self.info_label.configure(text=t("info_tunneld"))

        # Language label
        if hasattr(self, "lang_label"):
            self.lang_label.configure(text=t("lang_label"))

        # Status bar
        if hasattr(self, "status_label"):
            self.status_label.configure(text=t("status_ready"))

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

    def _update_device_list(self, devices: List[DeviceInfo]):
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
                device_btn = ctk.CTkButton(
                    self.device_listbox_frame,
                    text=device.display_name(),
                    command=lambda d=device: self._connect_to_device(d),
                    fg_color="#1e3a5f"
                    if not self._is_device_connected(device)
                    else "#10b981",
                    hover_color="#2563eb",
                    anchor="w",
                    height=40,
                )
                device_btn.grid(row=i, column=0, padx=5, pady=2, sticky="ew")

            self.status_label.configure(
                text=t("status_found_devices", count=len(devices))
            )

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
        self.mode = (
            AppMode.SINGLE_POINT if self.mode_var.get() == "single" else AppMode.ROUTE
        )

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
            self.status_label.configure(text=t("status_route_mode"))

    def _on_map_click(self, coords):
        """Handle map click."""
        lat, lon = coords

        # Update coordinate display
        self.coords_label.configure(text=f"Clicked: {lat:.6f}, {lon:.6f}")
        self.lat_entry.delete(0, "end")
        self.lat_entry.insert(0, f"{lat:.6f}")
        self.lon_entry.delete(0, "end")
        self.lon_entry.insert(0, f"{lon:.6f}")

        if self.mode == AppMode.SINGLE_POINT:
            # Single point mode - show confirmation before teleporting
            self._pending_teleport = (lat, lon)
            self._show_teleport_confirmation(lat, lon)
        else:
            # Route mode - add waypoint
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
            text=f"Added point {len(self.route_points)} at {lat:.6f}, {lon:.6f} (right-click to remove)"
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
                text=f"Removed point. {len(self.route_points)} points remaining."
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

        self.route_info.configure(
            text=f"Points: {num_points} | Distance: {distance_str}"
        )

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

    def _on_speed_entry_change(self, event=None):
        """Handle speed entry change."""
        try:
            val = float(self.speed_entry_var.get())
            if val < 0:
                val = 0.0
            if val > 1000:
                val = 1000.0
            self.speed_slider.set(val)
            self.route_walker.set_speed(val)
            # Update UI to clean formatting
            self.speed_entry_var.set(f"{val:.1f}")
        except ValueError:
            # Revert to slider value if invalid input
            self.speed_entry_var.set(f"{self.speed_slider.get():.1f}")

        # Remove focus from entry
        self.focus_set()

    def _on_noise_change(self, value):
        """Handle noise slider change."""
        noise_percent = float(value)
        self.noise_value_label.configure(text=f"{noise_percent:.0f}%")
        self.route_walker.set_speed_noise(noise_percent)

    def _start_walking(self):
        """Start or resume walking the route."""
        if not self.device_manager.connected:
            messagebox.showwarning(
                t("dialog_not_connected_title"), t("dialog_not_connected_msg")
            )
            return

        if len(self.route_points) < 2:
            messagebox.showwarning(
                t("dialog_invalid_route_title"), t("dialog_invalid_route_msg")
            )
            return

        # If currently paused, resume from the saved position
        if self.route_walker.is_walking and self.route_walker.is_paused:
            self.route_walker.resume()
            self.status_label.configure(text=t("status_resumed"))
            return

        # Otherwise, start fresh from the beginning
        self.route_walker.set_route(self.route_points)
        self.route_walker.set_loop(self.loop_var.get())
        self.route_walker.start()
        self.status_label.configure(text=t("status_walking"))

    def _pause_walking(self):
        """Pause walking at the current position (can be resumed with ▶)."""
        if self.route_walker.is_walking and not self.route_walker.is_paused:
            self.route_walker.pause()
            self.status_label.configure(text=t("status_paused"))
        elif not self.route_walker.is_walking:
            self.status_label.configure(text=t("status_not_walking"))

    def _stop_walking(self):
        """Stop walking."""
        self.route_walker.stop()

        # Remove current position marker
        if self.current_position_marker:
            self.current_position_marker.delete()
            self.current_position_marker = None

        self.status_label.configure(text=t("status_walk_stopped"))

    def _on_position_update(self, lat: float, lon: float):
        """Called when walking position updates."""

        def update():
            # Update or create position marker
            if self.current_position_marker:
                self.current_position_marker.delete()

            self.current_position_marker = self.map_widget.set_marker(
                lat,
                lon,
                text="🚶",
                marker_color_circle="#10b981",
                marker_color_outside="#059669",
            )

            self.coords_label.configure(text=f"Walking: {lat:.6f}, {lon:.6f}")

        self.after(0, update)

    def _on_walk_complete(self):
        """Called when walking is complete."""

        def update():
            self.status_label.configure(text=t("status_walk_complete"))

        self.after(0, update)

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

        except ValueError as e:
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
            self.status_label.configure(text=t("status_location_cleared"))
            if self.current_position_marker:
                self.current_position_marker.delete()
                self.current_position_marker = None
        else:
            self.status_label.configure(text=t("status_location_clear_failed"))

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
                headers = {"User-Agent": "iFakeGPS/1.0 (iOS Location Simulator)"}
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
