# PROJECT STATE / 專案狀態

Last updated: 2026-10-30（資料夾重整與交機準備）；2026-10-28 收進 R152 IMPACT 2026 獨立工作區紀錄；2026-10-24 文件整併改寫，內容事實截至 2026-10-23

這份只寫**現在的狀態**。系統怎麼設計、怎麼判斷好壞看 [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)；機器可讀的正式身分是 [ESTIMATOR_POLICY.json](ESTIMATOR_POLICY.json)；整體巡檢用 `python Tools/project_control_center.py`；縮寫看 [docs/README.md](docs/README.md)。

<!-- QUICK_HANDOFF_START -->
## Quick Handoff

### 模型身分
- **正式基準：COMBO**（`r38v2_8px_gate_p95`，2026-04-08 生效，分支 `sandbox/r38v2`），用於公司端環形影像 + 外部 GMF 的正式量測。
- **核准替代（Approved Alternates）：** R33（定位極致）、R38v2（視覺優先）、R39R40_avg_a025（平衡）。身分不因後續研究改變。
- **論文採用：R152（論文稱 MOSR）對 RAW**，來自 2026-09 的 930 張實拍比較。R152 沒有取代 COMBO 的正式身分。

### 論文結果（nm，越小越穩）
- 單趟 30 步合併波動（九顆平均，論文口徑）：RAW 8.781 → MOSR 4.273（−51.3%，30 趟全部改善）；相鄰步 PI 誤差 6.969 → 3.598（−48.4%）。直徑重拍 32.750 → 13.252；輪廓重拍 63.758 → 18.600。
- **與 SEM 平均直徑差反而變大**（169.883 → 204.281）：更穩不等於更準。
- R153 十種方法（RAW、Wiener、EDSR、NAFNet、RDN、RCAN、Restormer、USRNet、SwinIR、MOSR）各 930 張完成；MOSR 在三個主要欄位為最低點估計，但訓練輪數不等；U-Net、MambaIRv2 因官方後端受阻未完成。
- IMPACT 2026 海報（TW0243）用同一份 R152 權重、不重訓：20×／50× 各 30 個 1 µm 單步，RAW 9.506 → MOSR 4.068 nm（−57.2%）、5.938 → 4.542 nm（−23.5%）。這是影像量測的位移，不是外部 GMF；正式基準不變。紀錄見下方 §2 的 IMPACT 小節。
- 完整交接：[R153 論文交接](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)。

### 讀數字前
- 九顆位移改用算術平均，是回應口試委員建議；R152 原紀錄用中位數（RAW 10.200 → 4.865，−52.3%），論文不再沿用。兩種口徑**不可跨表比較**。
- R152 的多 PSF 融合模組作用極小，R152 ≈ 底座 R148v2。SEM 曾參與 PSF 校準，不是獨立驗證。

### 保存狀態
- 相機原拍、SEM、模型、資料以 GitHub 發布附件保存，按需下載，不須整套取回。固定保存版本：[research-curated-20261021](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-curated-20261021)。
- **逐輪必要來源的查核仍在進行，不能宣稱全專案完整。** 缺口：R63 一個原選中模型（第 24 輪版本）、主專案 R36 無法辨認、R95 早期狀態與 9 個早期 ANN 量當年未寫出。
- 可再生的大型訓練資料不上傳，只保留生成程式、設定、種子與必要來源；舊的全量上傳與排程已停用（停止標記不得移除）。
- **這台電腦之後會交給別人，從此 GitHub 程式庫加發布附件是唯一完整的家。** 2026-10-28 起按角色重整資料夾（新舊對照見[重整操作紀錄](docs/operations/TREE_RESTRUCTURE_20261028.md)），程式改成從自己的位置找專案根。交機前仍要清點只在本機的東西，見 §4。

### 保護規則
- 不改正式基準與核准替代的身分；原拍、論文、正式模型、活動訓練來源受保護；不啟動新訓練或推論除非明確要求。
- D 槽清理只限已確認安全的副本；H 槽至少留 1 TiB。

