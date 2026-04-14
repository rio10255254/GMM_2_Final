function summary = vlab_run_validation_lab(varargin)
global VLAB_CONTEXT VLAB_STATE

VLAB_CONTEXT = [];
VLAB_STATE = [];

opts = vlab_parse_inputs(varargin{:});
script_dir = fileparts(mfilename('fullpath'));
lab_root = fileparts(script_dir);
project_root = fileparts(lab_root);

opts.output_root = char(opts.output_root);
vlab_ensure_dir(opts.output_root);
vlab_ensure_dir(fullfile(opts.output_root, 'experiments'));
vlab_ensure_dir(fullfile(opts.output_root, 'figures'));
vlab_ensure_dir(fullfile(opts.output_root, 'reports'));
vlab_ensure_dir(fullfile(opts.output_root, 'tables'));

addpath(script_dir);
addpath(project_root);
addpath(fullfile(project_root, 'SimulatePSF'));
addpath(genpath(fullfile(project_root, 'bads-1.1.3')));

context = vlab_load_context(project_root, opts);
configs = vlab_get_experiment_configs( ...
    lab_root, ...
    'profile_name', opts.profile_name, ...
    'subset_indices', opts.subset_indices, ...
    'output_root', opts.output_root, ...
    'include_optional_experiment', opts.include_optional_experiment, ...
    'warm_start', opts.warm_start);

if ~isempty(opts.experiment_names)
    requested_names = string(opts.experiment_names);
    config_names = string({configs.name});
    configs = configs(ismember(config_names, requested_names));
end

if isempty(configs)
    error('No experiments selected.');
end

experiment_results = cell(1, numel(configs));
for ci = 1:numel(configs)
    fprintf('\n=== Running %s ===\n', configs(ci).name);
    experiment_results{ci} = vlab_run_experiment(context, configs(ci));
end
experiment_results = [experiment_results{:}];

summary = vlab_aggregate_existing_results( ...
    lab_root, ...
    'experiment_names', string({configs.name}), ...
    'output_root', opts.output_root);

VLAB_CONTEXT = [];
VLAB_STATE = [];
end

