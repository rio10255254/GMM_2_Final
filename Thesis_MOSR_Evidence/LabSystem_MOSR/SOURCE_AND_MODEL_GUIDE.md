# LabSystem來源、模型與深層資料夾

[逐輪核對總表](<../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) · [Lab研究沿革](<../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [模型包版本](<Model_Packages/README.md>)

## 從來源走到結果

| 階段 | 先讀哪裡 | 內容界線 |
|---|---|---|
| 原拍與PSF | [校正導讀](psf_calibration/CONTENTS.md) | 25張原拍只保存一次；舊資料夾日期與實拍日期分開 |
| Lab stage01–33及各輪資料 | [資料形成](Training_Data/CONTENTS.md)、[SOURCE_MANIFEST](Training_Data/SOURCE_MANIFEST.json)、[環形重組清單](Training_Data/tra_ring_manifest.json) | 大型影像由原生成器及固定PSF形成；stage不是實驗輪次 |
| R39／R40至R62 | [Lab各輪](Experiments/README.md) | 每輪FILE_GUIDE連到本次來源與模型總表；失敗、best與latest均保留 |
| 原模型歷程 | [訓練與選模](Traing_Progress/README.md) | 代表模型由既有附件按原路徑恢復；中途epoch不全傳 |
| R61／V41／V42獨立包 | [模型包入口](Model_Packages/README.md) | 早期短測、完整長訓練及後來論文模型分開 |
| 實拍與數學位移 | [重建歷史](Reconstruct_Progress/README.md)、[子像素測試](Experiments/Subpixel_Translation_Equivariance_20260720/FILE_GUIDE.md) | 數學平移不是平台重拍，舊七月資料不是九月30趟重拍 |

[47個既有代表模型的提供者](../../docs/reproducibility/round_source_reviews/LAB_REPRESENTATIVE_MODELS_20261023.json.gz)及[71份關鍵原件](../../docs/reproducibility/round_source_reviews/LAB_CRITICAL_SOURCES_20261023.json)可供機器核對。R62新補的兩份固定輸出模型位於原`Traing_Progress/packaged_checkpoints`。

本頁只整理深層關係，不改原模型採用判決。目前論文仍以R152／RAW及R153交接為準。
