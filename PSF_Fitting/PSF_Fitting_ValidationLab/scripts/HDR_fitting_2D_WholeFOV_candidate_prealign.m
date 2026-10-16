function summary = HDR_fitting_2D_WholeFOV_candidate_prealign(varargin)
global VLAB_CONTEXT VLAB_STATE

VLAB_CONTEXT = [];
VLAB_STATE = [];

opts = parse_inputs(varargin{:});
script_dir = fileparts(mfilename('fullpath'));
lab_root = fileparts(script_dir);
project_root = fileparts(lab_root);

addpath(script_dir);
addpath(project_root);
addpath(fullfile(project_root, 'SimulatePSF'));
addpath(genpath(fullfile(project_root, 'bads-1.1.3')));

opts.output_root = char(opts.output_root);
if ~exist(opts.output_root, 'dir')
    mkdir(opts.output_root);
end

context = candidate_load_context(project_root, opts);
if strcmp(opts.mode, 'evaluate_coefficients')
    [eval_table, stack_path, config_path] = candidate_evaluate_coefficients(context, opts);
    summary = struct();
    summary.output_root = string(opts.output_root);
    summary.evaluation_results_path = string(fullfile(opts.output_root, 'coefficient_evaluation.csv'));
    summary.stack_path = string(stack_path);
    summary.config_path = string(config_path);
    summary.num_cases = height(eval_table);
    summary.mean_loss = mean(eval_table.loss);
    VLAB_CONTEXT = [];
    VLAB_STATE = [];
    return
end

config = struct( ...
    'name', "candidate_flow", ...
    'subset_indices', opts.subset_indices, ...
    'warm_start', opts.warm_start, ...
    'pre_alignment', opts.pre_alignment, ...
    'lock_tilt', opts.lock_tilt, ...
    'psf_scale', opts.psf_scale, ...
    'prealign_search_radius', opts.prealign_search_radius, ...
    'prealign_search_step', opts.prealign_search_step, ...
    'output_dir', opts.output_root);

[batch_table, stack_path, config_path] = candidate_run_experiment(context, config);

summary = struct();
summary.output_root = string(opts.output_root);
summary.batch_results_path = string(fullfile(opts.output_root, 'batch_results.csv'));
summary.stack_path = string(stack_path);
summary.config_path = string(config_path);
summary.num_images = height(batch_table);
summary.mean_fval = mean(batch_table.fval);
summary.mean_iterations = mean(batch_table.iterations);
summary.mean_peak_offset_y = mean(batch_table.peak_offset_y);
summary.mean_peak_offset_x = mean(batch_table.peak_offset_x);

VLAB_CONTEXT = [];
VLAB_STATE = [];
end

