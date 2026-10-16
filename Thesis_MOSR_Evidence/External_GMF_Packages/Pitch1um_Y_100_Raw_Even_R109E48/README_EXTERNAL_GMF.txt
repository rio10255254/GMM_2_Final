Pitch1um_Y_100：Raw 與 R109 E48 外部 GMF 驗證

兩份外部 GMF 座標都已放入並完成分析。

原始資料共有 202 張，也就是 101 個位置、每個位置連拍兩張。依時間戳
檔名排序後，本包只保留第 2、4、6、…、202 張，因此共有 101 張影像，
可計算 100 段相鄰位置位移。

請分別對以下兩個影像資料夾執行外部 GMF：

1. pitch1um_y100_raw\bmp
2. pitch1um_y100_r109_e48\bmp

兩邊檔名完全相同，從 frame_0000.bmp 到 frame_0100.bmp。請不要改名、
刪除或重新排序。

兩份座標結果保存在 _gmf_scores 內對應的 Raw 與 R109 資料夾；完整分析
位於 gmf_analysis。R109_external_GMF_analysis.ipynb 是已由頭執行並確認
無錯誤的計算筆記，analysis_summary.json 是機器可讀摘要，
trajectory_step_score.png 是主要比較圖。

若日後重新執行外部 GMF，可用新結果覆蓋兩份 GMF_score.txt，再重新執行
分析筆記。paths_for_gmf_tool.tsv 保留影像與座標資料夾的完整對應，
source_mapping.csv 則保留標準檔名、原始時間戳檔名與檔案指紋。
