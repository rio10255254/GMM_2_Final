# 專案地圖

Last updated: 2026-10-21

這是整個專案唯一的跨區域人工導航。它只回答「先去哪裡找」與「新內容歸誰」，不複製研究結論，也不取代正式狀態、模型政策、實驗索引或各輪報告。

目前的實體骨架維持穩定。既有大型工作區不為了外觀搬家；未來靠明確歸屬、原位薄化與 H 槽封存，讓 D 槽逐步變得容易查找。

## 我現在要找什麼？

| 需求 | 第一個入口 | 接著看 |
|---|---|---|
| 現在做到哪裡、下一個決策是什麼 | `PROJECT_STATE.md` 的 Quick Handoff | 相關實驗的正式報告 |
| 哪個模型是正式版本 | `ESTIMATOR_POLICY.json` | `PROJECT_STATE.md` 與模型所屬實驗報告 |
| 已生效的穩定規則 | `PROJECT_ARCHITECTURE.md` | `docs/operations/SOURCE_OF_TRUTH_POLICY.md` |
| 某一輪實驗的結論 | `Experiments/INDEX.md` | 該輪 `reports` |
| 不靠舊磁碟從GitHub理解及取回研究 | [研究保存入口](../reproducibility/README.md) | [全專案實際內容核對](../reproducibility/project_completion/README.md)、逐輪方法及各版本附件 |
| 不下載完整訓練資料，先找生產方法 | [原生成程式與必要來源](../reproducibility/GENERATION_GUIDE.md) | R92／R93共用基礎、原修正及在線觀測分清；原資料產物不因可生成而重複上傳 |
| 文獻依據與研究設計理由 | [文獻與原方法來源](../reproducibility/LITERATURE_GUIDE.md)，再到所屬輪次原文獻整理與設計報告 | 文獻原方法與本專案設計推論分開；原文連結保留，沒有本機全文的文獻不冒稱已收錄全文 |
| 各輪程式、完整數據與失敗紀錄 | [逐輪問題、方法及來源](../reproducibility/EXPERIMENTS.md) | 先讀正式報告，再找該輪程式、完整數表與保存附件；不只留挑選過的好結果 |
| 從R1到R153、LabSystem及歷史分支找前後關係 | [研究沿革與逐號對照](../reproducibility/lineage/README.md) | 分清同號不同系統、資料stage、V版本及未能綁回的編號；不以分組或檔案數代替完整脈絡 |
| 原始相機照片、SEM與必要共用輸入 | [來源與影像保存判斷](../reproducibility/SOURCE_AND_IMAGE_DECISIONS.md) | 原拍與模型重建分開；多輪共用的原件保留一次，所有需要的原位置仍可對應 |
| 固定模型、初始化與中途歷程 | [模型身分及歷程](../reproducibility/project_completion/MODEL_HISTORY.md) | 原輪次、選模與未採用原因一起保存；名稱相似不代表相同模型 |
| 重要比較圖、失敗影像與選圖理由 | [共用訓練圖冊](../reproducibility/project_completion/GALLERY.md)、[R93圖冊](../reproducibility/r93_shared/GALLERY.md)、[R94／95／97／98圖冊](../reproducibility/four_rounds/GALLERY.md) | 原圖與完整影像附件並存，代表圖只用來幫助閱讀，不取代完整數據 |
| 原有論文文件、草稿及編輯歷史 | [文件與必要原始紀錄](../reproducibility/project_completion/CONTEXT_RECORDS.md)、[較早編輯歷史](../reproducibility/project_completion/EDITOR_HISTORY.md) | 各版按原日期和身分保留；目前論文結論仍回到最新R153交接 |
| 如何建立新實驗 | `docs/operations/STARTING_NEW_EXPERIMENT.md` | 未來結構與容量藍圖 |
| 論文目前採用的模型、主張與圖表 | `PROJECT_STATE.md` 的最新論文交接 | R153完整交接與原始實驗報告；舊README／HANDOFF只按日期作歷史閱讀 |
| LabSystem 的研究歷史 | `Thesis_MOSR_Evidence/LabSystem_MOSR/README.md` | 該區的實驗與正式報告 |
| PSF 擬合與正式入口 | `PSF_Fitting/README.md` | Whole-FOV 流程與驗證說明 |
| 大型區塊能不能動 | `docs/operations/PROJECT_STORAGE_REGISTRY.json` | 容量政策、活動標記與生命週期計畫 |
| 已移到 H 槽的完整歷史 | `docs/operations/PROJECT_ARCHIVE_INDEX.md` | D 槽恢復入口與 H 槽清單 |
| 全專案哪裡最大、某檔案在哪 | 2026-08-10 完整清冊 | H 槽的 `inventory_snapshots/20260810_full_project` |
| 未來新增內容該放哪裡 | `docs/operations/PROJECT_FUTURE_STRUCTURE_PLAN.md` | 本頁的歸屬表 |

## 新內容先判定主人

