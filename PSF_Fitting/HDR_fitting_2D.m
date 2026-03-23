%%
clearvars;
clc; close all; 
global psf_slice
global img
global GT
global AMP
global loss_history
global iter_count

% --- 修改點 1: 移除 psf_multi 的 clear 指令，並直接載入 2D PSF ---
load('SimulatePSF/psf_multi.mat'); % 載入你的 2D PSF (變數名為 psf_multi)

% --- 修改點 2: 移除 `psf_3d` 的初始化，因為我們只處理 2D ---
% psf_3d = zeros([165 165 61]); % <--- 刪除此行

% --- 修改點 3: 整個 for 迴圈結構被移除，以下是原本迴圈內的程式碼 ---
fprintf('\n開始處理 2D 影像...\n');
loss_history = [];
iter_count = 0;

% --- 修改點 4: 移除 AMP，或將其設為固定值 1 ---
% AMP = amp(i); % <--- 刪除此行
AMP = 1.0; % 設定一個固定的振幅/能量比例

INTERP_FACTOR_img = 1; % 圖像插值倍數：1=不插值

% 讀取指定的 2D 影像 (將檔名寫死)
% img_temp = im2double(imread("SingleImage_Input/VisionTop_20250903160550.bmp"));
img_temp = im2double(imread("SingleImage_Input/VisionTop_20250903160550_freqDenoise.bmp"));
img_temp = imresize(img_temp, INTERP_FACTOR_img, 'cubic');
img = gpuArray(img_temp);

% ---- 讀取 GT (BMP) ----
GT_temp = im2double(imread("SingleImage_Input/GT/GT_901_with_Block_proc.bmp"));
GT_temp = imresize(GT_temp, INTERP_FACTOR_img, 'cubic');
GT = gpuArray(GT_temp);


% --- 修改點 6: 正確處理 2D PSF 輸入 ---
% psf_slice = gpuArray(psf_multi(:,:,31)); % 這是 3D 的用法
psf_slice = gpuArray(psf_multi); % 對於 2D PSF，直接使用即可
fprintf('psf_slice 範圍: [%.6f, %.6f]\n', min(psf_slice(:)), max(psf_slice(:)));

% 優化器參數設定 (這部分不需變動)
x0 = gpuArray([0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.0]); % Starting point
lb = gpuArray([-0.3 -0.3 -0.1 0 -0.1 -0.05 -0.05 -0.05 -0.05 -0.01 -0.01 0 -0.01 -0.01 0.8]); % Lower bounds
ub = gpuArray([0.3 0.3 0.1 1.0 0.1 0.05 0.05 0.05 0.05 0.01 0.01 0.3 0.01 0.01 1.25]); % Upper bounds

% 執行優化
[x,fval] = bads(@aberration,x0,lb,ub);

% 根據優化結果 x，重新計算最終的 PSF (這部分不需變動)
x_coord = gpuArray(-50:1:50);
y_coord = gpuArray(-50:1:50);
[X,Y] = meshgrid(x_coord, y_coord); 
rho = ((X.^2+Y.^2).^0.5)./50;
phi = atan2(Y,X);
C = gpuArray(zeros(1,14));
C(1:14) = x(1:14);
Z1 = 2.*rho.*sin(phi); Z2 = 2.*rho.*cos(phi); Z3 = sqrt(6).*(rho.^2).*sin(2.*phi);
Z4 = sqrt(3).*(2.*(rho.^2)-1); Z5 = sqrt(6).*(rho.^2).*cos(2.*phi); Z6 = sqrt(8).*(rho.^3).*sin(3.*phi);
Z7 = sqrt(8).*(3.*rho.^3-2.*rho).*sin(phi); Z8 = sqrt(8).*(3.*rho.^3-2.*rho).*cos(phi);
Z9 = sqrt(8).*(rho.^3).*cos(3.*phi); Z10 = sqrt(10).*(rho.^4).*sin(4.*phi);
Z11 = sqrt(10).*(4.*(rho.^4)-3.*(rho.^2)).*sin(2.*phi); Z12 = sqrt(5).*(6.*rho.^4-6.*rho.^2+1);
Z13 = sqrt(10).*(4.*(rho.^4)-3.*(rho.^2)).*cos(2.*phi); Z14 = sqrt(10).*(rho.^4).*cos(4.*phi);
W = C(1).*Z1+C(2).*Z2+C(3).*Z3+C(4).*Z4+C(5).*Z5+C(6).*Z6+C(7).*Z7+C(8).*Z8+C(9).*Z9...
    +C(10).*Z10+C(11).*Z11+C(12).*Z12+C(13).*Z13+C(14).*Z14;
