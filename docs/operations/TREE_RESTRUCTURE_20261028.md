# 檔案樹重整與交機操作紀錄（2026-10-28 起）

這份是操作紀錄，跟 [LOCAL_CLEANUP_20261026.md](LOCAL_CLEANUP_20261026.md) 同一類：記下搬了什麼、為什麼、怎麼驗證。沒有任何工具讀它，樹的正確性也不靠它。設計見 [檔案樹重整與交機設計](../superpowers/specs/2026-10-28-tree-restructure-design.md)，執行計畫見 [執行計畫](../superpowers/plans/2026-10-28-tree-restructure.md)。

這份紀錄、同名資料夾、設計與計畫本身不套用轉換：它們寫的就是舊路徑搬到哪裡，改掉就看不出原本的樣子。

## 轉換前的原貌

第 1 階段的 PR 合併前，`main` 會打永久標籤 `pre-restructure-20261028` 並推上 GitHub。任何檔案轉換前的樣子，看 `https://github.com/rio10255254/GMM_2_Final/tree/pre-restructure-20261028/<舊路徑>`。

## 這個資料夾裡有什麼

| 檔案 | 內容 |
|---|---|
| `moves_phase2.json`、`moves_phase3.json`、`moves_phase4.json` | 各階段的搬移規則，就是設計裡那張對照表。座標是該階段開始時的樹 |
| `external_map.json` | 外部絕對路徑 → 內容從雲端取回後在專案裡的位置。只靠內容雜湊對應，名稱相同不算 |
| `external_unmapped.tsv` | 程式裡指向外部、但內容不在雲端（或檔案已經不在這台電腦）的位置與引用次數。這些引用照原樣保留 |
| `build_external_map.py` | 產生上面兩份的程式。它要讀這台電腦上的外部檔案，所以只能在交機前跑 |
| `baseline/` | 改動前記下的基準：本來就壞的連結、驗證器輸出、本來就失敗的測試 |
| `edits_phaseN.jsonl.gz`、`unresolved_phaseN.tsv`、`problems_phaseN.txt` | 各階段每一處改寫、工具無法決定的位置、無法讀取的檔 |
| `decisions_phaseN.json` | 工具無法決定的位置，人工判斷後的決定與理由 |
| `reader_hints_phaseN.json` | 工具算不出路徑的名字（從設定值拼出來的、或由載入它的程式在執行時才設定的），人工指出它指向哪個檔與理由 |
| `manual_phaseN_*.py` | `apply` 之後的人工修正，寫成可以重跑的程式：每一處都要原文完全相符才改 |
| `hash_changes_phaseN.json` | 各階段改寫後雜湊的變動（舊 sha → 新 sha），第 5 階段替換 Release 清單時用 |
| `verify_phaseN.txt` | 各階段驗證的結果 |
| `releases_phase5.json` | 第 5 階段每個 Release 的處理：換掉的原清單（改名後的名稱與 sha256）、新上傳的檔與 sha256、取回抽樣的結果 |
| `releases_phase6.json` | 第 6 階段：33 個 Release 改寫後的標題與說明全文（GitHub 不留說明的修改歷史）、讀回比對、實際跑過的取回範例，以及 `research-results-models` 補換的 `RESTORE_MANIFEST` |
| `hash_chain_phase6.json` | 第 6 階段找到並改回的雜湊連鎖誤換，以及判斷不了、照原樣留下的位置 |
| `handoff_check_phase6.json` | 交機前最後檢查（全新 clone、取回、測試、索引、分支、重新盤點）的結果 |

## 工具

- `Tools/restructure_tree.py`：每個階段的 `plan`、`apply`、`verify`，以及 `baseline`。
- `Tools/restructure_rules.py`、`restructure_resolve.py`、`restructure_text.py`、`restructure_python.py`、`restructure_hashes.py`、`restructure_verify.py`：規則、路徑解析、文字與 Python 改寫、雜湊連鎖、驗證。
- `Tools/restructure_readers.py`：程式把資料檔（JSON、YAML、TOML）裡的路徑讀回來用的地方。從讀檔的那一行一路追到用固定鍵名取值的地方，跨函式、跨模組、經過容器都追；讀取處改成接上專案根目錄，驗證時逐一確認讀到的位置跟原本相同。
- `Tools/check_markdown_links.py`：連結檢查，之後也會一直用。
- `Tools/handoff_inventory.py`：交機盤點，第 6 階段會再跑一次。

## 外部路徑（2026-10-28）

- 下載資料夾裡的 `20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903` 是目錄連結，指向專案的 `Shared_Sources/PI_Repeatability_20260903/raw`。程式裡寫成這個路徑的引用約 4,740 處，實際指的是專案內部，改成專案內的位置。
- `D:\NTU_ImageDataset`、`D:\NonSystemFiles\GMM2`、`H:\From_2TB_D_disk\13_thesis` 裡，內容已在雲端的 4,663 個檔、56 個資料夾，改成取回後的位置。NTU `Pitch1um_Y_100/Raw` 的 202 張全部對到 `Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw/`。
- 對不到的引用 682 處，見 `external_unmapped.tsv`。最大宗是 `C:\Users\Rio\Downloads\NTU_ImageDataset`（580 處）：那是公司序列更早放的位置，現在已經不在這台電腦上，無法用內容確認它和 `D:\NTU_ImageDataset` 是不是同一批，所以照原樣保留。

## 各階段

（每個階段完成後補上：搬了什麼、改寫數量、人工處理的位置、驗證結果。）

### 第 1 階段：路徑改成跟著專案走（2026-10-29）

不搬任何資料夾，只把寫死這台電腦的路徑改掉，讓專案放在哪個資料夾都能用。

**改了什麼。** 4,828 個檔、135,202 處。

