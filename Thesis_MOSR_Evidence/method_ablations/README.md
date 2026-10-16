# Method Ablations / 方法元件消融分析

Last updated: 2026-05-26
狀態:**PLAN(子 README 寫好,launcher 草稿備好,等使用者拍板 GPU 預算後啟動)**

## 這個目錄存在的目的

論文 main claim「誤差型態轉換」已通過 Tier 1 五項判準(C1-C5)強烈成立。但這只證明「型態轉換發生在我們的 model 上」,**沒證明「是訓練架構的哪些元件造成的」**。論文 4.3 / 4.5 / 4.6 各自宣稱 PSF 校正 / 物理殘差 / 多幀一致性對主軸貢獻,**ablation 是直接驗證這些宣稱**。

寫第 6.3「方法元件歸因」必須要的章節,沒有 ablation 就只能寫「我們用了 X 跟 Y 跟 Z」,不能寫「X 貢獻了什麼,Y 貢獻了什麼」。

## 對應論文段落

| 子 ablation | 對應論文段 | 對應 main claim |
|---|---|---|
| `single_vs_multi_frame/` | 4.6 多幀序列一致性 | **驗證 4.6.1 多幀一致性是分離 σ̂/b 的關鍵架構手段** |
| `physics_residual_ablation/` | 4.5 三類物理殘差 | 驗證 4.5.4 三類殘差互相封鎖退化解 |
| `psf_calibration_ablation/` | 4.3 PSF 空間校正 | 驗證 4.3 PSF 校正讓 b 反映模型行為而非 PSF 失配 |

## 四個 ablation 子目錄

```
method_ablations/
├── README.md                                       (本檔)
├── single_vs_multi_frame/                          Ablation A
│   ├── README.md
│   ├── scripts/launch_ablation_no_seq.py
│   ├── results/
│   └── reports/
│
├── physics_residual_ablation/                      Ablation B(3 個子實驗)
│   ├── README.md
│   ├── scripts/launch_ablation_no_eq.py
│   ├── scripts/launch_ablation_no_edge.py
│   ├── scripts/launch_ablation_no_freq.py
│   ├── results/
│   └── reports/
│
└── psf_calibration_ablation/                       Ablation C(最複雜,留後)
    └── README.md
```

## 訓練設計(共用)

**從哪個起點訓**:
- Ablation A/B 從 **R30 對應的 from-scratch checkpoint 點**訓,跟 COMBO 起跑線一致
- 用 COMBO 的訓練資料(`Training_Data/generated_convolved` + `generated`)
- 跟 COMBO 同樣 epoch 數設定

**訓練 epoch 數的選擇**:

|選項|epoch|單次 GPU 時長|4 個 ablation 總時長|證據強度|
|---|---:|---:|---:|:---:|
| 完整 100 epoch(跟 COMBO 一致) | 100 | ~24h | ~96h(4 天) | **最強** |
| 中段 50 epoch(SEQ_WARMUP=15 之後仍有 35 epoch seq 監督) | 50 | ~12h | ~48h(2 天) | **強** |
| 短訓 30 epoch(僅看主要趨勢) | 30 | ~7h | ~28h | 中等 |
| 微調 24 epoch(從 COMBO 起點走) | 24 | ~6h | ~24h(1 天) | 中等(從 COMBO 起點偏 fair) |

**我建議用 50 epoch 從 scratch**:
- 100 epoch 太久,投入回報不成正比(ablation 不是為了拿 best,是為了看趨勢)
- 24 epoch 從 COMBO 起點訓不夠 fair(COMBO 已內嵌 seq 監督的歷史)
- 50 epoch from scratch 是「足夠看到型態轉換是否發生」的最低 budget

**評估 metric**:
跟 Tier 1 同套 — σ̂ + b 分解、k=2 CV、邊界熱點。直接重用既有腳本(`Thesis_MOSR_Evidence/error_type_transformation/*/scripts/`)。

## 預期結果

主軸成立的話,預期看到的 pattern:

| Ablation | 預期 σ̂ vs COMBO | 預期 b vs COMBO | 預期 k=2 CV vs COMBO |
|---|---|---|---|
| no_seq(關多幀) | **顯著升高**(隨機分量回來) | 變動不明顯 | **顯著升高**(結構不穩定) |
| no_eq(關等變性) | 持平或微升 | 變動可能變不規則 | 可能升高 |
| no_edge(關邊界微分) | 持平 | 升高(邊界位置可任意飄) | k=2 振幅整體變大 |
| no_freq(關頻域) | 可能下降(允許假高頻)| 飄移可能變大 | 可能變高 |

如果這個 pattern 出現 → 強化 main claim 對應方法元件的因果論述。

如果某個 ablation 沒有預期效應(例如 no_seq 後 σ̂ 沒升高)→ 主軸對該元件的因果宣稱要修正。

## 進度追蹤

| Ablation | 狀態 | checkpoint | 報告 |
|---|---|---|---|
| A. single_vs_multi_frame | PENDING_AUTH | — | — |
| B1. physics_residual / no_eq | PENDING_AUTH | — | — |
| B2. physics_residual / no_edge | PENDING_AUTH | — | — |
| B3. physics_residual / no_freq | PENDING_AUTH | — | — |
| C. psf_calibration | DEFERRED(implementation 複雜) | — | — |

PSF ablation(C)為什麼 defer:
- **Implementation cost 比初估低**(2026-05-26 重新評估):`PSFDeconvPhysics` 從 .mat 載入 PSF stack,我只需建一個內含「單一全域 PSF」的 .mat,model 可能自動 adapt(N=1 時 multi-candidate fusion 退化為直接 Wiener)。Cost 約 1-2 天而非 1-2 週
- 但仍需驗證 model 在 N=1 PSF 下 forward 不崩
- 對 main claim 強度的邊際效益較低(PSF 校正章雖然有,但 main claim 主要驅動是 4.5/4.6)
- **戰略上**:等 A/B 跑完看 main claim 是否需要 PSF ablation 額外證據,再啟動

## 啟動順序(等使用者拍板 epoch budget)

按 main claim 重要性 + implementation 簡單度排:

1. **Ablation A: single_vs_multi_frame** — 最重要(對應 4.6 核心主張),implementation 最簡單(關 SEQ_ENABLE flag)
2. **Ablation B-edge** — 對應 4.5.3,把 W_GRADMAG / W_EDGE_ORI_SIMPLE / W_EDGELOCAL_LAP_END 全設 0
3. **Ablation B-eq** — 對應 4.5.1,EQ_PROB = 0
4. **Ablation B-freq** — 對應 4.5.2,W_HF_LAP = 0, FFT_W_PHASE = 0(複雜度中等)
5. **Ablation C: PSF** — 延後,需個別評估

## 對 main claim 強度的意涵

- **Ablation A 跑完**:驗證 4.6 多幀一致性主張,**論文 4.6.1 改寫的科學基礎完成**
- **Ablation B 三項跑完**:驗證 4.5.4 三類殘差互相封鎖退化解的主張
- **A + B 都跑完**:第 6.3「方法元件歸因」可以完整寫
- **C 不做**:4.3 PSF 章節在論文裡仍然站得住,但「PSF 是 main claim 的必要支柱」這個論述強度較弱

main claim 不依賴任何單一 ablation——Tier 1 已通過。ablation 是讓**因果歸因**乾淨,不是 main claim 本身的 verification。
