# PSF 置中退步根因調查

## 核心結論

1. 目前不能把退步簡化成「只有 PSF 置中害的」。
2. 已確認 PSF 的主要變化是 alignment semantics，而非 width blow-up。
3. 已確認新 retrain run 與舊 R26 run 存在 execution / recipe drift。
4. 已確認只靠原 infer script 的 `--psf-fitted-path` 不能做純 PSF 對照；但本輪新增的 post-load override 工具已能真正改變輸出。

## 這輪最重要的新證據

- Delta matrix 顯示新 run 與舊 run 不只 PSF 不同，還有 `model_name, run_tag, amp, seed_deterministic, cudnn_deterministic, cudnn_benchmark` 等執行差異。
- PSF summary 顯示 old peak = (49, 51), new peak = (50, 50), r90 delta = 0.0120。
- Selector audit 中 `best_tradeoff` = epoch 16，但若只看主邊界集中化，較有利的候選是 `epoch_075`。
- 不過 `epoch_075` 仍未追回舊 R26 的 CNR 與弱邊界品質：old CNR_main/CNR_weak = 19.55/33.34，epoch_075 = 4.95/4.47。
- Post-load override sanity = passed，表示後續 pure-PSF isolation 已有可信工具。

## 目前最合理的暫時 verdict

最合理的暫時 verdict 是：`new centered PSF 改變了 physics prior 的對齊語意，而舊 R26 訓練/選模機制沒有一起重新校準`。
但現階段仍不能把責任全部丟給 PSF fitting formal flow，也不能把責任全部丟給 selector。
本輪證據更支持「PSF 語意變更 + recipe drift + selector mismatch 共同造成退步，其中 selector mismatch 是共犯而非完整解釋」。

## 下一步

1. 用本輪準備好的 manifest 啟動真正的 2x2 control retrain。
2. 用同一批單張/外部樣本指標回看 selector 是否需要換規則。
3. 若 old recipe + new PSF 單獨就退步，再回頭改 PSF promotion 規則。