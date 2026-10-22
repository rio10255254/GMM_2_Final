# Lab獨立模型包：先分版本與用途

[Lab全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [全部模型取得](<../../../docs/reproducibility/MODEL_GUIDE.md>)

每個原包維持自己的檔案結構、原README及核對紀錄。本次只在包外整理入口，沒有將不同版本合併或複製一份模型。

| 原包 | 用途 | 版本界線 |
|---|---|---|
| [V42_SoftLabelSNR_Standalone_20260709](<V42_SoftLabelSNR_Standalone_20260709/README_TW.md>) | V42早期小測試包 | 180組資料的smoke階段，不是後來11,254組完整訓練。 |
| [V42_SoftLabelSNR_FullStandalone_20260709](<V42_SoftLabelSNR_FullStandalone_20260709/README_TW.md>) | V42完整訓練包 | 11,254組、15類資料；第10輪與第120輪差異須連同原比較閱讀。 |
| [R61_STEP_Generalization_Standalone_20260910](<R61_STEP_Generalization_Standalone_20260910/README_TW.md>) | R61獨立使用包 | 模型使用與R61 v16資料生成包用途不同；保留歷史來源／幾何。 |
| [R129_OpticalHybrid_Standalone_20260912](<R129_OpticalHybrid_Standalone_20260912/README_TW.md>) | R129光學融合獨立包 | 歷史研究與配套模型，不代表目前論文改採R129。 |
| [R134_DirectState_Precision_Standalone_20260915](<R134_DirectState_Precision_Standalone_20260915/README_TW.md>) | R134獨立包 | 依本包原設定及固定模型使用，不能只因日期較晚替換其他輪模型。 |

原說明寫的完整資料與模型可能在版本附件；主版本的檔案列表不等於包內全部大檔已直接放入Git。[按用途取回](<../../../docs/reproducibility/ASSET_GUIDE.md>)。
