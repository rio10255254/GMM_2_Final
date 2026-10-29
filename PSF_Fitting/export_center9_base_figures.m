function export_center9_base_figures()
    PROJECT_ROOT = fileparts(fileparts(mfilename('fullpath')));
%EXPORT_CENTER9_BASE_FIGURES Refresh the corrected GT, PSF, and forward model.
fit_root = fullfile(PROJECT_ROOT, 'PSF_Fitting', 'output', ...
    'deconvolution_baseline_psf_20260715');
figure_root = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence', ...
    'Final_Data_Figures', '03_PSF_EXPERIMENT_RESULTS', ...
    '01_global_bads_fit', 'figures', 'center9_pillar_fit_20x_50x');
v42_root = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence', ...
    'Final_Data_Figures', '03_PSF_EXPERIMENT_RESULTS', ...
    '01_global_bads_fit', 'source_data', 'center9_pillar_fit_20x_50x', ...
    'v42_rerun_final', 'outputs', ...
    'reconstruct_progress_epoch_120_in_inputs_20260709_202713', 'reconstructed');

for label_cell = {'20x', '50x'}
    label = label_cell{1};
    case_root = fullfile(fit_root, label);
    out_root = fullfile(figure_root, label);
    if ~isfolder(out_root), mkdir(out_root); end
    meta = jsondecode(fileread(fullfile(case_root, 'selected_frame.json')));
    captured_full = imread(meta.selected_image);
    if size(captured_full, 3) > 1, captured_full = rgb2gray(captured_full); end
    centers = double(meta.pillar_centers_xy);
    pitch_px = double(meta.pitch_px);
    margin = 0.75 * pitch_px;
    x1 = max(1, floor(min(centers(:, 1)) - margin));
    x2 = min(size(captured_full, 2), ceil(max(centers(:, 1)) + margin));
    y1 = max(1, floor(min(centers(:, 2)) - margin));
    y2 = min(size(captured_full, 1), ceil(max(centers(:, 2)) + margin));
    captured = captured_full(y1:y2, x1:x2);
    imwrite(captured, fullfile(out_root, '01_captured_pillar_3x3.png'));
    imwrite(captured, fullfile(out_root, '05_original_pillar_3x3.png'));
    imwrite(captured, fullfile(out_root, '05_original_pillar_3x3.bmp'));
    v42_name = sprintf('%s_selected_pillar_frame.bmp', label);
    v42_full = imread(fullfile(v42_root, v42_name));
    if size(v42_full, 3) > 1, v42_full = rgb2gray(v42_full); end
    v42_crop = v42_full(y1:y2, x1:x2);
    imwrite(v42_crop, fullfile(out_root, ...
        '06_v42_e120_reconstruction_pillar_3x3.png'));
    imwrite(v42_crop, fullfile(out_root, ...
        '06_v42_e120_reconstruction_pillar_3x3.bmp'));
    gt = im2double(imread(fullfile(case_root, 'fit_input', 'GT', ...
        'gt_sem_cd.bmp')));
    measured = im2double(imread(fullfile(case_root, 'fit_input', ...
        'fit_input.bmp')));
    loaded = load(fullfile(case_root, 'fit_result', ...
        'PSF_fitted_2D_FOVstack.mat'), 'psf_grid');
    psf = squeeze(double(loaded.psf_grid));
    forward = conv2(gt, psf, 'same');

    imwrite(gt, fullfile(out_root, '02_sem_cd_ground_truth.png'));
    imwrite(min(max(forward, 0), 1), ...
        fullfile(out_root, '04_forward_reconstruction.png'));

    fig = figure('Visible', 'off', 'Color', 'w', 'Units', 'inches', ...
        'Position', [1, 1, 5.6, 5.0]);
    ax = axes(fig);
    imagesc(ax, psf);
    axis(ax, 'image'); axis(ax, 'off');
    colormap(ax, parula(256));
    cb = colorbar(ax);
    cb.FontName = 'Arial'; cb.FontSize = 8;
    cb.Label.String = 'PSF intensity';
    cb.Label.FontName = 'Arial'; cb.Label.FontSize = 9;
    exportgraphics(fig, fullfile(out_root, '03_fitted_psf.png'), ...
        'Resolution', 240, 'BackgroundColor', 'white');
    close(fig);

    % Numeric audit: the exported forward image must match the same corrected
    % GT and fitted PSF used in the fitting result.
    correlation = corr(measured(:), forward(:));
    fprintf('%s base figures refreshed; full-canvas correlation %.6f\n', ...
        label, correlation);
end
end
