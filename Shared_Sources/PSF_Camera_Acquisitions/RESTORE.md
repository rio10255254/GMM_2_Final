# 按需下載及恢復原拍

本次新附件共12,732,442,971 bytes（約12.73GB）。解開新增929原位置約21.73GB；另外9份相同既有小來源由一般程式版本提供，合計938項選定原件。826張為全幅原拍，100張為已處理擬合輸入，兩者不可混稱。

| 用途分組 | 壓縮下載大小 | ZIP附件 |
|---|---:|---|
| june15-round1 | 3,717,419,945 bytes（3.717GB） | research-june15-round1-001.zip, research-june15-round1-002.zip, research-june15-round1-003.zip, research-june15-round1-004.zip |
| june15-round2 | 3,718,484,948 bytes（3.718GB） | research-june15-round2-005.zip, research-june15-round2-006.zip, research-june15-round2-007.zip, research-june15-round2-008.zip |
| june15-round3 | 3,719,382,031 bytes（3.719GB） | research-june15-round3-009.zip, research-june15-round3-010.zip, research-june15-round3-011.zip, research-june15-round3-012.zip |
| psf100-camera | 1,563,598,062 bytes（1.564GB） | research-psf100-camera-013.zip, research-psf100-camera-014.zip |
| psf100-frozen-inputs | 13,500,418 bytes（0.014GB） | research-psf100-frozen-inputs-015.zip |

附件各自獨立，不是需要拼接的分割壓縮檔。`psf100-frozen-inputs`含95張尚未發布的處理圖及8份上游來源；另外5張處理圖、GT、兩份光學數值及1份上游程式本已保存，這次在一般程式版本提供擬合實際讀取的路徑。相同檔案內容共用Git物件。

## 先取得一份新的研究資料夾

以下只用新的工作資料夾操作；不要指向現用研究、訓練或論文資料夾。私人倉庫需有原帳號權限及GitHub CLI登入。這些步驟只下載及恢復，沒有啟動擬合或訓練。

```powershell
gh repo clone rio10255254/GMM_2_Final psf-study -- --depth 1
cd psf-study
```

選擇PSF100的原拍、實際擬合輸入和上游：

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-psf-camera-acquisitions-20261022 --output ../psf100-download --prefix Shared_Sources/PSF_Camera_Acquisitions/PSF100_20250903 --prefix PSF_Fitting/Crop_circle_FreqFiltered
python Tools/research_asset_bundle.py restore --manifest ../psf100-download/RESEARCH_ASSETS.json.gz --assets ../psf100-download --destination . --prefix Shared_Sources/PSF_Camera_Acquisitions/PSF100_20250903 --prefix PSF_Fitting/Crop_circle_FreqFiltered --keep-identical-existing
```

只需0615第一輪時：

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-psf-camera-acquisitions-20261022 --output ../june15-round1-download --prefix PSF_Fitting/quick_recalibration/validation_experiments/Circle_Round1
python Tools/research_asset_bundle.py restore --manifest ../june15-round1-download/RESEARCH_ASSETS.json.gz --assets ../june15-round1-download --destination . --prefix PSF_Fitting/quick_recalibration/validation_experiments/Circle_Round1 --keep-identical-existing
```

第二／三輪將兩行的`Circle_Round1`及下載資料夾改成對應輪次。需本版全部來源時省略兩個工具的`--prefix`；不要下載其他無關版本。`--keep-identical-existing`只接受內容完全相同的已存在檔案；遇到不同內容會先停止，不替換原檔。下載器需要Python與requests，恢復工具使用Python標準套件。

一般程式版本的兩份光學數值與GT已位於原讀取位置。0615準備程式、三份原位置對照及45份設定／結果表也在程式版本；完整既存MAT結果取[39.5MB原結果包](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-optical-calibration-replay-20261021)，不必再下載重複模型或11.4GB本機綜合交付包。現存前處理來源不保證與歷史每一版逐行相同，舊100張實際輸入另行凍結保存。

逐檔選擇見[SOURCE_CATALOG.json](SOURCE_CATALOG.json)，新增附件恢復對照見[RESEARCH_ASSETS.json.gz](RESEARCH_ASSETS.json.gz)。既有Step另用[原附件位置表](June15_20260615/STEP_EXISTING_PROVIDERS.json)，不要將它套進本版恢復清單。
