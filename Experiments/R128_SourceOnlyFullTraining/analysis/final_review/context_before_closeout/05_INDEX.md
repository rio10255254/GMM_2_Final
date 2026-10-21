# 實驗索引 / Experiment Index

Last updated: 2026-09-09 17:12（R128前兩組完成，第三組中止後已獨立啟動續跑，第四組待執行）

一頁式快速索引——完整數字、checkpoint 路徑、外部 GMF 結果見 `ESTIMATOR_POLICY.json` 與各實驗 `reports/`。

視覺 demo 圖（每輪代表性重建圖 / 指標圖）見根目錄的 [`RECON_GALLERY.md`](../RECON_GALLERY.md)。

---

## Active（formal baseline + approved alternates）

| Round | 目錄 | Branch | 角色 | 關鍵報告 |
|-------|------|--------|------|---------|
| **COMBO** | `R38v2SeqFixed/` | `sandbox/r38v2` | formal production baseline | `R38v2SeqFixed/reports/COMBO_RESULTS.md` |
| **R33** | `R33RobustLoss/` | `sandbox/r33` | GMF extreme alternate | `R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md` |
| **R38v2** | `R38v2SeqFixed/` | `sandbox/r38v2` | visual priority alternate | `R38v2SeqFixed/reports/R38v2_RESULTS.md` |
| **R39R40_avg_a025** | `R39_ShapeGeneralization/results/a030_x_a043_sweep/` | (cross-round; checkpoints from `sandbox/r39` + `sandbox/r40`) | balanced full-spectrum alternate（2026-05-11 升級）| `R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md` |

## Open Research / Side Tracks

