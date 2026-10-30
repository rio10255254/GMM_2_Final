# Round23 + Round24 Joint Postmortem
Date: 2026-03-16

## 目的
兩輪均嘗試透過 fine-tuning 加入 abs_center loss 以改善 anchor temporal consistency。

## 結果摘要

| Round | 初始化 | Loss 方法 | epoch0 center | epoch0 step | best_epoch | 結論 |
|-------|--------|-----------|--------------|-------------|------------|------|
| R23 | R22 stepguard (c=0.1845, s=0.0658) | SEQ_ABS_CENTER_WEIGHT (pairmix blended) w=0.03/0.05/0.10 | 0.1845 | 0.0658 | 0（全部） | 失敗 |
| R24 | R22 hold (c=0.1508, s=0.0783) | SEQ_SINGLE_ABS_CENTER_WEIGHT (per-frame soft_band_refine) w=0.10/0.30/0.50 | 0.1508 | 0.0783 | 0（全部） | 失敗 |

## 根本原因：Fine-tuning abs_center 路線的結構性失敗

best_epoch_is_baseline=True for ALL candidates in BOTH rounds：
- 所有 8-epoch sweep 訓練 epoch 的指標均比 epoch 0（baseline）更差
- 兩種 abs_center 公式（pairmix blended vs per-frame single）均造成退步
- Weight 大小（0.03 到 0.50）無關，結果相同

**機制分析**：
1. abs_center loss 的 gradient 方向與現有 delta loss gradient 衝突
2. 已優化的 pairmix 模型處於 delta accuracy 的局部最優點
3. 引入 abs_center gradient → 推離局部最優 → 8 epoch 不足以在新限制下重新收斂
4. 結果：每個 epoch 都比 baseline 更差，最佳為 epoch 0

## 否定假說

- **「Fine-tuning with abs_center_weight can fix anchor autocorr」** — 已否定
- 兩種 loss 公式、兩個初始 checkpoint、多個 weight 值，均無效

## 含義

- Fine-tuning 路線已窮盡（Rounds 23-24）
- R24 的 "selected" checkpoint = R22 hold baseline（因 best_epoch=0）
- R22 hold 仍是目前最好的已驗證候選（center=0.1508, external GMF std=0.2855=R18 level）

## 下一步方向

**Round25：Full training from scratch with abs_center in recipe from epoch 1**
- 不從 R22 checkpoint fine-tune，而是從 Round18 baseline 開始全量訓練
- 從第 1 個 epoch 起就包含 SEQ_SINGLE_ABS_CENTER_WEIGHT
- 模型從頭學習同時優化 delta accuracy + abs_center
- 預計需要 20-30 epochs，而非 8-epoch sweep

**候選設定（建議）**：
- SEQ_GEOM_METHOD: pairmix_algblend
- SEQ_SINGLE_ABS_CENTER_WEIGHT: 0.10（已知不會阻止 delta 優化，只在 scratch 下才有效）
- 其餘與 r22_pairmix_hold 相同
