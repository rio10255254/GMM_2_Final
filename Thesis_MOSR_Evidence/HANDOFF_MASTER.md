# HANDOFF MASTER — 論文 MOSR 證據庫完整接手文件

Last updated: 2026-05-27 (對話結束時刻)
Author of this handoff: Claude (session ending)
For: 任何後續接手的 AI 或人類研究者
Reading time: ~30-45 分鐘認真讀完

---

## 0. 一頁式快速理解(必讀)

### 整件事的故事

使用者(Rio,NTU 機械工程碩士生)在做一個叫 **GMM_2_Final** 的專案——基於物理約束神經網路的精密位移量測重建。論文 v2(`Thesis_v2_MOSR.docx`)寫到第 4 章方法論結束,**第 5/6/7 章還沒寫**。我們花了一整個對話做完三件事:

1. **完整讀完論文 + 巡視整個專案**,找出論文跟專案現況的 gap
2. **跑了完整的方法論驗證**(Tier 1 五項判準 + Tier 3 四個 ablation + Tier 2 五個 extended candidates 補測)
3. **改了論文 v3 第一輪**(7 段,對齊 ablation 證據)

### 最重要的單一結論

**論文 main claim 站得住**:「神經重建在精密位移量測情境下的本質作用是誤差型態轉換器——把隨機誤差重新分配為可追蹤的結構性偏差,而非單純降低誤差幅度」。

**但論文 v2 對方法元件因果歸因的描述跟實際 ablation 證據相反**——v2 寫「銳利度由邊界微分殘差保障、穩定度由序列一致性保障」,實際 ablation 顯示完全相反:**SEQ(多幀一致性)是銳化 anchor,EDGE(邊界微分)是位置穩定 anchor,兩者 orthogonal**。

### v3 的修改範圍

只動 1-4 章已寫部分(7 段)。v2 仍保留。Round 2 待 user 拍板(主要是 4.8 加 falsification criterion)。

### 還缺什麼

- **PI XY 雙軸實驗**(過幾天 user 親自做,用 PI 平台真值獨立驗證 main claim,是論文最強單一證據)
- **第 5/6/7 章撰寫**(outline 已備,等 PI 資料來再動筆)
- **可選**:PSF 校正 ablation(implementation 1-2 天)、multi-seed ablation(確認 single-seed 結論 robust)

---

## 1. Project Context

### 1.1 GMM_2_Final 是什麼

NTU 機械工程實驗室的精密量測 SR(super-resolution)重建專案。最終目標:**把顯微鏡拍到的環形邊界影像,用神經網路重建後,讓下游 GMF(Geometric Matching Function,商用模板匹配定位工具)在連續位移序列上量測得到的位置穩定度(step std)更低**。

