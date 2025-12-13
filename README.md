# iFakeGPS 📍

> **🌐 [繁體中文版本](docs/README_ZHTW.md)**

A powerful GUI application for simulating GPS location on iOS devices (iOS 17+).

- **Teleport** your device's GPS to any location with a single click
- **Walk routes** by creating waypoints with realistic movement
- **Search locations** by name or address

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-green.svg)
![iOS](https://img.shields.io/badge/iOS-17--26.2-orange.svg)

---

## 📥 Download & Run

**Pre-built Windows executable available!** No Python installation required.

👉 **[Download from GitHub Releases](https://github.com/user/ifakegps/releases/latest)**

### Quick Start

1. **Download** `iFakeGPS.exe` from releases
2. **Enable Developer Mode** on your iOS device (Settings > Privacy & Security > Developer Mode)
3. **Connect** your iOS device via USB
4. **Run** `iFakeGPS.exe` (click "Yes" for admin prompt)
5. **Select** your device from the list and start spoofing!

> **That's it!** The app handles everything else automatically, including the iOS 17+ tunnel service.

---

## ✨ Features

### 🎯 Single Point Mode
Click anywhere on the map to instantly teleport your device's GPS location.

### 🚶 Route Walking Mode
- Click multiple points to create a walking route
- Adjust walking speed (1-50 km/h)
- Add speed noise for realistic movement
- Loop mode for continuous walking

### � Location Search
Search for any location by name and set it as your GPS position.

---

## � Troubleshooting

### Device Not Found
1. Ensure Developer Mode is enabled on your iOS device
2. Trust the computer when prompted on your device
3. Try reconnecting the USB cable
4. Wait a few seconds for device discovery

### Location Not Changing
1. Close and reopen location-dependent apps
2. Some apps cache location data - restart them

### Connection Issues (iOS 17+)
The app automatically manages the tunnel service. If you have issues:
1. Make sure you're running as Administrator
2. Check Windows Firewall allows Python/iFakeGPS
3. Ensure IPv6 is enabled on your system

---

## 👨‍💻 For Developers

<details>
<summary>Click to expand development setup</summary>

### Installation

```bash
# Clone the repository
git clone https://github.com/user/ifakegps.git
cd ifakegps

# Using uv (recommended)
uv sync

# Or using pip
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Running from Source

```bash
# Using uv
uv run python ifakegps.py

# Or directly (requires admin for iOS 17+)
python ifakegps.py
```

### Manual Tunnel Setup (Advanced)

For iOS 17+, if you need to run the tunnel separately:

```powershell
# Run as Administrator
python -m pymobiledevice3 remote tunneld
```

> **Note:** This is usually NOT needed as the app handles it automatically.

### Developer Disk Image (iOS 14-16 only)

For iOS 14-16, you may need to mount the developer disk image:

```bash
pymobiledevice3 mounter auto-mount
```

> **Note:** iOS 17+ does NOT require this step.

### Building Windows Executable

```bash
# Using batch file
pack.bat

# Or using Python
python pack.py
```

Output: `dist/iFakeGPS.exe` (auto-requests admin privileges)

</details>

---

## ⚖️ Legal Disclaimer

This tool is for **development and testing purposes only**. Location spoofing may violate app Terms of Service. Use responsibly.

---

## 🙏 Credits

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - iOS device communication
- [tkintermapview](https://github.com/TomSchimansky/TkinterMapView) - Interactive map widget
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI framework
