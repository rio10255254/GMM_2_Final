# 深層資料夾怎麼讀

[專案首頁](../../README.md) · [研究分區](../reproducibility/EXPERIMENTS.md) · [目前保存狀態](../reproducibility/STATUS.md)

這一輪深入現有資料夾，補上每輪檔案分工及複雜子區的內容說明。原方法、結果、檔名與固定交付包沒有搬動；閱讀整理不等於所有必要來源已查完。

## 三條找檔路線

| 目的 | 路線 |
|---|---|
| 找某一輪的設定、原報告與數表 | [研究分區](../reproducibility/EXPERIMENTS.md) → 該輪閱讀卡 → 「直接查看這一輪的檔案分工」 → 該輪FILE_GUIDE與原子資料夾 |
| 找Lab的校正、資料與模型版本 | [Lab校正](../../Thesis_MOSR_Evidence/LabSystem_MOSR/psf_calibration/CONTENTS.md) → [資料形成](../../Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/CONTENTS.md) → [Lab各輪](../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/README.md) → [模型包版本](../../Deliverables/Standalone_Models/README.md) |
| 找獨立使用包或舊論文交接 | [交付包分類](../../Deliverables/CONTENTS.md) → 包外內容導讀 → 原包；依用途再取得附件 |

## 優先釐清的深層區域

| 區域 | 現在怎麼分辨 |
|---|---|
| [R153報告區](../../Experiments/R153_MeanExternalBenchmark/reports/README.md) | mean-only、七方法、九方法與最終十方法各有原階段；先讀最終十方法，舊版不刪除或合併 |
| [R63結果區](../../Experiments/R63_CausalBoundaryMotionAblation/results/README.md) | 當年訓練完成、實際選中模型、後來清理紀錄分清；今天仍缺一個原第24輪模型 |
| [R93資料與來源](../../Experiments/R93_RecoverableDetailSeparatedScratch/FILE_GUIDE.md) | 失敗前測、正式資料、60輪停止與48輪綜合候選分開 |
| [R136重拍與量測](../../Experiments/R136_PIRepeatability/FILE_GUIDE.md) | 原中心量測、LSC、SEM與形狀尺寸結果分區；多張／多圈不直接當獨立重拍 |
| [R148v2幾何與比較來源](../../Experiments/R148v2_HybridContextNativePSF/FILE_GUIDE.md) | 幾何陣列、原比較中心與真正影像來源分開；短測模型不當正式8192模型 |
| [Lab模型包](../../Deliverables/Standalone_Models/README.md) | V42的180組小測試包與11,254組完整訓練包分開；R61、R129、R134維持原介面與身分 |

## 整理界線

- 依GitHub固定版本的實際檔案建立索引，沒有把本機資料夾名稱當成已上傳證據。
- 177個原研究閱讀範圍全部配到檔案導讀；R118因其原工作規則，導讀放在文件區，沒有修改它的實驗資料夾。
- 原報告、程式、數表、圖片、固定模型及原獨立包內容不改；只新增目錄說明並更新閱讀卡／導航。
- 本次沒有上傳大型資料、重新訓練、推論、重新計算全部實驗或清理本機原件。必要來源查漏沿[目前狀態](../reproducibility/STATUS.md)繼續。

表中的檔案數只計整理前主版本已存在的檔案，不把新增導讀算成新的研究成果；附件內容另按各次清單閱讀。