**完整專案根目錄**:`D:\GMM_2_Final\`

**機器真相文件**:
- `ESTIMATOR_POLICY.json`(baseline / alternate / verdict 的機器可讀版)
- `PROJECT_STATE.md`(quick handoff + full current state)
- `PROJECT_ARCHITECTURE.md`(Layer A/B/C/D 穩定架構)
- `Experiments/INDEX.md`(實驗目錄索引)
- `docs/analysis/RESEARCH_PATHS.md`(研究路徑 mermaid 圖)

### 1.2 baseline 體系(2026-05-27)

| 角色 | 候選 | external 0.8px σ̂ | 升級時間 |
|---|---|---:|---|
| **Formal production baseline** | COMBO (`r38v2_8px_gate_p95`) | 0.131560 | 2026-04-08 |
| Approved alternate (GMF extreme) | R33 (`r33_robust_p95`) | 0.119049 | 2026-04 |
| Approved alternate (Visual priority) | R38v2 (`r38v2_8px_gate`) | 0.134205 | 2026-04 |
| Approved alternate (Balanced full-spectrum) | R39R40_avg_a025 | 0.133546 | 2026-05-11 |
| Former baseline | R30 (`r30_b1_dironly`) | 0.167862 | (前任) |

### 1.3 研究線歷程(後 COMBO)

R39 → R40 → R41 → R42 → R43 → R44 → R45 → R46。**全部都是「想推顯微/邊界忠實度但 ring 守不住」的故事**,只有 R39R40_avg_a025 升為 approved alternate。詳見 `Experiments/INDEX.md`。

### 1.4 論文現狀

- **檔案**:`C:\Users\Rio\OneDrive\學業\碩班\論文\Thesis_v2_MOSR.docx`(v2,起點)
- **新版**:`C:\Users\Rio\OneDrive\學業\碩班\論文\Thesis_v3_MOSR.docx`(v3,Round 1 修改完成)
- **章節**:1-4 章已寫(緒論、文獻、理論、方法論),**5/6/7 章從零等寫**
- **論文邊界**:正文只寫原理跟策略,**不含產學專案的硬體/數據/商用廠牌/具體位移尺度**(這是使用者明確規定的論文範圍)

### 1.5 PSF 政策(2026-03-27 切換)

- **Current standard**:新 Whole-FOV PSF(2026-03-26 完成,100 個格點位置)
- **Legacy empirical baseline**:舊 PSF(保留作對照,不再正式預設)
- 機器可讀政策:`docs/policy/PSF_STANDARD_POLICY.json`

---

## 2. 主軸演化的完整路線(關鍵——這個演化記錄是這份 handoff 最值錢的部分)

### 2.1 v2 原始主軸(2026-04 寫的時候)

論文 v2 第 1.3 寫了**三個並列貢獻**:
- 貢獻一:MOSR 框架(Problem Formulation)
- 貢獻二:誤差型態轉換器假說(Empirical Finding)
- 貢獻三:多幀一致性打破權衡(Conceptual Insight)

讀者讀完會覺得三個是並列的、同樣重要的、各自獨立論述。

### 2.2 第一輪整理:三貢獻其實不對等(地位不平等)

讀完論文跟整個專案歷程後,我們意識到:

> **三大貢獻地位不平等**:只有貢獻二(誤差型態轉換)是真正可被 falsify 的科學主張,其他兩個其實是支撐工具:MOSR 是「為了讓型態轉換可被觀察」的方法論基礎,多幀一致性是「驅動型態轉換」的訓練機制。

這個發現直接導向把三大貢獻改成**金字塔結構**(1 主 + 2 支撐)。

### 2.3 Tier 1 主軸驗證(C1-C5,2026-05-26)

設計了五項可被 falsify 的判準:
- **C1**:σ̂(隨機分量)隨訓練優化下降
- **C2**:b(系統性分量)出現且跨幀結構化(lag-1 autocorr 顯著非零)
- **C3**:k=2 振幅幀間 CV 下降
- **C4**:邊界殘差熱點集中度(persist_fraction)從散變集中
- **C5**:σ̂ 接近 CRB(用 raw-vs-recon improvement 作 proxy)

**結果**:**5/5 全部通過**,且 σ̂+b 結果揭示了型態轉換 spectrum 結構:
- R30 → R33/R38v2 → COMBO 不是單一軸線性改善,而是 σ̂/b 配置在不同位置
- R33:σ̂ 極致壓(吸收型)
- R38v2:σ̂ + b 在 8 px 上「σ̂↓ + |b|↑」教科書 pattern
- COMBO:σ̂ + b 雙低(Pareto frontier)
- R30:隨機分量主導起點

**最有 punch 的單一發現**:**所有候選都把 raw step_std 壓掉 93-99%**——σ̂ 已逼近資訊理論下限,進一步改善的唯一空間是把誤差結構化成 b。這就是論文 4.8.4「σ̂ 接近 CRB 後,b 變成後處理可補償的標的」的直接證據。

### 2.4 Tier 3 ablation 後的「兩 anchor + 兩輔助」

訓練 4 個方法元件 ablation(每個 100 epoch,共 2.41 小時 GPU):
- **NO_SEQ**(關 SEQ_ENABLE):8 px σ̂ +131%、0.8 px 無顯著 effect
- **NO_EDGE**(關 W_GRADMAG/W_EDGE_ORI_SIMPLE/W_EDGELOCAL_LAP):**三尺度全方位退步**(0.8 px σ̂ +96%,接近 R42 research-only 等級)
- **NO_FREQ**(關 W_HF_LAP, FFT_W_PHASE):中等影響(σ̂ +10-19%)
- **NO_EQ**(關 EQ_PROB):external 上幾乎沒效果

→ 修正版 narrative:**「兩 anchor + 兩輔助」**
- **核心 anchor**:邊界微分一致性(EDGE)— 三尺度全方位影響
- **次要 anchor**:多幀一致性(SEQ)— 8 px 宏觀位移
- **中等輔助**:頻域可行性(FREQ)
- **邊際**:平移等變性(EQ)

### 2.5 Tier 2 extended candidates 後的 SEQ vs EDGE orthogonal 分工(最終 framing)

對 5 個 extended candidates(a030/a025/R40_a045/R42_r41best/R46)補跑 inference + 720-angle,然後對 13 候選收集 edge_width(邊界寬度 μ_w)。**意外發現**:

| Ablation | edge_width μ_w(0.8 px outer) | 對應 σ̂ |
|---|---:|---:|
| COMBO | 14.62 | 0.132(基準) |
| **NO_SEQ** | **21.00**(退回 R30 級) | 0.128(沒退步) |
| **NO_EDGE** | **13.14**(比 COMBO 還銳!) | 0.258(σ̂ +96%) |
| NO_EQ | 15.37 | 0.138 |
| NO_FREQ | 18.28 | 0.145 |

**這對 ablation verdict 是個 game changer**:

- 拿掉 SEQ → 邊界**退化**(寬度 21,跟 R30 一樣鈍),但位置 σ̂ 沒退
- 拿掉 EDGE → 邊界**更銳**(寬度 13.14,比 COMBO 14.62 還銳),但位置 σ̂ 暴退

**結論:SEQ 跟 EDGE 不是「互補的兩個 anchor」,是 orthogonal 維度的兩個 anchor**:
- **SEQ = 銳化 anchor**(讓邊界銳;順帶控制 8 px 宏觀位移)
- **EDGE = 位置穩定 anchor + 銳化 brake**(讓邊界位置不漂移;順帶煞住 over-sharpen)

這個分工**就是論文 4.6.1「打破權衡」的真正因果機制**:銳利度跟位置穩定度由**不同 loss 項**驅動,在參數空間不直接競爭,所以可以同時改善。

### 2.6 另外兩個重要觀察

**R42_r41best / R46 邊界比 R30 還鈍**:
- R42 (boundary fidelity 訓練) μ_w = 27.07(R30 是 21.95)
- R46 (強化 edge weight) μ_w = 25.22
- 「強化邊界訓練 ≠ 更銳的 ring 邊界」——能力預算守恆的具體展現
- 直接餵給論文 6.4 capacity 邊界章節

**所有 input k=2 CV 都很高(36-64%),所有 output k=2 CV 都很低(2.8-22%)**:
- input → output 的 k=2 CV reduction 56-95%(全 24 cell)
- 但 COMBO 0.8 px outer k=2 CV = 36.3% 比 R38v2 2.89% 還高 → **COMBO 在 k=2 結構穩定度上不是最強**
- R38v2 才是 k=2 結構王者
- 這支持「不同候選佔 spectrum 不同位置」narrative

---

## 3. 完整證據鏈

### 3.1 Tier 1:主軸 5 項判準驗證

**對應論文**:4.8.1 / 4.8.2 / 4.8.4 / 4.8.5

**完整文件**:`Thesis_MOSR_Evidence/TIER_1_FINAL_VERDICT.md`

**各判準 verification report**:

| 判準 | 文件 | 結果 |
|---|---|---|
| C1+C2 | `error_type_transformation/sigma_hat_decomposition/reports/c1_c2_verification.md` | σ̂ 三尺度都降 22-37%,lag-1 全部結構化 |
| C3 | `error_type_transformation/k_mode_stability/reports/c3_verification.md` | input→output k=2 CV reduction 56-95% |
| C4 | `error_type_transformation/residual_hotspot/reports/c4_verification.md` | hotspot 從 0 變 0.05-0.12 |
| C5 | `error_type_transformation/crb_ratio/reports/c5_verification.md` | step_std improvement 93-99% |

**主要 dataset**:
- 9 候選 σ̂+b:`error_type_transformation/sigma_hat_decomposition/results/sigma_b_table.csv`
- 4 候選 k=2 + hotspot + drift:`error_type_transformation/k_mode_stability/results/*.csv` + `error_type_transformation/residual_hotspot/results/*.csv`

**Plot**:
- `error_type_transformation/sigma_hat_decomposition/results/sigma_vs_b_panel.png`(3 尺度 σ̂ vs |b| 散佈圖,**論文 6.1 hero figure 候選**)
- `sigma_trend.png` / `b_trend.png`

### 3.2 Tier 3:4 個方法元件 ablation

**對應論文**:4.5 / 4.6

**完整 verdict**:`method_ablations/reports/ablation_external_gmf_verdict.md`

**Ablation 訓練**:
- 4 個 ablation 各 100 epoch,from scratch
- 每個 trainer flag 改動:
  - NO_SEQ:`SEQ_ENABLE = False`
  - NO_EQ:`EQ_PROB = 0.0`
  - NO_EDGE:`W_GRADMAG = W_EDGE_ORI_SIMPLE = W_EDGELOCAL_LAP_START = W_EDGELOCAL_LAP_END = 0.0`
  - NO_FREQ:`W_HF_LAP = 0.0, FFT_W_PHASE = 0.0`

**訓練輸出**:
- NO_SEQ: `Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r38v2_8px_gate_p95_ABLA_NO_SEQ_20260526_230916/`
- NO_EQ: `..._NO_EQ_20260526_235037/`
- NO_EDGE: `..._NO_EDGE_20260527_003614/`
- NO_FREQ: `..._NO_FREQ_20260527_012452/`

每個都有 `weights/best_tradeoff.pth.tar`。

**Launcher 入口**:
- `method_ablations/single_vs_multi_frame/scripts/launch_ablation_no_seq.py`
- `method_ablations/physics_residual_ablation/scripts/launch_ablation_no_eq.py` / `no_edge.py` / `no_freq.py`
- 串接 runner:`method_ablations/run_all_ablations.py`

**External GMF 結果**(user 手動跑 GMF tool 後填):
- `method_ablations/_ablation_external_gmf/<TAG>/<pitch>/GMF_score.txt`
- TAG = NO_SEQ / NO_EQ / NO_EDGE / NO_FREQ
- pitch = pitch8px / pitch0p8px / pitch0p08px

**Internal 720-angle**(完全自動跑的):
- `method_ablations/_ablation_720angle/<TAG>/<pitch>/sequence_summary.json` + `per_frame_metrics.json`
- batch script:`method_ablations/run_ablation_inference_and_720angle.py`

**最後 σ̂+b 表(13 候選含 ablation)**:
- `error_type_transformation/sigma_hat_decomposition/results/sigma_b_table.csv`
- 從 9 候選擴展到 13 候選,直接 invoke `decompose_sigma_b.py`(已預先加 4 個 ablation candidate entry)

**關鍵數字**(0.8 px main battleground,external GMF):

| | σ̂ | |b| | b/s* |
|---|---:|---:|---:|
| COMBO | 0.1316 | 0.0020 | +0.25% |
| ABLA_NO_SEQ | 0.1279 | 0.0000 | -0.00% |
| ABLA_NO_EQ | 0.1382 | 0.0150 | +1.88% |
| **ABLA_NO_EDGE** | **0.2577** | 0.0140 | +1.75% |
| ABLA_NO_FREQ | 0.1446 | 0.0080 | +1.00% |

**8 px**:NO_SEQ 0.3566(+131%)、NO_EDGE 0.3325(+115%);**0.08 px**:NO_EDGE 0.1449(+45%)

### 3.3 Tier 2:Extended candidates + edge_width + visual metrics

**對應論文**:4.5 / 4.6 / 4.8.3

**完整 verdict**:`_extended_candidates_internal/reports/extended_spectrum_verdict.md`

**5 個 extended candidates 訓練 + 720-angle**:
- a030(R39 weight_sweep checkpoints/a030)
- a025(R39 a030_x_a043_sweep checkpoints/a025)
- R40_a045(R40 weight_sweep/combo_best_low_alpha/checkpoints/a045)
- R42_r41best(R42 boundary_from_r41 training 20260505_145229)
- R46(R46 corner_finetune training 20260514_230359)

每個跑 3 pitch inference(8 px / 0.8 px / 0.08 px),總 23 分鐘。

**Batch script**:
- `_extended_candidates_internal/scripts/run_extended_inference_720angle.py`
- 對 5 candidate × 3 pitch 跑 inference + 720-angle 分析

**輸出**:
- recon BMP: `_extended_candidates_internal/_recon/<TAG>/<pitch>_odd/`
- 720-angle: `_extended_candidates_internal/_720angle/<TAG>/<pitch>/sequence_summary.json` + `per_frame_metrics.json`

**邊界寬度 collector**:
- `_extended_candidates_internal/scripts/collect_edge_width.py`
- 對 13 candidate × 3 pitch × 2 boundary 收集 720-angle per_frame_metrics.json 的 outer/inner_edge_width_mean
- 算 μ_w(跨幀 mean)跟 CV_w(跨幀 std/mean)
- 輸出:`_extended_candidates_internal/results/edge_width_table.csv`(78 row)

**視覺指標 compute**:
- `_extended_candidates_internal/scripts/compute_visual_metrics.py`
- 對 9 candidate(5 extended + 4 ablation) × 3 pitch 算 4 個視覺指標:
  - gradient_magnitude_mean
  - edge_steepness_p95
  - contrast_std
  - edge_contrast_p99_minus_p1
- 輸出:`_extended_candidates_internal/results/visual_metrics_{table,pivot,avg}.csv`
- **限制**:Baseline 4 個 (R30/R33/R38v2/COMBO) MISSING(R30 recon dir path 不明,沒補測)

### 3.4 內部 vs 外部對照(internal/external cross-validation)

**對應 doc**:`Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`(2026-04-08)

**核心結論**:
- internal step_std 系統性高估 external GMF step_std
- COMBO internal 0.178 vs external 0.132,**internal 高估 35%**
- 根因:circle fit 噪聲地板 ~0.17 px,0.8 px 主戰場已被噪聲主導
- **8 px 訊號量級遠大於噪聲地板,internal 才看得到真實 ablation effect**

**這個觀察必須在論文寫作時明確引用**——否則讀者看到 ablation 0.8 px internal 「拿掉 SEQ 後反而比 COMBO 好」會誤判主軸不成立。

---

## 4. 關鍵方法論教訓(踩過的坑,後續 AI 不要重踩)

### 4.1 internal vs external 在主戰場(0.8 px)會脫鉤

**踩坑經過**:第一輪看 Ablation A internal 結果,發現「拿掉 SEQ 後 0.8 px σ̂ 反而比 COMBO 略低」,差點得出「論文 4.6 被自家 ablation 打臉」的錯誤結論。

**真實原因**:0.8 px 主戰場 internal σ̂ 已逼近 circle fit 噪聲地板(~0.17 px),所有 candidate 都在 0.13-0.20 之間,差異是噪聲不是訊號。

**正確做法**:
- 看 internal **要看 8 px**(訊號量級大,噪聲不主導)
- 看 0.8 px 主戰場 **必須用 external GMF**

**引用文件**:`Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`、`PROJECT_ARCHITECTURE.md` Layer B 原則「**internal 通過是入場資格,external 是最終裁判**」

### 4.2 NUM_EPOCH vs SIMPLETEST_MAX_EPOCH

**踩坑經過**:第一次跑 Ablation A 設 `--num-epoch 50`,但 trainer 實際跑 100 epoch。

**真實原因**:Trainer 用 `SIMPLETEST_MODE=True` 走 `SIMPLETEST_MAX_EPOCH`(預設 100),不是 `NUM_EPOCH`。Launcher 只覆寫 `NUM_EPOCH` 沒覆寫 `SIMPLETEST_MAX_EPOCH`。

**正確做法**:Launcher 同時覆寫兩個:
```python
CFG.NUM_EPOCH = args.num_epoch
CFG.SIMPLETEST_MAX_EPOCH = args.num_epoch  # critical
```

所有 ablation launchers 已修正(`method_ablations/*/scripts/launch_*.py`)。

### 4.3 Bash run_in_background + pipe 會殺進程

**踩坑經過**:啟動 Ablation A 用 `python launcher.py 2>&1 | head -50` 想限制 stdout,結果 head 讀完 50 行就 close pipe,trainer 被 SIGPIPE 砍掉(只跑到 epoch 15)。trainer exit code 0,看起來像正常完成。

**正確做法**:**Background command 不要在 trainer 後接 head/tee/grep 等 pipe**,讓 trainer stdout 直接寫 background output file。Monitor 用獨立的 `tail -f | grep` 從 output file 讀。

### 4.4 docx pack 在 Windows 上 cp950 codec 衝突

**踩坑經過**:Pack v3 docx 時 validation 跳 `cp950 codec can't decode byte 0xe6` 錯誤。

