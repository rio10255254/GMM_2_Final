# 100MG 樣品 50× 位移原拍

2026-07-02 拍攝的 100MG 樣品，50×，兩組位移：`x_0.5um/` 51 張、`x_1um/` 50 張，8 位元灰階 BMP。分析在 [20260702_100MG_displacement_analysis](../../../Analyses/20260702_100MG_displacement_analysis/README.md)。

影像在發布附件 [research-shared-sources-20261016](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，Git 裡只有這份說明；恢復後就放在這裡，路徑是 `Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x/...`。原本在專案根目錄，只存在附件裡；2026-10-28 重整時定了這個位置。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output ../captures-100mg-50x --prefix Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x
python Tools/research_asset_bundle.py restore --manifest ../captures-100mg-50x/RESEARCH_ASSETS.json.gz --assets ../captures-100mg-50x --destination . --prefix Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x --keep-identical-existing
```

返回：[實拍原拍](../README.md)。
