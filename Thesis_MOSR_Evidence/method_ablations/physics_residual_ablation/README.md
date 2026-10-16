# Ablation B:Physics Residual Ablation

Last updated: 2026-05-26
狀態:**LAUNCHER_READY(3 個子實驗 launcher 已寫,等使用者啟動)**

## 這個 ablation 在問什麼

論文 4.5 主張三類物理殘差(平移等變性 / 頻域可行性 / 邊界微分一致性)**互相封鎖退化解** — 任一單獨關掉應該都會讓某個失效模式出現。本 ablation 個別關掉每一類,看哪個失效模式出現。

對應論文 4.5.4 排程原則 + 4.5.5 三類聯合的設計理由。

## 三個子實驗

| Tag | 關掉什麼 | 主要 trainer flags | 預期失效模式 |
|---|---|---|---|
| `no_eq` | 平移等變性 | `EQ_PROB = 0.0` | 對亞像素平移不穩定,σ̂ 升高、b 飄移不規則 |
| `no_edge` | 邊界微分一致性 | `W_GRADMAG=0`, `W_EDGE_ORI_SIMPLE=0`, `W_EDGELOCAL_LAP_START=0`, `W_EDGELOCAL_LAP_END=0` | 邊界位置任意飄,k=2 結構崩壞、|b| 升高 |
| `no_freq` | 頻域可行性 | `W_HF_LAP=0`, `FFT_W_PHASE=0` | 允許假高頻,視覺看似銳利但量測退步 |

## 跟 Ablation A 的關係

- A 證明「多幀一致性是型態轉換的訓練機制」
- B 證明「物理殘差是型態轉換的解空間 constraint」
- A 跟 B 加起來才能完整支撐 4.5+4.6 對 main claim 的因果論述

## Ablation 設計(跟 A 相同)

- **起點**:from scratch
- **訓練資料**:跟 COMBO 完全相同
- **hyperparameters**:跟 COMBO `r38v2_8px_gate_p95` 完全相同,**只關掉指定物理殘差**
- **保留 SEQ**:SEQ_ENABLE=True(SEQ 不在這條 ablation 線上)
- **訓練 epoch**:50 epoch
- **訓練命名**:`r38v2_8px_gate_p95_ABLA_NO_<EQ/EDGE/FREQ>`

## 評估流程(同 A)

每個訓完跑:external GMF → σ̂+b → 720-angle → C1-C5 → 對比 COMBO + Ablation A

最後寫一份綜合 report:`reports/ablation_b_verification.md`

## 啟動指令

```bash
cd D:/GMM_2_Final

# B1 - no_eq
python Thesis_MOSR_Evidence/method_ablations/physics_residual_ablation/scripts/launch_ablation_no_eq.py \
    --num-epoch 50 --device cuda:0

# B2 - no_edge
python Thesis_MOSR_Evidence/method_ablations/physics_residual_ablation/scripts/launch_ablation_no_edge.py \
    --num-epoch 50 --device cuda:0

# B3 - no_freq
python Thesis_MOSR_Evidence/method_ablations/physics_residual_ablation/scripts/launch_ablation_no_freq.py \
    --num-epoch 50 --device cuda:0
```

或一次串接 4 個(A + B1 + B2 + B3):

```bash
python Thesis_MOSR_Evidence/method_ablations/run_all_ablations.py --num-epoch 50 --device cuda:0
```

(`run_all_ablations.py` 在 method_ablations 根目錄)

## 預期 GPU 時長

50 epoch ~ 12h × 3 ablation = **約 36 小時 GPU**(不含 A 的 12h,所以 A+B 合計 48h)

100 epoch 完整 COMBO 賽程 × 3 = 約 72h(A+B 合計 96h)
