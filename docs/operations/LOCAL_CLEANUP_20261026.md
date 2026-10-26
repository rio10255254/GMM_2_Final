# 2026-10-26 本機清理：可重算的中間產物

這份紀錄說明 `D:\GMM_2_Final` 裡哪些檔案被刪除、依什麼規則選出來、樣本留在哪裡。目的是讓日後找不到某批資料的人知道它是刻意清掉的，而不是遺失；也知道要從哪裡重新產生。

**狀態：** 清單與刪除腳本在 2026-10-26 備妥並完成演練（1,578,144 個檔、664.0 GB，全部存在且大小與清單相符）。實際刪除由專案擁有者執行。

## 規則

專案擁有者的決定：能透過程式重跑出來的中間產物，本機與雲端都不必整套保留，每批留代表性樣本方便快速查看即可。雲端既有的 Release 不因此刪改。

整理時把「能重跑」分成兩種標準：

- **嚴格標準（整批保留，不在本次清單內）：** 正式基準與核准替代（COMBO、R33、R38v2、a025 所在的 R39／R40）、論文線（R152、R153、論文候選 R129 與 V42 相關輪次、論文比較基礎 R136、`Thesis_MOSR_Evidence` 的論文圖、方法消融與論文編輯）、廠商交付（R61 v16、`Validations/MOSR_ONNX_JunHua`）、所有整包交付（`Deliverables/`、`Model_Packages/`、外部 GMF 比較包、`_deployment_package/`）、共用原始來源，以及進行中的 `PSF_Fitting/quick_recalibration/`。
- **寬鬆標準（本次清單）：** 已結束、未採用的探索線。條件是該線在 git 上有報告或閱讀卡（結論已記錄），且原始拍攝在雲端或本機保留。這些產物日後只能用原程式與原始來源重新做一套，結果相近但不保證逐位元相同；r62 這類以前一版模型輸出當教師標籤的資料，重做需要重跑訓練鏈。

不論哪條線，以下一律不刪：相機原拍與原始量測、人工標記、模型檔（`.pth`、`.tar`、`.onnx`）、git 追蹤的檔、Markdown 文件直接連結的檔或其所在資料夾（上一兩層）、最近 14 天內修改過的檔。

## 刪除範圍

只含四類：訓練資料（圖與陣列）、分析用陣列（`.npz`、`.npy`）、重建圖、其他結果圖。圖檔每組（路徑前 7 層）保留頭、中、尾 3 張當樣本，共約 30.5 GB；陣列不留樣本，因為數字結論已在報告表格裡。文件連結而保留的約 8 GB。

| 資料夾 | 刪除量 |
|---|---:|
| `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r62_target_sample_boost` | 102.26 GB |
| `20260704_20x_5x_analysis` | 90.40 GB |
| `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization`（v16 以外的版本） | 53.43 GB |
| `20260702_100MG_displacement_analysis` | 49.90 GB |
| `Step_analysis_20260623` | 35.92 GB |
| `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r55_source_style_rebuild` | 34.81 GB |
| `Experiments/R147_FullResPSFConsistency` | 20.53 GB |
| `Experiments/R116_CoherentGeometryAnchorScratch` | 17.18 GB |
| `Experiments/R130_Clean` | 14.20 GB |
| `Experiments/R137_WeakPSFFeature` | 14.15 GB |
| `Experiments/R140v2_StableUNet` | 13.98 GB |
| `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r57_geometry_constrained` | 13.11 GB |
| `Experiments/R128_SourceOnlyFullTraining` | 12.40 GB |
| `Experiments/R114_ConfidenceGatedRecoverableScratch` | 12.18 GB |
| `Experiments/R143_PSF25_MatchedPairs` | 10.69 GB |
| `Experiments/R145_Center9PSF25_CorrectedPairs` | 10.67 GB |
| `Training_Data/r44_universal_boundary_motion` | 10.21 GB |
| `Experiments/R146_SEMCoreHaloPSF25_MatchedPairs` | 9.96 GB |
| `Experiments/R148v2_HybridContextNativePSF` | 9.93 GB |
| `Experiments/R150_MatchedGeometryMeanPSF` | 9.90 GB |
| 其他資料夾 | 約 118 GB |

三個連拍分析資料夾（`20260704_20x_5x_analysis`、`20260702_100MG_displacement_analysis`、`Step_analysis_20260623`）刪的是各版模型的重建輸出與從原拍中央裁出的輸入；原拍本身不在清單內。

每組的刪除檔數、位元組與保留樣本列在 [local_cleanup_20261026_groups.tsv.gz](local_cleanup_20261026_groups.tsv.gz)（5,244 組）。

## 要重新產生時

先讀 [訓練資料的生產方法與必要來源](../reproducibility/GENERATION_GUIDE.md)：其中 18 條路線（R88～R104、R61 v16、R152）的生成方式已按實際設定確認，其餘只保留原程式與報告索引。各輪原程式在該輪 `scripts/`，原始拍攝與共用來源用 `python Tools/cloud_locator.py where <路徑>` 查雲端位置。公司圓環序列的裁切參數見 [外部位移照片的裁切版](../reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)。
