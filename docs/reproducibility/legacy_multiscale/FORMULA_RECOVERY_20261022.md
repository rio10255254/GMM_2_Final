# R13較早原公式已找回

2026-10-22。原先缺少的是**一版較早公式，影響9項總分**，不是9份量測表遺失。已從2026-03-11 12:10:09的原成功新增程式紀錄取回整份原碼；該版本早於13:18原摘要。14:31後的修改另有成功紀錄，說明為何後來保存的公式不同。

以找回的原程式，只取出原算分函式執行，9項原總分及27項分尺度分數全部相同。沒有用原分數反推係數，沒有改寫原表，也沒有重新執行模型評估。

| 方法組 | 當時模型 | 原總分＝原公式重算 |
|---|---|---|
| universal_sign_guard | checkpoint_0p8 | 247.742744743824 |
| universal_sign_guard | checkpoint_0p08 | 247.1961254775524 |
| universal_sign_guard | checkpoint_8px | -540.4219010770321 |
| universal_macro_lock | checkpoint_0p08 | -556.875625371933 |
| universal_macro_lock | checkpoint_0p8 | -557.1304162144661 |
| universal_macro_lock | checkpoint_8px | -559.8448080718517 |
| universal_balanced_bridge | checkpoint_0p8 | -559.190353512764 |
| universal_balanced_bridge | checkpoint_0p08 | -898.4025514423847 |
| universal_balanced_bridge | checkpoint_8px | -899.4902728199959 |

13:18原選擇仍是universal_sign_guard的0.8尺度模型；15:02是另一份原資料、公式與0.08尺度模型。兩次不互相替代，總分也不能跨公式直接作模型物理精度比較。

## 從GitHub重算

```powershell
python Tools/replay_legacy_multiscale_selection.py --root . --output NEW_LEGACY_SELECTION_VERIFICATION.json
```

更新後工具按原試跑分開使用早期／後期程式，輸入身分全部相符才計算；五次審查合計216項分數與5次原選擇皆可重算，舊9項公式缺口已為零。只用Python標準套件，不匯入訓練主程式。

[找回的原碼](recovered_sources/20260311_121009/GeoEdgeAlignSR_v1_UniversalCheckpointAudit.py)、[兩次原成功程式修改](ORIGINAL_FORMULA_EVENTS_20260311.json)、[9項逐值結果](FORMULA_RECOVERY_20261022.json)及[輸入身分](INPUT_IDENTITIES.json)均保存。此原碼由原新增內容還原成UTF-8／LF；沒有冒稱當年另有保存其原檔核對碼。

2026-10-21的[207項核對收據](NUMERIC_REPLAY_VERIFIED.json)仍保留當時真實範圍與缺件；本次新結果不回填舊收據。這證明既有評估數據如何算分和選擇，不能擴成所有舊GPU訓練或影像輸出已重新驗收。
