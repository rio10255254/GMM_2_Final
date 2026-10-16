# R105C 均華跨位置 N=4 可行性

完成 100 組相鄰位置配對。每組由位置 k 的兩張與位置 k+1 的兩張構成四觀測，鄰近位置先對齊到 k。

## 位移與對齊

- X 位移中位數：-0.0826 px
- Y 位移中位數：-7.8856 px
- ECC 中位數／最小值：0.999374 / 0.999349
- 對齊後結構相關中位數／最小值：0.998978 / 0.998945

## 幾何代價

- 融合中心漂移中位數／95 百分位：0.1021 / 0.2150 px
- 結構邊緣比例中位數：0.978432
- 半徑變化中位數：0.0092 px
- 徑向寬度變化中位數：-0.0032 px

## 位移波動代理

- N=2 每位置獨立，Y 步距標準差：0.1120 px
- N=4 滑動且相鄰輸出共用 50% 來源，Y 步距標準差：0.1133 px
- N=4 不共用來源、換算每位置，Y 步距標準差：0.0540 px

## 判斷

{
  "cross_position_registration_feasible": true,
  "fusion_preserves_ring_geometry": true,
  "sliding_gmf_is_biased_by_shared_sources": false,
  "eligible_for_model_research": true,
  "eligible_for_formal_gmf": false
}

跨位置四張在影像內容上可對齊並值得進入模型研究；滑動視窗是否能用於正式 GMF，必須由不共用來源的外部程式結果決定，不能直接引用共享視窗的低波動。