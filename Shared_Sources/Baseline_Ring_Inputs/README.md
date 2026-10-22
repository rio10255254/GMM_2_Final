# 早期主線共用環形來源：R33、COMBO、R39、R40

[四輪方法與來源核對](../../docs/reproducibility/round_source_reviews/BASELINE_20261023.md) · [共用來源總入口](../README.md) · [目前保存狀態](../../docs/reproducibility/STATUS.md)

這裡只保留跨輪共用、目前未找到可靠原生成來源的固定輸入。不是把所有大型訓練資料重新上傳。

## 原1,100組分成兩部分

| 原位置 | 來源與保存方式 |
|---|---|
| tra_src_ring／tra_lbl_ring的6001–7000 | 1,000組原輸入／答案，共2,000檔；原生成器及當時PSF身分仍未釐清，因此經使用者明確同意補存一次。壓縮檔234,381,397 bytes（約234MB），原檔合計526,444,000 bytes |
| 同兩個資料夾的7001–7100 | 100組已對到既有PSF處理輸入與共用答案圖；使用已發布來源，不重傳這200個位置。100份答案圖內容相同，也不當成100份不同答案 |

後100組中，95張處理輸入在既有PSF附件，5張處理輸入與共用答案圖已在一般程式版本。這些是處理過的固定輸入，不能改稱100張全幅相機原拍；其相機來源另見[PSF原拍](../PSF_Camera_Acquisitions/README.md)。

早期原資料流報告已指出環形資料的來源與舊PSF版本不明。保存現存原件能保留研究輸入，不能反過來補造其生成歷史，也不能單憑現在檔案就證明每次歷史執行都讀到完全相同版本。

## 在新位置取回完整1,100組

需要Python3.11以上、requests及已登入的GitHub CLI。Windows取得副本時啟用Git長路徑支援（入門指南的clone命令已包含）。先取得最新GitHub副本，以下在該副本內執行；所有輸出用新的空位置。本機正在使用的D專案不需要執行這些命令。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-baseline-fixed-sources-20261023 --output ../baseline-download --prefix Training_Data
python Tools/research_asset_bundle.py restore --manifest ../baseline-download/RESEARCH_ASSETS.json.gz --assets ../baseline-download --destination ../baseline-restored --prefix Training_Data
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-psf-camera-acquisitions-20261022 --output ../existing-psf-download --manifest-path Shared_Sources/Baseline_Ring_Inputs/EXISTING_PSF_INPUTS_RESTORE.json.gz
python Tools/research_asset_bundle.py restore --manifest Shared_Sources/Baseline_Ring_Inputs/EXISTING_PSF_INPUTS_RESTORE.json.gz --assets ../existing-psf-download --destination . --keep-identical-existing
python Tools/restore_baseline_ring_aliases.py --source-root . --destination ../baseline-restored --manifest Shared_Sources/Baseline_Ring_Inputs/EXISTING_RING_ALIASES.json
```

第三行只取既有約13.50MB的處理輸入附件，不會下載完整PSF原拍。最後一行依逐檔對照補回7001–7100；相同既有內容保留，內容不同則停止，不覆寫。

結果是`baseline-restored/Training_Data/tra_src_ring`及`tra_lbl_ring`各1,100檔。後續使用原訓練程式時，需在新的副本按原設定對到這個位置；本次沒有啟動訓練或改寫原工作區。

[新增原件清單](RESEARCH_ASSETS.json.gz)、[已發布來源的位置對照](EXISTING_RING_ALIASES.json)、[全部固定來源判讀](FIXED_SOURCE_REVIEW.json.gz)。[發布版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-baseline-fixed-sources-20261023)只存必要共用來源一次。

## 這包沒有包含的內容

stage25／26的8px序列、R39後來的形狀集及R40顯微生成集，保留生成程式、實際配方、固定PSF及原資料清單，沒有整套重傳。這次R40生成器抽查20張影像內容相同，不冒稱所有生成資料、環境與歷史訓練都已完整重跑。

## 實際取回結果

新包的2,000個原檔與重用來源的200個位置已實際組回，兩個資料夾各1,100檔，全部內容相同。已有相同檔案保留，不同檔案會在開始複製前停止；原工作區沒有被覆寫。[完整交付核對](DELIVERY_VERIFIED.json)。暫存依使用者要求保留，沒有清理。
