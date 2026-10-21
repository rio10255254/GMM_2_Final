function run_r89_stage_acm(base_mat_path, stage_root, output_root, stage_labels_csv)
% Re-evaluate selected R89 checkpoints with the frozen primary SEM ACM rule.
%
% This intentionally reuses the SEM truth masks, optical centres, pitch, and
% primary ACM settings frozen by the R69/R89 full evaluation.  Only the
% checkpoint reconstructions are re-segmented, so checkpoint comparisons do
% not silently change the reference or the contour rule.

if nargin ~= 4
    error('Expected base_mat_path, stage_root, output_root, stage_labels_csv.');
end

base = load(base_mat_path, 'truth_masks', 'opt_centers', 'opt_pitch', ...
    'global_index', 'exposures', 'primary_iterations', 'primary_smooth', ...
    'cell_half', 'seed_radius', 'support_radius');

truth_masks = logical(base.truth_masks);
opt_centers = double(base.opt_centers);
opt_pitch = double(base.opt_pitch);
global_index = double(base.global_index);
exposures = double(base.exposures(:).');
primary_iterations = double(base.primary_iterations);
primary_smooth = double(base.primary_smooth);
cell_half = double(base.cell_half);
seed_radius = double(base.seed_radius);
support_radius = double(base.support_radius);
cell_side = 2 * cell_half;

stage_labels = strtrim(split(string(stage_labels_csv), ','));
stage_labels(stage_labels == "") = [];
if isempty(stage_labels)
    error('No stage labels were supplied.');
end

for stage_index = 1:numel(stage_labels)
    recon_dir = fullfile(stage_root, char(stage_labels(stage_index)), 'reconstruction');
    for exposure = exposures
        image_path = fullfile(recon_dir, sprintf('%d.bmp', exposure));
        if ~isfile(image_path)
            error('Missing reconstruction: %s', image_path);
        end
    end
end

if ~exist(output_root, 'dir'), mkdir(output_root); end

pool = gcp('nocreate');
if isempty(pool)
    pool = parpool('Processes', min(8, feature('numcores'))); %#ok<NASGU>
end

stage_count = numel(stage_labels);
exposure_count = numel(exposures);
task_count = stage_count * exposure_count;
task_results = cell(task_count, 1);

parfor task_index = 1:task_count
    [stage_index, exposure_index] = ind2sub([stage_count, exposure_count], task_index);
    label = char(stage_labels(stage_index));
    recon_path = fullfile(stage_root, label, 'reconstruction', ...
        sprintf('%d.bmp', exposures(exposure_index)));
    task_results{task_index} = evaluate_one_image(recon_path, truth_masks, ...
        opt_centers, opt_pitch, global_index, cell_half, seed_radius, ...
        primary_iterations, primary_smooth, support_radius);
end

metric_names = {'iou', 'dice', 'mean_boundary_distance_px', ...
    'mean_boundary_distance_pitch_pct', 'hd95_px', 'hd95_pitch_pct', ...
    'area_error_pct', 'perimeter_error_pct', 'truth_circularity', ...
    'pred_circularity', 'circularity_abs_error', ...
    'centroid_alignment_shift_px'};

for stage_index = 1:stage_count
    label = char(stage_labels(stage_index));
    table_dir = fullfile(output_root, label, 'tables');
    mask_dir = fullfile(output_root, label, 'masks');
    if ~exist(table_dir, 'dir'), mkdir(table_dir); end
    if ~exist(mask_dir, 'dir'), mkdir(mask_dir); end

    recon_cells = zeros(cell_side, cell_side, 36, exposure_count, 'uint8');
    recon_masks = false(cell_side, cell_side, 36, exposure_count);
    aligned_masks = false(cell_side, cell_side, 36, exposure_count);

    record_count = exposure_count * 36;
    exposure_col = zeros(record_count, 1);
    pillar_col = zeros(record_count, 1);
    row_col = zeros(record_count, 1);
    grid_col = zeros(record_count, 1);
    method_col = strings(record_count, 1);
    metric_cols = zeros(record_count, numel(metric_names));
    record_index = 0;

    for exposure_index = 1:exposure_count
        task_index = sub2ind([stage_count, exposure_count], stage_index, exposure_index);
        result = task_results{task_index};
        recon_cells(:, :, :, exposure_index) = result.cells;
        recon_masks(:, :, :, exposure_index) = result.masks;
        aligned_masks(:, :, :, exposure_index) = result.aligned_masks;

        for grid_row_index = 1:6
            for grid_col_index = 1:6
                pillar_id = global_index(grid_row_index, grid_col_index);
                record_index = record_index + 1;
                exposure_col(record_index) = exposures(exposure_index);
                pillar_col(record_index) = pillar_id;
                row_col(record_index) = grid_row_index;
                grid_col(record_index) = grid_col_index;
                method_col(record_index) = string(label);
                metric_cols(record_index, :) = result.metrics(pillar_id, :);
            end
        end
    end

    primary_metrics = table(exposure_col, pillar_col, row_col, grid_col, ...
        method_col, 'VariableNames', {'exposure', 'pillar_id', 'grid_row', ...
        'grid_col', 'method'});
    for metric_index = 1:numel(metric_names)
        primary_metrics.(metric_names{metric_index}) = metric_cols(:, metric_index);
    end
    writetable(primary_metrics, fullfile(table_dir, 'primary_contour_metrics.csv'));

    save(fullfile(mask_dir, 'stage_primary_masks.mat'), 'recon_cells', ...
        'recon_masks', 'aligned_masks', 'global_index', 'exposures', ...
        'opt_centers', 'opt_pitch', 'primary_iterations', 'primary_smooth', ...
        'cell_half', 'seed_radius', 'support_radius', '-v7');

    summary = struct();
    summary.status = 'complete';
    summary.stage = label;
    summary.exposure_count = exposure_count;
    summary.pillar_count = 36;
    summary.record_count = height(primary_metrics);
    summary.reference = char(base_mat_path);
    summary.optical_pitch_px = opt_pitch;
    summary.acm_method = 'Chan-Vese';
    summary.primary_iterations = primary_iterations;
    summary.primary_smooth_factor = primary_smooth;
    summary.seed_radius_px = seed_radius;
    summary.support_radius_px = support_radius;
    fid = fopen(fullfile(table_dir, 'stage_acm_summary.json'), 'w');
    fprintf(fid, '%s', jsonencode(summary, PrettyPrint=true));
    fclose(fid);

    fprintf('%s complete: %d fixed-rule contour records.\n', label, height(primary_metrics));
end
end


function result = evaluate_one_image(recon_path, truth_masks, opt_centers, ...
    opt_pitch, global_index, cell_half, seed_radius, primary_iterations, ...
    primary_smooth, support_radius)
recon_image = imread(recon_path);
if ndims(recon_image) == 3, recon_image = rgb2gray(recon_image); end
cell_side = 2 * cell_half;
result.cells = zeros(cell_side, cell_side, 36, 'uint8');
result.masks = false(cell_side, cell_side, 36);
result.aligned_masks = false(cell_side, cell_side, 36);
result.metrics = zeros(36, 12);

for grid_row_index = 1:6
    for grid_col_index = 1:6
        linear_position = (grid_row_index - 1) * 6 + grid_col_index;
        pillar_id = global_index(grid_row_index, grid_col_index);
        center = opt_centers(linear_position, :);
        recon_cell = extract_padded_cell(recon_image, center, cell_half);
        recon_mask = segment_acm(recon_cell, seed_radius, primary_iterations, ...
            primary_smooth, support_radius);
        [aligned_mask, shift_magnitude] = align_mask_translation( ...
            recon_mask, truth_masks(:, :, pillar_id));
        metrics = contour_metrics(truth_masks(:, :, pillar_id), aligned_mask, opt_pitch);

        result.cells(:, :, pillar_id) = im2uint8(mat2gray(recon_cell));
        result.masks(:, :, pillar_id) = recon_mask;
        result.aligned_masks(:, :, pillar_id) = aligned_mask;
        result.metrics(pillar_id, :) = [metrics.iou, metrics.dice, ...
            metrics.mean_distance_px, metrics.mean_distance_pitch_pct, ...
            metrics.hd95_px, metrics.hd95_pitch_pct, metrics.area_error_pct, ...
            metrics.perimeter_error_pct, metrics.truth_circularity, ...
            metrics.pred_circularity, metrics.circularity_abs_error, ...
            shift_magnitude];
    end
end
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
metrics.truth_circularity = truth_props(1).Circularity;
metrics.pred_circularity = pred_props(1).Circularity;
metrics.circularity_abs_error = abs(metrics.pred_circularity - metrics.truth_circularity);
end
