# iFakeGPS 📍

A powerful GUI application for simulating GPS location on iOS devices using `pymobiledevice3`. Fully supports **iOS 17+** (including iOS 18/26) via the RSD tunnel mechanism.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green.svg)
![iOS](https://img.shields.io/badge/iOS-14.0--18.x-orange.svg)

## ✨ Features

### 🎯 Single Point Mode
- Click anywhere on the interactive map to instantly teleport your device's GPS location
- Manual coordinate entry for precise positioning
- Search for locations by name or address

### 🚶 Route Walking Mode
- Click multiple points on the map to create a walking route
- Visual path display connecting all waypoints
- Customizable walking speed (1-50 km/h) with slider
- Start, pause, and stop walking controls
- Loop mode for continuous walking

### 🗺️ Interactive Map
- OpenStreetMap and Google Maps tile support
- Zoom controls
- Location search
- Click-to-place markers
- Real-time position updates

## 📋 Requirements

- **Python 3.9+**
- **iOS 14.0+** device (iOS 17+ requires special setup)
- **Windows/macOS/Linux** computer
- USB cable for connection
- **Developer Mode** enabled on iOS device (iOS 16+)

## 🚀 Installation

### 1. Clone or Download

```bash
cd e:\iFakeGPS
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Enable Developer Mode (iOS 16+)

On your iOS device:
1. Go to **Settings** > **Privacy & Security**
2. Scroll down and tap **Developer Mode**
3. Enable it and restart your device

Or use pymobiledevice3:
```bash
pymobiledevice3 amfi enable-developer-mode
```

## 📱 Usage

### For iOS 17+ (Requires RSD Tunnel)

iOS 17 introduced a new communication mechanism that requires running a tunnel service.

#### Step 1: Start the Tunnel (Admin/Root Required)

**On Windows (PowerShell as Administrator):**
```powershell
python -m pymobiledevice3 remote start-tunnel
```

**On macOS/Linux:**
```bash
sudo python3 -m pymobiledevice3 remote start-tunnel
```

The output will show something like:
```
Tunnel created for: iPhone
UDID: 00008030-001234567890802E
RSD Address: fd75:xxxx:xxxx::1
RSD Port: 58763
```

**Keep this terminal running!**

#### Step 2: Mount Developer Disk Image (First Time Only)

In a new terminal:
```bash
pymobiledevice3 mounter auto-mount
```

#### Step 3: Run iFakeGPS

```bash
python ifakegps.py
```

#### Step 4: Connect in the App

1. Copy the **RSD Address** (e.g., `fd75:xxxx:xxxx::1`) to the "RSD Host" field
2. Copy the **RSD Port** (e.g., `58763`) to the "RSD Port" field
3. Click **"Connect (RSD)"**

---

### For iOS < 17 (Direct USB)

Simply connect your device via USB and:

1. Run `python ifakegps.py`
2. Click **"USB Connect"**

---

## 🎮 How to Use

### Single Point Mode (Default)
1. Select "Single Point" mode in the sidebar
2. Click any point on the map
3. Your device's GPS will instantly move to that location

### Route Walking Mode
1. Select "Route Mode" in the sidebar
2. Click multiple points on the map to create a route
3. Adjust walking speed with the slider (1-50 km/h)
4. Click **"▶ Start"** to begin walking
5. Use **"⏸ Pause"** or **"⏹ Stop"** to control

### Manual Coordinates
1. Enter latitude and longitude in the sidebar
2. Click **"📍 Set Location"**

### Search Location
1. Type a location name in the search bar
2. Press Enter or click **"🔍 Search"**
3. The map will center on that location

---

## 🔧 Troubleshooting

### "Connection Failed" Error

1. **Check USB connection** - Use an Apple-certified cable
2. **Trust the computer** - Tap "Trust" on your iOS device when prompted
3. **Check Developer Mode** - Must be enabled for iOS 16+
4. **Restart usbmuxd** (macOS/Linux): `sudo killall usbmuxd`
5. **Install iTunes/Apple Mobile Device Support** (Windows)

### iOS 17+ Tunnel Issues

1. **Run as admin/root** - Tunnels require elevated privileges
2. **Keep tunnel running** - Don't close the tunnel terminal
3. **Check firewall** - Allow Python through Windows Firewall
4. **IPv6 support** - Ensure your system supports IPv6

### Location Not Changing

1. **Close location-dependent apps** - GPS simulation works best when apps are freshly launched
2. **Developer Disk Image** - Run `pymobiledevice3 mounter auto-mount`
3. **Restart the target app** - Some apps cache location data

### Map Not Loading

1. **Internet connection** - Required for map tiles
2. **Firewall/Proxy** - Allow access to OpenStreetMap/Google servers

---

## 📚 Technical Details

### How It Works

iFakeGPS uses `pymobiledevice3` to communicate with iOS devices:

1. **iOS < 17**: Direct USB communication via `usbmuxd`
2. **iOS 17+**: RSD (Remote Service Discovery) tunnel using CoreDevice framework

The location simulation uses the **DeveloperDiskImage** services:
- `DvtSecureSocketProxyService` - Secure communication channel
- `LocationSimulation` - GPS location override

### Walking Algorithm

The route walker:
1. Interpolates between waypoints
2. Calculates realistic timing based on distance and speed
3. Updates device location every 0.5 seconds
4. Uses Haversine formula for accurate distance calculation

---

## ⚖️ Legal Disclaimer

This tool is intended for **development and testing purposes only**. Using location spoofing:
- May violate Terms of Service of apps
- May be illegal in some jurisdictions
- Should not be used for fraud or deception

Use responsibly and at your own risk.

---

## 🙏 Credits

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - iOS device communication
- [tkintermapview](https://github.com/TomSchimansky/TkinterMapView) - Interactive map widget
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI framework

---

## 📄 License

MIT License - Feel free to use and modify.
