# R39R40 a025 ONNX 交付包內容審核

日期：2026-05-13

## 結論

`GeoEdge_R39R40_a025_ONNX_Company_Package_20260511` 是公司用 ONNX 測試包，應只保留可直接執行推論與基本驗證所需的內容。

本次審核發現，先前為了內部分析而產生的顯微測試輸出、a025 對 COMBO 的比較輸出，以及快速驗證輸出曾被放在交付包的 `outputs/` 內。這些內容不屬於公司交付必要項目，已移出交付包並保存到 R39 實驗結果區。

## 已移出的內部資料

移出來源：

`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/outputs`

保存位置：

`Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/delivery_audit/a025_onnx_internal_eval_20260513/moved_from_delivery_package_outputs`

內容：

- `a025_multitype_microscopy_and_gmf_20260513`：a025 ONNX 多類顯微影像重建與外部 GMF 準備輸出。
- `a025_vs_combo_onnx_microscopy_compare_20260513`：a025 ONNX 與 COMBO ONNX 在同一批顯微測試圖上的內部比較報告、逐張指標與代表圖。
- `verify_after_multitest`：內部快速驗證留下的 sample 輸出。

移出規模：

- 檔案數：998
- 大小：約 739.7 MB

## 交付包保留內容

清理後，交付包只保留以下必要內容：

- `model/geoedge_r39r40_a025_body.onnx`：ONNX 模型主體。
- `assets/preprocess_config.json`：推論前處理設定。
- `assets/psf_mean.npy`：固定 PSF 前處理資料。
- `run_a025_onnx.py`：公司端可用的推論入口。
- `requirements.txt`：最低執行依賴。
- `samples/sample_input.bmp`：sample 輸入。
- `samples/sample_output_onnx.bmp`：ONNX sample 輸出。
- `samples/sample_output_reference_pytorch.bmp`：PyTorch 參考輸出。
- `verification_report.json`：ONNX 匯出與 sample 驗證紀錄。
- `README.md` / `README.zh-TW.md`：使用說明。
- `MANIFEST.json`：交付檔案與雜湊紀錄。
- `tests/test_package_smoke.py`：本機 smoke test，用來確認包可執行。

清理後的交付包資料夾：

- 檔案數：13
- 大小：約 16.17 MB
- `outputs/`：不保留
- `__pycache__/`：不保留

重新壓縮後的 zip：

- 路徑：`Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511.zip`
- 大小：約 14.27 MB
- zip 內檔案數：13
- zip 內 `outputs/`：0
- zip 內 `__pycache__/`：0

驗證：

- 從重新壓縮後的 zip 解壓到臨時資料夾。
- 在臨時資料夾執行 `tests/test_package_smoke.py`。
- 結果：1 passed。
- 驗證後臨時資料夾已刪除；正式交付資料夾仍沒有 `outputs/` 與 `__pycache__/`。

## 後續規則

- 公司交付包不放內部測試圖、比較圖、GMF 中間輸出、簡報素材。
- 內部比較與簡報素材應放在 `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/` 下，必要時在 `reports/` 補正式紀錄。
- 若要提供公司展示圖，應另做展示附件或實驗報告，不要混入可執行 ONNX 交付包。
