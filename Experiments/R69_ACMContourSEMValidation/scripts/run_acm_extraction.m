function run_acm_extraction(experiment_root, raw_dir, recon_dir, model_name)
% Extract non-circular SEM, raw, and reconstruction pillar contours with ACM.

script_dir = fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(experiment_root)
    experiment_root = fileparts(script_dir);
end
if nargin < 2 || isempty(raw_dir)
    raw_dir = fullfile(fileparts(script_dir), 'inputs', 'sem_paired_50x_exposure_stack');
end
if nargin < 3 || isempty(recon_dir)
    recon_dir = fullfile(fileparts(script_dir), 'results', 'inference_runs', ...
        'reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020', ...
        'r61v16_psfoff_sem_paired_50x');
end
if nargin < 4 || isempty(model_name)
    model_name = 'R61v16';
end
sem_dir = 'H:\From_2TB_D_disk\13_thesis\SEM_data';
table_dir = fullfile(experiment_root, 'results', 'tables');
mask_dir = fullfile(experiment_root, 'results', 'masks');
if ~exist(table_dir, 'dir'), mkdir(table_dir); end
if ~exist(mask_dir, 'dir'), mkdir(mask_dir); end

exposures = 13:24;
primary_iterations = 200;
primary_smooth = 1.0;
cell_half = 52;
cell_side = 2 * cell_half;
% Start just outside the bright SEM rim. A larger seed can include the
% partial neighbouring acquisition visible at a few SEM cell edges.
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

% P-01 through P-09 block locations in the verified 3x3 SEM layout.
p_to_block = [
    3 1;
    3 2;
    3 3;
    2 3;
    2 2;
    2 1;
    1 1;
    1 2;
    1 3];
corner_names = {'top_left', 'top_right', 'bottom_left', 'bottom_right'};

