# lab/R61_BoundaryGeneralizationUniversal 研究與重做紀錄

[Lab逐輪必要來源與代表模型核對](<../round_source_reviews/LAB_SYSTEM_20261023.md>)

[直接查看這一輪的檔案分工](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>)

[全部實驗](../EXPERIMENTS.md) · [LabSystem：校正、資料與專屬模型](../routes/lab.md) · [現在保存到哪裡](../STATUS.md)

本卡保留原研究與當次保存紀錄；較晚的來源補件及缺件請以[目前狀態](../STATUS.md)為準。已建立閱讀卡不代表這一輪的全部來源已查完。

加入通用邊界、位移及Step保護形成v16

2026-10-22另整理[內部r36的原訓練、必要起點及96案例失敗](../lineage/R36_IDENTITIES_20261022.md)：當時用7,496組v10，不能用後來20,296組v16代替；內部編號也不是主專案R36。

保留歷版；3400早期來源及舊輪廓不能單靠新推算取代

## 必要來源

保留v1至v16的來源／失敗及固定起點；v16由3400組繼承來源與16896組新程序配對組成，合計20296組。繼承幾何必須凍結匯入，另保存seed6116、原step_guard_v16配方和實際分組；主專案R61是使用／驗證入口。

## 影像保存理由

保留同位置SEM、實拍、訓練答案與重建，以及錯亮暗方向／半量修正對照；SEM參與答案形成須同時標示，不能稱獨立SEM準確度。

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [原始報告：R61 boundary generalization progress - 2026-06-23](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/R61_PROGRESS_20260623.md>)
- [原始報告：Next Round Target Prompt - v15 Step Guard](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v15_step_guard/NEXT_ROUND_TARGET_PROMPT.md>)
- [原始報告：Previous Round Archive Index - v14 Motion Texture and Step Guard](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v15_step_guard/PREVIOUS_ROUND_ARCHIVE_INDEX.md>)
- [原始報告：R61 Next Round Handoff - v16](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v16_handoff/HANDOFF_README.md>)
- [原始報告：One-Shot Target Prompt For The Next Long Run](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v16_handoff/ONE_SHOT_NEXT_ROUND_TARGET_PROMPT.md>)
- [原始報告：Previous Round Organized File Map](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v16_handoff/PREVIOUS_ROUND_ORGANIZED_FILES.md>)
- [原始報告：Ready Checklist For The Next Round](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v16_handoff/READY_CHECKLIST.md>)
- [原始報告：v16 Implementation Status](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v16_handoff/V16_IMPLEMENTATION_STATUS.md>)
- [原始報告：R61 Next Round Handoff - post v16 full training](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/HANDOFF_README.md>)
- [原始報告：One-Shot Target Prompt For The Next Run](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/ONE_SHOT_NEXT_ROUND_TARGET_PROMPT.md>)
- [原始報告：One-Shot v17 Target Prompt After v16 Validation](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/ONE_SHOT_V17_TARGET_PROMPT_AFTER_V16.md>)
- [原始報告：Previous Round Organized File Map](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/PREVIOUS_ROUND_ORGANIZED_FILES.md>)
- [原始報告：Ready Checklist](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/READY_CHECKLIST.md>)
- [原始報告：v16 Full Training Status](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/V16_FULL_TRAINING_STATUS.md>)
- [原始報告：v16 Validation Results](<../../../LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/next_round_20260623_v17_post_v16_training_handoff/V16_VALIDATION_RESULTS.md>)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。

## 2026年10月16日保存核對

本輪入選的方法、設定、完整數值與代表影像已完成逐份內容核對並保存到GitHub；共用來源與先前移到H槽的歷史版本，按總入口的附件索引取回。

本次已實跑本輪的完整資料生成或保存觀測重算；實測範圍見總入口，並不表示重跑過所有歷史訓練。

D槽副本移除遭執行工具拒絕，本輪沒有因這次整理而被清理。

## 資料生產方法與共用來源

[本輪原生產／讀取程式、設定與修正紀錄](../GENERATION_GUIDE.md)已按實際來源確認；基礎來源：本輪獨立生成／原獨立生產包。可再生的大檔不必上傳整套。原絕對位置與固定內容身分供歷史追查，日後在新的研究副本設定自己的來源位置；新生成內容與原件不同時須保留差異，不改寫舊結果。

## 2026-10-22：這一輪在整條研究中的位置

[按R1至R153查找](../lineage/ROUND_NUMBER_MAP.md)／[本研究線的來源、得失與後續](../lineage/LAB_SYSTEM.md)。本輪上方已改為具體必要來源；原日期的保存、失敗與執行證據保留各自範圍，不以文件數或標號連續性冒稱全部歷史已重現。


---

[上一個閱讀入口：lab/R60_SEMTruthBoundaryTraining](lab__R60_SEMTruthBoundaryTraining.md) · [回本分區](../routes/lab.md) · [下一個閱讀入口：lab/R62_TargetSampleBoost](lab__R62_TargetSampleBoost.md)
