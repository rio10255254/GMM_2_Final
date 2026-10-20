# R94、R95、R97、R98：從 GitHub 理解、取回與重做

這四輪延續 R93 的保存標準：原設計、實際跑到哪裡、當年所有現存模型、完整數字、影像與失敗紀錄一起保存。2026-10-21 的事後審查不改寫歷史數字，也不替當年未完成的檢查補造結果。D 槽不清理，現行訓練與論文來源保留。

| 輪次 | 為什麼做這輪 | 實際完成與不能省略的歷史 |
|---|---|---|
| [R94](../../../Experiments/R94_EvidenceConditionalScratch/reports/R94_AUDIT.md) | 按雜訊、亮度、對比、邊界、紋理分工，另判斷是否需要且能夠修正 | 8 輪完整提交；第9輪算過但未提交即停止。保留原保護程式估算失敗與接近原圖的輸出 |
| [R95](../../../Experiments/R95_CounterfactualGateRepairScratch/reports/R95_AUDIT.md) | 修復清楚輸入、控制關閉與早期學習問題 | 48輪；首度從第8輪接續曾重建訓練更新狀態。四段表49列、第9輪有被取代舊列，原件全部留下 |
| [R97](../../../Experiments/R97_DirectCausalPhaseScratch/reports/R97_AUDIT.md) | 直接學實際修正，紋理保持原圖位置，加入相鄰週期辨識 | 48輪；正式第1輪後的檔案存取失敗恢復一次。開跑前顯示驅動事故另有原紀錄。後訓練固定48輪，不能看實拍後改挑模型 |
| [R98](../../../Experiments/R98_AggressiveTextureScratch/reports/R98_AUDIT.md) | 加強原圖可見紋理、固定補抽紋理場景、減少互相抵銷 | 48輪；舊報告停在預檢文字已補正。現存SEM及預覽全部保存，沒有把R97的整套後測冒稱也在R98完成 |

四輪共用相同固定合成來源，卻不是每一輪有相同模型、裁切或驗證範圍。R97／R98 最後的小面板裁切種子不同，不能從兩個最後分數直接判勝負。COMBO正式基準和論文採用維持原狀。

## 找模型、完整結果與原圖

- [R94完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r94-complete-record-20261021)：151個原位置、20個模型檔、51張影像。
- [R95完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r95-complete-record-20261021)：308個原位置、31個模型檔、148張影像。
- [R97完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r97-complete-record-20261021)：512個原位置、28個模型檔、396張影像，含301張完整實拍驗證重建與數表。
- [R98完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r98-complete-record-20261021)：121個原位置、28個模型檔、68張影像。

合計1,092個原位置、107個模型檔、663張影像。模型數包含早期測試與最後檔案別名，不能換算為107次獨立訓練。內容相同的檔案在附件中只存一次；每個原位置仍可完整恢復。各輪 `R##_RECORD_MANIFEST.json.gz` 和 [完整統計](RECORD_SUMMARIES.json) 列出每份內容核對碼。

[26張重要原比較圖](GALLERY.md)涵蓋相同四個實拍視野、合成清楚輸入、細節與位移、原驗證歷程及SEM不利結果，均未重編碼。實拍的差異放大圖不是SEM誤差；合成圖的RAW欄仍是模擬資料。

## 只想重算當年的數字

到[這次總入口](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-preservation-20261021)下載 `four-round-result-replay.zip`，解壓到一個新資料夾，不需要大型資料庫、模型或顯卡。用Python 3.11以上執行：

```powershell
python Tools/replay_four_round_results.py --output ../NEW_REPLAYED_RESULTS
```

重算包含四輪的完整提交歷程、R95被取代的第9輪、最後原表與執行摘要的核對、各軸曾觀察到的最佳值，以及R97實拍外觀、位移和六方法SEM完整摘要。最佳值只是歷程診斷，不會替原實驗重新挑選端點。SEM先在同一實體柱的12曝光內取中位數，再彙整36柱；不能把重複曝光當獨立樣本。

R98原SEM表另依同一方式重算並保留周長、圓度退步。[原數字重算參照](ORIGINAL_NUMERIC_REPLAY.json)。原表到新摘要的重算，不等同重新擬合全部輪廓或重新執行所有量測。

