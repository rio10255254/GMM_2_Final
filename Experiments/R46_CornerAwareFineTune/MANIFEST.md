# R46 Manifest

## 識別

- **Round**: 46
- **Directory**: `Experiments/R46_CornerAwareFineTune/`
- **目錄名稱**: R46_CornerAwareFineTune(底線+PascalCase 描述,符合 STARTING_NEW_EXPERIMENT.md 命名規則)
- **Branch**: 在 worktree `claude/gifted-shaw-29b50a`(尚未開 `sandbox/r46`,實驗結束再決定)
- **Created**: 2026-05-14
- **Status**: in_progress

## 一句話定位

R46 是 a025(approved alternate, balanced full-spectrum)的邊角細節微調探針,走「路徑 B」——不動 trainer,只強化既有的邊緣銳度 / 高頻保留權重。

## 設計來源

R46 設計直接源自前三輪 Rayleigh 診斷的結論(`Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_RAYLEIGH_*.md`):

1. 第一輪基礎診斷:把驗證集按特徵尺寸分桶
2. 第二輪統計檢驗:確認 a043 全面顯著贏 a025
3. 第三輪訓練分布 + 視覺驗證:確認 R46 增益會是「溫和銳化」,期望整體影像品質 +0.6 到 +1.0 分貝

## 主候選

| Tag | 起點 | 學習率 | 訓練輪數 | 訓練 profile |
|---|---|---|---|---|
| `r46_a025_corner_finetune` | a025 best_tradeoff | 4.0e-6 | 15 | r40_micro_capacity_train |

## 關鍵路徑

| 項目 | 路徑 |
|---|---|
| 主腳本 | `Experiments/R46_CornerAwareFineTune/scripts/launch_r46.py` |
| Trainer(沿用,不複製) | `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py` |
| 起點 checkpoint | `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar` |
| 訓練資料 | `Training_Data/r40_microscopy_feature_coverage/r40_micro_capacity_train/` |
| 訓練輸出 | 完整 run 依 `ARCHIVE_POINTER_20260824.md` 從 H 恢復；D 代表模型在 `results/archive_retained_20260824/training_checkpoints/` |

## Handoff 注意

- 本實驗走路徑 B(既有 hyperparam 強化),trainer 主檔**沒有**被修改 / 複製
- 如果未來要走路徑 A(加 corner-aware loss term),要複製 trainer 到 `Experiments/R46_*/scripts/r46_trainer.py` 再改,**不能動 Model/ 下的 canonical**
- a025 是 weight averaging 結果,trainer 載入時用 `LOAD_RESET_OPTIMIZER=True` + `LOAD_RESET_EPOCH=True`
- 訓練資料對齊 a043 訓練 profile(`r40_micro_capacity_train`),不是 R39 訓練 profile——R39 訓練 0% 次解析尺度覆蓋,沒法支持邊角細節推進

## 完成後動作清單

訓練 + 評估完成後:

- [ ] 寫 `reports/R46_RESULTS.md`
- [ ] 視結果填 README.md 「結果」區
- [ ] 更新 MANIFEST.md status(`completed` / `failed_research` / `promoted`)
- [ ] 升級判定(若達升級門檻才動):
  - `ESTIMATOR_POLICY.json` 加 entry
  - `PROJECT_STATE.md` Quick Handoff 區更新
  - `Experiments/INDEX.md` 加 entry
- [ ] 若有視覺輸出:`RECON_GALLERY.md` 加 section(純 markdown,不可有 HTML)
