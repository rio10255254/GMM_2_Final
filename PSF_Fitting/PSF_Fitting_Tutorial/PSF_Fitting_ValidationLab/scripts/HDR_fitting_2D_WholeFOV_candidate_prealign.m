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
config = struct( ...
    'name', "candidate_flow", ...
    'subset_indices', opts.subset_indices, ...
    'warm_start', opts.warm_start, ...
    'pre_alignment', opts.pre_alignment, ...
    'lock_tilt', opts.lock_tilt, ...
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
parser.addParameter('warm_start', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('pre_alignment', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('lock_tilt', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('output_root', fullfile(fileparts(fileparts(mfilename('fullpath'))), 'outputs', 'candidate_flow'), @(x) ischar(x) || isstring(x));
parser.addParameter('use_gpu', [], @(x) isempty(x) || islogical(x) || isnumeric(x));
parser.addParameter('prealign_search_radius', 2, @(x) isnumeric(x) && isscalar(x) && x >= 0);
parser.addParameter('prealign_step', [], @(x) isempty(x) || (isnumeric(x) && isscalar(x) && x > 0));
parser.addParameter('prealign_search_step', 0.25, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('prealign_crop_size', 257, @(x) isnumeric(x) && isscalar(x) && x >= 33);
parser.parse(varargin{:});
opts = parser.Results;
opts.subset_indices = unique(double(opts.subset_indices(:))', 'stable');
opts.warm_start = logical(opts.warm_start);
opts.pre_alignment = logical(opts.pre_alignment);
opts.lock_tilt = logical(opts.lock_tilt);
if ~isempty(opts.prealign_step)
    opts.prealign_search_step = opts.prealign_step;
end
end

function context = candidate_load_context(project_root, opts)
input_folder = fullfile(project_root, 'Crop_circle_FreqFiltered');
gt_path = fullfile(input_folder, 'GT', 'GT_901_with_Block_proc.bmp');
file_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
file_list = file_list(~[file_list.isdir]);

file_numbers = nan(1, numel(file_list));
for fi = 1:numel(file_list)
    tokens = regexp(file_list(fi).name, '_(\d+)\.bmp$', 'tokens', 'once');
    file_numbers(fi) = str2double(tokens{1});
end
[~, order] = sort(file_numbers);
file_list = file_list(order);

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
[Xg, Yg] = meshgrid(-pupil_res:pupil_res, -pupil_res:pupil_res);
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

    VLAB_CONTEXT = struct('model', context.model, 'img', fit_img, 'lock_tilt', config.lock_tilt);
    VLAB_STATE = struct('iter_count', 0, 'loss_history', zeros(0, 5));

    t_start = tic;
    [x, fval] = bads(@candidate_aberration_loss, x_init, context.lb, context.ub);
    elapsed = toc(t_start);

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
    'prealign_search_radius', config.prealign_search_radius, ...
    'prealign_search_step', config.prealign_search_step, ...
    'project_root', context.project_root, ...
    'output_dir', config.output_dir, ...
    'generated_at', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
config_path = fullfile(config.output_dir, 'candidate_config.json');
candidate_write_json(config_path, metadata);
end

function loss = candidate_aberration_loss(coef)
global VLAB_CONTEXT VLAB_STATE
fitted_psf = candidate_build_fitted_psf(coef, VLAB_CONTEXT.model, VLAB_CONTEXT.lock_tilt);
pred = conv2(VLAB_CONTEXT.model.gt, fitted_psf, 'same');
pred_grad_norm = normlz(imgradient(pred));
img_grad_norm = normlz(imgradient(VLAB_CONTEXT.img));
pred_freq = abs(fftshift(fft2(pred))) .* VLAB_CONTEXT.model.freq_mask;
img_freq = abs(fftshift(fft2(VLAB_CONTEXT.img))) .* VLAB_CONTEXT.model.freq_mask;
freq_loss = mean((img_freq(:) - pred_freq(:)) .^ 2);
grad_loss = mean((img_grad_norm(:) - pred_grad_norm(:)) .^ 2);
loss = gather(freq_loss + 8e4 * grad_loss);
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