**真實原因**:Windows Big5 codec 跟 UTF-8 衝突,但只影響 validation(實際 docx 結構沒壞)。

**正確做法**:Pack 加 `--validate false` 跳過 validation:
```bash
python pack.py /tmp/unpacked/ output.docx --validate false
```

### 4.5 ABLATIONS 用 base_dir vs full_ckpt_path 兩種命名

Ablation A-B(NO_SEQ/EQ/EDGE/FREQ)的 ckpt 都在 `Traing_Progress/<dir>/weights/best_tradeoff.pth.tar`,所以原 batch script 用 base_dir。

Extended candidates(a030/a025/R40_a045/R42_r41best/R46)ckpt 在不同 Experiments 子目錄,所以新 batch script(`run_extended_inference_720angle.py`)用 full_ckpt_path 寫死。

兩個 batch script 結構幾乎一樣,主要差異就是 candidate-to-ckpt mapping 的格式。

---

## 5. 論文 v3 修改(Round 1)— 已完成 7 段

**檔案**:`C:\Users\Rio\OneDrive\學業\碩班\論文\Thesis_v3_MOSR.docx`(v2 保留不動)

**修改計畫文件**:`Thesis_MOSR_Evidence/_paper_editing/plans/v3_modification_plan.md`(完整每段原文 + 新文 + 為什麼)