function opts = vlab_parse_inputs(varargin)
parser = inputParser;
parser.addParameter('subset_indices', [1 56 60 100], @(x) isnumeric(x) && ~isempty(x));
parser.addParameter('profile_name', 'subset4', @(x) ischar(x) || isstring(x));
parser.addParameter('warm_start', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('include_optional_experiment', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('output_root', fullfile(fileparts(fileparts(mfilename('fullpath'))), 'outputs'), @(x) ischar(x) || isstring(x));
parser.addParameter('experiment_names', strings(0, 1), @(x) isstring(x) || ischar(x) || iscellstr(x));
parser.addParameter('use_gpu', [], @(x) isempty(x) || islogical(x) || isnumeric(x));
parser.addParameter('prealign_search_radius', 2, @(x) isnumeric(x) && isscalar(x) && x >= 0);
parser.addParameter('prealign_search_step', 1.0, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('prealign_crop_size', 257, @(x) isnumeric(x) && isscalar(x) && x >= 33);
parser.parse(varargin{:});
opts = parser.Results;
opts.subset_indices = unique(double(opts.subset_indices(:))', 'stable');
opts.profile_name = string(opts.profile_name);
opts.warm_start = logical(opts.warm_start);
opts.include_optional_experiment = logical(opts.include_optional_experiment);
if ischar(opts.experiment_names)
    opts.experiment_names = string({opts.experiment_names});
elseif iscell(opts.experiment_names)
    opts.experiment_names = string(opts.experiment_names);
else
    opts.experiment_names = string(opts.experiment_names);
end
end

function context = vlab_load_context(project_root, opts)
input_folder = fullfile(project_root, 'Crop_circle_FreqFiltered');
gt_path = fullfile(input_folder, 'GT', 'GT_901_with_Block_proc.bmp');
file_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
file_list = file_list(~[file_list.isdir]);

if isempty(file_list)
    error('No input images found under %s.', input_folder);
end

file_numbers = nan(1, numel(file_list));
for fi = 1:numel(file_list)
    tokens = regexp(file_list(fi).name, '_(\d+)\.bmp$', 'tokens', 'once');
    if isempty(tokens)
        error('Failed to parse file index from %s.', file_list(fi).name);
    end
    file_numbers(fi) = str2double(tokens{1});
end

[~, order] = sort(file_numbers);
file_list = file_list(order);

if numel(file_list) ~= 100
    error('Expected 100 Whole-FOV images, found %d.', numel(file_list));
end

gt_cpu = im2double(imread(gt_path));
psf_data = load(fullfile(project_root, 'SimulatePSF', 'psf_multi.mat'), 'psf_multi');
psf_slice_cpu = double(psf_data.psf_multi);

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
else
    psf_slice = psf_slice_cpu;
    gt = gt_cpu;
end

[h_psf, w_psf] = size(psf_slice_cpu);
pupil_res = floor((min(h_psf, w_psf) - 1) / 2);
x_coord = -pupil_res:pupil_res;
y_coord = -pupil_res:pupil_res;
[Xg, Yg] = meshgrid(x_coord, y_coord);
rho_cpu = hypot(Xg, Yg) ./ pupil_res ./ 2;
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
    file_info(fi).row = floor((fi - 1) / 10) + 1;
    file_info(fi).col = mod(fi - 1, 10) + 1;
end

context = struct();
context.project_root = project_root;
context.input_folder = input_folder;
context.gt_path = gt_path;
context.file_info = file_info;
context.gt_cpu = gt_cpu;
context.use_gpu = use_gpu;
context.model = struct( ...
    'psf_slice', psf_slice, ...
    'gt', gt, ...
    'amp', 1.0, ...
    'rho', rho, ...
    'phi', phi, ...
    'psf_f', psf_f, ...
    'freq_mask', freq_mask, ...
    'use_gpu', use_gpu);
context.x0 = x0;
context.lb = lb;
context.ub = ub;
context.psf_size = size(psf_slice_cpu);
context.psf_center = [(context.psf_size(1) + 1) / 2, (context.psf_size(2) + 1) / 2];
context.prealign = struct( ...
    'search_radius', opts.prealign_search_radius, ...
    'search_step', opts.prealign_search_step, ...
    'search_values', -opts.prealign_search_radius:opts.prealign_search_step:opts.prealign_search_radius, ...
    'crop_rows', crop_rows, ...
    'crop_cols', crop_cols, ...
    'gt_grad_norm', gt_grad_norm);
end

function result = vlab_run_experiment(context, config)
global VLAB_CONTEXT VLAB_STATE

vlab_ensure_dir(config.output_dir);

subset_indices = config.subset_indices;
psf_h = context.psf_size(1);
psf_w = context.psf_size(2);
num_images = numel(subset_indices);

psf_grid = zeros(psf_h, psf_w, 1, num_images);
coef_grid = zeros(numel(context.x0), 1, num_images);
fval_map = nan(1, num_images);
iterations_map = nan(1, num_images);
filename_map = strings(1, num_images);
source_file_index_map = nan(1, num_images);
source_row_map = nan(1, num_images);
source_col_map = nan(1, num_images);
loss_histories = cell(1, num_images);

rows = repmat(struct( ...
    'experiment_name', "", ...
    'file_index', 0, ...
    'source_row', 0, ...
    'source_col', 0, ...
    'filename', "", ...
    'warm_start', false, ...
    'pre_alignment', false, ...
    'lock_tilt', false, ...
    'prealign_shift_y', 0, ...
    'prealign_shift_x', 0, ...
    'prealign_score', 0, ...
    'fval', 0, ...
    'iterations', 0, ...
    'seconds', 0, ...
    'peak_y', 0, ...
    'peak_x', 0, ...
    'peak_offset_y', 0, ...
    'peak_offset_x', 0, ...
    'centroid_y', 0, ...
    'centroid_x', 0, ...
    'centroid_offset_y', 0, ...
    'centroid_offset_x', 0, ...
    'peak_edge_distance', 0, ...
    'centroid_edge_distance', 0, ...
    'edge_energy_ratio', 0, ...
    'touches_edge', false), 1, num_images);

if config.warm_start
    x_prev = context.x0;
end

for ki = 1:num_images
    file_index = subset_indices(ki);
    file_entry = context.file_info(file_index);
    fprintf('[%d/%d] %s (fi=%d, R%dC%d)\n', ki, num_images, file_entry.name, file_index, file_entry.row, file_entry.col);

    img_cpu = im2double(imread(file_entry.path));
    if config.pre_alignment
        prealign_cfg = context.prealign;
        prealign_cfg.search_step = config.prealign_step;
        prealign_cfg.search_values = -prealign_cfg.search_radius:config.prealign_step:prealign_cfg.search_radius;
        align_info = vlab_prealign_image(img_cpu, prealign_cfg);
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

    VLAB_CONTEXT = struct('model', context.model, 'img', fit_img, 'lock_tilt', config.lock_tilt);
    VLAB_STATE = struct('iter_count', 0, 'loss_history', zeros(0, 5));

    t_start = tic;
    [x, fval] = bads(@vlab_aberration_loss, x_init, context.lb, context.ub);
    elapsed = toc(t_start);

    if config.warm_start
        x_prev = x;
    end

    fitted_psf = gather(vlab_build_fitted_psf(x, context.model, config.lock_tilt));
    loss_histories{ki} = VLAB_STATE.loss_history;
    metrics = vlab_compute_psf_metrics(fitted_psf, context.psf_center);

    psf_grid(:, :, 1, ki) = fitted_psf;
    coef_grid(:, 1, ki) = x(:);
    fval_map(1, ki) = double(fval);
    iterations_map(1, ki) = VLAB_STATE.iter_count;
    filename_map(1, ki) = string(file_entry.name);
    source_file_index_map(1, ki) = file_index;
    source_row_map(1, ki) = file_entry.row;
    source_col_map(1, ki) = file_entry.col;

    rows(ki).experiment_name = string(config.name);
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

    fprintf('    fval=%.6f, iter=%d, peak=(%.1f, %.1f), centroid=(%.2f, %.2f)\n', ...
        double(fval), VLAB_STATE.iter_count, metrics.peak_y, metrics.peak_x, metrics.centroid_y, metrics.centroid_x);
end

batch_table = struct2table(rows);
batch_results_path = fullfile(config.output_dir, 'batch_results.csv');
writetable(batch_table, batch_results_path);

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
    'lock_tilt', config.lock_tilt);
stack_path = fullfile(config.output_dir, 'PSF_fitted_2D_FOVstack.mat');
save(stack_path, '-struct', 'stack_payload');

metadata = struct();
metadata.experiment_name = config.name;
metadata.subset_indices = subset_indices;
metadata.warm_start = config.warm_start;
metadata.pre_alignment = config.pre_alignment;
metadata.lock_tilt = config.lock_tilt;
metadata.output_dir = config.output_dir;
metadata.project_root = context.project_root;
metadata.gt_path = context.gt_path;
metadata.input_folder = context.input_folder;
metadata.use_gpu = context.use_gpu;
metadata.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
metadata.matlab_release = version('-release');
metadata.bads_path = which('bads');
metadata.batch_results_csv = batch_results_path;
metadata.stack_path = stack_path;
metadata.prealign_search_values = context.prealign.search_values;
metadata.prealign_crop_size = numel(context.prealign.crop_rows);
metadata.prealign_step = config.prealign_step;
metadata.file_names = {context.file_info(subset_indices).name};
metadata.file_rows = [context.file_info(subset_indices).row];
metadata.file_cols = [context.file_info(subset_indices).col];
config_path = fullfile(config.output_dir, 'experiment_config.json');
vlab_write_json(config_path, metadata);

loss_history_path = fullfile(config.output_dir, 'loss_histories.mat');
save(loss_history_path, 'loss_histories');

result = struct();
result.config = config;
result.batch_table = batch_table;
result.batch_results_path = batch_results_path;
result.stack_path = stack_path;
result.config_path = config_path;
result.loss_history_path = loss_history_path;
end

function loss = vlab_aberration_loss(coef)
global VLAB_CONTEXT VLAB_STATE

fitted_psf = vlab_build_fitted_psf(coef, VLAB_CONTEXT.model, VLAB_CONTEXT.lock_tilt);
pred = conv2(VLAB_CONTEXT.model.gt, fitted_psf, 'same');

pred_grad_norm = normlz(imgradient(pred));
img_grad_norm = normlz(imgradient(VLAB_CONTEXT.img));
pred_freq = abs(fftshift(fft2(pred))) .* VLAB_CONTEXT.model.freq_mask;
img_freq = abs(fftshift(fft2(VLAB_CONTEXT.img))) .* VLAB_CONTEXT.model.freq_mask;

freq_loss = vlab_mse(img_freq, pred_freq);
grad_loss = vlab_mse(img_grad_norm, pred_grad_norm);
loss = gather(freq_loss + 8e4 * grad_loss);

VLAB_STATE.iter_count = VLAB_STATE.iter_count + 1;
VLAB_STATE.loss_history(VLAB_STATE.iter_count, :) = double([loss, gather(freq_loss), gather(grad_loss), gather(freq_loss), gather(grad_loss)]);
end

function fitted_psf = vlab_build_fitted_psf(coef, model, lock_tilt)
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
    Z(1) .* 1 + ...
    Z(2) .* 2 .* rho .* sin(phi) + ...
    Z(3) .* 2 .* rho .* cos(phi) + ...
    Z(4) .* sqrt(6) .* rho .^ 2 .* sin(2 .* phi) + ...
    Z(5) .* sqrt(3) .* (2 .* rho .^ 2 - 1) + ...
    Z(6) .* sqrt(6) .* rho .^ 2 .* cos(2 .* phi) + ...
    Z(7) .* sqrt(8) .* rho .^ 3 .* sin(3 .* phi) + ...
    Z(8) .* sqrt(8) .* (3 .* rho .^ 2 - 2 .* rho) .* sin(phi) + ...
    Z(9) .* sqrt(8) .* (3 .* rho .^ 2 - 2 .* rho) .* cos(phi) + ...
    Z(10) .* sqrt(8) .* rho .^ 3 .* cos(3 .* phi) + ...
    Z(11) .* sqrt(10) .* rho .^ 4 .* sin(4 .* phi) + ...
    Z(12) .* sqrt(10) .* (4 .* rho .^ 4 - 3 .* rho .^ 2) .* sin(2 .* phi) + ...
    Z(13) .* sqrt(5) .* (6 .* rho .^ 4 - 6 .* rho .^ 2 + 1) + ...
    Z(14) .* sqrt(10) .* (4 .* rho .^ 4 - 3 .* rho .^ 2) .* cos(2 .* phi) + ...
    Z(15) .* sqrt(10) .* rho .^ 4 .* cos(4 .* phi);

psf_a = psf_f .* (exp(1i .* 2 .* pi() .* W_phase) .^ 2);
fitted_psf = abs(ifft2(psf_a));
fitted_psf = fitted_psf ./ sum(fitted_psf(:));
fitted_psf = model.amp .* AC .* fitted_psf;
end

function align_info = vlab_prealign_image(img_cpu, prealign)
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
        score = vlab_ncc(gt_crop, shifted_crop);
        if score > best_score
            best_score = score;
            best_shift = [dy, dx];
        end
    end
end

align_info = struct();
align_info.shift_y = best_shift(1);
align_info.shift_x = best_shift(2);
align_info.score = best_score;
align_info.aligned_image = vlab_translate_image(img_cpu, best_shift(1), best_shift(2));
end

function shifted = vlab_apply_integer_shift(img, dy, dx)
[h, w] = size(img);
shifted = zeros(size(img), 'like', img);

src_rows = max(1, 1 - dy):min(h, h - dy);
src_cols = max(1, 1 - dx):min(w, w - dx);
dst_rows = src_rows + dy;
dst_cols = src_cols + dx;

if isempty(src_rows) || isempty(src_cols)
    return;
end

shifted(dst_rows, dst_cols) = img(src_rows, src_cols);
end

function metrics = vlab_compute_psf_metrics(psf, center)
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

metrics = struct();
metrics.peak_y = double(peak_y);
metrics.peak_x = double(peak_x);
metrics.peak_offset_y = double(peak_y - center(1));
metrics.peak_offset_x = double(peak_x - center(2));
metrics.centroid_y = double(centroid_y);
metrics.centroid_x = double(centroid_x);
metrics.centroid_offset_y = double(centroid_y - center(1));
metrics.centroid_offset_x = double(centroid_x - center(2));
metrics.peak_edge_distance = double(peak_edge_distance);
metrics.centroid_edge_distance = double(centroid_edge_distance);
metrics.edge_energy_ratio = double(edge_energy_ratio);
metrics.touches_edge = logical(touches_edge);
end

function summary = vlab_analyze_results(lab_root, experiment_results, context)
output_root = fullfile(lab_root, 'outputs');
tables_dir = fullfile(output_root, 'tables');
figures_dir = fullfile(output_root, 'figures');
reports_dir = fullfile(output_root, 'reports');

comparison_rows = repmat(struct( ...
    'experiment_name', "", ...
    'num_images', 0, ...
    'subset_indices', "", ...
    'warm_start', false, ...
    'pre_alignment', false, ...
    'lock_tilt', false, ...
    'mean_fval', 0, ...
    'mean_iterations', 0, ...
    'mean_seconds', 0, ...
    'mean_peak_offset_y', 0, ...
    'mean_peak_offset_x', 0, ...
    'mean_abs_peak_offset', 0, ...
    'mean_centroid_offset_y', 0, ...
    'mean_centroid_offset_x', 0, ...
    'mean_abs_centroid_offset', 0, ...
    'mean_edge_energy_ratio', 0, ...
    'num_touches_edge', 0, ...
    'mean_prealign_shift_y', 0, ...
    'mean_prealign_shift_x', 0, ...
    'offset_score', 0, ...
    'edge_score', 0, ...
    'overall_score', 0), 1, numel(experiment_results));

for ei = 1:numel(experiment_results)
    tbl = experiment_results(ei).batch_table;
    mean_abs_peak_offset = mean(abs(tbl.peak_offset_y) + abs(tbl.peak_offset_x));
    mean_abs_centroid_offset = mean(abs(tbl.centroid_offset_y) + abs(tbl.centroid_offset_x));
    num_touches_edge = sum(tbl.touches_edge);
    mean_edge_energy = mean(tbl.edge_energy_ratio);

    comparison_rows(ei).experiment_name = string(experiment_results(ei).config.name);
    comparison_rows(ei).num_images = height(tbl);
    comparison_rows(ei).subset_indices = join(string(tbl.file_index.'), ',');
    comparison_rows(ei).warm_start = experiment_results(ei).config.warm_start;
    comparison_rows(ei).pre_alignment = experiment_results(ei).config.pre_alignment;
    comparison_rows(ei).lock_tilt = experiment_results(ei).config.lock_tilt;
    comparison_rows(ei).mean_fval = mean(tbl.fval);
    comparison_rows(ei).mean_iterations = mean(tbl.iterations);
    comparison_rows(ei).mean_seconds = mean(tbl.seconds);
    comparison_rows(ei).mean_peak_offset_y = mean(tbl.peak_offset_y);
    comparison_rows(ei).mean_peak_offset_x = mean(tbl.peak_offset_x);
    comparison_rows(ei).mean_abs_peak_offset = mean_abs_peak_offset;
    comparison_rows(ei).mean_centroid_offset_y = mean(tbl.centroid_offset_y);
    comparison_rows(ei).mean_centroid_offset_x = mean(tbl.centroid_offset_x);
    comparison_rows(ei).mean_abs_centroid_offset = mean_abs_centroid_offset;
    comparison_rows(ei).mean_edge_energy_ratio = mean_edge_energy;
    comparison_rows(ei).num_touches_edge = num_touches_edge;
    comparison_rows(ei).mean_prealign_shift_y = mean(tbl.prealign_shift_y, 'omitnan');
    comparison_rows(ei).mean_prealign_shift_x = mean(tbl.prealign_shift_x, 'omitnan');
    comparison_rows(ei).offset_score = mean_abs_peak_offset + 0.5 * mean_abs_centroid_offset;
    comparison_rows(ei).edge_score = num_touches_edge * 100 + mean_edge_energy * 100;
    comparison_rows(ei).overall_score = comparison_rows(ei).offset_score + comparison_rows(ei).edge_score + 0.001 * comparison_rows(ei).mean_iterations;
end

comparison_table = struct2table(comparison_rows);
comparison_csv_path = fullfile(tables_dir, 'experiment_comparison.csv');
writetable(comparison_table, comparison_csv_path);

offset_fig_path = fullfile(figures_dir, 'representative_offset_comparison.png');
vlab_make_offset_figure(experiment_results, offset_fig_path);

fit_fig_path = fullfile(figures_dir, 'fval_iterations_comparison.png');
vlab_make_fit_figure(comparison_table, fit_fig_path);

[~, best_offset_idx] = min(comparison_table.offset_score);
[~, best_edge_idx] = min(comparison_table.edge_score);
[~, best_overall_idx] = min(comparison_table.overall_score);

best_offset = comparison_table(best_offset_idx, :);
best_edge = comparison_table(best_edge_idx, :);
best_overall = comparison_table(best_overall_idx, :);

summary_path = fullfile(reports_dir, 'validation_summary_tw.md');
recommendation_path = fullfile(reports_dir, 'next_recommendation_tw.md');

subset_info = context.file_info(experiment_results(1).config.subset_indices);
subset_text = strjoin(compose('fi=%d(R%dC%d)', [subset_info.index], [subset_info.row], [subset_info.col]), ', ');

summary_lines = {
    '# Whole-FOV PSF 驗證摘要'
    ''
    sprintf('- 執行時間：%s', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')))
    sprintf('- 子集代表點：%s', subset_text)
    ''
    '## 問題 1：raw/GT 預對齊是否能消除共同偏移'
    sprintf('- 以 `offset_score` 判斷，最佳組別是 `%s`。', best_offset.experiment_name(1))
    sprintf('- 這組的 mean abs peak offset = %.3f px，mean abs centroid offset = %.3f px。', best_offset.mean_abs_peak_offset, best_offset.mean_abs_centroid_offset)
    sprintf('- 其平均預對齊位移為 (dy=%.3f, dx=%.3f)。', best_offset.mean_prealign_shift_y, best_offset.mean_prealign_shift_x)
    ''
    '## 問題 2：放開 tilt 是否能改善共同偏移或貼界'
    sprintf('- 以 `edge_score` 判斷，最佳組別是 `%s`。', best_edge.experiment_name(1))
    sprintf('- 這組的 touches_edge=%d，mean edge energy ratio = %.4f。', best_edge.num_touches_edge, best_edge.mean_edge_energy_ratio)
    ''
    '## 最值得往正式可用版收斂的方向'
    sprintf('- 綜合 offset 與貼界分數，推薦 `%s` 作為下一步正式候選。', best_overall.experiment_name(1))
    sprintf('- 它的 mean fval = %.3f，mean iterations = %.1f，overall_score = %.3f。', best_overall.mean_fval, best_overall.mean_iterations, best_overall.overall_score)
    ''
    '## 產出位置'
    sprintf('- 比較表：`%s`', comparison_csv_path)
    sprintf('- 偏移比較圖：`%s`', offset_fig_path)
    sprintf('- fval/iterations 圖：`%s`', fit_fig_path)
};
vlab_write_lines(summary_path, summary_lines);

recommendation_lines = {
    '# 下一步建議'
    ''
    sprintf('- 先以 `%s` 當作正式修正版候選，保留目前的 subset 與 warm-start 設定，避免一次改太多變因。', best_overall.experiment_name(1))
    '- 接下來建議把相同設定擴到 10 到 20 個代表點，確認改善不是只出現在單一角落或單一邊界。'
    '- 若擴大子集後趨勢仍一致，再把這組設定整合回正式 Whole-FOV 流程，最後才做 full 100 張重跑。'
    '- 若 `pre_alignment=true` 是勝出關鍵，正式版應先把 raw 預對齊變成顯式可關閉選項；若 `lock_tilt=false` 才是勝出關鍵，正式版應同步開放 tilt 並補上貼界監控。'
};
vlab_write_lines(recommendation_path, recommendation_lines);

summary = struct();
summary.comparison_csv_path = comparison_csv_path;
summary.offset_figure_path = offset_fig_path;
summary.fit_figure_path = fit_fig_path;
summary.validation_summary_path = summary_path;
summary.next_recommendation_path = recommendation_path;
summary.best_offset_experiment = best_offset.experiment_name(1);
summary.best_edge_experiment = best_edge.experiment_name(1);
summary.best_overall_experiment = best_overall.experiment_name(1);
end

function vlab_make_offset_figure(experiment_results, output_path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 360 * numel(experiment_results), 720]);
tiledlayout(2, numel(experiment_results), 'Padding', 'compact', 'TileSpacing', 'compact');

all_peak_x = [];
all_peak_y = [];
all_centroid_x = [];
all_centroid_y = [];
for ei = 1:numel(experiment_results)
    tbl = experiment_results(ei).batch_table;
    all_peak_x = [all_peak_x; tbl.peak_offset_x]; %#ok<AGROW>
    all_peak_y = [all_peak_y; tbl.peak_offset_y]; %#ok<AGROW>
    all_centroid_x = [all_centroid_x; tbl.centroid_offset_x]; %#ok<AGROW>
    all_centroid_y = [all_centroid_y; tbl.centroid_offset_y]; %#ok<AGROW>
end
axis_limit = max([abs(all_peak_x); abs(all_peak_y); abs(all_centroid_x); abs(all_centroid_y); 1]) + 1;

for ei = 1:numel(experiment_results)
    tbl = experiment_results(ei).batch_table;

    nexttile(ei);
    scatter(tbl.peak_offset_x, tbl.peak_offset_y, 70, 'filled');
    hold on;
    xline(0, '--k');
    yline(0, '--k');
    text(tbl.peak_offset_x + 0.08, tbl.peak_offset_y + 0.08, compose('fi=%d', tbl.file_index), 'FontSize', 9);
    hold off;
    axis equal;
    xlim([-axis_limit, axis_limit]);
    ylim([-axis_limit, axis_limit]);
    grid on;
    xlabel('x offset (px)');
    ylabel('y offset (px)');
    title(sprintf('%s peak', experiment_results(ei).config.name), 'Interpreter', 'none');

    nexttile(numel(experiment_results) + ei);
    scatter(tbl.centroid_offset_x, tbl.centroid_offset_y, 70, 'filled');
    hold on;
    xline(0, '--k');
    yline(0, '--k');
    text(tbl.centroid_offset_x + 0.08, tbl.centroid_offset_y + 0.08, compose('fi=%d', tbl.file_index), 'FontSize', 9);
    hold off;
    axis equal;
    xlim([-axis_limit, axis_limit]);
    ylim([-axis_limit, axis_limit]);
    grid on;
    xlabel('x offset (px)');
    ylabel('y offset (px)');
    title(sprintf('%s centroid', experiment_results(ei).config.name), 'Interpreter', 'none');
end

exportgraphics(fig, output_path, 'Resolution', 200);
close(fig);
end

function vlab_make_fit_figure(comparison_table, output_path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 1000, 420]);
tiledlayout(1, 2, 'Padding', 'compact', 'TileSpacing', 'compact');

experiment_names = string(comparison_table.experiment_name);

nexttile;
bar(comparison_table.mean_fval);
set(gca, 'XTickLabel', experiment_names, 'XTickLabelRotation', 25);
ylabel('mean fval');
title('平均 fval');
grid on;

nexttile;
bar(comparison_table.mean_iterations);
set(gca, 'XTickLabel', experiment_names, 'XTickLabelRotation', 25);
ylabel('mean iterations');
title('平均 iterations');
grid on;

exportgraphics(fig, output_path, 'Resolution', 200);
close(fig);
end

function vlab_write_json(output_path, payload)
json_text = jsonencode(payload, PrettyPrint = true);
fid = fopen(output_path, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', json_text);
end

function vlab_write_lines(output_path, lines)
fid = fopen(output_path, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
for li = 1:numel(lines)
    fprintf(fid, '%s\n', lines{li});
end
end

function vlab_ensure_dir(path_value)
if ~exist(path_value, 'dir')
    mkdir(path_value);
end
end

function value = vlab_mse(a, b)
delta = a - b;
value = mean(delta(:) .^ 2);
end

function score = vlab_ncc(a, b)
a = double(a(:));
b = double(b(:));
a = a - mean(a);
b = b - mean(b);
denom = norm(a) * norm(b) + eps;
score = sum(a .* b) / denom;
end