- 紀錄（JSON、CSV、log 等）裡的絕對路徑改成相對於專案根目錄：122,536 處。
- 文件 8,619 處，連結 96 處。
- Python 的絕對路徑改成從檔案位置推出的專案根目錄（`PROJECT_ROOT`）：1,575 處（讀回資料檔的另計，見下）。
- MATLAB 217 處，PowerShell 51 處。
- 直譯器路徑改成 `python`：114 處。

單提專案資料夾本身的地方：在紀錄和模板裡寫成 `.`，在說明文字（文件、docstring、註解）裡照原樣保留，因為它記的是當時在哪裡做的。

**讀回資料檔的程式。** 紀錄裡的路徑改成相對之後，把這些紀錄讀回來用的程式（各輪的 `config/experiment.json`、manifest、`ESTIMATOR_POLICY.json`）會拿到相對路徑。原本的寫法是 `實驗資料夾 / 設定值` 或 `Path(設定值)`，前者會接錯資料夾，後者要看執行目錄。`Tools/restructure_readers.py` 從讀檔處追到每個用固定鍵名取值的地方，把讀取處改成接上專案根目錄：

- 一共 1,006 處，分布在 399 個檔。
- 寫法有三種：
  - `Path(PROJECT_ROOT / 值)`
  - `str(PROJECT_ROOT / 值)`：字串用法照舊是字串，值跟以前一樣是絕對路徑。
  - 原本是 `實驗資料夾 / 值` 的，把前面換成 `PROJECT_ROOT`。
- `PROJECT_ROOT / 絕對路徑` 得到的就是那個絕對路徑，所以之後重跑時程式自己寫出絕對路徑也一樣對。

**人工指出的地方。**

- `reader_hints_phase1.json`，4 處：
  - R67 以檔名動態載入論文 `source_scripts` 底下的三支分析腳本，並把 `MANIFEST_PATH` 設成它自己產生的 manifest。
  - R77 的 `R76_RUNNER` 是從設定值拼出來的。
- `decisions_phase1.json`，1 處：R63 的 `pair_text()` 把整筆紀錄串成文字來搜尋關鍵字，不開檔，維持原樣。

**人工修正（`apply` 之後）。**

- `manual_phase1_writer.py`：center9 頻譜 manifest 的寫出端改成寫相對路徑；讀回它的測試由工具改。
- `manual_phase1_data_readers.py`，工具不改寫的讀取端，共 20 個檔：
  - MATLAB 讀設定檔的 15 個檔（R72–R83 的 ACM、V42 第 6.2 節圖表腳本，以及 `docs/reproducibility` 底下的編輯用副本）：改成 `fullfile(PROJECT_ROOT, ...)`。
  - R148v2 的兩支監看腳本：用 `[System.IO.Path]::Combine($ProjectRoot, ...)`，相對、絕對路徑都對。
  - R128 `check_r61.py` 重播 `plan.json` 記錄的整串指令：工作目錄改成專案根目錄。
  - R135 `adapters.py`、`adapters_v2.py` 在行程內重跑同一串指令：沒被替換的路徑參數接上專案根目錄。

**留給人看的清單。** `unresolved_phase1.tsv` 76 列、41 個檔，全部是「值帶著改過的路徑進到工具追不到的地方」，不擋 `apply`。逐條看過：

- 寫出紀錄、畫圖、做表、印出、數值比對、遞迴序列化。
- 傳給讀取處已經改好的函式（R129 → R128 `reader()`、R152 的 PSF 融合只讀數值設定）。

都不需要再改。真的會讀路徑的（上面的人工修正與提示）已經處理。

**原樣保留。** 16 個非 UTF-8 的檔，見 `problems_phase1.txt`：

- 第三方的 `bads-1.1.3` 原始碼。
- 早期幾輪用 cp950 寫的 log。

**驗證。** `verify_phase1.txt`：0 個問題。檢查項目：

- 每一處改寫的等價性。
- Python 路徑重新求值。
- 每個讀回資料值的位置新舊相同。
- 殘留的本機路徑。
- 雜湊連鎖：內容改變的檔，它的 sha256 在引用它的紀錄裡跟著更新，人工修正之後再用 `rehash` 帶一次，最終共 4,426 個雜湊變動（`hash_changes_phase1.json`）。
- 連結、驗證器、各組 pytest 都對照基準線。

在這個 checkout 跑測試前，從原本的工作樹複製了測試會讀的本機資料：R118 的資料包、R67 名單上的 checkpoint 與影格等，共 38.2 GB，都不進 git。原本的工作樹靠絕對路徑直接讀到它們；改成相對路徑後，測試讀的是這個 checkout 自己的資料夾。

這一階段也修了工具在 MATLAB 的一個錯誤：`PROJECT_ROOT` 原本只定義在檔案的第一個函式裡，用到它的 local function 看不到。現在每個用到它的函式各自定義一次。

### 第 2 階段：封存與交付各歸一處（2026-10-29）

**搬了什麼。** 597 個檔，規則見 `moves_phase2.json`：

- 根目錄的六個封存資料夾，加上 `Thesis_MOSR_Evidence` 裡中途停止的 `Research_Round_Library_20260926_ABORTED_OVERSIZED`，集中到 `Archive/`。
- 交付包按用途分到 `Deliverables/` 底下：
  - `Company_Packages`：原本的 `_deployment_package` 和兩個 MOSR ONNX。
  - `Thesis_Handoffs`：R128 到 R137 的論文交接。
  - `Standalone_Models`：原本的 `LabSystem_MOSR/Model_Packages`，以及 R137、R152 的獨立包。
  - `Data_Regenerators`。
- `Validations` 移到 `Deliverables/Validations`。
- 根目錄的 `trial_README.md` 移回它說明的 R128 `trial/` 資料夾。

**改了什麼。** 431 個檔、7,663 處引用跟著改到新位置：紀錄 6,399 處、文件 814 處、連結 243 處、Python 199 處、腳本 8 處。內容改變的檔，雜湊共 559 個變動。

**人工判斷。**

