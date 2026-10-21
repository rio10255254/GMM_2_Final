# Thesis MOSR Evidence / 論文 MOSR 主軸補測證據庫

Last updated: 2026-09-26

## 模型設計與效果回顧入口

若要按實驗輪次快速回顧模型架構、實際效果、成功／失敗原因與後續建議，請從 [Research_Design_Effect_Review_20260926](Research_Design_Effect_Review_20260926/README.md) 開始。這是約300MB的輕量閱讀包；大型重建、權重和訓練資料仍由來源索引連回原實驗。

## 這個目錄存在的目的

`Thesis_MOSR_Evidence/` 收納所有**為論文 MOSR 主軸補測**而做的分析。

論文 (`Thesis_v2_MOSR.docx`) 第 4.8 節設下了「誤差型態轉換」的三項量化判準,但專案既有實驗報告 (`Experiments/R##_*/`) 用的是 `step_std / PSNR / SSIM / 邊界 F1` 這套語言,**沒有任何腳本算過 σ̂-b 分解、k=2 振幅 CV、邊界殘差熱點集中度、σ̂-vs-CRB 比值**。

這個目錄存在的唯一目的就是補上這些指標,讓論文第 6 章可以實證宣稱「誤差型態轉換」這條主軸,而不是空頭支票。

## 跟既有 `AnalysisLab/` 的分工

| | `AnalysisLab/` | `Thesis_MOSR_Evidence/` |
|---|---|---|
| 第一層組織 | **Version-first**(`r26/`, 未來 `r30/`...) | **Thesis-section-first**(對應論文章節) |
| Scope | 單一版本的多面向分析 | **跨多個 checkpoint 算同一個指標** |
| 服務對象 | 模型開發/部署稽核 | 論文寫作 |
| 報告語言 | 通用幾何品質分析 | 論文主軸的 quantitative evidence |

兩個目錄不重複,功能互補。AnalysisLab 是「我想理解這個版本的所有面向」;Thesis_MOSR_Evidence 是「我想跨所有版本算這個論文指標」。

## 三層敘事結構

這個目錄的子目錄結構,**直接對應論文第 6 章的章節順序**:

```
現象 (decoupling) → 機制驗證 (error_type_transformation) → 方法歸因 (method_ablations)
   ↓                       ↓                                    ↓
visual_vs_metric_      error_type_                          method_
decoupling/            transformation/                      ablations/
```

第一層**展示現象**:視覺銳利度跟量測穩定度是解耦的——這是論文最直接、最易溝通的發現。

第二層**驗證機制**:用論文 4.8.5 的三項判準(σ̂ 收斂 + k=2 CV 下降 + 邊界熱點集中)+ Tier 2 的 CRB 比值,證明「神經重建在量測情境下是誤差型態轉換器」這個假說。

第三層**做方法歸因**:用 ablation 證明 MOSR 框架裡哪些方法元件是必要的(多幀一致性、三類物理殘差、PSF 空間校正)。

寫第 6 章的時候,**從這三層由上而下展開**,讀者會從「看到一個反直覺現象」→「理解背後機制」→「知道哪些方法元件造成這件事」三步建構出對 MOSR 的完整理解。

## 目錄結構

```
Thesis_MOSR_Evidence/
├── README.md                                    (本檔)
│
├── visual_vs_metric_decoupling/                 對應論文第 6 章開場
│   ├── README.md
│   ├── scripts/                                 (跨候選資料收集 + 四象限散佈圖)
│   ├── tests/
│   ├── results/                                 (圖 + JSON 摘要)
│   └── reports/                                 (decoupling_evidence.md)
│
├── error_type_transformation/                   對應論文 4.8.1 / 4.8.2 / 4.8.4 / 4.8.5
│   ├── sigma_hat_decomposition/                 4.8.1 σ̂ + b 隨機/系統性誤差分解
│   ├── k_mode_stability/                        4.8.2 k=2 振幅幀間 CV
│   ├── residual_hotspot/                        4.8.5 第三項判準:邊界熱點集中度
│   └── crb_ratio/                               4.8.4 σ̂ vs CRB 資訊理論下限
│       (各自含 scripts/ tests/ results/ reports/)
│
└── method_ablations/                            對應論文 4.3 / 4.5 / 4.6
    (子目錄等 Tier 1 完成後再建)
    ├── single_vs_multi_frame/                   4.6 多幀一致性是否必要
    ├── physics_residual_ablation/               4.5 三類物理殘差各自貢獻
    └── psf_calibration_ablation/                4.3 PSF 空間校正 vs 全域單一 PSF
```

## 進度追蹤

