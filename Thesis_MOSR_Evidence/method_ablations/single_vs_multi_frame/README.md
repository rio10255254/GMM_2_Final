# Ablation A:Single-frame vs Multi-frame

Last updated: 2026-05-26
狀態:**LAUNCHER_READY(等使用者啟動訓練)**

## 這個 ablation 在問什麼

論文 4.6 的核心主張是:**「多幀序列一致性訓練(SEQ)是分離 σ̂(隨機分量)跟 b(系統性分量)的關鍵架構手段——單幀訓練因為無法分辨『銳利但抖動』vs『平滑但穩定』而導致型態轉換無法被驅動。」**

這個 ablation 直接驗證:**「如果只關掉 SEQ_ENABLE,其他 hyperparameter 跟 COMBO 完全一致,型態轉換還會發生嗎?」**

如果 single-frame baseline 的 σ̂/b 配置跟 COMBO 顯著不同(例如 σ̂ 退步、k=2 CV 升高、b 變動不規則)→ **多幀一致性確實是型態轉換的關鍵驅動因素**,4.6 主張站得住。

如果 single-frame 跟 COMBO 結果差不多 → 多幀一致性不是必要的,4.6 主張要修正甚至放棄。

## 對應論文段落

- **4.6 多幀序列一致性訓練協議**:整章的因果驗證
- **4.6.1 為什麼權衡是 artifact**:這個 ablation 就是論證「為什麼權衡是 artifact」的反證——如果關掉 seq 後型態轉換失敗,就證明 seq 才是打破權衡的關鍵

## Ablation 設計

**起點**:from scratch(跟 COMBO 起跑線一致)

**訓練資料**:跟 COMBO 完全相同
- `Training_Data/generated_convolved`(輸入)
- `Training_Data/generated`(label)
- 包含環形 + 顯微結構各 stage

**hyperparameters**:跟 COMBO 完全相同,**只關掉 SEQ**
- `SEQ_ENABLE = False`(關鍵差異)
- `SEQ_LOSS_WEIGHT = 0.0`
- 其他保持跟 `r38v2_8px_gate_p95` 一致:
  - `ROBUST_LOSS_PERCENTILE = 0.95`
  - `ROBUST_LOSS_WARMUP = 10`
  - 三類物理殘差 weight 全部跟 COMBO 同(W_GRADMAG=0.8, W_EDGE_ORI_SIMPLE=0.3, W_HF_LAP=0.15, EQ_PROB=0.25)

**訓練 epoch**:50 epoch(SEQ_WARMUP_EPOCH=15 之後仍有 35 epoch 純物理殘差訓練,看是否能補上 SEQ 的角色)

**訓練命名**:`r38v2_8px_gate_p95_ABLA_NO_SEQ`(沿用 COMBO 命名加 ablation suffix)

## 評估流程

訓練完成後:

1. **跑 external GMF 三尺度**(產生 GMF_score.txt)
2. **用既有 σ̂+b 腳本算 C1+C2**:`Thesis_MOSR_Evidence/error_type_transformation/sigma_hat_decomposition/scripts/decompose_sigma_b.py` 加 candidate
3. **跑 720-angle 序列分析**(產生 sequence_summary.json)
4. **用既有 collector 算 C3+C4+C5**:`Thesis_MOSR_Evidence/error_type_transformation/k_mode_stability/scripts/collect_k2_hotspot.py` 加 candidate
5. **寫 verification report**:跟 COMBO 對比 σ̂/b/k=2/hotspot

## 預期結果(主軸成立的話)

| 指標 | COMBO(reference) | no_seq(預期) | 解讀 |
|---|---:|---:|---|
| 0.8px σ̂ | 0.132 | **≥ 0.150**(回到 R30 級) | 隨機分量回升,SEQ 移除後無法保持 |
| 0.8px |b| | 0.002 | 可能升高 | 系統性偏差不再被 SEQ 拘束 |
| 0.8px outer k=2 CV | 36.30% | **≥ 50%**(回到接近 input level) | k=2 結構穩定化失效 |
| 邊界熱點 persist_fraction | 0.114 | **降到 ≤ 0.05**(接近 R30) | 熱點集中度退步 |
| step_y_std improvement vs raw | 94.6% | **降到 ≤ 85%** | σ̂ 對 CRB 距離拉開 |

**如果這個 pattern 出現** → 強烈支持 4.6 主張
**如果 no_seq 結果跟 COMBO 接近** → 4.6 主張要修正

## 啟動指令

```bash
# 從 repo root 跑
cd D:/GMM_2_Final
python Thesis_MOSR_Evidence/method_ablations/single_vs_multi_frame/scripts/launch_ablation_no_seq.py \
    --num-epoch 50 \
    --device cuda:0
```

訓練輸出會落在:
```
Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_r38v2_8px_gate_p95_ABLA_NO_SEQ_<timestamp>/
```

## 啟動前的最後 sanity check

打勾 5 件事:
- [ ] 確認 GPU 可用(`cuda:0` 沒被其他訓練佔用)
- [ ] 確認 `Training_Data/generated_convolved` 跟 `Training_Data/generated` 完整
- [ ] 確認你接受 ~12h GPU 時長
- [ ] 確認你 OK 50 epoch(可以改成 100 epoch 走完整 COMBO 賽程,但要 ~24h)
- [ ] 確認你想單獨跑 A(我可以串接 launcher,讓 A 跑完接著跑 B-edge / B-eq / B-freq;但這要 4× 時長)

## 訓練完成後我會做的事

1. 從 `Experiments/Training_Runs/training_progress_*_NO_SEQ_*/weights/best_tradeoff.pth.tar` 拿到 checkpoint
2. 跑 external GMF 三尺度 recon(把 `Cropped_Output` 帶 BMP 過模型)
3. 跑 σ̂+b 分解(直接加到 9 候選的 table 變 10)
4. 跑 720-angle 分析(用 Analyses/AnalysisLab/r26/sequence 腳本,加新 candidate dir)
5. 寫 `reports/ablation_a_verification.md`,跟 COMBO 對比
6. 更新 `TIER_1_FINAL_VERDICT.md` 的「方法歸因」段
