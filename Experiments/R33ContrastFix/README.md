# R33 Contrast Fix — W_STAT 提高（已否定）

## 假說

R33 p95 的視覺「糊」來自 contrast 壓縮（-44%）。提高 W_STAT（0.05→0.30）
讓模型更強力匹配 label 的 mean/std → 恢復 contrast。

## 結果：失敗

W_STAT 提高後 contrast 反而更差（-14% vs R33 的 -5%），因為 training label
本身的局部 std 很低（9.19），更強的 matching 壓模型往低 std 走。

## 結論

W_STAT 不是恢復 contrast 的正確旋鈕。R33 的「糊」90% 是真正的邊緣平滑（steepness -22%），
不是 contrast 問題。Post-processing contrast stretching 也只恢復 2pp。

## 分支

`sandbox/r33-contrast`