fitted_psf = abs(ifft2(fftshift(fft2(psf_slice)).*(exp(1i.*(2*pi()).*W).^2)));
fitted_psf = fitted_psf./(sum(sum(fitted_psf)));

% % --- 修改點 7: 簡化儲存 TIFF 的檔名 ---
% psf_save = uint16(normlz(fitted_psf) * 65535);
% imwrite(psf_save, "SimulatePSF/PSF_fitted_2D.tiff");

fprintf('2D 處理完成，最終誤差: %.6f\n', fval);


%% --- 修改點 8: 修改儲存 .mat 檔案的內容 ---
fitted_psf = gather(fitted_psf);
x = gather(x);
fval = gather(fval);

disp('--- MATLAB 存檔前偵錯檢查 ---');
whos fitted_psf;

save("SimulatePSF/PSF_fitted_2D_0924.mat", 'fitted_psf', 'x', 'fval');
fprintf('2D PSF 擬合數據已保存完成！\n');

%% function result = aberration(coef)
% aberration 函式本身幾乎不需要修改，因為它的計算本質上就是 2D 的。
% 唯一的修改是確認 AMP 的使用方式。
function result = aberration(coef)
    global psf_slice
    global img
    global GT
    global AMP % AMP 現在是一個純量 1.0
    PSF = gpuArray(fftshift(fft2(psf_slice)));
    x_coord = gpuArray(-50:1:50);
    y_coord = gpuArray(-50:1:50);
    [X,Y] = meshgrid(x_coord, y_coord); 
    rho = ((X.^2+Y.^2).^0.5)./50;
    phi = atan2(Y,X);
    % C = gpuArray([0 0 0 0 0 0 0 0 0 0 0 0 0 0]);
    % C(1:14) = coef(1:14);

   C = gpuArray(zeros(1,14,'like',rho));

    C(1)  = sqrt(8).*coef(6);   % Z1  ← √8 * x6
    C(2)  = sqrt(8).*coef(7);   % Z2  ← √8 * x7
    C(3)  = coef(2);            % Z3
    C(4)  = coef(3);            % Z4
    C(5)  = coef(4);            % Z5
    C(6)  = coef(5);            % Z6
    C(7)  = coef(6);            % Z7  ← x6
    C(8)  = coef(7);            % Z8  ← x7
    C(9)  = coef(8);            % Z9
    C(10) = 0;                  % Z10（未指定→0）
    C(11) = 0;                  % Z11（未指定→0）
    C(12) = coef(9);            % Z12
    C(13) = 0;                  % Z13（未指定→0）
    C(14) = 0;                  % Z14（未指定→0）

    AC = coef(15); % AC 仍然是優化的振幅係數
    
    Z1 = 2.*rho.*sin(phi); Z2 = 2.*rho.*cos(phi); Z3 = sqrt(6).*(rho.^2).*sin(2.*phi);
    Z4 = sqrt(3).*(2.*(rho.^2)-1); Z5 = sqrt(6).*(rho.^2).*cos(2.*phi); Z6 = sqrt(8).*(rho.^3).*sin(3.*phi);
    Z7 = sqrt(8).*(3.*rho.^3-2.*rho).*sin(phi); Z8 = sqrt(8).*(3.*rho.^3-2.*rho).*cos(phi);
    Z9 = sqrt(8).*(rho.^3).*cos(3.*phi); Z10 = sqrt(10).*(rho.^4).*sin(4.*phi);
    Z11 = sqrt(10).*(4.*(rho.^4)-3.*(rho.^2)).*sin(2.*phi); Z12 = sqrt(5).*(6.*rho.^4-6.*rho.^2+1);
    Z13 = sqrt(10).*(4.*(rho.^4)-3.*(rho.^2)).*cos(2.*phi); Z14 = sqrt(10).*(rho.^4).*cos(4.*phi);

    aberration = C(1).*Z1+C(2).*Z2+C(3).*Z3+C(4).*Z4...
            +C(5).*Z5+C(6).*Z6+C(7).*Z7+C(8).*Z8+C(9).*Z9...
            +C(10).*Z10+C(11).*Z11+C(12).*Z12+C(13).*Z13+C(14).*Z14;
            
    aberrated_psf = abs(ifft2(PSF.*(exp(1i.*(2.*pi()).*aberration).^2)));
    aberrated_psf = aberrated_psf./(sum(sum(aberrated_psf)));
    out = AC.*aberrated_psf;
    
    % --- 修改點 9: 這裡的 AMP 是一個純量 (scalar)，所以這行仍然有效 ---
    out = out./sum(sum(out)).*AMP; 
    
    pred = conv2(GT,out,"same");
    
    % 後面的 Loss 計算和繪圖部分維持原樣
    out_g = imgradient(pred);
    img_g = imgradient(img);
    out_gn= normlz(imgradient(pred));
    img_gn = normlz(imgradient(img));
    out_freq = abs(fftshift(fft2(pred)));
    img_freq = abs(fftshift(fft2(img)));
    [h, w] = size(img);
    [fx, fy] = meshgrid((-w/2:w/2-1)/w, (-h/2:h/2-1)/h);
    freq_radius = sqrt(fx.^2 + fy.^2);
    dc_mask = freq_radius < 0.02;
    high_freq_mask = freq_radius > 0.5;
    mask = ~(dc_mask | high_freq_mask);
    out_freq = out_freq .* mask;
    img_freq = img_freq .* mask;
    result = 1*mse(img_freq,out_freq)+ 2*10e4*mse(out_gn,img_gn );
    
    figure(1)
    subplot(131)
    imagesc(abs(out));
    title('PSF fitting')
    axis image
    subplot(132)
    imagesc(abs(conv2(GT,out,"same")));
    title('Image fitting')
    axis image
    subplot(133)
    imagesc(out_gn-img_gn);
    title('Deconv vs Oringinal')
    axis image
    colorbar
    figure(2)
    subplot(121)
    imagesc(out_gn)
    % imagesc(imgradient(pred))
    title('Deconv Gradient')
    axis image
    colorbar
    subplot(122)
    imagesc(img_gn)
    % imagesc(imgradient(img))
    title('Oringinal Gradient')
    axis image
    colorbar


    global loss_history
    global iter_count
    iter_count = iter_count + 1;
    freq_loss_raw = mse(img_freq,out_freq);
    grad_loss_raw = mse(out_g,img_g);
    freq_loss_weighted = 1 * freq_loss_raw;
    grad_loss_weighted = 2*10e4 * grad_loss_raw;
    total_loss = freq_loss_weighted + grad_loss_weighted;
    loss_history(iter_count,:) = [total_loss, freq_loss_weighted, grad_loss_weighted, freq_loss_raw, grad_loss_raw];
    if mod(iter_count, 3) == 0
        figure(4)
        subplot(2,1,1)
        semilogy (1:iter_count, loss_history(:,1), 'r-', 'LineWidth', 2);
        hold on;
        semilogy (1:iter_count, loss_history(:,2), 'b-', 'LineWidth', 1.5);
        semilogy (1:iter_count, loss_history(:,3), 'g-', 'LineWidth', 1.5);
        hold off;
        legend('Total Loss', 'Freq Loss (weighted)', 'Grad Loss (weighted)', 'Location', 'best');
        title('Weighted Loss Components (Log Scale)');
        ylabel('Loss Value (log scale)');
        grid on;
        subplot(2,1,2)
        start_idx = max(1, iter_count-49);
        semilogy (start_idx:iter_count, loss_history(start_idx:iter_count,4), 'b--', 'LineWidth', 1.5);
        hold on;
        semilogy (start_idx:iter_count, loss_history(start_idx:iter_count,5), 'g--', 'LineWidth', 1.5);
        hold off;
        legend('Freq Loss (raw)', 'Grad Loss (raw)', 'Location', 'best');
        title('Raw Loss Components - Recent 50 Iterations');
        xlabel('Iteration');
        ylabel('Loss Value');
        grid on;
        drawnow;
    end