| Round | 目錄 | 狀態 |
|-------|------|------|
| R128 完整研究訓練 | [最新中斷核對](R128_SourceOnlyFullTraining/reports/R128_RUNTIME_CHECK_20260909.md)・[目前進度](R128_SourceOnlyFullTraining/reports/TRAINING_PROGRESS.md) | 前兩組8192更新與預定檢查完成；第三組5359後程序消失，已從5248存檔以獨立背景程序續跑。第四組待執行；原科學設定不變，尚未完成最終單一模型選用 |
| R127 量測與保留修正 | [完成範圍與物理限制](R127_MeasurementPreservationRepair/reports/R127_RESULTS.md) | 原生SEM尺寸比例與取邊範圍、具有效性判斷的位移讀法、已知條件下原樣保留均完成。72個新參數測試通過；48完整視野輸出保留原小區塊，24組模型全圖位移與Raw相近。沒有新訓練或採用；材料邊界與獨立實際位置仍需對照 |
| R126 可學習性與亮暗擴充 | [完整驗證與下一步](R126_LearnabilityPhotometry/reports/R126_RESULTS.md) | 六組固定診斷768更新＋四組資料對照512更新、8次實拍评估全部完成。固定例子學習改善；暗例子Q比P誤差降低18–19%，但乾淨輸入改動加大，SEM參考結論分歧，位移讀值仍跳動。不採用或擴大訓練 |
| R125 資料修正與實際小試 | [完成範圍與不採用結論](R125_DataAlignedPilot/reports/R125_RESULTS.md) | 保留第一版失敗，修成8倍生成／4倍成像／2倍學習；64場景通過原限制。六組各64次更新共384次，12次實拍評估與來源核對完成。A正常曝光略好但暗曝光退步，B/C無可靠改善；資料亮暗與實拍仍有缺口，不擴大訓練 |
| R124 可執行模型原型 | [實作與實際運行結果](R124_RealFirstPrototype/reports/R124_RESULTS.md) | 四步完整二維模型、26項測試、兩張640px反向運算與分塊核對完成；6張實拍12份輸出、432筆SEM半對比讀值介接。未訓練、未校準、無效益或升級宣告；原始失敗及讀值敏感性保留 |
| R123 真實優先的下一代設計 | [架構、資料與實際核對](R123_RealFirstModelDesign/reports/R123_RESULTS.md) | 選定完整二維迭代重建與觀測核對、獨立幾何診斷。核對438個來源檔、364個主要真實光學檔與144個既有Raw選區；每次短測直接跑真實顯微／SEM。模型尚未實作／訓練，沒有新成績或升級 |
| R122 原理與資料來源驗證 | [實測結論與設計依據](R122_OperatorPrinciples/reports/R122_RESULTS.md) | 7,776 組操作、360 組修正後成像實測；像素插值不能當作純粹位置／寬度分離。V42 的 201 張位移評估來源、9 個尺寸答案均出現在訓練清單；1,000 組序列驗證也重用訓練影像對。下一步先做連續二維操作器，不以超越 V42 為目標；沒有新訓練或模型升級 |
| R109 / R119 固定模型量法核對 | [三種讀法與路徑比較](R119_SequenceGeometryValidation/reports/R119_R109_READOUT_COMPARISON.md) | 36 柱 ×12 曝光：R109 對 Raw 的 ACM 優勢不等於中點更準；R119 在兩者均較 R109 差。最陡點三方有效覆蓋不足，不能當一致通過。位置通道也會壓窄邊緣，R119 更明顯。無訓練、無升級；下一步先分清邊界定義與平移／寬度操作 |
| R119 模糊／亮度／位移控制與決斷 | [控制檢查與工作順序](R119_SequenceGeometryValidation/reports/R119_CONTROLLED_BOUNDARY_FACTORS.md) | 240 主條件＋100 亮度追查完成；標準模糊圓形受益於向外修正，但真實 Raw 對 SEM 已外偏約 0.661px。優先核對成像／邊界參考及亮度對比覆蓋，保留位置能力，不硬設縮小量、不啟動長訓練；物理來源尚未唯一確定 |
| R119 訓練位置分工診斷 | [已知答案與固定模型診斷](R119_SequenceGeometryValidation/reports/R119_TRAINING_POSITION_DIAGNOSIS.md) | 現有要求會罰最終影像膨脹，但無法區分相同輸出的位移／細節補償。固定 E42 關閉位置後，合成影像誤差在多數抽查場景反而增加；真實操作量則一致向外。原因範圍縮小，尚未證明單一訓練根因；無新訓練 |
| R119 跨曝光位置修正診斷 | [完整診斷結果](R119_SequenceGeometryValidation/reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md) | 固定 E42、12 曝光 × 36 柱；只關閉位置修正後 431/432 次輪廓改善、36/36 顆跨曝光中位數改善，但 282/432 次仍不如 Raw。位置路徑造成膨脹的證據跨曝光成立；細節保真與修改後位移未證實。舊證據不變，無新訓練或升級 |
| R118 / R119 Physical Coordinate Repair | [因果剖析與更正](R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md); `R118_PhysicalCoordinateRepairScratch/`; `R119_SequenceGeometryValidation/` | R119 B E42 訓練完成，但「忠實完成 P00–P12」已撤回：固定光學序列未接入訓練、對照與量測有混淆。保留實測 ACM/LSC 能力；單曝光真實 SEM 拆解指向邊界位置修正造成膨脹，並非證明必須犧牲細節。研究候選，不升級 |
| R88 Measurement Faithful Scratch | `R88_MeasurementFaithfulScratch/` | 設計與門檻已鎖定，尚未建立資料或訓練。預計以 5,120 個帶紋理程式觀察，從零同時約束邊界、ACM、正負次像素位移、系統偏差、真實紋理安全與分塊一致性；正式基準不變 |
| R87 Tile Native Scratch Generalization | `R87_TileNativeScratchGeneralization/` | 單次 100 輪從零訓練完成；分塊一致性與自身內部 ACM 通過，但 R73 新形狀與 R74 困難顯微明顯退化並產生假孔洞，因此不升級。保留為切片穩定研究模型與 R88 問題證據 |
| R83 R79 Severe Microscopy Strengthening | `R83_R79SevereMicroscopyStrengthening/` | 已完成但不升級。兩種乾淨微調都未超過 R79；保守整圖輸出在 R74 輪廓改善 23.42%，並通過 384 組保留合成影像、24 顆保留 SEM 與 6/6 真實位移，但 512 切片一致性失敗。因此預設仍為 R79，保守輸出只留作整張影像的受限選項，COMBO 正式 baseline 不變 |
| R79 R75v3 Dense Microscopy Scratch Generalization | `R79_R75v3_DenseMicroscopyScratchGeneralization/` | 第 23 輪 EMA 是目前研究線的強顯微候選，尚未取代正式 COMBO。R84-R86 已確認任何切片都會改變 R79 結果，因此來源入口與 ONNX 交付已根治為單次完整影像重建；12/12 跨場景逐像素對照通過，最大差 1 階灰階 |
| R61 STEP Generalization | `R61_STEP_Generalization_20260623/` | 近期多輪 R61 測試已收回 R 系列主線。這批不是雜散暫存，而是 Step/論文主力模型候選的研究線；最重要的是 `R61_stepguard_v16_dpv96_matched_20260623`。目前支撐 Step 樣本的位移穩定與 CD/形狀不失真證據，但尚未升級為 formal baseline，COMBO 仍是正式 baseline |
| R45 Family Boundary Adapter | `R45_FamilyBoundaryAdapter/` | R45A/R45B 完成：輸出端小校正守住位移但沒有改善大區塊/混合形狀；R45B 確認能力分散存在（逐張 oracle `0.2253` vs R44B `0.3384`，改善 `33.42%`；固定分族 oracle `0.2968`，改善 `12.30%`），但老師優勢不乾淨，多數老師在邊界像素殘差方向比 R44B 更差。研究負結果，不送外部 GMF；下一步若繼續單一入口，應做中間特徵層小分支 + 局部選擇器 |
| R44 Universal Boundary Motion Fidelity | `R44_UniversalBoundaryMotionFidelity/` | R44A-R44H Step B 皆已完成；`r44_motion_from_r42_best` 仍是最佳通用位移候選（整體位移 `0.3813 px`、格線位移 `2.2457 px`）。R44H Step A 證明家族平均可改善大區塊/混合形狀但會犧牲位移；Step B 單一老師局部蒸餾守住位移（`0.3837 px`）但形狀錯誤變差（`0.3481` vs `0.3384`）。研究成功但不可升級；不建議進 Step C 多老師全模型蒸餾，下一步應轉向 adapter / 分族小頭 / 分族選擇 |
| R43 Candidate Usability Audit | `R43_CandidateUsabilityAudit/` | analysis-only 近期候選堪用性盤點與肉眼檢查圖完成；沒有新候選可全面取代 COMBO；`R39 a030` 是最接近正式替代討論的近期候選，`R42` full endpoints 是顯微邊界重建最有價值的研究/人工檢查候選，但後補外部 GMF 確認不能作正式量測替代 |
| R42 Microscopy Boundary Fidelity | `R42_MicroscopyBoundaryFidelity/` | 訓練、本地完整分析、低比例權重平均、守門 KD 診斷與外部 GMF 補測皆已完成；R42 明顯改善未看過顯微邊界重建（最佳 PSNR 34.18、boundary F1 0.87，COMBO 為 20.55 / 0.63），但最佳外部候選 `r42_r41_best` 仍退步過大（8px +24.63%、0.8px +94.33%、0.08px +98.87%），所以 R42 僅保留研究用途，不建議作量測替代 |
| R41 Ring Distillation | `R41_RingDistillation/` | 訓練與 COMBO/R41 權重掃描已完成；direct endpoint 證明顯微能力很強（PSNR `29.4556` / HF `0.7241`），但沒有任何平均 alpha 同時通過顯微能力與本地環形守門；高 alpha 0.45/0.50 顯微通過但 0.8px/0.08px 環形失敗，所以 R41 僅作研究紀錄，不送外部 GMF。2026-08-01 完整歷史已核對封存至 H 槽，D 槽保留正式報告、摘要與恢復指引 |
| R40 Microscopy Feature Coverage | `R40_MicroscopyFeatureCoverage/` | 訓練、本地分析與外部 GMF 已完成；端點證明顯微特徵能力可被推高，但環形能力退步；`r40_combo_best_avg_a045` 改善顯微驗證，外部 8px 卻比 COMBO 退步 +22.80%，所以 R40 僅作研究紀錄，不升級 |
| R39 Shape Generalization | `R39_ShapeGeneralization/` | 訓練 endpoint 不可升級；`r39_combo_strong_avg_a030`（α=0.30 權重平均）external GMF PASS_TRADEOFF（8px −6.94%、0.08px −15.97% 專案歷史最低、0.8px +6.42% 在 alternate 容忍區內）；視覺在 sharp band（edge_steepness 比 COMBO 退 5.6%，遠優於 R33 soft band）；alternate-grade，等專案決策是否升級 |
| R26 PSF | `R26NewPSFCheck/` | pending external GMF; not active mainline |

