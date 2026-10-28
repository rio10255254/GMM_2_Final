> **2026-10-03新版：** [模型設計、共同量測與兩倍率結果海報](poster_final/START_HERE.md)，保留TW0243；功能圖及實際邊界示例已完成，公開版不附完整訓練配方與額外論文結果。

> **最新海報：** [兩倍率各30個1 µm單步位移](poster_final/START_HERE.md)。20×改用論文第一趟驗證資料，50×完整重跑核對；分別降低57.2%／23.5%，不跨條件平均。

> **最新檢查：** 原稿找外框流程有順序依賴，已固定狀態並重算四方法全部120配對。[查看LSC與位移稽核](reports/R152_DISPLACEMENT_AUDIT.md)。舊表保留作重播紀錄。

# R152 IMPACT2026：完整四條件交付

原四組120配對、166張原始影像的Raw／Fixed Wiener／R152比較已完成。20×使用R152原生光學資料，50×使用原校正單核並增加小幅推論輸入適配；同一套學得權重，沒有重訓。

- [主結果](reports/R152_RESULTS.md)
- [協議、光學來源與接線核對](reports/R152_AUDIT.md)
- [最新海報素材入口](poster_assets/full120/START_HERE.md)
- [最終驗證](results/full120/delivery_verification.json)
- [四條件總表](results/full120/aggregate_summary.csv)
- [各條件表](results/full120/condition_summary.csv)
- [全部逐對明細](results/full120/per_pair.csv)
- [與共用光學資料版本比較](results/full120/calibrated_vs_shared_optics.csv)

主結果設定來自使用者最後指令，不按量測結果選版本。原共用光學版本保存在results/shared_bank120及results/50x_shared_bank；早期缺項紀錄保存在reports/history_20x_stage。

工作區分支sandbox/r152-impact2026。D:/GMM_2_Final的原模型、光學檔、影像、既有結果與正式基準保持原樣；大型來源唯讀引用，小型程式和配對有核對副本。本工作區根層其餘專案內容可能來自較早Git提交，當次來源專案現況在sources/source_project_state.md。

## 重跑入口

使用C:/Users/Rio/anaconda3/python.exe，從本目錄執行：

```text
python -B scripts/check_objective_adapter.py
python -B scripts/run_50x_calibrated.py
python -B scripts/summarize_full120.py
python -B scripts/build_full120_assets.py
python -B scripts/finalize_full120.py
python -B scripts/verify_full120.py
```

已完成的20×輸出持續沿用。如需重做20×，使用scripts/run_20x.py；既有影像收據會核對後復用。所有入口不包含重新訓練。

## 實際影像與實驗設計

- [完整影像與具體設定](inspection/EXPERIMENT_DESIGN.md)
- [逐組影像瀏覽頁](inspection/image_browser.html)

## 定位與計算改良

[同一新讀法的Raw／Wiener／R152比較](reports/R152_LOCALIZATION_IMPROVEMENT.md)已完成；[公平呈現圖](poster_assets/localization_improvement/START_HERE.md)。未劣化Raw，原讀法與退步項完整保留。

## IMPACT海報

[最新海報PowerPoint](poster_final/IMPACT2026_MOSR_Design_TW0243_v3.pptx) · [印刷PDF](poster_final/IMPACT2026_MOSR_Design_TW0243_v3.pdf) · [預覽](poster_final/IMPACT2026_MOSR_Design_TW0243_v3.png)

依提供的90×120cm直式兩欄範本製作；20×／50×各30個1 µm单步位移分開呈現，Introduction及Methods擴充，新增兩張實測曲線。詳見[最新統計紀錄](reports/R152_30STEP_POSTER_RESULTS.md)。投稿編號為TW0243。
