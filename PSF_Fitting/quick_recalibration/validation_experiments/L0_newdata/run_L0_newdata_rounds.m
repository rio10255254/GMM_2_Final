% run_L0_newdata_rounds.m
%
% New-data L0 run for Circle_Round1/2/3.
% The three Circle_Round folders are capture repeats. Each folder contains
% an 11x11 grid, with two consecutive frames at each position. The prepared
% inputs use frame 1 from each pair. The fitting target is the circle edge:
% center square blocks are filled in the prepared crops and excluded from
% the loss through circle_edge_mask.bmp.

clear; clc;

%% ===== Configuration =====
fov_indices = [1, 6, 11, 56, 61, 66, 111, 116, 121];  % 11x11 old L0 pattern
trial_range = [1, 15];
seed_base = 0;
skip_existing = true;
grid_rows = 11;
grid_cols = 11;
repeats_per_position = 2;
frame_number_used = 1;
pre_alignment = false;
use_gpu = [];  % [] lets the fitter choose its default GPU policy.

target_policy = 'circle_boundary_only';
center_block_policy = 'filled_in_prepared_inputs_and_excluded_by_circle_edge_mask';

rounds = struct([]);
rounds(1).round_name = 'Circle_Round1';
rounds(1).input_folder = fullfile('quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round1', 'inputs_primary');
rounds(1).output_root = fullfile('quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round1', 'outputs');

rounds(2).round_name = 'Circle_Round2';
rounds(2).input_folder = fullfile('quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round2', 'inputs_primary');
rounds(2).output_root = fullfile('quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round2', 'outputs');

rounds(3).round_name = 'Circle_Round3';
rounds(3).input_folder = fullfile('quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round3', 'inputs_primary');
rounds(3).output_root = fullfile('quick_recalibration', 'validation_experiments', ...
    'L0_newdata_round3', 'outputs');

n_trials = trial_range(2);

%% ===== Locate PSF_Fitting root from this script =====
script_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(script_dir)));

expected_marker = fullfile(project_root, 'HDR_fitting_2D_WholeFOV_impl.m');
if ~isfile(expected_marker)
    error('Failed to locate PSF_Fitting root: %s', project_root);
end

cd(project_root);
fprintf('project_root: %s\n', project_root);

