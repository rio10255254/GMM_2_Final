# R94、R95、R97、R98：從 GitHub 理解、取回與重做

這四輪延續 R93 的保存標準：原設計、實際跑到哪裡、當年所有現存模型、完整數字、影像與失敗紀錄一起保存。2026-10-21 的事後審查不改寫歷史數字，也不替當年未完成的檢查補造結果。D 槽不清理，現行訓練與論文來源保留。

首次使用，先從本次GitHub總入口下載 `four-round-code-and-guide.zip` 並解壓；後面的命令都在解壓目錄執行。完整附件下載需要已安裝且登入的GitHub CLI及requests；相機、模型與資料準備驗證需要下方獨立CPU環境。純數字小包則可單獨使用，不需要額外套件。

| 輪次 | 為什麼做這輪 | 實際完成與不能省略的歷史 |
|---|---|---|
| [R94](../../../Experiments/R94_EvidenceConditionalScratch/reports/R94_AUDIT.md) | 按雜訊、亮度、對比、邊界、紋理分工，另判斷是否需要且能夠修正 | 8 輪完整提交；第9輪算過但未提交即停止。保留原保護程式估算失敗與接近原圖的輸出 |
| [R95](../../../Experiments/R95_CounterfactualGateRepairScratch/reports/R95_AUDIT.md) | 修復清楚輸入、控制關閉與早期學習問題 | 48輪；首度從第8輪接續曾重建訓練更新狀態。四段表49列、第9輪有被取代舊列，原件全部留下 |
| [R97](../../../Experiments/R97_DirectCausalPhaseScratch/reports/R97_AUDIT.md) | 直接學實際修正，紋理保持原圖位置，加入相鄰週期辨識 | 48輪；正式第1輪後的檔案存取失敗恢復一次。開跑前顯示驅動事故另有原紀錄。後訓練固定48輪，不能看實拍後改挑模型 |
| [R98](../../../Experiments/R98_AggressiveTextureScratch/reports/R98_AUDIT.md) | 加強原圖可見紋理、固定補抽紋理場景、減少互相抵銷 | 48輪；舊報告停在預檢文字已補正。現存SEM及預覽全部保存，沒有把R97的整套後測冒稱也在R98完成 |

四輪共用相同固定合成來源，卻不是每一輪有相同模型、裁切或驗證範圍。R97／R98 最後的小面板裁切種子不同，不能從兩個最後分數直接判勝負。COMBO正式基準和論文採用維持原狀。

四個固定實拍視野曾反覆供開發觀察，R98的方法調整也參考過R97在這些圖上的表現。沒有拿它們當訓練答案，不代表它們是全新的獨立測試。本次重做證明原輸入與模型結果可取回、可重現，沒有把這四圖改稱獨立泛化證據。

## 找模型、完整結果與原圖

