# 從哪裡讀、需要下載多少

[專案首頁](../../README.md) · [研究分區](EXPERIMENTS.md) · [目前保存狀態](STATUS.md)

## 先看懂，不用先取得訓練資料

1. 讀[目前論文交接](../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)，確認現在關心的是位移、尺寸、輪廓和效率中的哪一項。
2. 用[研究沿革](lineage/README.md)理解方法怎麼演變；已知輪次就查[逐號表](lineage/ROUND_NUMBER_MAP.md)。LabSystem、主R輪次、V版本及資料stage分開查。
3. 進[逐輪閱讀卡](EXPERIMENTS.md)，先找原報告的問題、方法、來源、完整結果與失敗，再讀程式及設定。
4. 看[文獻來源](LITERATURE_GUIDE.md)和[選圖理由](SOURCE_AND_IMAGE_DECISIONS.md)。重要圖幫助理解，完整原數表才保留全部觀察；不利結果也在原結果內。

GitHub網頁可直接閱讀，不需要先複製整個倉庫。私人倉庫和附件都需要具有讀取權限的帳號。

## 只想重算已有結果

先到[按用途選附件](ASSET_GUIDE.md)找小型包。R93的原數字包只有36,022 bytes，R94／95／97／98共用數字包約3.67MB；它們不需要訓練影像或模型。十方法完整結果包約77.32MB；請依包內原說明使用。

例如取回R93數字包，在一個**新的空資料夾**執行：

```powershell
gh release download r93-complete-record-20261020 --repo rio10255254/GMM_2_Final --pattern r93-result-replay.zip --dir downloads
Expand-Archive -LiteralPath downloads/r93-result-replay.zip -DestinationPath r93-result
cd r93-result
python Tools/replay_r93_stopped_results.py --root . --output replayed_results
```

這段只重算原停止結果與選擇，不會啟動模型或訓練。輸出會保留原訂64輪、實際60輪和48輪綜合候選，不補成完成64輪。若輸出已存在，請另選新位置，保留上次結果。

## 要產生訓練資料或操作原模型

先取得程式，再按該輪需要取回必要來源：

```powershell
git clone -c core.longpaths=true --depth 1 --single-branch --branch main https://github.com/rio10255254/GMM_2_Final.git
cd GMM_2_Final
```

這是目前整理後的閱讀版本；`--depth 1`省略完整舊歷史，不代表倉庫完全沒有影像。追查較早版本時，使用原報告指定的固定版本或另外取回歷史，不能只憑main最新程式代替當時版本。

| 你要做的事 | 必須先確認 |
|---|---|
| 生成訓練資料 | [生成方法](GENERATION_GUIDE.md)：原生成器、實際設定、亂數、來源與修正。R94至98共用R93；R99／100／102至104共用R92，兩套不能互換 |
| 重建R61 v16資料 | [獨立包說明](../../Deliverables/Data_Regenerators/R61_TrainingData_Regenerator_20261004/README_TW.md)：3,400組繼承來源和當時幾何仍要取回，其餘16,896組由原程式生成 |
| 使用R152論文版 | [獨立影像包](../../Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/README.md)：保留原25PSF、模型與資料配方，不是其他專案同名R152 |
| 讀取原模型 | [關鍵模型](MODEL_GUIDE.md)：先找用途、原內容身分及適配程式，最佳／最後／平滑模型不能互換 |
| 做實拍位移比較 | [930張共用原拍](../../Shared_Sources/PI_Repeatability_20260903/README.md)：同時保留30份原位置紀錄、順序及曝光，不以重建圖代替 |

原程式、套件版本與固定來源各歸原輪次。2026-10-28重整後，程式從自己的位置找專案根，不再寫死當年D槽位置；舊報告、log和設定快照仍記錄當時路徑，那是歷史紀錄。部分流程需MATLAB或外部GMF，請在新副本依原說明安裝，不覆寫自己的舊工作。沒有一條通用命令可宣稱所有歷史實驗都不需調整就能重跑。

## 看到舊日期或缺件時

先看[已知缺件](KNOWN_GAPS.md)。22份早期原程式與R13原公式已找回；仍缺的R63原模型、未辨認的主R36及當年未保存狀態分開記錄，不能拿後來版本補成原件。舊保存收據只證明當時列出的取回或執行；2026-10-21的舊全量上傳方案已停止，不是閱讀或重做的必要步驟。
