# 專案未來檔案結構與容量生命週期藍圖

Last updated: 2026-08-13

## 文件身分

這是檔案結構與長期整理的設計準則，不是已完成的搬遷結果，也不是刪除授權。正式研究結論、模型身分與報告權威位置仍以 `PROJECT_STATE.md`、`ESTIMATOR_POLICY.json`、`Experiments/INDEX.md` 與各實驗正式報告為準。

本版是在 2026-08-10 全專案清冊後，再對照 2026-08-13 的真實專案重新審查所得。第二版刻意減少新資料夾、新索引與大規模搬遷：**保留已經工作的骨架，只讓未來新增內容有清楚歸屬，並把完成後的大量過程資料移出 D 槽。**

## 第二版審查結論

第一版的安全原則正確，但有三個過度設計：

1. 同時規劃 `PROJECT_CATALOG`、`DATASET_CATALOG`、`RESULT_CATALOG`，會增加三份容易落後的中央清單；目前連既有實驗索引與容量登錄都已出現更新落差，不應再增加人工維護面。
2. 規劃把 LabSystem 搬到新 `Workspaces`、把日期型分析搬進 `Analyses/AnalysisLab/projects`，會改寫大量已記錄路徑，也與 AnalysisLab 現有「模型版本優先」設計衝突。
3. 對所有實驗強制同一棵結果樹，無法涵蓋 R87–R95 已經形成的自包含研究模式。

因此第二版改成：

- 不建立 `Workspaces`。
- 不搬動 LabSystem、PSF、論文證據區與既有日期型分析的正式入口。
- 不新增三份人工維護的中央 catalog。
- 保留一份跨區域專案地圖，其他身分回到既有真相文件與各自 manifest。
- 實驗採「固定最小核心 + 兩種擴充型態」，而不是一棵樹套到底。
- 整理大型舊區域時優先「原位薄化 + H 槽封存」，不是重新安置整個工作區。

## 本版採用的實證

### 2026-08-10 全專案清冊

- 2,822,006 個檔案、341,031 個資料夾、1,067.416 GiB。
- 1,656,171 個路徑長度達 240 字元以上。
- LabSystem 約 435 GiB，且大量歷史與程式已記錄現有位置。

### 2026-08-13 再檢查

- `Experiments` 已有 50 個實驗目錄，合計 320.331 GiB、390,904 個檔案。
- R87–R95 九輪合計 180.184 GiB、105,793 個檔案，證明主要風險是「新輪次快速累積卻沒有即時收尾」，不是根目錄名稱本身。
- R87–R95 的完整 scratch 實驗自然採用 `config/model/training/inference/tests/data/runs/weights` 自包含模式；這個模式合理，不應拆散。
- 目前結構檢查為 12 個錯誤、29 個警告，主要是舊實驗缺 README／MANIFEST，以及新輪次尚未進中央索引。
- 文字與設定檔中，100MG 分析現有路徑出現於 1,734 份檔案、20x/5x 分析出現於 2,749 份檔案、`Traing_Progress` 出現於 2,322 份檔案。實體搬家會製造遠大於收益的改寫與驗證成本。
- R95 正在正式續訓，但使用近期自包含實驗的 `runs/active_run.json`，舊容量工具只看 `active_formal_run.json`，曾錯誤顯示沒有活動輪次。守門工具已加入相容辨識，缺程序編號、狀態不明、失敗、中止或仍宣告活動的標記都會阻擋大量操作；未來啟動器仍只使用標準標記。

## 八條設計原則

1. **歸屬比外觀重要**：每份新內容只能有一個明確主人，例如某輪實驗、PSF、論文或正式交付。
2. **穩定工作區永久保留**：已被大量引用的 Model、Training_Data、Traing_Progress、PSF、Thesis 與 LabSystem 不為美觀搬家。
3. **一個真相，一個入口**：正式內容只在既定權威位置編輯；專案地圖只指路，不複製結論。
4. **最小核心，按需要擴充**：所有實驗共享五個基本入口，但完整 scratch 實驗可保留自包含程式與權重結構。
5. **新索引必須能自動產生**：若未來需要機器清單，應由 manifest 掃描產生，不再建立人工同步的平行真相。
6. **D 槽負責工作，H 槽負責歷史**：D 留活動內容、正式內容、精選成果與恢復入口；H 留完整過程與大量 bulk。
7. **先薄化，不搬工作區**：大型區域逐輪收尾；只有明確收益大於路徑風險時才考慮改位置。
8. **每批都可回復**：精確範圍、複製、SHA-256、逐檔核對、恢復入口、移除後復核缺一不可。