## Closed / Falsified

| Round | 目錄 | Branch | Verdict |
|-------|------|--------|---------|
| R121 | [四組短測完整結果](R121_BoundaryAnchorFactorial/reports/R121_RESULTS.md) | `codex/r121-boundary-anchor` | 八次有效 12 輪短測完成；資料、位置與合併改動在兩種子／兩套 SEM 參考下，均 36/36 顆比對照差，細節誤差增 8.80%–17.95%。不採用、不長訓練；失敗原型與全部證據保留。本次設定的負結果，不代表所有局部位置方法均被否定 |
| R84 / R85 / R86 | `R84_R79TileStableRootRepair/`、`R85_R79SharedCanvasOpticalRepair/`、`R86_R79BlockGroupNormRepair/` | `sandbox/r84-r79-tile-stable-root-repair` | 三種結構修復都消除切片差異，但分別傷害 SEM 或邊界品質，不升級。保留精確 R79 並鎖定全圖入口；結案見 `R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md` |
| R32 | `R32Sandbox/` | `sandbox/r32` | external FAIL, 0.8px +97.7% |
| R33c | `R33ContrastFix/` | `sandbox/r33-contrast` | contrast fix did not recover |
| R34 / R35 / R37 | (sandbox only) | `sandbox/r34` / `r35` / `r37` | all failed to restore sharpness |
| R38 | `R38SeqConsistency/` | `sandbox/r38` | seq all-stages noise corrupted 0.8px |

Round31（legacy batch）亦 closed，見 `Traing_Progress/organized_20260316/round31/`。

## 完整系列報告

R33 → R38v2 → COMBO 的 12 候選 / 7 輪完整系列見 `R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`。

## 規範文件

- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 命名、模板、SOP 三合一
- `docs/operations/QUIRKS.md` — 歷史遺留事項