## 取回原程式與完整紀錄

總入口另有 `four-round-code-and-guide.zip`，包含這四輪的原程式、設計、測試、說明、恢復工具與圖冊；可先解壓到新的研究目錄。它避免為了這四輪先下載整個大型歷史倉庫。需要完整倉庫歷史者再使用固定標籤 `research-preservation-20261021`。

倉庫保持私人，須登入有權限的GitHub帳號。在解壓的程式目錄執行：

```powershell
$researchRoot = (Get-Location).Path
foreach ($round in @(94, 95, 97, 98)) {
    $assetFolder = "../R${round}_download"
    python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag "r${round}-complete-record-20261021" --output $assetFolder --workers 1
    python Tools/research_asset_bundle.py restore --manifest "$assetFolder/RESEARCH_ASSETS.json.gz" --assets $assetFolder --destination $researchRoot --keep-identical-existing
}
```

恢復工具先檢查現有檔案，只接受完全相同內容共存，遇到改動即停止，不覆蓋原件。各段附件都有GitHub伺服器與本地雙方核對碼，再核對解壓後每一份內容。

## 用原模型重做固定實拍輸出

測過的獨立CPU環境見 [環境紀錄](ENVIRONMENT_CPU_TESTED.txt)。實際取回的四輪原模型與原推論路徑，各測兩個端點與四個固定實拍輸入：R94為4／8輪、R95為40／48輪、R97與R98為44／48輪，共32組。兩端點不是新一輪模型選擇。

```powershell
python Tools/replay_four_round_models.py --output ../NEW_MODEL_REPLAY --reference docs/reproducibility/four_rounds/MODEL_REFERENCE.json --audit-all-checkpoints
```

比較完整小數輸出陣列及實際BMP檔案，而不是只比較縮圖。參照是原程式在CPU實跑的結果，當年的GPU監看圖保留為歷史，沒有冒稱其計算環境也逐位元相同。程式只做CPU推論，沒有重跑訓練。

## 共用訓練資料、必要來源與完整重跑的界限

R93固定合成庫已在[共用來源版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，共15,004檔、1,250場景／5,000觀測。內容識別為 `6494719ad21665723ba32cdcb3871a40691753ca03791f181416349f02fd31a5`，詳見[原共用庫說明](../r93_shared/README.md)。使用篩選下載可只取該庫：

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output ../R93_shared_download --prefix Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/ --workers 2
python Tools/research_asset_bundle.py restore --manifest ../R93_shared_download/RESEARCH_ASSETS.json.gz --assets ../R93_shared_download --destination . --prefix Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/ --keep-identical-existing
python Tools/verify_r93_shared_recovery.py --rounds 94 95 97 98 --report ../NEW_FOUR_READERS.json
```

每輪都檢查八種訓練角色與首、中、尾樣本的原生準備結果；R94只驗證實際走到的512／256階段，其他三輪用實際48輪的896／512階段。R97／R98額外程序週期樣本的原生成程式也在各輪training內；R98固定補抽紋理的原取樣規則保留。

[必要來源對照表](SOURCE_DEPENDENCIES.json)逐一把R97的301張實拍、12曝光成對光學圖及SEM原件／排列，對上已發布的原內容與GitHub附件。原歷史設定保留D／H位置作證據，不要求未來電腦也具備相同磁碟代號。

日後完整重訓要在新的工作目錄，將副本的 `data.source_package` 設為取回資料的位置，依各輪原啟動器與硬體重新檢查。原48輪／失敗／恢復歷程、權重、最後版本程式均已保存；R95較早程式版本目前只有內容核對碼，首次恢復也沒有繼承訓練更新狀態。這次沒有宣稱已從零重跑當年所有GPU訓練，或能保證不同硬體得到完全相同訓練權重。

## 本次實際核對收據

[2026-10-21驗證範圍與完成狀態](VERIFICATION_20261021.json)會分別列出完整檔案取回、模型／數字重算、共用資料讀取與舊研究位置不可讀的測試。沒有全部通過前不把這次保存標成完成。
