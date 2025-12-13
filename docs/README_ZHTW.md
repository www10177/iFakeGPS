# iFakeGPS 📍

> **🌐 [English Version](../README.md)**

一款功能強大的圖形化介面應用程式，用於在 iOS 裝置上模擬 GPS 位置（支援 iOS 17+）。

- **瞬間移動** - 點一下即可將裝置的 GPS 傳送到任何地點
- **路線行走** - 建立路徑點並模擬真實的移動軌跡
- **搜尋地點** - 透過名稱搜尋並設定位置

---

## 📥 下載並執行

**已提供預先建置的 Windows 執行檔！** 無需安裝 Python。

👉 **[從 GitHub Releases 下載](https://github.com/user/ifakegps/releases/latest)**

### 快速開始

1. **下載** releases 中的 `iFakeGPS.exe`
2. **啟用開發者模式**（設定 > 隱私權與安全性 > 開發者模式）
3. **連接** 您的 iOS 裝置（使用 USB 線）
4. **執行** `iFakeGPS.exe`（在管理員提示時點選「是」）
5. **選擇** 清單中的裝置，開始模擬位置！

> **就這樣！** 應用程式會自動處理其他所有事項，包括 iOS 17+ 的通道服務。

---

## ✨ 功能

### 🎯 單點模式
在地圖上點選任意位置，即可將裝置的 GPS 瞬間傳送到該位置。

### 🚶 路線行走模式
- 點選多個點以建立行走路線
- 調整行走速度（1-50 km/h）
- 加入速度噪音讓移動更逼真
- 循環模式可持續行走

### 🔍 位置搜尋
透過名稱搜尋任何地點，並將其設定為您的 GPS 位置。

---

## 🔧 疑難排解

### 找不到裝置
1. 確保 iOS 裝置已啟用開發者模式
2. 在裝置上出現提示時點選「信任此電腦」
3. 嘗試重新連接 USB 線
4. 等待幾秒鐘讓裝置被偵測

### 位置沒有變更
1. 關閉並重新開啟依賴位置的應用程式
2. 某些應用程式會快取位置資料 - 請重新啟動它們

### 連線問題（iOS 17+）
應用程式會自動管理通道服務。如果遇到問題：
1. 確保以系統管理員身分執行
2. 檢查 Windows 防火牆是否允許 Python/iFakeGPS
3. 確保系統已啟用 IPv6

---

## 👨‍💻 開發者專區

<details>
<summary>點擊展開開發設定</summary>

### 安裝

```bash
# 複製儲存庫
git clone https://github.com/user/ifakegps.git
cd ifakegps

# 使用 uv（建議）
uv sync

# 或使用 pip
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 從原始碼執行

```bash
# 使用 uv
uv run python ifakegps.py

# 或直接執行（iOS 17+ 需要管理員權限）
python ifakegps.py
```

### 手動通道設定（進階）

對於 iOS 17+，如果需要單獨執行通道：

```powershell
# 以系統管理員身分執行
python -m pymobiledevice3 remote tunneld
```

> **注意：** 通常不需要這樣做，因為應用程式會自動處理。

### 開發者磁碟映像（僅 iOS 14-16）

對於 iOS 14-16，您可能需要掛載開發者磁碟映像：

```bash
pymobiledevice3 mounter auto-mount
```

> **注意：** iOS 17+ 不需要此步驟。

### 建置 Windows 執行檔

```bash
# 使用批次檔
pack.bat

# 或使用 Python
python pack.py
```

輸出：`dist/iFakeGPS.exe`（自動要求管理員權限）

</details>

---

## ⚖️ 法律聲明

此工具**僅供開發和測試目的使用**。位置模擬可能違反應用程式的服務條款。請負責任地使用。

---

## 🙏 致謝

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - iOS 裝置通訊
- [tkintermapview](https://github.com/TomSchimansky/TkinterMapView) - 互動式地圖元件
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - 現代化 UI 框架
