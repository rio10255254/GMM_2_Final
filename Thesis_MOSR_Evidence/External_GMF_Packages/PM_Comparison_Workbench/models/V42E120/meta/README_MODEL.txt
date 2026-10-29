模型：V42E120
來源原圖：Thesis_MOSR_Evidence/External_GMF_Packages/Pitch1um_Y_100_Raw_Even_R109E48/pitch1um_y100_raw/bmp
來源重建：Experiments/R111_R109V42ThesisReplacementQualification/external_gmf_v42/pitch1um_y100_v42_e120_tiled/bmp
影格數：101（frame_0000.bmp 至 frame_0100.bmp）

外部工具執行方式：
1) 讀取 raw/ 作為原始對照。
2) 讀取 recon/ 作為 V42 重建結果。
3) 不要改文字內容；將外部工具輸出的座標或評分文字原封不動放到 txt_out/，建議在檔名加上 raw_ 或 recon_ 前綴。

GMF 若輸出 GMF_score.txt，直接使用該檔名即可；PM 或其他方法可使用其原始 .txt 檔名，同一模型的文字檔全部放在此 txt_out/。
