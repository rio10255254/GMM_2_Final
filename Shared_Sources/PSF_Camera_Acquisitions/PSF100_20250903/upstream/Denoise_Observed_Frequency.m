clc; clear; close all;

%% ========== File Settings ==========
obs_img_path = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle_1201\Crop_circle_901_v2\VisionTop_20250903160550.bmp";
out_folder   = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle_1201\Crop_circle_901_v2\FrequencyFiltered\";
suffix_tag   = "_freqDenoise";

if ~exist(out_folder, 'dir'); mkdir(out_folder); end
[~, base_name, base_ext] = fileparts(obs_img_path);
fprintf('Loading observation image %s%s\n', base_name, base_ext);

%% ========== Frequency Filter Parameters ==========
cutoff_px        = 47;     % Butterworth cutoff radius (pixels) 截止半徑（頻域像素）
butterworth_ord  = 2;      % Filter order (steepness) 濾波器階數，越大越陡
hf_suppress      = 1.0;    % 1=full low-pass, 0=keep spectrum 1完全低通；0保留原譜
blend_with_input = 0.0;    % Blend with original 高頻回混比例，0只用濾波結果

apply_tukey_window = false; % Apply Tukey window 啟用窗函數減少邊界振鈴
tukey_alpha        = 0.1;  % Tukey shape parameter 形狀參數（0矩形,1餘弦）
window_floor       = 1e-3; % Floor when undoing window 逆窗時避免除零

apply_spatial_smoothing = false; % Apply extra spatial smoothing 額外空間平滑
spatial_smoothing_sigma = 1.5;   % Gaussian sigma (px) σ=1 代表弱平滑

%% ========== Load Image ==========
img_raw = imread(obs_img_path);
if size(img_raw, 3) == 3
    img_gray = im2gray(img_raw);
else
    img_gray = img_raw;
end
I = im2double(img_gray);
[rows, cols] = size(I);

%% ========== Optional Windowing ==========
if apply_tukey_window
    wy = tukeywin(rows, tukey_alpha);
    wx = tukeywin(cols, tukey_alpha);
    window2d = wy * wx.';                     % 2D Tukey window 乘外積形成二維窗
    I_windowed = I .* window2d;
else
    window2d   = ones(rows, cols);
    I_windowed = I;
end

%% ========== FFT & Filter Construction ==========
F        = fft2(I_windowed);
F_shift  = fftshift(F);
[xGrid, yGrid] = meshgrid(1:cols, 1:rows);
cx = (cols + 1) / 2;
cy = (rows + 1) / 2;
radius = sqrt((xGrid - cx).^2 + (yGrid - cy).^2);
H_base = 1 ./ (1 + (radius ./ cutoff_px).^(2 * butterworth_ord));
H = (1 - hf_suppress) + hf_suppress * H_base;    % Keep some highs if desired 依比例保留高頻

F_filt_shift = F_shift .* H;
F_filt = ifftshift(F_filt_shift);
I_filtered_window = real(ifft2(F_filt));

%% ========== Undo Window & Blend ==========
if apply_tukey_window
    safe_window = max(window2d, window_floor);
    I_filtered = I_filtered_window ./ safe_window;
else
    I_filtered = I_filtered_window;
end
I_filtered = min(max(I_filtered, 0), 1);        % Clamp intensities 限制在[0,1]
I_blended = (1 - blend_with_input) * I_filtered + blend_with_input * I;

%% ========== Optional Spatial Smoothing ==========
I_final = I_blended;
if apply_spatial_smoothing
    I_final = imgaussfilt(I_final, spatial_smoothing_sigma); % Weak Gaussian blur 弱化高頻殘留
end

%% ========== Export ==========
out_img = im2uint8(I_final);
out_path = fullfile(out_folder, base_name + suffix_tag + base_ext);
imwrite(out_img, out_path);
fprintf('Wrote frequency filtered image to %s\n', out_path);

%% ========== Diagnostics ==========
log_spec_in  = log1p(abs(F_shift));       % 原始頻譜對數幅度
log_spec_out = log1p(abs(F_filt_shift));  % 濾波後頻譜對數幅度

figure('Name','Spatial Domain','Color','w');
subplot(1,3,1); imshow(I, []);       title('Original 原圖');
subplot(1,3,2); imshow(I_final, []); title('Filtered Output 最終結果');
subplot(1,3,3); imshow(I - I_final, []); title('Difference (Orig - Output) 差異');
axis image
colorbar
colormap(gca, gray);

%% ========== Gradient Visualization ==========
[Gmag_filtered, ~] = imgradient(I_final);
figure('Name','Gradient of Filtered Image','Color','w');
imagesc(abs(Gmag_filtered));
axis image off;
colorbar;
title('Gradient Magnitude (Filtered Image) 濾波後梯度');

figure('Name','Frequency Magnitude','Color','w');
subplot(1,3,1); imagesc(log_spec_in);  axis image off; colorbar; title('log|F| 原圖頻譜');
subplot(1,3,2); imagesc(H);            axis image off; colorbar; title('Filter H 濾波器');
subplot(1,3,3); imagesc(log_spec_out); axis image off; colorbar; title('log|F_{filtered}| 結果頻譜');

fprintf('Frequency-domain noise suppression finished. Adjust cutoff_px or butterworth_ord to balance edges and smoothing.\n');