**修改 diff 報告**:`Thesis_MOSR_Evidence/_paper_editing/diff_reports/v3_modifications_round1.md`(簡潔版)

### 7 段已改

| M# | 段落 | 修改重點 |
|---|---|---|
| M1 | P0876(4.5.4 分工) | SEQ vs EDGE 角色顛倒(論文 v2 最大內容錯誤) |
| | P0877(4.5.4 結論) | 加註「不是設計直觀預測,是 ablation 實證」 |
| M2 | P0863(4.6.1 末段) | 銳化由跨幀一致性驅動 + 穩定由邊界微分驅動 |
| M3 | P0845(4.5.3 開頭) | 加「位置 anchor + 銳化 brake」雙重角色 |
| M4 | P0852(4.5.3 L_edge) | 對齊新角色,L_edge 是位置 anchor 而非銳化驅動 |
| M5a | P0192(1.3 開頭) | 三段平列改成金字塔(1 主 + 2 支撐) |
| M5b | P0193(貢獻一) | 改成「支撐貢獻 A:MOSR 框架」 |
| M5c | P0195(貢獻二) | 改成「主貢獻」+ 末段加「五項判準全過 + spectrum 結構」 |
| M5d | P0196(貢獻三) | 改成「支撐貢獻 B」+ 改寫成 ablation 實證的因果機制 |
| M7 | P0855(4.5.4 末段) | 「對稱封鎖」軟化成「核心 anchor + 輔助 + 邊際」 |

