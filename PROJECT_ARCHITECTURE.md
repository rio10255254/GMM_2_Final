# 專案架構與決策規則

Last updated: 2026-10-24

這份文件只寫**穩定不變的設計與規則**：系統怎麼組成、模型怎麼運作、怎麼判斷好壞、什麼時候能升級或開新實驗。
即時狀態與結果看 [PROJECT_STATE.md](PROJECT_STATE.md)；機器可讀的正式身分看 [ESTIMATOR_POLICY.json](ESTIMATOR_POLICY.json)；縮寫看 [docs/README.md](docs/README.md) 的名詞表。

---

## 1. 系統在做什麼

顯微影像的邊緣因光學而模糊，使「圓在哪裡」的量測抖動。本專案訓練影像重建模型，目標**不是好看，而是讓位移、尺寸、輪廓量測更穩定**。

```text
光學校正(PSF_Fitting, MATLAB) ──► PSF
                                   │
   乾淨合成場景 ──用 PSF 弄糊、加雜訊──► 「糊圖 ↔ 乾淨圖」訓練配對
                                                  │
                                           訓練模型(Python)
                                                  ▼
 真實照片 ──► 模型重建 ──► 外部量測程式找圓心／輪廓 ──► 對照 PI 平台回授、SEM 尺寸
```

PSF 是物理先驗的唯一來源：它既用來製造訓練資料，也進入模型的物理模組，所以 PSF 準確度直接影響訓練品質。

### PSF 政策

- 自 2026-03-27 起，標準 PSF 是 2026-03-26 完成的 **Whole-FOV PSF**（全視野 100 個格點）；舊 PSF 保留作歷史對照，不刪除、不再當預設。
- 論文那組用 2026-09-24 擬合的**研究版 25 顆 PSF**（5×5 位置）。
- 切換理由與機器可讀版：[PSF_POLICY_TRANSITION_R26.md](docs/policy/PSF_POLICY_TRANSITION_R26.md)、[PSF_STANDARD_POLICY.json](docs/policy/PSF_STANDARD_POLICY.json)。
- 不要把舊 PSF 寫成唯一標準，也不要寫成新 PSF 在所有指標都更好。

---

## 2. 兩代模型

| | 第一代：共用主線 | 第二代：R148v2 → R152 |
|---|---|---|
| 名稱 | GeoEdgeAlignSR_v1_v5_NoCoord | R148v2、R152（論文稱 MOSR） |
| 身分 | **COMBO（正式基準）**、R33、R38v2、R39R40 | 論文採用 |
| 程式 | `Model/` | 各輪自帶（`Experiments/R14x…`、`Deliverables/R152_Standalone_*`） |
| 參數量 | 本文件未查證 | 1,207,105 |
| 資料 | `Training_Data/` 環形配對 | 768 母場景 × 4 視圖的合成資料 |

`Model/README.md` 只涵蓋第一代，不能當 R87 之後各獨立架構的入口。

### 2.1 第一代：GeoEdgeAlignSR

U-Net（編碼 48→96→192 通道，三次下採樣，解碼接 skip），核心想法是**不為好看而改變邊緣位置**。

| 部件 | 作用 |
|---|---|
| PSFDeconvPhysics | 在輸入端做 Wiener 反捲積，但只保守混合：`out = x + α(Wiener(x) − x)`，α∈[0.05, 0.35] |
| WeakPSFDeconvBlock | 解碼中段（H/2）選 4 顆代表 PSF，用小型 gating 網路混合，只作用低頻，混入比例 β≤0.10 |
| ShiftSafeUpsample | 雙線性放大＋固定高斯模糊，避免棋盤格偽影並保持平移等變性（影像移 1 像素，輸出就移 1 像素，這對位移量測至關重要） |
| OpticalBandpassFilter | 僅訓練時模擬顯微鏡頻率截止，抑制物理上不可能的細節 |

訓練入口 `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`；自動調參 `…AutoTuneTrain.py`；外部比較 `…ExternalGMF*.py`。
權重在 `Traing_Progress/training_progress_*/weights/`（資料夾拼字是歷史錯誤，**不可改名**）：`best_tradeoff`（綜合最佳，COMBO 即此類）、`best_detail_guarded`、`latest`。名叫 best **不等於**正式採用。
`Training_Data/tra_src_ring`、`tra_lbl_ring` 被 gitignore，用 `Data_Simulaion.py` + `PSF_Convolution.py` 重新生成。
「完整重新訓練」與「autotune 搜尋（12 epoch、提早驗證）」語意不同，搜尋約束不是模型本身。

### 2.2 第二代：R148v2 與 R152

放棄一個大 U-Net 包辦，改成**大範圍脈絡＋原尺寸精修**。

