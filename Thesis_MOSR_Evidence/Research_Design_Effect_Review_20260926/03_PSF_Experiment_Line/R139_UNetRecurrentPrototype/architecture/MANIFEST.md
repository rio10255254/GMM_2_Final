# R139 原型檔案與證據邊界

- `model.py`：U-Net 加四次共享修正主體，**尚未訓練**。
- `optical/feature.py`：與原 V42 同類別的弱 PSF 模組，只改25顆 NPZ 載入介面。
- `config/measured_psf_bank.npz`：既有25顆 PSF 的完整副本，來源及歷史限制見 `config/INHERITED_PSF_PROVENANCE.json`。
- `training_policy.py`：暫定分階段訓練與 beta 邊界處理，尚未執行正式長訓練。
- `scripts/preflight.py` 與 `scripts/generated_pair_preflight.py`：原型可運作檢查；其中兩次資料更新的權重已丟棄。
- `results/*.json`：原型檢查紀錄，不能用於宣稱量測性能。

大型合成資料不複製，前置檢查讀取既有 R130 資料。無訓練權重、無實拍重建結果。本輪原型目標只確認 U-Net 與既有元件的資料流及可訓練性。
