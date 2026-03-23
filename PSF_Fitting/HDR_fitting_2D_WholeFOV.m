%% HDR fitting 2D - batch processing across a folder
clearvars;
clc; close all;
global psf_slice img GT AMP loss_history iter_count ENABLE_PLOTS
global PSF_f_global rho_global phi_global freq_mask_global  % << 新增的 global，用來存 precompute 結果

% ----------------------- Paths & switches -----------------------
input_folder = "Crop_circle_FreqFiltered";
% image_pattern = "*freqDenoise*.bmp"; % Original pattern
image_pattern = "VisionTop_*.bmp"; % New pattern for filenames like "VisionTop_20250903160550_1.bmp". Change .bmp to your actual extension if needed.
gt_path = "Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp";
output_root = fullfile(input_folder, "Fits");
grid_rows = 10; % number of rows in the FOV layout
grid_cols = 10; % number of columns in the FOV layout
if ~exist(output_root, 'dir')
    mkdir(output_root);
end
ENABLE_PLOTS = false; % set false to speed up batch runs (plots off)

% ----------------------- Load PSF & GT once ---------------------
load('SimulatePSF/psf_multi.mat'); % provides psf_multi
psf_slice = gpuArray(psf_multi); % 2D PSF directly
fprintf('psf_slice range: [%.6f, %.6f]\n', min(psf_slice(:)), max(psf_slice(:)));

AMP = 1.0;            % fixed amplitude
INTERP_FACTOR_img = 1; % no interpolation scaling

GT_temp = im2double(imread(gt_path));
GT_temp = imresize(GT_temp, INTERP_FACTOR_img, 'cubic');
GT = gpuArray(GT_temp);

% ----------------------- Precompute pupil & freq mask (建議 3) -----------------------
% 這一段之後在 aberration() / main 重建 PSF 都會重複用到
[Hpsf, Wpsf] = size(psf_slice);
pupil_res = floor((min(Hpsf, Wpsf) - 1) / 2);
x_coord = gpuArray(-pupil_res:pupil_res);
y_coord = gpuArray(-pupil_res:pupil_res);
[Xg, Yg] = meshgrid(x_coord, y_coord);
rho_global = ((Xg.^2 + Yg.^2).^0.5) ./ pupil_res ./ 2;
phi_global = atan2(Yg, Xg);
PSF_f_global = gpuArray(fftshift(fft2(psf_slice)));

% 頻率遮罩只跟影像大小有關，GT / img 大小固定，用一次即可
[hGT, wGT] = size(GT);
[fx, fy] = meshgrid((-wGT/2:wGT/2-1)/wGT, (-hGT/2:hGT/2-1)/hGT);
freq_radius = sqrt(fx.^2 + fy.^2);
dc_mask = freq_radius < 0.02;
high_freq_mask = freq_radius > 0.5;
freq_mask_global = gpuArray(~(dc_mask | high_freq_mask));

% ----------------------- BADS bounds (原維度不變，tilt 在內部鎖死) ----------------
x0 = gpuArray([0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.0]); % Starting point
lb = gpuArray([-0.3 -0.3 -0.1 0 -0.1 -0.05 -0.05 -0.05 -0.05 -0.01 -0.01 0 -0.01 -0.01 0.8]); % Lower bounds
ub = gpuArray([0.3 0.3 0.1 1.0 0.1 0.05 0.05 0.05 0.05 0.01 0.01 0.3 0.01 0.01 1.25]); % Upper bounds

% ----------------------- Collect inputs -------------------------
file_list = dir(fullfile(input_folder, image_pattern));
file_list = file_list(~[file_list.isdir]);

% --- Fix for natural-order sorting ---
nums = zeros(1, numel(file_list));
for i = 1:numel(file_list)
    tokens = regexp(file_list(i).name, '_(\d+)\.', 'tokens');
    if ~isempty(tokens)
        nums(i) = str2double(tokens{1}{1});
    else
        warning('Could not extract trailing number from filename: %s. Sorting may be incorrect.', file_list(i).name);
        nums(i) = NaN;
    end
end
[~, sort_idx] = sort(nums);
file_list = file_list(sort_idx);
if isempty(file_list)
    error('No input images found in %s matching %s.', input_folder, image_pattern);
end
if numel(file_list) ~= grid_rows * grid_cols
    error('Expected %d images for a %dx%d grid, but found %d files.', grid_rows*grid_cols, grid_rows, grid_cols, numel(file_list));
end

psf_size = size(psf_slice);
if numel(psf_size) < 2
    error('psf_slice must be 2D.');
