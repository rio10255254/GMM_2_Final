# R46 外部 GMF 驗證 — 操作說明

外部 GMF 是 baseline 升級的最終門檻(比本地 720-angle ring guard 還準)。本資料夾結構是給你拿 R46 的三尺度 ring 重建影像去跑外部 GMF 工具,把結果放回來這裡做最終判定。

## 你要做什麼

### Step 1:拿 R46 重建影像

R46 對三個 pitch 的環形重建 BMP 已經產生好,各 frame 命名跟 NTU_ImageDataset 原始一致(`VisionTop_*.bmp`):

**這些是 odd 模式重建**(按時間戳排序取奇數位置一半 frames,跟 a025 / a043 / COMBO 同慣例,可直接送外部 GMF 跟既有 baseline 比較):

| 尺度 | 重建 BMP 來源資料夾 | frame 數(odd) |
|---|---|---:|
| **8 px**(1 μm pitch) | `Experiments/R46_CornerAwareFineTune/results/ring_recon/r46/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260514_230359/pitch1um_y_100_odd` | 101 |
| **0.8 px**(0.1 μm pitch) | `...\reconstruct_progress_best_tradeoff_in_Cropped_Output_20260514_230359\pitch0p1um_y_60_odd\` | 61 |
| **0.08 px**(0.01 μm pitch) | `...\reconstruct_progress_best_tradeoff_in_Cropped_Output_20260514_230359\pitch0p01um_y_40_odd\` | 41 |

如果需要,完整路徑可以從這個檔案的 `..` 上一層的 `ring_recon/r46/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260514_230359/` 找。

### Step 2:用外部 GMF 工具量

對上面三組 BMP 各跑你慣用的外部 GMF 工具,輸出每個尺度對應的 `GMF_score.txt`(格式跟你之前 a025 / a043 / R40 上送外部驗證一樣)。

GMF_score.txt 每行應該是:
```
FileName, VisionTop_xxxxxxx.bmp, Time(ms), 20, PosX, ..., PosY, ..., Angle, 0, Scale, 1.0, Score0, 93.4, Score1, 0, Score Diff, 93.4
```

### Step 3:把 GMF_score.txt 放回對應位置

| 尺度 | 放到這裡 |
|---|---|
| 8 px | `Experiments/R46_CornerAwareFineTune/results/external_gmf/pitch8px/GMF_score.txt` |
| 0.8 px | `Experiments/R46_CornerAwareFineTune/results/external_gmf/pitch0p8px/GMF_score.txt` |
| 0.08 px | `Experiments/R46_CornerAwareFineTune/results/external_gmf/pitch0p08px/GMF_score.txt` |

(三個資料夾已經建好。)

### Step 4:跑分析腳本

放完三個 `GMF_score.txt` 後,告訴我或者自己跑:

```bash
cd D:/GMM_2_Final
python Experiments/R46_CornerAwareFineTune/scripts/r46_external_compare.py
```

腳本會:

- 解析每個 `GMF_score.txt` 的 PosY 序列,排序後算 step
- 算 raw step_std(R33+ 方法論:只移除 `|z| > 5` 的 GMF 失敗 step)
- 跟 COMBO 外部 step_std baseline 對比(8 px = 0.154515、0.8 px = 0.131560、0.08 px = 0.099891)
- 算 `Δ vs COMBO`,判定 3% 升級門檻通過與否
- 輸出 `external_compare_summary.json` 跟 `R46_EXTERNAL_COMPARE.md` 報告

## 升級門檻提醒

| 判定 | 條件 |
|---|---|
| `PASS_UPGRADE` | 三尺度都 `Δ ≤ +3%` |
| `PASS_TRADEOFF_7PCT` | 至少一個尺度 `Δ > +3%` 但所有都 `≤ +7%`(替代容忍區,R38v2 對 COMBO 8 px 為錨) |
| `FAIL_OUTSIDE_7PCT` | 任何尺度 `Δ > +7%` |

R46 升級為 approved alternate 至少要 `PASS_TRADEOFF_7PCT`,理想是 `PASS_UPGRADE`。

## 預期結果

從本地 720-angle ring guard 看,R46 三尺度 internal step_std 退步 +2834% / +180% / +98%(`results/ring_guard/r46_ring_guard_summary.json`)。

外部 GMF 是更準的 metric,但通常**跟內部 step_std 方向一致**(internal-external divergence analysis 在 R33 / R26 都驗證過,通常 internal 失敗外部也 fail)。所以**預期外部 GMF 也會 FAIL**,但你說「外部 GMF 才是最準的」,值得實測確認。

如果外部 GMF 意外通過(`PASS_UPGRADE` 或 `PASS_TRADEOFF_7PCT`),那就是 internal-external divergence 的反例,R46 仍可作為 approved alternate 候選;如果跟 internal 一致 FAIL,R46 確認 `RESEARCH_ONLY`。

## 故障排除

- **GMF_score.txt parsed empty**:檢查格式是否每行有 `FileName,...,PosY,...` 欄位,逗號分隔
- **腳本找不到 GMF_score.txt**:確認三個資料夾的檔名都精確是 `GMF_score.txt`(大寫敏感)
- **分析跑完但沒給判定**:看 `summary.json` 裡的 `missing_scores` 區,可能漏放某個尺度

## 跟其他 baseline 的外部 GMF 紀錄對照

| 候選 | 8 px | 0.8 px | 0.08 px | Verdict |
|---|---:|---:|---:|---|
| COMBO(formal baseline) | 0.154515 | 0.131560 | 0.099891 | baseline |
| a025(approved alternate) | −5.18% | +1.51% | +0.51% | PASS_UPGRADE_GUARD |
| a043(R40 sweep 端點) | −5.91% | −3.15% | +21.52% | RESEARCH_ONLY(0.08 px FAIL) |
| a030(R39 a030) | −6.94% | +6.42% | −15.97% | PASS_TRADEOFF(7% 邊緣) |
| **R46** | ? | ? | ? | 待你跑完 |
