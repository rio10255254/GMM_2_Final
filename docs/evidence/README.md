# 證據層 / Evidence Layer

這個資料夾收納的是**經過策展、值得追蹤進 GitHub 的小型高價值實驗證據副本**。  
This directory holds **curated, tracked copies of small, high-value experiment evidence** that is worth keeping in GitHub.

它的目的，是在**不把大型實驗輸出塞進 Git history** 的前提下，保留支撐正式判斷所需的證據面。  
Its purpose is to preserve the formal proof surface **without pulling bulk experiment outputs into Git history**.

這一層主要支撐：
- 目前正式 baseline
- 導向目前 baseline 的歷史基準路徑
- 已被正式否定的主線或 side-direction
- 分析與 screening 結論
- 小型、值得追蹤的 runtime truth

This layer mainly supports:
- the current promoted baseline
- the historical baseline path that led to the current baseline
- formally falsified main lines or side directions
- analysis and screening conclusions
- small runtime truth snapshots that are worth tracking

## 這裡應該放什麼 / What Belongs Here

- 正式 decision memo / formal decision memos
- external compare 摘要 / external compare summaries
- 小型 machine-readable compare JSON / small machine-readable compare JSON files
- 小型 canonical runtime truth snapshots / small canonical runtime truth snapshots
- 精簡的 analysis / screening reports / compact analysis and screening reports

## 這裡不該放什麼 / What Does Not Belong Here

- `weights`
- `reconstructions`
- raw GMF dumps
- bulk logs
- 大型或可重現的 payload / large or reproducible payloads

這些內容應繼續留在原本的實驗輸出位置，不應直接進入 evidence 層。  
Those artifacts should stay in their original experiment/output locations and should not be copied into the evidence layer.

## 為什麼這些是策展副本 / Why These Are Curated Copies

這個資料夾裡的檔案，是從原始 runtime 或 report 位置複製過來的**策展副本**。  
Files in this directory are **curated copies** taken from their original runtime or report locations.

原始來源仍然保留在原路徑。  
The original source files remain in place.

這裡不是原始執行目錄，也不應被視為 live runtime directory。  
This directory is not the original execution root and should not be treated as a live runtime directory.

## 第一站 / First Stop

如果你想最快理解整條證據鏈，先看：
- `EVIDENCE_MAP.md`

If you want the fastest way to understand the evidence chain, start with:
- `EVIDENCE_MAP.md`

那份文件會告訴你：
- 哪些證據支撐目前 baseline
- 哪些證據支撐歷史基準演進
- 哪些證據證明某條線被否定
- 哪些證據支撐分析與 runtime truth

That file explains:
- which evidence supports the current baseline
- which evidence supports the historical baseline path
- which evidence proves a line was falsified
- which evidence supports analysis conclusions and runtime truth

## 目錄結構 / Layout

- `baseline/`
  - 支撐目前正式 baseline 的證據  
    evidence that supports the current promoted baseline
- `historical_baselines/`
  - 說明 `R30` 之前基準線如何演進到 `R26 sm035`  
    evidence that explains the pre-R30 baseline path and the generic `step_mag` line that culminated in `R26 sm035`
- `falsified/`
  - 支撐正式退場或 external FAIL 的主線  
    evidence that supports formally rejected or externally failed lines
- `side_directions/`
  - 支撐重要 side-direction 被否定  
    evidence that formally rejects important side-direction attempts such as TTA
- `analysis/`
  - 支撐分析與 screening 結論  
    evidence that supports screening logic or cross-run analytical conclusions
- `runtime/`
  - 小型 canonical runtime truth snapshots  
    small canonical runtime truth snapshots that are worth tracking
- `visuals/`
  - 少量、可公平比較的代表性 comparison sheets  
    compact side-by-side comparison sheets for a very small number of representative image cases
- `EVIDENCE_MAP.md`
  - 一份說明「哪份證據支撐哪個 verdict / branch」的地圖  
    a one-file map of which evidence supports which verdict or branch

## 目前核心集 / Current Core Set

- `baseline/ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md`
  - 支撐 `baseline/r30-b1-dironly` 的 internal decision  
    supports the internal decision behind `baseline/r30-b1-dironly`
- `baseline/ROUND30_EXTERNAL_COMPARE.md`
  - 支撐目前 baseline 的 external promotion  
    supports the external promotion of the current baseline
- `falsified/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
  - 說明 Round31 B1 follow-up line 的正式定義  
    explains the Round31 B1 follow-up line
- `falsified/ROUND31_EXTERNAL_COMPARE.md`
  - 支撐 `research/round31-b1-hparam` external regression  
    supports the external regression verdict for `research/round31-b1-hparam`
- `falsified/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
  - 說明 Round32 internal winner 如何被選出  
    explains how the Round32 internal winner was selected
