# 早期批次與歷史支線

[全部分區](../EXPERIMENTS.md) · [研究沿革](../lineage/README.md) · [目前保存狀態](../STATUS.md)

早期調參、選模與外部比較；日期批次不等於連續R編號。

以下是閱讀順序，不表示相鄰兩輪必然繼承同一模型或資料。原正式報告優先於卡片的早期摘要。

| 實驗 | 研究問題 | 判讀與限制 |
|---|---|---|
| [legacy/branch_e](../experiments/legacy__branch_e.md) | 估計器Branch E探索 | 後續有跟進但不是最後基準 |
| [legacy/branch_e_followup](../experiments/legacy__branch_e_followup.md) | Branch E校正後再評估 | 未通過升級條件，保留反例 |
| [legacy/diagnostics](../experiments/legacy__diagnostics.md) | 選擇估計器研究分支的診斷 | 歷史決策證據，不是新模型 |
| [legacy/estimator_formula_probe](../experiments/legacy__estimator_formula_probe.md) | 早期估計公式探索 | 方法歷史不等於正式量測資格 |
| [legacy/organized_20260306](../experiments/legacy__organized_20260306.md) | 最早整理的訓練候選、採用與拒絕歷史 | 保留選擇脈絡；沒有完整來源證據的舊候選只標歷史紀錄 |
| [legacy/organized_20260307](../experiments/legacy__organized_20260307.md) | 內部種子搜尋與自動參數試驗 | 當時精選seed不是目前基準，完整拒絕歷史另在H |
| [legacy/organized_20260309](../experiments/legacy__organized_20260309.md) | 精選seed的外部GMF與視覺比較 | step8_curve_stdguard_v2屬歷史驗證對象，原始回傳不可用新讀法覆蓋 |
| [legacy/organized_20260310](../experiments/legacy__organized_20260310.md) | 多尺度、SeqVal、crossscale及uint16微步測試 | 中大尺度與微步結果分開，精度修復前後均保留 |
| [legacy/organized_20260311](../experiments/legacy__organized_20260311.md) | Round12長跑、Round13模型審查與Round14走廊檢查 | 把12到14輪各份selected報告保留，不用一個資料夾名取代各輪身分 |
| [legacy/organized_20260312](../experiments/legacy__organized_20260312.md) | Round15中心鎖定長訓練與外部驗證 | centerlock_pure是歷史研究候選，代表模型與被取代原因保留 |
| [legacy/pairwise_delta_probe](../experiments/legacy__pairwise_delta_probe.md) | 兩影格位移混合方式的前測 | 支撐R22的設計來源，與R22正式驗證分開 |
| [legacy/round16](../experiments/legacy__round16.md) | 更換邊界估計讀法 | 曾為內部較好版本，後被取代 |
| [legacy/round17](../experiments/legacy__round17.md) | 修復步距與位移估計 | 內部改善不能代替後來外部比較 |
| [legacy/round18](../experiments/legacy__round18.md) | 中心位置約束的歷史基準 | 當時採用，之後與R22外部比較 |
| [legacy/round19](../experiments/legacy__round19.md) | 絕對位置錨定假說 | 已完成未採用，保留反例 |
| [legacy/round20](../experiments/legacy__round20.md) | 固定基準的流程前測 | 假說未支持，不把流程完成當效益 |
| [legacy/round21](../experiments/legacy__round21.md) | 混合估計器的正式跟進 | 未解開主線限制 |
| [legacy/round22](../experiments/legacy__round22.md) | 成對混合估計器 | 歷史採用版本，後由外部系列比較 |
| [legacy/round23](../experiments/legacy__round23.md) | R22之後的歷史候選 | 依selected/reports保存當時結論，不能推定為目前基準 |
| [legacy/round24](../experiments/legacy__round24.md) | 主線與對照的歷史候選 | 保留實際配方與當時驗收，不補造缺失結果 |
| [legacy/round25](../experiments/legacy__round25.md) | 外部多尺度比較鏈的共同參照 | 後續各輪必須保留同一來源與讀法 |
| [legacy/round26](../experiments/legacy__round26.md) | 平滑強度與正式交付版本 | 歷史R26與新PSF沙盒的政策身分分開 |
| [legacy/round27](../experiments/legacy__round27.md) | 在R26基礎上的外部比較 | 以當時正式結果保留負面與正面讀值 |
| [legacy/round28](../experiments/legacy__round28.md) | 延續多尺度守門的歷史候選 | 保留完整外部回傳與採用判斷 |
| [legacy/round29](../experiments/legacy__round29.md) | R30之前的歷史候選 | 不因資料夾位於selected就推定目前正式 |
| [legacy/round30](../experiments/legacy__round30.md) | 方向約束的歷史前任正式模型 | 前任基準不是目前COMBO；保留確切模型及外部證據 |
| [legacy/round31](../experiments/legacy__round31.md) | 訓練權重與等化訊號再調整 | 外部退步，不能只看內部通過 |
| [legacy/round32](../experiments/legacy__round32.md) | 舊批次R32輸出 | 正式可編輯紀錄已移到主專案R32Sandbox |
| [legacy/tta_experiment](../experiments/legacy__tta_experiment.md) | 推論時多種變換與平均的影響 | 保存固定TTA規則與量測代價，不用單張清晰度決定採用 |
