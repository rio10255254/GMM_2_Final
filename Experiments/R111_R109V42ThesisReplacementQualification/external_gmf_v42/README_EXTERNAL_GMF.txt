V42 E120 外部 GMF 驗證包（已完成）

V42、Raw與R109三組外部GMF座標都已完成。V42座標保存在：
_gmf_scores\pitch1um_y100_v42_e120_tiled\GMF_score.txt

三方分析保存在：
..\results\external_gmf_three_way\analysis_summary.json

這批共有 101 張，檔名 frame_0000.bmp 到 frame_0100.bmp，與既有 Raw/R109 完全對齊。

V42 無法整張重建 5120x5120 影像，實測會要求約 84.38 GiB 顯存。因此本包採固定
1024 core、256 halo、反射邊界、只保留中央區域的切塊方式。V42 訓練時沒有像 R109
那樣明確加入切塊一致性契約；不過本次代表影像用 1024 與 1536 core 交叉檢查時，
最大只差 1 階灰階。詳細結果保存在 package_manifest.json。