end
psf_grid = zeros(psf_size(1), psf_size(2), grid_rows, grid_cols);
coef_grid = zeros(numel(x0), grid_rows, grid_cols);
fval_map = nan(grid_rows, grid_cols);
iteration_map = nan(grid_rows, grid_cols);
filename_map = strings(grid_rows, grid_cols);

fprintf('\nStarting batch 2D fitting on %d images...\n', numel(file_list));
summary_rows = cell(numel(file_list), 4); % filename, fval, iterations, seconds

% -------- Warm start：用上一顆的解當下一顆的 x0（建議 4.1）--------
x_prev = x0;   % 第一顆用原本的初始點

for fi = 1:numel(file_list)
    current_file = file_list(fi);
    img_path = fullfile(current_file.folder, current_file.name);
    fprintf('\n[%d/%d] Fitting %s\n', fi, numel(file_list), current_file.name);

    % reset trackers per image
    loss_history = [];
    iter_count = 0;

    % load image to GPU
    img_temp = im2double(imread(img_path));
    img_temp = imresize(img_temp, INTERP_FACTOR_img, 'cubic');
    img = gpuArray(img_temp);

    t_start = tic;
    % 使用上一顆的係數做 initial guess
    [x,fval] = bads(@aberration, x_prev, lb, ub);
    % 下一顆 FOV 用這顆的解當 x0
    x_prev = x; 

    % ------------------ 像差重建：與 aberration 完全一致 ------------------
    global PSF_f_global rho_global phi_global  % 讀取 precompute 的變數

    PSF_f = PSF_f_global;
    rho   = rho_global;
    phi   = phi_global;

    % Zernike 參數：Z2~Z15 <- x(1:14)，Z1 (piston) 固定為 0
    Z = gpuArray(zeros(1,15,'like',rho));
    Z(2:15) = x(1:14);
    Z(2) = 0;   % 強制 Y-tilt = 0（鎖住 y 方向平移）
    Z(3) = 0;   % 強制 X-tilt = 0（鎖住 x 方向平移）
    AC = x(15);  % 振幅縮放

    % Zernike 展開（與 3D 版本一致的寫法）
    W_phase = ...
        Z(1).*1 + ...
        Z(2).*2.*rho.*sin(phi) + ...                                  % Y-Tilt (Z2)
        Z(3).*2.*rho.*cos(phi) + ...                                  % X-Tilt (Z3)
        Z(4).*sqrt(6).*rho.^2.*sin(2.*phi) + ...                      % ObliqueAstigmatism (Z4)
        Z(5).*sqrt(3).*(2.*rho.^2-1) + ...                            % Defocus (Z5)
        Z(6).*sqrt(6).*rho.^2.*cos(2.*phi) + ...                      % VerticalAstigmatism (Z6)
        Z(7).*sqrt(8).*rho.^3.*sin(3.*phi) + ...                      % VerticalTrefoil (Z7)
        Z(8).*sqrt(8).*(3.*rho.^2-2.*rho).*sin(phi) + ...             % VerticalComa (Z8)
        Z(9).*sqrt(8).*(3.*rho.^2-2.*rho).*cos(phi) + ...             % HorizontalComa (Z9)
        Z(10).*sqrt(8).*rho.^3.*cos(3.*phi) + ...                     % ObliqueTrefoil (Z10)
        Z(11).*sqrt(10).*rho.^4.*sin(4.*phi) + ...                    % ObliqueQuadrafoil (Z11)
        Z(12).*sqrt(10).*(4.*rho.^4-3.*rho.^2).*sin(2.*phi) + ...     % ObliqueSecondaryAstigmatism (Z12)
        Z(13).*sqrt(5).*(6.*rho.^4-6.*rho.^2+1) + ...                 % PrimarySpherical (Z13)
        Z(14).*sqrt(10).*(4.*rho.^4-3.*rho.^2).*cos(2.*phi) + ...     % VerticalSecondaryAstigmatism (Z14)
        Z(15).*sqrt(10).*rho.^4.*cos(4.*phi);                         % VerticalQuadrafoil (Z15)

    % 生成擬合 PSF
    PSF_a = PSF_f .* (exp(1i.*2.*pi().*W_phase).^2);
    fitted_psf_tmp = abs(ifft2(PSF_a));
    fitted_psf_tmp = fitted_psf_tmp ./ sum(fitted_psf_tmp(:));  % 能量正規化
    fitted_psf = AMP * AC .* fitted_psf_tmp;                    % 加上 AMP 與 AC

    elapsed = toc(t_start);

    % gather for save/log
    fitted_psf = gather(fitted_psf);
    x_cpu = gather(x);        % 避免覆蓋 x_prev (GPU) 的型別
    fval = gather(fval);
    loss_history = gather(loss_history);

    % store into FOV grid container (row-major left-to-right)
    row_idx = floor((fi-1)/grid_cols) + 1;
    col_idx = mod(fi-1, grid_cols) + 1;
    psf_grid(:,:,row_idx,col_idx) = fitted_psf;
    coef_grid(:,row_idx,col_idx) = x_cpu(:);
    fval_map(row_idx,col_idx) = fval;
    iteration_map(row_idx,col_idx) = iter_count;
    filename_map(row_idx,col_idx) = string(current_file.name);

    fprintf('Done: fval=%.6f, time=%.2f s, iterations=%d\n', fval, elapsed, iter_count);
    summary_rows{fi,1} = current_file.name;
    summary_rows{fi,2} = fval;
    summary_rows{fi,3} = iter_count;
    summary_rows{fi,4} = elapsed;
