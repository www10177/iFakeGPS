# iFakeGPS 整理與修正 TODO

> 建立於 2026-06-20。本檔追蹤一系列「清理 + 修正」工作。

## 1. 專案結構整理 — 把進入點/腳本歸位 ✅
- [x] `run.py` → `scripts/run.py`（修正 sys.path 指向專案根目錄）
- [x] `run.bat` → `scripts/run.bat`（提權後 `cd` 回根目錄再 `uv run`）
- [x] `pack.bat` → `scripts/pack.bat`（`cd` 回根目錄解析 spec/docs/app.ico）
- [x] 更新 AGENTS.md / CLAUDE.md / README.md / docs/README_ZHTW.md 的路徑引用
- [x] 驗證 `uv run python scripts/run.py` 可正常 import src.main

## 2. 文件去重 — AGENTS.md 為正本 ✅
- [x] AGENTS.md 為單一正本（修正路徑、補打包單一來源、更新 CI 說明）
- [x] CLAUDE.md 縮成精簡指標檔（`@AGENTS.md` + 快速指令）
- [x] 修掉先前 CLAUDE.md 對儲存路徑的錯誤註記（實際是 %LOCALAPPDATA%\iFakeGPS\cache）

## 3. Auto Update 鎖檔修正 ✅
- [x] `TunneldManager.stop()` 殺整棵行程樹（Windows `taskkill /F /T`；POSIX killpg）
- [x] `stop()` 清除佔用 tunneld port(49151) 的殘留行程（涵蓋孤兒/沿用情況）
- [x] `start()` 註冊 `atexit` 保險，崩潰退出時也清理
- [x] 冒煙測試：import OK、stop() idempotent、netstat 解析正常
- [ ] **待實機驗證**：關閉 app 後確認無殘留 iFakeGPS 子行程、exe 可被覆蓋（不需重開機）

## 4. CI 調整 ✅
- [x] 保留 tag(`X.Y.Z`) push 自動發布 Release
- [x] 新增 `workflow_dispatch` 手動觸發 → dev build（上傳 artifact，不發 Release）
- [x] 一般 push 不觸發任何建置（省 Windows runner 費用）
- [x] YAML 格式驗證通過

## 5. 收尾
- [ ] 一次性 commit（等使用者確認）

## 備註 / 後續可考慮（非本次範圍）
- `src/ui/app.py:106-107`：location_storage 與 route_storage 都指向同一個 `routes.db`，可日後釐清。
- README「For Developers」原本引用不存在的 ifakegps.py / requirements.txt / pack.py，已順手修正。
