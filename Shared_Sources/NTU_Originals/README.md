# 公司圓環位移序列（NTU_ImageDataset）

六組公司提供的圓環位移序列，2025-10-29 拍攝，5120×5120、8 位元灰階：`Pitch1um_Y_100`、`Pitch1um_X_100`、`Pitch0.1um_Y_60`、`Pitch0.1um_X_60`、`Pitch0.01um_Y_40`、`Pitch0.01um_X_40`。這個資料夾在 Git 裡只有說明，影像都在發布附件，恢復後就放在這裡，路徑是 `Shared_Sources/NTU_Originals/<序列>/...`。原本的本機位置是 `D:/NTU_ImageDataset`（更早是下載資料夾裡的 `NTU_ImageDataset`），舊程式裡寫的就是那些路徑。

| 內容 | 附件 | 說明 |
|---|---|---|
| 相機原拍 | [research-shared-sources-20261016](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016) | `Pitch1um_Y_100` 的原拍在 `Raw/` 子資料夾，其餘在序列資料夾第一層 |
| 裁切輸入 `Cropped_Output`、`Cropped_Output_v2` | [research-ntu-gmf-and-crops-20261028](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-ntu-gmf-and-crops-20261028) | 模型實際讀的是裁切版；裁切座標與逐張核對見 [原拍與影像用途](../../docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md)，也能從原拍自己切 |
| R61 v16 外部 GMF 量測包 | [research-ntu-gmf-and-crops-20261028](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-ntu-gmf-and-crops-20261028) | `Pitch1um_Y_100`、`Pitch0.1um_X_60` 各一份 `external_gmf_r61_v16_psfoff_20260627/`：GMF 原始分數、逐幀與位置分析、當時送去量測的輸入與輸出影像、執行紀錄 |

外部 GMF 量測軟體已經不在，這兩份分數無法重新量測，所以和它量的影像整組保存。舊模型的整批重建輸出（`reconstructed_output_*`）與數位平移產生的 `Shifted_Up_Seq` 可由原拍重新產生，沒有上傳。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output ../ntu-originals --prefix Shared_Sources/NTU_Originals
python Tools/research_asset_bundle.py restore --manifest ../ntu-originals/RESEARCH_ASSETS.json.gz --assets ../ntu-originals --destination . --prefix Shared_Sources/NTU_Originals --keep-identical-existing
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-ntu-gmf-and-crops-20261028 --output ../ntu-gmf-crops
python Tools/research_asset_bundle.py restore --manifest ../ntu-gmf-crops/RESEARCH_ASSETS.json.gz --assets ../ntu-gmf-crops --destination . --keep-identical-existing
```

返回：[共用來源](../README.md)。
