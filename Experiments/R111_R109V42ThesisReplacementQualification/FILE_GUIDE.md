# R111：R109 能不能取代論文用的 V42

[研究時間線](<../../docs/research/TIMELINE.md>) · [候選 R109](<../R109_StagedMidpointWidthScratch/FILE_GUIDE.md>) · [現任 V42](<../../LabSystem_MOSR/Experiments/V42_SoftLabelSNR/FILE_GUIDE.md>) · [GMF 差異拆解 R112](<../R112_V42R109GMFMechanismDecomposition/FILE_GUIDE.md>)

**一句話：** 2026-08-27 凍結 V42 第 120 輪與 R109 第 48 輪，保留論文的原圖選定母體與所有量測規則，把替換前需要的證據一格一格填滿：120 步位移、靜態中心九顆 CD、門檻穩健的 CD、20×／50× 邊緣、線條、共用 SEM 輪廓、切塊一致性、同一批影像的外部 GMF。用確定性 LSC 量的位移，兩者統計上相當；但外部 GMF 上 V42 穩定得多，所以 V42 維持論文模型，R109 留作泛化、暗曝光、線條與工程上更強的研究延伸。

| | |
|---|---|
| 結果 | **未採用**（內部量法相近，外部 GMF 較弱） |
| 時間 | 2026-08-27 |
| 實驗條件 | C：7 月的位移序列與 6/18 的靜態影像（論文第六章用的資料）；B：均華的外部 GMF |
| 比較對象 | V42 第 120 輪、R109 第 48 輪（都沒有重新訓練） |

## 讀這些內容要知道的事

1. **判定的優先順序**：SEM 完整輪廓、LSC 中心位移、外部 GMF 穩定度是主要結果；CD 只當尺寸相容性的次要證據，不主導決定。
2. **找到並修正一個量測問題。** Chan–Vese 交替曲率運算子是有狀態的，同一個裁切重複呼叫會在兩個答案之間交替，方法量測的先後順序會影響比較；修正後每顆柱、每個方法量測前都重設，抽查重複差異為 0。
3. **`results/thesis_displacement_r109/` 的稽核報告表頭寫「V42」，但內容是 R109**（7 月的稽核工具把候選欄固定命名為 V42）。
4. 外部 GMF 上的具體差距（均華 Y 步距標準差 V42 1.660 px、R109 4.538 px）寫在 [R112](<../R112_V42R109GMFMechanismDecomposition/FILE_GUIDE.md>)。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| R109 的論文位移稽核與圖 | 本資料夾 [results/thesis_displacement_r109/](<results/thesis_displacement_r109>)，已在 GitHub |
| 其他比較的程式 | 本資料夾 |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** SEM、CD、線條、切塊與外部 GMF 的比較結果表不在 GitHub 程式樹上。

## 原始報告

[README](<README.md>) 是這輪的結論入口。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R111_R109V42ThesisReplacementQualification.md>)。