end

%% 核心反捲積驗證程式 - 2D 版本 (治本方法 - All on CPU)
clear all;
global GT
global img
global psf

% --- 數據準備 ---

% 載入 GT 並保持在 CPU
t = Tiff('Deconvolution/GT/pillar_30_SEM.tiff','r');
GT = im2double(read(t));
GT = imresize(GT, 1, 'cubic'); % GT is on CPU

% 載入擬合的 PSF 檔案
load("Deconvolution/PSF/PSF_fitted_2D.mat", "fitted_psf");

% [核心修正] 使用 gather() 確保載入的 PSF 變數一定會回到 CPU，以絕後患
% 這是解決所有 GPU 相關錯誤的關鍵步驟
fitted_psf = gather(fitted_psf);

% 載入實驗圖像並保持在 CPU
t = Tiff('Deconvolution/TestImages/30.tiff','r');
raw_img = im2double(read(t));
raw_img = imresize(raw_img, 1, 'cubic');
img = raw_img; % img is on CPU

% 將 CPU 上的 fitted_psf 賦值給 psf
psf = fitted_psf; % psf is on CPU

% --- 數據檢查 ---
fprintf('使用擬合出的 2D PSF\n');
fprintf('PSF大小: [%d, %d]\n', size(psf));
fprintf('PSF範圍: [%.6f, %.6f]\n', min(psf(:)), max(psf(:)));
fprintf('PSF總和: %.6f\n', sum(psf(:)));

