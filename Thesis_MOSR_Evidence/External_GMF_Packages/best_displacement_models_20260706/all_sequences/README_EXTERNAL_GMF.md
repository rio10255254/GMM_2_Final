# all_sequences

這是給外部 GMF 程式使用的影像包。

使用方式：
1. 打開 `paths_for_gmf_tool.tsv`。
2. 對每一列的 `image_folder` 跑外部 GMF。
3. 把輸出的 `GMF_score.txt` 放到同一列指定的 `score_folder`。

這包包含 Raw、V20、V28、V31、V35、V41。Raw 是對照，V20 是形狀保守參考，V28/V31/V35 是目前位移較穩候選，V41 是小方形形狀安全候選。

注意：`trusted_full_sequences` 排除了 5x_1um；`all_sequences` 仍保留 5x_1um 作完整檢查。

每個 case 的影像都已重新命名成 `frame_####.bmp`，同一組內 Raw 與各模型 frame 順序一致。