- `decisions_phase2.json`，31 處：都是在定義「`Thesis_MOSR_Evidence` 或 `LabSystem_MOSR` 這個資料夾」的寫法，例如 `THESIS = PROJECT_ROOT / 'Thesis_MOSR_Evidence'`。資料夾本身不搬，只有底下一兩個子資料夾搬走，所以維持原樣。從它往下接的固定路徑，工具各自求值、各自改寫。
- `trial_README.md` 搬進 `trial/` 後，工具把它的執行指令當成相對於文件的路徑，改成了 `'restore.py'`。這是要在專案根目錄執行的指令，所以改回 `Experiments/R128_SourceOnlyFullTraining/trial/restore.py`。它是同資料夾 `README.md` 較早的一份，兩份都留，在它開頭加一句說明。
- `Research_Round_Library_..._ABORTED_OVERSIZED` 的 `ABORTED_README.md` 寫「請使用同層的設計與效果回顧」。搬走之後兩者不再同層，所以在文末補一段現在的位置，原文不改。

**README。**

- 新寫：`Archive/README.md`、`Deliverables/Thesis_Handoffs/README.md`、`Deliverables/Data_Regenerators/README.md`。
- 擴充：`Deliverables/README.md` 補上五類的說明；`Company_Packages`、`Standalone_Models` 原本就有的 README 補上新放進來的包與原位置。

**`.gitignore`。**

- 指到 `Validations`、`Research_Round_Library` 的條目改到新位置。
- `_deployment_package/` 原條目保留，另外逐一列出搬到 `Company_Packages` 的三個包和兩個 zip。不整個忽略 `Company_Packages`，因為兩個 MOSR ONNX 原本不在忽略範圍內。
- `verify` 確認本機每個檔是否被忽略，前後都一樣。

**驗證。** `verify_phase2.txt`：0 個問題。

這一階段工具補了三處：

- `rehash` 改成照搬移規則找檔案在 HEAD 的原身，不靠 git 的改名猜測。新檔案在 HEAD 沒有原身；被大幅手改的搬移檔，git 會看成刪除加新增。
- 往上爬到共同上層再往下接的寫法，驗證時只算一個目標。
- 深層副本裡從根目錄寫起、本來就壞的連結，目標照規則搬移後仍視為同一個舊問題。

### 第 3 階段：跨輪分析與只在 Release 的原拍（2026-10-30）

**搬了什麼。** 589 個檔，規則見 `moves_phase3.json`：

- 根目錄的五個跨輪實拍分析和 `AnalysisLab` 集中到 `Analyses/`。
- 兩個位移分析資料夾第一層的 `_r61_real_sample_runtime_*` 快照，原封不動收進各自的 `_r61_real_sample_runtime/`。100MG 有 112 個、20×／5× 有 213 個，名稱不變，一個都沒刪。
- `_build153` 歸回 R153。

**只在 Release 的原拍。** `Step`、`20260702_100MG_位移_50x`、`20260704_20x`、`20260704_5x`、`20260924` 原本只在 Release 裡，檔案樹上看不到。

- 這一階段在解析時讓它們的 Release 路徑經過規則對應，指向它們的引用跟著改到 `Shared_Sources/Real_Sample_Captures/`、`Shared_Sources/PSF_Camera_Acquisitions/20260924/`。
- 每個新位置放一份 README，寫明內容、在哪個 Release、怎麼取回。取回指令用新位置當 `--prefix`。
- Release 清單本身在第 5 階段才換，換完之後這些指令就能直接用。

**改了什麼。** 983 個檔、12,763 處：紀錄 10,907 處、連結 820 處、文件 388 處、Python 589 處、腳本 59 處。雜湊 801 個變動。

**補進來的檔。** `Analyses/20260702_100MG_phase_dft_analysis_matlab/` 底下 10 張只在本機的 PNG（相位 DFT 位移圖、最佳 30 張的比較、ROI 預覽），從原工作樹複製進來，逐張核對 sha256 相同。

**README。**

- 新寫：`Analyses/README.md`、`Shared_Sources/Real_Sample_Captures/README.md`，以及五個原拍資料夾各一份。
- `Shared_Sources/README.md`、`Shared_Sources/PSF_Camera_Acquisitions/README.md` 補上新位置。

**沒有人工決定的地方。** `plan` 回報的兩處讀回資料值，是 `AnalysisLab/index.json` 的 `entry_point`，被拿來比較字串和顯示。值是從專案根目錄寫的專案相對路徑，照規則改成新位置後，讀它的地方本來就該跟著到新位置。工具補上這條規則之後，就不再回報。

**驗證。** `verify_phase3.txt`：0 個問題。

這一階段工具補了三處：

- 等價檢查改成用舊值當初的讀法（根目錄相對或檔案相對）去讀新值。`docs/reproducibility/` 底下有小寫的 `experiments/`，在 Windows 上會被重新猜成相對於檔案。
- 殘留檢查遇到 `lab_r46_*` 這類樣式片段，只要它所在的資料夾存在就算數。
- 殘留檢查裡，被判成「還指著舊位置」的解讀，必須在搬移前真的存在過才算。R53、R56 封存清單裡的路徑，是相對於封存資料夾寫的，從來不是指根目錄的 `Reconstruct_Progress`。

### 第 4 階段：拆開 `Traing_Progress`，LabSystem 回到根目錄（2026-10-30）

**搬了什麼。** 2,141 個檔，規則見 `moves_phase4.json`：

- 根目錄的 `Traing_Progress` 拆成兩處，資料夾名稱都沒改：
  - 每次訓練一個的 `training_progress_*` 移到 `Experiments/Training_Runs/`。
  - 其餘（`organized_*` 早期整理批次、`auto_tune_reports` 等）移到 `Experiments/Legacy/`，原本的 README 也跟著過去。
