# R32 Sandbox

## 概覽 / Overview

這裡是 `Round32` 的獨立實驗沙盒。
This directory is the isolated execution surface for `Round32`.

**R32 的核心問題**：在 R30 已訓練好的模型基礎上，加入「真實影像 EQ（等化訓練信號）」能否讓模型在真實量測資料上表現更好？
**Core research question**: Starting from the R30 trained checkpoint, does injecting real-domain equalization (EQ) training images help the model perform better on real-world measurement data?

**最終結論（2026-03-20）**：否。`r32_real_eq_finetune` 在內部合成資料探針全部通過，但在外部真實資料上，效能比 R30 基準線差了將近一倍。**無法升級 baseline。**
**Final answer (2026-03-20)**: No. `r32_real_eq_finetune` passed all internal synthetic probes, but on external real data, performance was nearly 2× worse than the R30 baseline. **Cannot be promoted to baseline.**

---

## 為什麼需要獨立沙盒 / Why an Isolated Sandbox

這個 sandbox 的存在，是把 `R32` 專用的所有訓練、稽核、runtime、外部比較流程，和 root 共用主線完全隔開，避免實驗性變更汙染穩定工作流程。
The sandbox exists to keep all `R32`-specific training, audit, runtime, and external compare logic separate from the root shared mainline, so experimental changes cannot leak back into the stable workflow.

- **root `Model/`** 只維護 R26 / R30 / shared stable workflow，不被 R32 異動。
  The root `Model/` stays clean for R26 / R30 / shared stable workflow and is not modified by R32.
- **R32 自己的** 訓練腳本、profile、稽核器、狀態機全部在這個沙盒內自包含。
  R32's own training scripts, profiles, auditors, and state machine are fully self-contained inside this sandbox.
- 共用的資源（骨幹模型、訓練資料、PSF 擬合結果）從 root 讀取，但不寫回 root。
  Shared assets (backbone model, training data, PSF results) are read from root but never written back.

---

## 目錄結構 / Directory Structure

```
R32Sandbox/
├── README.md                      ← 本文件
├── Model/                         ← 所有 Python 腳本
│   ├── profiles_r32.py            ← 候選組合定義（超參數、訓練資料選擇）
│   ├── autotune_r32.py            ← 自動掃描訓練主程式
│   ├── train_r32.py               ← 底層訓練引擎（與 root 隔離）
│   ├── process_probe_audit_base.py← 通用稽核器（0.8px / 8px 探針）
│   ├── process_probe_audit_r32.py ← R32 稽核器入口（轉交 base 執行）
│   ├── r32_real_eq.py             ← 真實影像 EQ dataloader
│   ├── external_gmf_round32_compare.py ← 外部 GMF 結果比對腳本
│   ├── longrun_round32.py         ← 端到端完整流程編排
│   └── r32_status.py              ← runtime 狀態讀寫工具
├── Tools/                         ← PowerShell 啟動與監看腳本
│   ├── start_r32_real_eq.ps1      ← 主啟動器（非同步啟動訓練）
│   ├── wait_r32_real_eq.ps1       ← 後台守護（等待完成、更新狀態）
│   ├── open_r32_output_window.ps1 ← 前景視窗監看 log
│   └── run_r32_external_recon.ps1 ← 外部重建 + GMF 比較批次
├── runtime/                       ← 即時執行狀態（唯一可信來源）
│   ├── R32_STATUS.json            ← 機器可讀狀態
│   ├── R32_STATUS.md              ← 人類可讀狀態
│   └── logs/                      ← 訓練 stdout / stderr log
├── artifacts/                     ← 訓練輸出（checkpoint + repro）
│   └── training_progress_GESR_v1_v5_ST0p8_SWP_r32realeq_*/
│       ├── weights/best_tradeoff.pth.tar  ← 最佳 checkpoint
│       └── _repro/                        ← 可重現訓練設定快照
├── reports/                       ← 所有稽核報告與決策備忘
│   ├── auto_tune_report_*.json    ← 每次 autotune sweep 的原始記錄
│   ├── ROUND32_DOMAIN_CAPACITY_AUDIT_0P8_*.{json,md}   ← 0.8px 內部稽核
│   ├── ROUND32_DOMAIN_CAPACITY_AUDIT_8P0_*.{json,md}   ← 8px 守衛稽核
│   ├── ROUND32_DOMAIN_CAPACITY_DECISION_*.{json,md}    ← 內部決策備忘
│   ├── ROUND32_DOMAIN_CAPACITY_MERGED_PROFILE_REPORT.json
│   └── ROUND32_EXTERNAL_COMPARE.{json,md}  ← 外部真實資料比較結果
└── external_compare/              ← 外部比較中間產物
    └── r32_real_eq_finetune/
        ├── reconstructions/       ← 推論重建影像
        └── gmf_results/raw/       ← GMF_score.txt（各尺度）
```