## 穩定的 D 槽骨架

這不是要求把現況立即改成完全相同的外觀，而是規定哪些一級入口永久存在，以及新內容應放去哪裡。

```text
D:\GMM_2_Final\
├── README.md                         全專案入口
├── PROJECT_STATE.md                  目前狀態與接手摘要
├── PROJECT_ARCHITECTURE.md           已生效穩定規則
├── ESTIMATOR_POLICY.json             正式模型身分
├── REPO_GOVERNANCE.md                版本與同步規則
│
├── docs\
│   ├── navigation\PROJECT_MAP.md     唯一跨區域人工導航
│   ├── operations\                   操作、容量、封存與特殊情況
│   ├── policy\                       正式政策
│   ├── analysis\                     研究路線與綜合分析
│   ├── evidence\                     小型引用副本
│   ├── history\                      長期歷史敘事
│   └── archive\                      小型歷史文件
│
├── Model\                            共享主模型程式；保持平面結構
├── Tools\                            全專案治理與檢查工具
├── Experiments\                      R 系列實驗；每輪直接掛在此層
├── Analyses\AnalysisLab\                      可重用、跨版本的模型分析；維持版本優先
├── Training_Data\                    共享訓練資料與既有產生程式
├── Traing_Progress\                  歷史與共享主線訓練輸出；名稱永久保留
├── Analyses\Reconstruct_Progress\             舊共享重建表面；新工作不再預設寫入
├── PSF_Fitting\                      獨立 PSF 工作系統；原位治理
├── Thesis_MOSR_Evidence\             論文證據與 LabSystem；原位治理
├── Deliverables\                     新正式交付包入口
├── Acquisitions\                     未來新原始採集的入口；需要時才建立
│
├── 20260702_*                         既有原始／分析入口；固定原位、逐批薄化
├── 20260704_*                         既有原始／分析入口；固定原位、逐批薄化
├── Shared_Sources\Real_Sample_Captures\Step\                              既有不可替代原始資料；固定原位
├── Analyses\Step_analysis_20260623\            既有分析入口；固定原位、逐批薄化
├── Deliverables\Company_Packages\              舊交付相容區；不再新增新包
└── 其他 legacy／archive 根層項目      先索引與判定，不因名稱直接搬動或刪除
```

## 新內容的歸屬規則

| 新內容是什麼 | 放置位置 | 原因 |
|---|---|---|
| 只服務一個 R 輪次的程式、資料、權重或結果 | 該輪 `Experiments/R##_Description` | 脈絡完整，自然一起收尾 |
| 多輪都會使用的正式模型程式 | `Model` | 保持共享主線唯一來源 |
| 多輪共享的大型訓練資料 | `Training_Data` | 避免每輪重複 payload |
| 可重用、跨模型版本的分析方法 | `Analyses/AnalysisLab/r##/...` | 符合既有版本優先設計 |
| 一次性實驗分析 | 所屬實驗的 `scripts/reports/results` | 不把短期工作變成全域模組 |
| 論文專屬圖表、主張與來源 | `Thesis_MOSR_Evidence` | 留在論文證據鏈內 |
| PSF 擬合、校正與驗證 | `PSF_Fitting` | 維持獨立工作系統 |
| 新的不可替代原始採集 | `Acquisitions/YYYYMMDD_system_sample` | 父層已表明角色，不再重複 `ACQ_` 前綴 |
| 可交付給他人的模型包 | `Deliverables/<product>_<version>` | 與研究工作區分開驗證 |
| 完成後的大量 checkpoint、逐張重建與中間輸出 | H 槽對應批次 | D 只留精選與恢復入口 |

如果一份內容無法用這張表判定主人，就先停在原位置並補說明，不建立新的根層資料夾。

## 實驗結構：固定核心與兩種型態

### 所有新實驗的固定核心

```text
Experiments/R##_Description\
├── README.md                         假說、角色、狀態與閱讀順序
├── MANIFEST.md                       來源、權威入口、依賴、容量與保留規則
├── scripts\                          本輪啟動、分析與收尾入口
├── reports\                          唯一可編輯的正式報告
└── results\                          評估與輸出；內部名稱由研究內容決定
```

這五項是結構契約。`results` 不再被強制拆成 `selected/tables/figures/bulk`；不同實驗的輸出語意不同，強制同名只會增加空資料夾。若 `results` 超過三個一級項目或 1 GiB，必須加 `results/README.md` 說明哪些是正式、精選、活動中與封存候選。