### 閱讀順序
- 研究脈絡：[EXPERIMENTS.md](docs/reproducibility/EXPERIMENTS.md)；資料夾：[PROJECT_MAP.md](docs/navigation/PROJECT_MAP.md)；缺件：[KNOWN_GAPS.md](docs/reproducibility/KNOWN_GAPS.md)；保存細節：[STATUS.md](docs/reproducibility/STATUS.md)。
<!-- QUICK_HANDOFF_END -->

---

## Full Current State / 完整現況

### 1. 研究與正式身分

| 項目 | 現況 |
|---|---|
| 正式基準（formal production baseline） | COMBO，外部 GMF（越低越好）0.8 px 0.131560／0.08 px 0.099891／8 px 0.154515；比前任 R30 分別好 21.6%／36.7%／24.7% |
| 核准替代 | R33、R38v2、R39R40_avg_a025（2026-05-11 升級） |
| 開放支線 | R26NewPSFCheck（新 PSF 重訓，等外部 GMF，非主線） |
| 已結案 | R31、R32（external FAIL，0.8 px +97.7%）、R33c、R34／35／37、R38 等；失敗保留在各輪報告 |
| 下一輪政策 | 只在有新機制假說或新部署需求時開新輪次（規則見 ARCHITECTURE §4） |
| 研究範圍 | 177 個閱讀範圍 = 122 個主專案資料夾 + 26 個 Lab 研究 + 29 個早期分組；**不等於 177 次訓練** |

階段式脈絡見 [EXPERIMENTS.md](docs/reproducibility/EXPERIMENTS.md)；每輪結論以各輪 `reports/` 的正式報告為準，索引在 [Experiments/INDEX.md](Experiments/INDEX.md)。

### 2. 論文版本（R152 / R153）

- **R152 = R148v2（凍結）+ 受限 25 PSF 融合支路**，兩階段各 8192 次更新；參數 1,207,105（新增 12,699）。
- 實拍：2026-09-03，30 趟 × 31 位置 = 930 張，每步約 1 µm，固定 3×3 九顆圓，約 172.5 nm／像素。

R152 對 RAW（R152 原紀錄口徑，九顆取中位數，nm；論文改用下方 R153 的算術平均口徑，位移類數字以那張表為準）：

| 指標 | RAW | R152 |
|---|---:|---:|
| 單趟 30 步合併波動 | 10.200 | 4.865 |
| 單步相對 PI 平均絕對差 | 8.167 | 4.003 |
| 起點相對位移平均絕對差 | 19.081 | 18.002 |
| 直徑重拍波動 | 32.750 | 13.252 |
| 輪廓重拍波動 | 63.758 | 18.600 |
| 去尺寸形狀重拍波動 | 61.667 | 17.401 |
| 與 SEM 平均直徑差 | 169.883 | 204.281 |
| 走完 30 步相對 PI 平均有號差 | 40.892 | 42.842（配對區間跨零） |

R153 十方法（算術平均口徑，nm）：

| 方法 | 單趟波動 | 相鄰步對 PI | 輪廓重拍 | 訓練 |
|---|---:|---:|---:|---|
| RAW | 8.781 | 6.969 | 63.758 | — |
| Wiener | 5.953 | 4.793 | 27.885 | 無 |
| EDSR-x1 | 4.772 | 3.992 | 18.860 | 32 輪 |
| NAFNet | 4.747 | 3.919 | 21.810 | 32 輪 |
| RDN-x1 | 4.975 | 4.147 | 19.488 | 14 輪 |
| RCAN-x1 | 5.206 | 4.346 | 24.058 | 8 輪 |
| Restormer | 5.666 | 4.716 | 20.723 | 8 輪 |
| USRNet-x1 | 5.024 | 4.070 | 22.887 | 8 輪 |
| SwinIR | 5.100 | 4.272 | 27.494 | 8 輪 |
| **MOSR（R152）** | **4.273** | **3.598** | **18.600** | 8192+8192 次 |

