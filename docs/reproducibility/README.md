# 研究保存與重做入口

2026-10-21最新範圍是**精選、輕量的研究倉庫**：原程式、設定、文獻／文件、完整量測與比較表、關鍵模型和必要代表圖。全量大檔上傳已停止；大量訓練影像、逐張重建陣列和全部中途模型留在本機／H，GitHub留下來源與重做方法。既有草稿先凍結，沒有自動刪除；較早保存與取回證據按原時間保留。從[專案地圖](../navigation/PROJECT_MAP.md#我現在要找什麼)依內容查找，最新判斷以[精選整理範圍](project_completion/README.md)為準。

早期R33至COMBO的10套重建現已[精選34張原圖並保留140份完整量測](project_completion/curated/EARLY_RECON_SELECTION.md)，完整生成序列改從固定歷史查找。新讀者請使用下方目前保存分支，不以舊版完整圖庫作為必下載內容。

2026-10-21最新：[R94／R95／R97／R98完整保存與另址重做](four_rounds/README.md)。完整模型、663張原影像、失敗與恢復歷程已取回核對，32組原推論輸出相同；[本次GitHub總入口](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-preservation-20261021)。

本次逐輪整理177個主專案、Lab系統實驗或早期歷史批次。目標是保留「當時想解決什麼、實際做了什麼、用過哪些來源、全部結果與限制」，並讓必要來源可以從GitHub取回。

2026-10-20 續整重點是 GitHub 能否真正取回使用。已補足 R93 的第48輪綜合候選與完整既存模型／影像歷程，另提供約36KB的原結果重算包；並核對R93、R94、R95、R97、R98的共用資料鏈。[新的重做入口](r93_shared/README.md)／[R93原圖與副作用](r93_shared/GALLERY.md)。

[逐輪研究入口](EXPERIMENTS.md)按實驗說明判讀、必要來源與選圖理由；各輪原始正式報告仍是科學結論的依據。整理不改變COMBO正式基準，也不把研究模型自動升級。

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
