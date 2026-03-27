%% HDR fitting 2D - batch processing across a folder
clearvars;
clc;
close all;

summary = HDR_fitting_2D_WholeFOV_impl();
fprintf('Formal Whole-FOV fitting completed.\n');
fprintf('Outputs:\n');
fprintf('  %s\n', summary.batch_results_path);
fprintf('  %s\n', summary.stack_path);

%% Wiener deconvolution check - 2D baseline (CPU only)
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
