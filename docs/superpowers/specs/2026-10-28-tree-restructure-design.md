# 檔案樹重整與交機設計（2026-10-28）

## 要解決什麼

這次要做到兩件事，第二件是後來才確定的前提，影響了整份設計：

1. **檔案樹本身的邏輯要清楚。** 要找某一輪的報告、某張重建圖、某個模型的程式，靠的是結構合理，而不是靠入口頁或捷徑。
2. **GitHub 要能自給自足。** 這台電腦之後要交給別人，D、H 兩顆硬碟都會跟著走。之後 GitHub 上的程式庫加上 Release，就是這個專案唯一完整的家。任何人只要有 GitHub 權限，就要能找到、讀懂、取回這些東西，不需要這台電腦。

現在亂的根源不是根目錄東西多，而是同一種角色被放在好幾個地方：

- 實驗分散三處：主線 R26–R153 在 `Experiments/`，R1–R32 在 `Traing_Progress/organized_*`，Lab 系統的各輪藏在 `Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/`。
- 交付包分散三處：`Deliverables/`、`_deployment_package/`、`Validations/`，Lab 的 `Model_Packages/` 又是第四處。
- 封存分散七處：`Historical_Archive/`、`Project_Archive/`、`Trash_Archive/`、`_MOSR_Project_Archive_20260624/`、`.history/`、`_portable_env_sim_20260318/`，以及論文區裡那個中止的資料夾。
- 跨輪次的實拍分析散在根目錄：`Step_analysis_20260623/`、`20260702_100MG_…`、`20260704_20x_5x_…`、`Reconstruct_Progress/`、`AnalysisLab/`。
- `Thesis_MOSR_Evidence/` 裡除了論文證據，還裝著一整套 Lab 研究系統。
- 有些原拍只存在 Release 裡（`Step/`、`20260704_20x/`、`20260704_5x/`、`20260702_100MG_位移_50x/`、`20260924/`、公司的 NTU 序列），在 git 的檔案樹上完全看不到。

交機這個前提另外帶出一個問題：**程式綁死在這台電腦上。** 可執行的程式和設定檔裡，寫死 `D:\GMM_2_Final` 的有 3,354 個檔、程式碼 2,379 行。另外還有指向專案外部資料夾的（`D:\NTU_ImageDataset`、下載資料夾、`D:\NonSystemFiles\GMM2`、`H:\From_2TB_D_disk`、已經不在的 E 槽），以及寫死 `C:\Users\Rio\anaconda3` 直譯器的 111 行。換一台電腦，這些全部失效。

## 已經完成的部分：交機前的盤點（2026-10-28）

這一段是設計的前提，不是待辦。

**盤點方法。** 掃描 D 槽專案、H 槽封存區、C 槽那個 R152 獨立工作區，以及程式引用到的四處外部資料夾，掃描時跳過所有目錄連結。每個檔用內容雜湊比對 GitHub 程式庫和全部 Release，分成「在雲端」和「只在本機」。

**結果。** 規則上必須保存的都已經在雲端：

- 所有原拍：930 張 PI 重拍、Step、20x／5x、100MG 50 倍、PSF100、0615、0924 的 25 張 PSF、NTU 六組序列、SEM 原圖。
- 政策檔點名的 39 個正式模型，以及每一輪選用的模型。

只在本機的，D 槽專案約 369 GB、H 槽封存區約 953 GB。內容是中途存檔、重建輸出、生成的訓練資料，以及各輪的完整歷史，依 2026-10-21 定的保存原則不上傳。

**當天補上的：**

