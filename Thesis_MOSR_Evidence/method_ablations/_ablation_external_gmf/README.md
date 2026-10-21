# Ablation External GMF — 操作指南

Last updated: 2026-05-27
狀態:**等使用者用 GMF 工具填入 12 個 GMF_score.txt**

## 目的

對 4 個 ablation(NO_SEQ / NO_EQ / NO_EDGE / NO_FREQ)的 recon BMP 跑 external GMF,
產出 12 個 GMF_score.txt(4 ablation × 3 pitch),讓我接手做 σ̂+b 分析跟既有 8 候選對比。

完成後論文 4.5 / 4.6 的因果歸因可以從「internal 8 px 強訊號」**升級為「internal 8 px + external 全尺度」雙重證據**。

## 對應 source → target 表(12 個 mapping)

| Ablation | Pitch | Source recon BMP 目錄 | Target GMF_score.txt 位置 |
|---|---|---|---|
| NO_SEQ | 8 px | `Thesis_MOSR_Evidence/method_ablations/_ablation_recon/NO_SEQ/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260526_230916/pitch1um_y_100_odd/` | `_ablation_external_gmf/NO_SEQ/pitch8px/GMF_score.txt` |
| NO_SEQ | 0.8 px | `..._230916/pitch0p1um_y_60_odd/` | `_ablation_external_gmf/NO_SEQ/pitch0p8px/GMF_score.txt` |
| NO_SEQ | 0.08 px | `..._230916/pitch0p01um_y_40_odd/` | `_ablation_external_gmf/NO_SEQ/pitch0p08px/GMF_score.txt` |
| NO_EQ | 8 px | `..._NO_EQ/reconstruct_progress_..._20260526_235037/pitch1um_y_100_odd/` | `_ablation_external_gmf/NO_EQ/pitch8px/GMF_score.txt` |
| NO_EQ | 0.8 px | `..._235037/pitch0p1um_y_60_odd/` | `_ablation_external_gmf/NO_EQ/pitch0p8px/GMF_score.txt` |
| NO_EQ | 0.08 px | `..._235037/pitch0p01um_y_40_odd/` | `_ablation_external_gmf/NO_EQ/pitch0p08px/GMF_score.txt` |
| NO_EDGE | 8 px | `..._NO_EDGE/reconstruct_progress_..._20260527_003614/pitch1um_y_100_odd/` | `_ablation_external_gmf/NO_EDGE/pitch8px/GMF_score.txt` |
| NO_EDGE | 0.8 px | `..._003614/pitch0p1um_y_60_odd/` | `_ablation_external_gmf/NO_EDGE/pitch0p8px/GMF_score.txt` |
| NO_EDGE | 0.08 px | `..._003614/pitch0p01um_y_40_odd/` | `_ablation_external_gmf/NO_EDGE/pitch0p08px/GMF_score.txt` |
| NO_FREQ | 8 px | `..._NO_FREQ/reconstruct_progress_..._20260527_012452/pitch1um_y_100_odd/` | `_ablation_external_gmf/NO_FREQ/pitch8px/GMF_score.txt` |
| NO_FREQ | 0.8 px | `..._012452/pitch0p1um_y_60_odd/` | `_ablation_external_gmf/NO_FREQ/pitch0p8px/GMF_score.txt` |
| NO_FREQ | 0.08 px | `..._012452/pitch0p01um_y_40_odd/` | `_ablation_external_gmf/NO_FREQ/pitch0p08px/GMF_score.txt` |

source 跟 target 完整絕對路徑寫在 `paths_for_gmf_tool.tsv`(機器可讀)。

## 給 GMF 工具的參數(跟既有候選一致)

跟 R39 / R46 過去送 external GMF 同款方式:
- input:對應 pitch 的 recon BMP 整個資料夾(8 px = 101 frames, 0.8 px = 61 frames, 0.08 px = 41 frames)
- output:GMF_score.txt(逗號分隔 key/value pair,跟既有 R30/R33/COMBO 格式一致)
- 用既有 template / 量測流程,不要改參數,否則跟既有 candidate 不可比

## 你跑完後我會做什麼

當 12 個 GMF_score.txt 都到位後,你跟我說一聲,我立刻:

1. 用既有 `decompose_sigma_b.py`(已預先加 4 個 ablation candidate entry,等檔到位就會 pick up)重跑,擴展 9 + 4 = **13 候選 σ̂ + b 表**
2. 跑既有 plot 腳本擴展 trend 圖跟 σ̂ vs b panel
3. 寫 `Thesis_MOSR_Evidence/method_ablations/reports/ablation_external_gmf_verdict.md`,把 internal 8 px 跟 external 三尺度結果整合對比

預估從你 GMF 跑完到我交報告:**< 10 分鐘**(全自動)。

## 完成度檢查

我預備了個 sanity-check 腳本,跑一次告訴你「12 個檔案缺哪些 / 格式是否正確」:

```bash
python Thesis_MOSR_Evidence/method_ablations/check_ablation_gmf_ready.py
```