reference_raw = imread(fullfile(raw_dir, '13.bmp'));
if ndims(reference_raw) == 3, reference_raw = rgb2gray(reference_raw); end
[opt_centers, opt_radii, opt_metric] = imfindcircles(reference_raw, [28 45], ...
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

    % This is the exact crop and scale used by the legacy SEM/optical alignment.
    sem_aligned = imresize(sem_image(7:754, 142:914), sem_resize_factor, 'bicubic');
    [centers, radii, metric] = imfindcircles(sem_aligned, [28 45], ...
        'ObjectPolarity', 'bright', 'Sensitivity', 0.90, 'EdgeThreshold', 0.05);
    if size(centers, 1) ~= 4
        error('%s: expected 4 SEM circles, found %d.', sem_file, size(centers, 1));
    end
    centers = sort_grid_centers(centers, 2, 2);

    block_row = p_to_block(p_index, 1);
    block_col = p_to_block(p_index, 2);
    ids = reshape(global_index(2*block_row-1:2*block_row, ...
        2*block_col-1:2*block_col).', 1, []); % TL, TR, BL, BR

    for local_index = 1:4
        pillar_id = ids(local_index);
        cell_image = extract_padded_cell(sem_aligned, centers(local_index, :), cell_half);
        mask = segment_acm(cell_image, seed_radius, primary_iterations, ...
            primary_smooth, support_radius);
        [mask, edge_was_cleaned] = remove_sem_edge_artifacts(mask);
        if edge_was_cleaned, sem_edge_cleanup_ids(end+1) = pillar_id; end %#ok<AGROW>
        truth_cells(:, :, pillar_id) = im2uint8(mat2gray(cell_image));
        truth_masks(:, :, pillar_id) = mask;
        sem_file_by_id(pillar_id) = string(sem_file);
        sem_corner_by_id(pillar_id) = string(corner_names{local_index});
    end
end

raw_cells = zeros(cell_side, cell_side, 36, numel(exposures), 'uint8');
recon_cells = zeros(cell_side, cell_side, 36, numel(exposures), 'uint8');
raw_masks = false(cell_side, cell_side, 36, numel(exposures));
recon_masks = false(cell_side, cell_side, 36, numel(exposures));

record_count = numel(exposures) * 36 * 2;
exposure_col = zeros(record_count, 1);
pillar_col = zeros(record_count, 1);
row_col = zeros(record_count, 1);
grid_col = zeros(record_count, 1);
method_col = strings(record_count, 1);
iou_col = zeros(record_count, 1);
dice_col = zeros(record_count, 1);
mean_distance_px_col = zeros(record_count, 1);
mean_distance_pitch_pct_col = zeros(record_count, 1);
hd95_px_col = zeros(record_count, 1);
hd95_pitch_pct_col = zeros(record_count, 1);
area_error_pct_col = zeros(record_count, 1);
perimeter_error_pct_col = zeros(record_count, 1);
truth_circularity_col = zeros(record_count, 1);
pred_circularity_col = zeros(record_count, 1);
circularity_abs_error_col = zeros(record_count, 1);
centroid_shift_px_col = zeros(record_count, 1);
record_index = 0;

for exposure_index = 1:numel(exposures)
    exposure = exposures(exposure_index);
    raw_image = imread(fullfile(raw_dir, sprintf('%d.bmp', exposure)));
    recon_image = imread(fullfile(recon_dir, sprintf('%d.bmp', exposure)));
    if ndims(raw_image) == 3, raw_image = rgb2gray(raw_image); end
    if ndims(recon_image) == 3, recon_image = rgb2gray(recon_image); end

    for grid_row_index = 1:6
        for grid_col_index = 1:6
            linear_position = (grid_row_index - 1) * 6 + grid_col_index;
            pillar_id = global_index(grid_row_index, grid_col_index);
            center = opt_centers(linear_position, :);
            raw_cell = extract_padded_cell(raw_image, center, cell_half);
            recon_cell = extract_padded_cell(recon_image, center, cell_half);
            raw_mask = segment_acm(raw_cell, seed_radius, primary_iterations, ...
                primary_smooth, support_radius);
            recon_mask = segment_acm(recon_cell, seed_radius, primary_iterations, ...
                primary_smooth, support_radius);

            raw_cells(:, :, pillar_id, exposure_index) = im2uint8(mat2gray(raw_cell));
            recon_cells(:, :, pillar_id, exposure_index) = im2uint8(mat2gray(recon_cell));
            raw_masks(:, :, pillar_id, exposure_index) = raw_mask;
            recon_masks(:, :, pillar_id, exposure_index) = recon_mask;

            method_masks = {raw_mask, recon_mask};
            method_names = {'Raw', char(model_name)};
            for method_index = 1:2
                record_index = record_index + 1;
                [aligned_mask, shift_magnitude] = align_mask_translation( ...
                    method_masks{method_index}, truth_masks(:, :, pillar_id));
                metrics = contour_metrics(truth_masks(:, :, pillar_id), aligned_mask, opt_pitch);

                exposure_col(record_index) = exposure;
                pillar_col(record_index) = pillar_id;
                row_col(record_index) = grid_row_index;
                grid_col(record_index) = grid_col_index;
                method_col(record_index) = string(method_names{method_index});
                iou_col(record_index) = metrics.iou;
                dice_col(record_index) = metrics.dice;
                mean_distance_px_col(record_index) = metrics.mean_distance_px;
                mean_distance_pitch_pct_col(record_index) = metrics.mean_distance_pitch_pct;
                hd95_px_col(record_index) = metrics.hd95_px;
                hd95_pitch_pct_col(record_index) = metrics.hd95_pitch_pct;
                area_error_pct_col(record_index) = metrics.area_error_pct;
                perimeter_error_pct_col(record_index) = metrics.perimeter_error_pct;
                truth_circularity_col(record_index) = metrics.truth_circularity;
                pred_circularity_col(record_index) = metrics.pred_circularity;
                circularity_abs_error_col(record_index) = metrics.circularity_abs_error;
                centroid_shift_px_col(record_index) = shift_magnitude;
            end
        end
    end
end

primary_metrics = table(exposure_col, pillar_col, row_col, grid_col, method_col, ...
    iou_col, dice_col, mean_distance_px_col, mean_distance_pitch_pct_col, ...
    hd95_px_col, hd95_pitch_pct_col, area_error_pct_col, perimeter_error_pct_col, ...
    truth_circularity_col, pred_circularity_col, circularity_abs_error_col, ...
    centroid_shift_px_col, ...
    'VariableNames', {'exposure', 'pillar_id', 'grid_row', 'grid_col', 'method', ...
    'iou', 'dice', 'mean_boundary_distance_px', 'mean_boundary_distance_pitch_pct', ...
    'hd95_px', 'hd95_pitch_pct', 'area_error_pct', 'perimeter_error_pct', ...
    'truth_circularity', 'pred_circularity', 'circularity_abs_error', ...
    'centroid_alignment_shift_px'});
writetable(primary_metrics, fullfile(table_dir, 'primary_contour_metrics.csv'));

mapping_table = table((1:36).', zeros(36, 1), zeros(36, 1), ...
    sem_file_by_id, sem_corner_by_id, ...
    'VariableNames', {'pillar_id', 'grid_row', 'grid_col', 'sem_file', 'sem_corner'});
for r = 1:6
    for c = 1:6
        pillar_id = global_index(r, c);
        mapping_table.grid_row(pillar_id) = r;
        mapping_table.grid_col(pillar_id) = c;
    end
end
writetable(mapping_table, fullfile(table_dir, 'pillar_mapping.csv'));

% Sensitivity audit: bright, mid, and darkest exposures; three fixed ACM presets.
sensitivity_exposures = [13 18 24];
preset_names = {'less_smooth', 'primary', 'more_smooth'};
preset_iterations = [150 200 250];
preset_smooth = [0.5 1.0 2.0];
sensitivity_rows = table();
for preset_index = 1:numel(preset_names)
    truth_variant = false(size(truth_masks));
    for pillar_id = 1:36
        truth_variant(:, :, pillar_id) = segment_acm( ...
            truth_cells(:, :, pillar_id), seed_radius, ...
            preset_iterations(preset_index), preset_smooth(preset_index), support_radius);
        truth_variant(:, :, pillar_id) = remove_sem_edge_artifacts( ...
            truth_variant(:, :, pillar_id));
    end

    for exposure = sensitivity_exposures
        exposure_index = find(exposures == exposure, 1);
        for pillar_id = 1:36
            for method_index = 1:2
                if method_index == 1
                    cell_image = raw_cells(:, :, pillar_id, exposure_index);
                    method_name = "Raw";
                else
                    cell_image = recon_cells(:, :, pillar_id, exposure_index);
                    method_name = string(model_name);
                end
                mask = segment_acm(cell_image, seed_radius, ...
                    preset_iterations(preset_index), preset_smooth(preset_index), ...
                    support_radius);
                [aligned_mask, shift_magnitude] = align_mask_translation( ...
                    mask, truth_variant(:, :, pillar_id));
                metrics = contour_metrics(truth_variant(:, :, pillar_id), aligned_mask, opt_pitch);
                new_row = table(string(preset_names{preset_index}), exposure, pillar_id, ...
                    method_name, metrics.iou, metrics.mean_distance_pitch_pct, ...
                    metrics.hd95_pitch_pct, metrics.area_error_pct, ...
                    metrics.circularity_abs_error, shift_magnitude, ...
                    'VariableNames', {'preset', 'exposure', 'pillar_id', 'method', ...
                    'iou', 'mean_boundary_distance_pitch_pct', 'hd95_pitch_pct', ...
                    'area_error_pct', 'circularity_abs_error', ...
                    'centroid_alignment_shift_px'});
                if isempty(sensitivity_rows)
                    sensitivity_rows = new_row;
                else
                    sensitivity_rows = [sensitivity_rows; new_row]; %#ok<AGROW>
                end
            end
        end
    end
end
writetable(sensitivity_rows, fullfile(table_dir, 'acm_sensitivity_metrics.csv'));

save(fullfile(mask_dir, 'acm_primary_masks.mat'), ...
    'truth_cells', 'truth_masks', 'raw_cells', 'raw_masks', ...
    'recon_cells', 'recon_masks', 'global_index', 'exposures', ...
    'opt_centers', 'opt_pitch', 'sem_file_by_id', 'sem_corner_by_id', ...
    'primary_iterations', 'primary_smooth', 'cell_half', 'seed_radius', ...
    'support_radius', 'sem_edge_cleanup_ids', ...
    '-v7');

summary = struct();
summary.status = 'complete';
summary.exposure_count = numel(exposures);
summary.pillar_count = 36;
summary.primary_record_count = height(primary_metrics);
summary.sensitivity_record_count = height(sensitivity_rows);
summary.optical_pitch_px = opt_pitch;
summary.acm_method = 'Chan-Vese';
summary.primary_iterations = primary_iterations;
summary.primary_smooth_factor = primary_smooth;
summary.seed_radius_px = seed_radius;
summary.support_radius_px = support_radius;
summary.sem_edge_cleanup_pillar_ids = unique(sem_edge_cleanup_ids);
fid = fopen(fullfile(table_dir, 'acm_extraction_summary.json'), 'w');
fprintf(fid, '%s', jsonencode(summary, PrettyPrint=true));
fclose(fid);

fprintf('%s ACM extraction complete: %d primary rows, %d sensitivity rows.\n', ...
    char(model_name), height(primary_metrics), height(sensitivity_rows));
end


function centers = sort_grid_centers(centers, rows, cols)
[~, y_order] = sort(centers(:, 2));
centers = centers(y_order, :);
sorted = zeros(size(centers));
for r = 1:rows
    block = centers((r-1)*cols+1:r*cols, :);
    [~, x_order] = sort(block(:, 1));
    sorted((r-1)*cols+1:r*cols, :) = block(x_order, :);
end
centers = sorted;
end


function pitch = estimate_grid_pitch(centers, rows, cols)
x_grid = reshape(centers(:, 1), cols, rows).';
y_grid = reshape(centers(:, 2), cols, rows).';
dx = diff(x_grid, 1, 2);
dy = diff(y_grid, 1, 1);
pitch = median([dx(:); dy(:)]);
end


function cell_image = extract_padded_cell(image, center, half_size)
if ~isfloat(image), image = im2double(image); end
padded = padarray(image, [half_size half_size], 'symmetric', 'both');
cx = round(center(1)) + half_size;
cy = round(center(2)) + half_size;
cell_image = padded(cy-half_size:cy+half_size-1, ...
    cx-half_size:cx+half_size-1);
end


function mask = segment_acm(cell_image, seed_radius, iterations, smooth_factor, support_radius)
image = mat2gray(cell_image);
limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1)
    image = imadjust(image, limits, [0 1]);
end
[height, width] = size(image);
[x, y] = meshgrid(1:width, 1:height);
cx = (width + 1) / 2;
cy = (height + 1) / 2;
initial_mask = (x-cx).^2 + (y-cy).^2 <= seed_radius^2;
mask = activecontour(image, initial_mask, iterations, 'Chan-Vese', ...
    'SmoothFactor', smooth_factor, 'ContractionBias', 0);
% Prevent a neighboring pillar that is only partially visible at the cell
% edge from joining the target component. This is an ROI guard, not a shape
% fit: the allowed radius is materially larger than every detected pillar.
support_mask = (x-cx).^2 + (y-cy).^2 <= support_radius^2;
mask = mask & support_mask;
mask = select_center_component(mask);
mask = imfill(mask, 'holes');
mask = bwareaopen(mask, 64);
area_fraction = nnz(mask) / numel(mask);
if area_fraction < 0.15 || area_fraction > 0.60
    error('ACM produced implausible area fraction %.4f.', area_fraction);
end
end


function [cleaned, was_cleaned] = remove_sem_edge_artifacts(mask)
% Some SEM tiles show a sliver from the neighbouring acquisition at a cell
% edge. Trigger only when the ACM mask reaches the outer 12 pixels, then
% remove the affected 15-pixel strip and retain the centre component.
trigger_width = 12;
trim_width = 15;
cleaned = mask;
was_cleaned = false;
if any(cleaned(1:trigger_width, :), 'all')
    cleaned(1:trim_width, :) = false; was_cleaned = true;
end
if any(cleaned(end-trigger_width+1:end, :), 'all')
    cleaned(end-trim_width+1:end, :) = false; was_cleaned = true;
end
if any(cleaned(:, 1:trigger_width), 'all')
    cleaned(:, 1:trim_width) = false; was_cleaned = true;
end
if any(cleaned(:, end-trigger_width+1:end), 'all')
    cleaned(:, end-trim_width+1:end) = false; was_cleaned = true;
end
if was_cleaned
    cleaned = select_center_component(cleaned);
    cleaned = imfill(cleaned, 'holes');
end
end


function selected = select_center_component(mask)
components = bwconncomp(mask, 8);
if components.NumObjects == 0
    error('ACM returned an empty mask.');
end
[height, width] = size(mask);
center = [(width + 1) / 2, (height + 1) / 2];
best_component = 0;
best_score = inf;
for index = 1:components.NumObjects
    [rows, cols] = ind2sub(size(mask), components.PixelIdxList{index});
    centroid = [mean(cols), mean(rows)];
    score = norm(centroid - center) - 0.001 * numel(rows);
    if score < best_score
        best_score = score;
        best_component = index;
    end
end
selected = false(size(mask));
selected(components.PixelIdxList{best_component}) = true;
end


function [aligned, shift_magnitude] = align_mask_translation(predicted, truth)
truth_props = regionprops(truth, 'Centroid');
pred_props = regionprops(predicted, 'Centroid');
if isempty(truth_props) || isempty(pred_props)
    error('Cannot align empty contour mask.');
end
truth_centroid = truth_props(1).Centroid;
pred_centroid = pred_props(1).Centroid;
shift = round(truth_centroid - pred_centroid);
shift_magnitude = norm(truth_centroid - pred_centroid);
aligned = shift_binary(predicted, shift(1), shift(2));
end


function shifted = shift_binary(mask, dx, dy)
[height, width] = size(mask);
shifted = false(size(mask));
src_x1 = max(1, 1-dx);
src_x2 = min(width, width-dx);
src_y1 = max(1, 1-dy);
src_y2 = min(height, height-dy);
dst_x1 = src_x1 + dx;
dst_x2 = src_x2 + dx;
dst_y1 = src_y1 + dy;
dst_y2 = src_y2 + dy;
if src_x1 <= src_x2 && src_y1 <= src_y2
    shifted(dst_y1:dst_y2, dst_x1:dst_x2) = ...
        mask(src_y1:src_y2, src_x1:src_x2);
end
end


function metrics = contour_metrics(truth, predicted, pitch_px)
intersection = nnz(truth & predicted);
union = nnz(truth | predicted);
metrics.iou = intersection / union;
metrics.dice = 2 * intersection / (nnz(truth) + nnz(predicted));

truth_edge = bwperim(truth, 8);
pred_edge = bwperim(predicted, 8);
distance_to_truth = bwdist(truth_edge);
distance_to_pred = bwdist(pred_edge);
boundary_distances = [distance_to_truth(pred_edge); distance_to_pred(truth_edge)];
metrics.mean_distance_px = mean(boundary_distances);
metrics.mean_distance_pitch_pct = 100 * metrics.mean_distance_px / pitch_px;
metrics.hd95_px = prctile(boundary_distances, 95);
metrics.hd95_pitch_pct = 100 * metrics.hd95_px / pitch_px;

truth_props = regionprops(truth, 'Area', 'Perimeter', 'Circularity');
pred_props = regionprops(predicted, 'Area', 'Perimeter', 'Circularity');
truth_area = truth_props(1).Area;
pred_area = pred_props(1).Area;
truth_perimeter = truth_props(1).Perimeter;
pred_perimeter = pred_props(1).Perimeter;
metrics.area_error_pct = 100 * abs(pred_area - truth_area) / truth_area;
metrics.perimeter_error_pct = 100 * abs(pred_perimeter - truth_perimeter) / truth_perimeter;
% MATLAB's Circularity property includes the digital-grid correction needed
% to keep a pixelated boundary within the physical 0-to-1 range.
metrics.truth_circularity = truth_props(1).Circularity;
metrics.pred_circularity = pred_props(1).Circularity;
metrics.circularity_abs_error = abs(metrics.pred_circularity - metrics.truth_circularity);
end
