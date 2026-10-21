# 100 顆 PSF 自適應選八顆獨立包

這包已備妥可接收 **100 顆實測 PSF** 的主網路、逐張選八顆機制、合成訓練資料副本、訓練／推論入口、原 R140v2 主網路的未訓練起點、驗證器與機制測試。**目前沒有在這包中啟用的 100 顆實測 PSF，也沒有用該資料訓練完成的模型；推論會明確拒絕執行。** 測試用合成 PSF 只在測試程序的暫存目錄出現，絕不充當實測銀行。

放入資料之前可用：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' verify_package.py --mode structural
```

實測資料應轉為 NPZ，陣列名稱 `all_kernels`，形狀 `(100,101,101)`，數值有限、非負、每顆總和大於零。另提供一份來源 JSON，至少說明 `origin`、`grid_rows=10`、`grid_cols=10`、`index_order`、`image_scale_um_per_px`、`sem_truth_dependency`。檢查後才可安裝：

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' install_bank.py --source 'D:\your_real_psf100.npz' --provenance 'D:\your_psf100_provenance.json'
```

安裝會留下銀行雜湊與來源鎖，不會覆蓋既有銀行。完成來源與尺度核對後，把具備逐影像 `psf_index` 的匹配資料放在**包外新資料夾**，保留 512/128/128 的相同清單格式，以 `train.py --run-name psf100_labeled --data-root 'D:\new_labeled_data' --init derived` 訓練；包內原始資料不需修改。沒有標記時只可做明確標記的非自適應探索。訓練結束並做實拍驗證後，使用 `infer.py --checkpoint <新模型> --input <影像> --output <新輸出>`。

在 `PSF_Fitting` 內找到一份 2026 年 3 月製作的 full100 舊候選，它的 PSF 差異比早期版本明顯；但該資料與目前顯微影像的尺度、樣本及 SEM 真值關係尚未完成對接。因此本包**不把它偷偷當成正式 100 顆輸入**。若日後選擇使用，先獨立核對來源，再走上面的安裝程序。

模型設計及受控選擇測試詳見 `MODEL_CARD.md` 與 `tests/`；那些測試只證明機制能在可區分的成像條件下學會選擇，不等於實際 100 顆資料已通過能力驗證。
