# Step 樣品原拍

2026-06-15 拍攝的 Step 樣品，788 張 8 位元灰階 BMP，都在資料夾第一層，檔名是拍攝時間。分析在 [Step_analysis_20260623](../../../Analyses/Step_analysis_20260623/README.md)。

影像在發布附件 [research-shared-sources-20261016](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，Git 裡只有這份說明；恢復後就放在這裡，路徑是 `Shared_Sources/Real_Sample_Captures/Step/...`。原本在專案根目錄，只存在附件裡；2026-10-28 重整時定了這個位置。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output ../step-captures --prefix Shared_Sources/Real_Sample_Captures/Step
python Tools/research_asset_bundle.py restore --manifest ../step-captures/RESEARCH_ASSETS.json.gz --assets ../step-captures --destination . --prefix Shared_Sources/Real_Sample_Captures/Step --keep-identical-existing
```

返回：[實拍原拍](../README.md)。
