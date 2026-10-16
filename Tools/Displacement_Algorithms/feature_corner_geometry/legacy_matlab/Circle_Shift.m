clear; close all;

%% ================= 參數區（請視需要調整） =================
imgPath     = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Crop_circle_901_v2\VisionTop_20250903160550.bmp";
outDir      = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Crop_circle_901_v2\VisionTop_20250903160550_imfindcircle.bmp";

rMin        = 200;      % imfindcircles 半徑搜尋下限 (px)
rMax        = 500;      % imfindcircles 半徑搜尋上限 (px)
sensitivity = 0.90;     % 0.85~0.95，越高越容易找到弱邊

tryBothPolarities = true;   % true: 同時嘗試 'bright' 與 'dark'，取 metric 較大者
methodPhaseCode    = true;  % 若版本支援，使用 'Method','PhaseCode'（對模糊邊更穩健）

% 平移後的畫布大小：預設 = 原圖大小；若想改大或改小可自定
useOriginalCanvasSize = true;  % true: 對齊到原圖大小的正中央
% ===========================================================


%% ================ 讀圖（保留原始 8-bit） =================
orig_u8 = imread(imgPath);
if size(orig_u8,3) > 1
    gray_u8 = rgb2gray(orig_u8);
else
    gray_u8 = orig_u8;
end
[H,W] = size(gray_u8);
if ~exist(outDir,'dir'); mkdir(outDir); end

% 供偵測與顯示的 double（仍以 0~255 尺度，不重縮放到 0~1）
gray_d = double(gray_u8);

%% ================== 以 imfindcircles 找圓 ==================
% 構造共同參數
commonArgs = {gray_u8, [rMin rMax], 'Sensitivity', sensitivity};
if methodPhaseCode
    commonArgs = [commonArgs, {'Method','PhaseCode'}]; %#ok<AGROW>
end

bestCenter = []; bestRadius = []; bestMetric = -Inf; bestPol = '';

if tryBothPolarities
    pols = {'bright','dark'};
else
    pols = {'bright'};  % 若你確定是亮圓
end

for k = 1:numel(pols)
    args = [commonArgs, {'ObjectPolarity', pols{k}}];
    try
        [C, R, M] = imfindcircles(args{:});
    catch
        % 若版本不支援 'Method','PhaseCode'，退化為預設方法
        argsFallback = args;
        if methodPhaseCode
            % 去掉 'Method','PhaseCode'
            idx = find(strcmp(argsFallback,'Method'));
            if ~isempty(idx)
                argsFallback(idx:idx+1) = [];
            end
        end
        [C, R, M] = imfindcircles(argsFallback{:});
    end

    if ~isempty(C)
        [mMax, idxMax] = max(M);
        if mMax > bestMetric
            bestMetric = mMax;
            bestCenter = C(idxMax,:);
            bestRadius = R(idxMax);
            bestPol    = pols{k};
        end
    end
end

if isempty(bestCenter)
    error('imfindcircles 未偵測到圓；請調整 rMin/rMax 或 sensitivity，或檢查極性。');
end

cx = bestCenter(1);  cy = bestCenter(2);  r = bestRadius;
fprintf('偵測到圓：center=(%.2f, %.2f), R=%.2f, metric=%.4f, polarity=%s\n', ...
    cx, cy, r, bestMetric, bestPol);

%% ================ 建立平移（將圓心對到畫布中心） ================
if useOriginalCanvasSize
    tgtW = W; tgtH = H;
else
    tgtW = W; tgtH = H;  % 如需自定，改這兩行
end

target_cx = (tgtW+1)/2;
target_cy = (tgtH+1)/2;

dx = target_cx - cx;    % +x 右移
dy = target_cy - cy;    % +y 下移
fprintf('平移量：dx=%.2f, dy=%.2f（像素）\n', dx, dy);

% 平移時的邊界填充值（用影像邊界的中位數，避免硬黑邊）
borderVals = double([gray_u8(1,:), gray_u8(end,:), gray_u8(:,1).', gray_u8(:,end).']);
fillVal    = uint8(round(median(borderVals)));

% 做仿射平移到同尺寸畫布
tform = affine2d([1 0 0; 0 1 0; dx dy 1]);
refOut = imref2d([tgtH tgtW]);
aligned_u8 = imwarp(gray_u8, tform, 'OutputView', refOut, ...
    'FillValues', fillVal, 'InterpolationMethod', 'cubic');

%% =================== 差異圖（固定尺度顯示） ===================
% 使用絕對差，單位 8-bit，方便觀察位移前後改變
diff_u8 = imabsdiff(aligned_u8, gray_u8);

% 亦可提供梯度差（如需）
% G_before = imgradient(double(gray_u8));
% G_after  = imgradient(double(aligned_u8));
% diffG    = imabsdiff(uint16(G_after), uint16(G_before));  % 若要看梯度差

%% ======================== 視覺化 ==========================
figure('Name','Centering with imfindcircles','Color','w');

subplot(1,3,1);
imshow(gray_u8, [0 255]); title('原圖 (標示偵測圓)');
hold on; viscircles([cx cy], r, 'Color','y');

subplot(1,3,2);
imshow(aligned_u8, [0 255]); title('平移對心後影像');
hold on; viscircles([target_cx target_cy], r, 'Color','c');

subplot(1,3,3);
imshow(diff_u8, [0 255]); title('差異圖 |aligned - original|'); colorbar;

%% ======================== 存檔（8-bit） =====================
[~, base, ~] = fileparts(imgPath);
outAligned = fullfile(outDir, base + "_centered.bmp");
outDiff    = fullfile(outDir, base + "_diff.bmp");

imwrite(aligned_u8, outAligned, 'bmp');
imwrite(diff_u8,    outDiff,    'bmp');

fprintf('已儲存：\n  %s\n  %s\n', outAligned, outDiff);
