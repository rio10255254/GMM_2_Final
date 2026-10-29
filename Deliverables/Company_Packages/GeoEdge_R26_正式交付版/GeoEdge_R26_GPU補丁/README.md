# GeoEdge R26 GPU 補丁說明

這個資料夾放的是獨立 GPU runtime 補丁。

## 這是做什麼用的

- 只有在主機無法直接使用主包內建 Python / CUDA 路線時才安裝
- 全程離線，不會從網路下載任何內容
- 只建議安裝在對應版本的主包上

## 安裝方式

1. 如果 `GeoEdge_R26_GPU補丁` 還是壓縮檔，先解壓縮
2. 執行 `INSTALL_GPU_PATCH.bat`
3. 如果有詢問主包根目錄，請輸入主包資料夾路徑
4. 安裝完成後，再回主包重新執行 `START_HERE.bat`

## 回退方式

1. 執行 `UNINSTALL_GPU_PATCH.bat`
2. 如果有找到備份，就會自動還原最近一次安裝前的狀態

## 預期結果

- 主包會取得 `內部檔案\portable_runtime`
- 啟動器就能在 CUDA 可用時使用這套獨立 GPU runtime
