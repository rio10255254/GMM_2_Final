# 檔案樹重整與交機 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 依設計把檔案樹整理成「一種角色一個家」，讓程式不綁這台電腦，讓 Release 清單和樹一致，最後用一份全新 clone 證明 GitHub 能自給自足。

**Architecture：** 先寫一組轉換工具（規則、解析、改寫、雜湊連鎖、驗證），每個階段用同一套工具，吃該階段的搬移規則 JSON，執行 `git mv`、改寫所有指向被搬位置的路徑與雜湊，再跑驗證。每階段一個 PR。Release 清單在第 5 階段用合成後的規則一次替換。

**Tech Stack：** Python 3（anaconda 環境）、`ast`、`sqlite3`（雲端索引）、`gh` CLI、pytest、git。

**Spec：** `docs/superpowers/specs/2026-10-28-tree-restructure-design.md`

## Global Constraints

- 工作目錄是 `D:\GMM_2_Final_restructure`。不碰 `D:\GMM_2_Final` 的工作樹（裡面有別人未提交的改動）。
- git 一律加 `-c gc.auto=0 -c maintenance.auto=false`。
- 提交前 `export PATH="/c/Users/Rio/anaconda3:/c/Users/Rio/anaconda3/Scripts:/c/Users/Rio/anaconda3/Library/bin:$PATH"`，不跳過 hook。
- 提交訊息結尾 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`；PR 說明結尾 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`。PR 用 merge commit 合併。
- 不做訓練或推論。不改 `ESTIMATOR_POLICY.json` 的模型身分，只改其中的路徑字串。
- 單位名稱（各輪、各包、各批次、各訓練紀錄的資料夾名）一律不改。
- Markdown 只改連結目標和路徑字樣，不改敘述文字。
- 雜湊只換「長度 64、完全等於某個被改寫檔舊 sha256」的值；git commit／blob 編號不改。
- 原貌標籤 `pre-restructure-20261028`，在第一個改內容的 PR（第 1 階段）合併前推上 GitHub。
- Release 原清單改名為 `RESEARCH_ASSETS.pre-restructure-20261028.json.gz`，`SHA256SUMS.txt` 改名為 `SHA256SUMS.pre-restructure-20261028.txt`。
- 任何上傳或修改 GitHub Release，先把清單給專案擁有者看，得到同意才執行。
- 不刪任何本機資料。搬移只發生在 git 追蹤的樹裡。
- 記錄這次轉換本身的檔案不套用轉換：`TRANSFORM_RECORDS = ('docs/operations/TREE_RESTRUCTURE_20261028.md', 'docs/operations/TREE_RESTRUCTURE_20261028/', 'docs/superpowers/specs/2026-10-28-tree-restructure-design.md', 'docs/superpowers/plans/2026-10-28-tree-restructure.md')`。理由：它們的內容就是舊路徑對新路徑的說明，改寫會讓它們失去意義。這是執行者的決定，殘留掃描用同一個常數。

## Review Focus

1. **同名不同物**：交付包內部的 `'/app/Traing_Progress'`、`'../Reconstruct_Progress'`、V42 包 `train_v42.py` 的 `"Traing_Progress"` 指的是包內資料夾，不能被改成專案路徑。測試在 Task 2。
2. **名稱前綴相同**：`Step` 和 `Step_analysis_20260623`、`20260704_20x` 和 `20260704_20x_5x_analysis`，只能在路徑段落邊界比對。測試在 Task 1。
3. **Windows 路徑的各種寫法**：`d:\gmm_2_final` 大小寫、`/` 和 `\` 混用、JSON 裡的 `\\`、`\\?\` 長路徑前綴、Markdown 連結裡的 `%20` 和 URL 編碼的中文（`位移`），都要認得，改寫後保留原本的分隔符號風格。測試在 Task 2。
4. **檔案格式不能被弄壞**：CRLF 檔（例如 `docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md`）、UTF-8 BOM、無法用 UTF-8 解碼的檔。前兩種位元組層級保留原樣，第三種跳過並列入報告。測試在 Task 3。
5. **同時在 git 和 Release 裡的文字檔被改寫**：新內容要補傳成新物件，新清單的 sha256 和 bytes 要指向新物件。測試在 Task 12。

---

## 檔案結構

| 檔案 | 責任 |
|---|---|
| `Tools/restructure_rules.py` | 搬移規則：讀 JSON、展開萬用字元、最長前綴對應、跨階段合成 |
| `Tools/restructure_resolve.py` | 路徑的世界（git 追蹤檔 + Release 路徑 + 本機盤點 + 目錄連結），把一個參照字串解析成舊樹位置，再依原風格寫回 |
| `Tools/restructure_text.py` | 非 Python 文字檔的改寫：Markdown、結果表與紀錄、`.json.gz`、MATLAB、PowerShell、批次檔、notebook |
| `Tools/restructure_python.py` | Python 的 `ast` 改寫（由 scratch 的 `feasibility.py` 的 `PyAnalyzer` 發展而來） |
| `Tools/restructure_hashes.py` | 雜湊連鎖更新到不動點 |
| `Tools/restructure_verify.py` | 路徑等價、殘留掃描、雜湊一致、虛擬樹、`.gitignore` 範圍檢查 |
| `Tools/restructure_tree.py` | CLI：`plan`、`apply`、`verify`，每階段一次 |
| `Tools/check_markdown_links.py` | 連結檢查，可記基準、可比對 |
| `Tools/handoff_inventory.py` | 交機盤點（由 scratch 版搬進來，第 6 階段會再跑） |
| `Tools/restructure_release_manifests.py` | 第 5 階段：產生新清單、改名舊清單、上傳、抽樣取回 |
| `docs/operations/TREE_RESTRUCTURE_20261028/moves_phase{2,3,4}.json` | 各階段搬移規則 |
| `docs/operations/TREE_RESTRUCTURE_20261028/external_map.json` | 外部檔 → 雲端恢復位置（第 0 階段算好） |
| `docs/operations/TREE_RESTRUCTURE_20261028/edits_phaseN.jsonl`、`hash_changes_phaseN.json`、`baseline/` | 每階段的改寫紀錄、雜湊變動、基準 |
| `docs/operations/TREE_RESTRUCTURE_20261028.md` | 操作紀錄本文 |
| `Tools/tests/test_restructure_*.py`、`Tools/tests/test_check_markdown_links.py` | 測試 |

規則 JSON 格式（每階段一份，座標是「該階段開始時的樹」）：

```json
{"phase": 3, "moves": [
  {"old": "Step_analysis_20260623", "new": "Analyses/Step_analysis_20260623"},
  {"old": "20260702_100MG_displacement_analysis/_r61_real_sample_runtime_*",
   "into": "Analyses/20260702_100MG_displacement_analysis/_r61_real_sample_runtime"}
]}
```

`old` 只有最後一段可以帶 `*`，搭配 `into` 表示「符合的子項各自原名搬進這個資料夾」。

---

## 第 0 階段：工具、基準、外部對應（分支 `restructure/phase0-tools`，從 `docs/tree-restructure-design` 分出）

### Task 1：搬移規則

**Files:**
- Create: `Tools/restructure_rules.py`
- Create: `docs/operations/TREE_RESTRUCTURE_20261028/moves_phase2.json`、`moves_phase3.json`、`moves_phase4.json`（內容照設計的「完整搬移對照表」，錄影那列不放，錄影在 Task 11 另外處理）
- Test: `Tools/tests/test_restructure_rules.py`

**Interfaces:**
- Produces:
  - `Rule(old: str, new: str)`（dataclass，repo 相對、`/` 分隔、無結尾斜線）
  - `RuleSet.map(rel: str) -> str | None`：最長前綴、段落邊界，未搬回 `None`
  - `RuleSet.moved_roots() -> list[str]`
  - `load_rules(path: Path, universe_names: Callable[[str], Iterable[str]]) -> RuleSet`：展開 `*`/`into`
  - `compose(rulesets: list[RuleSet]) -> Composed`，`Composed.map(rel) -> str | None` 依序套用，任一階段有搬就回最終位置

- [ ] **Step 1：寫失敗測試**

```python
def test_longest_prefix_wins():
    rs = RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR'),
                  Rule('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages', 'Deliverables/Standalone_Models')])
    assert rs.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/R129_x/README.md') == 'Deliverables/Standalone_Models/R129_x/README.md'
    assert rs.map('Thesis_MOSR_Evidence/LabSystem_MOSR/README.md') == 'LabSystem_MOSR/README.md'

