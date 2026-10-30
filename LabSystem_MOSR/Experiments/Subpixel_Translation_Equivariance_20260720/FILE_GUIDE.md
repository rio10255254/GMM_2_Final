# 次像素平移測試：輸入移一點點，輸出的邊界跟不跟得上

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [EDSR／NAFNet 對照](<../Modern_Restoration_Benchmarks_20260719/FILE_GUIDE.md>) · [後續的原因診斷](<../MOSR_CheckpointConfig_Diagnostic_20260724/FILE_GUIDE.md>)

**一句話：** EDSR／NAFNet 比較的稽核建議，用已知的次像素位移直接測「邊界位置能不能被保住」，避開平台指令不準的問題。2026-07-20 把六個實拍區域各在水平、垂直方向平移 ±0.10～±1.00 px，產生 126 張 16-bit 測試影像，比較五種方法。EDSR 最接近理想，Base U-Net 次之，V42 明確優於 NAFNet，但沒有贏 EDSR 和 Base U-Net。

| | |
|---|---|
| 結果 | **分析**（插值位移不同於平台重拍，MOSR 沒有全面勝過 EDSR） |
| 時間 | 2026-07-20 |
| 實驗條件 | C：實驗室顯微系統；50×、20× 的 100MG 實拍影像，柱、孔、線條共六個固定區域 |
| 比較對象 | 原圖、Base U-Net、EDSR、NAFNet、V42 第 120 輪（文件裡稱 MOSR） |

## 這輪在問什麼

對同一張影像做已知的數學平移，各方法重建後的邊界有沒有跟著移動同樣的量？

## 怎麼做

- 設計事先寫進 `predeclared_design.json`：區域、方向、位移量、有效規則在推論前就固定。
- 每個方法 100 組完全配對的「區域、方向、位移」；所有模型整張 512×512 推論，不分塊。
- 圓形結構取九個邊界中心的中位數；線條至少要十條有效邊界。

## 結果

| 方法 | 誤差中位數（px） | 第 95 百分位（px） | 物空間中位誤差（nm） |
|---|---:|---:|---:|
| 原圖 | 0.00397 | 0.01914 | 0.403 |
| Base U-Net | 0.00747 | 0.03040 | 0.698 |
| EDSR | 0.00402 | 0.02624 | 0.329 |
| NAFNet | 0.01544 | 0.07075 | 1.459 |
| V42 | 0.00954 | 0.04287 | 0.985 |

逐組比較，V42 在 58% 的組合中贏 NAFNet，對 EDSR 只有 37%、對 Base U-Net 42%。100 組全部可量測。

**邊界形狀：** V42 的局部斜率（0.382）接近 EDSR，但 10%～90% 過渡寬度（8.3 px）遠大於其他網路、振鈴最明顯——它形成「局部很陡、外圍還有一圈亮暗」的雙層邊界。

## 讀這些數字要知道的事

1. **原圖接近理想是預期的。** 原圖本身就是被數學平移的那張影像，不代表原圖重建能力好。
2. **測的是對插值平移的等變性**，不等於平台真的移動、重新取像、雜訊與模糊都改變時的量測表現。報告建議把它當方法壓力測試，不當主證據。
3. **最小的 0.1 px 位移時 V42 最好**（中位誤差 0.00374 px，EDSR 0.00503 px），這是 7/24 診斷補上的細項。
4. 為什麼 V42 輸給 EDSR，見 [7/24 的設定診斷](<../MOSR_CheckpointConfig_Diagnostic_20260724/FILE_GUIDE.md>)：三層步幅 2 的降採樣讓特徵落在不同取樣相位。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 輸入產生、推論、品質檢查、分析、驗證、畫圖程式 | 本資料夾根目錄，已在 GitHub |
| 事先宣告的設計、輸入清單、推論清單 | [predeclared_design.json](<predeclared_design.json>)、[inputs/](<inputs>)、[results/](<results>) |
| 結果表與七張圖 | [analysis/tables/](<analysis/tables>)、[figures/](<figures>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 126 張 16-bit 測試影像與各方法的輸出只在原電腦上；可用 `prepare_subpixel_inputs.py` 依事先宣告的設計重新產生輸入。

## 原始報告

| 報告 | 內容 |
|---|---|
| [實驗報告](<EXPERIMENT_REPORT_zh-TW.md>) | 設計、結果、雙層邊界的解讀、論文使用建議、驗證狀態 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__Subpixel_Translation_Equivariance_20260720.md>)。
