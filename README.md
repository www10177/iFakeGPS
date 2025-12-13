# iFakeGPS 📍

> **🌐 [繁體中文版本](docs/README_ZHTW.md)**

A powerful GUI application for simulating GPS location on iOS devices (iOS 17+) using `pymobiledevice3`. This application allows you to:

- **Teleport** your device's GPS to any location on Earth with a single click
- **Walk routes** by creating waypoints and simulating realistic movement
- **Search locations** by name or address
- **Fine-tune** walking speed with noise for realistic simulation

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green.svg)
![iOS](https://img.shields.io/badge/iOS-14.0--18.x-orange.svg)

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Features](#features)
5. [Build Windows Executable](#build-windows-executable)
6. [Troubleshooting](#troubleshooting)
7. [Technical Details](#technical-details)
8. [Legal Disclaimer](#legal-disclaimer)

---

## System Requirements

### Software
- **Python 3.9+** (Recommended: Python 3.11 or newer)
- **Windows 10/11**, macOS, or Linux
- **iTunes** (Windows) or **Apple Mobile Device Support**

### Hardware
- USB cable for device connection (Apple-certified recommended)
- Internet connection (for map tiles)

### iOS Device
- **iOS 14.0+** supported
- **iOS 17+** requires special tunnel setup (explained below)
- **Developer Mode** must be enabled (iOS 16+)

---

## Installation

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager.

```bash
# Install uv if not already installed
pip install uv

# Clone and enter project
cd iFakeGPS

# Sync dependencies
uv sync
```

### Using pip

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Enable Developer Mode on iOS Device (iOS 16+)

1. Go to **Settings** > **Privacy & Security**
2. Scroll down and tap **Developer Mode**
3. Enable it and restart your device

Or use the command line:
```bash
pymobiledevice3 amfi enable-developer-mode
```

---

## Quick Start

### For iOS 17+ Devices

iOS 17 introduced a new communication mechanism that requires running a tunnel service with **administrator privileges**.

#### Step 1: Start the Tunnel Service

**Option A: Using the provided batch file (Recommended)**
1. Double-click `start_tunneld.bat`
2. Click "Yes" when prompted for administrator access
3. Keep this window open!

**Option B: Manual command**
```powershell
# Run PowerShell as Administrator
python -m pymobiledevice3 remote tunneld
```

#### Step 2: Mount Developer Disk Image (First Time Only)

```bash
pymobiledevice3 mounter auto-mount
```

#### Step 3: Run iFakeGPS

**Option A: Using the provided batch file (Recommended)**
1. Double-click `run.bat`
2. The application will auto-elevate to administrator

**Option B: Manual command**
```bash
# With uv
uv run python ifakegps.py

# Or directly
python ifakegps.py
```

#### Step 4: Connect Your Device

1. Your device should appear in the device list automatically
2. Click on the device to connect
3. The status will change to "🟢 Connected"

---

### For iOS < 17 Devices

1. Connect your device via USB
2. Run `python ifakegps.py`
3. Click **"USB Connect"** or select your device from the list

---

## Features

### 🎯 Single Point Mode (Default)

1. Select **"Single Point"** mode in the sidebar
2. Click any point on the map
3. Your device's GPS will instantly teleport to that location
4. The coordinates are displayed in the sidebar

### 🚶 Route Walking Mode

1. Select **"Route Mode"** in the sidebar
2. Click multiple points on the map to create a walking route
3. A path line will connect your waypoints
4. **Right-click** on any marker to remove it

#### Walking Controls:
- **Speed Slider (1-50 km/h)**: Adjust walking speed
- **Noise Slider (0-50%)**: Add random speed variation for realistic movement
- **▶ Start**: Begin walking the route
- **⏸ Pause**: Pause walking (retains position)
- **⏹ Stop**: Stop walking and reset
- **Loop**: Enable continuous loop walking
- **🗑 Clear Route**: Remove all waypoints

### 📍 Manual Coordinates

1. Enter latitude and longitude in the sidebar fields
2. Click **"📍 Set Location"**
3. The map will center on the location and send it to the device

### 🔍 Location Search

1. Type a location name in the search bar (e.g., "Tokyo Tower")
2. Press **Enter** or click **"🔍 Search"**
3. The map will center on that location
4. Click to set it as your GPS location

### 🔄 Clear Simulated Location

Click **"🔄 Clear Simulated Location"** to restore the device's real GPS.

---

## Build Windows Executable

To create a standalone Windows executable (.exe) that requires administrator privileges:

**Option 1: Using batch file**
```bash
pack.bat
```

**Option 2: Using Python script**
```bash
python pack.py
```

**Option 3: Using uv**
```bash
uv run python pack.py
```

The output executable will be created at `dist/iFakeGPS.exe` and will automatically request administrator privileges when launched.

---

## Troubleshooting

### "Connection Failed" Error

1. **Check USB connection** - Use an Apple-certified cable
2. **Trust the computer** - Tap "Trust" on your iOS device when prompted
3. **Check Developer Mode** - Must be enabled for iOS 16+
4. **Install iTunes** (Windows) - Required for device drivers
5. **Restart usbmuxd** (macOS/Linux): `sudo killall usbmuxd`

### iOS 17+ Tunnel Issues

1. **Run as Administrator** - Tunnels require elevated privileges
2. **Keep tunnel running** - Don't close the tunnel terminal
3. **Check firewall** - Allow Python through Windows Firewall
4. **IPv6 support** - Ensure your system supports IPv6

### Location Not Changing

1. **Close location-dependent apps** - GPS simulation works best when apps are freshly launched
2. **Mount Developer Disk Image** - Run `pymobiledevice3 mounter auto-mount`
3. **Restart the target app** - Some apps cache location data

### Map Not Loading

1. **Internet connection** - Required for map tiles
2. **Firewall/Proxy** - Allow access to OpenStreetMap/Google servers

### Device Not Found

1. Ensure tunneld is running with admin privileges
2. Check USB cable connection
3. Unlock your device and trust the computer
4. Wait a few seconds for device discovery

---

## Technical Details

### How It Works

iFakeGPS uses `pymobiledevice3` to communicate with iOS devices:

1. **iOS < 17**: Direct USB communication via `usbmuxd`
2. **iOS 17+**: RSD (Remote Service Discovery) tunnel using CoreDevice framework

The location simulation uses the **DeveloperDiskImage** services:
- `DvtSecureSocketProxyService` - Secure communication channel
- `LocationSimulation` - GPS location override

### Walking Algorithm

The route walker:
1. Interpolates between waypoints using linear interpolation
2. Calculates realistic timing based on distance and speed
3. Updates device location every 0.5 seconds
4. Uses Haversine formula for accurate distance calculation
5. Applies optional speed noise for realistic movement

### Key Components

| Component | Description |
|-----------|-------------|
| `TunneldManager` | Manages the tunneld service for iOS 17+ |
| `DeviceManager` | Handles device connection and location simulation |
| `RouteWalker` | Manages route walking with interpolation |
| `iFakeGPSApp` | Main GUI application |

---

## Legal Disclaimer

⚠️ **This tool is intended for development and testing purposes only.**

Using location spoofing:
- May violate Terms of Service of apps
- May be illegal in some jurisdictions
- Should not be used for fraud or deception

**Use responsibly and at your own risk.**

---

## Credits

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - iOS device communication
- [tkintermapview](https://github.com/TomSchimansky/TkinterMapView) - Interactive map widget
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI framework

---

## License

MIT License - Feel free to use and modify.
