# 精選保存範圍與歷次紀錄

本區是保存工作的說明與收據，不是新的全量上傳待辦。第一次讀研究請回[方法與結果入口](../README.md)；需要資料或模型時，用[按用途選附件](../ASSET_GUIDE.md)。

## 現在的狀態

| 日期／範圍 | 事實與入口 |
|---|---|
| 2026-10-21精選固定保存 | [交付範圍](SELECTIVE_DELIVERY.md)及[原固定版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-curated-20261021)保留當次程式、來源、結果、精選圖／模型與實際收據 |
| 2026-10-22舊草稿處理 | [六份舊草稿的取捨](curated/draft_cleanup_20261022/README.md)：先保存約237MB精選原件與171份小型來源，再撤下六份過量草稿；目前沒有待發布的舊全量草稿 |
| 2026-10-22沿革補查 | [R1至R153、Lab及歷史分支](../lineage/README.md)：補原報告、早期profile／日誌、資料與失敗接續。不能用177個入口數替代完整歷史重現 |
| 2026-10-22文件整理 | [專案地圖](../../navigation/PROJECT_MAP.md)與各區README分清目前研究、來源、交付及歷史；[缺件](../KNOWN_GAPS.md)持續如實保留 |

舊收據寫的`draft`、傳輸中或待綁定，只是**該收據當時的範圍與狀態**。先看上表和後續收據，不以舊狀態重新啟動全量流程。舊數值、模型、來源身分及收據日期沒有改寫。

## 找保存內容

| 要查什麼 | 入口 |
|---|---|
| 每輪保留與省略原則 | [目前精選範圍](SELECTIVE_DELIVERY.md)、[較早逐輪首版](curated/ROUND_CURATED_PLAN.md) |
| 精選模型、圖、來源身分及各輪索引 | [固定精選索引](curated/SELECTIVE_RESEARCH_INDEX.json.gz)；內容屬2026-10-21原範圍，不當成今日全目錄清單 |
| 完整小型原表與不利結果 | [失敗脈絡](curated/FAILURE_LINEAGE_READING.md)、[早期原重建精選](curated/EARLY_RECON_SELECTION.md) |
| 舊模型及訓練表如何讀 | [模型歷程](MODEL_HISTORY.md)、[各版寫入欄位](TRAINING_LOG_LAYOUTS.md) |
| 論文、修訂、原文件與編輯歷史 | [文件來源](CONTEXT_RECORDS.md)、[編輯歷史](EDITOR_HISTORY.md)、[草稿精選交付](curated/draft_cleanup_20261022/README.md) |
| 共用位置和H封存 | [原位置引用](REGISTERED_DIRECTORY_REFERENCES.json)、[H資料當次檢查](REGISTERED_H_DELTA_VERIFIED.json)、[封存總入口](../../operations/PROJECT_ARCHIVE_INDEX.md) |
| 既有固定包與工具實測 | [原小型交付紀錄](CONVENIENCE_DELIVERIES_VERIFIED.json)、各研究線自己的取回／重算收據 |

## 收據和原檔的讀法

`*_VERIFIED.json`保留當次核對內容、程式版本與執行範圍，`*.json.gz`是壓縮的原檔／用途清單。它們不是同一份必須重新執行的排程。圖冊和原文件只協助閱讀，正式科學判決回到原實驗報告。

`MODEL_BATCHES_SERVER_VERIFIED.json`等全量探索時的收據，保留當時下載檢查的事實；相關過量草稿已依後續取捨撤回。`FROZEN_DRAFT_DISPOSITION_CANDIDATES.json`是**處理前候選**，不是仍存在草稿的聲明。[較早本頁完整版本](https://github.com/rio10255254/GMM_2_Final/blob/1b1cbdf3804df53f0e3c853b8dcf57e7471c6520/docs/reproducibility/project_completion/README.md)可在固定歷史查閱。

## 私人工具備份不屬於實驗保存

與研究無關的舊登入／工具備份排除在GitHub研究內容外，原件留本機；[排除紀錄](EXCLUDED_PRIVATE_TOOL_BACKUPS.json)及[當次撤回收據](PRIVATE_BACKUP_DRAFT_WITHDRAWAL_VERIFIED.json)保留原因和處理範圍，不刊出登入內容。

## 本機整理另按當時授權

[D槽已清副本與取回](../../operations/D_DRIVE_FULL_CLEANUP_20261022.md)有獨立範圍；本次GitHub文件整理沒有再刪D/H研究原件。原拍、正式模型、論文及活動訓練資料維持保護，H至少保留1TiB。不能以一份舊保存收據直接推定另一個目錄可刪。