- [R94完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r94-complete-record-20261021)：151個原位置、20個模型檔、51張影像。
- [R95完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r95-complete-record-20261021)：308個原位置、31個模型檔、148張影像。
- [R97完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r97-complete-record-20261021)：512個原位置、28個模型檔、396張影像，含301張完整實拍驗證重建與數表。
- [R98完整紀錄](https://github.com/rio10255254/GMM_2_Final/releases/tag/r98-complete-record-20261021)：121個原位置、28個模型檔、68張影像。

合計1,092個原位置、107個模型檔、663張影像。模型數包含早期測試與最後檔案別名，不能換算為107次獨立訓練。內容相同的檔案在附件中只存一次；每個原位置仍可完整恢復。各輪 `R##_RECORD_MANIFEST.json.gz` 和 [完整統計](RECORD_SUMMARIES.json) 列出每份內容核對碼。

[26張重要原比較圖](GALLERY.md)涵蓋相同四個實拍視野、合成清楚輸入、細節與位移、原驗證歷程及SEM不利結果，均未重編碼。實拍的差異放大圖不是SEM誤差；合成圖的RAW欄仍是模擬資料。

## 四張預覽確實來自相機原件

這次另外逐像素找回四張預覽的完整相機來源：5倍與20倍取自既存多倍率連拍原件、50倍陣列取自既存短步距連拍原件，九宮格來自原檔名與既有裁切紀錄均標示2026-06-18的實拍。原位置與完整檔名列在來源表，不把分析目錄日期冒認為拍攝日期。四輪的16份預覽都能由原相機圖按固定位置直接裁切，連BMP檔案內容都完全相同，沒有經過模型重建。

其中6月18日完整相機圖未在先前GitHub保存清單，本次已補上。四份完整相機原件另放在小型[預覽相機原件版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/four-round-preview-origins-20261021)，不必為這四個視野先下載整個大型圖庫。[逐張來源、裁切位置與核對碼](PREVIEW_CAMERA_ORIGINS.json)。

九宮格的歷史檔名含center9，原裁切程式卻明列柱號22、23、24、28、29、30、34、35、36；位置應按裁切座標與柱號查閱，不能只憑檔名認定中央。本次只驗證相機／裁切內容，沒有替歷史SEM對應重新背書。

```powershell
.venv/Scripts/python.exe Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag four-round-preview-origins-20261021 --output ../preview_camera_download --workers 1
.venv/Scripts/python.exe Tools/research_asset_bundle.py restore --manifest ../preview_camera_download/RESEARCH_ASSETS.json.gz --assets ../preview_camera_download --destination . --keep-identical-existing
.venv/Scripts/python.exe Tools/verify_four_round_camera_origins.py --report ../NEW_CAMERA_CROPS_VERIFIED.json
```

上述裁切核對須同時取回各輪完整紀錄中的預覽檔。它只核對原圖與裁切，不會修改論文原件。

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
    .venv/Scripts/python.exe Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag "r${round}-complete-record-20261021" --output $assetFolder --workers 1
    .venv/Scripts/python.exe Tools/research_asset_bundle.py restore --manifest "$assetFolder/RESEARCH_ASSETS.json.gz" --assets $assetFolder --destination $researchRoot --keep-identical-existing
}
```

恢復工具先檢查現有檔案，只接受完全相同內容共存，遇到改動即停止，不覆蓋原件。各段附件都有GitHub伺服器與本地雙方核對碼，再核對解壓後每一份內容。

## 用原模型重做固定實拍輸出

測過的獨立CPU環境見 [環境紀錄](ENVIRONMENT_CPU_TESTED.txt)。實際取回的四輪原模型與原推論路徑，各測兩個端點與四個固定實拍輸入：R94為4／8輪、R95為40／48輪、R97與R98為44／48輪，共32組。兩端點不是新一輪模型選擇。

Windows、Python3.12的實測安裝方式如下；使用新的環境，與其他訓練環境分開。OpenCV採不額外改動NumPy版本的安裝方式，這個組合已實際運行：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python.exe -m pip install --no-deps numpy==1.26.4 scipy==1.13.1 opencv-python-headless==4.12.0.88
.venv/Scripts/python.exe -m pip install requests==2.32.3
```

本文下載、相機、模型與資料準備命令均使用 `.venv/Scripts/python.exe`。請先建立此環境再執行；純數字重算仍可直接使用既有Python。

```powershell
.venv/Scripts/python.exe Tools/replay_four_round_models.py --output ../NEW_MODEL_REPLAY --reference docs/reproducibility/four_rounds/MODEL_REFERENCE.json --audit-all-checkpoints
```

比較完整小數輸出陣列及實際BMP檔案，而不是只比較縮圖。參照是原程式在CPU實跑的結果，當年的GPU監看圖保留為歷史，沒有冒稱其計算環境也逐位元相同。程式只做CPU推論，沒有重跑訓練。

## 共用訓練資料、必要來源與完整重跑的界限

