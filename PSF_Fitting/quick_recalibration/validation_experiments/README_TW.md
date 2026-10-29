# Validation Experiments — PSF 快速校正方法的 A 階段算法驗證

> 用實驗校準 [`../DESIGN_TW.md`](../DESIGN_TW.md) §10 提出的階梯校正方法的所有閾值與 noise floor。
> 跟 [`PSF_Fitting/PSF_Fitting_ValidationLab/`](../../PSF_Fitting_ValidationLab/) 隔開——那邊是現行流程的修正驗證,這邊是新方法的算法驗證。

完整實驗設計、四層架構、acceptance criteria 在 DESIGN §10,**這份不重複設計層的內容**,只記:**現在跑到哪、什麼結論、下一步是什麼**。

---

## 進度看板

| 階段 | 狀態 | 子目錄 | 一句話結論 | 完整數字 |
|---|---|---|---|---|
| **L0 setA**(同張影像 BADS 多次) | ✓ 完成 2026-05-06 | [`L0_repeat_fit/`](L0_repeat_fit/) | 偵測到 2 個收斂域(機率 73/27);乾淨 noise floor 中位 std = 0.0286 | [outputs/L0_noise_floor_report.md](L0_repeat_fit/outputs/L0_noise_floor_report.md) · [outputs/L0_deep_analysis_report.md](L0_repeat_fit/outputs/L0_deep_analysis_report.md) |
| **L0 setB**(row 2,6,9 × col 2,6,9) | ✓ 完成 2026-05-14 | [`L0_repeat_fit_setB/`](L0_repeat_fit_setB/) | 對齊後 67/33;noise floor 0.0273 | [outputs/L0_noise_floor_report.md](L0_repeat_fit_setB/outputs/L0_noise_floor_report.md) · [outputs/L0_deep_analysis_report.md](L0_repeat_fit_setB/outputs/L0_deep_analysis_report.md) |
| **L0 setC**(row 3,6,8 × col 3,7,10) | ✓ 完成 2026-05-15 | [`L0_repeat_fit_setC/`](L0_repeat_fit_setC/) | 對齊後 80/20;noise floor 0.0225(主 basin 收斂特別死) | [outputs/L0_noise_floor_report.md](L0_repeat_fit_setC/outputs/L0_noise_floor_report.md) · [outputs/L0_deep_analysis_report.md](L0_repeat_fit_setC/outputs/L0_deep_analysis_report.md) |
| **L0 setD**(row 2,7,10 × col 3,4,7) | ✓ 完成 2026-05-15 | [`L0_repeat_fit_setD/`](L0_repeat_fit_setD/) | 對齊後 80/20;noise floor 0.0230 | [outputs/L0_noise_floor_report.md](L0_repeat_fit_setD/outputs/L0_noise_floor_report.md) · [outputs/L0_deep_analysis_report.md](L0_repeat_fit_setD/outputs/L0_deep_analysis_report.md) |
| **L0 跨 4 組對比** | ✓ 完成 2026-05-15 | (本 root) | 「2 個 basin」是 BADS 常態;主 basin 機率 75% ± 6.4%(範圍 13 個百分點);noise floor 量級跨組差 21.5% | [all_sets_comparison.md](all_sets_comparison.md) · [reference_basins.json](reference_basins.json) |
| **L1**(同機台重拍 100 張 × 3) | 待開始;前置驗證計畫見 [L1_PRECHECK_PLAN_TW.md](L1_PRECHECK_PLAN_TW.md) | — | — | — |
| **L2**(假介入:關機重開、輕碰外殼) | 待開始 | — | — | — |
| **L3**(真介入:拆裝物鏡) | 待開始 | — | — | — |

---

## L0 階段結論(已 freeze)

4 組 × 15 trial = 60 個 BADS run,加上 10 個深度分析(§6–§9 in [all_sets_comparison.md](all_sets_comparison.md))。

**穩定的事實**:
1. **2 個 mode 是常態**(4 組全 best_k=2)
2. **主/次 basin 機率 75 ± 6.4 個百分點**,跨組變動 13 個百分點,可當先驗(但 L1 跨拍攝沒驗證)
3. **Top 1 區別維度都是 Z5 defocus**,4 組一致
4. **15 個係數可信度分類 4 組完全一致**(7 trustworthy / 2 locked / 5 bound_saturated / 1 dead)
5. **Trial 內 9 視野一起決定** — basin 是 trial-level 決策,不是 FOV-level(setB/C/D 100% 一致、setA 87%)