---

## 候選組合 / Candidate Definitions

在 [Model/profiles_r32.py](Model/profiles_r32.py) 中定義了三個候選，全部從相同的 `r32_base_probe` 超參數組出發：

| 候選名稱 | 核心差異 | seed checkpoint |
|---------|---------|----------------|
| `r32_real_eq_finetune` | 啟用真實影像 EQ（`REAL_EQ_ENABLE=True`，機率 30%） | R30 B1 dironly |
| `r32_long_from_r25` | 從 R25 seed 出發，LR=2e-6，跑更長（40 epochs） | R25 |
| `r32_wider_b1` | 加寬模型（base=64），從頭訓練，LR=5e-5 | 無（from scratch） |

本次實驗只跑了 `r32_real_eq_finetune`（啟動器以 `--candidate-filter` 限定）。
Only `r32_real_eq_finetune` was executed in this experiment (launcher used `--candidate-filter` to restrict).

### 真實影像 EQ 是什麼 / What is Real-Image EQ

`r32_real_eq.py` 的 `RealImageOnlyFolder` 從 `Training_Data/generated_convolved/Real_Image/` 載入真實顯微鏡影像（BMP 格式），隨機裁切 256×256 patch。在每個訓練 step，以 30% 的機率用真實影像替換合成影像作為 EQ loss 的輸入來源，讓模型學到真實感測器的紋理特性。
`RealImageOnlyFolder` in `r32_real_eq.py` loads real microscope images (BMP) from `Training_Data/generated_convolved/Real_Image/`, randomly crops 256×256 patches. During each training step, with 30% probability, the synthetic EQ source is replaced by a real-domain patch, so the model learns real sensor texture characteristics.

---

## 完整執行流程 / End-to-End Pipeline

整個 R32 流程分為五個階段，由 `longrun_round32.py` 編排，也可以透過 PowerShell 腳本手動觸發個別階段：

```
[階段 1] 訓練 Sweep
         autotune_r32.py
         → 40 epochs sweep + GMF 評分
         → 選出 best_tradeoff checkpoint
         → 輸出 auto_tune_report_*.json

[階段 2] 彙總 family summary
         → ROUND32_DOMAIN_CAPACITY_SUMMARY_*.json/md

[階段 3] 內部 0.8px 稽核
         process_probe_audit_r32.py (--expect-dy 0.8)
         → 中尺度追蹤探針（pairmix_algblend 方法）
         → 輸出 AUDIT_0P8_*.json/md

[階段 4] 內部 8px 守衛稽核
         process_probe_audit_r32.py (--expect-dy 8.0)
         → 大尺度追蹤穩定性守衛（edge_band_refine 方法）
         → 輸出 AUDIT_8P0_*.json/md
         → 寫出 DECISION 備忘

[階段 5] 外部真實資料比較
         run_r32_external_recon.ps1
         → 對 3 個 NTU 真實資料集推論重建
         → 計算 GMF step std
         → 與 R30 baseline 比較
         → 輸出 ROUND32_EXTERNAL_COMPARE.json/md
```

---

## 啟動方式 / How to Launch

### 手動啟動訓練 sweep（階段 1）

```powershell
# 從 project root 執行
.\Experiments\R32Sandbox\Tools\start_r32_real_eq.ps1
```

這個腳本會：
1. 以非同步方式啟動 `autotune_r32.py`，將 stdout/stderr 寫到 `runtime/logs/`
2. 立刻更新 `runtime/R32_STATUS.json` 和 `runtime/R32_STATUS.md` 為 `state: running`
3. 在背景再啟動 `wait_r32_real_eq.ps1` 守護程序，等待主程序結束後自動更新最終狀態

The script launches `autotune_r32.py` asynchronously, writes stdout/stderr to `runtime/logs/`, updates status files immediately, and spawns a background watcher that updates final status on completion.

### 監看訓練進度 / Monitor Training Progress

```powershell
.\Experiments\R32Sandbox\Tools\open_r32_output_window.ps1
```

在新視窗持續顯示最新 log 輸出。
Opens a new window tailing the latest log output.

### 執行外部重建比較（階段 5）

```powershell
.\Experiments\R32Sandbox\Tools\run_r32_external_recon.ps1
```

腳本會自動從 `reports/` 下最新的 DECISION JSON 讀取 winner checkpoint，依序對 3 個真實資料集執行推論，再呼叫 `external_gmf_round32_compare.py` 產生比較報告。
Automatically reads the latest DECISION JSON, runs inference on 3 real datasets, then calls the compare script to generate the final report.

---

## Runtime 狀態機 / Runtime State Machine

`runtime/R32_STATUS.json` 和 `runtime/R32_STATUS.md` 是同一份狀態的兩種格式。關鍵欄位：

