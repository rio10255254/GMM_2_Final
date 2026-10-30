# R62固定輸出模型

[Lab逐輪來源與模型](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) · [R62研究卡](<../../../docs/reproducibility/experiments/lab__R62_TargetSampleBoost.md>)

這裡的模型沒有重新訓練參數，只把已保存模型配上固定原圖錨定輸出設定。

| 原封裝 | 基礎模型 | 固定輸出用途 |
|---|---|---|
| [v24 blend10](r62_v24_v7_anchor_blend10_builtin/r62_v24_v7_anchor_blend10_builtin.pth.tar) | R62 V7 best | 90%原圖＋10%重建，保守跨資料輸出 |
| [v29 detail035](r62_v29_v28_detail35_anchor/r62_v29_v28_detail35_anchor.pth.tar) | R62 V28 latest | 保留原圖低頻並加入固定細節比例，供100MG論文樣品比較 |

兩份模型參數已逐項確認與各自基礎模型相同。其他V25／V27混合探索未列為必要模型；原結果仍在R62報告區。