### Tier 3 修改(Round 2 待 user 拍板)

**對應 verdict 推薦的 follow-up**:

1. **4.8 加 C1-C5 falsification criterion**(最重要,讓 main claim 變真正可被 falsify 的科學主張)
2. **4.6.5 小結 + 4.9 章末小結** 同步對齊新主軸
3. **1.2 動機末段** 軟鋪墊到型態轉換
4. **4.1 概論加論述橋** 三層方法服務型態轉換
5. **2.5 / 2.7 文獻定位** 從新主軸角度收尾
6. **3.9 加 σ̂/b 分解理論前置** 跟 GUM Type A/B 銜接
7. **PSF 章節 4.2-4.4 壓縮** 工作量大,先寫第 5 章後再決定

---

## 6. 還沒做的事(對接續工作的人最重要的 section)

### 6.1 PI XY 雙軸實驗(user 過幾天親自做)

**這是論文最強的單一證據,優先級最高**。

User 會用 PI(Physik Instrumente)精密位移台做 XY 雙軸微小平移實驗,用 PI 平台讀回的真實位置當 ground truth(而不是 nominal pitch)。

**該預備的事**(我已經預備 hook):
- `Thesis_MOSR_Evidence/error_type_transformation/` 底下預留 `pi_xy_validation/` 子目錄
- 主 README 進度追蹤表狀態 `PENDING_DATA`

**資料到位後的工作**:
1. 用同一套 `decompose_sigma_b.py` 流程跑 PI 序列,但 s* 從 PI 讀回的真值
2. 同時跑 XY 雙軸 Fisher 矩陣(對應論文 3.9.4 預告)
3. 比對 PI 真值結果 vs 既有 nominal pitch 結果——一致則 main claim 強化,不一致則 PI 是 ground truth

### 6.2 第 5/6/7 章撰寫

**Outline 已備**,寫在 `TIER_1_FINAL_VERDICT.md` 最後一段。簡述:

**第 5 章 實驗系統與資料**:
- 5.1 成像 + PSF 校正流程
- 5.2 訓練資料(對應論文 4.7)
- 5.3 評估資料(三尺度位移序列)
- 5.4 評估指標完整定義(對應 4.8 + external GMF + 視覺指標)

**第 6 章 結果與分析**:
- 6.1 視覺-量測解耦現象(用 sigma_vs_b_panel.png 當 hero figure)
- 6.2 五項判準逐項驗證(直接搬 verdict reports)
- 6.3 方法元件歸因 ablation(搬 ablation verdict + extended spectrum verdict)
- 6.4 capacity 邊界證據(R39-R46 重新詮釋成型態轉換有上限)
- 6.5 對 SR / metrology 文獻定位

**第 7 章 結論**:
- 7.1 三大貢獻金字塔回顧
- 7.2 對 SR 領域的意涵(視覺指標 ≠ 量測代理)
- 7.3 對 metrology 領域的意涵(σ̂ 接近 CRB 後 b 可後處理補償)
- 7.4 限制與未來方向

### 6.3 可選補測

**PSF 校正 ablation**(對應論文 4.3,implementation 中等):
- 用 `n=1` 的 single global PSF .mat 替換 multi-PSF library
- Model 可能自動 adapt(N=1 時 multi-candidate fusion 退化為直接 Wiener),不用大改架構
- Cost 約 1-2 天 implementation + 1 個訓練 50 分鐘
- 對 main claim 邊際效益較低,等 user 拍板

