# 整理計畫與搬動帳本（初稿，2026-10-25）

這是提案，還沒有執行任何搬動。每一項都要使用者確認後才做，做完的項目會在這裡更新狀態。

## 目標

讓 GitHub 成為這個研究完整、看得懂的紀錄，服務三種人：

1. **參觀者**：不下載任何東西，就能看懂每一輪在問什麼、怎麼做、結果如何、限制在哪。
2. **想拿資料的人**：知道原拍、模型、量測在哪裡，能只拿自己需要的那一份。
3. **想復現的人**：程式、設定、種子、資料來源都找得到。

前提是**任何當時的脈絡都不能遺失**：原始報告、設定、改動前快照、失敗紀錄一律保留原樣。

## 一、調查後確定的限制

### 1. 大部分頂層資料夾不能搬

檔案樹看起來亂，主因是根目錄有 26 個資料夾、角色混雜。但逐一查過引用後，大部分資料夾都被**當時的實驗設定與程式實際讀取**。搬動就得改寫那些設定，等於改寫「當時實驗怎麼跑」的紀錄；不改的話，就沒人能照原設定重跑。

| 資料夾 | 被誰實際讀取 | 判斷 |
|---|---|---|
| `Experiments/`、`Model/`、`PSF_Fitting/`、`Training_Data/`、`Traing_Progress/`、`Thesis_MOSR_Evidence/`、`Shared_Sources/` | 上千個程式、設定、報告 | 不動 |
| `20260702_100MG_displacement_analysis/`、`20260704_20x_5x_analysis/` | R63～R140 約 30 輪的設定與腳本把它們當實拍序列輸入；論文證據區的審核腳本與測試 | 不動 |
| `Step_analysis_20260623/` | 論文證據區的製圖腳本、R139／R140 的儲存登記 | 不動 |
| `AnalysisLab/` | R33～R46 的守門腳本與論文消融分析直接匯入它的程式 | 不動 |
| `_deployment_package/` | 874 處絕對路徑、38 個實驗程式 | 不動 |
| `Reconstruct_Progress/` | `ESTIMATOR_POLICY.json`、`Model/`、多輪設定 | 不動 |
| `_build153/` | R153 的重試腳本用 `ROOT.parents[1]/'_build153'` 讀取 | 不動 |
| `Deliverables/` | 189 個 markdown 連結，其中 11 份是原始報告 | 不動 |

所以檔案樹的整理重點，放在**導覽層**和**文件層**，不放在搬動研究資料夾。

### 2. 雲端資料其實大多在，但很難單獨拿

10 月的保存工作已經把大量檔案放進 GitHub Release：合併所有 Release 的內容清單後，一共登記了 394,713 個路徑、230,601 種不同內容，而且附有 SHA-256。

問題在打包方式：檔案是按大小和去重複切成分卷的，不是按輪次分。所以每一輪的檔案都散在好幾個分卷裡：

| 想拿的東西 | 實際大小 | 用 `--prefix` 取回要下載 |
|---|---:|---:|
| R152 的 `results/` | 約 430 MB | 14 個分卷，約 20 GB |
| COMBO 訓練資料夾（權重與紀錄） | 約 172 MB | 6 個分卷，約 7.6 GB |
| R38v2SeqFixed 的數值結果 | 約 8 MB | 4 個分卷，約 4.2 GB |
| R46 的權重與結果 | 約 51 MB | 約 5.8 GB |

資料是保住了，但「未來的人只拿某一輪的資料做實驗」現在很難做到。

### 3. 原始報告引用的檔案，GitHub 上點不開

全 repo 的 markdown 共有 10,122 個斷掉的相對連結：

- **9,869 個**是改動前快照造成的（`project_context_before/`、`governance_before_closeout/`、9 月設計回顧、`Historical_Archive` 的完整歷史副本）。原檔被複製到別處，相對連結自然指不到；快照照規則保持原樣，不修。
- **222 個目標**是原電腦上有、GitHub 程式樹沒有，展開後共 838 個檔案：
  - 317 個已經以相同內容存在 Release 裡，只是 GitHub 上點不開。
  - 520 個不在任何 Release，見下一節。

### 4. 確定只存在原電腦的重要檔案（目前發現的部分）