addpath(fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts'));
addpath(fullfile(project_root, 'SimulatePSF'));

fprintf('\n========================================\n');
fprintf(' New-data L0: %d rounds, %d FOV points, trials %d-%d\n', ...
    numel(rounds), numel(fov_indices), trial_range(1), trial_range(2));
fprintf(' FOV indices: %s\n', mat2str(fov_indices));
fprintf(' Grid       : %dx%d, %d frames/position, using frame %d\n', ...
    grid_rows, grid_cols, repeats_per_position, frame_number_used);
fprintf(' Target     : %s\n', target_policy);
fprintf(' Center mask: %s\n', center_block_policy);
fprintf(' Started at : %s\n', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
fprintf('========================================\n\n');

overall_timer = tic;

for round_idx = 1:numel(rounds)
    round_cfg = rounds(round_idx);
    input_folder = round_cfg.input_folder;
    output_root = round_cfg.output_root;
    gt_path = fullfile(input_folder, 'GT', 'GT_901_with_Block_proc.bmp');
    loss_mask_path = fullfile(input_folder, 'GT', 'circle_edge_mask.bmp');

    if ~isfolder(input_folder)
        error('Prepared input folder not found: %s', input_folder);
    end
    if ~isfile(gt_path)
        error('Prepared circle-only GT not found: %s', gt_path);
    end
    if ~isfile(loss_mask_path)
        error('Circle edge mask not found: %s', loss_mask_path);
    end

    if ~exist(output_root, 'dir')
        mkdir(output_root);
    end

    trial_dirs = strings(1, n_trials);
    trial_seconds = nan(1, n_trials);
    new_trial_count = 0;

    fprintf('\n----------------------------------------\n');
    fprintf(' Round %d/%d: %s\n', round_idx, numel(rounds), round_cfg.round_name);
    fprintf(' Input : %s\n', input_folder);
    fprintf(' Output: %s\n', output_root);
    fprintf(' Mask  : %s\n', loss_mask_path);
    fprintf('----------------------------------------\n');

    round_timer = tic;

    for trial_idx = trial_range(1):trial_range(2)
        trial_dir = fullfile(output_root, sprintf('trial_%02d', trial_idx));
        trial_dirs(trial_idx) = string(trial_dir);

        existing_stack = fullfile(trial_dir, 'PSF_fitted_2D_FOVstack.mat');
        if skip_existing && isfile(existing_stack)
            fprintf('--- %s trial %02d exists, skip (%s)\n', ...
                round_cfg.round_name, trial_idx, trial_dir);
            continue
        end

        timestamp = char(datetime('now', 'Format', 'HH:mm:ss'));
        if new_trial_count == 0
            eta_str = '(ETA unknown until first new trial finishes)';
        else
            finished_seconds = trial_seconds(~isnan(trial_seconds));
            avg_per_trial = mean(finished_seconds);
            remaining_count = trial_range(2) - trial_idx + 1;
            eta_str = sprintf('(ETA ~%.1f min for remaining %d trials)', ...
                avg_per_trial * remaining_count / 60, remaining_count);
        end

        fprintf('\n>>> [%s] %s trial %02d/%02d starting %s\n', ...
            timestamp, round_cfg.round_name, trial_idx, trial_range(2), eta_str);
        fprintf('    seed: rng(%d)\n', seed_base + trial_idx);
        fprintf('    output: %s\n\n', trial_dir);

        rng(seed_base + trial_idx);

        fit_args = { ...
            'subset_indices', fov_indices, ...
            'input_folder', input_folder, ...
            'gt_path', gt_path, ...
            'loss_mask_path', loss_mask_path, ...
            'grid_rows', 11, ...
            'grid_cols', 11, ...
            'pre_alignment', pre_alignment, ...
            'output_root', trial_dir};
        if ~isempty(use_gpu)
            fit_args = [fit_args, {'use_gpu', use_gpu}]; %#ok<AGROW>
        end

        trial_timer = tic;
        HDR_fitting_2D_WholeFOV_reasonable_v1(fit_args{:});
        trial_seconds(trial_idx) = toc(trial_timer);
        new_trial_count = new_trial_count + 1;

        timestamp = char(datetime('now', 'Format', 'HH:mm:ss'));
        csv_path = fullfile(trial_dir, 'batch_results.csv');
        if isfile(csv_path)
            try
                tbl = readtable(csv_path, TextType = "string");
                fprintf('<<< [%s] %s trial %02d done in %.1f s (%.2f min)\n', ...
                    timestamp, round_cfg.round_name, trial_idx, ...
                    trial_seconds(trial_idx), trial_seconds(trial_idx) / 60);
                fprintf('    fval: min=%.2f, mean=%.2f, max=%.2f | mean iters: %.0f\n', ...
                    min(tbl.fval), mean(tbl.fval), max(tbl.fval), mean(tbl.iterations));
            catch
                fprintf('<<< [%s] %s trial %02d done in %.1f s (csv read failed)\n', ...
                    timestamp, round_cfg.round_name, trial_idx, trial_seconds(trial_idx));
            end
        else
            fprintf('<<< [%s] %s trial %02d done in %.1f s (no csv found)\n', ...
                timestamp, round_cfg.round_name, trial_idx, trial_seconds(trial_idx));
        end
    end

    round_seconds = toc(round_timer);
    write_round_manifest( ...
        output_root, round_cfg, input_folder, gt_path, loss_mask_path, ...
        fov_indices, grid_rows, grid_cols, repeats_per_position, frame_number_used, ...
        trial_range, n_trials, seed_base, trial_dirs, trial_seconds, ...
        round_seconds, project_root, target_policy, center_block_policy, ...
        pre_alignment, use_gpu);

    fprintf('\nRound %s done. Elapsed %.1f min. Manifest: %s\n', ...
        round_cfg.round_name, round_seconds / 60, fullfile(output_root, 'manifest.json'));
end

total_seconds = toc(overall_timer);
fprintf('\n========================================\n');
fprintf(' New-data L0 finished in %.1f min\n', total_seconds / 60);
fprintf('========================================\n');


function write_round_manifest( ...
    output_root, round_cfg, input_folder, gt_path, loss_mask_path, ...
    fov_indices, grid_rows, grid_cols, repeats_per_position, frame_number_used, ...
    trial_range, n_trials, seed_base, trial_dirs, trial_seconds, ...
    total_seconds, project_root, target_policy, center_block_policy, ...
    pre_alignment, use_gpu)

    [git_status, git_commit] = system('git -C "d:/GMM_2_Final" rev-parse HEAD');
    if git_status ~= 0
        git_commit = 'unknown';
    else
        git_commit = strtrim(git_commit);
    end

    [git_status, git_branch] = system('git -C "d:/GMM_2_Final" rev-parse --abbrev-ref HEAD');
    if git_status ~= 0
        git_branch = 'unknown';
    else
        git_branch = strtrim(git_branch);
    end

    try
        gpu_available = gpuDeviceCount > 0;
    catch
        gpu_available = false;
    end

    manifest = struct();
    manifest.experiment = 'L0_newdata_circle_edge';
    manifest.design_doc = 'PSF_Fitting/quick_recalibration/DESIGN_TW.md';
    manifest.round_name = round_cfg.round_name;
    manifest.repeat_role = 'Circle_Round1/2/3 are capture repeats; two frames per position are duplicate frames';
    manifest.input_folder = input_folder;
    manifest.output_root = output_root;
    manifest.gt_path = gt_path;
    manifest.loss_mask_path = loss_mask_path;
    manifest.image_pattern = 'VisionTop_*.bmp';
    manifest.target_policy = target_policy;
    manifest.center_block_policy = center_block_policy;
    manifest.fov_indices = fov_indices;
    manifest.grid_rows = grid_rows;
    manifest.grid_cols = grid_cols;
    manifest.repeats_per_position = repeats_per_position;
    manifest.frame_number_used = frame_number_used;
    manifest.trial_range = trial_range;
    manifest.n_trials = n_trials;
    manifest.seed_base = seed_base;
    manifest.rng_seeds = seed_base + (1:n_trials);
    manifest.trial_dirs = cellstr(trial_dirs);
    manifest.trial_seconds = trial_seconds;
    manifest.total_seconds = total_seconds;
    manifest.completed_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
    manifest.matlab_version = version;
    manifest.gpu_available = gpu_available;
    manifest.use_gpu_requested = use_gpu;
    manifest.pre_alignment = pre_alignment;
    manifest.git_commit = git_commit;
    manifest.git_branch = git_branch;
    manifest.project_root = project_root;

    started_dt = datetime('now') - seconds(total_seconds);
    started_dt.Format = 'yyyy-MM-dd HH:mm:ss';
    manifest.started_at = char(started_dt);

    manifest_path = fullfile(output_root, 'manifest.json');
    fid = fopen(manifest_path, 'w');
    fprintf(fid, '%s\n', jsonencode(manifest, 'PrettyPrint', true));
    fclose(fid);
end