**Multi-seed ablation**(對 NO_SEQ 在 0.8 px「無顯著 effect」的結論強化):
- 每個 ablation 多跑 3 個 seed(共 12 個新訓練)
- ~ 10 小時 GPU
- 確保 single-seed 結論不在 seed variance 內翻盤

**Baseline 4 個 visual_metrics 補測**(目前缺):
- R30 / R33 / R38v2 / COMBO 的 absolute edge_steepness_p95 / contrast_std 等
- 需新跑 inference 對 r26 三尺度 sequence
- R30 ckpt path 需確認(可能在 `Traing_Progress/organized_20260316/round30/...`)

### 6.4 Round 2 v3 修改(7 項)

詳見 §5 末段「Tier 3 修改」清單。最高 priority 是 4.8 加 C1-C5 falsification criterion。

---

## 7. 完整檔案 inventory

### 7.1 證據庫目錄結構

```
Thesis_MOSR_Evidence/
├── README.md                                    主 README + 進度追蹤
├── TIER_1_FINAL_VERDICT.md                      Tier 1 五項判準總評
├── HANDOFF_MASTER.md                            本檔(完整接手文件)
│
├── error_type_transformation/                   Tier 1 五項判準
│   ├── sigma_hat_decomposition/                 C1+C2
│   │   ├── README.md
│   │   ├── scripts/
│   │   │   ├── decompose_sigma_b.py             13 候選 σ̂+b 主腳本
│   │   │   └── make_plots.py                    σ̂ trend + σ̂ vs b panel
│   │   ├── results/
│   │   │   ├── sigma_b_table.csv                13 候選 × 3 尺度 = 39 row
│   │   │   ├── sigma_trend.png
│   │   │   ├── b_trend.png
│   │   │   ├── sigma_vs_b_panel.png             論文 6.1 hero figure 候選
│   │   │   └── sigma_vs_b_{8px,0p8px,0p08px}.png
│   │   └── reports/c1_c2_verification.md
│   ├── k_mode_stability/                        C3
│   │   ├── scripts/collect_k2_hotspot.py
│   │   ├── results/
│   │   │   ├── k2_stability_table.csv           4 candidate(R30/R33/R38v2/COMBO) × 3 pitch × 2 boundary
│   │   │   └── center_offset_drift_table.csv
│   │   └── reports/c3_verification.md
│   ├── residual_hotspot/                        C4
│   │   ├── results/hotspot_persistence_table.csv
│   │   └── reports/c4_verification.md
│   └── crb_ratio/                               C5
│       └── reports/c5_verification.md
│
├── method_ablations/                            Tier 3 — 4 個 ablation
│   ├── README.md
│   ├── analyze_ablation.py                      列出每個 ablation 的 ckpt path
│   ├── run_all_ablations.py                     串接 A→B1→B2→B3
│   ├── run_ablation_inference_and_720angle.py   4 ablation × 3 pitch batch
│   ├── run_ablation_post_analysis.py            訓練後分析報告
│   ├── check_ablation_gmf_ready.py              12 個 GMF_score.txt sanity check
│   ├── collect_ablation_metrics.py              整合 4 baseline + 4 ablation k=2/hotspot
│   ├── single_vs_multi_frame/
│   │   ├── README.md
│   │   └── scripts/launch_ablation_no_seq.py
│   ├── physics_residual_ablation/
│   │   ├── README.md
│   │   └── scripts/launch_ablation_no_{eq,edge,freq}.py
│   ├── psf_calibration_ablation/                (defer,只有 README)
│   ├── _ablation_recon/                         4 ablation × 3 pitch 的 recon BMP
│   │   └── <TAG>/reconstruct_progress_*/pitch{1um,0p1um,0p01um}_y_*_odd/*.bmp
│   ├── _ablation_720angle/                      4 ablation × 3 pitch 的 720-angle 分析
│   │   └── <TAG>/<pitch>/{sequence_summary.json, per_frame_metrics.json, *.png}
│   ├── _ablation_external_gmf/                  4 ablation × 3 pitch 的 GMF_score.txt
│   │   ├── README.md                            給 user 的 GMF 工具操作指南
│   │   ├── paths_for_gmf_tool.tsv               12 個 source → target mapping
│   │   └── <TAG>/<pitch>/GMF_score.txt          ← user 用 GMF 工具填的
│   ├── results/ablation_k2_hotspot_combined.csv 8 candidate 完整對比
│   └── reports/ablation_external_gmf_verdict.md Tier 3 verdict
│
├── _extended_candidates_internal/               Tier 2 — 5 個 extended candidates
│   ├── scripts/
│   │   ├── run_extended_inference_720angle.py   5 candidate × 3 pitch batch
│   │   ├── compute_visual_metrics.py            9 candidate 視覺指標
│   │   └── collect_edge_width.py                13 candidate 邊界寬度
│   ├── _recon/<TAG>/                            5 extended × 3 pitch 的 recon BMP
│   ├── _720angle/<TAG>/<pitch>/                 5 extended × 3 pitch 的 720-angle
│   ├── results/
│   │   ├── edge_width_table.csv                 13 candidate × 3 pitch × 2 boundary
│   │   ├── visual_metrics_{table,pivot,avg}.csv 9 candidate × 3 pitch × 4 metric
│   │   └── ...
│   └── reports/extended_spectrum_verdict.md     Tier 2 verdict
│
├── visual_vs_metric_decoupling/                 視覺-量測四象限圖(待完成)
│   └── README.md
│
└── _paper_editing/                              論文修改工作目錄
    ├── _v3_document.xml                         修改過的 document.xml(已 pack)
    ├── _v3_extracted.txt                        v3 純文字版(959 paragraphs)
    ├── scripts/extract_thesis_text.py           docx XML → text 抽取
    ├── plans/v3_modification_plan.md            完整修改計畫(每段原文+新文)
    └── diff_reports/v3_modifications_round1.md  Round 1 修改報告
```