```text
x ─► 一次 U-Net 脈絡(24→40→64→40→24，輸出 16 通道) ─┐
 └───────────────► 三個原尺寸修正階段(各 64 通道、參數獨立、擴張 1/2/4/2) ─► y_base   (= R148v2，主體 1,194,406 參數)

R152：凍結 R148v2，再附加一條受限光學支路
x ─► 頻率統計 + FFT + 脈絡特徵 ─► 25 個 softmax 權重 ─► 25 顆 PSF 的受限反濾波加權融合 ─► iFFT ─► 小修正
y_R152 = clip( y_base + d·s·(x_PSF − x), 0, 1 )      d=1，s≈0.0138，模組內 β≈0.0120
```

- 只訓練新增的 12,699 個參數。兩個比例相乘約 0.000165，支路被**刻意設得很弱**。
- 抽查三張實拍，25 顆 PSF 權重幾乎均分（每顆約 0.04），模型並沒有學會「該用哪一顆」。
- 因此 R152 與 R148v2 的實拍數字極接近；R152 的意義是「論文需要的多 PSF 融合模組確實存在並參與輸出」，代價是約慢 2.2%、GPU 峰值多 0.34 GiB。
- 兩階段訓練：R148v2 從零 8192 次更新；R152 凍結它再 8192 次。不要說成全模型第二階段從零共同訓練。
- 合成資料：768 母場景（訓練 512／開發 128／測試 128），每場景 4 視圖；乾淨目標與邊界來自合成場景，**沒有把實拍 SEM 直徑當訓練標籤**。
- 部署倍率 d 在看實拍結果**之前**，用合成開發集預先對 {0, 0.25, 0.5, 0.75, 1} 檢查後決定。
- 推論：整張原生尺寸；記憶體不夠時用 512 核心／24 邊緣分塊。
- SEM 的外框幾何曾協助 PSF 校準，所以同九顆的 SEM 比較只是**校準條件下的一致性檢查**，不是獨立驗證。

細節與公式：[R152 完整紀錄](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_RAW_FULL_RECORD_20261002/REPORT.md)。

---

## 3. 怎麼判斷好壞

### 3.1 三條原則

1. **圖變清楚 ≠ 量得更準。** 視覺銳利與幾何定位是兩回事（R33 定位準但邊緣軟，就是警示）。
2. **內部分數只是入場券，外部量測才是裁判。** `seq_val`、`ann_seq`、deploy audit、process-audit 等只能篩選，通過不代表外部會好。
3. **合成分數不能代替真實拍攝。** 自 2026-09-08 起，新候選的每個短測就直接用真實顯微影像、SEM、真實位移序列、真實困難結構檢驗；合成資料可訓練，但不能當「先贏合成才准看真實」的關卡。SEM 的材料幾何、光學細節、實際位移三種答案資格分開；既有樣品不能重新命名為「未見確認」。完整契約：[R123 資料與驗證](Experiments/R123_RealFirstModelDesign/reports/R123_DATA_AND_VALIDATION.md)。

### 3.2 兩套考試

**考試 A：環形 + 外部 GMF（至 COMBO，約 2026-04）。** 外部 GMF 對整個環找亞像素中心，指標 `step_std = np.std(np.diff(PosY))`，越小越穩，看三個位移尺度：0.08、**0.8（主戰場）**、8 px。評估面向：整環幾何支撐、中心絕對穩定、相鄰影格位移一致、方向符號單調。
規則：原始標準差一律計入，**唯一例外**是 GMF 自己失敗的影格（z>5）；輪廓取樣 720 方向（不是 360）。方法論：[GMF_STEP_STD_METHODOLOGY.md](Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md)。
環形只是正式量測的**代理測試**，不等於全部科學目標；真正長期目標是各種顯微結構（線條、格線、曲線、缺口、刮痕、紋理）的邊界忠實重建，這條線（R39–R45）允許環形代理出現有限退步，但要進正式量測替代仍須回到外部 GMF 與專案擁有者判斷。

**考試 B：實拍 930 張 + PI + SEM（2026-09 起，論文）。** 2026-09-03 拍攝，30 趟 × 31 位置，每步約 1 µm，固定 3×3 九顆圓，約 172.5 nm／像素。

| 指標（nm） | 回答什麼 |
|---|---|
| **單趟 30 步合併波動**（主要指標） | 一次掃描走得平不平順 |
| 相鄰步相對 PI 差 | 影像位移與平台回授差多少 |
| 起點相對位移差 | 累積誤差 |
| 直徑／輪廓重拍波動 | 同一顆圓重拍 30 趟讀值抖多少（輪廓 720 方向；另有去尺寸形狀） |
| 與 SEM 差 | 準不準 |
| 時間、GPU 記憶體、參數 | 效率 |

信賴區間用**整趟重抽樣**（固定種子），因為同趟各步相關。
**兩套考試的數字、同一考試內不同的九顆彙整方式（R152 用中位數、R153 用算術平均）的數字都不能互比**，只在同一張表內比較。