- `Thesis_MOSR_Evidence/LabSystem_MOSR` 移到根目錄 `LabSystem_MOSR/`。它有自己的校正、資料與模型歷史，不是論文證據的一部分。`LabSystem_MOSR/Traing_Progress` 是 Lab 自己的資料夾，名稱照舊。

**改了什麼。** 1,658 個檔、91,770 處：紀錄 84,924 處、文件 4,247 處、連結 1,001 處、Python 1,573 處、腳本 24 處、notebook 1 處。雜湊 1,335 個變動。

`Model/` 訓練器的預設輸出位置跟著改成 `Experiments/Training_Runs/`。改之前先加了 `Model/tests/test_default_training_output_dir.py`，確認它在舊程式上失敗、改寫後通過。

**人工判斷。**

- `decisions_phase4.json`，594 處。程式裡寫 `PROJECT_ROOT / 'Traing_Progress'` 的地方，工具無法自己知道要接的是哪一半，所以逐處判斷：
  - 548 處接的是訓練輸出，改到 `Experiments/Training_Runs`。
  - 6 處接的是早期批次（自動調參與 R32 的 `progress_root`、DiagnosticMatrix、`research_recovery`、驗證器的 `legacy_root` 和它的測試），改到 `Experiments/Legacy`。
  - 40 處維持原樣：24 處是論文區自己的路徑，4 處是 LabSystem R51–R54 測試裡的暫存資料夾，1 處是封存的垃圾區，1 處是 LabSystem `psf_calibration` 往上爬到論文區的寫法，10 處是不指路徑的字串。
  - 往上爬那處（`validate_inner_circle_psf_fit.py`）：`ROOT.parents[1]` 原本是論文區，LabSystem 搬到根目錄後剛好變成專案根，原本接的 `LabSystem_MOSR/…` 照樣找得到，所以整支程式該跟搬家前一樣。apply 卻在同檔另兩行爬回 `Thesis_MOSR_Evidence`，`manual_phase4.py` 把它還原，sha256 與搬家前相同。判斷裡加了 `reaches: ""`，寫明這段不改的程式搬家後指到專案根。
- `reader_hints_phase4.json`，3 處：自動調參與 R32 用 `train_mod.PROJECT_ROOT`、`research_recovery` 用 `root` 當根目錄，工具從別的模組追不到它的值，所以人工告訴它這就是專案根。
- `manual_phase4_legacy_joins.py`，515 個檔：第一次 `verify` 抓到的錯。推論程式（`Model/` 的 `Infer_v5_SimpleTest`、`Infer_TTA`，以及它們散在各輪快照與交付包裡的副本）用同一個 `TRAINING_PROGRESS_ROOT` 既找 `training_progress_*` 權重，又接 `organized_*` 早期批次；`PostLongRunCleanup` 的 `TP_ROOT` 也一樣。這個根照判斷改到 `Training_Runs` 之後，接 `organized_*` 的地方會指到不存在的 `Experiments/Training_Runs/organized_…`。腳本在根的下一行加 `LEGACY_ROOT`，把那些接法改用它；重跑不會再改。根本身不是專案根的副本（交付包內部的 `Traing_Progress`、`parents[1]` 指到副本上層的舊版）不動。
- `manual_phase4.py`，4 處只出現在訊息和組字串裡的舊名，工具不會改：R46 的找不到檔訊息、`project_reproducibility_audit` 的兩個邏輯位置、`replay_legacy_multiscale_selection` 和 `replay_shared_model_history` 組出來的路徑。

**README。**

- 新寫：`Experiments/Training_Runs/README.md`。
- `Experiments/Legacy/README.md`（原 `Traing_Progress/README.md`）補一段拆分說明；`Experiments/INDEX.md` 頂端加兩行指到這兩區。
- `Thesis_MOSR_Evidence/README.md` 標題改成「論文證據」，註明 LabSystem 的新位置。

**規則與首頁文件。**

- `CLAUDE.md`、`AGENTS.md`：Known quirks 改成新位置；加一條提醒，新程式從自己的位置找專案根，不寫死磁碟路徑。
- `QUIRKS.md` 第 1 節改寫成這個拼字的歷史；`STARTING_NEW_EXPERIMENT.md`、`LEGACY_ROUNDS_OPERATIONS.md`、`SOURCE_OF_TRUTH_POLICY.md`、`Model/README.md`、`TIMELINE.md` 裡「拼字是歷史，不可改名」這類現在已不成立的句子，改成「原在根目錄 `Traing_Progress`，2026-10-28 移來」。`HANDOFF_DOC_RESTRUCTURE_20261024.md` 是當時的紀錄，原意不改，只加註。
- `README.md`、`PROJECT_MAP.md`、`PROJECT_ARCHITECTURE.md` 第 5 節換成重整後的根目錄；`README.md` 加「從 GitHub 接手」的三步。`PROJECT_MAP.md` 原本那句「不為了外觀搬動 LabSystem、Model、Traing_Progress」改成搬動時路徑要一起改的說明。
- `PROJECT_STATE.md`：寫明 GitHub 之後是唯一的家，§4 補上外部 GMF 量測程式、H 槽路徑依賴、本機獨有內容三項尚未清點的缺口。

**驗證器。** `Tools/validate_project_structure.py` 把 `Experiments/Legacy`、`Experiments/Training_Runs` 當成共用區，只要求 README，不套輪次規則。

另外新增的 Check 12（程式裡寫死 `D:\GMM_2_Final\…` 這類路徑時發提醒，目前 0 處）是新功能，不是搬家帶來的改寫，所以放在第 4 階段之後另一個 commit，不算進這一階段的紀錄。

**`.gitignore`。** `Traing_Progress/*` 換成 `Experiments/Legacy/*`、`Experiments/Training_Runs/*`，各自放行 README；原本 90 條 `organized_*` 的條目改到 `Experiments/Legacy/`。根目錄 `Traing_Progress/` 的條目保留，舊副本裡若還有這個資料夾也照樣忽略。

