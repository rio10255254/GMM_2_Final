clear; close all;

%% make GT with 0.125 um/pixel, canvas 901x901
img = im2double(imread("D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle_1201\Crop_circle_901_v2\VisionTop_20250903160550.bmp"));
% imshow(img)
%%
% 取亮暗值
% w = mean2(img(280:300,390:400));
w = 0.68;
b = mean2(img(2:20,2:20));

edge = 161;

% 建立 901x901 畫布，以 b 為底（單通道）
GT = zeros(901) + b;

% 中心座標
cx = 451; cy = 451;

% ===【上色步驟】==========================================================
% 同心圓（半徑 400，完全覆寫為 w）
alpha = 1;
[XX,YY] = meshgrid(1:901, 1:901);              % XX: column (x), YY: row (y)
circleMask = (XX - cx).^2 + (YY - cy).^2 <= 400^2;
GT(circleMask) = (1 - alpha) * GT(circleMask) + alpha * w;

% 兩個中心十字矩形（edge x edge），覆寫為 b
% 第一個：左上角在 (cx, cy)，大小 edge×edge
r1 = cy : (cy + edge - 1);
c1 = cx : (cx + edge - 1);
GT(r1, c1) = b;

% 第二個：左上角在 (cx-edge, cy-edge)，大小 edge×edge
r2 = (cy - edge) : (cy - 1);
c2 = (cx - edge) : (cx - 1);
GT(r2, c2) = b;
% ========================================================================

% 轉灰階（保險；若已單通道則無改變）
GT = im2gray(GT);

% === 最後疊上一層「原影像雜訊範圍」的隨機雜訊（混合，不覆蓋形狀）===
% if ndims(img)==3, imgg = im2gray(img); else, imgg = img; end
% bg   = imgg(280:300, 390:400);                 % 以背景小區塊估計雜訊上下限
% vmin = min(bg(:)); 
% vmax = max(bg(:));
% eta  = 0.35;                             % 雜訊混合係數（0~1），可依需求調整
% noiseFull = vmin + (vmax - vmin) * rand(size(GT));
% GT = (1 - eta) * GT + eta * noiseFull;   % 疊加雜訊，不會吃掉形狀

% GT = imnoise(GT,'gaussian',0,1e-2);    % （保留你的原註解行）
imwrite(GT, "PSF_Fitting/Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp")
imshow(GT)

% 簡化後：顯示 GT 與 img 的梯度差異圖
if ndims(img)==3, imgg = im2gray(img); else, imgg = img; end
[Gmag_GT, ~]  = imgradient(GT);
[Gmag_img, ~] = imgradient(imgg);

figure;
imagesc(Gmag_GT);
axis image; colorbar

figure;
imagesc(Gmag_img);
axis image; colorbar

figure;
imagesc(Gmag_GT - Gmag_img);
axis image; colorbar
title('Gradient Difference: GT - IMG');
