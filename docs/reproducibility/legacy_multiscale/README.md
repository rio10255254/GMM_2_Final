# 早期多尺度實驗：為什麼方法排名和實際選中的模型不同

這裡補充2026年3月11日至12日的Round12–15。這些是早期研究歷程，不改變現在正式COMBO基準或R152／RAW論文身分。完整原報告、未採用模型、途中影像及失敗保留；較早和較晚的試跑分開閱讀。

## 方法如何演進

| 輪次與原紀錄 | 當時試圖解決什麼 | 實際如何選擇 | 必須保留的限制 |
| --- | --- | --- | --- |
| Round12，20260311_023449 | 希望0.08、0.8、8像素位移都能表現穩定 | 五組方法先分別在三個尺度訓練；`universal_sign_guard`方法組排名第一，再依當時規則優先取該組0.8尺度模型 | 三個尺度的組合分數來自三份模型，不能說一份模型已通過三尺度測試 |
| Round13，20260311_150225 | 補上前一輪「同組三模型」與「一份可用模型」之間的落差 | 先排六組方法，再把前三組各自的三份模型固定下來，逐份測三尺度。最後是`universal_sign_guard`的0.08尺度模型，總分−87.21851635836065 | 0.8尺度是主要篩選條件，不代表最後一定選0.8尺度模型。較早13:18試跑另有不同選擇，不能互換 |
| Round14，20260311_174207 | 把0.8尺度列為主要目標，同時檢查8尺度是否退步、0.08尺度是否仍可用 | 五組方法初排以`corridor_microbridge`最高；前四組固定模型再查後，選中`corridor_macrobridge`的0.8尺度模型，總分−125.30187479518355 | 初排第一的方法組沒有成為最後採用模型；只留下初排冠軍會丟失真正決策脈絡 |
| Round15，20260312_022742 | 再加重0.8尺度中心穩定性，同時約束其他兩尺度 | 四組方法；`centerlock_pure`初排最高。四組固定模型審查的最高分完全相同，均為−125.82125443819912；原排序保留`centerlock_pure`的0.8尺度模型 | 原程式以穩定排序保留原先順序，所以這是同分時延續前一排序，不能宣稱固定模型總分證明pure勝過其餘三組，更不能據此推定四組權重相同 |

上述分數是原程式用多項內部指標和門檻合成的選擇分數；負數照原值保存。它們不是外部GMF位移標準差，也不是實際物理誤差或絕對準確度。

固定模型審查是只評估而不訓練，原設定會重設評估輪數；其中`best_epoch=0`不能解讀成原模型從未訓練。原摘要保留的`NaN`也不能改成零或當作通過。

## 固定模型的確切身分

下列是原檔名的辨識片段；完整舊路徑仍保存在原JSON中。恢復後的根目錄可以不同，不需要原本的D槽。

| 最後一份相應輪次摘要 | 原訓練資料夾辨識片段 | 模型檔 |
| --- | --- | --- |
| Round12 | `ST0p8_SWP_usg_20260311_022337` | `weights/best_tradeoff.pth.tar` |
| Round13 15:02 | `ST0p08_SWP_usg_20260311_143757` | `weights/best_tradeoff.pth.tar` |
| Round14 17:42 | `ST0p8_SWP_cmb_20260311_173108` | `weights/best_tradeoff.pth.tar` |
| Round15 | `ST0p8_SWP_clp_20260312_021219` | `weights/best_tradeoff.pth.tar` |

不要把較早13:18或16:42試跑的模型，替換進上表較晚摘要。完整保存全部模型的理由，就是讓採用與未採用的路徑都可追查。

## 小型數字重算與實測界線

取回本專案程式與原JSON後，僅使用Python標準套件便能執行：

```text
python Tools/replay_legacy_multiscale_selection.py --root . --output NEW_LEGACY_SELECTION_VERIFICATION.json
```

[輸入身分清單](INPUT_IDENTITIES.json)固定原程式及五次審查JSON；工具只取出原程式的三個算分函式，不匯入訓練入口，也不訓練模型。2026-10-21實測結果：207個分數重新計算吻合，五次原本的選擇都能由各自原分數排序重建。[原數字核對](NUMERIC_REPLAY_VERIFIED.json)／[實際GitHub取回與禁止舊位置讀取的收據](GITHUB_REPLAY_VERIFIED.json)。

**2026-10-22已補回：Round13較早20260311_131800的原公式。** 從原成功新增程式紀錄取得，9個總分及27個分尺度分數全部相同，沒有反推係數或覆寫原表。更新後重算工具按各次原版計算216項分數與5次原選擇，較早13:18仍取0.8尺度模型，較晚15:02另取0.08模型。[原碼、逐值結果及來源](FORMULA_RECOVERY_20261022.md)。上方207項與九項缺口是2026-10-21當時實測，舊收據不回填。

上述實測重做的是「如何由既有評估數據算分與選擇」，沒有重新產生這些評估數據，也沒有重跑歷史訓練或宣稱全部模型的實際影像輸出已重現。原始影像、完整表格、模型與數值陣列的保存覆蓋，另由[全專案保存入口](../project_completion/README.md)逐批核對。

## 原始依據

- [Round12三尺度方法組初排](../../../Experiments/Legacy/organized_20260311/selected/reports/ROUND12_UNIVERSAL_MULTISCALE_SUMMARY_20260311_023449.md)
- [Round13較晚方法組初排](../../../Experiments/Legacy/organized_20260311/selected/reports/ROUND13_UNIVERSAL_MULTISCALE_SUMMARY_20260311_150225.md)與[固定模型審查](../../../Experiments/Legacy/organized_20260311/selected/reports/ROUND13_UNIVERSAL_CHECKPOINT_AUDIT_SUMMARY_20260311_150225.md)
- [Round13較早審查原值](../../../Experiments/Legacy/organized_20260311/selected/reports/ROUND13_UNIVERSAL_CHECKPOINT_AUDIT_SUMMARY_20260311_131800.md)
- [Round14較晚方法組初排](../../../Experiments/Legacy/organized_20260311/selected/reports/ROUND14_CORRIDOR_MULTISCALE_SUMMARY_20260311_174207.md)與[固定模型審查](../../../Experiments/Legacy/organized_20260311/selected/reports/ROUND14_CORRIDOR_CHECKPOINT_AUDIT_SUMMARY_20260311_174207.md)
- [Round15方法組初排](../../../Experiments/Legacy/organized_20260312/selected/reports/ROUND15_CENTERLOCK_MULTISCALE_SUMMARY_20260312_022742.md)與[固定模型審查](../../../Experiments/Legacy/organized_20260312/selected/reports/ROUND15_CENTERLOCK_CHECKPOINT_AUDIT_SUMMARY_20260312_022742.md)
- [原審查程式](../../../Model/GeoEdgeAlignSR_v1_UniversalCheckpointAudit.py)及[Round15排序與啟動程式](../../../Model/GeoEdgeAlignSR_v1_LongRunCenterLock.py)
