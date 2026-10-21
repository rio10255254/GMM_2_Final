function run_sem_acm_multimethod(experiment_root)
% Compare Raw and all R82 reconstructions against the verified 36 SEM pillars.

if nargin < 1 || strlength(string(experiment_root)) == 0
    experiment_root = fileparts(fileparts(mfilename('fullpath')));
end
experiment_root = char(experiment_root);
cfg = jsondecode(fileread(fullfile(experiment_root, 'config', 'experiment.json')));
raw_dir = char(cfg.sem_acm.raw_input_dir);
sem_dir = char(cfg.sem_acm.sem_dir);
table_dir = fullfile(experiment_root, 'results', 'acm_sem', 'tables');
mask_dir = fullfile(experiment_root, 'results', 'acm_sem', 'masks');
if ~exist(table_dir, 'dir'), mkdir(table_dir); end
if ~exist(mask_dir, 'dir'), mkdir(mask_dir); end

model_names = fieldnames(cfg.models).';
method_names = [{'Raw'}, model_names];
method_count = numel(method_names);
exposures = double(cfg.sem_acm.optical_exposures(:)).';
primary_iterations = 200;
primary_smooth = 1.0;
cell_half = 52;
cell_side = 2 * cell_half;
seed_radius = 40;
support_radius = 45;
sem_resize_factor = 1 / 3.23;

global_index = [
     6  5  4  3  2  1;
    12 11 10  9  8  7;
    18 17 16 15 14 13;
    24 23 22 21 20 19;
    30 29 28 27 26 25;
    36 35 34 33 32 31];
p_to_block = [3 1; 3 2; 3 3; 2 3; 2 2; 2 1; 1 1; 1 2; 1 3];
corner_names = {'top_left', 'top_right', 'bottom_left', 'bottom_right'};

reference_raw = imread(fullfile(raw_dir, '13.bmp'));
if ndims(reference_raw) == 3, reference_raw = rgb2gray(reference_raw); end
[opt_centers, ~, ~] = imfindcircles(reference_raw, [28 45], ...
    'ObjectPolarity', 'dark', 'Sensitivity', 0.92, 'EdgeThreshold', 0.05);
if size(opt_centers, 1) ~= 36
    error('Expected 36 optical circles in exposure 13, found %d.', size(opt_centers, 1));
end
opt_centers = sort_grid_centers(opt_centers, 6, 6);
opt_pitch = estimate_grid_pitch(opt_centers, 6, 6);