def test_segment_boundary():
    rs = RuleSet([Rule('Step', 'Shared_Sources/Real_Sample_Captures/Step'),
                  Rule('20260704_20x', 'Shared_Sources/Real_Sample_Captures/20260704_20x')])
    assert rs.map('Step_analysis_20260623/a.py') is None
    assert rs.map('20260704_20x_5x_analysis/x.csv') is None
    assert rs.map('Step') == 'Shared_Sources/Real_Sample_Captures/Step'
    assert rs.map('Step/134822.bmp') == 'Shared_Sources/Real_Sample_Captures/Step/134822.bmp'

def test_phase4_traing_split(repo_rules_dir):
    rs = load_rules(repo_rules_dir / 'moves_phase4.json', lambda d: [])
    assert rs.map('Traing_Progress/training_progress_20260410/log.txt') == 'Experiments/Training_Runs/training_progress_20260410/log.txt'
    assert rs.map('Traing_Progress/organized_20260313/round01/a.py') == 'Experiments/Legacy/organized_20260313/round01/a.py'
    assert rs.map('Traing_Progress/README.md') == 'Experiments/Legacy/README.md'
    assert rs.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Traing_Progress/x') == 'LabSystem_MOSR/Traing_Progress/x'

def test_glob_into_expands_children():
    names = {'A': ['_r61_real_sample_runtime_001', '_r61_real_sample_runtime_002', 'report.md']}
    rs = load_rules_from_obj({'moves': [{'old': 'A', 'new': 'Analyses/A'},
        {'old': 'A/_r61_real_sample_runtime_*', 'into': 'Analyses/A/_r61_real_sample_runtime'}]}, names.get)
    assert rs.map('A/_r61_real_sample_runtime_001/x.json') == 'Analyses/A/_r61_real_sample_runtime/_r61_real_sample_runtime_001/x.json'
    assert rs.map('A/report.md') == 'Analyses/A/report.md'

def test_compose_runs_phases_in_order():
    c = compose([RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages', 'Deliverables/Standalone_Models')]),
                 RuleSet([Rule('Thesis_MOSR_Evidence/LabSystem_MOSR', 'LabSystem_MOSR')])])
    assert c.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages/p/a') == 'Deliverables/Standalone_Models/p/a'
    assert c.map('Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R47/x') == 'LabSystem_MOSR/Experiments/R47/x'
    assert c.map('Model/x.py') is None
```

`load_rules_from_obj(obj, names)` 是 `load_rules` 的記憶體版本，一起提供。`repo_rules_dir` fixture 指向 `docs/operations/TREE_RESTRUCTURE_20261028`。

- [ ] **Step 2：跑測試確認失敗** — `python -m pytest Tools/tests/test_restructure_rules.py -q`，預期 ImportError。
- [ ] **Step 3：實作 `restructure_rules.py`，寫三份規則 JSON。** `training_progress_*` 用 glob/into 規則表達，不寫特例程式。
- [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add restructure move rules`

### Task 2：路徑的世界與解析

**Files:**
- Create: `Tools/restructure_resolve.py`
- Test: `Tools/tests/test_restructure_resolve.py`

**Interfaces:**
- Consumes: `Composed.map`（Task 1）
- Produces:
  - `Universe.build(repo: Path, cloud_index: Path, local_inventory: Path | None, applied: Composed | None) -> Universe`。成員是 git 追蹤檔與其所有父資料夾、雲端索引裡的 Release 路徑（先經過已套用的階段規則對應）、本機盤點 TSV 中 `path` 欄的專案內路徑。`Universe.exists(rel) -> bool`，`Universe.children(rel) -> list[str]`
  - `Universe.junctions: dict[str, str]`：外部絕對路徑前綴 → 專案相對路徑。至少要有 `C:/Users/Rio/Downloads/20260902_100MF_uncertainty/20260903` → `Shared_Sources/PI_Repeatability_20260903/raw`（從盤點的 `.reparse.tsv` 讀）
  - `Ref(text: str, start: int, end: int, style: Style)`，`Style(sep: str, escaped: bool, kind: Literal['file_rel','root_rel','abs_project','abs_external'], drive_case: str)`
  - `resolve(text: str, source_rel: str, uni: Universe, external_map: dict[str,str]) -> Resolved | None`，`Resolved(target_rel: str, style: Style, exists: bool)`
  - `render(target_new_rel: str, source_new_rel: str, style: Style, mode: Literal['keep','root_rel']) -> str`

解析順序（執行者照做，不另做判斷）：

