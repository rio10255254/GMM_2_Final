# 研究方法、原結果與必要來源

本次精選保存讓讀者能理解當時研究、查看完整原結果，並找回原生產方法與必要來源。大型訓練影像、逐張重建和其他可再生產物，不要求整套下載或上傳。

| 目的 | 先看 |
|---|---|
| 每一輪的研究問題、方法、失敗與限制 | [逐輪入口](EXPERIMENTS.md) |
| 從程式重新生產資料 | [原生成器、設定與真正基礎來源](GENERATION_GUIDE.md) |
| 文獻、設計推論及官方原碼 | [文獻與來源](LITERATURE_GUIDE.md) |
| 直接讀完整小型結果 | [R153原論文交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)、[R100／103／104原表與失敗](project_completion/curated/FAILURE_LINEAGE_READING.md) |
| 看實際原拍及重要影像 | [來源與影像取捨](SOURCE_AND_IMAGE_DECISIONS.md)、[主要原圖冊](../../RECON_GALLERY.md) |
| 本次固定保存的範圍、模型、原紀錄及缺件 | [精選交付內容](project_completion/SELECTIVE_DELIVERY.md) |

[固定保存版本及最後交付收據](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-curated-20261021)另記實際取得的程式／索引與檔案。177範圍的原問題、來源和結果一併保存；18條資料生產路線有額外的原設定整理，沒有編造其他生成命令或重跑全部GPU實驗。


原相機／量測／人工來源與可生成產物分清。9月3日930張原拍及30份原始平台紀錄只保留一份共用來源；22份早期程式、9項早期R13公式及原未寫出欄位的缺件如實保留。既有超量草稿凍結未刪，本機論文和訓練資料不動。

下方保留已發布原來源及原實測的取得方式與歷史範圍。大附件按真正需要選取，沒有要求先取回全部資料才能看方法或原數表。

## 來源與附件

