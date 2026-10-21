# R43 近期候選堪用性盤點

## 目的

這不是訓練輪次，而是一次近期候選堪用性盤點。目標是把 COMBO、已核准替代、R39、R40、R41、R42 放在同一張表裡，判斷哪些模型能正式討論、哪些只能作顯微研究或人工檢查、哪些暫時沒有使用價值。

## 設計

- 不新增訓練資料。
- 不改模型。
- 不重新訓練。
- 讀取近期各輪已完成的 canonical 結果檔，並納入 R42 後補的外部 GMF。
- 用同一套分類規則輸出 JSON、CSV 與中文分析報告。
- 另外整理肉眼檢查圖，讓顯微特徵與邊界重建差異可以直接看。

## 主要結論

- COMBO 仍是正式 baseline。
- R39 a030 是近期最接近正式替代討論的候選。
- R42 full endpoints 是目前最有顯微邊界重建價值的研究候選，但外部 GMF 補測確認不能直接取代正式量測流程；最佳外部候選 `r42_r41_best` 仍退步 8px +24.6%、0.8px +94.3%、0.08px +98.9%。
- R40/R41 證明顯微細節能力可被推起來，但目前更適合作為能力來源。
- R42 低比例混合版守住舊能力時，新能力太弱，暫時不值得使用。

## 產物

- 報告：`reports/R43A_USABILITY_AUDIT.md`
- 分數表：`results/candidate_usability/usability_scorecard.json`
- CSV：`results/candidate_usability/usability_scorecard.csv`
- 肉眼檢查圖：`results/visual_review/`

## 重跑方式

```powershell
python Experiments\R43_CandidateUsabilityAudit\scripts\candidate_usability_audit.py
python -m pytest Experiments\R43_CandidateUsabilityAudit\tests\ -q
```