1. 絕對路徑：去掉 `\\?\`，大小寫不敏感比對 `<任一磁碟>:` 加 `GMM_2_Final`，或 `D:/GMM_2_Final_restructure`；命中就是 `abs_project`。否則查 `junctions`，再查 `external_map`，命中就是 `abs_external`。
2. 相對路徑：先試「相對於來源檔所在資料夾」，條件是第一段在那個資料夾下存在；不成立再試「相對於專案根目錄」，條件是第一段在根目錄存在，或是某條規則的來源頂層。
3. 解析到不存在的路徑時，以「最長的存在祖先」判斷它在不在搬移範圍內（執行時才產生的輸出資料夾靠這條）。

- [ ] **Step 1：寫失敗測試**

```python
def test_package_internal_names_stay_internal(uni):
    # uni 含 _deployment_package/GeoEdge_R26_正式交付版/Reconstruct_Progress/ 與根目錄 Reconstruct_Progress/
    r = resolve('../Reconstruct_Progress', '_deployment_package/GeoEdge_R26_正式交付版/app/run.py', uni, {})
    assert r.target_rel == '_deployment_package/GeoEdge_R26_正式交付版/Reconstruct_Progress'
    assert resolve('/app/Traing_Progress', '_deployment_package/GeoEdge_R26_正式交付版/app/run.py', uni, {}) is None
    r = resolve('Traing_Progress', 'Deliverables/R137_PSF100_V42_Select8_20260923/train_v42.py', uni, {})
    assert r.target_rel == 'Deliverables/R137_PSF100_V42_Select8_20260923/Traing_Progress'

def test_absolute_forms(uni):
    for s in [r'D:\GMM_2_Final\Traing_Progress\organized_20260313', 'd:/gmm_2_final/Traing_Progress/organized_20260313',
              r'D:\\GMM_2_Final\\Traing_Progress\\organized_20260313', r'\\?\D:\GMM_2_Final\Traing_Progress\organized_20260313']:
        assert resolve(s, 'Tools/x.json', uni, {}).target_rel == 'Traing_Progress/organized_20260313'

def test_render_keeps_style(uni):
    r = resolve(r'D:\\GMM_2_Final\\Traing_Progress\\organized_20260313', 'Tools/x.json', uni, {})
    assert render('Experiments/Legacy/organized_20260313', 'Tools/x.json', r.style, 'keep') == r'D:\\GMM_2_Final\\Experiments\\Legacy\\organized_20260313'
    assert render('Experiments/Legacy/organized_20260313', 'Tools/x.json', r.style, 'root_rel') == 'Experiments/Legacy/organized_20260313'

def test_markdown_encoded_link(uni):
    r = resolve('../20260702_100MG_%E4%BD%8D%E7%A7%BB_50x/a.bmp', 'docs/x.md', uni, {})
    assert r.target_rel == '20260702_100MG_位移_50x/a.bmp'
    assert render('Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x/a.bmp', 'docs/x.md', r.style, 'keep') == \
        '../Shared_Sources/Real_Sample_Captures/20260702_100MG_%E4%BD%8D%E7%A7%BB_50x/a.bmp'

