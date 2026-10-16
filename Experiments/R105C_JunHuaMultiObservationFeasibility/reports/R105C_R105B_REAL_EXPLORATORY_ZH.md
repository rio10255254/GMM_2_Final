# R105C 使用 R105B 探針的真實跨位置探索

R105B was trained only on procedural 96x96 data. Real blur, exposure and illumination parameters were not estimated; physics selection used identity nuisance settings. These outputs are not a model validation or delivery result.

- N=1 中心變化中位數：0.1052 px
- N=2 中心變化中位數：0.1061 px
- 跨位置 N=4 中心變化中位數：0.1051 px
- N=2 邊緣比例中位數：1.1061
- 跨位置 N=4 邊緣比例中位數：1.1078
- N=4 相對 N=2 的平均變化：0.0980 灰階
- N=4 不確定性中位數：2.1048 灰階

## 判斷

{
  "cross_position_changes_output": true,
  "cross_position_center_not_worse_than_n2": true,
  "cross_position_edge_not_worse_than_n2": true,
  "eligible_for_real_model_adaptation": true,
  "eligible_for_external_gmf": false
}

這只能確認跨位置四張能被現有概念探針讀取，以及輸出是否出現明顯幾何破壞；不能用來聲稱真實重建變準。