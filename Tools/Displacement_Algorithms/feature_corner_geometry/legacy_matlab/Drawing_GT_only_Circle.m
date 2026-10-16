%% ======= 從模糊影像生成「聚焦版」GT =======
inputImgPath  = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle\Crop_circle_901\VisionTop_20250903160735.bmp";
outputBmpPath = 'D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\GT_focus.bmp';

% 讀影像
I = imread(inputImgPath);
if size(I,3) > 1, I = rgb2gray(I); end
I = im2double(I);
[H,W] = size(I);

% --- 1. 找模糊圓心與半徑 ---
[centers, radii] = imfindcircles(I,[30 500],'ObjectPolarity','bright','Sensitivity',0.95);
if isempty(centers)
    error('找不到圓，請調整 imfindcircles 的半徑範圍');
end
cx = centers(1,1);
cy = centers(1,2);
r_blur = radii(1);

% --- 2. 灰階估計 ---
mask_in  = (sqrt(( (1:W)-cx ).^2 + ( (1:H)'-cy ).^2) <= r_blur*0.5); % 圓內小區域
mask_out = (sqrt(( (1:W)-cx ).^2 + ( (1:H)'-cy ).^2) >= r_blur*1.2); % 圓外區域

w = mean(I(mask_in));   % 亮值 (圓內)
b = mean(I(mask_out));  % 暗值 (背景)

% --- 3. 半徑校正 ---
% 物理真實半徑 (像素)，這裡用你之前的公式換算
p_cam_um    = 2.5;      % 相機 pixel pitch (µm)
M_objective = 20;
M_relay     = 1;
binning     = 1;
s_post      = 1;
p_obj_um = (p_cam_um / (M_objective*M_relay)) * binning / s_post;
r_true = (100/2) / p_obj_um;   % 直徑 100 µm -> 半徑像素

% --- 4. 建立 GT ---
[X,Y] = meshgrid(1:W,1:H);
R = sqrt((X-cx).^2 + (Y-cy).^2);
GT = ones(H,W)*b;
GT(R <= r_true) = w;

% --- 5. 輸出 ---
imwrite(im2uint8(GT), outputBmpPath, 'bmp');
subplot(1,2,1), imagesc(I),  axis image off, colormap gray; caxis([0 1]); title('原始模糊影像');
subplot(1,2,2), imagesc(GT), axis image off, colormap gray; caxis([0 1]); title('聚焦 GT');