- `falsified/ROUND32_EXTERNAL_COMPARE.md`
  - 以人類可讀形式支撐 `sandbox/r32` external FAIL  
    supports the `sandbox/r32` external FAIL verdict in human-readable form
- `falsified/ROUND32_EXTERNAL_COMPARE.json`
  - Round32 external FAIL 的 machine-readable companion  
    machine-readable companion to the Round32 external FAIL verdict
- `runtime/R32_STATUS.md`
  - 目前 canonical sandbox runtime truth（文字版）  
    current canonical sandbox runtime truth in human-readable form
- `runtime/R32_STATUS.json`
  - canonical sandbox runtime truth（機器可讀版）  
    machine-readable companion to the canonical sandbox runtime truth

## 歷史基準路徑 / Historical Baseline Path

- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.json`
  - 記錄從 `R18/R22` 走到 `Round25` 的正式外部比較  
    documents the step from the earlier `R18/R22` references to `Round25`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.json`
  - 記錄接著走到 `R26` 的正式比較  
    shows the next formal compare step that established the `R26` line
- `historical_baselines/ROUND29_STEP_MAG_UPPER_DECISION_20260317_124715.md`
- `historical_baselines/ROUND29_STEP_MAG_UPPER_DECISION_20260317_124715.json`
  - 說明 `Round29` upper-sweep 的正式決策邏輯  
    explains the formal upper-sweep decision logic around `Round29`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.md`
- `historical_baselines/EXTERNAL_COMPARE_R18_R22_R25_R26_R27_R28_R29_SUMMARY.json`
  - 保留 `R26 sm035` 是 generic `step_mag` 線 externally verified optimum 的最強精簡證據  
    preserves the strongest compact proof that `R26 sm035` remained the externally verified optimum of the generic `step_mag` line

## 其他否定線與分析證據 / Additional Falsified and Analysis Evidence

- `falsified/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.json`
- `falsified/ROUND31_EXTERNAL_COMPARE.json`
- `falsified/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.json`
  - Round31 / Round32 主要否定線的 machine-readable companions  
    machine-readable companions for the core Round31 / Round32 falsified lines
- `analysis/INTERNAL_EXTERNAL_CORRELATION.md`
- `analysis/INTERNAL_EXTERNAL_CORRELATION.json`
  - 支撐 `center_err` 作為 Tier2 screening signal  
    supports the `center_err` Tier2 screening conclusion
- `side_directions/TTA_VS_BASELINE_CROSS5_COMPARISON.md`
- `side_directions/TTA_VS_BASELINE_CROSS5_COMPARISON.json`
  - 保留 `TTA C2` side-direction 被正式否定的證據  
    preserves the formal rejection of the `TTA C2` side direction

## 視覺證據 / Visual Evidence

- `visuals/comparison_0p8px_case_01.png`
  - 比較 `R26`、`Round30 baseline`、`Round31 regression`、`Round32 fail`  
    compares `R26`, `Round30 baseline`, `Round31 regression`, and `Round32 fail`
  - 案例：`VisionTop_20251029185330879.bmp`  
    case: `VisionTop_20251029185330879.bmp`
- `visuals/comparison_0p8px_case_02.png`
  - 在第二個 matched case 上重做同樣的四線比較  
    repeats the same four-line comparison on a second matched case
  - 案例：`VisionTop_20251029185655191.bmp`  
    case: `VisionTop_20251029185655191.bmp`

更詳細的視覺收錄規則請看 `visuals/README.md`。  
For the visual curation rule, see `visuals/README.md`.

## 收錄規則 / Curation Rule

這個資料夾刻意保持**選擇性**。  
This directory is intentionally **selective**.

- 只有當某份文件能實質支撐目前 baseline、關鍵歷史基準轉折、重大 falsified line、或 durable analytical conclusion 時，才應增加到這裡。  
  It should grow only when a document materially supports the current baseline, a key historical baseline transition, a major falsified line, or a durable analytical conclusion.
- 視覺證據必須保持極少且高度可比：少量有標籤的 comparison sheets 有用，但原始 reconstruction 集不屬於 evidence 層。  
  Visual evidence should stay extremely small and highly comparable: a few labeled comparison sheets are useful, but raw reconstruction sets do not belong here.
- 不能因為報告存在就收錄。  
  It should not grow just because a report exists in an experiment directory.
- 單候選 audit、batch manifest、auto-tune noise、圖片全集與 bulk raw outputs，原則上都不應進 Git。  
  Per-candidate audits, batch manifests, auto-tune noise, full image sets, and bulk raw outputs should remain outside Git unless there is a strong reviewable reason to curate them here.