if sum(psf(:)) < 1e-10
    error('載入的 PSF 無效！');
end
psf = psf / sum(psf(:));

% --- 優化與反捲積 ---
x0 = 1;
lb = 1e-3;
ub = 1e3;
fprintf('正在優化NSR參數...\n');
[x, fval] = bads(@wnrbads,x0,lb,ub);
fprintf('最佳NSR參數: %.6f，誤差: %.6f\n', x, fval);

% 執行維納反捲積 (所有輸入都已在 CPU，此處會安全執行)
img_d = deconvwnr(img,psf,x);

% --- 結果保存與顯示 ---
save_dir = 'Deconvolution/Results/';
if ~exist(save_dir, 'dir')
    mkdir(save_dir);
end

output_filename = 'deconv_result_2D.tiff';
output_path = fullfile(save_dir, output_filename);
fprintf('保存路徑: %s\n', output_path);

img_d_16bit = uint16(img_d * 65535);
imwrite(img_d_16bit, output_path);
fprintf('反卷積結果已保存！\n');

figure(1)
subplot(2,2,1)
imagesc(img)
axis image
title('原始圖像')
colorbar

subplot(2,2,2)
imshow(img_d_16bit)
axis image
title('反捲積結果')

subplot(2,2,3)
imagesc(psf)
axis image
title('使用的PSF')
colorbar

subplot(2,2,4)
imagesc(img_d - GT) % 所有數據都在 CPU，可直接運算
axis image
title('Deconv vs GT')
colorbar

fprintf('反捲積完成！\n');

%% --- wnrbads 函式 ---
% 因為主腳本已確保所有 global 變數都在 CPU 上，
% 這個函式可以保持最簡潔的形式，無需任何 gather() 或 gpuArray()
function out = wnrbads(input)
    global img
    global psf
    global GT
    
    gt_g = imgradient(GT);
    img_d = deconvwnr(img, psf, input);
    img_dg = imgradient(img_d);
    
    out = 100*mse(img_dg,gt_g);
end