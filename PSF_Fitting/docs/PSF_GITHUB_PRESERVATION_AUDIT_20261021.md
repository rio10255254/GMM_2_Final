# PSF來源、歷史與GitHub重算審查

本審查整理既存來源與結果，不重新擬合、不改光學答案、不使用訓練顯卡，也不改正式模型或論文採用身分。全專案其他大型資料仍在保存核對，不能由這份小包推定整個專案完成。

## 四條不同用途的路線

| 路線 | 真正做的事 | 應讀的來源與限制 |
| --- | --- | --- |
| 正式Whole-FOV擬合 | 理論光學基底與量測／目標配對，先細化對齊再最佳化像差；維持tilt鎖定 | [正式入口](../run_psf_fitting_manual.m)、[核心](../HDR_fitting_2D_WholeFOV_impl.m)、[ValidationLab已完成結果](../PSF_Fitting_ValidationLab/outputs/reports/final_candidate_full100_summary_tw.md)。不能把教學預覽當成這個程序 |
| 早期L0 setA–D | 同一批影像重跑，研究擬合收斂域、參數邊界和計算底噪 | [歷史總覽](../quick_recalibration/validation_experiments/README_TW.md)。其L1待開始文字是較早快照；舊四組分類與新拍攝結果分開 |
| 新拍攝L0／L1 | Circle_Round1為正式L0；Round2/3只做拍攝之間的來源診斷，每輪各15次擬合，取每輪中位代表再比較 | [正式L0來源規則](../quick_recalibration/validation_experiments/L0_newdata/README_TW.md)、[較晚L1完成摘要](../quick_recalibration/validation_experiments/L1_newdata/README_TW.md)。三輪拍攝是三個拍攝單位，15次擬合不能當作15次新拍攝 |
| 教學包的Python流程預覽 | 複製初始PSF形成stack，計算raw與GT差異；預覽圖由`raw + 0.2*(raw-GT)`產生 | [實際程式](../PSF_Fitting_Tutorial/scripts/tutorial_workflow.py)。它沒有最佳化像差，也沒有執行Wiener反捲積；`fitted_count`與輸出檔名不能作為真實擬合完成證據。教學包的MATLAB主入口另有實作，兩者不混用 |

快速校正的[原設計](../quick_recalibration/DESIGN_TW.md)仍按設計案閱讀；後來完成的L0／L1有各自結果，不能據此宣稱整套跨機台轉移、假介入或真介入都完成。

## 實拍、擬合與來源層級

Circle_Round1/2/3各有11×11位置，每位置連拍兩張。主擬合取第一張，原九點位置是1、6、11、56、61、66、111、116、121，每輪15次，共45份已完成結果。另一張影像只進[363組paired-frame影像比較](../quick_recalibration/validation_experiments/L1_paired_frame_check/README_TW.md)，沒有另做PSF擬合。

原L1結果的拍攝間中位波動0.004086，小於重複擬合底噪0.027055；扣除後的中位淨量為零。這表示在本次來源與讀法下，未能分辨超過擬合底噪的拍攝差異。不能說機台完全沒變、係數是真實光學答案，或已完成絕對校準。鎖定、貼到搜尋邊界與幾乎固定的係數也不能拿來冒充獨立且可靠的底噪來源。

必要原件包括：原相機圖、當時裁切／中心填平和邊界遮罩、原GT與SEM配對、理論光譜／PSF基底、45份重複擬合MAT和原表、100位置正式候選、原設定和被取代版本。相機照片與擬合PSF明確分開，MATLAB與BADS執行需求保留。全文脈絡與完整原件依[全專案保存入口](../../docs/reproducibility/project_completion/README.md)核對，不只留最後一張PSF圖。

## 小型重算包與已實測範圍

約40MB的既存結果包保留102份原結果、原分析程式及核對參照，可不下載完整拍攝資料就執行：

```text
python Tools/replay_psf_saved_results.py --root EXTRACTED_KIT --output NEW_PSF_RESULT_FOLDER
```

此處重做分析，不重跑最佳化。三輪45份結果由原L0／L1讀取程式重算，原L1摘要和陣列的2016個數字欄位吻合。100位置原讀法另有48個摘要數字，與2026-10-21用原程式建立的CPU參照吻合；這份CPU參照不冒稱歷史擬合重跑。[取回與實測入口](../../docs/reproducibility/optical_calibration/README.md)。

## 100位置的儲存形狀與真正位置

原候選MAT把100份PSF存成`101×101×1×100`，而且明記`subset-order`。原報告輔助程式直接按這個儲存形狀畫成1×100；其中「中心／邊緣／角落」標籤是儲存陣列位置，不能直接當作原拍攝的10×10實體位置。

本次另外依原MAT的`source_file_index_map`、`source_row_map`、`source_col_map`與原CSV逐筆相符的位置，建立10×10顯示版。全部100位置、1020100個PSF原值及其他陣列逐份不變；重複位置或MAT／CSV位置不符會停止。原MAT、原讀法、原圖保留，新圖明記是本次由原位置資料重新排列，沒有重新擬合或改物理結果。兩個版圖的代表位置不同，不用新圖冒充歷史原圖。

原案例、完整負面結果與來源限制保留，不因成功重算而把研究校正結果升格為正式外部真值。


## 頻譜新舊版與原件重算

全內容核對另找出兩張反捲積頻譜圖與GitHub舊版不同。舊圖說標0.08，現圖及原MAT標0.05；20倍原拍頻譜不變但V42／反捲積頻譜不同，50倍較早範圍256×257、目前256×256。兩版原圖／陣列分別保留，不能只當作換版面，也不只用單一參數解釋全部差異。

九份小型必要原件共5058734 bytes，以原FFT函式重算目前16份陣列458832數值逐值相同，不執行原圖表寫入入口、不重做PSF擬合／V42推論。[完整版本判讀與執行方式](../../docs/reproducibility/optical_calibration/SPECTRA.md)。後續已實際下載固定GitHub來源，在原D／H研究位置不可讀的條件下重算同樣16份陣列458832數值完全相同；故意修改取回輸入則在寫出結果前正確停止。[GitHub取回收據](../../docs/reproducibility/optical_calibration/SPECTRUM_GITHUB_REPLAY_VERIFIED.json)。
