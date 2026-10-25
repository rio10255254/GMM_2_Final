# R84：消除 R79 的切塊差異，以及最後的結案

[研究時間線](<../../docs/research/TIMELINE.md>) · [起點 R79](<../R79_R75v3_DenseMicroscopyScratchGeneralization/FILE_GUIDE.md>) · [前一輪 R83](<../R83_R79SevereMicroscopyStrengthening/FILE_GUIDE.md>) · [第二種修法 R85](<../R85_R79SharedCanvasOpticalRepair/FILE_GUIDE.md>) · [第三種修法 R86](<../R86_R79BlockGroupNormRepair/FILE_GUIDE.md>) · [R79 ONNX 交付包](<../../Deliverables/MOSR_ONNX/README.md>)

**一句話：** R83 發現 R79 的輸出會隨切塊大小改變。2026-08-10 的 R84 改成只用局部運算的網路從頭訓練，切塊一致性修好了、實拍位移也保住，但 10 道門檻只過 7 道，SEM 邊界誤差是 R79 的 2.28 倍。R85、R86 換了兩種修法也一樣。**這個資料夾同時放了三輪的總結案：** 保留原本的 R79，把來源推論與 ONNX 交付都改成只能整張重建一次。

| | |
|---|---|
| 結果 | **未採用**（各有代價；最後保留原 R79 並固定整張推論） |
| 時間 | 2026-08-10 |
| 實驗條件 | 純合成資料訓練；確認用新合成、R73、R74、36 顆柱 SEM、六組實拍位移 |
| 起點 | 局部運算的新結構，只用程式生成形狀訓練 |

## R84 的結果（10 道門檻過 7 道）

| 項目 | R84 ／ R79 |
|---|---:|
| 新合成整體誤差 | 0.625 |
| 新合成邊界誤差 | 1.096（未過） |
| 新合成 ACM 輪廓 | 1.141（未過） |
| R74 困難顯微 | 0.642 |
| 36 顆 SEM | **2.281（未過）** |
| 實拍位移 | 6/6 通過 |

## 三種修法的總結

| 輪次 | 修法 | 切塊一致 | 代價 |
|---|---|---|---|
| R84 | 改成局部運算網路，從頭訓練 | 修好 | SEM 邊界誤差 2.28 倍 |
| R85 | 保留 R84 的局部網路，光學前處理在整張畫布只算一次 | 修好 | 兩個保存點的邊界誤差 1.18、1.16 倍，沒有可選權重 |
| R86 | 不訓練，把全圖的 GroupNorm 換成固定 8×8 區塊 | 修好 | 整體誤差 1.41 倍、邊界誤差 1.96 倍，連訓練都不值得開始 |

結論是問題不在接縫融合參數，而是 R79 本身就依整張可見範圍計算；不犧牲品質的最小修法，就是只允許整張重建。

## 結案時完成的修改

- 來源推論入口與 ONNX 交付入口都取消切塊大小與重疊選項，只剩整張流程。
- 先整批檢查尺寸，超出範圍就在載入模型、寫出檔案前停止，不會退回切塊。驗證過的範圍：短邊至少 21 px、長邊不超過 2,180 px、總像素不超過 3,313,600。
- 禁止輸出資料夾放進輸入資料夾、禁止覆蓋原圖。
- 模型檔與 R79 權重完全沒變。

**檢測：** ONNX 與原始 R79 在 12 張跨場景影像（均華前中後、5×／20×／50× 首尾、兩張 SEM、標準示例）逐像素對照全部通過，最大差 1 階灰階；同圖重跑差異 0；壓縮包解壓後獨立實跑與標準答案完全相同。

## 讀這些內容要知道的事

1. **`Deliverables/MOSR_ONNX` 是 R79，`Deliverables/MOSR_R61_ONNX` 是 R61**，兩個交付包不同。
2. **外部 GMF 沒有重跑**（當時新金鑰還沒取得），改用相同模型雜湊、12 張逐像素一致與既有六組位移當不變性確認。
3. **專案正式基準仍是 COMBO**；R79 是當時研究線與應急重建的預設。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料生成、篩選、最終確認、交付一致性程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)、[config/](<config>)，已在 GitHub |
| 最終判決、交付修正、共用前處理探測的結果 | [results/](<results>) |
| R79 ONNX 交付包 | [Deliverables/MOSR_ONNX/](<../../Deliverables/MOSR_ONNX/README.md>) 的說明與程式在 GitHub；`model.onnx`（15.4 MB）在那個路徑上沒有上傳，但**同內容**的檔案在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 的 `research-fixed-models-006.zip` 裡，路徑是本資料夾 `results/delivery_root_fix/extracted_package_1_1/MOSR_ONNX/model.onnx`（結案時解壓驗證的那份） |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R79 根治與完整檢測結案](<reports/R79_ROOT_REPAIR_CLOSEOUT.md>) | 先讀這份：三種修法的總結、完成的修改、檢測結果、交付 |
| [R84 最終判決](<reports/R84_FINAL_VERDICT.md>) | 10 道門檻的結果 |
| [README](<README.md>) | 目標與最終狀態 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R84_R79TileStableRootRepair.md>)。
