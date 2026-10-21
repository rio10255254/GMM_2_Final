# R113 模型與訓練影像超深度剖析

## 最終答案

R109 的主要瓶頸不是模型太小，也不是 patch 不夠大。真正原因是：邊界／修正需求控制器已經死亡、資料以邊界像素計算時嚴重失衡、width/shift 同時收到互相衝突的訊號、超過一半訓練樣本在要求保持原圖，而部分 mixed-hard 標籤從單張輸入本來就不可辨識。

## 最重要發現

1. 正式 boundary AUC 僅 0.496，輸出固定在 0.508；簡單固定特徵分類器卻能達到 0.870。因此是訓練失敗，不是輸入沒資訊。
2. dense array只佔 7.6% 記錄，卻佔 67.7% 邊界權重；它本身又是最難辨認的family。
3. 展開資料後，clear/identity實際佔 54.7%；clear樣本在shift head上的總梯度是退化樣本的 5.92 倍，而且方向相反。
4. width target在width head與renderer backbone都是最大梯度來源；contour與gradient在width head上的方向餘弦達 -0.982，代表兩者幾乎正面衝突。
5. mixed-hard即使使用真實midpoint與polarity，來源輪廓IoU中位仍只有 0.337；可對齊的真實高頻只剩 6.8% 左右。
6. 90%有效視野半徑約 41.8px、99%約 56.1px；放大patch不會根治控制器與loss問題。

## 下一步

先做一個小型 boundary/SDF/confidence microprobe：重新正規化每張影像的邊界權重、降低clear pairing、把dense array獨立配額化，並讓controller在renderer階段持續更新。只有這個controller確實學出空間分離與跨退化穩定性，才值得啟動完整新模型。