| 保存內容 | 為什麼必須保存 | 取得位置 |
|---|---|---|
| 9月3日30步、30趟原始拍攝 | 930張相機BMP與30份原始平台位置紀錄，多輪實驗共同使用，不能由模型或合成資料取代 | [已發布原始資料](https://github.com/rio10255254/GMM_2_Final/releases/tag/shared-pi-20260903-v1) |
| R61／R152固定來源 | R61早期繼承的影像與幾何標記不能只靠重新推算取代；R152保留實際PSF與原模型 | [固定來源](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-training-kits-20261016) |
| R93完整歷程與簡便重算 | 補上綜合候選、全部保存的模型檔和245張原results圖；不下載大型資料也能由約36KB包重算原選擇與數字 | [R93完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r93-complete-record-20261020) |
| 共用實拍與實體參照 | Step完整788張、多倍率連拍、六組外部照片、18張P/V SEM、原始工作表與對應光學圖 | [共用來源](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016) |
| 完整逐輪結果與固定模型 | 逐筆結果、圓心／邊界、訓練紀錄、失敗與選模依據，包含實際被引用的中途模型 | [結果與模型](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) |
| 先前已封存的結果與必要補件 | 保留H槽舊版本的身分與完整數值，不覆蓋較新的正式報告 | [歷史結果與補件](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-historical-evidence-20261016) |

附件清單記錄每個原檔的內容核對值、用途與還原位置。相同內容集中保存一次，各輪原本的檔名與路徑仍會完整還原。[來源與選圖判斷](SOURCE_AND_IMAGE_DECISIONS.md)解釋取捨。

## 已實際執行的核對

| 項目 | 實測範圍與結果 |
|---|---|
| 原始30趟資料 | 從GitHub重新下載原始ZIP、拍攝清單與恢復程式，在禁止讀取舊研究位置的另一資料夾還原。930張原圖與30份原始CSV全部相同，平台X/Y、時間、影格與曝光相同 |
| R61完整資料生成 | 在另一位置禁止讀取原實驗資料，完整重建20,296組；114,283個訓練資料檔全部相同；重新執行的日期與來源位置另外記錄，不只抽樣比較 |
| R152完整資料生成 | 在另一位置禁止讀取原影像，完整重建768個母場景、3,072組視圖、9,216個TIFF；所有影像內容與檔案相同 |
| 十方法完整數值重算 | 從全部保存的邊界點、圓心、平台讀值與固定SEM參照重算。270個數值、18,000筆位移、162組完整趟次配對區間全部符合原完整報告 |
| 平均／中位數比較 | 從包內保存的原圓心與平台數值重算7,200筆彙整位移及36組區間，與既有論文交接資料相同 |
| 恢復工具 | 實測越出目錄、檔案被改動、附件損壞及既有檔案保護；有差異即停止，不覆蓋使用者改過的檔案 |

這些核對沒有重新訓練全部歷史模型，也沒有重新擬合實體輪廓。重跑訓練可能受環境與顯卡計算差異影響；當年的固定模型、完整數值與實際環境紀錄仍一併保存。

## 從GitHub取回

先取得本次保存分支的程式與說明，再按需要下載附件。倉庫維持私人狀態，需使用具有權限的GitHub帳號。

```powershell
git clone -c core.longpaths=true --depth 1 --single-branch --branch codex/research-completion-20261021 https://github.com/rio10255254/GMM_2_Final.git
cd GMM_2_Final
```

以下兩行只供需要取回既有固定訓練來源時選用；先看上方資料生產方法與各輪必要來源，不是一般閱讀的必做步驟。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-training-kits-20261016 --output downloads/training-kits
python Tools/research_asset_bundle.py restore --manifest downloads/training-kits/RESEARCH_ASSETS.json.gz --assets downloads/training-kits --destination . --keep-identical-existing
```

恢復到已有檔案的資料夾時，工具先核對所有既有檔案，只有完全相同的內容可以共存；任何修改都會停止，保留原件。也可以省略`--keep-identical-existing`，指定另一個新的空目錄。

R61與R152的完整生成入口：

```powershell
python Deliverables/R61_TrainingData_Regenerator_20261004/regenerate_r61.py --output-root YOUR_NEW_R61_FOLDER --report YOUR_NEW_R61_REPORT.json
python Deliverables/R152_Standalone_ImageFiles_20261004/generate_data.py --workers 2 --output-dir YOUR_NEW_R152_FOLDER
```

原始30趟相機資料另依[原始資料的恢復說明](../../Shared_Sources/PI_Repeatability_20260903/README.md)取回。十方法完整結果可在取回共用來源附件後重算：

```powershell
python Tools/replay_thesis_results.py --root Shared_Sources/TenMethod_SavedObservations_20261007 --spec Shared_Sources/TenMethod_SavedObservations_20261007/replay_spec.json --output YOUR_NEW_RESULT_FOLDER
```

原始歷史設定保留當年的位置作為來源紀錄。R61／R152完整生成包和上述結果重算使用相對位置或明確輸入；其他歷史程式若仍有固定位置，須依該輪來源表設定，不能只因檔案已保存便宣稱每一輪都已在任意位置重新跑通。

## D槽清理條件

原始相機資料、論文需要的資料、正式採用與對照模型、正在訓練的資料保持保護。R87已於2026-10-20以前述原模式完成單次清理，原路徑仍可讀取H工作副本；其餘52個20x／5x目錄本輪僅重核，沒有刪除。使用者再次明確指定GitHub為首要目標後，本次續整以補件及GitHub取回重做為主，不把釋放D空間當成果。[R87已完成狀態](../../Experiments/R87_TileNativeScratchGeneralization/ARCHIVE_POINTER_R87_20260926.md)／[10月16日歷史收尾](../operations/GITHUB_PRESERVATION_CLOSEOUT_20261016.md)。

## 不需要完整資料時重算論文結果

只下載[十方法完整結果重算包](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)中的`ten-method-result-replay.zip`（約77 MB），解開後依包內說明執行即可。不必先下載全部模型、照片或訓練資料。這份包已從GitHub取回，重新計算全部270項數值、18000筆位移與162組區間通過。

## 恢復各輪共用資料入口

多輪原本共用同一份資料，沒有各自複製。下載並恢復必要來源後，可執行`python Tools/restore_research_aliases.py --root .`恢復11個專案內的共用資料入口。工具先確認所有來源都在新工作區內，保留任何不同的既有資料夾；不建立通往舊H槽的依賴。這項功能已用實際資料檔測試，經新入口讀到的內容完全相同。

## 完整恢復結果與模型

結果與模型版本新增的`RESTORE_MANIFEST_20261016.json.gz`是本次收尾使用的恢復索引。它把兩份當時的容量設定放到歷史目錄，保留原內容，同時沿用程式倉庫內目前的來源保護與清理受阻狀態。科學數值、模型、影像和28個資料附件的內容均未改動。其餘三組版本使用各自的`RESEARCH_ASSETS.json.gz`。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-results-models-20261016 --output downloads/results-models
python Tools/research_asset_bundle.py restore --manifest downloads/results-models/RESTORE_MANIFEST_20261016.json.gz --assets downloads/results-models --destination . --keep-identical-existing
```

## 核對取回的程式與紀錄

`python Tools/research_recovery.py verify --root . --manifest docs/reproducibility/REPOSITORY_FILES.json.gz --report YOUR_NEW_CHECK_REPORT.json`會逐份核對這個固定版本的已保存檔案。核對清單本身除外；另裝的環境或新結果不在這份固定版本清單內。