**驗證。** `verify_phase4.txt`：0 個問題。跑了三次才到 0：第一次抓到 `organized_*` 接錯根（上面的 `manual_phase4_legacy_joins.py`）和 5 處單段名稱的誤報；第二次抓到 LabSystem 往上爬那支被改壞、新加的 `LEGACY_ROOT` 被算成新目的地、說明文字裡帶斜線的 `Traing_Progress/` 被當成舊路徑，以及 Check 12 的新程式。真的錯都修了，誤報則修工具並補測試。

這一階段工具補了五處：

- 判斷可以加 `reaches`，寫明不改的程式搬家後指到哪裡（`""` 是專案根），驗證時拿它當預期。
- 一個根拆成兩個時，新加的那個根（例如 `LEGACY_ROOT`）只是其他新目標的上層，不算新的目的地；接錯根的地方照樣會報成目標遺失。

- 等價檢查遇到只剩一段、沒有斜線的新值（`'Thesis_MOSR_Evidence/LabSystem_MOSR'` 改成 `'LabSystem_MOSR'`），若這個名字在新樹根目錄存在，就把它當目標。原本會誤報成「目標消失」。

- 人工提示可以給一個運算式（例如 `train_mod.PROJECT_ROOT`）指定路徑，不只限變數名。
- 人工判斷可以只針對某一個檔，同一個寫法在不同檔可以判成不同去處；往上爬的寫法也能被判斷保留。

**2026-10-31 補修：兩份文件裡指的是自己包裡的資料夾。** 準備第 5 階段時，把第 2 到第 4 階段的 11.2 萬處改寫逐一對回 git 與本機清單，找到 4 處真的改錯：

- R26 打包備份裡那份 `Model/README.md` 的副本（第 41、51 行）：它的 `Traing_Progress/` 指的是包裡自己的 `內部檔案/Traing_Progress/`。
- LabSystem 的 R62 報告（第 65、86 行）：它指的是 LabSystem 自己的訓練紀錄 `LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_*`，根目錄從來沒有。

搬家規則把這幾行改成 `Experiments/Legacy`、`Experiments/Training_Runs`。`manual_phase4_inner_folders.py` 把它們從第 1 階段前的 commit 改回原文，兩個檔的新 sha256 也帶進 `hash_changes_phase4.json` 和三份目錄檔（`REPOSITORY_FILES.json.gz`、`SOURCE_AVAILABILITY.json.gz`、`CURATED_FILE_MAP.json.gz`）。腳本重跑不會再改任何東西。其餘疑似的地方（142 處 `py:join`、`.history` 與 `FILE_GUIDE` 裡的命中）逐一看過，都是誤報。

### 只在本機的控制程式錄影上傳（2026-10-30）

專案根目錄有三支 2026-09-24 的控制程式效果錄影（MP4，共 124.9 MB），原本只在原電腦上。專案擁有者看過檔名與大小後同意上傳。