| 新內容 | 唯一主人 | 放置原則 |
|---|---|---|
| 只服務一輪的程式、資料、權重、紀錄與結果 | 該輪實驗 | 全部留在該輪，完成後一起收尾 |
| 多輪共用的正式模型程式 | `Model` | 維持主線唯一來源，不搬成新套件樹 |
| 多輪共用的大型訓練資料 | `Training_Data` | 只保存一份 payload，其他輪用來源與核對值引用 |
| 可重用且跨模型版本的分析方法 | `AnalysisLab` | 沿用既有「版本優先」結構 |
| 一次性分析 | 所屬實驗 | 不把短期腳本變成全域工具 |
| 論文專屬證據與圖表 | `Thesis_MOSR_Evidence` | 留在論文證據鏈內 |
| PSF 擬合、校正與驗證 | `PSF_Fitting` | 維持獨立工作系統 |
| 未來新原始採集 | `Acquisitions` | 只管新資料；舊資料不追溯搬遷 |
| 可交付給他人的模型包 | `Deliverables` | 與研究區分開驗證 |
| 已完成的大量 checkpoint、逐張重建與中間輸出 | H 槽對應批次 | D 留正式內容、代表成果與恢復入口 |

如果無法判定主人，先留在原位置並補 README，不新增根層資料夾。

## 現在的實體工作區

| 區域 | 目前角色 | 穩定規則 |
|---|---|---|
| `Model` | 共享主模型、訓練與推論程式 | 平面結構是既有設計，不重排 |
| `Experiments` | 主專案 R 系列實驗與正式報告 | R33+ 的 `reports` 是唯一可編輯報告來源 |
| `Training_Data` | 多輪共享的訓練資料與產生程式 | 既有子目錄不搬；新共享資料避免重複 payload |
| `Traing_Progress` | 舊主線與共享模型的訓練歷史 | 拼字是相容路徑；不可更名 |
| `Reconstruct_Progress` | 舊共享重建表面 | 原位薄化；新實驗預設把結果留在自己的 `results` |
| `AnalysisLab` | 可重用、跨版本的模型分析 | 保留版本優先；不收納所有日期型工作區 |
| `PSF_Fitting` | PSF 擬合、校正與驗證 | 原位治理，不為外觀重排 |
| `Thesis_MOSR_Evidence` | 論文證據、圖表與 LabSystem | LabSystem 永久留在其下，逐輪薄化而非整區搬家 |
| `Step` 與既有日期型原始影像 | 不可替代採集資料 | 固定原位；新採集才使用 `Acquisitions` |
| 100MG、20x/5x、Step 日期型分析 | 既有大型分析工作區 | 固定原位，保留正式入口並封存 bulk |
| `_deployment_package` | 舊交付相容區 | 不再新增新包 |
| `Deliverables` | 新正式交付包 | 每包自帶說明、核對清單、範例與驗證 |
| `.git` | 完整版本歷史 | 使用獨立維護流程，不與研究資料整理混做 |

## 找實驗的最短路徑

1. 從 `Experiments/INDEX.md` 找輪次與狀態。
2. 進該輪 `reports` 讀正式結論，不先翻大量結果。
3. 需要重做時，再讀該輪 README、MANIFEST 與 `scripts`。
4. 自包含實驗再依序看 `config`、`model`、`training`、`inference`、`data`、`runs` 與 `weights`。
5. 大型歷史若已離開 D 槽，從該輪恢復入口連到 H 槽。

新實驗有兩種合理型態：沿用共享主線的精簡型，以及自帶模型、訓練、推論與測試的完整型。兩者都必須有 README、MANIFEST、`scripts`、`reports`、`results`；不要為了長得一致而拆散完整型實驗。

不要因為某個模型檔名稱像 `best` 或 `latest` 就判定它是正式版本；模型身分必須回到 `ESTIMATOR_POLICY.json`。

## 找論文證據的最短路徑

1. 從論文工作區總覽與 handoff 確認目前主張。
2. 正式採用圖表從 `Final_Data_Figures` 的區域說明進入。
3. 圖表若引用某個 R 輪次，回到該輪正式報告與來源資料。
4. `docs/evidence` 是穩定引用副本；若內容不同，以實驗 `reports` 為準。

## 找歷史大型資料的最短路徑

1. 從 `docs/operations/PROJECT_ARCHIVE_INDEX.md` 找封存批次。
2. 讀 D 槽留下的恢復入口，確認原始角色與保留邊界。
3. 在 H 槽找到完整快照與含 SHA-256 的清單。
4. 恢復時先複製回 D 並逐檔核對，不直接把 H 槽當工作區。

## 使用完整清冊

H 槽的 2026-08-10 清冊資料夾內：

- `summary.json`：全專案總量與掃描範圍。
- `tree_depth3.csv`：根層到第三層容量與檔案數。
- `largest_files.csv`：前 2,000 個最大檔案。
- `large_same_size_candidates.csv`：同尺寸大型候選；只能安排後續雜湊核對。
- `documents.csv.gz`：文件與表格索引，含 Markdown 標題提示。
- `inventory_entries.csv.gz`：完整檔案與資料夾位置清冊。
- `artifact_checksums_sha256.csv`：清冊成果自身的核對值。

盤點解讀與 2026-08-13 設計複核見 `docs/operations/PROJECT_STRUCTURE_INVENTORY_20260810.md`。

## 目前不要做的事

- 不把 `Traing_Progress` 改成正確拼字。
- 不自行搬動 `Model` 主程式。
- 不重構 `organized_20260313` 至 `organized_20260316` 的內部歷史。
- 不把 LabSystem 搬出論文工作區。
- 不把日期型分析搬進 AnalysisLab。
- 不把同尺寸檔案直接當成重複檔。
- 不建立更多需要人工同步的中央清單。
- 不在活動標記、實際程序與輸出完成狀態不一致時搬動大型資料。
- 不把 H 槽唯一副本當作不可替代資料的完整備份。
