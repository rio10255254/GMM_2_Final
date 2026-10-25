# Lab R62：針對目標樣品增補，兩天跑了 41 個候選

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R61](<../R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>) · [下一步 V41](<../V41_Standalone/FILE_GUIDE.md>) · [V42](<../V42_SoftLabelSNR/FILE_GUIDE.md>)

**一句話：** 拿 R61 v16 當起點，把 7/2（100MG）和 7/4（20×、5×）拍的位移影像加進訓練，想讓模型在論文要用的樣品上位移量得更穩。2026-07-05～07 兩天內從 V1 試到 V41，過程中先後抓到「權重根本沒動」、「重複結構讓位移答案錯」、「平台本身的壞步混進訓練」三個問題；最後沒有一個訓練出來的網路明顯贏過原圖，當時採用的是**外部固定混合**：90% 原圖加 10% V7 重建（`anchor_blend10`，後來包成 V24）。這輪累積的 11,254 組資料包成了 V41 的訓練資料。

| | |
|---|---|
| 結果 | **研究候選**（沒有訓練出可升級的網路；固定混合輸出在論文位移分析中當作保守的重建模式） |
| 時間 | 2026-07-05～07-07 |
| 實驗條件 | C：實驗室顯微系統；目標樣品是 7/2 的 100MG 序列與 7/4 的 20×、5× 序列（各有 1 µm、0.5 µm 兩種步距） |
| 起點 | Lab R61 v16 最佳權重 |

> **兩套編號別搞混：** 訓練候選是 V1～V41（例如 V7、V24、V28），資料包是 v1～v14（例如 `v4_motion_clean`、`v13_measurement_view_safe_teacher`）。V41 用的是**資料包 v13**，不是**訓練候選 V13**。資料包 v14 是 V42 短測用的柔化答案資料。

## 在研究裡的位置

Lab R61 的 v16 有了通用邊界和位移保護，但在論文要用的幾組實拍位移序列上沒有明顯優勢。R62 改成直接拿這些目標樣品加強訓練。之後 V41 把這兩天的探索整理成一條「從 R61 v16 起步、一次訓練」的正式路線，V42 再從 V41 出發。

## 這輪在問什麼

在目標樣品上加訓練，能不能讓重建後的位移量測比原圖更穩，又不破壞其他倍率？

## 怎麼做，以及一路發現的問題

1. **V2、V3：權重幾乎沒動。** 加了 1,500 組目標樣品的假邊界答案（V2），再加 1,200 張真實連續位移影像（V3），重建結果卻跟 R61 一模一樣（平均差不到 0.00001 灰階）。原因有兩個：假答案是 R61 老師做出來的，邊界位置跟 R61 一樣；開啟混合精度（AMP）時權重實際上幾乎不更新。
2. **真實位移的答案本身有錯。** 樣品是重複的柱陣列，相位比對會鎖到旁邊那顆一樣的柱子，例如指令走了 −14.6 px，量出來只有 −0.08 px。所以改成「自我位移」資料：用真實影像當紋理，自己做已知的次像素位移（V4、V5）。
3. **V7 才真的更新。** 關掉 AMP、修正檔名讓位移配對讀得到、把序列幾何損失接到新資料上，學習率 3e-7。V7 是這輪的主力網路，但它會把邊界變得太銳。
4. **平台壞步。** 100MG 0.5 µm 序列在第 27、31 步有平台自己跳動的壞步，影響 66 組訓練資料；清掉之後做成乾淨資料包（V11），但沒有贏過 V7。
5. **改量法也改目標。** 加入成對（pairwise）GMF 量法，避免長序列追蹤時特徵越來越少；V12、V13 加入邊界中心位移約束；之後一路試到 V41（形狀守門、多倍率原圖守門、量測視角老師……），都是 1 輪、幾百批次的短探針。
6. **改走固定混合。** 既然網路改不太動位移、又容易把影像改壞，就測「原圖為底、只加一點重建」：`anchor_blend10`（90% 原圖＋10% V7）與 `anchor_detail035`（原圖加上 0.35 倍的重建高頻細節）。這是對所有影像都一樣的固定規則，不是逐張校正。

## 結果

**100MG 邊緣相位位移**（步距中位數／標準差，µm）——原圖幾乎看不到指令位移，混合後恢復：

| 序列 | 原圖 | `anchor_blend10` |
|---|---|---|
| 100MG 1 µm | 0.030／0.434 | 1.006／0.011 |
| 100MG 0.5 µm | 0.052／0.406 | 0.500／0.051 |

**GMF 量法**（標準差，µm；5× 用方塊形狀的 ROI）——幾乎跟原圖一樣，5× 0.5 µm 小幅改善：