end

summary_tbl = cell2table(summary_rows, 'VariableNames', {'filename','fval','iterations','seconds'});
writetable(summary_tbl, fullfile(output_root, 'batch_results.csv'));
fprintf('Batch results saved to %s\n', output_root);

fov_psf_data = struct( ...
    'psf_grid', psf_grid, ...
    'coef_grid', coef_grid, ...
    'fval_map', fval_map, ...
    'iterations_map', iteration_map, ...
    'filename_map', filename_map, ...
    'grid_rows', grid_rows, ...
    'grid_cols', grid_cols, ...
    'ordering', 'row-major-left-to-right');
stack_path = fullfile(output_root, 'PSF_fitted_2D_FOVstack.mat');
save(stack_path, '-struct', 'fov_psf_data');
fprintf('FOV PSF stack saved to %s\n', stack_path);

%------------------------------------------------------------------------------%
%% Wiener deconvolution check - 2D baseline (CPU only)
% clear all;
global GT
global img
global psf

% --- Preparation ---
t = Tiff('Deconvolution/GT/pillar_30_SEM.tiff','r');
GT = im2double(read(t));
GT = imresize(GT, 1, 'cubic'); % GT is on CPU

% Load fitted PSF file
load("Deconvolution/PSF/PSF_fitted_2D.mat", "fitted_psf");
fitted_psf = gather(fitted_psf);

% Load raw image (CPU)
t = Tiff('Deconvolution/TestImages/30.tiff','r');
raw_img = im2double(read(t));
raw_img = imresize(raw_img, 1, 'cubic');
img = raw_img; % img is on CPU

psf = fitted_psf; % psf is on CPU

% --- Checks ---
fprintf('Using loaded 2D PSF\n');
fprintf('PSF size: [%d, %d]\n', size(psf));
fprintf('PSF range: [%.6f, %.6f]\n', min(psf(:)), max(psf(:)));
fprintf('PSF sum: %.6f\n', sum(psf(:)));

if sum(psf(:)) < 1e-10
    error('Loaded PSF is nearly zero.');
end
psf = psf / sum(psf(:));

% --- Optimize NSR ---
x0 = 1;
lb = 1e-3;
ub = 1e3;
fprintf('Optimizing NSR...\n');
[x, fval] = bads(@wnrbads,x0,lb,ub);
fprintf('Best NSR: %.6f, loss %.6f\n', x, fval);

% --- Deconvolution ---
img_d = deconvwnr(img,psf,x);

% --- Save & visualize ---
save_dir = 'Deconvolution/Results/';
if ~exist(save_dir, 'dir')
    mkdir(save_dir);
end

output_filename = 'deconv_result_2D.tiff';
output_path = fullfile(save_dir, output_filename);
fprintf('Saving to: %s\n', output_path);

img_d_16bit = uint16(img_d * 65535);
imwrite(img_d_16bit, output_path);
fprintf('Deconvolution result saved.\n');

figure(1)
subplot(2,2,1)
imagesc(img)
axis image
title('Raw')
colorbar

subplot(2,2,2)
imshow(img_d_16bit)
axis image
title('Deconvolved')

subplot(2,2,3)
imagesc(psf)
axis image
title('PSF used')
colorbar

subplot(2,2,4)
imagesc(img_d - GT)
axis image
title('Deconv vs GT')
colorbar

fprintf('Wiener deconvolution check completed.\n');

