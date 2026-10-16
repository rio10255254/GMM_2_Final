function normalized = normlz(x)
% NORMLZ 正規化函數，將輸入數據縮放到 [0,1] 範圍
% 輸入: x - 任意數值陣列（支援 gpuArray）
% 輸出: normalized - 正規化後的陣列

    normalized = (x - min(x(:))) ./ (max(x(:)) - min(x(:)) + eps);
end