| 檔案 | 大小 | 為什麼重要 |
|---|---:|---|
| `Experiments/R152_R148v2_SafeAdaptivePSF/runs/formal_8192/checkpoints/deployed_step08192.pth` | 7.1 MB | 論文模型 R152 實拍驗證用的原始保存點（SHA-256 開頭 `17bf7c63`）。雲端有張量完全相同的重新封裝版，但原檔本身不在任何 Release。**2026-10-26 已補上：** Release [`research-localonly-models-20261026`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-localonly-models-20261026)，取回核對通過 |
| `Experiments/R45_FamilyBoundaryAdapter/results/checkpoints/r45_oracle_adapter_large_mixed{,_s04,_s08,_s12}.pth` | 共約 0.2 MB | R45 的四個校正模組權重（同資料夾的 `_latest` 與兩個短測權重已在 Release）。**2026-10-26 已補上：** 同上一列的 Release |
| `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/{external,shape,micro}_recon/a025/` | 約 700 MB | 核准替代 a025 送外部 GMF 的重建影像與形狀／顯微重建。**2026-10-26 查核：** 依[保存原則](../reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)屬整批模型輸出，不上傳；重算所需的 a025 權重與 ONNX、外部 GMF 分數都在雲端。輸入的 `Cropped_Output` 裁切版也不在雲端，但已逐張證實是雲端原拍的固定區塊，裁切參數補記在[同一份文件](../reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)，所有用公司圓環序列的輪次都適用 |
| `Experiments/R136_PIRepeatability/output/*.zip`（10 個閱讀包與圖表包） | 約 489 MB | R136 原報告引用的結果包。**2026-10-26 逐檔比對：** 包內 1,307 個檔有 1,300 個以相同內容在 git 或 Release；只存在包裡的 7 個說明與核對檔（兩包的「00_先讀我」與打包清單、Raw／R128 完整比較包的 README、打包清單與核對紀錄，共約 65 KB）已放進 git 的 `output/<包名>/`。ZIP 本身不另存 |
| `Experiments/R153_MeanExternalBenchmark/reports/*.zip`（5 個交接包） | 約 8 MB | 論文交接包。**2026-10-26 逐檔比對：** 包內 153 個檔全部以相同內容在 git 或 Release，ZIP 本身不另存 |
| `Deliverables/R152_Standalone_20261004.zip`、`R152_Standalone_ImageFiles_20261004.zip` | 約 760 MB | 打包好的 R152 獨立包；程式已在 git、模型已在 Release。**2026-10-26 逐檔比對：** 兩包共 10,051 個檔全部以相同內容在 git 或 Release，ZIP 本身不另存 |

這只是「原始報告有連結到」與寫閱讀卡時查到的部分。2026-10-26 已用 `Tools/cloud_locator.py` 掃完整個專案（約 315 萬個檔）並展開所有沒有清單的 Release 附件後重驗：上表各列仍成立；原本列在表內的 COMBO 與 a025 兩個 ONNX 其實在雲端（見下一段），已移出本表。全專案只在本機的檔約 208 萬個、1,019 GB，絕大多數是 BMP 原拍與重建、NPZ／NPY 陣列與中間保存點；2 MB 以下的文字結果表只有約 3,400 個、共 26 MB，集中在 `PSF_Fitting`、R129、R136、`Thesis_MOSR_Evidence/Data_Reports`。