truth_cells = zeros(cell_side, cell_side, 36, 'uint8');
truth_masks = false(cell_side, cell_side, 36);
sem_file_by_id = strings(36, 1);
sem_corner_by_id = strings(36, 1);
sem_edge_cleanup_ids = [];
for p_index = 1:9
    sem_file = sprintf('P-%02d.tiff', p_index);
    sem_image = imread(fullfile(sem_dir, sem_file));
    if ndims(sem_image) == 3, sem_image = sem_image(:, :, 1); end
    sem_aligned = imresize(sem_image(7:754, 142:914), sem_resize_factor, 'bicubic');
    [centers, ~, ~] = imfindcircles(sem_aligned, [28 45], ...
        'ObjectPolarity', 'bright', 'Sensitivity', 0.90, 'EdgeThreshold', 0.05);
    if size(centers, 1) ~= 4, error('%s: expected 4 SEM circles.', sem_file); end
    centers = sort_grid_centers(centers, 2, 2);
    block_row = p_to_block(p_index, 1); block_col = p_to_block(p_index, 2);
    ids = reshape(global_index(2*block_row-1:2*block_row, 2*block_col-1:2*block_col).', 1, []);
    for local_index = 1:4
        pillar_id = ids(local_index);
        cell_image = extract_padded_cell(sem_aligned, centers(local_index, :), cell_half);
        mask = segment_acm(cell_image, seed_radius, primary_iterations, primary_smooth, support_radius);
        [mask, edge_was_cleaned] = remove_sem_edge_artifacts(mask);
        if edge_was_cleaned, sem_edge_cleanup_ids(end+1) = pillar_id; end %#ok<AGROW>
        truth_cells(:, :, pillar_id) = im2uint8(mat2gray(cell_image));
        truth_masks(:, :, pillar_id) = mask;
        sem_file_by_id(pillar_id) = string(sem_file);
        sem_corner_by_id(pillar_id) = string(corner_names{local_index});
    end
end

method_cells = struct(); method_masks = struct();
for method_index = 1:method_count
    method_name = method_names{method_index};
    method_cells.(method_name) = zeros(cell_side, cell_side, 36, numel(exposures), 'uint8');
    method_masks.(method_name) = false(cell_side, cell_side, 36, numel(exposures));
end

record_count = numel(exposures) * 36 * method_count;
exposure_col = zeros(record_count, 1); pillar_col = zeros(record_count, 1);
row_col = zeros(record_count, 1); grid_col = zeros(record_count, 1);
method_col = strings(record_count, 1); iou_col = zeros(record_count, 1);
dice_col = zeros(record_count, 1); mean_distance_px_col = zeros(record_count, 1);
mean_distance_pitch_pct_col = zeros(record_count, 1); hd95_px_col = zeros(record_count, 1);
hd95_pitch_pct_col = zeros(record_count, 1); area_error_pct_col = zeros(record_count, 1);
perimeter_error_pct_col = zeros(record_count, 1); truth_circularity_col = zeros(record_count, 1);
pred_circularity_col = zeros(record_count, 1); circularity_abs_error_col = zeros(record_count, 1);
centroid_shift_px_col = zeros(record_count, 1); record_index = 0;

for exposure_index = 1:numel(exposures)
    exposure = exposures(exposure_index);
    images = cell(method_count, 1);
    images{1} = imread(fullfile(raw_dir, sprintf('%d.bmp', exposure)));
    for model_index = 1:numel(model_names)
        model_name = model_names{model_index};
        images{model_index + 1} = imread(fullfile(experiment_root, 'results', ...
            'reconstructions', 'sem_acm', model_name, sprintf('%d.bmp', exposure)));
    end
    for method_index = 1:method_count
        if ndims(images{method_index}) == 3, images{method_index} = rgb2gray(images{method_index}); end
    end

    for grid_row_index = 1:6
        for grid_col_index = 1:6
            linear_position = (grid_row_index - 1) * 6 + grid_col_index;
            pillar_id = global_index(grid_row_index, grid_col_index);
            center = opt_centers(linear_position, :);
            for method_index = 1:method_count
                method_name = method_names{method_index};
                cell_image = extract_padded_cell(images{method_index}, center, cell_half);
                mask = segment_acm(cell_image, seed_radius, primary_iterations, primary_smooth, support_radius);
                method_cells.(method_name)(:, :, pillar_id, exposure_index) = im2uint8(mat2gray(cell_image));
                method_masks.(method_name)(:, :, pillar_id, exposure_index) = mask;
                [aligned_mask, shift_magnitude] = align_mask_translation(mask, truth_masks(:, :, pillar_id));
                metrics = contour_metrics(truth_masks(:, :, pillar_id), aligned_mask, opt_pitch);
                record_index = record_index + 1;
                exposure_col(record_index) = exposure; pillar_col(record_index) = pillar_id;
                row_col(record_index) = grid_row_index; grid_col(record_index) = grid_col_index;
                method_col(record_index) = string(method_name); iou_col(record_index) = metrics.iou;
                dice_col(record_index) = metrics.dice; mean_distance_px_col(record_index) = metrics.mean_distance_px;
                mean_distance_pitch_pct_col(record_index) = metrics.mean_distance_pitch_pct;
                hd95_px_col(record_index) = metrics.hd95_px; hd95_pitch_pct_col(record_index) = metrics.hd95_pitch_pct;
                area_error_pct_col(record_index) = metrics.area_error_pct;
                perimeter_error_pct_col(record_index) = metrics.perimeter_error_pct;
                truth_circularity_col(record_index) = metrics.truth_circularity;
                pred_circularity_col(record_index) = metrics.pred_circularity;
                circularity_abs_error_col(record_index) = metrics.circularity_abs_error;
                centroid_shift_px_col(record_index) = shift_magnitude;
            end
        end
    end
    fprintf('SEM primary exposure %d complete (%d/%d).\n', exposure, exposure_index, numel(exposures));
end

primary_metrics = table(exposure_col, pillar_col, row_col, grid_col, method_col, ...
    iou_col, dice_col, mean_distance_px_col, mean_distance_pitch_pct_col, ...
    hd95_px_col, hd95_pitch_pct_col, area_error_pct_col, perimeter_error_pct_col, ...
    truth_circularity_col, pred_circularity_col, circularity_abs_error_col, ...
    centroid_shift_px_col, 'VariableNames', {'exposure', 'pillar_id', 'grid_row', ...
    'grid_col', 'method', 'iou', 'dice', 'mean_boundary_distance_px', ...
    'mean_boundary_distance_pitch_pct', 'hd95_px', 'hd95_pitch_pct', ...
    'area_error_pct', 'perimeter_error_pct', 'truth_circularity', ...
    'pred_circularity', 'circularity_abs_error', 'centroid_alignment_shift_px'});
writetable(primary_metrics, fullfile(table_dir, 'primary_contour_metrics.csv'));

mapping_table = table((1:36).', zeros(36, 1), zeros(36, 1), sem_file_by_id, ...
    sem_corner_by_id, 'VariableNames', {'pillar_id', 'grid_row', 'grid_col', 'sem_file', 'sem_corner'});
for r = 1:6
    for c = 1:6
        pillar_id = global_index(r, c); mapping_table.grid_row(pillar_id) = r; mapping_table.grid_col(pillar_id) = c;
    end
end
writetable(mapping_table, fullfile(table_dir, 'pillar_mapping.csv'));

sensitivity_exposures = [13 18 24];
preset_names = {'less_smooth', 'primary', 'more_smooth'};
preset_iterations = [150 200 250]; preset_smooth = [0.5 1.0 2.0];
sensitivity_rows = table();
for preset_index = 1:numel(preset_names)
    truth_variant = false(size(truth_masks));
    for pillar_id = 1:36
        truth_variant(:, :, pillar_id) = segment_acm(truth_cells(:, :, pillar_id), ...
            seed_radius, preset_iterations(preset_index), preset_smooth(preset_index), support_radius);
        truth_variant(:, :, pillar_id) = remove_sem_edge_artifacts(truth_variant(:, :, pillar_id));
    end
    for exposure = sensitivity_exposures
        exposure_index = find(exposures == exposure, 1);
        for pillar_id = 1:36
            for method_index = 1:method_count
                method_name = method_names{method_index};
                cell_image = method_cells.(method_name)(:, :, pillar_id, exposure_index);
                mask = segment_acm(cell_image, seed_radius, preset_iterations(preset_index), ...
                    preset_smooth(preset_index), support_radius);
                [aligned_mask, shift_magnitude] = align_mask_translation(mask, truth_variant(:, :, pillar_id));
                metrics = contour_metrics(truth_variant(:, :, pillar_id), aligned_mask, opt_pitch);
                new_row = table(string(preset_names{preset_index}), exposure, pillar_id, ...
                    string(method_name), metrics.iou, metrics.mean_distance_pitch_pct, ...
                    metrics.hd95_pitch_pct, metrics.area_error_pct, ...
                    metrics.circularity_abs_error, shift_magnitude, 'VariableNames', ...
                    {'preset', 'exposure', 'pillar_id', 'method', 'iou', ...
                    'mean_boundary_distance_pitch_pct', 'hd95_pitch_pct', ...
                    'area_error_pct', 'circularity_abs_error', 'centroid_alignment_shift_px'});
                if isempty(sensitivity_rows), sensitivity_rows = new_row;
                else, sensitivity_rows = [sensitivity_rows; new_row]; %#ok<AGROW>
                end
            end
        end
    end
    fprintf('SEM sensitivity preset %s complete.\n', preset_names{preset_index});
end
writetable(sensitivity_rows, fullfile(table_dir, 'acm_sensitivity_metrics.csv'));

save(fullfile(mask_dir, 'acm_primary_masks.mat'), 'truth_cells', 'truth_masks', ...
    'method_cells', 'method_masks', 'global_index', 'exposures', 'opt_centers', ...
    'opt_pitch', 'sem_file_by_id', 'sem_corner_by_id', 'primary_iterations', ...
    'primary_smooth', 'cell_half', 'seed_radius', 'support_radius', ...
    'sem_edge_cleanup_ids', '-v7.3');

summary = struct(); summary.status = 'complete'; summary.exposure_count = numel(exposures);
summary.pillar_count = 36; summary.methods = method_names;
summary.primary_record_count = height(primary_metrics);
summary.sensitivity_record_count = height(sensitivity_rows);
summary.optical_pitch_px = opt_pitch; summary.acm_method = 'Chan-Vese';
summary.primary_iterations = primary_iterations; summary.primary_smooth_factor = primary_smooth;
summary.seed_radius_px = seed_radius; summary.support_radius_px = support_radius;
summary.sem_edge_cleanup_pillar_ids = unique(sem_edge_cleanup_ids);
fid = fopen(fullfile(table_dir, 'acm_extraction_summary.json'), 'w', 'n', 'UTF-8');
if fid < 0, error('Could not write SEM ACM summary.'); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(summary, PrettyPrint=true), 'char');
fprintf('SEM ACM complete: %d primary rows, %d sensitivity rows.\n', ...
    height(primary_metrics), height(sensitivity_rows));