| 欄位 | 說明 |
|------|------|
| `state` | `running` / `completed` / `error` |
| `step_index` | 目前執行到第幾個計畫步驟（1-based） |
| `active_label` | 目前步驟名稱（例如 `round32_real_eq_rerun`） |
| `plan_done` / `plan_total` | 已完成 / 總計畫步驟數 |
| `selected_candidate` | 內部競賽的獲勝候選名稱 |
| `selected_checkpoint` | 獲勝 checkpoint 的完整路徑 |
| `active_log` / `active_err_log` | 當前 log 檔案路徑 |
| `last_report` | 最後寫出的報告路徑 |
| `updated_at` | 最後更新時間 |

**目前狀態（2026-03-20）**：`state: completed`，全部 4 步完成，winner = `r32_real_eq_finetune`。

---

## 訓練設定細節 / Training Configuration Details

`autotune_r32.py` 在執行時套用兩層設定：

**1. 共用基礎設定（common_overrides）** — 所有候選共享：
- Sweep 40 epochs，每 epoch 做 GMF 驗證
- 0.8px step 期望位移（`GMF_EXPECT_DY_PX=0.8`）
- Shift mix 比例：tiny（0-0.3px）70%、mid（0.3-1.5px）20%、int（1-8px）10%
- EQ warmup 在 epoch 10 結束，epoch 11-30 漸進增強

**2. 候選專屬設定（overrides）** — `r32_real_eq_finetune` 特有：
- `REAL_EQ_ENABLE: True` — 開啟真實影像 EQ
- `REAL_EQ_DIR` → `Training_Data/generated_convolved/Real_Image/`
- `REAL_EQ_PROB: 0.30` — 每步 30% 機率替換為真實影像
- LR=1.1e-6（非常低，屬於 fine-tune 等級）
- 訓練資料：6 個靜態環形 stage（08-10, 14-16）
- 序列資料：3 個核心環形 stage（08-10）

**Best checkpoint 選擇策略**：
以 `best_tradeoff_score`（GMF 目標函數綜合分數）為主；若 edge width 超差 6% 以上罰分 18 倍，HF proxy 超差 3% 罰分 55 倍，防止模型犧牲邊緣清晰度換取位移精度。

---

## 稽核指標說明 / Audit Metrics

### 0.8px 中尺度稽核（pairmix_algblend）

探針在合成 mid stage（stage_23/24/27/28）上測試 0.8px 步長追蹤：

| 指標 | 意義 | 通過門檻 |
|------|------|---------|
| `mid_center` | 中心位置誤差（越小越好） | ratio > 0.25（即 `1 - mid_center > 0.25`） |
| `mid_step` | 步長誤差（越小越好） | < 0.45 |
| `mid_pass` | 兩者都通過 | 1 = pass |

`r32_real_eq_finetune` 結果：`mid_center=0.2016`，`mid_step=0.1096`，**兩項均通過**。

### 8px 守衛稽核（edge_band_refine）

探針在合成 macro stage（stage_25/26）上測試大尺度穩定性：

| 指標 | 意義 | 通過門檻 |
|------|------|---------|
| `macro_step` | 大尺度步長誤差 | < 0.2995 |
| `macro_seq_sign` | 方向符號一致率 | > 0.7559 |
| `macro_pass` | 兩者都通過 | 1 = pass |

`r32_real_eq_finetune` 結果：`macro_step=0.0967`，`macro_seq_sign=0.8649`，**兩項均通過**。

**內部結論：`r32_real_eq_finetune` 通過所有合成探針，成為 Round32 內部獲勝者。**
**Internal conclusion: passes all synthetic probes, becomes Round32 internal winner.**

---

## 外部真實資料比較 / External Real-Data Comparison

外部比較是最終的「真實世界」驗收測試。流程：

1. 以 winner checkpoint 對 3 個 NTU 顯微鏡資料集逐幀推論
2. 從 GMF_score.txt 解析每幀的 `PosY` 估計值
3. 計算連續幀差分 `step[i] = PosY[i+1] - PosY[i]`
4. 計算 `step std`（主要評分指標）
5. 與 R30 baseline（`r30_b1_dironly`）比較

### 比較結果 / Comparison Results

| 尺度 | 實際位移 | R30 baseline | R32 winner | 差異 |
|------|---------|-------------|-----------|------|
| **8px**（大尺度） | Pitch1um 資料集 | 0.2052 | 0.3197 | **+55.8%** ← 更差 |
| **0.8px**（主戰場） | Pitch0.1um 資料集 | **0.1679** | **0.3318** | **+97.7%** ← 幾乎差一倍 |
| **0.08px**（小尺度） | Pitch0.01um 資料集 | 0.1577 | 0.2301 | **+45.9%** ← 更差 |