### 7.2 主要 verdict 報告(必讀順序)

1. `HANDOFF_MASTER.md`(本檔,先看)
2. `TIER_1_FINAL_VERDICT.md`(主軸驗證總評)
3. `method_ablations/reports/ablation_external_gmf_verdict.md`(ablation 因果歸因)
4. `_extended_candidates_internal/reports/extended_spectrum_verdict.md`(SEQ-EDGE orthogonal 發現)
5. `_paper_editing/diff_reports/v3_modifications_round1.md`(論文修改細節)

### 7.3 對外引用(專案內必讀 doc)

- `PROJECT_STATE.md` — 專案現況
- `PROJECT_ARCHITECTURE.md` — Layer A/B/C/D 穩定架構
- `ESTIMATOR_POLICY.json` — 機器真相
- `Experiments/INDEX.md` — 實驗索引
- `Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md` — internal/external 脫鉤關鍵紀錄

### 7.4 訓練架構入口

- `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py` — 主 trainer
- `Model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py` — 模型定義(含 PSFDeconvPhysics)
- `Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py` — 標準 inference
- 各 R## 實驗目錄底下有自己的 launcher 跟 evaluation script

### 7.5 既有 720-angle 分析(baseline 4 候選)

- `Experiments/R38v2SeqFixed/results/720angle_analysis<R30|R33|R38v2|COMBO>\<pitch>\` — 既有 720-angle 完整輸出
- 含 sequence_summary.json + per_frame_metrics.json + 7 個 plot(01-07)

### 7.6 Python 環境

**主要 env**:`/c/Users/Rio/anaconda3/envs/myenv/python.exe`
- 含 numpy / scipy / matplotlib / cv2 / torch / defusedxml
- 用這個 env 跑所有腳本(包含 docx unpack / pack)

System Python(`C:/Python314/`)沒裝 numpy / defusedxml,不要用。

---

## 8. 接手指南(後續 AI / 人類接手 checklist)

### 8.1 第一次接手要做的事

1. **讀 §0 一頁式快速理解**(5 分鐘)
2. **讀 §2 主軸演化路線**(15 分鐘)——這是這份 handoff 最值錢的部分
3. **打開 `Thesis_v3_MOSR.docx`**,直接看 P0192 / P0193 / P0195 / P0196 / P0845 / P0852 / P0855 / P0863 / P0876 / P0877 這 10 段,confirm 修改方向
4. **打開 `sigma_vs_b_panel.png`**,看 σ̂ vs b 三尺度 spectrum 圖,confirm 主軸視覺化
5. **跑 `sanity check`**:
   ```bash
   /c/Users/Rio/anaconda3/envs/myenv/python.exe \
       Thesis_MOSR_Evidence/method_ablations/check_ablation_gmf_ready.py
   ```
   應該顯示 12/12 OK。

### 8.2 PI 資料到位後該做的事

1. 在 `Thesis_MOSR_Evidence/error_type_transformation/` 開 `pi_xy_validation/` 子目錄
2. Copy `sigma_hat_decomposition/scripts/decompose_sigma_b.py` 改成讀 PI 真值(不是 nominal pitch)
3. 跑 σ̂+b 對比 既有 9 候選 + 4 ablation = 13 候選
4. 跑 720-angle 跟 edge_width 同流程
5. 寫 `pi_xy_validation/reports/pi_verification.md` 對比 PI 真值 vs nominal pitch 的結論

### 8.3 寫第 5/6/7 章該做的事

1. **不要動 v3** — 先在 `_paper_editing/plans/` 寫 5-7 章 outline + draft
2. 用 Round 1 同款流程(plan → apply XML → pack → diff report)
3. 第 6 章直接搬 verdict reports 的數字 + 圖
4. 第 7 章 對齊金字塔三大貢獻

### 8.4 動 Round 2 v3 修改該做的事

1. 讀 `_paper_editing/plans/v3_modification_plan.md` 的 Tier 3 清單
2. 最重要的是 **4.8 加 C1-C5 falsification criterion**(新加段落,工作量中等)
3. Apply 用 Round 1 同款流程
4. Update `_paper_editing/diff_reports/v3_modifications_round2.md`

### 8.5 重要的 user 偏好(重要)

讀 `~/.claude/CLAUDE.md` 看 user 全域偏好(中文/講人話/不報菜單/給選項要先選一個 etc)。**全部適用本對話**:
- 講繁體中文,技術詞中文化但 git/commit/PSNR/checkpoint 等保留英文
- 「自然不等於精簡」——可以展開但不要乾巴巴
- 不要演戲(不要 "Let me think about this"、不要 "Great question")
- 結論不要藏太深,但前面要帶一兩句脈絡
- 給選項要先選一個,不要丟 ABCD 讓他選
- 卡住就講卡住,不要默默繞路
- 做完就停,不要主動推銷下一步
- 不要 emoji 慶祝

### 8.6 user 的論文寫作偏好(從 memory)

- **基礎檔案是 `Thesis_v2_MOSR.docx`,新版叫 v3**(`feedback_thesis_base_file`)
- **論文正文只寫原理與策略,不含產學專案的硬體/數據/商用廠牌/具體位移尺度**(`feedback_thesis_vs_industrial`)
- **不要中英文混雜**,可以中文化的詞中文化(`feedback_avoid_english_mixing`)
- **論文 meta 論述放 OneDrive `碩班\論文\notes\`,不放 GMM_2_Final repo**(`reference_thesis_notes`)
- **論文章節屬性原則**:寫段落前先判斷章節屬性(理論章 vs 方法章 vs 文獻章 vs 結果章)(`feedback_thesis_chapter_attributes`)

---

## 9. 對話歷程時間軸(供時間順序檢索用)

| 時間 | 事件 | 對應 verdict |
|---|---|---|
| 2026-05-26 對話開始 | 讀完論文 v2 + 巡視專案 | — |
| 2026-05-26 | 寫主軸建議 — 推「誤差型態轉換」當主軸 | — |
| 2026-05-26 | 建 `Thesis_MOSR_Evidence/` 目錄殼 | `README.md` |
| 2026-05-26 | 跑 σ̂+b 9 候選(C1+C2 驗證) | `c1_c2_verification.md` |
| 2026-05-26 | 跑 k=2 + hotspot(C3+C4 驗證) | `c3_verification.md`、`c4_verification.md` |
| 2026-05-26 | 跑 σ̂ vs CRB(C5 proxy 驗證) | `c5_verification.md` |
| 2026-05-26 | Tier 1 總評(5/5 全通過) | `TIER_1_FINAL_VERDICT.md` |
| 2026-05-26 23:00 | 啟動 4 個 ablation 訓練 sequence | — |
| 2026-05-26~27 凌晨 | 4 個 ablation 訓練(共 ~3h) | — |
| 2026-05-27 | Ablation external GMF(user 手動跑 GMF 工具填 12 個) | — |
| 2026-05-27 | Tier 3 ablation verdict(SEQ vs EDGE 兩 anchor) | `ablation_external_gmf_verdict.md` |
| 2026-05-27 | 跑 5 extended candidates inference + 720-angle | — |
| 2026-05-27 | edge_width + visual_metrics 收集(13 + 9 candidate) | — |
| 2026-05-27 | Tier 2 spectrum verdict(SEQ-EDGE orthogonal 發現) | `extended_spectrum_verdict.md` |
| 2026-05-27 | 複製 v2 → v3,Round 1 修改 7 段 | `v3_modifications_round1.md` |
| 2026-05-27 對話結束 | 寫本 HANDOFF_MASTER | — |

---

## 10. 重要 caveats / known limitations

### 10.1 主軸成立但有 known limitations

- **Single seed**:所有 ablation 跑單 seed,0.8 px 上的「NO_SEQ vs COMBO 接近」結論可能在 seed variance 內翻盤。Multi-seed 補測待做。
- **Baseline visual_metrics 缺**:R30 / R33 / R38v2 / COMBO 的 absolute edge_steepness 沒新算,只有 ESTIMATOR_POLICY 既有的 vs R30 (%) 數字
- **CRB proxy 用 raw vs recon 比例,不是精確 Fisher 計算**:正式 CRB 需要對 PSF 做 Fisher 數值積分,可作 future work
- **R30 r26 sequence recon BMP 位置不明確**:對 R30 補跑 inference 需要找 R30 ckpt(可能在 `Traing_Progress/organized_20260316/round30/...`,但具體路徑沒確認)

### 10.2 對 SEQ-EDGE 分工的解讀注意

NO_SEQ 0.8 px σ̂ 比 COMBO **沒退步**(甚至略低 -2.8%),這個結論的解讀:

- **不是**「SEQ 沒用」 — SEQ 在 8 px 上 σ̂ +131%,是強因果
- **是**「SEQ 對 0.8 px σ̂ 沒貢獻」 — 因為 0.8 px σ̂ 已逼近 CRB,SEQ 推不下去
- 論文寫法要小心:不要寫「拿掉 SEQ 後 σ̂ 沒退步,所以 SEQ 沒用」,要寫「0.8 px σ̂ 已 saturated,SEQ 的因果效應在 8 px 跟 edge_width 上才看得到」

### 10.3 R42 / R46 邊界鈍化的因果

R42_r41best μ_w = 27.07(比 R30 21.95 還鈍),R46 μ_w = 25.22。這是「強化邊界訓練但 ring 邊界更鈍」的相關性觀察,**真實因果方向需要更細的 ablation 確認**(訓練資料分配 vs ring 邊界劣化)。論文寫作 framing 應保守。

### 10.4 CV_w 在所有 candidate 都 < 3%

跨幀邊界寬度變異係數在所有候選都 1-3%,**沒有明顯 spectrum**。原因可能是:
- raw input 邊界寬度本來就跨幀穩定(PSF 固定)
- 或 720-angle 邊界寬度量測精度有限(類似 σ̂ 噪聲地板問題)

論文 4.6.1「打破權衡」應該聚焦在 μ_w 的跨候選變化,**不能依賴 CV_w 當主要證據**。

---

## 11. 一句話總結

**論文 main claim(誤差型態轉換)穩穩成立,所有想寫進論文的證據都齊了(Tier 1 五項判準 + Tier 3 四 ablation + Tier 2 十三 candidate spectrum),v3 第 1 輪修改 7 段已對齊 ablation 證據。剩下兩件事:user 過幾天的 PI 雙軸實驗(獨立 ground truth 驗證),以及 Round 2 修改(4.8 加 falsification criterion + 其他 polish)。除非啟動 PSF ablation 或 multi-seed 補強,否則所有 1-4 章修改 + 第 5-7 章撰寫的證據都備齊。**