end


function centers = sort_grid_centers(centers, rows, cols)
[~, y_order] = sort(centers(:, 2)); centers = centers(y_order, :); sorted = zeros(size(centers));
for r = 1:rows
    block = centers((r-1)*cols+1:r*cols, :); [~, x_order] = sort(block(:, 1));
    sorted((r-1)*cols+1:r*cols, :) = block(x_order, :);
end
centers = sorted;
end


function pitch = estimate_grid_pitch(centers, rows, cols)
x_grid = reshape(centers(:, 1), cols, rows).'; y_grid = reshape(centers(:, 2), cols, rows).';
dx = diff(x_grid, 1, 2); dy = diff(y_grid, 1, 1); pitch = median([dx(:); dy(:)]);
end


function cell_image = extract_padded_cell(image, center, half_size)
if ~isfloat(image), image = im2double(image); end
padded = padarray(image, [half_size half_size], 'symmetric', 'both');
cx = round(center(1)) + half_size; cy = round(center(2)) + half_size;
cell_image = padded(cy-half_size:cy+half_size-1, cx-half_size:cx+half_size-1);
end


function mask = segment_acm(cell_image, seed_radius, iterations, smooth_factor, support_radius)
image = mat2gray(cell_image); limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1), image = imadjust(image, limits, [0 1]); end
[height, width] = size(image); [x, y] = meshgrid(1:width, 1:height);
cx = (width + 1) / 2; cy = (height + 1) / 2;
initial_mask = (x-cx).^2 + (y-cy).^2 <= seed_radius^2;
mask = activecontour(image, initial_mask, iterations, 'Chan-Vese', ...
    'SmoothFactor', smooth_factor, 'ContractionBias', 0);
