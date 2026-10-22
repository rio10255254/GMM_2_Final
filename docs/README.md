# 文件入口

第一次閱讀請從[研究閱讀與取得指南](reproducibility/GETTING_STARTED.md)開始；不知道內容屬於哪個資料夾，查[專案地圖](navigation/PROJECT_MAP.md)。研究結論只回到[目前狀態](../PROJECT_STATE.md)及各輪正式報告。

## 文件樹

```text
docs/
├── navigation/          專案地圖：資料夾角色與正式位置
├── reproducibility/     方法、文獻、來源、每輪閱讀與按需取得
│   ├── lineage/         R1–R153、LabSystem與歷史分支沿革
│   ├── experiments/     各現有研究範圍的閱讀卡
│   ├── scratch_lineage/ R89–R93方法與資料修正
│   ├── r93_shared/      R93停止結果與五輪共用來源
│   ├── four_rounds/     R94／95／97／98原歷程與限制
│   ├── lab_comparisons/ Lab數學平移、V42歷史與原數表
│   ├── legacy_multiscale/ 早期R12–R15選模及公式缺件
│   ├── optical_calibration/ 光學原結果與頻譜來源
│   └── project_completion/ 精選範圍與歷次保存收據
├── analysis/            跨研究路徑總覽
├── evidence/            論文穩定引用副本；原實驗報告優先
├── policy/              光學等專項政策
├── operations/          開新實驗、位置相容、容量與恢復規則
├── history/             按原日期閱讀的研究敘事及舊版入口
└── archive/             小型歷史快照；其中進行中狀態不是今日待辦
```

## 三種用途分清楚

| 用途 | 看哪裡 | 如何使用 |
|---|---|---|
| 理解研究 | [逐輪](reproducibility/EXPERIMENTS.md)、[沿革](reproducibility/lineage/README.md)、[文獻](reproducibility/LITERATURE_GUIDE.md) | 先讀問題、方法、完整結果和失敗，再找程式 |
| 在新位置重做所需部分 | [生成方法](reproducibility/GENERATION_GUIDE.md)、[附件選擇](reproducibility/ASSET_GUIDE.md) | 先確認原拍／人工來源與可生成資料的差別，只取必要來源 |
| 維護與查證歷史 | [操作說明](operations/README.md)、[歷史](history/README.md)、[保存紀錄](reproducibility/project_completion/README.md) | 固定舊收據按原日期及範圍閱讀，不當成現在的工作指示 |

`presentations_assets`保存簡報素材，`runtime`只留舊執行位置說明，`superpowers`內本次保存的少數設計／計畫按原身分閱讀，不能以資料夾原先被忽略推定它完全沒有Git內容。這些不是新的正式實驗區。

來源相同而位置不同時，按[正式來源規則](operations/SOURCE_OF_TRUTH_POLICY.md)找原件；不要把引用副本當成第二份可各自改寫的結論。