| 子分析 | 對應論文段 | 狀態 | 主要產出 |
|---|---|---|---|
| **Tier 1 總評** | — | **COMPLETE(2026-05-26)**:5/5 判準通過 | `TIER_1_FINAL_VERDICT.md` |
| **Tier 3 ablation verdict** | 4.5 / 4.6 | **COMPLETE(2026-05-27)**:13 候選 external GMF + internal 對比;EDGE 是核心 anchor,SEQ 主要在 8 px,EQ 弱 | `method_ablations/reports/ablation_external_gmf_verdict.md` |
| **Tier 2 spectrum verdict** | 4.5 / 4.6 / 4.8.3 | **COMPLETE(2026-05-27)**:13 候選完整邊界寬度 + 9 候選視覺指標;SEQ 是銳化 anchor,EDGE 是位置穩定 anchor 雙維度分工 | `_extended_candidates_internal/reports/extended_spectrum_verdict.md` |
| visual_vs_metric_decoupling | 第 6 章開場 hero figure | DESIGN(sigma_vs_b spectrum 已可代替) | σ̂+b 散佈圖已在 sigma_hat_decomposition 出 |
| error_type_transformation / sigma_hat_decomposition | 4.8.1 | **REPORT_DONE(13 候選含 4 ablation)**:C1+C2 通過 | `reports/c1_c2_verification.md` + `results/sigma_b_table.csv` |
| error_type_transformation / k_mode_stability | 4.8.2 | **REPORT_DONE(4 + 4 ablation 候選)**:C3 通過 | `reports/c3_verification.md` + `method_ablations/results/ablation_k2_hotspot_combined.csv` |
| error_type_transformation / residual_hotspot | 4.8.5 第三項 | **REPORT_DONE(4 + 4 ablation 候選)**:C4 通過 | `reports/c4_verification.md` |
| error_type_transformation / crb_ratio | 4.8.4 | **REPORT_DONE(4 候選,proxy)**:C5 通過 | `reports/c5_verification.md` |
| error_type_transformation / pi_xy_validation | 4.8.1(獨立驗證) | PENDING_DATA(等 PI 實驗) | σ̂+b 用 PI 真值重做 |
| method_ablations / single_vs_multi_frame | 4.6 | **COMPLETE**:internal + external 都跑完,主要 effect 在 8 px(σ̂ +131%),0.8 px 無顯著 effect | `_ablation_external_gmf/NO_SEQ/` |
| method_ablations / physics_residual_ablation (no_eq) | 4.5.1 | **COMPLETE**:external 沒獨立 effect(可能跟 SEQ 互補) | `_ablation_external_gmf/NO_EQ/` |
| method_ablations / physics_residual_ablation (no_edge) | 4.5.3 | **COMPLETE**:三尺度 σ̂ 全退步(8px +115% / 0.8px +96% / 0.08px +45%),**核心 anchor** | `_ablation_external_gmf/NO_EDGE/` |
| method_ablations / physics_residual_ablation (no_freq) | 4.5.2 | **COMPLETE**:中等 effect(σ̂ +10-19%, 0.08px b 翻向) | `_ablation_external_gmf/NO_FREQ/` |
| method_ablations / psf_calibration_ablation | 4.3 | PENDING_AUTH(implementation 1-2 天,等使用者拍板) | 單一全域 PSF 對照訓練 |

狀態值:`NOT_STARTED` / `DESIGN` / `SCRIPT_DRAFT` / `RESULTS_READY` / `REPORT_DONE`。

## 子目錄子結構約定

每個子分析(`visual_vs_metric_decoupling/`、`error_type_transformation/*/`)固定遵循:

| 子目錄 | 放什麼 | 必要性 |
|---|---|---|
| `README.md` | 本子分析的設計、候選清單、指標定義、資料來源、預期輸出 | 必備 |
| `scripts/` | 一個 `.py` 就是一條完整分析管線(從讀資料到產圖) | 必備 |
| `tests/` | pytest 驗證指標計算正確 | 強烈建議 |
| `results/` | PNG 圖 + JSON/CSV 摘要,即使不跑腳本也能閱讀 | 必備 |
| `reports/` | 中文 markdown 報告,含數據表、解讀、論文對應段 | 必備 |

跟 `AnalysisLab/` 的子結構慣例完全一致,將來如果要把整套移到 AnalysisLab 底下也很容易。

## 怎麼新增一個子分析

1. 在 `error_type_transformation/` 或 `method_ablations/` 底下開新子目錄,**先寫 README**——說明它對應論文哪一段、要算什麼、資料從哪來、預期輸出
2. README 經過 review 後再寫 `scripts/`
3. `scripts/` 跑出 `results/` 後再寫 `reports/`(中文 markdown,含數據解讀跟論文對應段)
4. 更新本檔的「進度追蹤」表

## 跟 `Experiments/R##_*/` 的關係

`Thesis_MOSR_Evidence/` **不訓練任何模型**,所有 checkpoint 都來自 `Experiments/R##_*/`。如果某個分析發現需要訓練新東西(例如 single-frame baseline ablation),那是 `Experiments/R##_*/` 該開新輪次的事,**結果回頭被這裡引用**。

絕對不要在 `Thesis_MOSR_Evidence/` 底下放 checkpoint 或長時間訓練腳本——這裡的腳本應該都是「讀現成 checkpoint + 算指標 + 出圖」的後分析。
