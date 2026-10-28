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
| `edits_phaseN.jsonl`、`unresolved_phaseN.tsv`、`problems_phaseN.txt` | 各階段每一處改寫、工具無法決定的位置、無法讀取的檔 |
| `decisions_phaseN.json` | 工具無法決定的位置，人工判斷後的決定與理由 |
| `hash_changes_phaseN.json` | 各階段改寫後雜湊的變動（舊 sha → 新 sha），第 5 階段替換 Release 清單時用 |
| `verify_phaseN.txt` | 各階段驗證的結果 |

## 工具

- `Tools/restructure_tree.py`：每個階段的 `plan`、`apply`、`verify`，以及 `baseline`。
- `Tools/restructure_rules.py`、`restructure_resolve.py`、`restructure_text.py`、`restructure_python.py`、`restructure_hashes.py`、`restructure_verify.py`：規則、路徑解析、文字與 Python 改寫、雜湊連鎖、驗證。
- `Tools/check_markdown_links.py`：連結檢查，之後也會一直用。
- `Tools/handoff_inventory.py`：交機盤點，第 6 階段會再跑一次。

## 外部路徑（2026-10-28）

- 下載資料夾裡的 `20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903` 是目錄連結，指向專案的 `Shared_Sources/PI_Repeatability_20260903/raw`。程式裡寫成這個路徑的引用約 4,740 處，實際指的是專案內部，改成專案內的位置。
- `D:\NTU_ImageDataset`、`D:\NonSystemFiles\GMM2`、`H:\From_2TB_D_disk\13_thesis` 裡，內容已在雲端的 4,663 個檔、56 個資料夾，改成取回後的位置。NTU `Pitch1um_Y_100/Raw` 的 202 張全部對到 `Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw/`。
- 對不到的引用 682 處，見 `external_unmapped.tsv`。最大宗是 `C:\Users\Rio\Downloads\NTU_ImageDataset`（580 處）：那是公司序列更早放的位置，現在已經不在這台電腦上，無法用內容確認它和 `D:\NTU_ImageDataset` 是不是同一批，所以照原樣保留。

## 各階段

（每個階段完成後補上：搬了什麼、改寫數量、人工處理的位置、驗證結果。）