| 序列 | 原圖 | `anchor_blend10` | 改善 |
|---|---:|---:|---:|
| 100MG 1 µm | 0.009391 | 0.009392 | −0.01% |
| 100MG 0.5 µm | 0.052039 | 0.052010 | +0.06% |
| 20× 1 µm | 0.025569 | 0.025489 | +0.32% |
| 20× 0.5 µm | 0.076249 | 0.076219 | +0.04% |
| 5× 1 µm | 0.158455 | 0.158290 | +0.10% |
| 5× 0.5 µm | 0.013996 | 0.012896 | +7.86% |

同樣用方塊 ROI 時，R61 v16 單獨使用會把 5× 的方塊形狀改壞（平均改善 −70%）。影像品質上，`anchor_blend10` 與原圖的相似度 0.998，只多一點細節。

## 讀這些數字要知道的事

1. **相位位移恢復不代表每個局部圓心都更準。** 邊緣相位量法上的大幅改善，在 GMF 局部中心量法上幾乎看不到；兩種量法量的是不同東西。
2. **0.5 µm 序列的波動主要來自平台。** 原圖和重建後的逐步位移相關係數 0.99994，模型能改的量大約只有 0.0005 µm，序列本身的標準差約 0.052 µm。
3. **好的結果是外部混合，不是網路本身。** V24 把 `anchor_blend10` 寫進模型檔的設定裡，但模型參數就是 V7；V29 同樣是 V28 加上固定的 detail 模式。想讓網路自己學會這個行為的 V23，會在 5× 方塊上產生點狀假影。
4. **短探針不代表完整訓練。** V8～V41 大多是 1 輪、120～500 批次，報告每次都寫「不值得長訓練」。
5. **ROI 選擇會改變結論。** 同一張 100MG 影像不同 ROI 的改善從 −1% 到 +4.6%；5× 用固定 ROI 時重建影像會失敗，所以才另外做方塊 ROI。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 各版決策報告、GMF 評分、量法研究 | 本資料夾 [reports/](<reports/README.md>)，已在 GitHub |
| 兩個固定輸出模型（V24＝V7＋blend10，V29＝V28＋detail35） | [packaged_checkpoints/](<../../Traing_Progress/packaged_checkpoints/README.md>)，已在 GitHub；也可以用 [`Tools/rebuild_r62_anchor_checkpoint.py`](<../../../../Tools/rebuild_r62_anchor_checkpoint.py>) 從 V7／V28 重建（參數與設定相同，檔案不逐位元組相同） |
| V7、V28 原始權重 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |
| 資料包建置、訓練、重建、GMF 評分程式 | 本資料夾 [scripts/](<scripts/README.md>)、[tests/](<tests>)；固定混合工具在 `Tools/Displacement_Algorithms/scripts/motion_preserving_fusion.py` |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 14 版資料包與 V1～V41 所有訓練資料夾只在原電腦上，依保存原則不全部上傳；雲端保存的是代表模型、兩個固定輸出模型、程式與全部報告。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [目標增補稽核](<reports/R62_TARGET_BOOST_AUDIT_20260705.md>) | V2、V3 為什麼權重沒動 |
| [自我位移決策](<reports/R62_SELFSHIFT_TRAINING_DECISION_20260705.md>)、[序列／位移稽核](<reports/R62_SEQGEOM_MOTION_AUDIT_20260705.md>) | 重複結構造成錯誤位移答案、AMP 問題、V7 的設定 |
| [V8 成對 GMF](<reports/R62_V8_GMF_PAIRWISE_PROGRESS_20260706.md>)、[V11 乾淨資料](<reports/R62_V11_motion_clean_GMF_summary_20260706_TW.md>)、[V12／V13](<reports/R62_V12_V13_GMF_probe_summary_20260706_TW.md>) | 量法修正、平台壞步、位移約束 |
| [錨點融合](<reports/ANCHOR_FUSION_DECISION_20260706.md>)、[detail035](<reports/ANCHOR_DETAIL035_DECISION_20260706.md>)、[目前最佳重建決策](<reports/BEST_CURRENT_THESIS_RECON_DECISION_20260706.md>) | 固定混合怎麼來、為什麼選 blend10 |
| [V23／V24](<reports/V23_V24_ANCHOR_TEACHER_DECISION_20260706.md>)、[V25](<reports/V25_SAFE_SHAPE_ANCHOR_READOUT_20260706.md>) | 想讓網路自己學會混合行為的嘗試 |
| [量測方法研究](<reports/measurement_method_research_20260706/METHOD_RESEARCH_READOUT_20260706.md>) | 7/6～7/7 比較相位、ECC、GMF、形狀邊緣等量法 |

其他 GMF 評分資料夾的完整清單在 [reports/README.md](<reports/README.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R62_TargetSampleBoost.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
