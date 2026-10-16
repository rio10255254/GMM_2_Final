# R44F 診斷 — 大區塊與混合場景錯誤解剖

## 摘要

R44F 不訓練、不開新 round。它只使用 R44 已有的重建影像與逐 pair 指標，目的是判斷大區塊與混合場景的問題到底是模型能力、資料標註，還是評估指標造成的假象。

結論：**目前沒有證據顯示只是指標誤判。指標能抓到人工位移；但大區塊/混合場景的高邊界距離常發生在位移向量已經很準的情況，代表主要瓶頸是邊界形狀品質與邊界抽取穩定度，而不是整張圖沒有跟著移動。**

## 指標壓力測試

我用答案邊界人工製造 1px、2px、5px 偏移，以及邊界變厚/變薄/缺角，確認目前邊界距離指標是否有基本辨識力。

| 類型 | 1px 偏移 | 5px 偏移 | 邊界變厚 |
| --- | --- | --- | --- |
| large_regions | 0.5335 | 2.5477 | 1.5596 |
| mixed_fields | 0.5673 | 2.6217 | 1.5794 |

判讀：人工偏移會被指標明確放大，代表它不是完全失效。不過邊界變厚也會被明顯懲罰，所以若模型把大區塊邊界重建得偏厚、偏碎或有波紋，數字會快速變差。

## 錯誤案例挑選

R44F 自動挑出四類案例：R42 明顯優於 R44B、R44B 明顯優於 R42、R44E repair 有小幅改善、以及位移已準但邊界仍差的案例。

| 原因 | 類型 | seq | frame | R42 邊界 | R44B 邊界 | R44E repair 邊界 |
| --- | --- | --- | --- | --- | --- | --- |
| r42_much_better_than_r44b | large_regions | 80 | 5 | 4.2150 | 13.3684 | 7.2307 |
| r42_much_better_than_r44b | large_regions | 85 | 4 | 5.2815 | 9.7708 | 9.4721 |
| r42_much_better_than_r44b | mixed_fields | 91 | 5 | 26.8536 | 31.1703 | 31.1599 |
| r42_much_better_than_r44b | mixed_fields | 84 | 4 | 10.4242 | 13.8799 | 12.1139 |
| r44b_much_better_than_r42 | mixed_fields | 93 | 2 | 5.4565 | 2.9810 | 2.7848 |
| r44b_much_better_than_r42 | mixed_fields | 84 | 2 | 19.5777 | 17.1202 | 11.6594 |
| r44b_much_better_than_r42 | large_regions | 99 | 6 | 5.5412 | 3.2903 | 3.6939 |
| r44b_much_better_than_r42 | mixed_fields | 93 | 3 | 5.1253 | 2.9421 | 2.5431 |
| r44e_repair_improves_mixed_or_region | mixed_fields | 84 | 2 | 19.5777 | 17.1202 | 11.6594 |
| r44e_repair_improves_mixed_or_region | mixed_fields | 87 | 3 | 10.9106 | 11.3590 | 7.4520 |

代表圖中綠色是答案邊界，紅色是模型輸出的邊界，黃色是重疊區。肉眼判讀重點不是亮不亮，而是紅綠是否貼在同一條邊上、是否變厚、是否碎裂或波紋化。

## R44F 判斷

- 大區塊與混合場景不是單純「整體沒跟著位移」。很多案例的位移誤差很低，但邊界距離仍高。
- 目前指標能抓到人工偏移，因此不能直接說大區塊分數差只是指標壞掉。
- 指標對邊界厚度與碎裂敏感；這符合我們要的邊界忠實度，但也表示下一輪不能只追清晰或高頻，必須讓邊界形狀本身更穩。
- R44E 的短訓練沒有解開問題，因為它沒有改變邊界形狀的產生方式，只是讓模型在既有能力之間拉扯。

## 下一步

不建議再做同型短訓練。若要繼續，下一步應該是二選一：

1. 先修評估：加入更直接的邊界厚度、碎裂、角點/直邊保持指標，避免只靠單一距離值判斷。
2. 再設計訓練：若評估確認無誤，再做分族邊界形狀目標，讓大區塊直邊、混合場景小細節、格線位移各自有不同約束。

## 產物

- 案例表：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44f_selected_cases.csv`
- 案例 JSON：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44f_selected_cases.json`
- 指標壓力測試：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44f_metric_stress.csv`
- 指標壓力測試 JSON：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44f_metric_stress.json`
- 錯誤解剖代表圖：`Experiments\R44_UniversalBoundaryMotionFidelity\results\visual_samples\r44f_error_dissection_sheet.png`