- 發布附件 [labsystem-control-recordings-20261028](https://github.com/rio10255254/GMM_2_Final/releases/tag/labsystem-control-recordings-20261028)，在專案裡的位置是 `LabSystem_MOSR/control_program_recordings_20260924/`，資料夾裡只追蹤 README，`.gitignore` 擋住還原回來的 MP4。
- 打包時把三支的 sha256 與大小寫進選擇清單；上傳後從 Release 重新下載、驗證、還原，三支 sha256 與原檔相同，檔名（含全形破折號）一字不差。README 裡的取回指令照寫法實際跑過。
- 本機原檔沒有刪。

**repo 是公開的。** 上傳工具原本只准傳到私人 repo，這次被擋下。專案擁有者確認是自己公開的，所有資料（含發布附件）都已授權公開。`publish_research_assets.py`、`publish_research_batch.py` 改成公開 repo 要加 `--public-ok` 才放行：公開 repo 的附件也是公開的，所以仍要明確表示。

### 第 5 階段：Release 清單跟著新路徑（2026-11-01 到 11-02）

**動了哪些 Release。** 33 個裡動了 14 個，逐一記在 `releases_phase5.json`：

- 10 個沒有路徑清單，只按附件編目，不受搬家影響，沒碰。
- 9 個有清單，但沒有任何路徑在搬移範圍內，也沒有 git 改寫過的內容，沒碰。
- 14 個換了清單。設計時估 11 個；多出來的 `r94-complete-record`、`r95-complete-record`、`research-psf-camera-acquisitions` 路徑一條都沒變，但裡面有檔在 git 裡被前幾階段改寫過，要補傳改寫後的版本，清單才指得到。

14 個合計 393,379 條路徑，其中 210,424 條換到新位置；399 筆紀錄改指向補傳的內容，共補傳 395 個物件。路徑最多的是 `research-project-context`，換了 151,537 條。

**每個 Release 怎麼換。** 照設計的做法，`Tools/restructure_release_manifests.py` 的 `apply` 一次處理一個：

- `RESEARCH_ASSETS.json.gz`、`BUNDLE_SUMMARY.json`、`SHA256SUMS.txt` 改名成 `*.pre-restructure-20261028.*` 留在原 Release，內容一個位元都沒動。
- 上傳新的三份，加上一個 `<tag>.restructure-20261028.zip` 裝補傳的物件；每個上傳的檔都跟 GitHub 回報的 sha256 核對。
- 換完立刻用 `verify` 抽樣取回：補傳的物件全部抽，搬家的路徑抽 20 條，下載附件、`restore` 到暫存資料夾，逐檔核對 sha256 落在新路徑。14 個全部 PASS。

先做只有 1 條路徑的 `research-lab-r61-r36-source`，確認沒問題才做其他 13 個。

**新舊清單只有路徑不同。** 每個新清單在產生時都核對過：內容雜湊的集合跟原清單相同，只多了補傳的那些。條目裡記原始位置的欄位（`historical_source`、`run`）照原值保留，它們記的是當初從哪裡來。

**雜湊連鎖說法不同的 1,996 處。** 前幾階段的雜湊紀錄說某些內容在 git 裡被改寫過，但逐條路徑去對，Release 裡那條路徑的內容並沒有被改寫。1,996 處逐一分類，全部是同一種：那條路徑從來不在 git 裡，是只存在 Release 的副本，git 改寫的是同樣內容在別的路徑上的那一份。所以這些條目保留 Release 原本的位元組。主要在 `research-historical-evidence`（1,845 處）和 `research-results-models`（150 處）。

**git 裡的清單副本。** 有 14 份 Release 清單或摘要的副本放在 git 裡。其中 5 份本來就跟新上傳的一樣；另外 9 份換成新上傳的位元組：

- `Shared_Sources/PSF_Camera_Acquisitions/` 的 `RESEARCH_ASSETS.json.gz`、`BUNDLE_SUMMARY.json`
- `docs/reproducibility/four_rounds/` 的 `CAMERA_ORIGINALS_MANIFEST.json.gz`、`R94_RECORD_MANIFEST.json.gz`、`R95_RECORD_MANIFEST.json.gz`
- `docs/reproducibility/priority_sources_20261022/RESEARCH_ASSETS.json.gz`、`round_source_followthrough_20261022/RESEARCH_ASSETS.json.gz`
- `docs/reproducibility/project_completion/TRAINING_HISTORY_MANIFEST.json.gz`
- `docs/reproducibility/verification/RESULTS_MODELS_BUNDLE_SUMMARY.json`

前幾階段的全文改寫已經動過這幾份副本，但改成了半套：R94、R95 被改寫的檔換上了新雜湊，`asset` 卻還指著原本的 zip，照它取回會核對失敗；另外四份把 `historical_source`、`run` 這些記原始位置的欄位也改成了新路徑。換成 Release 上的版本之後，兩個問題都消失。沒有程式讀這些副本。

`Shared_Sources/PSF_Camera_Acquisitions/DELIVERY_VERIFIED.json`、`priority_sources_20261022/` 與 `round_source_followthrough_20261022/` 的 `DELIVERY_VERIFIED.json`，以及 `docs/reproducibility/lineage/` 的 `HISTORICAL_GAPS_DELIVERY_20261022.json`、`LAB_R61_R36_FIXED_INITIALIZER.json`、`LAB_R61_R36_PROVIDERS.json`，記著原清單的雜湊。它們是當時取回驗證的收據，原清單也還在 Release 裡（改名成 `*.pre-restructure-20261028.*`），所以不改。

**執行中補的三處。**

- `plan` 第一次跑了兩天沒有結束。原因是 `git cat-file --batch` 的請求一次全部寫進去，量一大，兩邊的管道都滿了，git 和這支程式互相等。改成另開一條執行緒送請求、主程式同時讀回應，補了一個大量物件的測試。
- `research-project-context` 的抽樣要下載約 0.95 GB，600 秒逾時；重試時 `gh` 又不肯覆蓋上一次留下的半個檔。下載改成兩小時逾時，重試加 `--clobber`，兩件事各補了測試。
- `research-training-history-supplement` 的抽樣要下載一個 1.52 GB 的附件，兩次都在約 55 分鐘、下載超過 95% 時被 GitHub 斷線（HTTP/2 `PROTOCOL_ERROR`）。`gh` 不能接續，重試只會從頭再來、再撞上同一個斷點。抽樣的附件下載改用 `curl -C -`，斷了就從已經下載的位置接下去，最多五次，下載完再跟 GitHub 列的 sha256 核對；補了三個測試。改完重跑，PASS。

`r95-complete-record` 的 `apply` 在上傳完之後、寫下結果之前被中斷（當時外層迴圈把驗證的結束碼吃掉了，停下來改寫迴圈）。它的每個改名與上傳都已經跟 GitHub 回報的 sha256 核對過，結果是事後照實補寫的，`releases_phase5.json` 裡這筆有註記。之後重跑 `verify` 一樣 PASS。

**雲端索引。** 換完之後第一次 `python Tools/cloud_locator.py build`，抽查的結果反過來：新路徑查不到，舊路徑查得到。原因是 `cloud_locator` 下載清單時，快取裡只要有同名檔就不再下載，這次清單換了內容、名稱沒變，它就一直讀舊的。改成快取檔的 sha256 要跟 Release 列的一致才沿用，不一致就重新下載，補了兩個測試。重建後 33 個 Release、398,192 條路徑；從 `research-training-kits`、`research-project-context`、`research-lab-r61-r36-source`、`research-training-history-supplement` 各抽一條搬過家的路徑，新路徑都查得到，舊路徑都查不到。在這之前 build 過的電腦（包括原電腦的主工作區）重跑一次 `build` 就會自動換新。

### 第 6 階段：交機前的最後檢查（2026-11-03）

照設計書「交機前的最後檢查」做，結果記在 `handoff_check_phase6.json`。過程中找到三個要修的地方，也一起處理了。

**全新 clone。** 在 `D:\GMM_2_Final_handoff_check` 照入門指南的 `git clone --depth 1` 取 main（`c8ea0ef4`），之後只用這份 clone 和 GitHub。

- **測試**：pre-commit 那套測試在 clone 裡 422 個通過、15 個失敗。失敗的跟 GitHub CI 上一直失敗的那批相同（CI 多一個要呼叫 PowerShell 的測試，本機被跳過）。它們缺的是不進 git 的資料：R26 交付包內部檔、`Experiments/Legacy/auto_tune_reports/`、R26 的 `archived_inputs` 與 `package_cleanup_archive`，這些都在 Release 裡，取回後就有；center9 Wiener 的圖表（`Thesis_MOSR_Evidence/Final_Data_Figures/03_PSF_EXPERIMENT_RESULTS/01_global_bads_fit/figures/center9_pillar_fit_20x_50x/`）不在雲端，是原工作區 sandbox 分支上還沒提交的工作，見下面「只在本機」。
- **雲端索引**：clone 裡從零 `cloud_locator.py build`，33 個 Release；四條搬過家的路徑新位置都查得到、舊位置都查不到。
- **取回代表性資料**：照樹上 README 的指令（`download_research_assets.py --prefix` 加 `research_asset_bundle.py restore --destination . --keep-identical-existing`），把 `--prefix` 縮到每類一個檔，取回到 clone 裡：Step、NTU `Pitch1um_Y_100` 一張原拍和它外部 GMF 量測包裡的一個檔、PSF100 一張原拍、COMBO 模型、R152 兩個模型與 PSF。全部 PASS，都落在 README 寫的位置。930 張 PI 重拍照它 README 的 `restore_pi_acquisition.py` 取回，結果見 `handoff_check_phase6.json`。
- **乾跑**：`ESTIMATOR_POLICY.json` 登記的 COMBO 模型路徑，在 clone 裡指到剛取回的檔。R152 論文版獨立包 `R152_Standalone_ImageFiles_20261004` 的 `manifest.py` 裡，屬於 git 的 34 個檔和從 Release 取回的 6 個檔全部核對相符；它接著要的 9,216 張 TIFF 是由 `generate_data.py` 生成的，這次不生成，沒有跑推論。

**分支和標籤。** `D:\GMM_2_Final` 與另兩個工作樹共用的 102 個本機分支和標籤，37 個在 GitHub 有同名的、65 個已被 GitHub 上的分支包含，沒有只在本機的。沒提交的改動不在 GitHub：原工作區有 438 個刪除（原檔在 git 歷史裡）和 52 個修改，`C:\Users\Rio\.codex\worktrees\impact-r152` 有 3 個修改；這些是專案擁有者自己的工作，沒有動。

**再盤點一次。** 用 10-28 同一支 `Tools/handoff_inventory.py`、同樣三個根目錄（原專案、`H:\GMM_2_Final_Archive`、C 槽的 R152 IMPACT 工作區）重掃 2,623,875 個檔。10-28 之後沒有新出現的檔，也沒有新變成只在本機的檔。第一次重掃一度報出 688 個「新的只在本機」，原因是第 5 階段重建索引時沒加 `--with-zips`，沒有清單的 ZIP（R61 ONNX 交付包、歷史精選包等）裡面的檔沒進索引；加上之後重掃，歸零。

**補換 `research-results-models` 的第二份取回清單。** 這個 Release 另有一份 `RESTORE_MANIFEST_20261016.json.gz`，跟 `RESEARCH_ASSETS.json.gz` 只差兩條：兩份 2026-10-16 收尾前的舊治理設定檔還原到 `Historical_Archive/pre_closeout_20261016/`，不會跟現行的同名檔撞在一起。第 5 階段只換了 `RESEARCH_ASSETS.json.gz`，這份還寫著舊路徑（`Traing_Progress/` 756 條、`Thesis_MOSR_Evidence/LabSystem_MOSR/` 10,946 條）。照第 5 階段的做法換掉：新檔以第 5 階段的新清單為底，那兩條改放 `Archive/Historical_Archive/pre_closeout_20261016/`，原檔改名成 `RESTORE_MANIFEST_20261016.pre-restructure-20261028.json.gz` 留著。上傳後 GitHub 回報的 sha256 跟本機相同，用它取回 R152 的 PSF 檔也 PASS。`SHA256SUMS.txt` 從來沒列過這份，前後都沒列。

**改寫 33 個 Release 的說明。** 每份都照同一個格式：這是什麼、取回後放在哪（從清單算出的位置表）、怎麼取回、核對過什麼，加上 2026-10-28 整理對它的影響。英文標題改成中文，tag 不改。原文在 `docs/history/RELEASE_NOTES_BEFORE_20261031/`，新的全文在 `releases_phase6.json`。發布後逐份從 GitHub 讀回，33 份都相同（GitHub 存說明時把換行改成 CRLF，比對時先統一換行）。說明裡的取回範例，下載量 130 MB 以下的 11 個照原樣實際跑過，全部 PASS；較大的沒跑，說明裡也不寫跑過。

**SEM 原圖的路徑。** 10 支會讀 SEM 原圖的程式（R69、R103、R113、R121、R127、R136 和 `PSF_Fitting/output/20260924_center9_psf/audit_sem_mapping.py`）寫死 `H:\From_2TB_D_disk\13_thesis\SEM_data`。那個資料夾的 25 個檔，在雲端都以同樣的相對路徑、同樣的 sha256 還原到 `Shared_Sources/SEM_Originals/`，所以改成專案內的這個位置（`manual_phase6_sem_originals.py`）。寫在報告文字裡的「原始 SEM：H:/…」是出處紀錄，照原樣留著；`Thesis_MOSR_Evidence` 裡兩份 R127 腳本是論文回顧的節錄副本，資料夾裡沒有它們需要的 `common.py`，也照原樣留著。記著這些程式雜湊的紀錄用 `rehash --phase 6` 帶過一次（`hash_changes_phase6.json`；這階段沒有搬家，`moves_phase6.json` 是空的）。

**雜湊連鎖的誤換。** R152 論文版獨立包自我核對時，有 2 個檔對不上。追下去是前幾階段的雜湊連鎖只看內容不看路徑：同一份內容放在兩個位置、只有一個位置被改寫時，所有寫著那個舊雜湊的地方都被換成新雜湊，包括配對著「沒被改寫的那個位置」的紀錄。全 repo 掃一遍（`manual_phase6_hash_chain_audit.py`），每一處找它在紀錄裡配對的路徑，那個檔如果還是舊內容，就把值改回舊雜湊（`manual_phase6_hash_chain_fix.py`）：改回 102 處，168 處本來就對，38 處配對不到路徑、照原樣留下（清單在 `hash_chain_phase6.json`）。`rehash` 跟著又把 10 處換錯，用同一支程式改回，之後不再用 `rehash`，改用按路徑更新的 `manual_phase6_path_rehash.py` 把三份路徑對照表（`REPOSITORY_FILES.json.gz`、`CURATED_FILE_MAP.json.gz`、`SOURCE_AVAILABILITY.json.gz`）帶到一致。最後逐筆核對這三份表裡在 git 的路徑：雜湊跟檔案不符的，main 上有 1,331 筆，現在 1,254 筆，沒有新增，77 筆是這次順便修好的；剩下的在整理之前就存在，因為這些表記的是固定 commit 的快照。`hash_changes_phase6.json` 本身也是照內容記的，用它的時候要注意同一個問題。

**已知差異。** R134 `native_calibration_replay.json` 與 R135 `reference_scope.json` 這兩份紀錄也存在 `research-results-models-20261016`，git 裡的版本這次多改了一個雜湊值。檔案本身在 git 裡，照 README 的方式取回時遇到內容不同的既有檔會停下，不會蓋掉 git 的版本，所以沒有為這兩個檔重換整份清單。

**只在本機的東西。** 下面這些不在 GitHub，交機前要由專案擁有者決定：

- 原工作區 sandbox 分支上沒提交的 52 個修改，以及 center9 Wiener 的 67 個圖表與數據檔（18.9 MB）。
- 10-28 盤點時照保存原則判斷不上傳的本機資料（原專案 368 GB、H 槽封存區 953 GB，大多是可以重新生成的訓練資料、逐張重建與中途模型）。

> 2026-11-05 補記：上面的 center9 圖表，以及下一節找到的論文圖、簡報原檔和各輪成品圖，已經補進 git 和 Release，見「交機前補件」。

**留下的外部路徑。** 程式裡還寫著 `H:\GMM_2_Final_Archive\…` 的，是當年為這台電腦的 H 槽寫的封存與清理工具（`Tools/assemble_verified_archive_collection.py`、`plan_research_*_archive.py`、`storage_cleanup_*_20260926.py` 等），以及 R130、R137–R140 把重建結果寫到 H 槽的準備腳本；它們交機後本來就跑不了，照原樣留著當紀錄。`d:/GMM_2_Final/` 只剩 13 處，都在註解裡的使用說明。

### 交機前補件：只在本機的圖與原檔（2026-11-05）

第 6 階段「再盤點一次」說 10-28 之後沒有新變成只在本機的檔。這句話只跟 10-28 的盤點比較，沒有回頭檢查 10-28 當時就判成只在本機、但照保存原則其實要留的檔。所以 11-04 從原工作區 `D:\GMM_2_Final` 重新逐檔比對：每個檔都去對 origin/main 的完整歷史（git blob）和 33 個 Release 的內容清單（sha256）。舊配置的路徑先照 `moves_phase*.json` 換成新樹路徑，補回的檔一律放回新樹裡原本的位置。

**小資料夾（825 個只在本機的檔）。**

- **進 git 的 600 個**：論文各章成品圖、簡報圖、`PSF_Fitting/quick_recalibration` 的簡報圖集、三倍率手動 ROI 預覽、各輪展示圖，以及少量 `.sql`、`.md`。main 上的導讀（例如 `IMAGE_GUIDE.txt`、`README_FIRST.txt`）原本就在介紹這些圖。逐檔核對過，進 git 後的內容跟原檔相同。
- **進 Release 的 224 個**：MATLAB `.fig` 原檔、BMP 重建輸出、權重，以及位在 main 的 `.gitignore` 排除位置（`runs/`、`weights/`、`reconstruct_progress_*`）的檔。
- **兩個 ZIP**：`Research_Design_Effect_Review_20260926.zip` 和 `PSF_Fitting_Tutorial.zip` 在 main 上已經有展開的資料夾，所以不傳整包，只補缺的 12 張 PNG 和 1 個 tiff。
- **不收**：12 份整理前的舊版說明，main 上已經有改寫路徑後的版本。

**112 個超過 50 MB 的大資料夾。** 扣掉 `.npz` 逐張陣列之後，比對了 94,000 個檔，其中 16,375 個（17.9 GB）不在雲端。

- **收進 Release**：
  - 報告或導讀以路徑引用的 119 個。只算 `.md`、`.txt`、`.html`、`.tex` 和圖表來源對照 JSON 裡的引用；推論完列出輸出檔的執行紀錄不算。
  - 放在 `figures/`、`reports/`、`Final_Data_Figures/` 這類成品圖資料夾的 743 個，含舊版論文圖。
  - `.fig` 原檔。
  - 表格和資料檔。
- **不收**：
  - 打包進去的 Python 執行環境和 `node_modules`，1,452 個。
  - 從論文 docx 轉出來的逐頁檢查圖，4,579 個、1.0 GB。
  - 沒有被報告以路徑引用的逐張結果圖，約 16 GB，主要是 R136、R135、R134。

  這三類照 `docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md` 在 2026-10-21 定的界線留在本機。

**Release `research-local-only-recovery-20261105`。** 共 1,157 個位置、1,091 個內容物件，打包成一個 568 MB 的附件，用 `Tools/research_asset_bundle.py` 打包。上傳前在本機跑過兩項檢查，都 PASS：`verify` 讀過每個物件，取回到空資料夾後逐檔比對 sha256。附件裡附了 `RESEARCH_ASSETS.json.gz`，`Tools/cloud_locator.py build` 會把它收進索引。

**逐檔紀錄。** 去處、理由、大小、sha256、新樹路徑和本機原位置都在 `TREE_RESTRUCTURE_20261028/local_only_recovery_20261105.tsv.gz`。

原工作區 sandbox 分支上沒提交的 52 個修改這次沒有動。逐檔比對的結果是：它們跟 main 相同、在 git 歷史裡、在 Release 裡，或是已被 main 上新版取代的舊稿。
