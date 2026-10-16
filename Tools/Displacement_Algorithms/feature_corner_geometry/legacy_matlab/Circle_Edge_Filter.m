%% ================= 可調整參數區 =================
imgPath     = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle\Crop_circle_901\VisionTop_20250903160735.bmp";
rMin        = 200;     % imfindcircles 搜尋半徑下限 (px)
rMax        = 500;     % imfindcircles 搜尋半徑上限 (px)
sensitivity = 0.90;    % 圓偵測靈敏度 (0.85~0.95)

delta_in    = 2;      % 遮罩往內縮 (px) : r_in = r - delta_in
delta_out   = 16;      % 遮罩往外擴 (px) : r_out = r + delta_out

% 估計代表灰階時的取樣帶厚度（避免邊緣污染）
innerSampleBand = 12;  % 在 r_in 內側往回取樣厚度 (px)
outerSampleBand = 16;  % 在 r_out 外側往外取樣厚度 (px)
expandIfEmpty    = 8;  % 若取樣帶無有效像素時的自動擴張 (px)

% 羽化過渡寬度（控制過渡的「柔和」程度）
feather_in  = 8;       % 內區由 r_in 向內過渡的寬度 (px)
feather_out = 10;      % 外區由 r_out 向外過渡的寬度 (px)

% 顯示固定尺度（避免顯示端歸一化）
gradMaxDisp = 1020;    % 8-bit 梯度保守上限 (Sobel 約 4*255)
% =================================================

%% Step 0: 讀取原圖（保持 8-bit），另備 double 做運算（不縮放到[0,1]）
img_u8 = imread(imgPath);
if size(img_u8,3) > 1, img_u8 = rgb2gray(img_u8); end
img_d  = double(img_u8);   % 0~255 尺度

%% Step 1: 自動偵測圓
[centers, radii, metric] = imfindcircles(img_u8, [rMin rMax], ...
    'ObjectPolarity','bright','Sensitivity', sensitivity);
if isempty(centers)
    error('沒找到圓，請調整 rMin/rMax 或 Sensitivity。');
end
[~, idx] = max(metric);
cx = centers(idx,1); cy = centers(idx,2); r = radii(idx);

%% Step 2: 幾何區域與座標
[H,W] = size(img_u8);
[X,Y] = meshgrid(1:W, 1:H);
R     = hypot(X - cx, Y - cy);

r_in  = max(1,  r - delta_in);
r_out = min(max(H,W), r + delta_out);

innerMask = (R <= r_in);
ringMask  = (R >  r_in) & (R <  r_out);
outerMask = (R >= r_out);

%% Step 3: 估計各區域代表灰階（中位數；取樣帶避開邊緣）
% 內側取樣帶：[r_in - innerSampleBand, r_in)
innerBand = (R >= max(1, r_in - innerSampleBand)) & (R < r_in);
innerVals = img_d(innerBand);
if isempty(innerVals)
    innerBand = (R >= max(1, r_in - innerSampleBand - expandIfEmpty)) & (R < r_in);
    innerVals = img_d(innerBand);
end
if isempty(innerVals), innerVals = img_d(R < r_in); end
g_inner = median(innerVals, 'omitnan');

% 外側取樣帶：(r_out, r_out + outerSampleBand]
outerBand = (R > r_out) & (R <= min(max(H,W), r_out + outerSampleBand));
outerVals = img_d(outerBand);
if isempty(outerVals)
    outerBand = (R > r_out) & (R <= min(max(H,W), r_out + outerSampleBand + expandIfEmpty));
    outerVals = img_d(outerBand);
end
if isempty(outerVals), outerVals = img_d(R > r_out); end
g_outer = median(outerVals, 'omitnan');

%% Step 4（已移除）：不做梯度強邊篩選，圓環完整保留原圖

%% Step 5: 羽化過渡權重（線性夾取；避免新邊緣）
% 內區：w_in = clamp((r_in - R)/feather_in, 0..1)
w_in  = zeros(H,W);
if feather_in > 0
    w_in = (r_in - R) / feather_in;
    w_in = max(0, min(1, w_in));
end

% 外區：w_out = clamp((R - r_out)/feather_out, 0..1)
w_out = zeros(H,W);
if feather_out > 0
    w_out = (R - r_out) / feather_out;
    w_out = max(0, min(1, w_out));
end

%% Step 6: 生成輸出（8-bit 尺度；圓環保持原值；內外區羽化到代表灰階）
img_out_d = img_d;  % 起始為原圖
% 內區：由 r_in 邊界向內，逐步平滑到 g_inner
img_out_d(innerMask) = (1 - w_in(innerMask)) .* img_d(innerMask) + ...
                        w_in(innerMask)     .* g_inner;

% 圓環：ringMask 保留原圖，不動

% 外區：由 r_out 邊界向外，逐步平滑到 g_outer
img_out_d(outerMask) = (1 - w_out(outerMask)) .* img_d(outerMask) + ...
                        w_out(outerMask)     .* g_outer;

% 夾限並轉回 uint8
img_out_d = max(0, min(255, img_out_d));
img_out_u8 = uint8(round(img_out_d));

%% Step 7: 檢視（固定尺度；避免顯示端歸一化）
G_before = imgradient(img_d);            % 原圖梯度 (8-bit 尺度)
G_after  = imgradient(double(img_out_u8)); % 羽化後影像的梯度

figure('Name','Feathered Region Masking','Color','w');
subplot(2,3,1); imshow(img_u8, [0 255]); title('原圖 (8-bit)');
hold on; viscircles([cx cy], r, 'Color','y');

subplot(2,3,2); imshow(innerMask); title('內區 (R \le r_{in})');
subplot(2,3,3); imshow(outerMask); title('外區 (R \ge r_{out})');

% subplot(2,3,4); imshow(G_before, [0 gradMaxDisp]); colormap(gca,'jet'); colorbar;
subplot(2,3,4); imshow(G_before, []); colormap(gca,'jet'); colorbar;
title('原圖梯度 (固定尺度)');

subplot(2,3,5); imshow(img_out_u8, [0 255]); title('羽化後影像 (8-bit)');
% subplot(2,3,6); imshow(G_after,  [0 gradMaxDisp]); colormap(gca,'jet'); colorbar;
subplot(2,3,6); imshow(G_after,  []); colormap(gca,'jet'); colorbar;
title('羽化後梯度 (固定尺度)');

%% Step 8: 儲存（8-bit BMP；不做任何重新歸一化）
outPath = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle\Crop_circle_901\GradFilter_Output\masked_image_8bit.bmp";
imwrite(img_out_u8, outPath, 'bmp');
fprintf('已輸出：%s\n', outPath);