### 型態 A：共享主線實驗

適合 R33–R46 這類沿用 `Model`、`Training_Data`、`Traing_Progress` 的實驗。實驗內保存 launcher、報告與結果，主模型程式與共享資料仍在既有權威位置。

可選增加：

```text
├── tests\
└── runs\launcher_logs\active_formal_run.json
```

### 型態 B：自包含 scratch 實驗

適合 R87–R95 這類新架構與完整訓練系統。允許且鼓勵保留：

```text
├── config\                           鎖定設計與執行設定
├── model\                            本輪專屬模型
├── training\                         本輪專屬訓練程式
├── inference\                        本輪唯一推論入口
├── tests\                            架構與行為回歸測試
├── data\                             payload、程序化資料或外部來源指標
├── runs\launcher_logs\              活動標記與執行紀錄
├── weights\                          活動 checkpoint 與收尾後精選權重
└── logs\                             只有無法合理放進 runs 時才另設
```

`data/README` 或 MANIFEST 必須說明 `data` 是實際 payload、程序化產生方式，還是指向共享資料；不得讓一份 20–40 GiB 資料因複製方便而在連續輪次重複出現。

正式訓練開始前，兩種型態都必須有容量登錄與 `active_formal_run.json`。程序消失不等於完成；輸出核對後才進 closeout。

## 資料集結構

既有 `Training_Data` 子目錄不搬動。新共享資料直接使用短而明確的名稱，不增加 `datasets/DS_...` 這一層：

```text
Training_Data\r##_purpose_v##\
├── README.md                         用途、採用狀態、限制與使用者
├── MANIFEST.json                     檔案數、容量、來源、產生方式與校驗
├── recipes\                          產生程式與鎖定設定（需要時）
├── splits\                           train/val/test 清單（需要時）
├── payload\                          實際資料；父層不能再複製一份同內容
└── ARCHIVE_POINTER.md                 payload 封存後才建立
```

如果資料只服務一輪自包含 scratch 實驗，就留在該實驗的 `data`，不再同時複製到 `Training_Data`。如果兩輪以上確實共用，才升成 `Training_Data` 共享資料集。

資料變體優先保存種子、設定、產生程式與差異清單；只有重建成本過高或正式稽核需要時才保存完整衍生 payload。

## AnalysisLab、日期型分析與原始採集

### AnalysisLab 永久維持版本優先

現有 `Analyses/AnalysisLab/r26/{single_image,sequence,performance}` 設計合理，因此不新增 `Analyses/AnalysisLab/projects`，也不把 100MG、20x/5x 或 Step 日期型工作區硬塞進去。

- 可重用、跨版本的方法：進 AnalysisLab。
- 一次性研究：留在所屬實驗。
- 論文專屬分析：留在 Thesis 工作區。

### 既有日期型工作區固定原位

100MG、20x/5x 與 Step 分析已被數千份 manifest、程式與報告記錄。未來處理方式是：

1. 原位置補齊 README、正式結果入口與 archive pointer。
2. 找出不可替代輸入、正式表格、論文引用圖與精選重建。
3. 完整逐張重建與重複候選封存到 H。
4. D 槽保留薄化後的原入口，不再做第二次實體搬家。

### 未來新原始採集

只有未來新採集才進 `Acquisitions/YYYYMMDD_system_sample`。舊 Step、100MG、20x、5x 不追溯搬遷。

```text
Acquisitions\YYYYMMDD_system_sample\
├── README.md                         裝置、樣本、倍率、條件與資料角色
├── MANIFEST.json                     檔案、容量與校驗
├── raw\                              唯讀原始資料
├── calibration\                      同次採集校正資料
└── derivatives\                      小型正式衍生品；大量分析另有主人
```

## 永久保留原位的相容區

### Model

平面結構與 import 相依是既有設計，不重排。交付包中的推論副本仍按真相政策同步。

### Traing_Progress

錯字名稱永久保留。它是舊主線與共享 Model 訓練的相容表面，不再被當成所有新 scratch 實驗的預設輸出位置。新自包含實驗使用自己的 `runs` 與 `weights`。

### Reconstruct_Progress

既有內容固定原位並逐批封存。新實驗重建預設放回該輪 `results`；只有既有共享工具明確需要時才繼續寫入這裡。

### PSF_Fitting

正式入口、vendored BADS、校正、驗證與大量 MATLAB 路徑關係複雜，不強制重排成 `formal/work/validation`。由現有 README 說明角色；暫存與 QA 依生命週期清理。

### Thesis_MOSR_Evidence 與 LabSystem_MOSR

