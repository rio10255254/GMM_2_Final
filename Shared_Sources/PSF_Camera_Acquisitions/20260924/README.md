# 2026-09-24 中央九點 PSF 原拍

2026-09-24 拍攝的中央九點 PSF 原拍，25 張 BMP，加上拍攝紀錄 `snapshots.csv`（同一份也附在 [research-results-models-20261016](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)）。同一天另有三支控制程式的錄影，那是實驗室系統的紀錄，不在這裡。

影像在發布附件 [research-shared-sources-20261016](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，Git 裡只有這份說明；恢復後就放在這裡，路徑是 `Shared_Sources/PSF_Camera_Acquisitions/20260924/...`。原本在專案根目錄，只存在附件裡；2026-10-28 重整時定了這個位置。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output ../psf-20260924 --prefix Shared_Sources/PSF_Camera_Acquisitions/20260924
python Tools/research_asset_bundle.py restore --manifest ../psf-20260924/RESEARCH_ASSETS.json.gz --assets ../psf-20260924 --destination . --prefix Shared_Sources/PSF_Camera_Acquisitions/20260924 --keep-identical-existing
```

返回：[PSF 取像](../README.md)。