### 3.3 讀報告的慣用語

「重拍穩定不等於絕對準確」「同樣本 SEM／同九顆只算一致性檢查」「單次實用比較不是穩定規律」「只留研究紀錄不升級」「已撤回（R119）」——這些限制句是結論的一部分，不可略去。

---

## 4. 角色與升級規則

| 角色 | 目前成員 |
|---|---|
| 正式基準 | **COMBO**（`r38v2_8px_gate_p95`，2026-04-08 生效；R33 Winsorize p95 + R38v2 序列訓練/8px 門檻/暖身） |
| 核准替代 | R33（定位極致）、R38v2（視覺優先）、R39R40_avg_a025（平衡；R39 與 R40 權重平均，2026-05-11） |
| 前任基準 | R30（`r30_b1_dironly`） |
| 開放支線 | R26NewPSFCheck（新 PSF 重訓，等外部 GMF；非主線） |
| 論文採用 | R152 / MOSR vs RAW（考試 B 的結果，不改變正式基準身分） |

### 升級條件（必須同時滿足）

1. 內部校準閘通過（pairmix 探針：`mid_center ratio > 0.25` 且 `mid_step < 0.45`；edge_band_refine 探針：`macro_step < 0.2995` 且 `macro_seq_sign > 0.7559`）。
2. 外部 0.8 px step_std **< 0.131560**（COMBO 的數字），或在特定部署下有明確的替代理由。
3. 8 px 大尺度不明顯退步。
4. 若 0.08 px 變好、0.8 px 變差，需有工程理由，不能互相抵銷。

升級與否由專案擁有者決定。候選達 `PASS_TRADEOFF` 以上時，另建議報告視覺指標（梯度大小、邊緣銳利度、對比、動態範圍）以防「GMF 過關卻視覺塌陷」。

### 何時值得開新實驗

- 值得：與現有失敗分支**不同**的新機制假說；在成功主線上可驗證且成本合理的微調；比較對象明確包含現行基準。
- 不值得：重掃已否定範圍（`step_mag` 以 0.35 切）；重開 R23/R24 型 fine-tune；只靠 internal gate 就假設 external 會好；沿用已 external FAIL 的方向（如 `r32_real_eq_finetune`）修補。

---

## 5. 穩定的結構邊界

| 區域 | 規則 |
|---|---|
| 根目錄共用主線（`Model/`、`PSF_Fitting/`） | 維護 R26/R30 的穩定流程：訓練、推論、稽核、外部比較；**不吸收**實驗專用 loader／launcher |
| `Experiments/R##_…` | 每輪自成一體，報告只在自己的 `reports/` 編輯；R32 沙盒已關閉保留（external FAIL） |
| LabSystem | `Thesis_MOSR_Evidence/LabSystem_MOSR/` 是獨立的成像條件與研究史；Lab R39 ≠ 主 R39，V42 ≠ 主 R42 |
| 共用原始資料 | `Shared_Sources/` 保存一次，各輪引用同一來源 |

細節、新實驗模板與命名：[docs/operations/STARTING_NEW_EXPERIMENT.md](docs/operations/STARTING_NEW_EXPERIMENT.md)；哪份才是正本：[SOURCE_OF_TRUTH_POLICY.md](docs/operations/SOURCE_OF_TRUTH_POLICY.md)；特殊路徑：[QUIRKS.md](docs/operations/QUIRKS.md)。

---

## 6. 保存與容量原則

- 資料分四層：活動中、正式保留、歷史封存、可重建內容。活動中的工作不得移動或刪除。
- 永久保護：正式基準與核准替代、相機原拍、正式 PSF、論文採用證據及其來源。
- 不可替代的來源（相機原拍、儀器量測、人工標記、完整實驗結果）必須原樣保存；可再生的大型訓練資料以**生成程式、設定、種子、環境、必要來源**保存，不要求整套上傳。
- 失敗或完成的實驗保留正式報告、manifest、採用權重、代表圖、輸入位置與重做方法。
- 外部封存先建含雜湊的清單，複製後驗證，再另行確認刪除目標。
- D 槽剩餘 <300 GiB 警告，<150 GiB 不開新長訓練。
- 研究保存檔保留原始位元組，Git 不自動轉換換行。

規則全文與取回方式：[PROJECT_STORAGE_AND_ARCHIVE_POLICY.md](docs/operations/PROJECT_STORAGE_AND_ARCHIVE_POLICY.md)、[docs/reproducibility/README.md](docs/reproducibility/README.md)。

> 本頁 2026-10-24 改寫前的原文逐位元組保留在 [PROJECT_ARCHITECTURE.md](docs/history/BEFORE_PLAIN_REWRITE_20261024/PROJECT_ARCHITECTURE.md)。