**深度分析後浮現的新理解**:
6. **主 basin 跟次 basin 的 fval 幾乎一樣**(差 < 1 / 基準 1400+) — **兩個 basin 是等高的 local minima**,不是「正確解 vs 錯誤解」。次 basin 散焦值 0.70 比主 basin 0.14 大 0.55,加上球差 0.21、散光 0.05 的差距,代表兩個 basin 對應「散焦不同方向 + 對應的像差組合」兩種等效擬合
7. **noise floor 跨組差 21.5% 主要是擬合品質本身的差** — Pearson −0.814(主解佔比越高、noise 越低);setC fval 中位 1401 < setA 1453,擬合本來就乾淨
8. **MATLAB rng 不控制 basin 落點** — 4 組同 seed 落到同 basin 只有 26.7%,接近純隨機 25%。BADS 內部有 rng 控制不到的隨機性
9. **Basin pair distance 跨組變動 40.8%**(setA 1.89 → setC 2.67),「兩個 basin 拉多開」也是 FOV-dependent
10. **撞邊飽和係數 setC 最極端**(Z6/Z7/Z10 撞 lb 93%、Z14 撞 ub 93%),其他組撞兩邊較均勻

**對 DESIGN §9 attribution 設計的影響**:
- 第 6 條改變了 framing — Test 1 不再是「判正確 vs 錯誤」,而是「**判離兩個等高 reference basin 哪個近**」
- Layer 1c basin 機率核對的意涵也變 — 不是「BADS 對某 basin 有 bias」,而是「兩個合理解的物理權重」;L1 重點是「同機重拍會不會推這個權重」
- noise floor 可以取 4 組最大值(setA 0.0286)當保守分母,避免 false positive
- 第 8 條對 L1 設計有警示:rng 不可重現 → L1 設計不能用「同 seed 重跑驗證」確認 attribution

完整證據在 [all_sets_comparison.md](all_sets_comparison.md) §6–§9,基準 basin 在 [reference_basins.json](reference_basins.json)。

舊的兩組對比 [setA_vs_setB_comparison.md](setA_vs_setB_comparison.md) 保留作為歷史快照,已被 4 組 + 深度分析版取代。

---

## 下一步決策(等使用者選)

| 選項 | 動作 | 阻擋條件 |
|---|---|---|
| **(a) 改 DESIGN §9 歸因設計** | 把單層 z-score 改成兩層(判 basin + basin-internal z-score) | 無;L0 結論已充分 |
| **(b) L1 前置驗證** | 同機重拍 3 次,看主/次 basin 機率會不會偏離 70/30 | 無 |
| **(c) 累積 setC、setD** | 把 mode 機率穩定性的樣本數從 2 加到 4+(更強的統計信心) | 無;但邊際效益遞減 |
| **(d) 直接動手做 L1** | 跟 DESIGN §10 寫的 L1 完整版 | (a) 沒做的話,L1 的 attribution 分析腳本會卡 |

---

## 共用前提與依賴

所有實驗依賴的既有資源,本子專案不複製、不修改:

| 資源 | 路徑 |
|---|---|
| BADS 擬合核心 | `PSF_Fitting_ValidationLab/scripts/HDR_fitting_2D_WholeFOV_candidate_prealign.m` |
| Whole-FOV wrapper | `PSF_Fitting_ValidationLab/scripts/HDR_fitting_2D_WholeFOV_reasonable_v1.m` |
| 種子機影像 | `PSF_Fitting/Crop_circle_FreqFiltered/VisionTop_*.bmp` |
| GT | `PSF_Fitting/Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp` |
| 理論 PSF 基底 | `PSF_Fitting/SimulatePSF/psf_multi.mat` |
| BADS 套件 | `PSF_Fitting/bads-1.1.3/` |

MATLAB Current Folder 必須設為 `PSF_Fitting`。

---

## 污染控制(全實驗共用)

| 不要做 | 為什麼 |
|---|---|
| 拆裝中順便清鏡頭 | 變兩個變數 |
| 換不同物鏡 | 同上,且變數更大 |
| 中間移動 GT 樣本 | 影像位置變,Zernike 中心被吃掉 |
| 一天做不完拖到隔天 | 室溫差 5°C 足以造成可量測的 PSF 漂移 |
| 拆裝交給不同人 | 操作差異混入 |

精神:只動一個變數,其他全部凍結。
