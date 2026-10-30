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
