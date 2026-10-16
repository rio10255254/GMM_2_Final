# 研究保存與重做入口

本次逐輪整理177個主專案、Lab系統實驗或早期歷史批次。目標是保留「當時想解決什麼、實際做了什麼、用過哪些來源、全部結果與限制」，並讓必要來源可以從GitHub取回。

[逐輪研究入口](EXPERIMENTS.md)按實驗說明判讀、必要來源與選圖理由；各輪原始正式報告仍是科學結論的依據。整理不改變COMBO正式基準，也不把研究模型自動升級。

## 來源與附件

| 保存內容 | 為什麼必須保存 | 取得位置 |
|---|---|---|
| 9月3日30步、30趟原始拍攝 | 930張相機BMP與30份原始平台位置紀錄，多輪實驗共同使用，不能由模型或合成資料取代 | [已發布原始資料](https://github.com/rio10255254/GMM_2_Final/releases/tag/shared-pi-20260903-v1) |
| R61／R152固定來源 | R61早期繼承的影像與幾何標記不能只靠重新推算取代；R152保留實際PSF與原模型 | `research-training-kits-20261016` |
| 共用實拍與實體參照 | Step完整788張、多倍率連拍、六組外部照片、18張P/V SEM、原始工作表與對應光學圖 | `research-shared-sources-20261016` |
| 完整逐輪結果與固定模型 | 逐筆結果、圓心／邊界、訓練紀錄、失敗與選模依據，包含實際被引用的中途模型 | `research-results-models-20261016` |
| 先前已封存的結果與必要補件 | 保留H槽舊版本的身分與完整數值，不覆蓋較新的正式報告 | `research-historical-evidence-20261016` |

附件清單記錄每個原檔的內容核對值、用途與還原位置。相同內容集中保存一次，各輪原本的檔名與路徑仍會完整還原。[來源與選圖判斷](SOURCE_AND_IMAGE_DECISIONS.md)解釋取捨。

## 已實際執行的核對

| 項目 | 實測範圍與結果 |
|---|---|
| 原始30趟資料 | 從GitHub重新下載原始ZIP、拍攝清單與恢復程式，在禁止讀取舊研究位置的另一資料夾還原。930張原圖與30份原始CSV全部相同，平台X/Y、時間、影格與曝光相同 |
| R61完整資料生成 | 在另一位置禁止讀取原實驗資料，完整重建20,296組；114,283個檔案全部相同，不只抽樣比較 |
| R152完整資料生成 | 在另一位置禁止讀取原影像，完整重建768個母場景、3,072組視圖、9,216個TIFF；所有影像內容與檔案相同 |
| 十方法完整數值重算 | 從全部保存的邊界點、圓心、平台讀值與固定SEM參照重算。270個數值、18,000筆位移、162組完整趟次配對區間全部符合原完整報告 |
| 平均／中位數比較 | 從包內保存的原圓心與平台數值重算7,200筆彙整位移及36組區間，與既有論文交接資料相同 |
| 恢復工具 | 實測越出目錄、檔案被改動、附件損壞及既有檔案保護；有差異即停止，不覆蓋使用者改過的檔案 |

這些核對沒有重新訓練全部歷史模型，也沒有重新擬合實體輪廓。重跑訓練可能受環境與顯卡計算差異影響；當年的固定模型、完整數值與實際環境紀錄仍一併保存。

## 從GitHub取回

先取得本次保存分支的程式與說明，再按需要下載附件。倉庫維持私人狀態，需使用具有權限的GitHub帳號。

```powershell
git clone --branch codex/research-recovery-20261016 https://github.com/rio10255254/GMM_2_Final.git
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

原始相機資料、論文需要的資料、正式採用與對照模型、正在訓練的資料保持保護。只有完整備份重新逐檔核對、GitHub保存驗證、活動程序與下游讀取位置都確認後，才執行清單內的舊副本清理。實際清理及回收空間以收尾紀錄為準。
