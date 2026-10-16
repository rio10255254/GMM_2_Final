這個資料夾由 tools/verify_bundle.py 與 tools/analyze_outputs.py 產生。

verification.json：檢查五個模型是否各有 101 張影像、影格索引是否完整、BMP 尺寸是否一致，以及外部文字結果是否已放入。
external_outputs_summary.json / .csv：讀取各模型 txt_out/ 中的非空文字檔。檔名前綴 raw_ 或 recon_ 會記錄為輸入來源；GMF_score.txt 與 PM_score.txt 會計算可辨識的座標步進、波動與分數；其他格式若沒有可辨識的 PosX/PosY，會保留為 unparsed，不會被當成失敗或零分。若外部程式把影格名稱改成時間戳，程式會依文字檔內的行順序暫時編號，並在 frame_index_inferred 標記為 true。

external_comparison.json / .csv：當同一模型、同一方法的 raw_ 與 recon_ 結果都存在時，會列出 recon 減 raw 的變化，方便直接看重建後位移波動、直線殘差與分數如何改變。沒有配對的結果不會被補成零。

若只有一個共用的 Raw PM 結果，可執行 tools/compare_pm_with_raw.py --raw <Raw_PM_score.txt>。它會把每個模型 txt_out/ 的結果視為重建結果，產生 pm_raw_vs_recon_comparison.json / .csv；報告會保留 Raw 檔案路徑與這個配對假設。本次提供的 Raw 已固定收在 reference/raw/PM_score.txt，直接執行 tools/compare_pm_with_raw.py 即可重做。

PM_RAW_VS_RECON_READOUT.md 是本次五模型比較的白話摘要；PM 分數只代表外部程式的匹配結果，不能單獨當成影像細節或 ACM 的真值。

目前尚未放入新的外部結果，所以所有模型的狀態是 pending；這是等待輸入，不代表模型分數為零。