R93固定合成庫已在[共用來源版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，共15,004檔、1,250場景／5,000觀測。內容識別為 `6494719ad21665723ba32cdcb3871a40691753ca03791f181416349f02fd31a5`，詳見[原共用庫說明](../r93_shared/README.md)。使用篩選下載可只取該庫：

```powershell
.venv/Scripts/python.exe Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output ../R93_shared_download --prefix Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/ --workers 2
.venv/Scripts/python.exe Tools/research_asset_bundle.py restore --manifest ../R93_shared_download/RESEARCH_ASSETS.json.gz --assets ../R93_shared_download --destination . --prefix Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/ --keep-identical-existing
.venv/Scripts/python.exe Tools/verify_r93_shared_recovery.py --rounds 94 95 97 98 --report ../NEW_FOUR_READERS.json
```

每輪都檢查八種訓練角色與首、中、尾樣本的原生準備結果；R94只驗證實際走到的512／256階段，其他三輪用實際48輪的896／512階段。R97／R98額外程序週期樣本的原生成程式也在各輪training內；R98固定補抽紋理的原取樣規則保留。

另外重做原程式即時生成的週期樣本，以及R98在1／17／48輪的16批補抽序列，可執行：

補抽使用原表實際記錄的6／2／1場景批量，不把設計候選值當作真正執行量。

```powershell
.venv/Scripts/python.exe Tools/verify_four_round_procedural_sources.py --output ../NEW_PROCEDURAL_REPLAY --reference docs/reproducibility/four_rounds/PROCEDURAL_REFERENCE.json
```

[必要來源對照表](SOURCE_DEPENDENCIES.json)逐一把R97的301張實拍、12曝光成對光學圖及SEM原件／排列，對上已發布的原內容與GitHub附件。原歷史設定保留D／H位置作證據，不要求未來電腦也具備相同磁碟代號。

日後完整重訓要建立新的工作目錄，只複製各輪的config、model、training、inference、scripts、tests與固定預覽輸入；歷史runs、weights、logs、results保留在原恢復目錄，避免把舊結案登錄當成新訓練。將新副本的 `data.source_package` 設為取回資料的位置，指定自己的Python環境並依原校準程式重新檢查硬體，再依原啟動器執行。這套新訓練步驟本次沒有實際開跑。

原48輪／失敗／恢復歷程、權重、最後版本程式均已保存；R95較早程式版本目前只有內容核對碼，首次恢復也沒有繼承訓練更新狀態。這次沒有宣稱已從零重跑當年所有GPU訓練，或能保證不同硬體得到完全相同訓練權重。

2026-10-22已補回原先缺少的22版程式／設定，完整內容皆符合當年記錄；[逐版可得性](HISTORICAL_SOURCE_AVAILABILITY.json)及[受影響階段與接續限制](RECOVERY_IMPACT_20261022.md)分開說明。[正式程式核對](SOURCE_HASH_AUDIT.json)則證明本次實跑的模型定義、最後訓練程式及原設計12項均符合當年的原紀錄；兩種範圍分開交代。

## 本次實際核對收據

[2026-10-21驗證範圍與完成狀態](VERIFICATION_20261021.json)已分別列出完整檔案取回、模型／數字重算、共用資料讀取與舊研究位置不可讀的測試。沒有全部通過前不把這次保存標成完成。

本次上述核對已全部通過：1,092個原位置、107個模型檔、663張可讀影像；8個正式端點×4輸入的32組完整輸出相同。共用15,004檔重新還原核對，四輪36個準備樣本、8批程序週期樣本與3個補抽排程相同。數字小包實際從GitHub另址執行，包含R94最後完整8輪的驗證量。原D／H研究來源被拒讀的反例也實際通過。

另補4份完整相機原件，包含先前漏存的6月18日原圖；從GitHub取回後，四輪16份固定預覽均能由原相機圖裁切成完全相同的檔案。
