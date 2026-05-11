%% HDR fitting 2D - Whole-FOV batch processing (Tutorial Edition)
%   Stage 1 已由 SimulatePSF/psf_multiwavelength_2D.m 預跑, 產物為 SimulatePSF/psf_multi.mat。
%   本檔負責 Stage 2 (Zernike 像差擬合) 與 Stage 3 (Wiener 反捲積驗證)。
%
%   [教學版差異] 相對正式版 (PSF_Fitting/HDR_fitting_2D_WholeFOV.m):
%     (1) 在 Stage 2 之前加上 subset_indices, 預設只跑 5 張代表 FOV (4 角 + 中心)
%         而不是全 100 張, 讓教學一次跑完只要幾分鐘。
%     (2) 在 Stage 2 與 Stage 3 之間加一段「自動從 4D stack 抽單張 PSF」, 把擬合
%         結果搬到 Deconvolution/PSF/PSF_fitted_2D.mat, 直接餵給 Stage 3, 不必手動搬檔。
%   想跑正式版完整流程 (全 100 張 + 手動挑 PSF), 請使用 PSF_Fitting/ 根目錄的同名檔。

clearvars;
clc;
close all;

%% [Tutorial] 1) 選 FOV 子集 (4 角 + 中心)
% 想跑全 FOV:    tutorial_subset = 1:100;
% 想跑單張:      tutorial_subset = 55;
% 想跑指定幾張:  tutorial_subset = [N1 N2 ... Nk];   (每個 N 都是 1..100 的整數)
tutorial_subset = [1 10 55 91 100];

%% Stage 2: PSF aberration fitting across selected FOVs
summary = HDR_fitting_2D_WholeFOV_impl('subset_indices', tutorial_subset);
fprintf('Formal Whole-FOV fitting completed.\n');
fprintf('Outputs:\n');
fprintf('  %s\n', summary.batch_results_path);
fprintf('  %s\n', summary.stack_path);

%% [Tutorial] 2) 從 4D PSF stack 抽出單張代表 PSF, 餵給 Stage 3
% 預設抽 R6C5 = FOV 55 (10x10 grid 中心)。
% 想換別張: 改 picked_row / picked_col。
% 若所選 (row, col) 不在 subset 內 (擬合結果為 0), 會 fallback 抽 subset 中第一張成功擬合的 FOV。
%
% 注意: impl.m 預設 output_root 是 relative path 'Crop_circle_FreqFiltered/Fits'。
% 直接 load(summary.stack_path) 會被 MATLAB path 上的同名檔搶走 (例如原專案 PSF_Fitting/
% 的 stack 也叫 PSF_fitted_2D_FOVstack.mat)。所以這裡用 absolute path 強制 anchor。
project_root_pick = fileparts(mfilename('fullpath'));
stack_path_abs = fullfile(project_root_pick, 'Crop_circle_FreqFiltered', 'Fits', 'PSF_fitted_2D_FOVstack.mat');
stack_data = load(stack_path_abs);
picked_row = 6;
picked_col = 5;

fitted_psf = stack_data.psf_grid(:, :, picked_row, picked_col);
if sum(fitted_psf(:)) < 1e-10
    valid_mask = ~isnan(stack_data.fval_map);
    [picked_row, picked_col] = find(valid_mask, 1, 'first');
    fitted_psf = stack_data.psf_grid(:, :, picked_row, picked_col);
    fprintf('[Tutorial] 中心位置不在 subset, fallback 抽 R%dC%d.\n', picked_row, picked_col);
end

deconv_psf_dir = fullfile(project_root_pick, 'Deconvolution', 'PSF');
if ~exist(deconv_psf_dir, 'dir')
    mkdir(deconv_psf_dir);
end
save(fullfile(deconv_psf_dir, 'PSF_fitted_2D.mat'), 'fitted_psf');
fprintf('[Tutorial] 抽 R%dC%d 的 PSF -> Deconvolution/PSF/PSF_fitted_2D.mat\n', picked_row, picked_col);

%% Stage 3: Wiener deconvolution check - 2D baseline (CPU only)
global GT
global img
global psf

project_root = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(project_root, 'bads-1.1.3')));

t = Tiff(fullfile(project_root, 'Deconvolution', 'GT', 'pillar_30_SEM.tiff'), 'r');
GT = im2double(read(t));
GT = imresize(GT, 1, 'cubic');

load(fullfile(project_root, 'Deconvolution', 'PSF', 'PSF_fitted_2D.mat'), 'fitted_psf');
fitted_psf = gather(fitted_psf);

t = Tiff(fullfile(project_root, 'Deconvolution', 'TestImages', '30.tiff'), 'r');
raw_img = im2double(read(t));
raw_img = imresize(raw_img, 1, 'cubic');
img = raw_img;

psf = fitted_psf;

fprintf('Using loaded 2D PSF\n');
fprintf('PSF size: [%d, %d]\n', size(psf));
fprintf('PSF range: [%.6f, %.6f]\n', min(psf(:)), max(psf(:)));
fprintf('PSF sum: %.6f\n', sum(psf(:)));

if sum(psf(:)) < 1e-10
    error('Loaded PSF is nearly zero.');
end
psf = psf / sum(psf(:));

x0 = 1;
lb = 1e-3;
ub = 1e3;
fprintf('Optimizing NSR...\n');
[x, fval] = bads(@wnrbads, x0, lb, ub);
fprintf('Best NSR: %.6f, loss %.6f\n', x, fval);

img_d = deconvwnr(img, psf, x);

save_dir = fullfile(project_root, 'Deconvolution', 'Results');
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

function out = wnrbads(input)
global img
global psf
global GT

gt_g = imgradient(GT);
img_d = deconvwnr(img, psf, input);
img_dg = imgradient(img_d);

out = 100 * mse(img_dg, gt_g);
end