兩者永久留在目前位置。LabSystem 的問題是 435 GiB 歷史累積，不是父層名稱；解法是按 R 輪次薄化與封存，不是搬到新 `Workspaces`。

### Legacy rounds

`Traing_Progress/organized_20260313` 至 `organized_20260316` 只加導覽與恢復資訊，不重構內容。

## Deliverables

目前只有少量交付包，不先建立 `formal/research/retired` 三層。每個新包直接放在 `Deliverables`，並自帶：

- README 與版本／用途。
- 檔案與 SHA-256 清單。
- 可執行範例。
- 真實參考輸出與一致性結果。
- 解壓後 smoke test。

當正式包超過十個，再由 README 或自動產生索引分組；不要預先建立大量空分類。

`_deployment_package` 只保留舊相容包，不再新增。

## H 槽結構

H 槽設計維持簡單且與現況一致：

```text
H:\GMM_2_Final_Archive\
├── experiments\                       主專案已完成實驗
├── lab_system\                        LabSystem 逐輪歷史
├── analyses\                          日期型分析 bulk
├── acquisitions\                      原始採集第二份保存
├── deployments\                       舊交付與可重建 runtime
├── legacy\                            現代 Experiments 以前的批次
├── git_maintenance\                   版本維護快照與隔離
├── manifests\                         封存清單與 SHA-256
├── operation_logs\                    複製、核對、移除與復核紀錄
├── inventory_snapshots\               全專案唯讀清冊
└── quarantine\                        30 天隔離；到期仍不自動刪除
```

新封存批次建議使用：

```text
<collection>\<identity>\YYYYMMDD_full_history\
├── ARCHIVE_RECORD.md
└── payload\                            保留來源相對結構
```

既有批次如果使用 `snapshot` 或直接保存來源結構，不為統一外觀重包一次。中央 manifests 與操作紀錄仍是核對入口。

## 命名與路徑預算

父資料夾已經表達角色時，不在子項目重複 `DS_`、`ACQ_`、`ANALYSIS_` 等前綴。

| 項目 | 建議格式 |
|---|---|
| 實驗 | `R##_Description` |
| 共享資料集 | `r##_purpose_v##` |
| 新原始採集 | `YYYYMMDD_system_sample` |
| run | `r##_short_YYYYMMDD_HHMM` |
| 封存時間點 | `YYYYMMDD_full_history` |

路徑規則：

- 新檔案絕對路徑超過 180 字元時警告，超過 220 字元時阻擋。
- 單一檔名或資料夾名稱目標不超過 64 字元。
- 種子、倍率、權重、老師、資料混合比例與完整描述寫進 manifest，不全部塞進名稱。
- 禁止新增 `final_final`、`new_new`、`backup2`、`copy`、`old2` 這類狀態不明名稱。
- D 槽不得用 `_archive` 或 `backup` 保存另一套完整大型 payload。

## 導航與真相分工

不再新增人工維護的 project/dataset/result catalog。

| 要找的內容 | 入口 |
|---|---|
| 現在做到哪裡 | `PROJECT_STATE.md` |
| 正式模型身分 | `ESTIMATOR_POLICY.json` |
| 穩定規則 | `PROJECT_ARCHITECTURE.md` |
| 實驗清單 | `Experiments/INDEX.md` |
| 實驗正式報告 | 該輪 `reports` |
| 跨區域查找 | `docs/navigation/PROJECT_MAP.md` |
| 大型區塊身分 | `PROJECT_STORAGE_REGISTRY.json` |
| H 槽歷史 | `PROJECT_ARCHIVE_INDEX.md` |
| 全檔案清冊 | H 槽 `inventory_snapshots` |

若日後需要機器可讀總表，只能由這些現有真相與各輪 MANIFEST 自動產生，產物不得成為新的可編輯真相。

## 防止再次失控的守門

### 正式工作開始前

1. 實驗有 README、MANIFEST、scripts、reports、results。
2. MANIFEST 聲明實驗型態、資料來源、預估容量、活動輸出與 closeout 規則。
3. 容量中央登錄已有該輪或該大型區塊。
4. `active_formal_run.json` 會在啟動與續訓時更新。
5. 新輸出預估路徑與容量通過檢查。

`runs/active_run.json` 只作為近期實驗的相容讀取入口，不是新標準。新 launcher 一律寫 `runs/launcher_logs/active_formal_run.json`，並包含目前程序編號、開始時間、預定輪數與輸出位置。

### 執行期間