這次掃描只涵蓋 `D:\GMM_2_Final`。專案外還有被實驗直接讀取的資料夾，例如 `D:\NTU_ImageDataset\`（公司圓環原拍、`Cropped_Output` 裁切版與 1 月的早期重建，舊紀錄裡也寫成 `C:\Users\Rio\Downloads\NTU_ImageDataset\`）。它的原拍已在雲端、裁切版可由原拍重做（見[裁切參數](../reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)），但日後清理本機時要另外逐項看，不能套用專案內的掃描結果。

**寫閱讀卡時發現的另一類缺口：** 有些輪次的結果檔在 Release 裡，但不在 GitHub 程式樹（有些是 2026-10 從主版本移出、只留在 git 歷史），所以報告與閱讀卡提到的數字在 GitHub 上點不到出處。目前查到的有：R148v2 的 12 模型比較表與最終稽核（R148v2 也沒有寫最終結果報告）、R43 的分數表、R44 的總表與分族診斷、R45 的縮放掃描與 R45B／R45C 逐塊表。這些多半是小型 CSV／JSON，適合直接補回 git（見下方 E2）。寫第六、七階段閱讀卡時又找到幾批，**原本以為只在原電腦上，2026-10-25 用 cloud_locator 逐檔查過，其實都在 Release `research-results-models-20261016` 的壓縮包裡**，只是不在程式樹上，讀者要下載 1～4 GB 的附件才拿得到一個幾 KB 的檔：R102 的停止與塌縮診斷（`reports/*.json`，五個共約 31 KB）、R108A／R108C～R108G 的結果摘要與表格、R117 的訓練完成稽核與因果決策、R120 的 `results/`（約 0.5 MB；MANIFEST 指向的 `reports/R120_RESULTS.md` 從沒寫出來）、R121 的決策與 SEM 量測表、R122 的 V42 來源追查逐筆表（約 3.6 MB，論文相關）、R123 的真實來源清單與重算表；另外 R61_STEP 的三份清單、R75v2／R79／R81／R88～R91／R99 的正式權重、LabSystem Modern_Restoration 的兩個對照模型權重也是同一類。這些閱讀卡已在 2026-10-25 改正說法（先前十七處寫成「只在原電腦上」）。小型表格適合直接補回 git（E2）；權重留在 Release，但 E1 重新打包時應讓單一輪次能單獨下載。

**還有一類是「在雲端，但不在讀者會找的位置」。** 例如 R79 的交付模型 `Deliverables/MOSR_ONNX/model.onnx`（15.4 MB）在交付包的路徑上沒有上傳，同內容的檔案卻在 `research-fixed-models-006.zip` 裡、掛在 R84 結案時解壓驗證的副本路徑下。檔案沒丟，但只看交付包的人會以為缺件。**COMBO 與 a025 交給公司的兩個 ONNX**（`_deployment_package/GeoEdge_COMBO_ONNX_Company_Package_20260424/model/geoedge_combo_body.onnx`、`_deployment_package/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/model/geoedge_r39r40_a025_body.onnx`，各約 16 MB）也是同一類：內容在 Release `research-history-curated-20261022` 的 `selected-history-and-deployments.zip` 裡（`deployment_graphs/COMBO_company_body/model.onnx`、`deployment_graphs/R39R40_a025_company_body/model.onnx`）。那個壓縮包沒有清單，2026-10-26 用 `cloud_locator.py build --with-zips` 展開後才查到。`cloud_locator.py scan` 的 `release-other-path` 狀態就是在找這一類；E3 補件時，這種小而重要的交付檔適合直接放回原位置。

**寫閱讀卡時發現的跨輪閱讀陷阱：** 7 月的位移稽核工具把候選欄固定命名為「V42」，後來 Base U-Net、R63 等重用它時，報告寫的「V42」其實是各自的候選（已在時間線開頭加註）；R64 換量法重算後 R63 的消融結論改變；R80、R81 的轉折點量法下 50× CD 原圖比所有模型都好。這些都寫進了對應的閱讀卡，引用數字時要連量法一起說。

## 二、建議的整理內容

### A. 導覽層（不搬任何檔案）

1. **研究時間線** `docs/research/TIMELINE.md`：R1～R153 加 LabSystem，八階段，每輪一列寫「做了什麼 → 結果」。**樣板已完成。**
2. **每輪閱讀卡**：把各輪的 `FILE_GUIDE.md` 改寫成閱讀卡（在研究裡的位置、問什麼、怎麼做、結果、限制、資料怎麼拿、原始報告、檔案分工），原始 `README.md` 不動。**2026-10-26 全部完成**：主專案 R26NewPSFCheck、R32～R153、LabSystem 各輪，以及 `Traing_Progress/` 的 R1～R32 早期批次，倉庫裡已沒有舊格式的 FILE_GUIDE。早期批次的卡片較精簡，數字照原報告寫並註明出處。寫卡過程中發現並改正的錯誤（R18／R22 的外部比較結論、十七處「只在原電腦上」的誤寫、COMBO 與 a025 ONNX 的位置、SEM 九顆方向的更正）都已同步到時間線與本計畫。
3. **根目錄 README 的資料夾地圖**：既然大部分資料夾不能搬，就在首頁把 26 個資料夾分成「研究本體／實拍分析／交付／工具與文件／封存」幾組，每個寫一句角色和「日常需不需要打開」。

### B. 文件層（搬動 `docs/` 內部，引用以腳本改寫並驗證）

`docs/` 裡大部分是導覽與紀錄，比較能動。建議把 `docs/reproducibility/`（877 個檔案）分開：

| 新位置 | 內容 |
|---|---|
| `docs/research/` | 時間線、八階段敘事（`EXPERIMENTS.md`）、各階段路線（`routes/`）、沿革（`lineage/` 的閱讀頁） |
| `docs/data_access/` | 資料與模型怎麼拿：`ASSET_GUIDE`、`MODEL_GUIDE`、`GENERATION_GUIDE`、`GETTING_STARTED`、`KNOWN_GAPS` |
| `docs/preservation_records/` | 10 月保存工作的收據：`project_completion/`、`round_source_*`、`priority_sources_*`、`verification/`、`remaining_audit_*`、各 `*_RECEIPT_*.json`，以及原本 177 張閱讀卡裡的保存紀錄 |

要一起處理的：177 個 `FILE_GUIDE.md` 指向舊卡片的連結、`Tools/build_research_recovery.py`、`build_project_restore_index.py`、`project_reproducibility_audit.py` 讀取的固定路徑（如 `docs/reproducibility/experiment_index.json`），以及 validator 與控制中心的檢查。收據 json 裡登記的舊路徑屬於歷史紀錄，不改寫，改由帳本對照。

### C. 收掉低耦合的封存區

| 舊位置 | 新位置 | 要一起改的 | 風險 |
|---|---|---|---|
| `trial_README.md` | `archive/trial_README.md` | 1 份導覽文件 | 低 |
| `Project_Archive/` | `archive/Project_Archive/` | 導覽文件、`.gitignore` | 低 |
| `Trash_Archive/` | `archive/Trash_Archive/` | 導覽文件、`.gitignore` | 低 |
| `_MOSR_Project_Archive_20260624/` | `archive/_MOSR_Project_Archive_20260624/` | 導覽文件 | 低 |
| `_portable_env_sim_20260318/` | `archive/_portable_env_sim_20260318/` | `.gitignore`、`Tools/research_recovery.py` 的排除清單 | 中，要實跑工具 |
| `Validations/` | `Deliverables/Validations/` | 根 README、2 個 R61 交付工具 | 中，要實跑工具 |
| `Historical_Archive/` | `archive/Historical_Archive/` | 6 個還原／索引工具 | 中，工具用路徑組出邏輯位置，要改並重新驗證 |

最底層的資料夾名稱一律不改，只改上層位置。10 月收據 json 裡的舊路徑不改寫，由本帳本對照。根目錄只會少 4～7 個項目，效果有限，所以這一項不急。

### D. 程式快照合併（需要使用者點頭）

`20260702_100MG_displacement_analysis/`、`20260704_20x_5x_analysis/`、`Reconstruct_Progress/`、`Step_analysis_20260623/` 等處，共有 364 個 `_r61_real_sample_runtime_<時間>/` 資料夾，每個只有一支推論程式快照，但實際只有 **2 種內容**（230 份與 134 份）。

建議改成「2 份程式 + 一張清單」，清單寫明每個舊位置、時間與對應版本。檔案仍在 git 歷史裡。要先確認沒有設定或報告用這些路徑實際讀取程式；這是唯一會讓檔案數變少的動作，所以需要使用者明確同意。

### E. 資料層（Release 重新打包與補件）

1. **按輪次重新打包：** 為常用的輪次建立「每輪一個資料包」的 Release 附件（例如 `R152-results.zip`、`COMBO-model.zip`），讓讀者只下載需要的那一份。原本的分卷保持不動，新包是另一種取用方式；每個新包附 SHA-256，並與原分卷內容核對相同。
2. **小型結果表直接放進 git：** 原始報告引用、又只有幾 MB 的 csv／json（例如 R120～R153 約 35 MB 的比較表、完成標記），直接提交到原位置，讓 GitHub 上的報告連結點得開。
3. **補上只存在原電腦的檔案：** 先處理第一節第 4 點的清單，再做整台電腦的完整盤點。
4. **建立「這個檔案在雲端哪裡」的查詢：** 把所有 Release 清單合併成一份索引並放進 repo，加一支小工具：輸入任何舊路徑，回答它在 git、在哪個 Release 附件，或只在原電腦。這份索引也是之後安全清理本機的依據：只有確認雲端有逐位元組相同的副本，才能刪除本機那份。

## 三、建議順序

每一步一個 PR，做完跑 `validate_project_structure.py`、連結檢查與相關工具，再進下一步。

1. 導覽層：時間線、三張樣板卡（已完成，待合併）。
2. 其餘閱讀卡，分階段分批寫。（2026-10-26 完成）
3. 雲端查詢索引與小工具（E4），它是 E1～E3 與本機清理的基礎。（`Tools/cloud_locator.py` 已可用；2026-10-26 已展開所有沒有清單的附件並掃完整個專案，見第 4 節）
4. 小型結果表補進 git（E2）、補上只存在原電腦的重要檔案（E3）。
5. 按輪次重新打包常用資料（E1）。（2026-10-26 先做模型：[模型指南](../reproducibility/MODEL_GUIDE.md)表內 16 個精選固定模型，各成一個小包放在 Release [`research-models-by-round-20261026`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-models-by-round-20261026)，取回核對通過；結果表多半已在 git 上，暫不另做結果包）
6. 文件層拆分（B）。
7. 封存區（C）、程式快照合併（D），視需要再做。
8. 本機整台盤點與清理。

## 搬動帳本

| 日期 | 舊路徑 | 新路徑 | 一起修改的檔案 | 驗證 |
|---|---|---|---|---|
| （尚未執行任何搬動） | | | | |
