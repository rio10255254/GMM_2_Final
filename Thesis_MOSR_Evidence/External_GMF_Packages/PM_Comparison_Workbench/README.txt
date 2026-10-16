這是外部定位比較包；GMF、PM 或其他能輸出座標的工具都可以共用同一個佈局。

目前固定比較五個已完成的影像序列：
- models\R61v11
- models\V42E120
- models\R103E48
- models\R104E48
- models\R109E48

每個模型底下都有三個主要資料夾：
- raw：同一批 101 張原始影像（frame_0000.bmp 至 frame_0100.bmp；R61 的來源檔名已在包內整理成 raw_0000.bmp 形式）
- recon：該模型的 101 張重建影像
- txt_out：外部工具輸出放置區（原圖與重建圖都放這裡，但檔名要區分來源）

使用方式：
1) 由 paths_for_external_tools.tsv 取得每個模型的 raw、recon 和 txt_out 路徑。
2) 外部程式分別對 raw 與 recon 執行；每個模型請使用同一套參數、同一個模板與同一個參考影格。
3) 將輸出文字原封不動放入對應的 models\<模型>\txt_out\。建議使用以下命名，避免原圖與重建圖覆蓋：
   - raw_GMF_score.txt
   - recon_GMF_score.txt
   - raw_PM_score.txt
   - recon_PM_score.txt
   也可以保留工具自動產生的長檔名，只要檔名中包含 raw 或 recon。若只測重建結果，至少使用 recon_ 開頭；不需要修改文字內容。
4) 完成後執行 tools\check_and_summarize.ps1；它會先檢查影格，再重新產生 analysis\verification.json、analysis\external_outputs_summary.json、external_outputs_summary.csv，以及 raw／recon 配對用的 external_comparison.json 和 .csv。沒有文字檔的模型會被標成 pending，不會被誤算成零分。
5) 若你另外提供一份共用的 Raw PM 結果，執行 tools\compare_pm_with_raw.py --raw <Raw_PM_score.txt>，即可把這份 Raw 與五個模型逐一比較。

目前這次提供的 Raw PM 已經收在 reference\raw\PM_score.txt；因此直接執行 tools\compare_pm_with_raw.py（不加參數）即可重做同一份比較。

V42 的 recon 是 R111 實驗中固定 1024 core、256 halo、反射邊界、只保留中央區域的切塊結果；R61 的檔名與其他模型不同，但每一張都保留原始影格索引，分析程式會依索引對齊。

外部程式（若要直接使用）：
E:\Archive\GMM_Software_residual\GmmVisionToolExe_20260107\GmmVisionToolExe\GmmVisionTool.exe

結果檔不會在本包內預填；目前留下的空白 GMF_score.txt 只是位置提示。實際輸出請使用上面的 raw_/recon_ 檔名，並保留原始內容。之後可直接把整個 PM_Comparison_Workbench 資料夾交回分析。
