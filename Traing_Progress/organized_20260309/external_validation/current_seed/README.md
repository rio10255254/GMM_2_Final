# 0309 Current Seed 外部驗證入口

## 目前要驗證的權重

- seed label: `step8_curve_stdguard_v2`
- manifest:
  - `Traing_Progress/organized_20260307/selected/current_seed.json`
- weights:
  - `Traing_Progress/organized_20260307/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`

## 推理腳本目前預設行為

目前 [GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py](../../../../Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py) 已改成：

- 預設權重：讀取 `organized_20260307/selected/current_seed.json`
- 預設輸入資料夾：
  - `C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output`
- 預設選圖模式：`odd`
- 預設重建輸出根目錄：
  - `Traing_Progress/organized_20260309/external_validation/current_seed/reconstructions`

也就是說，你現在直接執行推理腳本時，會優先拿這個 current seed 做外部驗證用重建。

## 這個資料夾怎麼用

- `reconstructions/`
  - 放這次 current seed 的重建結果
- `gmf_results/raw/`
  - 放你外部程式輸出的原始座標/分數文字檔
  - 例如 `GMF_score.txt`
- `gmf_results/analyzed/`
  - 放我後續整理出的統計結果
- `reports/`
  - 放這次外部驗證的 md 報告

## 建議流程

1. 直接執行推理腳本做重建。
2. 用外部 GMF 程式跑定位。
3. 把 `GMF_score.txt` 放進 `gmf_results/raw/`。
4. 回來把檔案路徑給我，我會幫你做步長統計與報告。