效率（RTX A6000、FP32、單張 1544×2064，15 次前向）：MOSR 1.461 s、GPU 配置峰值 2.785 GiB（保留峰值 5.555 GiB）；EDSR-x1 0.526 s；NAFNet 0.513 s；RCAN 6.731 s；Restormer 5.007 s；USRNet 2.967 s；RDN 9.873 s／32.7 GiB；SwinIR 27.171 s。MOSR 沒有比 EDSR、NAFNet 快。速度不能推論量測效果。

**限制（請在任何引用時保留）：** 更穩不等於更準；長距離位移沒有明顯改善；外部模型訓練輪數不一、不代表收斂；所有外部模型與 Wiener 只用合成資料訓練／挑選；單一樣品單一時段；U-Net 與 MambaIRv2 未完成；RAW 與 MOSR 使用既有保存的圓心與輪廓，未重擬合。

#### R152 IMPACT 2026 海報驗證（2026-10-28 從獨立工作區收進 main）

這批驗證在 C 槽獨立工作區（分支 `sandbox/r152-impact2026`）完成，當時刻意沒有同步回主專案。以下各段是那個工作區紀錄的原文，「本獨立工作區」「本工作區」都指它。資料夾：[Experiments/R152_IMPACT2026Validation](Experiments/R152_IMPACT2026Validation/README.md)；逐張重建陣列在發布附件 [r152-impact2026-reconstructions-20261028](https://github.com/rio10255254/GMM_2_Final/releases/tag/r152-impact2026-reconstructions-20261028)。

##### R152 IMPACT2026 獨立工作區補充

<!-- R152_IMPACT2026_WORKTREE_ONLY -->
2026-09-29 本獨立工作區R152四條件120配對完成：20×原生25顆光學資料、50×原校正單核及推論輸入轉接；相同學得權重、未重訓。原配對及量測協議不變，共用光學版本保留為附加比較。正式基準不變。[完整結果](Experiments/R152_IMPACT2026Validation/reports/R152_RESULTS.md)

本工作區根層其餘內容源自較早的Git提交；當次D槽現況快照保存在本驗證資料夾sources中。未向D槽同步這些治理註記。

##### R152位移讀法追加核對

<!-- R152_LSC_ORDER_AUDIT -->
2026-09-29 R152位移稽核：確認原稿粗外框有處理順序依賴；相同LSC逐顆固定狀態後重算四方法120配對。R152為7.123347／5.489350／4.356654 nm，V42為7.367438／5.784830／4.908968 nm；三項新舊配對區間均包含零，50×兩項仍落後V42。原表保留，正式基準不變。[稽核](Experiments/R152_IMPACT2026Validation/reports/R152_DISPLACEMENT_AUDIT.md)

##### R152定位讀法研究

<!-- R152_LOCALIZATION_IMPROVEMENT -->
2026-09-29 定位讀法改良：以已知平移選定720方向重擬合LSC，同一讀法完成Raw/Wiener/R152全部120配對；R152三項7.113328／5.558788／4.258168 nm，原圖8.839481／7.233079／10.862548 nm。原圖也受益；R152名義平均差較前一固定狀態讀法略增，未全面改善、不升級正式基準。[結果](Experiments/R152_IMPACT2026Validation/reports/R152_LOCALIZATION_IMPROVEMENT.md)


##### MOSR海報統計呈現

2026-09-30 MOSR海報改版：保留原四条件各30單步位移，樣本標準差四組平均Raw 8.84→MOSR 7.11 nm，降低19.5%；各條件降低9.8–24.1%。未納入另批30趟重拍，未重訓或變更正式基準。[海報與核對](Experiments/R152_IMPACT2026Validation/reports/R152_POSTER_STEP_SD_SUMMARY.md)


##### MOSR兩倍率各30步海報

2026-09-30 MOSR海報改為20×／50×各30個1 µm單步位移分開展示。20×取論文首個驗證掃描，Raw 9.506→MOSR 4.068 nm（57.2%）；50×原鎖定30配對5.938→4.542 nm（23.5%）。完整930張三方法重測、50×86張重新推論核對通過。30趟及0.5 µm保留補充，不重訓或變更正式基準。[結果與海報](Experiments/R152_IMPACT2026Validation/reports/R152_30STEP_POSTER_RESULTS.md)


##### IMPACT2026海報設計更新

2026-10-03 TW0243海報設計完成：新增模型功能圖、實際64點邊界／LSC圓心示例、三方法數值表與改善解釋；保留兩倍率各30步及原57.2%／23.5%。PPTX、90×120cm PDF及公開內容核對通過。未重訓或改變正式基準。[最新版](Experiments/R152_IMPACT2026Validation/reports/R152_POSTER_DESIGN_SUMMARY.md)

### 3. 保存與重現狀態（截至 2026-10-23）

| 項目 | 現況 |
|---|---|
| GitHub 內容 | 919 份正式文件、1,885 份主要程式、322 份設定與主版本相符；80 個本機分支版本都可由 GitHub 歷史到達 |
| 發布版本 | 23 個發布、211 個附件，約 124.7 GB（2026-10-22 統計）；草稿 0 |
| 不可替代原拍 | 930 張位移重拍 + 30 份平台紀錄（[Shared_Sources/PI_Repeatability_20260903](Shared_Sources/PI_Repeatability_20260903/README.md)）；PSF100 的 100 張 2025-09-03 全幅原拍（及完整 395 張挑圖來源）、0615 三輪 726 張；Lab 2026-06-05 的 25 張原校正；皆已發布並取回核對 |
| 模型 | 16 個精選固定模型；31 個 R63 選用模型、R32 選用／R147 最後模型、R108B/C 的 15 個小模型已補；清單見 [MODEL_GUIDE](docs/reproducibility/MODEL_GUIDE.md) |
| 原表 | 247 份重要原表／SEM 工作表／平台 CSV 提出供直接閱讀（約 14.6 MB） |
| 資料生成 | 18 條確認的資料路線；R94–R98 共用 R93 基礎，R99/100/102–104 共用 R92 基礎，**不可互換**；R108 兩套資料已由取回的程式重新生成並與歷史檔案相同；R61 v16 的 3,400 組繼承來源與歷史幾何仍需原件 |
| 重做驗證 | 多組小型包已在乾淨環境從 GitHub 取回並重算（R93、R94/95/97/98、V42 等），**沒有重跑全部歷史 GPU 訓練** |
| 儲存清理 | D 槽已確認安全的副本清理，累計約 282.31 GB；H 槽剩餘 >1 TiB；原拍、論文、正式模型、活動訓練保留 |

**保存原則（2026-10-21 使用者確認）：** 目標是精選、輕量的研究倉庫。原程式、設定、完整量測／比較表、方法、失敗與必要代表成果留在 GitHub；大型訓練資料、逐張重建陣列與中途模型留本機／H 槽，只記錄來源、身分與重建方式。原始拍攝、儀器量測、人工標記與完整實驗結果不能以生成程式取代。舊的全量上傳與排程已停止。

### 4. 缺件與重做界線

| 項目 | 狀況 |
|---|---|
| R63 | 原 32 個選用模型找回 31 個；缺第 24 輪版本（舊清理紀錄顯示 2026-08-13 刪除其目錄）。不用後來的第 60 輪替代 |
| 主專案 R36 | 找不到獨立證據。Lab R61 內部 r36 另有完整紀錄，不能代替 |
| R32 處理輸入 | 已凍結 100 張 EQ 輸入，從相機原拍到該版本的完整對照未找到 |
| R95 與早期 ANN | 第一次回到第 8 輪的更新／亂數狀態、9 個早期 ANN 量當年未寫出，不補造 |
| 其餘逐輪來源 | 已對 62 個範圍的指定面向核對；全專案閉合**尚未宣稱** |
| 已找回 | R94 的 19 版與 R95 的 3 版早期程式、R13 較早公式（216 項分數與 5 次選擇重算相同） |
| 外部 GMF 量測程式 | 廠商提供的量測工具，在本機 `E:/GMM_Software/GmmVisionToolExe_20260107`，不在 GitHub。各輪的外部 GMF 結果已保存，但交機後要重新量測，得另外取得這個工具 |
| H 槽封存路徑 | 仍有地方寫著 `H:/From_2TB_D_disk`、`H:/GMM_2_Final_Archive` 的位置：程式裡約 40 處（28 支 Python、少數 PowerShell 與 MATLAB），其餘約 5,600 處在 1,025 份 JSON 清單與取回紀錄裡（2026-10-30 統計）。H 槽不會跟著 GitHub 走；那些資料是否都已在發布附件，屬於交機前清點，尚未完成 |
| 只在本機的內容 | 未提交的改動、其他工作目錄、`D:/NTU_ImageDataset`、`E:/MitsutoyoSample_GMMSys_20x` 等外部資料還沒逐項清點；清點後先給專案負責人看清單，再決定上傳哪些 |

細節：[KNOWN_GAPS.md](docs/reproducibility/KNOWN_GAPS.md)、[STATUS.md](docs/reproducibility/STATUS.md)。

### 5. 保存工作收據索引

2026-10 的保存工作產生大量逐批收據；它們是**保存紀錄，不是科學結論**，各自只證明當時列出的範圍。

| 想知道 | 入口 |
|---|---|
| 目前保存程度 | [STATUS.md](docs/reproducibility/STATUS.md)、[COMPLETENESS_AND_CAPACITY.md](docs/reproducibility/COMPLETENESS_AND_CAPACITY.md) |
| 精選範圍與固定版本 | [SELECTIVE_DELIVERY.md](docs/reproducibility/project_completion/SELECTIVE_DELIVERY.md)、[逐輪精選清單](docs/reproducibility/project_completion/curated/ROUND_CURATED_PLAN.md) |
| 逐輪必要來源核對 | [round_source_followthrough_20261022](docs/reproducibility/round_source_followthrough_20261022/README.md)、[round_source_reviews](docs/reproducibility/round_source_reviews/) |
| 395 份優先原件補件 | [priority_sources_20261022](docs/reproducibility/priority_sources_20261022/README.md) |
| 原拍補全 | [PSF_Camera_Acquisitions](Shared_Sources/PSF_Camera_Acquisitions/README.md) |
| 研究沿革、R1–R153 逐號表 | [lineage](docs/reproducibility/lineage/README.md) |
| 模型、附件、生成方法、文獻 | [MODEL_GUIDE](docs/reproducibility/MODEL_GUIDE.md)、[ASSET_GUIDE](docs/reproducibility/ASSET_GUIDE.md)、[GENERATION_GUIDE](docs/reproducibility/GENERATION_GUIDE.md)、[LITERATURE_GUIDE](docs/reproducibility/LITERATURE_GUIDE.md) |
| D／H 槽清理與取回 | [D_DRIVE_FULL_CLEANUP_20261022](docs/operations/D_DRIVE_FULL_CLEANUP_20261022.md)、[PROJECT_ARCHIVE_INDEX](docs/operations/PROJECT_ARCHIVE_INDEX.md) |
| 較早的程序狀態 | `docs/archive/legacy_runtime_status/`（僅供歷史查閱，不取代本頁） |

### 6. 本頁的歷史版本

本頁在 2026-10-24 前是一份約 16 萬字、逐日累積的保存流水帳。完整原文逐位元組保留在 [docs/history/BEFORE_PLAIN_REWRITE_20261024/PROJECT_STATE.md](docs/history/BEFORE_PLAIN_REWRITE_20261024/PROJECT_STATE.md)（也可看 [GitHub 上的 d12dd7e0 版本](https://github.com/rio10255254/GMM_2_Final/blob/d12dd7e0/PROJECT_STATE.md)）；更早的交接見 [docs/history/](docs/history/README.md)。本次改寫只整理敘述，沒有改變任何研究結論、採用判決或保存事實。