%% --- aberration ---
% Core aberration loss，使用 precompute 的 pupil / freq mask，並鎖死 tilt
function result = aberration(coef)
    global psf_slice
    global img
    global GT
    global AMP
    global loss_history
    global iter_count
    global ENABLE_PLOTS
    global PSF_f_global rho_global phi_global freq_mask_global

    PSF_f = PSF_f_global;
    rho   = rho_global;
    phi   = phi_global;
    mask  = freq_mask_global;

    % Zernike 參數：Z2~Z15 <- coef(1:14)，Z1 (piston) = 0
    Z = gpuArray(zeros(1,15,'like',rho));
    Z(2:15) = coef(1:14);
    Z(2) = 0;   % 強制 Y-tilt = 0
    Z(3) = 0;   % 強制 X-tilt = 0
    AC = coef(15);   % 振幅縮放

    % Zernike 展開（與 main 中重建完全一致）
    W_phase = ...
        Z(1).*1 + ...
        Z(2).*2.*rho.*sin(phi) + ...                                  % Y-Tilt
        Z(3).*2.*rho.*cos(phi) + ...                                  % X-Tilt
        Z(4).*sqrt(6).*rho.^2.*sin(2.*phi) + ...                      % ObliqueAstigmatism
        Z(5).*sqrt(3).*(2.*rho.^2-1) + ...                            % Defocus
        Z(6).*sqrt(6).*rho.^2.*cos(2.*phi) + ...                      % VerticalAstigmatism
        Z(7).*sqrt(8).*rho.^3.*sin(3.*phi) + ...                      % VerticalTrefoil
        Z(8).*sqrt(8).*(3.*rho.^2-2.*rho).*sin(phi) + ...             % VerticalComa
        Z(9).*sqrt(8).*(3.*rho.^2-2.*rho).*cos(phi) + ...             % HorizontalComa
        Z(10).*sqrt(8).*rho.^3.*cos(3.*phi) + ...                     % ObliqueTrefoil
        Z(11).*sqrt(10).*rho.^4.*sin(4.*phi) + ...                    % ObliqueQuadrafoil
        Z(12).*sqrt(10).*(4.*rho.^4-3.*rho.^2).*sin(2.*phi) + ...     % ObliqueSecondaryAstigmatism
        Z(13).*sqrt(5).*(6.*rho.^4-6.*rho.^2+1) + ...                 % PrimarySpherical
        Z(14).*sqrt(10).*(4.*rho.^4-3.*rho.^2).*cos(2.*phi) + ...     % VerticalSecondaryAstigmatism
        Z(15).*sqrt(10).*rho.^4.*cos(4.*phi);                         % VerticalQuadrafoil

    % 生成帶像差的 PSF
    PSF_a = PSF_f .* (exp(1i.*2.*pi().*W_phase).^2);
    aberrated_psf = abs(ifft2(PSF_a));
    aberrated_psf = aberrated_psf ./ sum(aberrated_psf(:));   % 能量正規化
    out = AMP * AC .* aberrated_psf;                          % 加上 AMP 與 AC

    % 影像預測
    pred = conv2(GT,out,"same");
    
    % Loss terms
    out_g = imgradient(pred);
    img_g = imgradient(img);
    out_gn= normlz(imgradient(pred));
    img_gn = normlz(imgradient(img));
    out_freq = abs(fftshift(fft2(pred)));
    img_freq = abs(fftshift(fft2(img)));

    % 套用預先計算好的 freq mask
    out_freq = out_freq .* mask;
    img_freq = img_freq .* mask;

    result = 1*mse(img_freq,out_freq)+ 8*10e3*mse(out_gn,img_gn );
    
    % Visualization (optional)
    if ENABLE_PLOTS
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
        title('Deconv vs Original')
        axis image
        colorbar
        figure(2)
        subplot(121)
        imagesc(out_gn)
        title('Deconv Gradient')
        axis image
        colorbar
        subplot(122)
        imagesc(img_gn)
        title('Original Gradient')
        axis image
        colorbar
    end

    iter_count = iter_count + 1;
    freq_loss_raw = mse(img_freq,out_freq);
    grad_loss_raw = mse(out_g,img_g);
    freq_loss_weighted = 1 * freq_loss_raw;
    grad_loss_weighted = 8*10e3 * grad_loss_raw;
    total_loss = freq_loss_weighted + grad_loss_weighted;
    loss_history(iter_count,:) = gather([total_loss, freq_loss_weighted, grad_loss_weighted, freq_loss_raw, grad_loss_raw]);

    if ENABLE_PLOTS && mod(iter_count, 3) == 0
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

%% --- wnrbads ---
function out = wnrbads(input)
    global img
    global psf
    global GT
    
    gt_g = imgradient(GT);
    img_d = deconvwnr(img, psf, input);
    img_dg = imgradient(img_d);
    
    out = 100*mse(img_dg,gt_g);
end
