# R76：R75 對 SEM 的完整輪廓驗證

這個資料夾用來回答一件事：完全從頭訓練的 R75，重建後的柱子形狀是否真的更接近 SEM。

驗證不靠半徑，也不假設柱子是圓形。每一顆柱子的完整外框都會拿來比較，而且只允許把中心位置對齊，不會偷偷替模型調整大小或角度。

## 這裡如何知道哪一顆是哪一顆

九張 P 系列 SEM 各包含 2×2 四顆柱子。舊研究程式保存了九張圖在中央 3×3 區塊中的放置順序，再配合每張圖內的左上、右上、左下、右下位置，就能還原中央 6×6 的 36 顆編號。

R76 會在執行前再次確認：

1. 現在 H 槽的 18 張 P/V SEM 與舊研究資料逐張完全相同。
2. 新整理的 36 顆對照表與先前 R69 實驗使用的表完全一致。
3. 十二張光學影像與當年來源逐張完全相同。
4. R75 權重是在訓練內部選出的，沒有看 SEM 挑權重。

## 執行方式

訓練完成後，在這個資料夾執行：

`C:\Users\Rio\anaconda3\python.exe scripts\run_r76.py --stage all`

如果訓練尚未完成，也可以讓它等待：

`C:\Users\Rio\anaconda3\python.exe scripts\run_r76.py --stage all --wait-training-minutes 120`

最後結果會放在：

- `reports/R76_FINAL_SYNTHESIS_TW.md`：第 21 輪與第 100 輪合併後的最終結論。
- `reports/R76_RESULTS_TW.md`：白話結論。
- `reports/R76_EPOCH100_AUDIT_TW.md`：第 100 輪的獨立排除檢查。
- `results/figures`：重建前後、36 顆疊圖、亮度穩定性與輪廓設定敏感度。
- `results/tables`：逐曝光、逐顆柱子的完整數字。
- `results/input_audit.json`：影像配對與權重來源的核對紀錄。

本次另外固定檢查了第 100 輪，用來排除正式最佳權重停在第 21 輪造成的誤判。兩個 checkpoint 都是在看 SEM 結果前先定義好的；SEM 沒有參與挑 epoch。