- [PR #54](https://github.com/rio10255254/GMM_2_Final/pull/54)：R152 IMPACT 2026 驗證原本只在 C 槽的獨立工作區，已收進 `Experiments/R152_IMPACT2026Validation/`。
- 三個新 Release，全部從 GitHub 取回、逐檔重算雜湊後才發布：
  - `r152-impact2026-reconstructions-20261028`：R152 的重建陣列。
  - `research-psf100-chessboard-20261028`：393 張同日棋盤原拍。
  - `research-ntu-gmf-and-crops-20261028`：R61 v16 的外部 GMF 量測包和裁切輸入。量測軟體已經不在，這些分數無法重量。
- 救援分支：`rescue/local-leftovers-20261028` 放 4 個只在本機的草稿；`rescue/stash-temp-domain-doc-reflow-20260324` 放 3 月那筆 stash。

**刻意留在本機、由專案擁有者自行帶走的：**

- `H:\From_2TB_D_disk`：GMM 之前的研究。GMM 用到的 SEM 原圖和 ch4 程式已在雲端。
- `D:\NonSystemFiles\GMM2` 裡專案沒用到的 2025 年拍攝。
- 上述 369 GB 和 953 GB 的中途產物。

這些只要複製到外接硬碟，不進 GitHub。

**已知、無法補的缺口：**

- E 槽已經不在。外部 GMF 量測軟體 `GmmVisionToolExe` 原本在那裡，所以外部 GMF 量測無法重做，只能讀已保存的分數。
- R63 的一個原選用模型（第 24 輪版本），之前已經記錄為缺件。

## 原則

1. **一種角色一個家。** 實驗、Lab 系統、跨輪分析、原始來源、訓練資料、程式、論文、交付、文件、封存，各有一個頂層位置。
2. **已經在對的家裡的東西不動，也不改名。** 只搬放錯家的東西。主線 R26–R153 留在 `Experiments/R##_…` 原位。理由是量出來的：文件裡指向 `Experiments/` 的引用約 1 萬 7 千處，1,454 個腳本用 `Path(__file__).parents[N]` 往上找根目錄。把主線各輪往下多塞一層，這兩大塊要全部改，得到的只是「看起來更對稱」。
3. **單位名稱永遠不改，只換容器。** 一輪實驗、一個交付包、一個分析、一個舊批次、一次訓練紀錄，資料夾名稱照舊。舊名稱在任何文件、對話、論文筆記裡都還搜得到。
4. **整棵樹套用同一個轉換，轉換後的樹自己就是一致的。** 程式、設定、文件、結果表、清單、收據，只要指向被搬動的檔，不管寫的是路徑還是雜湊，一律跟著更新。專案裡不留任何翻譯層、對照工具或人工例外清單；工具和讀者看到的路徑都是真的路徑。
5. **轉換前的原貌由標籤保存。** 重整前在 `main` 打永久標籤，舊樹的每個位元都在。「當年這份紀錄原本寫什麼」去標籤上看；現行的樹只負責正確、能用。
6. **程式不綁在這台電腦上。** 指向專案內部的路徑一律相對於專案根目錄。程式從自己的位置找到根目錄，不寫死磁碟代號。指向專案外部、但內容已在雲端的檔案，改成它從 Release 取回後在專案裡的位置。
7. **雲端的東西在樹上看得到。** 只存在 Release 裡的資料，在它恢復後所在的資料夾留一份 README，寫明裡面是什麼、在哪個 Release、怎麼取回。`Shared_Sources/NTU_Originals/README.md` 就是這個做法的第一份。

## 目標結構

```
README.md  PROJECT_STATE.md  PROJECT_ARCHITECTURE.md  ESTIMATOR_POLICY.json
AGENTS.md  CLAUDE.md  CONTRIBUTING.md  REPO_GOVERNANCE.md  RECON_GALLERY.md
.github/  .gitignore  .gitattributes

Experiments/            主專案（公司光學系統）的所有實驗
  R26NewPSFCheck/ … R153_MeanExternalBenchmark/   原位不動（含 2026-10-28 收進來的 R152_IMPACT2026Validation）
  Legacy/               R1–R32 的十個舊批次（原 Traing_Progress/organized_*）
  Training_Runs/        共用訓練器直接輸出、沒歸入批次的訓練紀錄（原 Traing_Progress/training_progress_*）

LabSystem_MOSR/         實驗室成像系統的完整工作區：自己的校正、資料、訓練、各輪實驗
                        （原 Thesis_MOSR_Evidence/LabSystem_MOSR，原有內部結構不變）
  control_program_recordings_20260924/  新控制程式的效果錄影（在 Release，留 README）

Analyses/               不屬於單一輪次的實拍分析與共享重建
  Step_analysis_20260623/  20260702_100MG_displacement_analysis/
  20260702_100MG_phase_dft_analysis_matlab/  20260704_20x_5x_analysis/
  Reconstruct_Progress/  AnalysisLab/

Shared_Sources/         不能重來的原拍、量測、SEM、PSF 取像
  Real_Sample_Captures/  Step/、20260702_100MG_位移_50x/、20260704_20x/、20260704_5x/（影像在 Release，各留 README）
  PSF_Camera_Acquisitions/20260924/  中央九點 PSF 的 25 張原拍（影像在 Release，留 README）
  NTU_Originals/        公司六組圓環序列（2026-10-28 已建，影像在 Release）
  （其餘子資料夾原位不動）

Training_Data/          共用訓練資料與生成程式（不動）
Model/                  GeoEdgeAlignSR 共用模型程式（不動，扁平結構照舊）
PSF_Fitting/            主專案光學擬合（不動）
Tools/                  專案工具（不動）

Thesis_MOSR_Evidence/   只剩論文證據：論文圖、數據報告、模型比較、消融、外部 GMF 包、編輯紀錄

Deliverables/
  Company_Packages/     給公司端的 ONNX 與正式交付版
  Thesis_Handoffs/      論文交接與網頁文件包
  Standalone_Models/    可獨立訓練／重建的模型包
  Data_Regenerators/    訓練資料重建包
  Validations/          各交付包當時的核對紀錄

docs/                   不動
Archive/                所有「本身就是為了封存而建立」的資料夾
```

頂層資料夾從 24 個變成 12 個（不含 `.github`）。

找東西的方式會變成：

| 要找 | 去哪 |
|---|---|
| 主線某一輪的報告、腳本、結果圖 | `Experiments/R143_…/reports/`、`scripts/`、`results/` |
| R1–R32 的某一輪 | `Experiments/Legacy/organized_YYYYMMDD/roundNN/`（哪輪在哪批見逐號表） |
| COMBO 或 R39 用的那次訓練紀錄 | `Experiments/Training_Runs/training_progress_…/` |
| Lab R47 | `LabSystem_MOSR/Experiments/R47_…/` |
| 實驗室系統新控制程式的錄影 | `LabSystem_MOSR/control_program_recordings_20260924/` |
| 100MG 樣品的位移分析 | `Analyses/20260702_100MG_displacement_analysis/` |
| Step 樣品的原拍 | `Shared_Sources/Real_Sample_Captures/Step/`：README 說明在哪個 Release、怎麼取回 |
| 公司的位移序列與外部 GMF 分數 | `Shared_Sources/NTU_Originals/` |
| 共用模型程式 | `Model/` |
| 某輪自己的模型架構（例如 R139 U-Net） | 該輪 `scripts/` |
| 給公司的 ONNX | `Deliverables/Company_Packages/` |
| 論文圖 | `Thesis_MOSR_Evidence/Final_Data_Figures/` |

## 完整搬移對照表

這張表就是搬移規則，轉換工具照它執行。多條規則同時符合時，以最長的前綴為準。搬完之後這張表只留在操作紀錄裡，樹的正確性不靠它。

表中標「Release」的項目，git 裡沒有內容。搬的是它在 Release 清單裡記的恢復路徑，以及樹上那份 README（見「雲端」）。

| 舊位置 | 新位置 | 階段 |
|---|---|---|
| `Historical_Archive/` | `Archive/Historical_Archive/` | 2 |
| `Project_Archive/` | `Archive/Project_Archive/` | 2 |
| `Trash_Archive/` | `Archive/Trash_Archive/` | 2 |
| `_MOSR_Project_Archive_20260624/` | `Archive/_MOSR_Project_Archive_20260624/` | 2 |
| `.history/` | `Archive/.history/` | 2 |
| `_portable_env_sim_20260318/` | `Archive/_portable_env_sim_20260318/` | 2 |
| `Thesis_MOSR_Evidence/Research_Round_Library_20260926_ABORTED_OVERSIZED/` | `Archive/Research_Round_Library_20260926_ABORTED_OVERSIZED/` | 2 |
| `_deployment_package/GeoEdge_COMBO_ONNX_Company_Package_20260424/` | `Deliverables/Company_Packages/GeoEdge_COMBO_ONNX_Company_Package_20260424/` | 2 |
| `_deployment_package/GeoEdge_R26_正式交付版/` | `Deliverables/Company_Packages/GeoEdge_R26_正式交付版/` | 2 |
| `_deployment_package/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/` | `Deliverables/Company_Packages/GeoEdge_R39R40_a025_ONNX_Company_Package_20260511/` | 2 |
| `_deployment_package/`（其餘根層檔） | `Deliverables/Company_Packages/` | 2 |
| `Deliverables/MOSR_ONNX/` | `Deliverables/Company_Packages/MOSR_ONNX/` | 2 |
| `Deliverables/MOSR_R61_ONNX/` | `Deliverables/Company_Packages/MOSR_R61_ONNX/` | 2 |
| `Deliverables/R128_Corrected_Corner9_Thesis_Handoff_20260920/` | `Deliverables/Thesis_Handoffs/…`（同名） | 2 |
| `Deliverables/R129_Corrected_Corner9_Thesis_Handoff_20260920/` | `Deliverables/Thesis_Handoffs/…` | 2 |
| `Deliverables/R129_Thesis_Rewrite_Ready_20260920/` | `Deliverables/Thesis_Handoffs/…` | 2 |
| `Deliverables/R129_Web_Thesis_Documents_20260920/` | `Deliverables/Thesis_Handoffs/…` | 2 |
| `Deliverables/R130_Clean_Corrected_Corner9_Validation_Handoff_20260920/` | `Deliverables/Thesis_Handoffs/…` | 2 |
| `Deliverables/R130_Clean_Web_Thesis_Documents_20260920/` | `Deliverables/Thesis_Handoffs/…` | 2 |
| `Deliverables/R137_WeakPSF_Web_Documents_20260922/` | `Deliverables/Thesis_Handoffs/…` | 2 |
| `Deliverables/R137_PSF100_Model_Copy_20260923/` | `Deliverables/Standalone_Models/…` | 2 |
| `Deliverables/R137_PSF100_V42_Select8_20260923/` | `Deliverables/Standalone_Models/…` | 2 |
| `Deliverables/R152_Standalone_20261004/` | `Deliverables/Standalone_Models/…` | 2 |
| `Deliverables/R152_Standalone_ImageFiles_20261004/` | `Deliverables/Standalone_Models/…` | 2 |
| `Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/<五個包>/` | `Deliverables/Standalone_Models/<同名>/` | 2 |
| `Deliverables/R61_TrainingData_Regenerator_20261004/` | `Deliverables/Data_Regenerators/R61_TrainingData_Regenerator_20261004/` | 2 |
| `Validations/` | `Deliverables/Validations/` | 2 |
| `trial_README.md` | `Experiments/R128_SourceOnlyFullTraining/trial/trial_README.md` | 2 |
| `Step_analysis_20260623/` | `Analyses/Step_analysis_20260623/` | 3 |
| `20260702_100MG_displacement_analysis/` | `Analyses/20260702_100MG_displacement_analysis/` | 3 |
| `20260702_100MG_phase_dft_analysis_matlab/` | `Analyses/20260702_100MG_phase_dft_analysis_matlab/`（10 張只在本機的分析圖、6 MB，一併放進 git） | 3 |
| `20260704_20x_5x_analysis/` | `Analyses/20260704_20x_5x_analysis/` | 3 |
| `Reconstruct_Progress/` | `Analyses/Reconstruct_Progress/` | 3 |
| `AnalysisLab/` | `Analyses/AnalysisLab/` | 3 |
| `Step/`（Release） | `Shared_Sources/Real_Sample_Captures/Step/` | 3 |
| `20260702_100MG_位移_50x/`（Release） | `Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x/` | 3 |
| `20260704_20x/`（Release） | `Shared_Sources/Real_Sample_Captures/20260704_20x/` | 3 |
| `20260704_5x/`（Release） | `Shared_Sources/Real_Sample_Captures/20260704_5x/` | 3 |
| `20260924/`（Release） | `Shared_Sources/PSF_Camera_Acquisitions/20260924/` | 3 |
| `_build153/` | `Experiments/R153_MeanExternalBenchmark/_build153/` | 3 |
| `Traing_Progress/organized_*/` | `Experiments/Legacy/organized_*/` | 4 |
| `Traing_Progress/training_progress_*/` | `Experiments/Training_Runs/training_progress_*/` | 4 |
| `Traing_Progress/`（其餘：README、ARCHIVE_POINTER 等） | `Experiments/Legacy/` | 4 |
| `Thesis_MOSR_Evidence/LabSystem_MOSR/` | `LabSystem_MOSR/` | 4 |
| 根目錄 3 支 2026-09-24 錄影（只在本機） | `LabSystem_MOSR/control_program_recordings_20260924/`，檔名不改，上傳 Release | 4（LabSystem 上移之後，這樣上傳時記的就是最終路徑，之後不用再換清單） |

各組的判斷依據：

- **Company_Packages**：README 寫明是給公司端測試或給均華用的包，包括 COMBO 和 R39R40 a025 的 ONNX、R26 正式交付版、R79 的 `MOSR_ONNX`、R61 的 `MOSR_R61_ONNX`。
- **Thesis_Handoffs**：名稱帶 `Thesis_Handoff`、`Thesis_Rewrite`、`Web_*_Documents` 的論文交接包。
- **Standalone_Models**：README 寫明可獨立訓練或重建的模型包，含 Lab 那五個（R129、R134、R61 STEP、兩個 V42）。它們雖然是 Lab 區產生的，但角色是交付包，不是 Lab 的工作資料。
- **Data_Regenerators**：目前只有 R61 v16 的訓練資料重建包。

## 刻意不動的東西

- **主線各輪 `Experiments/R##_…`**：理由見原則 2。代價是 GitHub 按字母排序時，`R100` 會排在 `R26` 前面。這個問題現在就存在；如果補零改名，會動到 122 個單位名稱，不值得。
- **`Training_Data/`、`Shared_Sources/` 不合併成一個 `Data/`**：兩者角色不同，一個是可重新生成的訓練資料，一個是不能重來的原始來源。合併只會多一層，還要改約 1,300 處引用。
- **`Model/`、`PSF_Fitting/`、`Tools/` 不收進 `Code/`**：`PSF_Fitting` 不只是程式，還有擬合輸出、教學版、驗證和快速校正研究。三者本來就各自是一個家。
- **`Thesis_MOSR_Evidence/` 不改名，內部也不再分組**：搬走 Lab 和中止的資料夾後，剩下約 20 個項目，都是論文用途。再分組要改 151 個腳本裡往上爬的層數，收益不大。`Thesis_MOSR_Evidence/Archive/` 只裝被取代的論文圖，跟著論文圖留著。
- **`LabSystem_MOSR` 內部結構**：它本來就是一個自成一體的工作區，裡面有自己的 `Experiments/`、`Training_Data/`、`psf_calibration/`、`Traing_Progress/`。拆散它反而要改內部互相引用的路徑。整包上移一層，內部的相對關係完全不變。唯一新增的是錄影資料夾，只放一份 README。
- **`docs/`**：內部結構不動。

## 路徑與雜湊怎麼改

### 判斷依據是「解析到哪裡」，不是字面

一個字串要不要改，看的是它在舊樹上實際指到哪裡，而不是字面上有沒有出現舊名字，因為同一個名字不一定指同一個地方。例如 R26 正式交付包裡的 `'/app/Traing_Progress'`、`'../Reconstruct_Progress'`，指的是交付包自己內部的資料夾；V42 獨立包的 `train_v42.py` 裡的 `"Traing_Progress"`，也是包內的資料夾。照字面改會把包弄壞。所以改寫工具會先把每個路徑在舊樹上解析出來，只有解析結果落在被搬動的位置時才改。

解析時會跟進目錄連結。例如下載資料夾裡的 `20260902_100MF_uncertainty\20260903` 是一個連結，指向專案的 `Shared_Sources/PI_Repeatability_20260903/raw`。所以寫成下載資料夾路徑的引用（程式碼約 580 行），實際指的是專案內部，改成專案內的相對路徑。

### 範圍：整棵樹，一視同仁

所有追蹤中的文字檔都在範圍內：程式、設定、文件、結果表、清單、收據、紀錄檔，以及 `.gz` 壓縮的 JSON（解開、改、再壓回去）。`Deliverables/` 和 `Archive/` 裡指向專案路徑的部分也包括在內。Release 的資產清單也套用同一個轉換，見「雲端」。

2026-10-28 在 `main`（48dd2ca9a）用分析程式實測，追蹤中的檔案裡：

| 種類 | 規模 | 怎麼改 |
|---|---|---|
| 文件裡的路徑字樣與連結 | 約 1 萬 2 千處 | 解析成舊位置 → 換成新位置 → 從檔案的新位置重算相對路徑 |
| 結果表、清單、紀錄裡寫明的完整路徑 | 約 15 萬處 | 都是寫明的完整路徑，直接換前綴 |
| Python 裡能靜態算出結果的路徑式（含 `__file__` 往上爬層數、`ROOT / "x" / "y"`、`os.path.join`） | 約 8,000 處 | 用 `ast` 在舊樹上算出位置，換成新位置後，寫回各段字串或層數 |
| Python 裡靜態算不出來的 | 約 40 處 | 人工在程式裡改好 |
| MATLAB、PowerShell、批次檔 | 約 260 處，另有 12 個會搬動的檔用 `..` 往上爬 | 一樣先解析再改；`fullfile('D:','GMM_2_Final',…)` 這類分段寫法也算得出來 |

需要人工處理的那約 40 處，大多是同一行訓練程式的多份副本：`os.path.join(PROJECT_ROOT, "Traing_Progress")`。它出現在 `Model/` 的訓練器，也出現在 R75、R79、R83 的 `training/runtime/` 副本，以及 `docs/history/TRAINING_LOG_WRITERS_20261021/`。每一份都要看它的 `PROJECT_ROOT` 是專案根目錄還是某個包的根目錄，再決定改不改。另外還有幾種：

- `PROJECT_ROOT / "Traing_Progress" / name` 這種後面接變數的寫法，共 4 處。要看 `name` 實際是批次名還是訓練紀錄名，才知道該去 `Legacy` 還是 `Training_Runs`。
- `Tools/` 裡有幾支保存工具，把資料夾名稱寫成清單常數（例如 `.history`、`_build153`），要直接改成新位置。

這些都直接改在程式裡，改完不留任何例外清單。

靜態分析看不到的，主要是執行時才從設定檔讀進來的路徑。但那些設定檔本身也在轉換範圍內，會一起被改到。真正會漏網的，只剩「在執行時才把路徑片段拼起來」的寫法，這次掃描沒有發現。

`"Traing_Progress"` 後面接 `organized_*`、`auto_tune_reports` 的，去 `Experiments/Legacy/`；接 `training_progress_*` 的，去 `Experiments/Training_Runs/`。`Model/` 訓練器之後產生的新訓練紀錄，預設寫到 `Experiments/Training_Runs/`。

Markdown 只改連結目標和路徑字樣，不改敘述文字。敘述裡提到舊名稱（例如「原名 `Traing_Progress`，歷史拼字」）是在講歷史，不是路徑，保留。原始報告因此不再逐位元等於當年版本，這是專案擁有者 2026-10-28 同意的取捨，原貌由標籤保存。

### 絕對路徑與外部路徑（原則 6）

同一個轉換，再多處理三種寫法：

| 寫法 | 規模（可執行檔） | 改成 |
|---|---|---|
| `D:\GMM_2_Final\…`、`D:/GMM_2_Final/…`、JSON 裡的 `D:\\GMM_2_Final\\…` | 程式碼 2,379 行，連設定共 3,354 個檔 | 程式裡：從專案根目錄算出的路徑，根目錄由程式自己的位置求得（`Path(__file__).resolve().parents[N]`，MATLAB 用 `mfilename('fullpath')`，PowerShell 用 `$PSScriptRoot`）。設定和紀錄裡：存成相對於專案根目錄的路徑 |
| 指向專案外、內容已在雲端的檔案（`D:\NTU_ImageDataset`、下載資料夾、`D:\NonSystemFiles\GMM2` 裡的 PSF100 挑圖來源、`H:\From_2TB_D_disk\13_thesis\SEM_data`） | 約 1,200 行 | 它從 Release 取回後在專案裡的位置，例如 `Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw/…`。對應關係用內容雜湊判斷：在這台電腦上讀出原檔、算雜湊、到雲端索引查它的恢復路徑。名稱相同不算數 |
| `C:\Users\Rio\anaconda3\python.exe` 這類直譯器路徑 | 111 行 | 程式和腳本裡改成 `python`。文件敘述裡記的「當時用哪個環境」照留 |

有三點要先講清楚：

- **讀取這些值的程式要跟著改。** 紀錄裡的路徑從絕對變成相對之後，讀它的程式必須用專案根目錄去接，而不是用執行時所在的目錄去接。改寫工具會找出讀這些欄位的程式，一起改掉。路徑等價檢查（見「驗證」）會核對改完之後解析到的位置不變。
- **內容不在雲端的外部路徑不改。** 例如 E 槽、`D:\NonSystemFiles\GMM2` 裡沒保存的拍攝、各輪只在本機的中途產物，這些路徑照實留著，因為它們誠實記錄了「當時那個檔在那裡」。用到它們的程式交機後會讀不到，這是保存原則的結果，不是轉換的錯誤。交機檢查會列出這些位置，連同數量寫進操作紀錄。
- **對應關係必須在交機前算完。** 判斷外部檔案的內容是否在雲端，需要讀這台電腦上的原檔。電腦交出去之後就無法再算了。

### 雜湊跟著路徑一起更新

實測有 143 份紀錄檔記下了 1,616 個「會被改寫的文字檔」的 sha256，共 6,438 處。大宗是 `docs/reproducibility/` 裡的清單，例如 `REPOSITORY_FILES.json.gz`、`CURATED_FILE_MAP.json.gz`、`SOURCE_AVAILABILITY.json.gz`。也有用雜湊來保護來源的設定，例如 R135 的 `config/dependencies.json`、R138 的 `config/protected_sources.json`：如果不更新，重跑時程式會以為來源被竄改，拒絕執行。

做法是把雜湊當成另一種引用：

- 檔案 F 被改寫後，舊雜湊 H 變成新雜湊 H′。樹裡每一處記著 H 的地方都換成 H′。
- 同一筆紀錄裡的大小欄位（`bytes`、`size`）也一起更新。
- 紀錄檔被這樣更新後，它自己的雜湊也會變。工具重複這個過程，直到沒有任何雜湊再變動為止。
- 只換「完全等於某個被改寫檔案舊雜湊」的值。圖檔、權重、資料陣列這些二進位檔內容不變，雜湊也不變。
- git 的 commit 編號和 blob 編號指的是 git 歷史裡仍然存在的物件，不受影響，不改。

### 原貌保存

- 第一個會改內容的 PR 合併之前，在當時的 `main` 打永久標籤 `pre-restructure-20261028` 並推上 GitHub。目前 `main` 是 06c32e461，比原本計畫的 48dd2ca9a 多了 PR #54。要看任何檔案、任何紀錄轉換前的原貌，網址是 `https://github.com/rio10255254/GMM_2_Final/tree/pre-restructure-20261028/<舊路徑>`。
- 這次操作本身寫一份紀錄 `docs/operations/TREE_RESTRUCTURE_20261028.md`，記下搬了什麼、為什麼、上面那張搬移對照表，以及交機時留下的外部路徑。它和 `LOCAL_CLEANUP_20261026.md` 一樣是操作紀錄：沒有任何工具讀它，樹的正確性也不靠它。
- 個別檔案的搬動，git 自己會偵測改名（`git log --follow`）。

### 雲端

雲端是交機後唯一的家，所以 Release 的資產清單必須和樹一致，這一步是必要的。

每個 Release 裡有兩種東西。一種是資料本體，以內容雜湊存放（`objects/<sha256>`），跟路徑無關。另一種是清單 `RESEARCH_ASSETS.json.gz`，記著每份內容取回後在專案裡的位置，`Tools/cloud_locator.py` 和 `research_asset_bundle.py restore` 都靠它。資料夾搬家後，如果清單沒跟著改，取回的檔會落在舊位置，雲端索引用新路徑也查不到。

2026-10-28 用雲端索引實算，32 個 Release 分成三種：

| 情況 | 數量 | 處理 |
|---|---|---|
| 沒有路徑清單，只按附件編目 | 9 | 不受路徑影響，不碰 |
| 有清單，但沒有任何路徑在搬移範圍內 | 12 | 不碰 |
| 有清單，部分路徑會被搬 | 11 | 替換清單 |

受影響的 11 個裡，路徑最多的是 `research-project-context-20261021`（約 15 萬條，大半在 LabSystem 和 `Validations/`），其次是 `research-historical-evidence-20261016`、`research-training-kits-20261016`、`research-results-models-20261016`。最少的 `research-lab-r61-r36-source-20261022` 只有 1 條。

替換的做法：

1. 新清單用同一個轉換產生。產生後核對：新舊清單的內容雜湊集合必須完全相同，只有路徑不同（第 5 點補傳的物件除外）。
2. 原清單在原 Release 裡直接改名成 `RESEARCH_ASSETS.pre-restructure-20261028.json.gz`。GitHub 允許改附件名稱，內容不用重傳，所以原清單一個位元都不會變。它對 Release 的作用就和標籤對 git 一樣：保存原貌，沒有工具讀它。
3. 上傳新清單，核對伺服器端的 sha256。中間任何一步失敗，就把原清單的名稱改回來。
4. 各 Release 的 `SHA256SUMS.txt` 記著清單的雜湊，要一起更新，舊的同樣改名保留。git 裡有 14 份收據提到 Release 清單，記著被替換清單雜湊的，照雜湊規則換成新清單的雜湊。
5. 少數文字檔同時存在 Release 和 git 裡，例如 E2 從 Release 取回進 git 的那批。這種檔被改寫後雜湊會變，要把轉換後的版本補傳成新物件，新清單才找得到它。
6. 先做只有 1 條路徑的 `research-lab-r61-r36-source-20261022`，取回、恢復都確認沒問題，再做其他 10 個。每個做完都用 `download_research_assets.py` 和 `restore` 實際取回一份抽樣，確認檔案恢復到新位置。

另一種做法是 Release 不動，在 git 裡放一張「舊路徑對新路徑」的對照表，讓取回工具查表。這次不採用：那正是原則 4 不要的翻譯層，而且那張表得永遠留著。

每個只存在 Release 的資料夾，在恢復位置留一份 README（原則 7）。至少包括：`Shared_Sources/Real_Sample_Captures/` 下的四個資料夾、`Shared_Sources/PSF_Camera_Acquisitions/20260924/`、`LabSystem_MOSR/control_program_recordings_20260924/`。其他 Release 若有整個資料夾都不在 git 裡的，也照做。

替換 Release 裡的檔案是修改 GitHub 上的內容。執行前，我會列出每個 Release 要替換的清單和補傳的物件，專案擁有者看過才動手。

## 驗證

每個 PR 都要通過下面這些檢查才合併：

1. **先記下基準**：改動前，在 `main` 上跑一次連結檢查、`Tools/validate_project_structure.py` 和各組 pytest，記下原本就壞的項目。之後只看有沒有新增。
2. **連結檢查**：新增 `Tools/check_markdown_links.py`。它之後會反覆用到，所以放進 `Tools/`。改動前能點的連結，改動後必須仍然能點。
3. **路徑等價檢查**：每一處改過的路徑，舊值在舊樹上解析出的位置，經過搬移規則轉換後，必須等於新值在新樹上解析出的位置。絕對路徑改成相對路徑的，用專案根目錄去接之後，也要指到同一個位置。
4. **本機虛擬樹檢查**：拿本機的完整檔案清單（掃描時不跟進目錄連結），套用搬移規則，得到一棵虛擬的新樹。程式和紀錄裡原本在本機找得到的路徑，轉換後也必須在虛擬新樹上找得到。這一項必須在交機前做。
5. **殘留掃描**：轉換後，整棵樹裡（含 `.gz` 和紀錄檔）解析到舊位置的路徑必須是零。可執行檔裡寫死 `D:\GMM_2_Final` 和寫死直譯器的地方也必須是零。敘述文字裡提到舊名稱不算路徑，不在此限。
6. **雜湊一致性**：轉換前，樹裡每一個「等於某個追蹤檔 sha256」的值，轉換後都必須等於那個檔目前內容的 sha256。
7. **程式檢查**：所有 `.py` 跑 `py_compile`；跑 `Tools/tests`、`Model/tests`、`PSF_Fitting/tests`、`AnalysisLab/tests`、`Thesis_MOSR_Evidence/tests` 以及各輪的 `tests/`。不做訓練或推論。
8. **規則跟著改**：`validate_project_structure.py` 和 pre-commit hook 改成認新結構，而且要能通過。

## 交機前的最後檢查

全部 PR 合併、Release 清單替換完之後，在這台電腦上、但完全不碰原專案資料夾，做一次「假裝已經交機」的檢查：

1. **全新 clone**：在專案外的新資料夾 `gh repo clone`。之後的步驟只用這份 clone 和 GitHub。
2. **取回代表性資料**：每類各取一組，用專案自己的工具取回，確認檔案恢復到樹上 README 寫的位置，內容雜湊相同。至少包括：930 張 PI 重拍的一趟、Step、NTU 一組序列加它的外部 GMF 包、PSF100、COMBO 和 R152 的模型。
3. **程式在新位置能用**：在 clone 裡跑第 7 項的測試；再挑幾支讀實拍或模型的分析腳本，只做讀取和路徑解析的乾跑，不做推論，確認它們找得到剛取回的檔。
4. **雲端索引一致**：用 clone 裡的 `cloud_locator.py build` 重建索引，抽查搬過的路徑，都要查得到。
5. **分支和標籤**：本機每個分支和標籤，都必須在 GitHub 上找得到（遠端同名分支，或已被遠端某個分支包含）。找不到的列出來，推成救援分支或由專案擁有者決定。
6. **再盤點一次**：用 2026-10-28 那套盤點方法重掃一次，確認這段期間沒有新產生、只在本機、而且依原則必須保存的東西。

這一節做完，交機前要做的只剩專案擁有者自己把要帶走的東西複製到外接硬碟。

## 分階段

| 階段 | 內容 | 風險 |
|---|---|---|
| 0 | 打標籤；寫好轉換工具 `Tools/restructure_tree.py`、`Tools/check_markdown_links.py` 和驗證腳本；記錄基準；在這台電腦上算好「外部路徑 → 雲端恢復位置」的對應 | 無搬動 |
| 1 | 不搬任何資料夾，只讓程式不綁這台電腦：絕對路徑改相對、外部路徑改恢復位置、直譯器路徑改 `python` | 中：改動面廣，但每一處都是同一個位置的不同寫法 |
| 2 | 封存收進 `Archive/`；交付包分組進 `Deliverables/`；`trial_README.md` 回 R128 | 低：引用少 |
| 3 | 跨輪分析收進 `Analyses/`；`_build153` 回 R153；只在 Release 的原拍改恢復路徑並留 README；364 個 runtime 快照收進子資料夾（見下） | 中 |
| 4 | `Traing_Progress` 拆成 `Experiments/Legacy` 和 `Experiments/Training_Runs`；`LabSystem_MOSR` 上移到頂層，之後放錄影資料夾的 README 並上傳錄影（先列清單給專案擁有者看）；規則文件全面更新 | 高：程式裡的分段路徑和層數改寫集中在這裡 |
| 5 | 11 個受影響 Release 的清單套用 2–4 的轉換並替換回去（先列清單給專案擁有者看，先做最小的一個） | 中：改的是 GitHub 上的內容，原清單改名留在同一個 Release |
| 6 | 交機前的最後檢查 | 無搬動 |

每個階段開一個 PR，通過驗證才合併。第 1 階段排在搬動之前，因為先把路徑統一成相對路徑，之後各階段的搬移就只需要處理相對路徑。

**364 個 runtime 快照**：`20260702_100MG_displacement_analysis` 和 `20260704_20x_5x_analysis` 底下各有一百多個 `_r61_real_sample_runtime_*` 資料夾，每次執行留一個，把分析資料夾的第一層擠滿。之前的 D 項打算刪到剩兩份，再附一張清單。照現在「不靠清單補救」的原則，改成把它們原封不動收進同一層的 `_r61_real_sample_runtime/` 子資料夾：單位名稱不變，什麼都不刪，引用由同一個轉換更新。分析資料夾的第一層因此只剩真正的分析內容。

## 要跟著改的規則文件

- `CLAUDE.md`、`AGENTS.md`：刪掉「`Traing_Progress` 不准改名」，改成說明新位置。新實驗仍放在 `Experiments/R##_…`。另外補一句提醒：新程式從自己的位置找專案根目錄，不寫死磁碟路徑。
- `docs/operations/QUIRKS.md`：`Traing_Progress` 拼字那條改成歷史說明。`Model/` 扁平結構照舊。
- `docs/operations/STARTING_NEW_EXPERIMENT.md`：路徑不變，補一句說明 `Legacy/`、`Training_Runs/` 是什麼。
- `docs/operations/LEGACY_ROUNDS_OPERATIONS.md`、`SOURCE_OF_TRUTH_POLICY.md`：舊批次的位置改成 `Experiments/Legacy/`。
- `PROJECT_ARCHITECTURE.md`、`README.md`：頂層結構圖換成新版。`README.md` 補上「從 GitHub 取得這個專案」：clone、需要的 Python 環境、怎麼取回 Release 裡的資料。
- `PROJECT_STATE.md`：保存狀態那段寫明「交機後 GitHub 是唯一的家」，並列出已知無法補的缺口（E 槽的 GMF 軟體、R63 一個模型）。
- `Model/` 訓練器的預設輸出位置，從 `Traing_Progress/` 改成 `Experiments/Training_Runs/`。舊自動調參程式讀寫的 `organized_*` 改指 `Experiments/Legacy/`。
- `.gitignore`：所有寫死舊資料夾的規則照搬移規則改寫，而且新規則涵蓋的範圍要和舊規則完全一樣。例如舊的 `_deployment_package/` 忽略整個資料夾，新規則只能忽略搬過去的那三個包，不能把整個 `Deliverables/Company_Packages/` 一起忽略。現有的 `.history/` 規則沒有前導斜線，本來就涵蓋根目錄，所以 VS Code 本機歷史外掛之後在根目錄寫的新 `.history` 仍會被忽略，不需要另加。
- `Tools/validate_project_structure.py`、`Tools/hooks/pre-commit`、`.github/workflows/validate-governance.yml`：
  - 「`Experiments/` 每個子資料夾都要有 MANIFEST 與 README，且列在 `INDEX.md` 裡」這條規則，要排除 `Legacy/` 和 `Training_Runs/`。這兩個資料夾各自要有 README，並在 `INDEX.md` 開頭各用一行說明。
  - 舊批次的檢查改認 `Experiments/Legacy/organized_*`。
  - 加一條提醒：可執行檔裡出現寫死的 `D:\GMM_2_Final` 時發出警告。
- 記憶檔裡提到舊路徑的條目，搬完後一併更新。

## 風險

- **靜態分析和實際執行的差距**：路徑等價檢查證明的是「每一處改寫後指到的位置和原本相同」，不等於每支腳本都實際跑過。這次不做訓練或推論，所以 2,000 多支歷史腳本只做到靜態正確、測試通過、能編譯。交機檢查的乾跑只抽樣。
- **絕對改相對之後，讀取端沒跟上**：紀錄裡的路徑變成相對路徑，但某支程式仍直接 `open(值)`。這時它會在「目前所在的目錄」下找檔，而不是在專案根目錄下找。路徑等價檢查涵蓋改寫工具認得的讀取端；認不得的只能靠測試和乾跑抽查。
- **交機前沒算完的東西就再也算不了**：外部路徑的對應、虛擬樹檢查、最後的重新盤點，都需要這台電腦上的檔案。所以這些排在階段 0 和階段 6，不能拖到交機之後。
- **`.gitignore` 改錯**：後果是大量本機資料暴露成未追蹤檔，甚至被誤加進 git。每個 PR 前後在本機各比對一次被忽略的檔數。
- **雜湊連鎖更新出錯**：可能把不該換的值換掉，例如剛好相同的十六進位字串。只換長度 64、且完全等於某個被改寫檔舊雜湊的值，發生機率極低；雜湊一致性檢查也會抓到。
- **舊分支**：合併時會有衝突。標籤讓這件事有辦法處理，但衝突不會自動消失。

## 由執行者自行判斷的部分

- 改寫工具和驗證腳本的實作細節。
- 各新資料夾的 README 內容：`Experiments/Legacy/`、`Experiments/Training_Runs/`、`Analyses/`、`Archive/`、`Deliverables/` 各子組，以及只在 Release 的資料夾。每份說明這一層是什麼，底下各單位一行說明。
- `trial_README.md` 搬到 R128 的 `trial/` 後，如果內容和那裡的 `README.md` 重複，兩份都保留，只在其中一份加一句說明。
- 交機檢查中「代表性資料」和「乾跑腳本」挑哪幾組，原則是每種角色至少一組。

## 專案擁有者的決定

1. **根目錄 3 支錄影**（「Basler acA2040-120um + PI Control — Optimized」，2026-09-24 14:00–14:03，共 125 MB，只在本機）：專案擁有者 2026-10-28 說明，這是實驗室系統新控制程式的效果錄影。所以它們歸到 `LabSystem_MOSR/control_program_recordings_20260924/`，不放在 PSF 原拍那裡，檔名不改，上傳 Release，樹上留 README。控制程式本身不在本專案的 git 裡，本專案只保存錄影。
2. **第 5 階段替換 11 個 Release 的清單**：這是執行者的建議，理由和做法見「雲端」，等專案擁有者同意。
