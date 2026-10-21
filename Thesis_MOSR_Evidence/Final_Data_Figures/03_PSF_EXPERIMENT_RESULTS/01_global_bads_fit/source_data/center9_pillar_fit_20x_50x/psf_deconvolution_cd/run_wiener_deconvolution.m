function run_wiener_deconvolution()
% Apply each fitted PSF to a background-normalized pillar-contrast image.
% One fixed regularization value is used for both magnifications.  It is
% selected on held-out calibration imagery and is not tuned against CD.

figure_root = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\center9_pillar_fit_20x_50x';
fit_root = 'D:\GMM_2_Final\PSF_Fitting\output\deconvolution_baseline_psf_20260715';
source_root = fileparts(mfilename('fullpath'));

cfg = struct('label', {'20x', '50x'});

for k = 1:numel(cfg)
    label = cfg(k).label;
    image_path = fullfile(figure_root, label, '05_original_pillar_3x3.bmp');
    meta_path = fullfile(fit_root, label, 'selected_frame.json');
    psf_path = fullfile(fit_root, label, 'fit_result', 'PSF_fitted_2D_FOVstack.mat');
    out_dir = fullfile(figure_root, label);

    I = im2double(imread(image_path));
    if size(I, 3) > 1
        I = rgb2gray(I);
    end
    meta = jsondecode(fileread(meta_path));
    full_centers = double(meta.pillar_centers_xy);
    pitch_px = double(meta.pitch_px);
    margin = 0.75 * pitch_px;
    crop_x1 = max(1, floor(min(full_centers(:, 1)) - margin));
    crop_y1 = max(1, floor(min(full_centers(:, 2)) - margin));
    centers_xy = full_centers - [crop_x1 - 1, crop_y1 - 1];

    loaded = load(psf_path, 'psf_grid');
    psf = squeeze(double(loaded.psf_grid));
    psf = psf ./ sum(psf(:));
    pad_y = floor(size(psf, 1) / 2);
    pad_x = floor(size(psf, 2) / 2);
    noise_nsr = estimate_image_nsr(I, centers_xy, double(meta.pitch_px));
    calibrated_common_nsr = 0.05;
    nsr = calibrated_common_nsr;

    % Match the representation used in PSF fitting: remove the slowly
    % varying bright background and invert dark pillars to positive contrast.
    background_radius = ceil(0.36 * double(meta.pitch_px));
    background = imclose(I, strel('disk', background_radius));
    contrast = max(background - I, 0);
    contrast_scale = prctile(contrast(:), 99.5);
    contrast = contrast / max(contrast_scale, eps);
    padded_contrast = padarray(contrast, [pad_y pad_x], 'symmetric', 'both');
    padded_contrast = edgetaper(padded_contrast, psf);
    restored_contrast_padded = deconvwnr(padded_contrast, psf, nsr);
    restored_contrast = restored_contrast_padded( ...
        pad_y + 1:pad_y + size(I, 1), ...
        pad_x + 1:pad_x + size(I, 2));
    restored_contrast = min(max(restored_contrast, 0), 1.25);
    restored = background - contrast_scale * restored_contrast;

    % Preserve the unclipped values for CD measurement and save a viewable copy.
    restored_display = min(max(restored, 0), 1);
    png_path = fullfile(out_dir, '09_fitted_psf_wiener_deconvolution_pillar_3x3.png');
    bmp_path = fullfile(out_dir, '09_fitted_psf_wiener_deconvolution_pillar_3x3.bmp');
    imwrite(im2uint8(restored_display), png_path);
    imwrite(im2uint8(restored_display), bmp_path);

    result_path = fullfile(source_root, sprintf('%s_wiener_deconvolution.mat', label));
    save(result_path, 'I', 'restored', 'restored_display', 'psf', 'nsr', ...
        'noise_nsr', 'calibrated_common_nsr', 'background', ...
        'background_radius', 'contrast', 'contrast_scale', ...
        'restored_contrast', 'crop_x1', 'crop_y1', ...
        'centers_xy', 'image_path', 'meta_path', 'psf_path', '-v7');

    fprintf('%s: noise NSR=%.9g, fixed NSR=%.9g, range=[%.6g, %.6g]\n', ...
        label, noise_nsr, nsr, min(restored(:)), max(restored(:)));
end
end

function nsr = estimate_image_nsr(I, centers_xy, pitch_px)
% Robustly estimate camera noise from adjacent background-pixel differences.
[yy, xx] = ndgrid(1:size(I, 1), 1:size(I, 2));
background = true(size(I));
exclude_radius = 0.27 * pitch_px;
for i = 1:size(centers_xy, 1)
    background = background & ...
        ((xx - centers_xy(i, 1)).^2 + (yy - centers_xy(i, 2)).^2 ...
        > exclude_radius^2);
end

dx = I(:, 2:end) - I(:, 1:end-1);
mx = background(:, 2:end) & background(:, 1:end-1);
dy = I(2:end, :) - I(1:end-1, :);
my = background(2:end, :) & background(1:end-1, :);
differences = [dx(mx); dy(my)];

difference_median = median(differences);
noise_sigma = median(abs(differences - difference_median)) ...
    / 0.6744897501960817 / sqrt(2);
signal_variance = max(var(I(:), 1) - noise_sigma^2, eps);
nsr = noise_sigma^2 / signal_variance;
end