- 只保護目前活動輸出，不把所有舊輪次永久標成 active。
- 自包含輪次不得複製上一輪大型 payload；以來源 manifest 與 hash-locked reference 重用。
- 活動標記、實際程序與最新日誌三者交叉判定。
- 任何 stale、讀取失敗、失敗／中止或仍宣告 active 卻缺程序證據的標記，都先列為待核對並阻擋大量操作。

### verdict 後七天內

- 選出採用、最後與最多一份必要診斷模型。
- 在 README／MANIFEST 寫明正式結果與負結果。
- `results` 標出 D 保留內容與 H 封存候選。
- 更新 Experiments/INDEX 與容量登錄。
- 一次只執行一個精確封存批次。

### 每週／每月

- 每週檢查新根層項目、未登錄大型區塊、路徑超長與已完成未收尾實驗。
- 每月建立新的唯讀完整清冊，不覆寫舊清冊。
- 檢查 `Experiments` 新目錄是否已進 INDEX 與 storage registry。
- 所有檢查只產生候選清單，不自動刪除。

## 實施順序

### 階段 0：設計與導航

已完成全專案清冊、專案地圖與第二版結構審查。沒有搬動大型資料。

### 階段 1：先停止繼續變亂

- 把兩種實驗型態寫入新實驗指南。
- 補上「結果過大需 README」、「資料是 payload 或 reference」與路徑預算守門。
- 修復目前 12 個結構錯誤與 29 個索引警告，但必須逐輪讀正式證據，不能用空白文件或猜測 verdict。
- 對 R89–R95 與容量登錄、實驗索引的落差做正式收尾。

### 階段 2：近期自包含輪次 closeout

- 逐輪核對 R87–R95；只有正常完成、輸出完整且 verdict 清楚的輪次才進入處理。
- 保留程式、設定、測試、報告、採用模型、最後模型、代表圖與必要重做資料。
- 完整 checkpoint、逐輪監看與可重建驗證 bulk 進 H。
- 任一輪的活動標記、程序、日誌或預定輪數不一致時，該輪繼續保護。

### 階段 3：既有大型歷史逐輪薄化

- LabSystem 依既有 queue 一輪完成才進下一輪。
- 主專案按正式、核准替代、研究、負結果分類，不跨輪混刪。
- 同尺寸候選先算 SHA-256，再查引用與恢復方式。
- 2026-08-24 已完成 R1–R51 可證明安全的第一輪全面薄化：R16–R31、七個主專案已結案輪次、Lab R46/R47 與 61 個散落舊 run 均建立 H 槽完整快照並在 D 精簡前後核對。正式／核准核心與未對應歷史仍原位保護；詳細結果見 `PROJECT_R1_R51_STORAGE_REVIEW_20260824.md`。

### 階段 4：日期型分析原位薄化

- 100MG、20x/5x、Step 各自鎖定原始輸入、正式表格、論文圖與精選重建。
- bulk 保存到 H，D 原位置留薄化入口與恢復說明。
- 不再規劃搬進 AnalysisLab 或改寫數千份路徑。

### 階段 5：獨立維護批次

- `.git` 中斷封裝、測試快取、PSF 編輯暫存與舊交付 runtime 分開處理。
- 每一類都有自己的活動程序檢查與驗收，不和研究封存混成一批。

## 每批封存的完成清單

1. 活動標記、實際程序與最新日誌都確認安全。
2. 精確列出來源、保留內容與預估容量。
3. 建立來源清單與 SHA-256。
4. 複製到全新的 H 槽時間點位置。
5. 逐檔核對檔名、大小與 SHA-256。
6. D 槽保留正式報告、manifest、程式、代表成果與恢復入口。
7. 移除前先做精確預演，不使用廣泛萬用字元。
8. 只移除已核對的大型副本。
9. 移除後再次核對 H 槽。
10. 更新容量登錄、封存索引、操作紀錄與專案狀態。
11. 跑結構、容量工具、正式入口及代表性重做測試。

任何一項失敗，就停在可恢復狀態，不進下一批。

## 明確不做的事

- 不一次移動整個專案。
- 不建立三份新的人工中央 catalog。
- 不把 LabSystem 搬到新 Workspaces。
- 不把既有日期型分析搬進 AnalysisLab。
- 不為整齊重排 PSF、Thesis、Model 或 legacy rounds。
- 不強迫所有實驗使用相同的結果子目錄。
- 不因名稱像 tmp、archive 或 Trash 就直接刪除。
- 不把同尺寸檔案當成已確認重複。
- 不讓 H 槽成為不可替代資料的唯一副本。