support_mask = (x-cx).^2 + (y-cy).^2 <= support_radius^2;
mask = select_center_component(mask & support_mask); mask = imfill(mask, 'holes'); mask = bwareaopen(mask, 64);
area_fraction = nnz(mask) / numel(mask);
if area_fraction < 0.15 || area_fraction > 0.60, error('Implausible ACM area fraction %.4f.', area_fraction); end
end


function [cleaned, was_cleaned] = remove_sem_edge_artifacts(mask)
trigger_width = 12; trim_width = 15; cleaned = mask; was_cleaned = false;
if any(cleaned(1:trigger_width, :), 'all'), cleaned(1:trim_width, :) = false; was_cleaned = true; end
if any(cleaned(end-trigger_width+1:end, :), 'all'), cleaned(end-trim_width+1:end, :) = false; was_cleaned = true; end
if any(cleaned(:, 1:trigger_width), 'all'), cleaned(:, 1:trim_width) = false; was_cleaned = true; end
if any(cleaned(:, end-trigger_width+1:end), 'all'), cleaned(:, end-trim_width+1:end) = false; was_cleaned = true; end
if was_cleaned, cleaned = imfill(select_center_component(cleaned), 'holes'); end
end


function selected = select_center_component(mask)
components = bwconncomp(mask, 8); if components.NumObjects == 0, error('ACM returned empty mask.'); end
[height, width] = size(mask); center = [(width + 1) / 2, (height + 1) / 2];
best_component = 0; best_score = inf;
for index = 1:components.NumObjects
    [rows, cols] = ind2sub(size(mask), components.PixelIdxList{index});
    score = norm([mean(cols), mean(rows)] - center) - 0.001 * numel(rows);
    if score < best_score, best_score = score; best_component = index; end
