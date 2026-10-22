# 已知缺件、已保存內容與可重做的界線

2026-10-22。本頁只整理目前有明確證據的限制；找不到原件不等於整輪結果遺失，已有後來版本也不能冒充較早原版。

## 22份較早程式／設定版本

依[原內容身分清單](four_rounds/HISTORICAL_SOURCE_AVAILABILITY.json)，22份缺件是 **R94的19版、R95的3版**：合計2版模型定義、17版訓練程式、3版設定。不是22個實驗，也不是R97／R98正式模型遺失。四輪最後模型定義、訓練程式及設計12項都符合當時記錄；完整模型與結果按[四輪入口](four_rounds/README.md)保存。

R95另有兩版早期訓練程式已由原版本內容找回，並已實際從GitHub取回相同，見[已找回原件](four_rounds/R95_EARLY_SOURCES_RECOVERED_VERIFIED.json)。剩下版本影響的是精確回看那些較早預檢、失敗或接續時的程式，不能用正式最後版補造。

| 輪次 | 缺少哪種原件 | 當時內容身分開頭 | 保留它身分的原紀錄範例 |
|---|---|---|---|
| R94 | 模型定義 | `ddf73583052f…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_181537/run_progress.json>) |
| R94 | 訓練程式 | `b47870e2ffc8…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_181537/run_progress.json>) |
| R94 | 設定 | `23ec1123a91e…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_181537/run_progress.json>) |
| R94 | 訓練程式 | `db8580239818…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_183038/run_progress.json>) |
| R94 | 訓練程式 | `e739b9185c9d…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_183244/failure.json>) |
| R94 | 訓練程式 | `f13e4846a107…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_183304/failure.json>) |
| R94 | 訓練程式 | `bb222630e533…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_183328/failure.json>) |
| R94 | 訓練程式 | `0f705254f67a…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_183348/run_progress.json>) |
| R94 | 訓練程式 | `5ff4993737b2…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_183529/run_progress.json>) |
| R94 | 訓練程式 | `fe450221906d…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_184512/run_progress.json>) |
| R94 | 設定 | `a8a2866fee7d…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_184512/run_progress.json>) |
| R94 | 訓練程式 | `56ef073108e4…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_185333/failure.json>) |
| R94 | 訓練程式 | `f437b2ebcbf4…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_185402/run_progress.json>) |
| R94 | 模型定義 | `8f03e949f439…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_190117/run_progress.json>) |
| R94 | 訓練程式 | `88c5e52416a0…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/smoke_R94_scratch_seed940041_20260812_190117/run_progress.json>) |
| R94 | 訓練程式 | `b19127c9571f…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/training_R94_scratch_seed940041_20260812_184607/scratch_initialization_audit.json>) |
| R94 | 訓練程式 | `0509aaa2f661…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/training_R94_scratch_seed940041_20260812_185800/scratch_initialization_audit.json>) |
| R94 | 訓練程式 | `9b3cb78a7f0d…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/training_R94_scratch_seed940041_20260812_191058/scratch_initialization_audit.json>) |
| R94 | 訓練程式 | `2a25d203d059…` | [原紀錄](<../../Experiments/R94_EvidenceConditionalScratch/runs/training_R94_scratch_seed940041_20260812_191420/scratch_initialization_audit.json>) |
| R95 | 訓練程式 | `810f04e36a0e…` | [原紀錄](<../../Experiments/R95_CounterfactualGateRepairScratch/runs/smoke_R95_scratch_seed950041_20260813_002234/run_progress.json>) |
| R95 | 設定 | `7431df7b4669…` | [原紀錄](<../../Experiments/R95_CounterfactualGateRepairScratch/runs/smoke_R95_scratch_seed950041_20260813_002234/run_progress.json>) |
| R95 | 訓練程式 | `d0cb1a2759e5…` | [原紀錄](<../../Experiments/R95_CounterfactualGateRepairScratch/runs/training_R95_scratch_seed950041_20260813_003125/interruptions/continuation_02/continuation_audit.json>) |

完整64字內容身分與全部原紀錄在上方清單。日後若找到候選檔，必須與當時記錄的完整內容相符，再標為找回；只有相似檔名或功能接近不算。

## 早期R13的9項總分公式

2026-03-11 13:18那次原表仍在；它的27個分尺度分數符合後來保存的程式，但9個合成總分不符合後來公式。15:02那次是不同試跑和選中模型，不能替代13:18。原9個總分照存，不改用擬合出的係數宣稱找回原公式。

[原方法與固定模型讀法](legacy_multiscale/README.md)及[原重算程式](../../Tools/replay_legacy_multiscale_selection.py)保留實際通過的207個分數與5次原選擇，也明列9項未恢復公式。這個證據不是全部訓練重新執行。

## R36及原先未寫出的量

[歷史查找紀錄](lineage/R36_HISTORY_CHECK.json)檢查了當時可到達的243個提交敘述及R36路徑，未找到足以獨立指定的一輪。可能是未使用編號或未留在那些歷史，現階段只列未辨認，不宣稱一定做過或從沒做過。

另有9個早期ANN量原表沒有寫出，不能拿其他欄位補成當時原觀察。部分舊訓練表欄名數量與數值數量不同，依[原寫入程式讀法](project_completion/TRAINING_LOG_LAYOUTS.md)判讀，不能一律套後來V42的欄位。

## 已查到哪裡

- 原盤點與目前程式、設定、正式文件的保存對照，以及80個本機有名分支的遠端歷史，見[沿革入口](lineage/README.md)。分支都在不等於每份未提交的舊程式都在。
- [既有版本內容搜尋](project_completion/BOUNDED_GIT_SOURCE_SEARCH.json)已讀154,176份不大於512,000 bytes的版本內容，找回上述兩版R95原件，只找到較晚R13公式；本次沒有再重複讀完整大庫。
- 本次另讀VS Code／Cursor共226份檔案歷史目錄紀錄，沒有符合上述缺件來源的條目，沒有找到新原件。[本次限定查找紀錄](lineage/GAP_SEARCH_20261022.json)保留範圍及結果。

這些是限定範圍的搜尋結果，不是所有電腦和所有備份都不存在的證明。新的原件若出現，可依原內容身分補回；目前不據此捏造一個已完成的歷史版本。

## 不屬於漏傳的內容

可再生的整套訓練影像、逐張重建、全部中途模型及暫存不再整批補傳。保留生成程式、設定與必要來源；不可替代的相機／量測／人工來源另存。[生成方法](GENERATION_GUIDE.md)及[附件界線](ASSET_GUIDE.md)列明何時仍需固定來源。

外部GMF、MATLAB、舊位置調整、來源答案依賴及官方後端失敗照原報告保留。現在能讀到完整原表、取回固定模型或重算某些結果，不代表全部歷史GPU訓練都重新跑過，也不代表重拍穩定即絕對準確。
