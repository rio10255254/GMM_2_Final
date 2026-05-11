# R44E 大區塊與混合場景專項探針

## 定位

R44E 不是新 round，而是 R44 內部追加的小型探針。

R44D 已經顯示：R42/R44B/R44C 在細線、格線、曲線、交叉線上已經接近較好區間，真正拖住整體的是大區塊與混合場景。R44E 因此只針對這兩類做短訓練，目的是確認「從已知較強來源出發，再用少量專項資料保護邊界」是否足夠。

## 完成標準

R44E 要被視為值得繼續追，至少要做到：

- 大區塊或混合場景邊界距離明顯低於 R42 / R44B from R42。
- 整體位移不能大幅退回。
- 格線位移不能回到 R40/R41 那種失控狀態。
- 代表圖要看得出邊界更忠實，而不是只是亮度或銳度改變。

## 探針設計

三個探針皆使用 R42 靜態資料中的大區塊與混合場景，並使用 R44 位移資料中的大區塊與混合場景。每個探針做 14 epoch 短訓練，每 epoch 最多 60 batches。

| 探針 | 起點 | 目的 |
|---|---|---|
| `r44e_region_mix_repair_from_r44b_r42` | R44B from R42 | 檢查主候選能不能靠小修補救回大區塊/混合場景 |
| `r44e_region_prior_from_r41` | R41 direct | 檢查 R41 的大區塊邊界先驗能不能保住 |
| `r44e_mixed_prior_from_r44b_r40` | R44B from R40 | 檢查 R44B/R40 的混合場景邊界先驗能不能保住 |

注意：這三個探針只有 14 epoch，低於主訓練器的 best 更新門檻。因此評估使用每次訓練的 `latest.pth.tar`，不是 `best_tradeoff.pth.tar`。

## 結果

數字越低越好。

| 模型 | 整體位移誤差 px | 整體邊界距離 px | 格線位移誤差 px | 大區塊邊界距離 px | 混合場景邊界距離 px |
|---|---:|---:|---:|---:|---:|
| R42 best | 0.4609 | 3.6726 | 2.7911 | 7.3401 | 6.6915 |
| R44B from R42 | 0.3813 | 3.7276 | 2.2457 | 7.5878 | 6.9202 |
| R44B from COMBO | 0.5313 | 3.9081 | 3.2741 | 5.9436 | 6.9901 |
| R44B from R40 | 0.9087 | 3.7808 | 5.9051 | 6.9774 | 5.9151 |
| R44C static heavy | 0.4011 | 3.7198 | 2.3820 | 7.7098 | 6.7994 |
| R44E repair from R44B/R42 | 0.3820 | 3.7421 | 2.2420 | 7.7581 | 6.6060 |
| R44E region prior from R41 | 1.3705 | 5.9104 | 9.1453 | 7.2545 | 7.1743 |
| R44E mixed prior from R44B/R40 | 1.0646 | 4.1191 | 6.9561 | 7.2954 | 6.6220 |

## 判讀

- `R44E repair from R44B/R42` 幾乎保住了 R44B 的整體位移，格線位移還略低一點，混合場景也比 R42 / R44B from R42 小幅變好；但大區塊與整體邊界沒有改善，所以不能算突破。
- `R44E region prior from R41` 的大區塊只比 R42 好一點，但整體位移與格線位移大幅退步，不能接受。
- `R44E mixed prior from R44B/R40` 的大區塊與混合場景都比 R42 小幅好，但格線與整體位移大幅退步，也不能接受。
- 肉眼代表圖顯示差異很小，沒有出現足以說服升級或長訓練的明確改善。

## 結論

R44E 是有價值的否定結果。

它確認「只拿大區塊/混合場景做短訓練修補」不夠。從 R41 或 R44B/R40 這類分族較強來源出發，雖然能稍微碰到目標分族，但會把格線與整體位移拉壞；從 R44B/R42 出發則能保住位移，卻救不回大區塊。

目前不建議把任何 R44E 探針作為候選，也不建議送外部 GMF。下一步如果要繼續 R44，應改成「分族目標與分族選擇機制」或「重新檢查大區塊邊界標註/量測定義」，而不是再做同型短訓練。

## 產物

| 類型 | 位置 |
|---|---|
| R44E 啟動器 | `scripts/launch_r44e_probe.py` |
| R44E 測試 | `tests/test_r44e_probe.py` |
| R44E 總表 | `results/summary/r44e_probe_summary.csv` |
| R44E 總表 JSON | `results/summary/r44e_probe_summary.json` |
| R44E 指標最佳表 | `results/summary/r44e_best_by_metric.json` |
| R44E 代表圖 | `results/visual_samples/r44e_region_mixed_probe_sheet.png` |
| R44E 重建影像 | `results/motion_recon/r44e_region_mix_repair_from_r44b_r42/` |
| R44E 重建影像 | `results/motion_recon/r44e_region_prior_from_r41/` |
| R44E 重建影像 | `results/motion_recon/r44e_mixed_prior_from_r44b_r40/` |
