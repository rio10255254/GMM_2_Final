function summary = run_20260924_center9(mode)
%RUN_20260924_CENTER9 Apply the existing SEM-diameter/BADS workflow to 25 frames.
if nargin < 1, mode = 'prepare'; end
run_root = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(run_root));
addpath(project_root);
addpath(fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts'));
addpath(fullfile(project_root, 'SimulatePSF'));
addpath(genpath(fullfile(project_root, 'bads-1.1.3')));

input_root = fullfile(run_root, 'fit_input');
fit_root = fullfile(run_root, 'fit_result');
gt_root = fullfile(input_root, 'GT');
if ~exist(input_root, 'dir'), mkdir(input_root); end
if ~exist(gt_root, 'dir'), mkdir(gt_root); end
if ~exist(fit_root, 'dir'), mkdir(fit_root); end
gt_path = fullfile(gt_root, 'gt_sem_cd.bmp');
mask_path = fullfile(input_root, 'loss_mask.bmp');

if strcmp(mode, 'prepare')
    locations = readtable(fullfile(run_root, 'center9_locations.csv'), TextType='string');
    assert(height(locations) == 225, 'Expected 25 x 9 located pillars.');
    ids = [36 35 34; 30 29 28; 24 23 22];
    assert(isequal(reshape(locations.sem_id_working(1:9), [3, 3])', ids), ...
        'SEM IDs do not match the inherited 20x image orientation.');
    source_root = fullfile(fileparts(project_root), '20260924');
    physical_cd_nm = center_9pillar_sem_cd();
    % Current locked 20x sequence uses a vertical flip of SEM data!J8:L10.
    image_cd_nm = flipud(physical_cd_nm);
    gt0 = [];
    mask0 = [];
    for image_index = 1:25
        rows = locations(locations.image_index == image_index, :);
        assert(height(rows) == 9, 'Every frame must have exactly nine locations.');
        assert(numel(unique(rows.image)) == 1, 'Mixed source images in one frame.');
        image_path = fullfile(source_root, char(rows.image(1)));
        assert(isfile(image_path), 'Source image is missing: %s', image_path);
        detection = struct( ...
            'selected_centers', [rows.x rows.y], ...
            'selected_radii', repmat(mean(physical_cd_nm(:)) / 2 / 172.5, 9, 1), ...
            'pitch_px', 5 / (3.45 / 20), ...
            'polarity', 'dark', ...
            'magnification', 20, ...
            'pillar_junction_corner', "top-left");
        pair = build_center_9pillar_fit_pair(image_path, detection, image_cd_nm);
        if image_index == 1
            gt0 = pair.gt;
            mask0 = pair.loss_mask;
            imwrite(uint8(round(gt0 * 255)), gt_path);
            imwrite(uint8(mask0) * 255, mask_path);
        else
            assert(isequal(pair.gt, gt0) && isequal(pair.loss_mask, mask0), ...
                'SEM target or fitting mask changed across frames.');
        end
        input_name = sprintf('fit_input_%02d.bmp', image_index);
        imwrite(uint8(round(pair.fit_input * 255)), fullfile(input_root, input_name));
        fprintf('Prepared %02d/25: %s\n', image_index, char(rows.image(1)));
    end
    summary = struct('input_root', input_root, 'gt_path', gt_path, ...
        'mask_path', mask_path, 'image_count', 25);
elseif strcmp(mode, 'fit') || strcmp(mode, 'fit_wide2') || strcmp(mode, 'fit_wide4')
    files = dir(fullfile(input_root, 'fit_input_*.bmp'));
    assert(numel(files) == 25 && isfile(gt_path) && isfile(mask_path), ...
        'Prepared input set is incomplete.');
    bound_scale = 1;
    use_warm_start = true;
    if strcmp(mode, 'fit_wide2') || strcmp(mode, 'fit_wide4')
        if strcmp(mode, 'fit_wide2'), bound_scale = 2; else, bound_scale = 4; end
        fit_root = fullfile(run_root, sprintf('fit_wide%d', bound_scale));
        use_warm_start = false;
    end
    summary = HDR_fitting_2D_WholeFOV_reasonable_v1( ...
        'subset_indices', 1:25, ...
        'input_folder', input_root, ...
        'gt_path', gt_path, ...
        'loss_mask_path', mask_path, ...
        'grid_rows', 5, ...
        'grid_cols', 5, ...
        'image_pattern', 'fit_input_*.bmp', ...
        'warm_start', use_warm_start, ...
        'pre_alignment', false, ...
        'lock_tilt', true, ...
        'psf_scale', 0.125 / (3.45 / 20), ...
        'aberration_bound_scale', bound_scale, ...
        'output_root', fit_root, ...
        'use_gpu', false);
    assert(summary.num_images == 25, 'BADS did not return all 25 fits.');
    fprintf('Completed 25 BADS fits (bound scale %g): %s\n', ...
        bound_scale, char(summary.batch_results_path));
else
    error('Unknown mode: %s', mode);
end
end