end
selected = false(size(mask)); selected(components.PixelIdxList{best_component}) = true;
end


function [aligned, shift_magnitude] = align_mask_translation(predicted, truth)
truth_props = regionprops(truth, 'Centroid'); pred_props = regionprops(predicted, 'Centroid');
if isempty(truth_props) || isempty(pred_props), error('Cannot align empty mask.'); end
shift_float = truth_props(1).Centroid - pred_props(1).Centroid;
shift = round(shift_float); shift_magnitude = norm(shift_float);
aligned = shift_binary(predicted, shift(1), shift(2));
end


function shifted = shift_binary(mask, dx, dy)
[height, width] = size(mask); shifted = false(size(mask));
src_x1 = max(1, 1-dx); src_x2 = min(width, width-dx);
src_y1 = max(1, 1-dy); src_y2 = min(height, height-dy);
dst_x1 = src_x1 + dx; dst_x2 = src_x2 + dx;
dst_y1 = src_y1 + dy; dst_y2 = src_y2 + dy;
if src_x1 <= src_x2 && src_y1 <= src_y2
    shifted(dst_y1:dst_y2, dst_x1:dst_x2) = mask(src_y1:src_y2, src_x1:src_x2);
end
end


function metrics = contour_metrics(truth, predicted, pitch_px)
intersection = nnz(truth & predicted); union = nnz(truth | predicted);
metrics.iou = intersection / union; metrics.dice = 2 * intersection / (nnz(truth) + nnz(predicted));
truth_edge = bwperim(truth, 8); pred_edge = bwperim(predicted, 8);
distance_to_truth = bwdist(truth_edge); distance_to_pred = bwdist(pred_edge);
boundary_distances = [distance_to_truth(pred_edge); distance_to_pred(truth_edge)];
metrics.mean_distance_px = mean(boundary_distances);
metrics.mean_distance_pitch_pct = 100 * metrics.mean_distance_px / pitch_px;
metrics.hd95_px = prctile(boundary_distances, 95);
metrics.hd95_pitch_pct = 100 * metrics.hd95_px / pitch_px;
truth_props = regionprops(truth, 'Area', 'Perimeter', 'Circularity');
pred_props = regionprops(predicted, 'Area', 'Perimeter', 'Circularity');
metrics.area_error_pct = 100 * abs(pred_props(1).Area - truth_props(1).Area) / truth_props(1).Area;
metrics.perimeter_error_pct = 100 * abs(pred_props(1).Perimeter - truth_props(1).Perimeter) / truth_props(1).Perimeter;
metrics.truth_circularity = truth_props(1).Circularity;
metrics.pred_circularity = pred_props(1).Circularity;
metrics.circularity_abs_error = abs(metrics.pred_circularity - metrics.truth_circularity);
end
