# iFakeGPS 📍

> **🌐 [English Version](../README.md)**

## iOS GPS 位置模擬器 - 使用者指南

一款功能強大的圖形化介面應用程式，使用 `pymobiledevice3` 在 iOS 裝置上模擬 GPS 位置（支援 iOS 17+）。此應用程式可讓您：

- **瞬間移動** - 點一下即可將裝置的 GPS 位置傳送到地球上的任何地點
- **路線行走** - 建立路徑點並模擬真實的移動軌跡
- **搜尋地點** - 透過名稱或地址搜尋位置
- **微調設定** - 調整行走速度與隨機噪音，讓模擬更逼真

---

## 目錄

1. [系統需求](#系統需求)
2. [安裝步驟](#安裝步驟)
3. [快速開始](#快速開始)
4. [功能說明](#功能說明)
5. [疑難排解](#疑難排解)
6. [技術細節](#技術細節)
7. [法律聲明](#法律聲明)

---

## 系統需求

### 軟體需求
- **Python 3.9+**（建議使用 Python 3.11 或更新版本）
- **Windows 10/11**、macOS 或 Linux
- **iTunes**（Windows）或 **Apple Mobile Device Support**

### 硬體需求
- USB 傳輸線（建議使用 Apple 原廠認證線材）
- 網際網路連線（用於載入地圖圖磚）

### iOS 裝置
- 支援 **iOS 14.0+**
- **iOS 17+** 需要特殊的通道設定（詳見下文）
- 必須啟用**開發者模式**（iOS 16+）

---

## 安裝步驟

### 步驟 1：下載專案

```bash
cd e:\iFakeGPS
```

### 步驟 2：建立虛擬環境（建議）

```bash
python -m venv .venv
```

### 步驟 3：啟用虛擬環境

**Windows：**
```bash
.venv\Scripts\activate
```

**macOS/Linux：**
```bash
source .venv/bin/activate
```

### 步驟 4：安裝相依套件

```bash
pip install -r requirements.txt
```

### 步驟 5：啟用 iOS 裝置的開發者模式（iOS 16+）

1. 前往 **設定** > **隱私權與安全性**
2. 向下滑動並點選**開發者模式**
3. 啟用後重新啟動裝置

或使用命令列：
```bash
pymobiledevice3 amfi enable-developer-mode
```

---

## 快速開始

### iOS 17+ 裝置

iOS 17 引入了新的通訊機制，需要以**系統管理員權限**執行通道服務。

#### 步驟 1：啟動通道服務

**選項 A：使用提供的批次檔（建議）**
1. 雙擊 `start_tunneld.bat`
2. 在提示系統管理員存取權限時點選「是」
3. 保持此視窗開啟！

**選項 B：手動執行命令**
```powershell
# 以系統管理員身分執行 PowerShell
python -m pymobiledevice3 remote tunneld
```

#### 步驟 2：掛載開發者磁碟映像（僅首次需要）

```bash
pymobiledevice3 mounter auto-mount
```

#### 步驟 3：執行 iFakeGPS

**選項 A：使用提供的批次檔（建議）**
1. 雙擊 `run.bat`
2. 應用程式會自動提升為系統管理員權限

**選項 B：手動執行命令**
```bash
python ifakegps.py
```

#### 步驟 4：連接您的裝置

1. 您的裝置應會自動出現在裝置清單中
2. 點選裝置以連接
3. 狀態會變更為「🟢 已連接」

---

### iOS 17 以下的裝置

1. 透過 USB 連接您的裝置
2. 執行 `python ifakegps.py`
3. 點選 **「USB 連接」** 或從清單中選擇您的裝置

---

## 功能說明

### 🎯 單點模式（預設）

1. 在側邊欄選擇 **「Single Point」** 模式
2. 在地圖上點選任意位置
3. 您的裝置 GPS 將立即傳送到該位置
4. 座標會顯示在側邊欄中

### 🚶 路線行走模式

1. 在側邊欄選擇 **「Route Mode」** 模式
2. 在地圖上點選多個點以建立行走路線
3. 路徑線會連接您的路徑點
4. **右鍵點選**任何標記可將其移除

#### 行走控制：
- **速度滑桿（1-50 km/h）**：調整行走速度
- **噪音滑桿（0-50%）**：加入隨機速度變化，讓移動更逼真
- **▶ 開始**：開始行走路線
- **⏸ 暫停**：暫停行走（保留位置）
- **⏹ 停止**：停止行走並重設
- **循環**：啟用持續循環行走
- **🗑 清除路線**：移除所有路徑點

### 📍 手動座標

1. 在側邊欄欄位中輸入緯度和經度
2. 點選 **「📍 Set Location」**
3. 地圖會置中到該位置並將其傳送到裝置

### 🔍 位置搜尋

1. 在搜尋欄中輸入位置名稱（例如：「台北 101」）
2. 按 **Enter** 或點選 **「🔍 Search」**
3. 地圖會置中到該位置
4. 點選以將其設定為您的 GPS 位置

### 🔄 清除模擬位置

點選 **「🔄 Clear Simulated Location」** 以恢復裝置的真實 GPS。

---

## 疑難排解

### 「連線失敗」錯誤

1. **檢查 USB 連接** - 使用 Apple 原廠認證線材
2. **信任此電腦** - 在 iOS 裝置出現提示時點選「信任」
3. **檢查開發者模式** - iOS 16+ 必須啟用
4. **安裝 iTunes**（Windows）- 需要裝置驅動程式
5. **重新啟動 usbmuxd**（macOS/Linux）：`sudo killall usbmuxd`

### iOS 17+ 通道問題

1. **以系統管理員身分執行** - 通道需要提升的權限
2. **保持通道執行** - 不要關閉通道終端視窗
3. **檢查防火牆** - 允許 Python 通過 Windows 防火牆
4. **IPv6 支援** - 確保您的系統支援 IPv6

### 位置沒有變更

1. **關閉依賴位置的應用程式** - GPS 模擬在應用程式重新啟動時效果最佳
2. **掛載開發者磁碟映像** - 執行 `pymobiledevice3 mounter auto-mount`
3. **重新啟動目標應用程式** - 某些應用程式會快取位置資料

### 地圖無法載入

1. **網際網路連線** - 需要用於地圖圖磚
2. **防火牆/代理** - 允許存取 OpenStreetMap/Google 伺服器

### 找不到裝置

1. 確保 tunneld 以系統管理員權限執行
2. 檢查 USB 線材連接
3. 解鎖您的裝置並信任此電腦
4. 等待幾秒鐘以進行裝置探索

---

## 技術細節

### 運作原理

iFakeGPS 使用 `pymobiledevice3` 與 iOS 裝置通訊：

1. **iOS 17 以下**：透過 `usbmuxd` 直接 USB 通訊
2. **iOS 17+**：使用 CoreDevice 框架的 RSD（遠端服務探索）通道

位置模擬使用 **DeveloperDiskImage** 服務：
- `DvtSecureSocketProxyService` - 安全通訊通道
- `LocationSimulation` - GPS 位置覆蓋

### 行走演算法

路線行走器：
1. 使用線性插值在路徑點之間進行插值
2. 根據距離和速度計算真實的時間
3. 每 0.5 秒更新裝置位置
4. 使用 Haversine 公式進行精確的距離計算
5. 套用可選的速度噪音以實現逼真的移動

### 主要元件

| 元件 | 說明 |
|------|------|
| `TunneldManager` | 管理 iOS 17+ 的 tunneld 服務 |
| `DeviceManager` | 處理裝置連接和位置模擬 |
| `RouteWalker` | 使用插值管理路線行走 |
| `iFakeGPSApp` | 主要圖形化介面應用程式 |

---

## 法律聲明

⚠️ **此工具僅供開發和測試目的使用。**

使用位置欺騙：
- 可能違反應用程式的服務條款
- 在某些司法管轄區可能屬於違法行為
- 不應用於詐欺或欺騙

**請負責任地使用，風險自負。**

---

## 致謝

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - iOS 裝置通訊
- [tkintermapview](https://github.com/TomSchimansky/TkinterMapView) - 互動式地圖元件
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - 現代化 UI 框架

---

## 授權

MIT 授權 - 歡迎自由使用和修改。