def test_junction_and_external(uni):
    r = resolve(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260903\run01\a.bmp', 'Tools/x.py', uni, {})
    assert r.target_rel == 'Shared_Sources/PI_Repeatability_20260903/raw/run01/a.bmp'
    ext = {'D:/NTU_ImageDataset/Pitch1um_Y_100/Raw': 'Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw'}
    r = resolve(r'D:\NTU_ImageDataset\Pitch1um_Y_100\Raw\VisionTop_1.bmp', 'Tools/x.py', uni, ext)
    assert (r.target_rel, r.style.kind) == ('Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw/VisionTop_1.bmp', 'abs_external')
    assert resolve(r'E:\GmmVisionToolExe\run.exe', 'Tools/x.py', uni, ext) is None
```

測試用的 `uni` 用 `Universe.from_paths(paths, junctions)` 建（一起提供，給測試和 Task 7 用）。

- [ ] **Step 2：跑測試確認失敗。**
- [ ] **Step 3：實作 `restructure_resolve.py`。**
- [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add restructure path resolver`

### Task 3：非 Python 文字檔改寫

**Files:**
- Create: `Tools/restructure_text.py`
- Test: `Tools/tests/test_restructure_text.py`

**Interfaces:**
- Consumes: `resolve`、`render`、`Universe`（Task 2）；`Composed`（Task 1）
- Produces:
  - `Edit(file_old: str, file_new: str, line: int, old: str, new: str, kind: str, old_target: str, new_target: str)`
  - `Mode = Literal['moves', 'location']`：`moves` 套搬移規則（第 2–4 階段）；`location` 套原則 6（第 1 階段）
  - `rewrite_bytes(data: bytes, file_old: str, file_new: str, ctx: Context) -> tuple[bytes, list[Edit], list[str]]`，第三項是「無法處理」的說明。`Context(uni, rules, external_map, mode)`
  - 依副檔名分派：`.md .markdown .html .htm .txt .tex` 走文件規則；`.json .csv .tsv .yaml .yml .toml .ini .cfg .log .xml` 走紀錄規則；`.json.gz` 解壓後走紀錄規則再用相同壓縮等級寫回；`.m .ps1 .psm1 .bat .cmd .sh` 走腳本規則；`.ipynb` 的 code cell 走 Task 4 的 Python 規則，相對路徑以 notebook 所在資料夾為準
- `location` 模式的寫法（執行者照做）：
  - 紀錄與文件：`abs_project` 改成專案相對的 `/` 路徑；`abs_external` 改成恢復位置。
  - MATLAB：改成 `fullfile(PROJECT_ROOT, '<rel>')`，並在檔頭插入 `PROJECT_ROOT = <從 mfilename('fullpath') 往上 N 層>;`（函式檔插在函式內第一行）。
  - PowerShell：改成 `(Join-Path $ProjectRoot '<rel>')`，在 `param()` 之後插入 `$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '<..\ 重複 N 次>')).Path`。
  - 批次檔：改成 `%~dp0<..\ 重複 N 次><rel>`。
  - `C:\Users\Rio\anaconda3\python.exe` 這類直譯器路徑，在腳本規則裡改成 `python`；文件規則裡不動。

- [ ] **Step 1：寫失敗測試**

```python
def test_markdown_link_rewritten_narrative_kept(ctx_moves):
    src = '原名 `Traing_Progress`（歷史拼字）。見 [批次](../Traing_Progress/organized_20260313/README.md)。\n'.encode()
    out, edits, _ = rewrite_bytes(src, 'docs/x.md', 'docs/x.md', ctx_moves)
    assert out.decode() == '原名 `Traing_Progress`（歷史拼字）。見 [批次](../Experiments/Legacy/organized_20260313/README.md)。\n'
    assert len(edits) == 1

def test_crlf_and_bom_preserved(ctx_moves):
    src = b'\xef\xbb\xbfpath: Traing_Progress/organized_20260313/a.csv\r\nother\r\n'
    out, _, _ = rewrite_bytes(src, 'x.yaml', 'x.yaml', ctx_moves)
    assert out == b'\xef\xbb\xbfpath: Experiments/Legacy/organized_20260313/a.csv\r\nother\r\n'

def test_undecodable_reported_not_touched(ctx_moves):
    src = b'\xff\xfeT\x00r\x00'
    out, edits, problems = rewrite_bytes(src, 'a.txt', 'a.txt', ctx_moves)
    assert out == src and edits == [] and problems

def test_json_gz_roundtrip(ctx_moves):
    data = gzip.compress(json.dumps({'files': [{'path': 'Validations/a.json'}]}).encode(), compresslevel=9)
    out, _, _ = rewrite_bytes(data, 'docs/r/X.json.gz', 'docs/r/X.json.gz', ctx_moves)
    assert json.loads(gzip.decompress(out)) == {'files': [{'path': 'Deliverables/Validations/a.json'}]}

def test_location_mode_matlab(ctx_location):
    src = "img = imread('D:\\GMM_2_Final\\Shared_Sources\\a.bmp');\n".encode()
    out, _, _ = rewrite_bytes(src, 'Analyses_dir/sub/run.m', 'Analyses_dir/sub/run.m', ctx_location)
    assert "fullfile(PROJECT_ROOT, 'Shared_Sources/a.bmp')" in out.decode()
    assert "PROJECT_ROOT = fileparts(fileparts(fileparts(mfilename('fullpath'))));" in out.decode()

def test_location_mode_record_and_interpreter(ctx_location):
    out, _, _ = rewrite_bytes(b'{"model": "D:\\\\GMM_2_Final\\\\Model\\\\a.pth"}', 'r.json', 'r.json', ctx_location)
    assert json.loads(out) == {'model': 'Model/a.pth'}
    out, _, _ = rewrite_bytes(b'& C:\\Users\\Rio\\anaconda3\\python.exe Tools\\x.py\r\n', 'Tools/run.ps1', 'Tools/run.ps1', ctx_location)
    assert out == b'& python Tools\\x.py\r\n'
```

- [ ] **Step 2：跑測試確認失敗。**
- [ ] **Step 3：實作 `restructure_text.py`。** 換行與 BOM 在位元組層級保留：先偵測，用 `newline=''` 讀，處理後原樣寫回。
- [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add restructure text rewriter`

### Task 4：Python 改寫

**Files:**
- Create: `Tools/restructure_python.py`（以 scratch `feasibility.py` 的 `PyAnalyzer` 為起點；那份是 `C:\Users\Rio\AppData\Local\Temp\claude\D--GMM-2-Final\499bc111-1dea-4166-b4db-dfccdf2d77ed\scratchpad\feasibility.py`）
- Test: `Tools/tests/test_restructure_python.py`

**Interfaces:**
- Consumes: Task 2、Task 3 的 `Context`、`Edit`
- Produces: `rewrite_python(src: str, file_old: str, file_new: str, ctx: Context) -> tuple[str, list[Edit], list[Unresolved]]`，`Unresolved(file: str, line: int, segment: str, reason: str)`

規則：
- 能算出位置的路徑式（`__file__` 加 `.parent`／`.parents[N]`、`/`、`os.path.join`、`joinpath`、`Path(...)`），用舊位置算出目標，再對新位置重算，寫回各段字串或層數。`Path(__file__).parents[N]` 只在 N 必須改變時才改。
- 目標是新位置的子路徑時，把字串段拆成新段數：`ROOT / "Traing_Progress" / "organized_x"` 寫成 `ROOT / "Experiments" / "Legacy" / "organized_x"`。單一字串含 `/` 的就換整個字串。
- `location` 模式：字串常數裡的 `abs_project` 改成 `str(PROJECT_ROOT / '<rel>')`。如果檔案已經有某個名稱解析到專案根目錄，就沿用那個名稱；沒有的話，在最後一個 import 之後插入 `PROJECT_ROOT = Path(__file__).resolve().parents[N]`，需要時補 `from pathlib import Path`。`PROJECT_ROOT` 已被用作別的意義時改用 `_PROJECT_ROOT`。註解和 docstring 裡的絕對專案路徑改成相對路徑字樣。`subprocess` 參數裡的直譯器絕對路徑改成 `'python'`。
- 算不出來的（`PROJECT_ROOT / "Traing_Progress" / name` 這類動態尾段、根目錄可能是包根的 `os.path.join(PROJECT_ROOT, "Traing_Progress")`、清單常數裡的資料夾名）回報成 `Unresolved`，不自動改。

- [ ] **Step 1：寫失敗測試**

```python
def test_parents_level_changes_when_file_moves_deeper(ctx_moves):
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nX = ROOT / 'Model' / 'a.py'\n"
    out, edits, _ = rewrite_python(src, 'AnalysisLab/run.py', 'Analyses/AnalysisLab/run.py', ctx_moves)
    assert 'parents[2]' in out and "ROOT / 'Model' / 'a.py'" in out

def test_segments_split_to_new_prefix(ctx_moves):
    src = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\nB = ROOT / 'Traing_Progress' / 'organized_20260313'\n"
    out, _, _ = rewrite_python(src, 'Tools/x.py', 'Tools/x.py', ctx_moves)
    assert "ROOT / 'Experiments' / 'Legacy' / 'organized_20260313'" in out

def test_dynamic_tail_is_reported(ctx_moves):
    src = "import os\nPROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\nP = os.path.join(PROJECT_ROOT, 'Traing_Progress', name)\n"
    out, edits, unresolved = rewrite_python(src, 'Model/train.py', 'Model/train.py', ctx_moves)
    assert out == src and [u.line for u in unresolved] == [3]

def test_location_mode_inserts_root(ctx_location):
    src = "import json\nW = r'D:\\GMM_2_Final\\Model\\w.pth'\n"
    out, _, _ = rewrite_python(src, 'Experiments/R61_x/scripts/run.py', 'Experiments/R61_x/scripts/run.py', ctx_location)
    assert 'PROJECT_ROOT = Path(__file__).resolve().parents[3]' in out
    assert "W = str(PROJECT_ROOT / 'Model/w.pth')" in out
    compile(out, 'run.py', 'exec')
```

- [ ] **Step 2：跑測試確認失敗。**
- [ ] **Step 3：實作 `restructure_python.py`。** 改寫用原始碼的位置區段替換（`ast` 給行列），不重新產生整個檔案，以保留格式與註解。
- [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add restructure python rewriter`

### Task 5：雜湊連鎖

**Files:**
- Create: `Tools/restructure_hashes.py`
- Test: `Tools/tests/test_restructure_hashes.py`

**Interfaces:**
- Produces: `propagate(repo: Path, changed: dict[str, str], files: list[str], read: Callable, write: Callable) -> HashReport`。`changed` 是舊 sha → 新 sha。`HashReport(changes: dict[str,str], touched_files: list[str], rounds: int)`。在 JSON／`.json.gz` 裡，同一個物件內的 `bytes`、`size` 欄位一起更新；CSV／TSV 同一列同名欄位一起更新。每輪把被更新紀錄檔自己的新舊雜湊加進 `changed`，直到不再變動。

- [ ] **Step 1：寫失敗測試**

```python
def test_chain_reaches_fixed_point(tmp_repo):
    # a.md 被改寫：H_a -> H_a2；index.json 記 H_a 與 bytes；top.json 記 index.json 的雜湊
    rep = propagate(tmp_repo, {H_A: H_A2}, ['index.json', 'top.json'], read, write)
    assert json.loads(read('index.json'))['files'][0] == {'path': 'a.md', 'sha256': H_A2, 'bytes': 7}
    assert sha256_of('index.json') in read('top.json')
    assert rep.rounds == 2

def test_only_exact_64hex_tokens(tmp_repo):
    write('notes.txt', ('x' + H_A + 'y\n' + H_A[:63] + '\n').encode())
    propagate(tmp_repo, {H_A: H_A2}, ['notes.txt'], read, write)
    assert read('notes.txt') == ('x' + H_A + 'y\n' + H_A[:63] + '\n').encode()
```

（`x<64hex>y` 不在詞邊界，不換。）

- [ ] **Step 2：跑測試確認失敗。** - [ ] **Step 3：實作。** - [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add restructure hash propagation`

### Task 6：連結檢查與驗證

**Files:**
- Create: `Tools/check_markdown_links.py`（由 scratch `md_links.py` 擴充）
- Create: `Tools/restructure_verify.py`
- Test: `Tools/tests/test_check_markdown_links.py`、`Tools/tests/test_restructure_verify.py`

**Interfaces:**
- Produces:
  - `check_markdown_links.scan(repo: Path) -> list[Broken]`，`Broken(file, line, target)`；CLI `--write-baseline <json>`、`--compare <json> [--rules <phase json>...]`。比對時先用規則把基準裡的檔案與目標對應到新位置，有新增的壞連結就 exit 1。認 `](x)`、`](<x>)`、`%` 編碼；`#錨點` 與 `scheme:` 跳過。
  - `restructure_verify.equivalence(edits: list[Edit], old_uni, new_uni, rules) -> list[str]`（設計的驗證 3，含絕對改相對：新值用專案根目錄或 notebook 資料夾去接）
  - `residual(repo, rules, records=TRANSFORM_RECORDS) -> list[str]`（驗證 5：解析到舊位置的路徑數必須為 0；第 1 階段之後，可執行檔的字串裡出現 `GMM_2_Final` 絕對路徑或 anaconda 直譯器也算）
  - `hash_pairs(repo) -> set[tuple[str, str]]` 與 `hash_consistency(before_pairs, repo, rules) -> list[str]`（驗證 6：轉換前「紀錄檔 R 記著檔 F 的 sha」的每一對，轉換後 `map(R)` 必須含 `map(F)` 目前的 sha）
  - `virtual_tree(edits, local_inventory, rules) -> list[str]`（驗證 4：舊值在本機找得到的，新值在虛擬新樹也要找得到）
  - `gitignore_scope(old_gitignore: Path, new_gitignore: Path, local_paths: list[str], rules) -> list[str]`：對每個本機未追蹤路徑 P，比較舊規則下 P 的忽略結果和新規則下 `map(P)` 的忽略結果，兩者必須相同。用暫存 repo 加 `git check-ignore --no-index --stdin` 判斷。

- [ ] **Step 1：寫失敗測試**

```python
def test_compare_flags_only_new_breaks(tmp_repo):
    base = scan(tmp_repo)                      # 已有一個壞連結
    move(tmp_repo, 'AnalysisLab', 'Analyses/AnalysisLab')  # 不改連結
    assert compare(base, scan(tmp_repo), rules) != []
    rewrite_links(tmp_repo)
    assert compare(base, scan(tmp_repo), rules) == []

def test_gitignore_scope_detects_widening(tmp_path):
    old = '_deployment_package/\n'; new = 'Deliverables/Company_Packages/\n'
    paths = ['_deployment_package/GeoEdge_R26_正式交付版/w.onnx', 'Deliverables/MOSR_ONNX/m.onnx']
    assert gitignore_scope(write(old), write(new), paths, rules_phase2) == ['Deliverables/MOSR_ONNX/m.onnx']

def test_residual_ignores_transform_records(tmp_repo):
    write('docs/operations/TREE_RESTRUCTURE_20261028.md', '`Traing_Progress/organized_x` → `Experiments/Legacy/organized_x`')
    assert residual(tmp_repo, rules_phase4) == []
```

- [ ] **Step 2：跑測試確認失敗。** - [ ] **Step 3：實作兩支。** - [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add markdown link check and restructure verification`

### Task 7：CLI

**Files:**
- Create: `Tools/restructure_tree.py`
- Test: `Tools/tests/test_restructure_tree.py`（在暫存 git repo 上跑完整的 `plan → apply → verify`）

**Interfaces:**
- Consumes: Task 1–6 全部
- Produces，CLI：
  - `python Tools/restructure_tree.py plan --phase N` 不改任何檔，寫 `edits_phaseN.jsonl`（預定）與 `unresolved_phaseN.tsv`，印出各類數量
  - `apply --phase N`：依序做 `git mv`（第 1 階段不做）→ 改寫全部追蹤文字檔 → 雜湊連鎖 → 寫 `edits_phaseN.jsonl`、`hash_changes_phaseN.json`。`unresolved_phaseN.tsv` 裡有任何一列沒被人工處理（工具重掃仍算不出來，而且解析結果落在搬移範圍內）就拒絕執行
  - `verify --phase N`：跑 Task 6 的全部檢查，加上 `py_compile`、`Tools/validate_project_structure.py`，以及各組 pytest（`Tools/tests`、`Model/tests`、`PSF_Fitting/tests`、`AnalysisLab/tests`（第 3 階段後為 `Analyses/AnalysisLab/tests`）、`Thesis_MOSR_Evidence/tests`、各輪 `tests/`），結果和 `baseline/` 比較，只報新增的失敗
  - 共用參數：`--repo`（預設 `Path(__file__).resolve().parents[1]`）、`--cloud-index`（預設 `.cache/cloud_locator/index.sqlite`）、`--local-inventory`（D 槽專案盤點 TSV）、`--records-dir`（預設 `docs/operations/TREE_RESTRUCTURE_20261028`）

- [ ] **Step 1：寫失敗測試**：暫存 repo 放 `AnalysisLab/run.py`（`parents[1]`）、`docs/a.md`（連到 `../AnalysisLab/run.py`）、`docs/idx.json`（記 `docs/a.md` 的 sha），套一份只有 `AnalysisLab → Analyses/AnalysisLab` 的規則。斷言：`apply` 後檔案在新位置、`parents[2]`、連結改好、`idx.json` 的 sha 等於新 `docs/a.md`，而且 `verify` 結束碼為 0。
- [ ] **Step 2：跑測試確認失敗。** - [ ] **Step 3：實作。** - [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add restructure_tree CLI`

### Task 8：盤點工具、基準、外部對應，開第 0 階段 PR

**Files:**
- Create: `Tools/handoff_inventory.py`（scratch 版搬進來，參數不變，加上模組 docstring 說明用途）
- Create: `docs/operations/TREE_RESTRUCTURE_20261028/baseline/`（`links.json`、`validate.txt`、`pytest_<組>.txt`）
- Create: `docs/operations/TREE_RESTRUCTURE_20261028/external_map.json`、`external_unmapped.tsv`
- Create: `docs/operations/TREE_RESTRUCTURE_20261028.md`（先寫背景與規則檔說明，後面每階段補）

**Interfaces:**
- Produces：`external_map.json` 的格式為 `{"files": {"<外部絕對路徑, / 分隔>": "<恢復後的專案相對路徑>"}, "dirs": {...}}`。一個外部資料夾底下的每個檔，都要對應到同一個新資料夾前綴，這個資料夾才進 `dirs`。

- [ ] **Step 1：記基準。** 在 `main` 的乾淨 checkout 上跑 `python Tools/check_markdown_links.py --write-baseline …/baseline/links.json`、`python Tools/validate_project_structure.py > …/baseline/validate.txt`，以及各組 pytest。預期：數字記下來，不要求為零。
- [ ] **Step 2：算外部對應。** 對 `D:\NTU_ImageDataset`、`C:\Users\Rio\Downloads`（只算被引用的資料夾）、`D:\NonSystemFiles\GMM2`、`H:\From_2TB_D_disk\13_thesis\SEM_data` 跑 `Tools/handoff_inventory.py`（可沿用 scratch 的 `external_inventory.tsv` 與雜湊快取）。用 sha 到雲端索引查恢復路徑，同一 sha 有多個恢復路徑時，選和外部相對路徑尾段最長相同的那個。查不到的寫進 `external_unmapped.tsv`（含被引用次數）。檢查：NTU 的 `Pitch1um_Y_100/Raw/*` 全部對到 `Shared_Sources/NTU_Originals/Pitch1um_Y_100/Raw/*`。
- [ ] **Step 3：跑 `restructure_tree.py plan` 第 1–4 階段**（只產報告），確認各類數量和設計的實測數量同一個量級（文件約 1.2 萬、紀錄約 15 萬、Python 約 8,000、無法解析約 40、絕對路徑程式碼 2,379 行）。差距超過兩倍就停下來跟專案擁有者說明。
- [ ] **Step 4：提交、推送、開 PR**（含設計、計畫、工具、基準、外部對應），通過後合併。

---

## 第 1 階段：程式不綁這台電腦（分支 `restructure/phase1-location`）

### Task 9：打標籤、套用 location 模式

**Files:** 全樹（工具改寫）；人工：`unresolved_phase1.tsv` 列出的位置，以及讀取「絕對改相對」欄位的程式。

- [ ] **Step 1：打原貌標籤**：`git tag -a pre-restructure-20261028 origin/main -m "Tree before the 2026-10-28 restructure"`，然後 `git push origin pre-restructure-20261028`。確認 `gh api repos/rio10255254/GMM_2_Final/git/refs/tags/pre-restructure-20261028` 有回應。
- [ ] **Step 2：`plan --phase 1`**，逐列處理 `unresolved_phase1.tsv`，把結果直接改在程式裡。
- [ ] **Step 3：找讀取端。** 從 `plan` 的報告取出「值從絕對改相對」的 JSON 鍵名與 CSV 欄名，`git grep` 讀這些鍵的 Python，改成用專案根目錄去接（`PROJECT_ROOT / value`）。每改一處，就在 Task 4 的測試檔加一個這種讀法的案例。
- [ ] **Step 4：`apply --phase 1`，`verify --phase 1`。** 預期：殘留掃描裡，可執行檔寫死 `GMM_2_Final` 和直譯器的地方為 0；等價、雜湊一致、連結、測試都沒有新增失敗。
- [ ] **Step 5：補操作紀錄**（數量、人工處理清單、`external_unmapped.tsv` 的摘要），提交，開 PR，合併。

---

## 第 2 階段：封存與交付包（分支 `restructure/phase2-archive-deliverables`）

### Task 10：Archive 與 Deliverables

**Files:**
- `moves_phase2.json`
- Create: `Archive/README.md`、`Deliverables/README.md`、`Deliverables/{Company_Packages,Thesis_Handoffs,Standalone_Models,Data_Regenerators}/README.md`（每份說明這一層是什麼，每個單位一行；內容由執行者寫）
- Modify: `.gitignore`（照規則改寫，`gitignore_scope` 必須為空）

- [ ] **Step 1：`plan --phase 2`**，處理 unresolved。
- [ ] **Step 2：`apply --phase 2`。** `trial_README.md` 搬到 R128 後，如果和那裡的 `README.md` 重複，兩份都留，只在其中一份加一句說明。
- [ ] **Step 3：寫 README，改 `.gitignore`。**
- [ ] **Step 4：`verify --phase 2`**，包括 `gitignore_scope`（本機路徑取自 D 槽專案盤點）。預期全部沒有新增失敗。
- [ ] **Step 5：補操作紀錄，提交，開 PR，合併。**

---

## 第 3 階段：跨輪分析與只在 Release 的原拍（分支 `restructure/phase3-analyses-sources`）

### Task 11：Analyses、runtime 快照、Release-only README、phase_dft 圖

**Files:**
- `moves_phase3.json`（含兩個分析資料夾的 `_r61_real_sample_runtime_*` → `_r61_real_sample_runtime/` 規則，以及 `_build153`）
- Create: `Analyses/README.md`
- Create: `Shared_Sources/Real_Sample_Captures/README.md`，以及 `Step/`、`20260702_100MG_位移_50x/`、`20260704_20x/`、`20260704_5x/` 各一份 README；`Shared_Sources/PSF_Camera_Acquisitions/20260924/README.md`。格式照 `Shared_Sources/NTU_Originals/README.md`：裡面是什麼、哪個 Release、取回指令，指令裡的 `--prefix` 用新位置
- Add: `Analyses/20260702_100MG_phase_dft_analysis_matlab/` 底下那 10 張只在本機的 PNG（從 `D:\GMM_2_Final\20260702_100MG_phase_dft_analysis_matlab\` 複製，複製後核對 sha）

只在 Release 的原拍，在 git 樹裡沒有內容，所以這一階段不 `git mv` 它們，只做兩件事：讓解析世界裡的 Release 路徑經過規則對應，以便改寫指向它們的引用；在新位置放 README。Release 清單在第 5 階段才換。

- [ ] **Step 1：`plan --phase 3`**，處理 unresolved，確認 `Step/` 的引用沒有誤抓 `Step_analysis_20260623`。
- [ ] **Step 2：`apply --phase 3`**，寫 README，複製 PNG。
- [ ] **Step 3：`verify --phase 3`。** 預期全部沒有新增失敗；兩個分析資料夾第一層不再有 `_r61_real_sample_runtime_*`。
- [ ] **Step 4：補操作紀錄，提交，開 PR，合併。**

---

## 第 4 階段：Traing_Progress、LabSystem 上移、規則文件（分支 `restructure/phase4-legacy-labsystem`）

### Task 12：搬移與程式

**Files:**
- `moves_phase4.json`
- 人工：`unresolved_phase4.tsv`。已知的有：`Model/` 訓練器和 R75、R79、R83 的 `training/runtime/` 副本、`docs/history/TRAINING_LOG_WRITERS_20261021/` 裡的 `os.path.join(PROJECT_ROOT, "Traing_Progress")`；4 處 `PROJECT_ROOT / "Traing_Progress" / name`；`Tools/` 裡以清單常數寫資料夾名的保存工具。
- Modify: `Model/` 訓練器的預設輸出改成 `Experiments/Training_Runs/`；舊自動調參程式讀寫的 `organized_*` 改指 `Experiments/Legacy/`
- Create: `Experiments/Legacy/README.md`、`Experiments/Training_Runs/README.md`

- [ ] **Step 1：`plan --phase 4`，逐列處理 unresolved。** 每一處先判斷它的 `PROJECT_ROOT` 是專案根目錄還是包的根目錄：包根的不改，專案根的改。`name` 是批次名的去 `Legacy`，是訓練紀錄名的去 `Training_Runs`；兩者都可能的，用執行時的實際值判斷，寫成兩條明確的分支。
- [ ] **Step 2：在 `Model/tests` 加測試**：`test_default_training_output_dir`，斷言訓練器的預設輸出資料夾是 `<專案根>/Experiments/Training_Runs`。先跑一次確認失敗，改完再跑確認通過。
- [ ] **Step 3：`apply --phase 4`，寫兩份 README。**
- [ ] **Step 4：`verify --phase 4`。** 預期全部沒有新增失敗。

### Task 13：規則文件、驗證器、`.gitignore`

**Files:**
- Modify: `CLAUDE.md`、`AGENTS.md`、`docs/operations/QUIRKS.md`、`docs/operations/STARTING_NEW_EXPERIMENT.md`、`docs/operations/LEGACY_ROUNDS_OPERATIONS.md`、`docs/operations/SOURCE_OF_TRUTH_POLICY.md`、`PROJECT_ARCHITECTURE.md`、`README.md`、`PROJECT_STATE.md`、`Experiments/INDEX.md`、`.gitignore`
- Modify: `Tools/validate_project_structure.py`、`Tools/hooks/pre-commit`、`.github/workflows/validate-governance.yml`
- Test: `Tools/tests/test_validate_project_structure.py`

各文件要改的內容照設計的「要跟著改的規則文件」一節。新條文用提醒口氣，不用硬性規定的語氣。

- [ ] **Step 1：寫失敗測試**

```python
def test_legacy_and_training_runs_exempt_from_round_rules(tmp_project):
    make_dir(tmp_project, 'Experiments/Legacy/organized_20260313/round01')
    make_dir(tmp_project, 'Experiments/Training_Runs/training_progress_20260410')
    write(tmp_project, 'Experiments/Legacy/README.md'); write(tmp_project, 'Experiments/Training_Runs/README.md')
    assert not [e for e in validate(tmp_project) if 'Legacy' in e or 'Training_Runs' in e]

def test_missing_legacy_readme_is_reported(tmp_project):
    make_dir(tmp_project, 'Experiments/Legacy/organized_20260313')
    assert any('Experiments/Legacy/README.md' in e for e in validate(tmp_project))

def test_hardcoded_project_path_warns(tmp_project):
    write(tmp_project, 'Tools/x.py', "P = r'D:\\GMM_2_Final\\Model'\n")
    assert any('GMM_2_Final' in w for w in warnings(tmp_project))
```

`validate`／`warnings` 是測試檔裡對驗證器現有入口的包裝，照 `test_validate_project_structure.py` 的現有寫法。
- [ ] **Step 2：跑測試確認失敗。** - [ ] **Step 3：改驗證器、hook、workflow 和文件。** - [ ] **Step 4：跑測試確認通過，再跑 `verify --phase 4`。**
- [ ] **Step 5：補操作紀錄，提交，開 PR，合併。**
- [ ] **Step 6：更新記憶檔**：`C:\Users\Rio\.claude\projects\D--GMM-2-Final\memory\` 裡提到舊路徑的條目改成新位置（不在 git 裡，合併後做）。

### Task 14：錄影資料夾與上傳

**Files:**
- Create: `LabSystem_MOSR/control_program_recordings_20260924/README.md`（實驗室系統新控制程式的效果錄影，2026-09-24，三支、共 125 MB，檔名原樣，在哪個 Release、怎麼取回；寫明控制程式本身不在本專案）
- Selection：`{"reviewed": true, "files": [...]}`，三個檔的 `path` 是 `LabSystem_MOSR/control_program_recordings_20260924/<原檔名>`，`source` 是 `D:\GMM_2_Final\<原檔名>`

- [ ] **Step 1：把三個檔名、大小、預定的 Release 名稱 `labsystem-control-recordings-20261028` 給專案擁有者看，等同意。**
- [ ] **Step 2：`research_asset_bundle.py pack`（輸出到 repo 外）→ `publish_research_assets.py` 建草稿並上傳 → `download_research_assets.py` 取回 → `research_asset_bundle.py verify`。** 預期 3/3 雜湊相符。檔名含全形破折號和空白，要在 `restore` 後用 `Get-ChildItem` 確認檔名一字不差。
- [ ] **Step 3：發布**（`gh release edit … --draft=false --latest=false`），`cloud_locator.py build` 重建索引，查得到三個新路徑。
- [ ] **Step 4：提交 README，開 PR，合併。**

---

## 第 5 階段：Release 清單（分支 `restructure/phase5-release-manifests`）

### Task 15：清單替換工具

**Files:**
- Create: `Tools/restructure_release_manifests.py`
- Test: `Tools/tests/test_restructure_release_manifests.py`

**Interfaces:**
- Consumes: `compose`（Task 1，讀 `moves_phase2–4.json`）；各階段的 `hash_changes_phaseN.json`（合成成「最初 sha → 最終 sha」）；`research_asset_bundle.py pack`（打包補傳物件）
- Produces，CLI：
  - `plan --repo rio10255254/GMM_2_Final --out <repo 外資料夾>`：下載每個 Release 的 `RESEARCH_ASSETS.json.gz`，`path` 用合成規則對應；`sha256` 在雜湊變動表裡的，換成新 sha 和新 bytes，並把那個檔的現行內容打包成 `<tag>.restructure-20261028.zip`，新紀錄的 `asset` 指向它。每個 Release 寫 `summary.json`：`paths_changed`、`objects_added`、`sha_sets_equal_except_added: true/false`。沒有任何變動的 Release 標成 `unchanged`，不產生檔案。
  - `apply --tag T --plan-dir D`：依序執行 ① 用 `gh api -X PATCH repos/{repo}/releases/assets/{id} -f name=…` 把舊清單和 `SHA256SUMS.txt` 改名 ② 上傳補傳的 zip ③ 上傳新清單 ④ 上傳新的 `SHA256SUMS.txt`（含新清單、新 zip、改名後的舊清單）⑤ 核對每個新上傳附件的伺服器 sha256。②–⑤ 任何一步失敗，就把舊名稱改回來並結束。`BUNDLE_SUMMARY.json` 如果列出了附件，同樣先改名保留，再上傳更新版。
  - `verify --tag T --plan-dir D --sample 20`：取回到暫存資料夾，`restore` 的抽樣包括全部補傳物件，以及隨機挑選的搬移路徑，檢查檔案出現在新位置且 sha 相符。
  - 所有 `gh` 呼叫都經過可注入的 `run` 參數。

- [ ] **Step 1：寫失敗測試**（用假的 `run` 記錄呼叫）

```python
def test_plan_maps_paths_and_adds_rewritten_objects(fake_release):
    s = plan_one(fake_release, rules, {OLD_SHA: (NEW_SHA, 812)}, repo_reader)
    assert s['paths_changed'] == 2 and s['objects_added'] == 1 and s['sha_sets_equal_except_added']
    rec = next(r for r in s['manifest']['files'] if r['path'] == 'Deliverables/Validations/a.json')
    assert (rec['sha256'], rec['bytes'], rec['asset']) == (NEW_SHA, 812, 'T.restructure-20261028.zip')

def test_unaffected_release_untouched(fake_release_unmoved):
    assert plan_one(fake_release_unmoved, rules, {}, repo_reader)['status'] == 'unchanged'

def test_apply_renames_back_on_upload_failure(fake_gh_failing_upload):
    with pytest.raises(UploadFailed):
        apply_one('T', plan_dir, run=fake_gh_failing_upload)
    names = fake_gh_failing_upload.asset_names('T')
    assert 'RESEARCH_ASSETS.json.gz' in names and 'RESEARCH_ASSETS.pre-restructure-20261028.json.gz' not in names
```

- [ ] **Step 2：跑測試確認失敗。** - [ ] **Step 3：實作。** - [ ] **Step 4：跑測試確認通過。**
- [ ] **Step 5：提交** `feat(tools): add release manifest restructure tool`

### Task 16：執行替換

- [ ] **Step 1：`plan`。** 預期剛好 11 個 Release 有變動（設計裡列的那 11 個），其餘 21 個是 `unchanged` 或沒有路徑清單；每個有變動的 `sha_sets_equal_except_added` 都是 true。數量不同就停下來說明。
- [ ] **Step 2：把 11 個 Release 的 `summary.json`（路徑變動數、補傳物件數與檔名）給專案擁有者看，等同意。**
- [ ] **Step 3：先做 `research-lab-r61-r36-source-20261022`**：`apply` 後 `verify`，預期抽樣全部相符，`gh release view` 看得到改名後的舊清單。
- [ ] **Step 4：其餘 10 個逐一 `apply`、`verify`。**
- [ ] **Step 5：git 裡的收據。** 那 14 份提到 Release 清單的收據，凡是記著被替換清單 sha 的，用 `restructure_hashes.propagate` 套「舊清單 sha → 新清單 sha」。`cloud_locator.py build` 重建索引，抽查每個 Release 至少 3 條搬過的路徑查得到新位置。補操作紀錄，提交，開 PR，合併。

---

## 第 6 階段：交機前的最後檢查

### Task 17：假裝已經交機

- [ ] **Step 1：全新 clone**：`gh repo clone rio10255254/GMM_2_Final D:/GMM_2_Final_handoff_check`。之後只用這份 clone 和 GitHub。
- [ ] **Step 2：取回代表性資料**：930 張 PI 重拍的一趟、Step、NTU 一組序列加它的外部 GMF 包、PSF100、COMBO 和 R152 的模型，各用樹上 README 寫的指令取回。預期檔案落在 README 寫的位置，sha 和雲端索引相同。
- [ ] **Step 3：在 clone 裡跑第 7 項的測試組。** 再挑每種角色至少一支讀實拍或模型的分析腳本，只做讀取與路徑解析的乾跑，預期找得到剛取回的檔。不做推論。
- [ ] **Step 4：`python Tools/cloud_locator.py build`（clone 裡）**，抽查搬過的路徑，預期全部查得到。
- [ ] **Step 5：分支和標籤。** `D:\GMM_2_Final` 與 `D:\GMM_2_Final_restructure` 的每個本機分支和標籤，用 `git branch -r --contains` 或遠端同名分支確認在 GitHub 上找得到。找不到的列出來，給專案擁有者決定是推成救援分支還是放掉。
- [ ] **Step 6：再盤點一次。** 對 D 槽專案和 H 槽封存區重跑 `Tools/handoff_inventory.py`，和 2026-10-28 的結果比較，列出這段期間新出現、只在本機、依保存原則必須保存的檔。有的話給專案擁有者看，再決定是否上傳。
- [ ] **Step 7：收尾文件。** `docs/operations/TREE_RESTRUCTURE_20261028.md` 寫上交機檢查結果，以及留下的外部路徑和數量。`PROJECT_STATE.md` 寫明「交機後 GitHub 是唯一的家」和已知缺口；`ESTIMATOR_POLICY.json` 的註記、`Experiments/INDEX.md` 有需要就更新。提交，開 PR，合併。
- [ ] **Step 8：告訴專案擁有者**哪些東西要自己複製到外接硬碟（`H:\From_2TB_D_disk`、`D:\NonSystemFiles\GMM2` 沒用到的拍攝、中途產物、控制程式原始碼如果只在這台電腦上），以及可以刪除的暫存資料夾（`D:\GMM_2_Final_handoff_check`、各階段的 repo 外打包資料夾）。刪除由專案擁有者自己執行。