**R32 在所有尺度上都比 R30 更差，主戰場（0.8px）甚至差了將近一倍。**
**R32 is worse than R30 on every scale. On the main battlefield (0.8px), it is nearly 2× worse.**

**最終裁決 / Final Verdict：FAIL — `r32_real_eq_finetune` 不能升級 baseline。**

---

## 為何內部通過、外部失敗 / Why Internal Pass but External Fail

內部稽核全部使用合成資料（模擬器生成的環形 stage），R32 在這些資料上表現良好。
但是，外部比較使用的是真實顯微鏡採集影像（NTU 資料集），呈現出與合成資料截然不同的噪訊和紋理分布。

加入真實影像 EQ（`REAL_EQ_ENABLE`）雖然意圖是讓模型習慣真實感測器紋理，但可能導致：
- 合成 → 真實域適應過度，破壞了原本 R30 在真實資料上的泛化能力
- 訓練資料分布改變後，模型在 fine-tune 的極低 LR（1.1e-6）下過擬合了合成資料的特性

Internal audits all use synthetic data (simulator-generated annulus stages). R32 performs well there. But external comparison uses real microscope images (NTU dataset) with genuinely different noise and texture distribution. Injecting real EQ images may have caused the model to over-adapt, breaking the generalization R30 already had.

---

## 現況摘要 / Current Status Summary（2026-03-20）

| 項目 | 狀態 |
|------|------|
| R32 內部鏈 | ✓ 完成 |
| 內部獲勝者 | `r32_real_eq_finetune` |
| 內部 0.8px 稽核 | ✓ 通過 |
| 內部 8px 守衛 | ✓ 通過 |
| 外部真實資料比較 | ✗ 失敗（比 R30 差 +97.7%） |
| 升級 baseline | **否決** |
| 下一步 | 若續做 R32，必須另立新 sandbox branch 或採用不同機制 |

---

## 主要入口 / Main Entry Points

### 訓練與流程 / Training and Workflow

- 候選定義：[Model/profiles_r32.py](Model/profiles_r32.py)
- 自動掃描訓練：[Model/autotune_r32.py](Model/autotune_r32.py)
- 底層訓練引擎：[Model/train_r32.py](Model/train_r32.py)
- 內部稽核入口：[Model/process_probe_audit_r32.py](Model/process_probe_audit_r32.py)
- 通用稽核器：[Model/process_probe_audit_base.py](Model/process_probe_audit_base.py)
- 真實 EQ loader：[Model/r32_real_eq.py](Model/r32_real_eq.py)
- 外部比較腳本：[Model/external_gmf_round32_compare.py](Model/external_gmf_round32_compare.py)
- 端到端流程：[Model/longrun_round32.py](Model/longrun_round32.py)

### 啟動與監看 / Launch and Monitoring

- 主啟動器：[Tools/start_r32_real_eq.ps1](Tools/start_r32_real_eq.ps1)
- 完成守護：[Tools/wait_r32_real_eq.ps1](Tools/wait_r32_real_eq.ps1)
- 前景監看：[Tools/open_r32_output_window.ps1](Tools/open_r32_output_window.ps1)
- 外部重建批次：[Tools/run_r32_external_recon.ps1](Tools/run_r32_external_recon.ps1)

### Runtime 狀態 / Runtime Status

- 機器可讀：[runtime/R32_STATUS.json](runtime/R32_STATUS.json)
- 人類可讀：[runtime/R32_STATUS.md](runtime/R32_STATUS.md)

### 正式決策文件 / Canonical Decision Documents

- 內部決策備忘：[reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md](reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md)
- 外部比較結果：[reports/ROUND32_EXTERNAL_COMPARE.md](reports/ROUND32_EXTERNAL_COMPARE.md)

---

## 共用資產 / Shared Assets（只讀，不寫回）

這個 sandbox 讀取以下 root 資源，但不修改它們：

| 資源 | 用途 |
|------|------|
| `root/Model/` 骨幹 / utils | 訓練引擎依賴的共用模型結構與工具 |
| `root/Training_Data/` | 合成訓練資料（annulus stage 資料夾） |
| `root/Training_Data/generated_convolved/Real_Image/` | 真實影像 EQ 資料來源 |
| `root/PSF_Fitting/` | PSF 擬合結果（訓練資料生成依賴） |
| R30 B1 dironly checkpoint | `r32_real_eq_finetune` 的 seed 起點 |

---

## 輸出位置 / Output Locations

| 類型 | 路徑 |
|------|------|
| 執行狀態 | `Experiments/R32Sandbox/runtime/` |
| 訓練 checkpoint | `Experiments/R32Sandbox/artifacts/` |
| 稽核與決策報告 | `Experiments/R32Sandbox/reports/` |
| 外部推論與 GMF 結果 | `Experiments/R32Sandbox/external_compare/` |
| 訓練 log | `Experiments/R32Sandbox/runtime/logs/` |
