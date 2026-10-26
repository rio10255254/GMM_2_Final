# R92：補上物理邊緣過渡，平衡曝光的取樣

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R91](<../R91_DetailDecoupledScratch/FILE_GUIDE.md>) · [下一輪 R93](<../R93_RecoverableDetailSeparatedScratch/FILE_GUIDE.md>) · [R89～R93 的設計演進](<../../docs/reproducibility/scratch_lineage/README.md>) · [生成方法](<../../docs/reproducibility/GENERATION_GUIDE.md>)

**一句話：** 針對 R91 找出的原因修正：曝光組改成受控的更新比例（不再每輪耗盡）、對比範圍涵蓋 SEM 匿名統計裡的極低對比、答案加入不對稱的物理邊緣過渡並記錄過渡位置、移除不穩定的自適應細節控制。2026-08-12 從零完成 80 輪。清楚輸入的改動和新增結構錯誤比 R91 少，但位移尾端變差；更重要的是，**R92 這一份固定資料後來成為 R99、R100、R102～R104 的共用基礎**。

| | |
|---|---|
| 結果 | **研究候選**（成為 R99、R100、R102～R104 的共用資料基礎） |
| 時間 | 2026-08-12（01:51 啟動，05:53 完成 80 輪） |
| 實驗條件 | 純合成：1,250 個場景、5,000 個觀察；真實影像只提供匿名光學統計 |
| 起點 | 隨機初始化，種子 920041 |

## 結果（第 80 輪的原始驗證量，對照 R91）

| 驗證量 | R91 第 60 輪 | R92 第 80 輪 |
|---|---:|---:|
| 清楚輸入的平均改動 | 4.73 灰階 | 2.69 灰階 |
| 新增的結構錯誤 | 33 | 7 |
| 位移平均誤差 | 0.157 px | 0.287 px |
| 位移第 95 百分位 | 0.466 px | 1.106 px |
| 位移系統偏差 x／y | −0.046／−0.022 | −0.041／−0.096 px |
| 切塊差異 | 0 | 0 |

兩輪的資料與驗證讀法不同，這張表只是讓方向看得出來，不是排名。

## 讀這些數字要知道的事

1. **R92 和 R93 是兩套不同的共用資料。** R99、R100、R102～R104 用 R92；R94～R98 用 R93。引用時不能混用，也不能用 R93 的配方替換。
2. **資料真的被修過。** 69 張來源影像做了整體光度投影、4 組 16 張曝光跨度修復、另 1 張投影；封存組另有 1 張在同退化家族內重抽光學與雜訊參數。幾何、答案、分組、角色都沒動，答案像素沒有混入來源。實際使用的內容身分是 `260ccc5b…`。
3. **主要驗證與部署用 float32**，bfloat16 只是診斷選項。
4. 跟 R91 一樣，舊進度檔寫「active」，但結束摘要與 80 列逐輪表相符。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 設計、安全設定、授權；模型、訓練、推論、資料生成、監看、驗證程式 | 本資料夾 [config/](<config>)、[model/](<model>)、[training/](<training>)、[inference/](<inference>)、[scripts/](<scripts>)，已在 GitHub |
| 資料修復紀錄 | 本資料夾 `reports/` 的 `formal_recoverability_projection.json`、`formal_exposure_span_repair.json` |
| 結束摘要與完整逐輪表 | [runs/training_R92_scratch_seed920041_20260812_015138/](<runs/training_R92_scratch_seed920041_20260812_015138>) |
| 怎麼重建這份共用資料 | [R92 資料生產來源](<reports/R92_GENERATION_SOURCE_GUIDE_20261021.md>)、[生成方法](<../../docs/reproducibility/GENERATION_GUIDE.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [完成狀態與來源審查](<reports/R92_PRESERVATION_AUDIT_20261021.md>) | 完成狀態、必要來源、不利讀值 |
| [資料生產來源](<reports/R92_GENERATION_SOURCE_GUIDE_20261021.md>) | 種子、修復步驟、內容身分，以及哪些輪次引用它 |
| [README](<README.md>) | 對 R91 的修正、隔離規則、執行順序 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R92_PhysicalTransitionBalancedScratch.md>)。
