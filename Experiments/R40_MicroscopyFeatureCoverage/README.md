# R40 — 顯微特徵覆蓋

## 假說

R40 測試:用受控的合成 microscopy 特徵覆蓋,能不能把模型對 grid、紋理、大塊區域、defect 的重建容量拉起來。

這是一輪 capacity 試探,不是預設的升級嘗試。

## 設計

- 不加真實影像。
- 不動模型本體。
- 主要候選都從既有 checkpoint 接續:
  - `r40_micro_capacity_combo`:從 COMBO 接。
  - `r40_micro_capacity_a030`:從 R39 alpha=0.30 接。
- 訓練資料用部分 ring replay、R39 simple-shape replay,加上比例較高的新 microscopy 特徵場景。
- 升級門檻不變:訓練後的權重平均要再過一次三尺度 ring guard 與外部 GMF gate,才會考慮升級。

## 候選

| Tag | 起點 | 角色 |
|-----|------|------|
| `r40_micro_capacity_combo` | COMBO | 主要 capacity 探針 |
| `r40_micro_capacity_a030` | R39 a030 | 看 R39 形狀 prior 對 microscopy 特徵有沒有幫助 |

## 資料

新的乾淨 label stage:

| Stage | 特徵家族 |
|-------|----------|
| `stage_29_micro_lines_grid` | 細線、grid、交叉週期結構 |
| `stage_30_micro_large_regions` | 明亮 / 暗的 IC 風格區域與邊界 |
| `stage_31_micro_textures` | 顆粒狀與低對比紋理 |
| `stage_32_micro_edge_defects` | 鋸齒邊、缺角、刮痕、斑點 |
| `stage_33_micro_mixed_fields` | grid + 紋理 + 區域 + marker + defect 的混合場景 |

乾淨 label 產在 `Training_Data/generated/`。要先用 `Training_Data/PSF_Convolution.py` 做正向模擬,才能進 training 包 build 流程。

## 流程

1. 產生乾淨合成 label:

   ```powershell
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\r40_micro_data.py generate-clean --force
   ```

2. 在既有的 PSF convolution script 裡把 `RUN_STAGE_IDS=[29, 30, 31, 32, 33]` 跑一遍。

3. Build R40 資料包:

   ```powershell
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\r40_micro_data.py build --profile all --force
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\r40_micro_data.py validate-splits --profile all
   ```

4. 在 unseen microscopy 特徵驗證集上跑 baseline:

   ```powershell
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\run_r40_micro_recon.py --weights combo
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\r40_micro_metrics.py --output-json Experiments\R40_MicroscopyFeatureCoverage\results\micro_recon\combo_micro_summary.json
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\run_r40_micro_recon.py --weights a030
   ```

5. 訓練 capacity 候選:

   ```powershell
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\launch_r40.py --candidate r40_micro_capacity_combo --build-data
   python Experiments\R40_MicroscopyFeatureCoverage\scripts\launch_r40.py --candidate r40_micro_capacity_a030
   ```

6. 訓練後跑 microscopy 驗證、local ring guard、權重平均 sweep,過了再考慮外部 GMF。

## 結果

狀態:訓練、local 分析、外部 GMF 都跑完。最佳的 local guarded 權重平均仍是研究用,因為它讓 8px 外部 ring guard 退步。

unseen microscopy 特徵驗證集上的 baseline:

| Model | Avg PSNR | Avg SSIM | High-frequency retention | Edge retention |
|-------|---------:|---------:|-------------------------:|---------------:|
| COMBO | 22.7326 | 0.8588 | 0.2234 | 0.6607 |
| R39 a030 | 25.0323 | 0.8904 | 0.2206 | 0.6181 |
| R40 combo best | 28.9546 | 0.9506 | 0.8485 | 1.0336 |
| R40 a030 best | 29.6323 | 0.9573 | 0.7904 | 0.9880 |
| R40 combo best avg a045 | 26.8911 | 0.9199 | 0.3414 | 0.7458 |

R40 訓練確認了一件事:合成 microscopy 特徵覆蓋可以把 capacity 上限推得遠遠超過 COMBO 與 R39 a030。直接的 endpoint 在 microscopy 細節上進步,但 local ring guard 都沒過。找到的最佳 local guarded trade-off 是 `r40_combo_best_avg_a045`——它過了 local 三尺度 ring guard,但外部 8px guard 沒過(vs COMBO +22.80%)。所以 R40 是成功的 capacity study,不是升級候選。

詳見 `reports/R40_RESULTS.md` 與 `reports/R40_EXTERNAL_COMPARE.md`。

## 分支

`sandbox/r40`
