function run_cd_deconvolution_sweep()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
% Compare direct and background-normalized deconvolution without using SEM.
figure_root = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence', ...
    'Final_Data_Figures', '03_PSF_EXPERIMENT_RESULTS', ...
    '01_global_bads_fit', 'figures', 'center9_pillar_fit_20x_50x');
fit_root = fullfile(PROJECT_ROOT, 'PSF_Fitting', 'output', ...
    'pillar_via_junction_psf_20260713');
output_root = fileparts(mfilename('fullpath'));
nsr_values = [0.002, 0.004, 0.008, 0.015, 0.03, ...
    0.050:0.0005:0.080, 0.12, 0.20, 0.35, 0.60, 1.0, 1.8, 3.0];
rl_iterations = [1, 2, 3, 5, 8, 12, 20];
cfg = struct('label', {'20x', '50x'});

for k = 1:numel(cfg)
    label = cfg(k).label;
    I = im2double(imread(fullfile(figure_root, label, ...
        '05_original_pillar_3x3.bmp')));
    if size(I, 3) > 1, I = rgb2gray(I); end
    meta = jsondecode(fileread(fullfile(fit_root, label, ...
        'selected_frame.json')));
    loaded = load(fullfile(fit_root, label, 'fit_result', ...
        'PSF_fitted_2D_FOVstack.mat'), 'psf_grid');
    psf = squeeze(double(loaded.psf_grid));
    psf = psf / sum(psf(:));
    pad_y = floor(size(psf, 1) / 2);
    pad_x = floor(size(psf, 2) / 2);
    padded = padarray(I, [pad_y, pad_x], 'symmetric', 'both');

    % Estimate the slowly varying bright background before inverting the
    % dark pillars into a positive contrast image. The structuring element
    % is larger than a pillar radius but smaller than the pillar pitch.
    background_radius = ceil(0.36 * double(meta.pitch_px));
    background = imclose(I, strel('disk', background_radius));
    contrast = max(background - I, 0);
    contrast_scale = prctile(contrast(:), 99.5);
    contrast = contrast / max(contrast_scale, eps);
    padded_contrast = padarray(contrast, [pad_y, pad_x], 'symmetric', 'both');

    direct_wiener = zeros([size(I), numel(nsr_values)]);
    contrast_wiener = zeros([size(I), numel(nsr_values)]);
    for idx = 1:numel(nsr_values)
        direct_full = deconvwnr(padded, psf, nsr_values(idx));
        direct_wiener(:, :, idx) = crop_padding(direct_full, size(I), pad_y, pad_x);

        contrast_full = deconvwnr(padded_contrast, psf, nsr_values(idx));
        restored_contrast = crop_padding(contrast_full, size(I), pad_y, pad_x);
        contrast_wiener(:, :, idx) = background - contrast_scale * restored_contrast;
    end

    contrast_rl = zeros([size(I), numel(rl_iterations)]);
    for idx = 1:numel(rl_iterations)
        rl_full = deconvlucy(padded_contrast, psf, rl_iterations(idx));
        restored_contrast = crop_padding(rl_full, size(I), pad_y, pad_x);
        contrast_rl(:, :, idx) = background - contrast_scale * restored_contrast;
    end

    save(fullfile(output_root, sprintf('%s_deconvolution_sweep.mat', label)), ...
        'I', 'psf', 'background', 'contrast', 'contrast_scale', ...
        'direct_wiener', 'contrast_wiener', 'contrast_rl', ...
        'nsr_values', 'rl_iterations', '-v7');
    fprintf('%s sweep saved: %d Wiener settings, %d RL settings.\n', ...
        label, numel(nsr_values), numel(rl_iterations));
end
end

function cropped = crop_padding(full_image, original_size, pad_y, pad_x)
cropped = full_image(pad_y + 1:pad_y + original_size(1), ...
    pad_x + 1:pad_x + original_size(2));
end
