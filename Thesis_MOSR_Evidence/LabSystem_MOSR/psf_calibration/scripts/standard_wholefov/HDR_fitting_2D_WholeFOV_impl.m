% Copied for LabSystem_MOSR from D:/GMM_2_Final/PSF_Fitting/HDR_fitting_2D_WholeFOV_impl.m.
% Keeps the project-standard Whole-FOV Zernike/BADS workflow; only lab data
% paths are parameterized in this copy.
function summary = HDR_fitting_2D_WholeFOV_impl(varargin)
parser = inputParser;
parser.addParameter('subset_indices', 1:100, @(x) isnumeric(x) && ~isempty(x));
parser.addParameter('grid_rows', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('grid_cols', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('source_grid_cols', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('warm_start', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('pre_alignment', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('lock_tilt', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('output_root', fullfile('Crop_circle_FreqFiltered', 'Fits'), @(x) ischar(x) || isstring(x));
parser.addParameter('input_folder', '', @(x) ischar(x) || isstring(x));
parser.addParameter('gt_path', '', @(x) ischar(x) || isstring(x));
parser.addParameter('psf_basis_path', '', @(x) ischar(x) || isstring(x));
parser.addParameter('dependency_root', 'D:/GMM_2_Final/PSF_Fitting', @(x) ischar(x) || isstring(x));
parser.addParameter('use_gpu', [], @(x) isempty(x) || islogical(x) || isnumeric(x));
parser.addParameter('prealign_search_radius', 2, @(x) isnumeric(x) && isscalar(x) && x >= 0);
parser.addParameter('prealign_search_step', 0.25, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('prealign_crop_size', 257, @(x) isnumeric(x) && isscalar(x) && x >= 33);
parser.addParameter('reuse_candidate_output_root', '', @(x) ischar(x) || isstring(x));
parser.parse(varargin{:});
opts = parser.Results;
opts.subset_indices = unique(double(opts.subset_indices(:))', 'stable');
opts.grid_rows = double(opts.grid_rows);
opts.grid_cols = double(opts.grid_cols);
opts.warm_start = logical(opts.warm_start);
opts.pre_alignment = logical(opts.pre_alignment);
opts.lock_tilt = logical(opts.lock_tilt);
opts.output_root = char(opts.output_root);
opts.reuse_candidate_output_root = char(opts.reuse_candidate_output_root);
opts.input_folder = char(opts.input_folder);
opts.gt_path = char(opts.gt_path);
opts.psf_basis_path = char(opts.psf_basis_path);
opts.dependency_root = char(opts.dependency_root);

project_root = fileparts(mfilename('fullpath'));
addpath(project_root);
if ~isempty(opts.dependency_root)
    addpath(opts.dependency_root);
    addpath(fullfile(opts.dependency_root, 'SimulatePSF'));
    addpath(genpath(fullfile(opts.dependency_root, 'bads-1.1.3')));
end

if ~exist(opts.output_root, 'dir')
    mkdir(opts.output_root);
end

if ~isempty(opts.reuse_candidate_output_root)
    candidate_root = opts.reuse_candidate_output_root;
    candidate_summary = struct('config_path', string(fullfile(candidate_root, 'candidate_config.json')));
else
    candidate_root = tempname;
    mkdir(candidate_root);
    temp_cleanup = onCleanup(@() cleanup_temp_root(candidate_root)); %#ok<NASGU>
    candidate_summary = HDR_fitting_2D_WholeFOV_reasonable_v1( ...
        'subset_indices', opts.subset_indices, ...
        'warm_start', opts.warm_start, ...
        'pre_alignment', opts.pre_alignment, ...
        'lock_tilt', opts.lock_tilt, ...
        'output_root', candidate_root, ...
        'use_gpu', opts.use_gpu, ...
        'prealign_search_radius', opts.prealign_search_radius, ...
        'prealign_search_step', opts.prealign_search_step, ...
        'prealign_crop_size', opts.prealign_crop_size, ...
        'source_grid_cols', opts.source_grid_cols, ...
        'input_folder', opts.input_folder, ...
        'gt_path', opts.gt_path, ...
        'psf_basis_path', opts.psf_basis_path, ...
        'dependency_root', opts.dependency_root);
end

candidate_table = readtable(fullfile(candidate_root, 'batch_results.csv'), TextType = "string");
candidate_stack = load(fullfile(candidate_root, 'PSF_fitted_2D_FOVstack.mat'));

legacy_table = candidate_table(:, {'filename', 'fval', 'iterations', 'seconds'});
writetable(legacy_table, fullfile(opts.output_root, 'batch_results.csv'));

[psf_grid, coef_grid, fval_map, iterations_map, filename_map] = repack_candidate_outputs(candidate_table, candidate_stack, opts.grid_rows, opts.grid_cols);
fov_psf_data = struct( ...
    'psf_grid', psf_grid, ...
    'coef_grid', coef_grid, ...
    'fval_map', fval_map, ...
    'iterations_map', iterations_map, ...
    'filename_map', filename_map, ...
    'grid_rows', opts.grid_rows, ...
    'grid_cols', opts.grid_cols, ...
    'ordering', "row-major-left-to-right");
save(fullfile(opts.output_root, 'PSF_fitted_2D_FOVstack.mat'), '-struct', 'fov_psf_data');

metadata = struct( ...
    'entry_point', 'HDR_fitting_2D_WholeFOV_impl', ...
    'description', 'Current Whole-FOV fitting implementation promoted from ValidationLab reasonable_v1.', ...
    'subset_indices', opts.subset_indices, ...
    'grid_rows', opts.grid_rows, ...
    'grid_cols', opts.grid_cols, ...
    'warm_start', opts.warm_start, ...
    'pre_alignment', opts.pre_alignment, ...
    'lock_tilt', opts.lock_tilt, ...
    'prealign_search_radius', opts.prealign_search_radius, ...
    'prealign_search_step', opts.prealign_search_step, ...
    'prealign_crop_size', opts.prealign_crop_size, ...
    'source_grid_cols', opts.source_grid_cols, ...
    'input_folder', opts.input_folder, ...
    'gt_path', opts.gt_path, ...
    'psf_basis_path', opts.psf_basis_path, ...
    'dependency_root', opts.dependency_root, ...
    'output_root', opts.output_root, ...
    'generated_at', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')), ...
    'reasonable_candidate_config_path', char(candidate_summary.config_path), ...
    'batch_results_path', fullfile(opts.output_root, 'batch_results.csv'), ...
    'stack_path', fullfile(opts.output_root, 'PSF_fitted_2D_FOVstack.mat'));
write_json(fullfile(opts.output_root, 'formal_config.json'), metadata);

summary = struct();
summary.output_root = string(opts.output_root);
summary.batch_results_path = string(fullfile(opts.output_root, 'batch_results.csv'));
summary.stack_path = string(fullfile(opts.output_root, 'PSF_fitted_2D_FOVstack.mat'));
summary.config_path = string(fullfile(opts.output_root, 'formal_config.json'));
summary.num_images = height(candidate_table);
summary.mean_fval = mean(candidate_table.fval);
summary.mean_iterations = mean(candidate_table.iterations);
summary.mean_peak_offset_y = mean(candidate_table.peak_offset_y);
summary.mean_peak_offset_x = mean(candidate_table.peak_offset_x);
end

function [psf_grid, coef_grid, fval_map, iterations_map, filename_map] = repack_candidate_outputs(candidate_table, candidate_stack, grid_rows, grid_cols)
psf_stack = candidate_stack.psf_grid;
psf_stack = reshape(psf_stack, size(psf_stack, 1), size(psf_stack, 2), []);
coef_stack = candidate_stack.coef_grid;
coef_stack = reshape(coef_stack, size(coef_stack, 1), []);

num_images = height(candidate_table);
if num_images > grid_rows * grid_cols
    error('grid_rows x grid_cols is too small for %d images.', num_images);
end

psf_grid = zeros(size(psf_stack, 1), size(psf_stack, 2), grid_rows, grid_cols);
coef_grid = zeros(size(coef_stack, 1), grid_rows, grid_cols);
fval_map = nan(grid_rows, grid_cols);
iterations_map = nan(grid_rows, grid_cols);
filename_map = strings(grid_rows, grid_cols);

use_source_layout = all(candidate_table.source_row >= 1 & candidate_table.source_row <= grid_rows & ...
    candidate_table.source_col >= 1 & candidate_table.source_col <= grid_cols);

for idx = 1:num_images
    if use_source_layout
        row_idx = candidate_table.source_row(idx);
        col_idx = candidate_table.source_col(idx);
    else
        row_idx = floor((idx - 1) / grid_cols) + 1;
        col_idx = mod(idx - 1, grid_cols) + 1;
    end

    psf_grid(:, :, row_idx, col_idx) = psf_stack(:, :, idx);
    coef_grid(:, row_idx, col_idx) = coef_stack(:, idx);
    fval_map(row_idx, col_idx) = candidate_table.fval(idx);
    iterations_map(row_idx, col_idx) = candidate_table.iterations(idx);
    filename_map(row_idx, col_idx) = candidate_table.filename(idx);
end
end

function cleanup_temp_root(temp_root)
if exist(temp_root, 'dir')
    try
        rmdir(temp_root, 's');
    catch
    end
end
end

function write_json(output_path, payload)
json_text = jsonencode(payload, PrettyPrint = true);
fid = fopen(output_path, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', json_text);
end