function opts = parse_inputs(varargin)
parser = inputParser;
parser.addParameter('subset_indices', 1:100, @(x) isnumeric(x) && ~isempty(x));
parser.addParameter('input_folder', "", @(x) ischar(x) || isstring(x));
parser.addParameter('gt_path', "", @(x) ischar(x) || isstring(x));
parser.addParameter('loss_mask_path', "", @(x) ischar(x) || isstring(x));
parser.addParameter('grid_rows', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('grid_cols', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('image_pattern', 'VisionTop_*.bmp', @(x) ischar(x) || isstring(x));
parser.addParameter('warm_start', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('pre_alignment', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('lock_tilt', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('output_root', fullfile(fileparts(fileparts(mfilename('fullpath'))), 'outputs', 'candidate_flow'), @(x) ischar(x) || isstring(x));
parser.addParameter('use_gpu', [], @(x) isempty(x) || islogical(x) || isnumeric(x));
parser.addParameter('prealign_search_radius', 2, @(x) isnumeric(x) && isscalar(x) && x >= 0);
parser.addParameter('prealign_step', [], @(x) isempty(x) || (isnumeric(x) && isscalar(x) && x > 0));
parser.addParameter('prealign_search_step', 0.25, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('prealign_crop_size', 257, @(x) isnumeric(x) && isscalar(x) && x >= 33);
parser.addParameter('psf_scale', 1, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('aberration_bound_scale', 1, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('gradient_weight', 8e4, @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x >= 0);
parser.addParameter('rho_divisor', 2, @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x > 0);
parser.addParameter('fix_locked_tilt_in_bads', false, @(x) islogical(x) || isnumeric(x));
parser.addParameter('fix_amplitude_in_bads', false, @(x) islogical(x) || isnumeric(x));
parser.addParameter('profile_gain', false, @(x) islogical(x) || isnumeric(x));
parser.addParameter('plausible_bound_fraction', 1, @(x) isnumeric(x) && isscalar(x) && x > 0 && x <= 1);
parser.addParameter('bads_options', struct(), @(x) isstruct(x) && isscalar(x));
parser.addParameter('mode', 'fit', @(x) ischar(x) || isstring(x));
parser.addParameter('coefficient_csv_path', "", @(x) ischar(x) || isstring(x));
parser.parse(varargin{:});
opts = parser.Results;
opts.subset_indices = unique(double(opts.subset_indices(:))', 'stable');
opts.input_folder = char(opts.input_folder);
opts.gt_path = char(opts.gt_path);
opts.loss_mask_path = char(opts.loss_mask_path);
opts.grid_rows = double(opts.grid_rows);
opts.grid_cols = double(opts.grid_cols);
opts.image_pattern = char(opts.image_pattern);
opts.warm_start = logical(opts.warm_start);
opts.pre_alignment = logical(opts.pre_alignment);
opts.lock_tilt = logical(opts.lock_tilt);
opts.mode = char(opts.mode);
if ~ismember(opts.mode, {'fit', 'evaluate_coefficients'})
    error('Unsupported mode: %s', opts.mode);
end
opts.coefficient_csv_path = char(opts.coefficient_csv_path);
if strcmp(opts.mode, 'evaluate_coefficients') && strlength(string(opts.coefficient_csv_path)) == 0
    error('coefficient_csv_path is required when mode is evaluate_coefficients.');
end
if ~isempty(opts.prealign_step)
    opts.prealign_search_step = opts.prealign_step;
end
end

function context = candidate_load_context(project_root, opts)
if strlength(string(opts.input_folder)) == 0
    input_folder = fullfile(project_root, 'Crop_circle_FreqFiltered');
else
    input_folder = opts.input_folder;
end
if strlength(string(opts.gt_path)) == 0
    gt_path = fullfile(input_folder, 'GT', 'GT_901_with_Block_proc.bmp');
else
    gt_path = opts.gt_path;
end
if strlength(string(opts.loss_mask_path)) == 0
    loss_mask_path = "";
else
    loss_mask_path = opts.loss_mask_path;
end
if ~isfolder(input_folder)
    error('Input folder not found: %s', input_folder);
end
if ~isfile(gt_path)
    error('GT image not found: %s', gt_path);
end
if strlength(string(loss_mask_path)) > 0 && ~isfile(loss_mask_path)
    error('Loss mask image not found: %s', loss_mask_path);
end

file_list = dir(fullfile(input_folder, opts.image_pattern));
file_list = file_list(~[file_list.isdir]);
if isempty(file_list)
    error('No input images found in %s matching %s', input_folder, opts.image_pattern);
end

file_numbers = nan(1, numel(file_list));
for fi = 1:numel(file_list)
    tokens = regexp(file_list(fi).name, '_(\d+)\.bmp$', 'tokens', 'once');
    if isempty(tokens)
        file_numbers(fi) = fi;
    else
        file_numbers(fi) = str2double(tokens{1});
    end
end
[~, order] = sort(file_numbers);
file_list = file_list(order);

gt_cpu = im2double(imread(gt_path));
loss_mask_cpu = [];
if strlength(string(loss_mask_path)) > 0
    loss_mask_cpu = imread(loss_mask_path) > 0;
    if ~isequal(size(loss_mask_cpu), size(gt_cpu))
        error('Loss mask size %s does not match GT size %s', mat2str(size(loss_mask_cpu)), mat2str(size(gt_cpu)));
    end
end
psf_data = load(fullfile(project_root, 'SimulatePSF', 'psf_multi.mat'), 'psf_multi');
psf_slice_cpu = double(psf_data.psf_multi);
if abs(opts.psf_scale - 1) > eps
    psf_slice_cpu = resample_centered_psf(psf_slice_cpu, opts.psf_scale);
end

if isempty(opts.use_gpu)
    use_gpu = false;
    try
        use_gpu = gpuDeviceCount > 0;
    catch
        use_gpu = false;
    end
else
    use_gpu = logical(opts.use_gpu);
end

if use_gpu
    psf_slice = gpuArray(psf_slice_cpu);
    gt = gpuArray(gt_cpu);
    if ~isempty(loss_mask_cpu)
        loss_mask = gpuArray(loss_mask_cpu);
    else
        loss_mask = [];
    end
else
    psf_slice = psf_slice_cpu;
    gt = gt_cpu;
    loss_mask = loss_mask_cpu;
end

[h_psf, w_psf] = size(psf_slice_cpu);
pupil_res = floor((min(h_psf, w_psf) - 1) / 2);
[Xg, Yg] = meshgrid(-pupil_res:pupil_res, -pupil_res:pupil_res);
rho_cpu = hypot(Xg, Yg) ./ pupil_res ./ opts.rho_divisor;
phi_cpu = atan2(Yg, Xg);
psf_f_cpu = fftshift(fft2(psf_slice_cpu));

[h_gt, w_gt] = size(gt_cpu);
[fx, fy] = meshgrid((-w_gt / 2:w_gt / 2 - 1) / w_gt, (-h_gt / 2:h_gt / 2 - 1) / h_gt);
freq_radius = hypot(fx, fy);
freq_mask_cpu = ~(freq_radius < 0.02 | freq_radius > 0.5);

if use_gpu
    rho = gpuArray(rho_cpu);
    phi = gpuArray(phi_cpu);
    psf_f = gpuArray(psf_f_cpu);
    freq_mask = gpuArray(freq_mask_cpu);
else
    rho = rho_cpu;
    phi = phi_cpu;
    psf_f = psf_f_cpu;
    freq_mask = freq_mask_cpu;
end

x0 = [0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.0];
lb = [-0.3 -0.3 -0.1 0 -0.1 -0.05 -0.05 -0.05 -0.05 -0.01 -0.01 0 -0.01 -0.01 0.8];
ub = [0.3 0.3 0.1 1.0 0.1 0.05 0.05 0.05 0.05 0.01 0.01 0.3 0.01 0.01 1.25];
lb(3:14) = lb(3:14) * opts.aberration_bound_scale;
ub(3:14) = ub(3:14) * opts.aberration_bound_scale;
if opts.fix_locked_tilt_in_bads
    if ~opts.lock_tilt
        error('fix_locked_tilt_in_bads requires lock_tilt=true.');
    end
    lb(1:2) = 0;
    ub(1:2) = 0;
end
if opts.fix_amplitude_in_bads
    lb(15) = 1;
    ub(15) = 1;
end
if opts.profile_gain && ~opts.fix_amplitude_in_bads
    error('profile_gain requires fix_amplitude_in_bads=true to avoid a flat amplitude variable.');
end
plb = x0 + opts.plausible_bound_fraction * (lb - x0);
pub = x0 + opts.plausible_bound_fraction * (ub - x0);

crop_size = min([opts.prealign_crop_size, h_gt, w_gt]);
if mod(crop_size, 2) == 0
    crop_size = crop_size - 1;
end
half_crop = floor(crop_size / 2);
center_row = floor((h_gt + 1) / 2);
center_col = floor((w_gt + 1) / 2);
crop_rows = (center_row - half_crop):(center_row + half_crop);
crop_cols = (center_col - half_crop):(center_col + half_crop);
gt_grad_norm = normlz(imgradient(gt_cpu));

file_info = repmat(struct('path', '', 'name', '', 'index', 0, 'row', 0, 'col', 0), 1, numel(file_list));
for fi = 1:numel(file_list)
    file_info(fi).path = fullfile(file_list(fi).folder, file_list(fi).name);
    file_info(fi).name = file_list(fi).name;
    file_info(fi).index = fi;
    file_info(fi).row = floor((fi - 1) / opts.grid_cols) + 1;
    file_info(fi).col = mod(fi - 1, opts.grid_cols) + 1;
end

if any(opts.subset_indices < 1) || any(opts.subset_indices > numel(file_list))
    error('subset_indices must be within 1..%d for input folder %s', numel(file_list), input_folder);
end

context = struct();
context.project_root = project_root;
context.input_folder = input_folder;
context.gt_path = gt_path;
context.loss_mask_path = loss_mask_path;
context.file_info = file_info;
context.use_gpu = use_gpu;
context.model = struct( ...
    'psf_slice', psf_slice, ...
    'gt', gt, ...
    'loss_mask', loss_mask, ...
    'amp', 1.0, ...
    'rho', rho, ...
    'phi', phi, ...
    'psf_f', psf_f, ...
    'freq_mask', freq_mask, ...
    'use_gpu', use_gpu);
context.x0 = x0;
context.lb = lb;
context.ub = ub;
context.plb = plb;
context.pub = pub;
context.aberration_bound_scale = opts.aberration_bound_scale;
context.gradient_weight = opts.gradient_weight;
context.rho_divisor = opts.rho_divisor;
context.fix_locked_tilt_in_bads = logical(opts.fix_locked_tilt_in_bads);
context.fix_amplitude_in_bads = logical(opts.fix_amplitude_in_bads);
context.profile_gain = logical(opts.profile_gain);
context.plausible_bound_fraction = opts.plausible_bound_fraction;
context.bads_options = opts.bads_options;
context.explicit_bads_config = opts.fix_locked_tilt_in_bads || opts.fix_amplitude_in_bads || ...
    opts.plausible_bound_fraction < 1 || ~isempty(fieldnames(opts.bads_options));
context.psf_size = size(psf_slice_cpu);
context.psf_center = [(context.psf_size(1) + 1) / 2, (context.psf_size(2) + 1) / 2];
context.psf_scale = opts.psf_scale;
context.prealign = struct( ...
    'search_radius', opts.prealign_search_radius, ...
    'search_step', opts.prealign_search_step, ...
    'search_values', -opts.prealign_search_radius:opts.prealign_search_step:opts.prealign_search_radius, ...
    'crop_rows', crop_rows, ...
    'crop_cols', crop_cols, ...
    'gt_grad_norm', gt_grad_norm);
end

function [batch_table, stack_path, config_path] = candidate_run_experiment(context, config)
global VLAB_CONTEXT VLAB_STATE

subset_indices = config.subset_indices;
num_images = numel(subset_indices);
psf_h = context.psf_size(1);
psf_w = context.psf_size(2);

psf_grid = zeros(psf_h, psf_w, 1, num_images);
coef_grid = zeros(numel(context.x0), 1, num_images);
fval_map = nan(1, num_images);
iterations_map = nan(1, num_images);
filename_map = strings(1, num_images);
source_file_index_map = nan(1, num_images);
source_row_map = nan(1, num_images);
source_col_map = nan(1, num_images);

rows = repmat(struct( ...
    'experiment_name', "", 'file_index', 0, 'source_row', 0, 'source_col', 0, ...
    'filename', "", 'warm_start', false, 'pre_alignment', false, 'lock_tilt', false, ...
    'prealign_shift_y', 0, 'prealign_shift_x', 0, 'prealign_score', 0, ...
    'fval', 0, 'iterations', 0, 'seconds', 0, ...
    'peak_y', 0, 'peak_x', 0, 'peak_offset_y', 0, 'peak_offset_x', 0, ...
    'centroid_y', 0, 'centroid_x', 0, 'centroid_offset_y', 0, 'centroid_offset_x', 0, ...
    'peak_edge_distance', 0, 'centroid_edge_distance', 0, 'edge_energy_ratio', 0, 'touches_edge', false), 1, num_images);

if config.warm_start
    x_prev = context.x0;
end

for ki = 1:num_images
    file_index = subset_indices(ki);
    file_entry = context.file_info(file_index);
    img_cpu = im2double(imread(file_entry.path));

    if config.pre_alignment
        align_info = candidate_prealign_image(img_cpu, context.prealign);
        fit_img_cpu = align_info.aligned_image;
    else
        align_info = struct('shift_y', 0, 'shift_x', 0, 'score', NaN, 'aligned_image', img_cpu);
        fit_img_cpu = img_cpu;
    end

    if context.use_gpu
        fit_img = gpuArray(fit_img_cpu);
    else
        fit_img = fit_img_cpu;
    end

    if config.warm_start && ki > 1
        x_init = x_prev;
    else
        x_init = context.x0;
    end

    VLAB_CONTEXT = struct('model', context.model, 'img', fit_img, ...
        'lock_tilt', config.lock_tilt, 'gradient_weight', context.gradient_weight, ...
        'profile_gain', context.profile_gain);
    VLAB_STATE = struct('iter_count', 0, 'loss_history', zeros(0, 5));

    t_start = tic;
    if context.explicit_bads_config
        [x, fval, exitflag] = bads(@candidate_aberration_loss, x_init, ...
            context.lb, context.ub, context.plb, context.pub, [], context.bads_options);
    else
        [x, fval, exitflag] = bads(@candidate_aberration_loss, x_init, context.lb, context.ub);
    end
    elapsed = toc(t_start);
    fprintf('BADS frame %d: exitflag=%d loss=%.9g calls=%d seconds=%.3f\n', ...
        file_index, exitflag, fval, VLAB_STATE.iter_count, elapsed);

    if config.warm_start
        x_prev = x;
    end

    fitted_psf = gather(candidate_build_fitted_psf(x, context.model, config.lock_tilt));
    metrics = candidate_compute_psf_metrics(fitted_psf, context.psf_center);

    psf_grid(:, :, 1, ki) = fitted_psf;
    coef_grid(:, 1, ki) = x(:);
    fval_map(1, ki) = double(fval);
    iterations_map(1, ki) = VLAB_STATE.iter_count;
    filename_map(1, ki) = string(file_entry.name);
    source_file_index_map(1, ki) = file_index;
    source_row_map(1, ki) = file_entry.row;
    source_col_map(1, ki) = file_entry.col;

    rows(ki).experiment_name = "candidate_flow";
    rows(ki).file_index = file_index;
    rows(ki).source_row = file_entry.row;
    rows(ki).source_col = file_entry.col;
    rows(ki).filename = string(file_entry.name);
    rows(ki).warm_start = config.warm_start;
    rows(ki).pre_alignment = config.pre_alignment;
    rows(ki).lock_tilt = config.lock_tilt;
    rows(ki).prealign_shift_y = align_info.shift_y;
    rows(ki).prealign_shift_x = align_info.shift_x;
    rows(ki).prealign_score = align_info.score;
    rows(ki).fval = double(fval);
    rows(ki).iterations = VLAB_STATE.iter_count;
    rows(ki).seconds = elapsed;
    rows(ki).peak_y = metrics.peak_y;
    rows(ki).peak_x = metrics.peak_x;
    rows(ki).peak_offset_y = metrics.peak_offset_y;
    rows(ki).peak_offset_x = metrics.peak_offset_x;
    rows(ki).centroid_y = metrics.centroid_y;
    rows(ki).centroid_x = metrics.centroid_x;
    rows(ki).centroid_offset_y = metrics.centroid_offset_y;
    rows(ki).centroid_offset_x = metrics.centroid_offset_x;
    rows(ki).peak_edge_distance = metrics.peak_edge_distance;
    rows(ki).centroid_edge_distance = metrics.centroid_edge_distance;
    rows(ki).edge_energy_ratio = metrics.edge_energy_ratio;
    rows(ki).touches_edge = metrics.touches_edge;
end

batch_table = struct2table(rows);
writetable(batch_table, fullfile(config.output_dir, 'batch_results.csv'));

stack_payload = struct( ...
    'psf_grid', psf_grid, ...
    'coef_grid', coef_grid, ...
    'fval_map', fval_map, ...
    'iterations_map', iterations_map, ...
    'filename_map', filename_map, ...
    'grid_rows', 1, ...
    'grid_cols', num_images, ...
    'ordering', 'subset-order', ...
    'source_file_index_map', source_file_index_map, ...
    'source_row_map', source_row_map, ...
    'source_col_map', source_col_map, ...
    'subset_indices', subset_indices, ...
    'warm_start', config.warm_start, ...
    'pre_alignment', config.pre_alignment, ...
    'lock_tilt', config.lock_tilt, ...
    'psf_scale', context.psf_scale, ...
    'aberration_bound_scale', context.aberration_bound_scale, ...
    'gradient_weight', context.gradient_weight, ...
    'rho_divisor', context.rho_divisor, ...
    'fix_locked_tilt_in_bads', context.fix_locked_tilt_in_bads, ...
    'fix_amplitude_in_bads', context.fix_amplitude_in_bads, ...
    'profile_gain', context.profile_gain, ...
    'plausible_bound_fraction', context.plausible_bound_fraction, ...
    'prealign_search_radius', config.prealign_search_radius, ...
    'prealign_search_step', config.prealign_search_step);
stack_path = fullfile(config.output_dir, 'PSF_fitted_2D_FOVstack.mat');
save(stack_path, '-struct', 'stack_payload');

metadata = struct( ...
    'entry_point', 'HDR_fitting_2D_WholeFOV_candidate_prealign', ...
    'subset_indices', subset_indices, ...
    'warm_start', config.warm_start, ...
    'pre_alignment', config.pre_alignment, ...
    'lock_tilt', config.lock_tilt, ...
    'psf_scale', context.psf_scale, ...
    'aberration_bound_scale', context.aberration_bound_scale, ...
    'gradient_weight', context.gradient_weight, ...
    'rho_divisor', context.rho_divisor, ...
    'fix_locked_tilt_in_bads', context.fix_locked_tilt_in_bads, ...
    'fix_amplitude_in_bads', context.fix_amplitude_in_bads, ...
    'plausible_bound_fraction', context.plausible_bound_fraction, ...
    'bads_options', context.bads_options, ...
    'profile_gain', context.profile_gain, ...
    'prealign_search_radius', config.prealign_search_radius, ...
    'prealign_search_step', config.prealign_search_step, ...
    'project_root', context.project_root, ...
    'input_folder', context.input_folder, ...
    'gt_path', context.gt_path, ...
    'loss_mask_path', context.loss_mask_path, ...
    'output_dir', config.output_dir, ...
    'generated_at', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
config_path = fullfile(config.output_dir, 'candidate_config.json');
candidate_write_json(config_path, metadata);
end

function [eval_table, stack_path, config_path] = candidate_evaluate_coefficients(context, opts)
global VLAB_CONTEXT VLAB_STATE

if ~isfile(opts.coefficient_csv_path)
    error('Coefficient CSV not found: %s', opts.coefficient_csv_path);
end

coef_table = readtable(opts.coefficient_csv_path, TextType = "string");
required_columns = ["file_index", compose("x%d", 1:15)];
missing_columns = setdiff(required_columns, string(coef_table.Properties.VariableNames));
if ~isempty(missing_columns)
    error('Coefficient CSV is missing required columns: %s', strjoin(missing_columns, ', '));
end

if ismember("case_id", string(coef_table.Properties.VariableNames))
    case_ids = string(coef_table.case_id);
else
    case_ids = "case_" + compose("%04d", (1:height(coef_table))');
end

num_cases = height(coef_table);
psf_h = context.psf_size(1);
psf_w = context.psf_size(2);
psf_grid = zeros(psf_h, psf_w, 1, num_cases);
coef_grid = zeros(numel(context.x0), 1, num_cases);
loss_map = nan(1, num_cases);
filename_map = strings(1, num_cases);
case_id_map = strings(1, num_cases);
source_file_index_map = nan(1, num_cases);
source_row_map = nan(1, num_cases);
source_col_map = nan(1, num_cases);

rows = repmat(struct( ...
    'case_id', "", 'file_index', 0, 'source_row', 0, 'source_col', 0, ...
    'filename', "", 'lock_tilt', false, 'pre_alignment', false, ...
    'prealign_shift_y', 0, 'prealign_shift_x', 0, 'prealign_score', 0, ...
    'loss', 0, 'iterations', 0, ...
    'psf_sum', 0, 'psf_peak', 0, ...
    'peak_y', 0, 'peak_x', 0, 'peak_offset_y', 0, 'peak_offset_x', 0, ...
    'centroid_y', 0, 'centroid_x', 0, 'centroid_offset_y', 0, 'centroid_offset_x', 0, ...
    'peak_edge_distance', 0, 'centroid_edge_distance', 0, 'edge_energy_ratio', 0, 'touches_edge', false), 1, num_cases);

coef_columns = compose("x%d", 1:15);
for ci = 1:num_cases
    file_index = double(coef_table.file_index(ci));
    if file_index < 1 || file_index > numel(context.file_info)
        error('file_index must be within 1..%d. Got %d at row %d.', numel(context.file_info), file_index, ci);
    end

    file_entry = context.file_info(file_index);
    img_cpu = im2double(imread(file_entry.path));
    if opts.pre_alignment
        align_info = candidate_prealign_image(img_cpu, context.prealign);
        fit_img_cpu = align_info.aligned_image;
    else
        align_info = struct('shift_y', 0, 'shift_x', 0, 'score', NaN, 'aligned_image', img_cpu);
        fit_img_cpu = img_cpu;
    end

    if context.use_gpu
        fit_img = gpuArray(fit_img_cpu);
    else
        fit_img = fit_img_cpu;
    end

    coef = double(table2array(coef_table(ci, coef_columns)));
    VLAB_CONTEXT = struct('model', context.model, 'img', fit_img, ...
        'lock_tilt', opts.lock_tilt, 'gradient_weight', context.gradient_weight, ...
        'profile_gain', context.profile_gain);
    VLAB_STATE = struct('iter_count', 0, 'loss_history', zeros(0, 5));
    loss = candidate_aberration_loss(coef);

    fitted_psf = gather(candidate_build_fitted_psf(coef, context.model, opts.lock_tilt));
    metrics = candidate_compute_psf_metrics(fitted_psf, context.psf_center);

    psf_grid(:, :, 1, ci) = fitted_psf;
    coef_grid(:, 1, ci) = coef(:);
    loss_map(1, ci) = double(loss);
    filename_map(1, ci) = string(file_entry.name);
    case_id_map(1, ci) = case_ids(ci);
    source_file_index_map(1, ci) = file_index;
    source_row_map(1, ci) = file_entry.row;
    source_col_map(1, ci) = file_entry.col;

    rows(ci).case_id = case_ids(ci);
    rows(ci).file_index = file_index;
    rows(ci).source_row = file_entry.row;
    rows(ci).source_col = file_entry.col;
    rows(ci).filename = string(file_entry.name);
    rows(ci).lock_tilt = opts.lock_tilt;
    rows(ci).pre_alignment = opts.pre_alignment;
    rows(ci).prealign_shift_y = align_info.shift_y;
    rows(ci).prealign_shift_x = align_info.shift_x;
    rows(ci).prealign_score = align_info.score;
    rows(ci).loss = double(loss);
    rows(ci).iterations = VLAB_STATE.iter_count;
    rows(ci).psf_sum = double(sum(fitted_psf(:)));
    rows(ci).psf_peak = double(max(fitted_psf(:)));
    rows(ci).peak_y = metrics.peak_y;
    rows(ci).peak_x = metrics.peak_x;
    rows(ci).peak_offset_y = metrics.peak_offset_y;
    rows(ci).peak_offset_x = metrics.peak_offset_x;
    rows(ci).centroid_y = metrics.centroid_y;
    rows(ci).centroid_x = metrics.centroid_x;
    rows(ci).centroid_offset_y = metrics.centroid_offset_y;
    rows(ci).centroid_offset_x = metrics.centroid_offset_x;
    rows(ci).peak_edge_distance = metrics.peak_edge_distance;
    rows(ci).centroid_edge_distance = metrics.centroid_edge_distance;
    rows(ci).edge_energy_ratio = metrics.edge_energy_ratio;
    rows(ci).touches_edge = metrics.touches_edge;
end

eval_table = struct2table(rows);
for coef_idx = 1:numel(context.x0)
    eval_table.(sprintf('x%d', coef_idx)) = squeeze(coef_grid(coef_idx, 1, :));
end
writetable(eval_table, fullfile(opts.output_root, 'coefficient_evaluation.csv'));

stack_payload = struct( ...
    'psf_grid', psf_grid, ...
    'coef_grid', coef_grid, ...
    'loss_map', loss_map, ...
    'filename_map', filename_map, ...
    'case_id_map', case_id_map, ...
    'grid_rows', 1, ...
    'grid_cols', num_cases, ...
    'ordering', 'coefficient-csv-order', ...
    'source_file_index_map', source_file_index_map, ...
    'source_row_map', source_row_map, ...
    'source_col_map', source_col_map, ...
    'lock_tilt', opts.lock_tilt, ...
    'pre_alignment', opts.pre_alignment);
stack_path = fullfile(opts.output_root, 'PSF_evaluated_coefficients.mat');
save(stack_path, '-struct', 'stack_payload');

metadata = struct( ...
    'entry_point', 'HDR_fitting_2D_WholeFOV_candidate_prealign', ...
    'mode', 'evaluate_coefficients', ...
    'coefficient_csv_path', opts.coefficient_csv_path, ...
    'project_root', context.project_root, ...
    'input_folder', context.input_folder, ...
    'gt_path', context.gt_path, ...
    'loss_mask_path', context.loss_mask_path, ...
    'output_dir', opts.output_root, ...
    'num_cases', num_cases, ...
    'pre_alignment', opts.pre_alignment, ...
    'lock_tilt', opts.lock_tilt, ...
    'generated_at', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
config_path = fullfile(opts.output_root, 'coefficient_evaluation_config.json');
candidate_write_json(config_path, metadata);
end

function loss = candidate_aberration_loss(coef)
% Optional gain profiling keeps exposure outside the PSF shape search.
global VLAB_CONTEXT VLAB_STATE
fitted_psf = candidate_build_fitted_psf(coef, VLAB_CONTEXT.model, VLAB_CONTEXT.lock_tilt);
pred = conv2(VLAB_CONTEXT.model.gt, fitted_psf, 'same');
if VLAB_CONTEXT.profile_gain
    gain_mask = VLAB_CONTEXT.model.loss_mask;
    if isempty(gain_mask)
        error('profile_gain requires a loss_mask_path.');
    end
    candidate_values = pred(gain_mask);
    observed_values = VLAB_CONTEXT.img(gain_mask);
    gain = max(0, sum(candidate_values .* observed_values) / ...
        max(sum(candidate_values .^ 2), eps));
    pred = gain .* pred;
end
pred_grad_norm = normlz(imgradient(pred));
img_grad_norm = normlz(imgradient(VLAB_CONTEXT.img));
if isfield(VLAB_CONTEXT.model, 'loss_mask') && ~isempty(VLAB_CONTEXT.model.loss_mask)
    mask = VLAB_CONTEXT.model.loss_mask;
    intensity_delta = VLAB_CONTEXT.img - pred;
    grad_delta = img_grad_norm - pred_grad_norm;
    intensity_loss = mean(intensity_delta(mask) .^ 2);
    grad_loss = mean(grad_delta(mask) .^ 2);
    loss = gather(intensity_loss + VLAB_CONTEXT.gradient_weight * grad_loss);
else
    pred_freq = abs(fftshift(fft2(pred))) .* VLAB_CONTEXT.model.freq_mask;
    img_freq = abs(fftshift(fft2(VLAB_CONTEXT.img))) .* VLAB_CONTEXT.model.freq_mask;
    freq_loss = mean((img_freq(:) - pred_freq(:)) .^ 2);
    grad_loss = mean((img_grad_norm(:) - pred_grad_norm(:)) .^ 2);
    loss = gather(freq_loss + VLAB_CONTEXT.gradient_weight * grad_loss);
end
VLAB_STATE.iter_count = VLAB_STATE.iter_count + 1;
end

function fitted_psf = candidate_build_fitted_psf(coef, model, lock_tilt)
coef = coef(:).';
if model.use_gpu && ~isa(coef, 'gpuArray')
    coef = gpuArray(coef);
end

rho = model.rho;
phi = model.phi;
psf_f = model.psf_f;
Z = zeros(1, 15, 'like', rho);
Z(2:15) = coef(1:14);
if lock_tilt
    Z(2) = 0;
    Z(3) = 0;
end
AC = coef(15);

W_phase = ...
    Z(1).*1 + ...
    Z(2).*2.*rho.*sin(phi) + ...
    Z(3).*2.*rho.*cos(phi) + ...
    Z(4).*sqrt(6).*rho.^2.*sin(2.*phi) + ...
    Z(5).*sqrt(3).*(2.*rho.^2-1) + ...
    Z(6).*sqrt(6).*rho.^2.*cos(2.*phi) + ...
    Z(7).*sqrt(8).*rho.^3.*sin(3.*phi) + ...
    Z(8).*sqrt(8).*(3.*rho.^2-2.*rho).*sin(phi) + ...
    Z(9).*sqrt(8).*(3.*rho.^2-2.*rho).*cos(phi) + ...
    Z(10).*sqrt(8).*rho.^3.*cos(3.*phi) + ...
    Z(11).*sqrt(10).*rho.^4.*sin(4.*phi) + ...
    Z(12).*sqrt(10).*(4.*rho.^4-3.*rho.^2).*sin(2.*phi) + ...
    Z(13).*sqrt(5).*(6.*rho.^4-6.*rho.^2+1) + ...
    Z(14).*sqrt(10).*(4.*rho.^4-3.*rho.^2).*cos(2.*phi) + ...
    Z(15).*sqrt(10).*rho.^4.*cos(4.*phi);

psf_a = psf_f .* (exp(1i .* 2 .* pi() .* W_phase) .^ 2);
fitted_psf = abs(ifft2(psf_a));
fitted_psf = fitted_psf ./ sum(fitted_psf(:));
fitted_psf = model.amp .* AC .* fitted_psf;
end

function align_info = candidate_prealign_image(img_cpu, prealign)
img_grad_norm = normlz(imgradient(img_cpu));
gt_crop = prealign.gt_grad_norm(prealign.crop_rows, prealign.crop_cols);
if isfield(prealign, 'search_values')
    search_values = prealign.search_values;
else
    search_values = -prealign.search_radius:prealign.search_step:prealign.search_radius;
end
best_score = -Inf;
best_shift = [0, 0];
for dy = search_values
    for dx = search_values
        shifted_grad = vlab_translate_image(img_grad_norm, dy, dx);
        shifted_crop = shifted_grad(prealign.crop_rows, prealign.crop_cols);
        score = candidate_ncc(gt_crop, shifted_crop);
        if score > best_score
            best_score = score;
            best_shift = [dy, dx];
        end
    end
end
align_info = struct('shift_y', best_shift(1), 'shift_x', best_shift(2), 'score', best_score, ...
    'aligned_image', vlab_translate_image(img_cpu, best_shift(1), best_shift(2)));
end

function metrics = candidate_compute_psf_metrics(psf, center)
[h, w] = size(psf);
[~, peak_idx] = max(psf(:));
[peak_y, peak_x] = ind2sub(size(psf), peak_idx);
[x_grid, y_grid] = meshgrid(1:w, 1:h);
mass = sum(psf(:));
centroid_x = sum(x_grid(:) .* psf(:)) ./ mass;
centroid_y = sum(y_grid(:) .* psf(:)) ./ mass;
edge_width = 3;
edge_mask = true(size(psf));
edge_mask((edge_width + 1):(end - edge_width), (edge_width + 1):(end - edge_width)) = false;
edge_energy_ratio = sum(psf(edge_mask)) ./ mass;
peak_edge_distance = min([peak_y - 1, h - peak_y, peak_x - 1, w - peak_x]);
centroid_edge_distance = min([centroid_y - 1, h - centroid_y, centroid_x - 1, w - centroid_x]);
touches_edge = peak_edge_distance <= 2 || edge_energy_ratio >= 0.05;
metrics = struct( ...
    'peak_y', double(peak_y), ...
    'peak_x', double(peak_x), ...
    'peak_offset_y', double(peak_y - center(1)), ...
    'peak_offset_x', double(peak_x - center(2)), ...
    'centroid_y', double(centroid_y), ...
    'centroid_x', double(centroid_x), ...
    'centroid_offset_y', double(centroid_y - center(1)), ...
    'centroid_offset_x', double(centroid_x - center(2)), ...
    'peak_edge_distance', double(peak_edge_distance), ...
    'centroid_edge_distance', double(centroid_edge_distance), ...
    'edge_energy_ratio', double(edge_energy_ratio), ...
    'touches_edge', logical(touches_edge));
end

function score = candidate_ncc(a, b)
a = double(a(:)); b = double(b(:));
a = a - mean(a); b = b - mean(b);
score = sum(a .* b) / (norm(a) * norm(b) + eps);
end

function candidate_write_json(output_path, payload)
json_text = jsonencode(payload, PrettyPrint = true);
fid = fopen(output_path, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', json_text);
end
