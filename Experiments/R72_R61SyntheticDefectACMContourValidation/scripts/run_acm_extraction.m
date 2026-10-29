function run_acm_extraction(experiment_root)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
% Extract full closed contours with the same Chan-Vese ACM family used by
% R69/R70. All methods share one fixed, truth-independent outer seed.

if nargin < 1 || strlength(string(experiment_root)) == 0
    experiment_root = fileparts(fileparts(mfilename('fullpath')));
end
experiment_root = char(experiment_root);
config_path = fullfile(experiment_root, 'config', 'experiment.json');
cfg = jsondecode(fileread(config_path));

table_dir = fullfile(experiment_root, 'results', 'tables');
mask_dir = fullfile(experiment_root, 'results', 'masks');
if ~exist(table_dir, 'dir'), mkdir(table_dir); end
if ~exist(mask_dir, 'dir'), mkdir(mask_dir); end

image_ids = double(cfg.sources.image_ids(:)');
method_names = {'Raw', 'COMBO', 'R61v16'};
method_dirs = {
    fullfile(PROJECT_ROOT, char(cfg.sources.raw_dir)), ...
    fullfile(PROJECT_ROOT, char(cfg.sources.combo_dir)), ...
    fullfile(PROJECT_ROOT, char(cfg.sources.r61_dir)) ...
};
truth_dir = fullfile(PROJECT_ROOT, char(cfg.sources.truth_dir));

primary_iterations = double(cfg.acm.iterations);
primary_smooth = double(cfg.acm.smooth_factor);
contraction_bias = double(cfg.acm.contraction_bias);

first_truth = read_gray(fullfile(truth_dir, sprintf('%04d.bmp', image_ids(1))));
[image_height, image_width] = size(first_truth);
image_count = numel(image_ids);
truth_masks = false(image_height, image_width, image_count);
raw_masks = false(image_height, image_width, image_count);
combo_masks = false(image_height, image_width, image_count);
r61_masks = false(image_height, image_width, image_count);
primary_rows = struct([]);

fprintf('R72 primary ACM: %d images, %d methods.\n', image_count, numel(method_names));
for image_index = 1:image_count
    image_id = image_ids(image_index);
    filename = sprintf('%04d.bmp', image_id);
    truth_image = read_gray(fullfile(truth_dir, filename));
    truth_mask = segment_acm(truth_image, primary_iterations, primary_smooth, contraction_bias);
    validate_mask(truth_mask, sprintf('truth %s', filename));
    truth_masks(:, :, image_index) = truth_mask;

    for method_index = 1:numel(method_names)
        method_image = read_gray(fullfile(method_dirs{method_index}, filename));
        predicted_mask = segment_acm(method_image, primary_iterations, primary_smooth, contraction_bias);
        validate_mask(predicted_mask, sprintf('%s %s', method_names{method_index}, filename));
        if method_index == 1
            raw_masks(:, :, image_index) = predicted_mask;
        elseif method_index == 2
            combo_masks(:, :, image_index) = predicted_mask;
        else
            r61_masks(:, :, image_index) = predicted_mask;
        end

        [translated_mask, shift_magnitude] = align_mask_translation(predicted_mask, truth_mask);
        alignment_names = {'fixed_pixel_coordinates', 'translation_only'};
        masks_for_scoring = {predicted_mask, translated_mask};
        for alignment_index = 1:2
            metrics = contour_metrics(truth_mask, masks_for_scoring{alignment_index});
            row = make_primary_row(image_id, method_names{method_index}, ...
                alignment_names{alignment_index}, method_image, truth_mask, ...
                masks_for_scoring{alignment_index}, shift_magnitude, ...
                primary_iterations, primary_smooth, metrics);
            if isempty(primary_rows)
                primary_rows = row;
            else
                row = orderfields(row, primary_rows(1));
                primary_rows(end+1, 1) = row; %#ok<AGROW>
            end
        end
    end
    fprintf('  completed %s (%d/%d)\n', filename, image_index, image_count);
end

primary_table = struct2table(primary_rows);
writetable(primary_table, fullfile(table_dir, 'primary_contour_metrics.csv'));

presets = cfg.acm.sensitivity_presets;
if ~isstruct(presets), error('Sensitivity presets are missing.'); end
sensitivity_ids = double(cfg.acm.sensitivity_image_ids(:)');
sensitivity_rows = struct([]);
fprintf('R72 ACM sensitivity: %d images, %d presets.\n', numel(sensitivity_ids), numel(presets));
for preset_index = 1:numel(presets)
    preset = presets(preset_index);
    for selected_index = 1:numel(sensitivity_ids)
        image_id = sensitivity_ids(selected_index);
        filename = sprintf('%04d.bmp', image_id);
        truth_image = read_gray(fullfile(truth_dir, filename));
        truth_mask = segment_acm(truth_image, double(preset.iterations), ...
            double(preset.smooth_factor), contraction_bias);
        validate_mask(truth_mask, sprintf('sensitivity truth %s %s', char(preset.name), filename));
        for method_index = 1:numel(method_names)
            method_image = read_gray(fullfile(method_dirs{method_index}, filename));
            predicted_mask = segment_acm(method_image, double(preset.iterations), ...
                double(preset.smooth_factor), contraction_bias);
            validate_mask(predicted_mask, sprintf('sensitivity %s %s %s', ...
                char(preset.name), method_names{method_index}, filename));
            [translated_mask, shift_magnitude] = align_mask_translation(predicted_mask, truth_mask);
            metrics = contour_metrics(truth_mask, translated_mask);
            row = make_sensitivity_row(image_id, char(preset.name), ...
                method_names{method_index}, method_image, truth_mask, translated_mask, ...
                shift_magnitude, double(preset.iterations), ...
                double(preset.smooth_factor), metrics);
            if isempty(sensitivity_rows)
                sensitivity_rows = row;
            else
                row = orderfields(row, sensitivity_rows(1));
                sensitivity_rows(end+1, 1) = row; %#ok<AGROW>
            end
        end
    end
    fprintf('  completed preset %s\n', char(preset.name));
end

sensitivity_table = struct2table(sensitivity_rows);
writetable(sensitivity_table, fullfile(table_dir, 'acm_sensitivity_metrics.csv'));

save(fullfile(mask_dir, 'acm_primary_masks.mat'), ...
    'image_ids', 'truth_masks', 'raw_masks', 'combo_masks', 'r61_masks', ...
    'primary_iterations', 'primary_smooth', 'contraction_bias');

summary = struct();
summary.experiment_id = char(cfg.experiment_id);
summary.image_count = image_count;
summary.image_ids = image_ids;
summary.methods = method_names;
summary.image_shape = [image_height image_width];
summary.primary_iterations = primary_iterations;
summary.primary_smooth_factor = primary_smooth;
summary.initialization = 'fixed outer rectangle, 10.5%-89.5% of each axis';
summary.initialization_uses_truth_shape = false;
summary.primary_alignment = 'translation_only';
summary.secondary_alignment = 'fixed_pixel_coordinates';
summary.scale_fitting = false;
summary.rotation_fitting = false;
summary.primary_row_count = height(primary_table);
summary.sensitivity_row_count = height(sensitivity_table);
summary.generated_at = char(datetime('now', 'TimeZone', 'Asia/Taipei', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
json_text = jsonencode(summary, PrettyPrint=true);
fid = fopen(fullfile(table_dir, 'acm_extraction_summary.json'), 'w', 'n', 'UTF-8');
if fid < 0, error('Could not write ACM summary JSON.'); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, json_text, 'char');
fprintf('R72 ACM extraction complete.\n');
end


function image = read_gray(path)
if ~exist(path, 'file'), error('Missing image: %s', path); end
image = imread(path);
if ndims(image) == 3, image = rgb2gray(image); end
image = im2double(image);
end


function mask = segment_acm(image, iterations, smooth_factor, contraction_bias)
image = mat2gray(image);
limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1)
    image = imadjust(image, limits, [0 1]);
end
[height, width] = size(image);
y1 = max(2, round(0.105 * height));
y2 = min(height - 1, round(0.895 * height));
x1 = max(2, round(0.105 * width));
x2 = min(width - 1, round(0.895 * width));
initial_mask = false(height, width);
initial_mask(y1:y2, x1:x2) = true;
mask = activecontour(image, initial_mask, iterations, 'Chan-Vese', ...
    'SmoothFactor', smooth_factor, 'ContractionBias', contraction_bias);
mask = select_largest_component(mask);
mask = imfill(mask, 'holes');
mask = bwareaopen(mask, 256);
mask = select_largest_component(mask);
end


function selected = select_largest_component(mask)
components = bwconncomp(mask, 8);
if components.NumObjects == 0, error('ACM returned an empty mask.'); end
[~, best_index] = max(cellfun(@numel, components.PixelIdxList));
selected = false(size(mask));
selected(components.PixelIdxList{best_index}) = true;
end


function validate_mask(mask, label)
area_fraction = nnz(mask) / numel(mask);
if area_fraction < 0.25 || area_fraction > 0.60
    error('Implausible ACM area fraction %.4f for %s.', area_fraction, label);
end
if any(mask(1, :)) || any(mask(end, :)) || any(mask(:, 1)) || any(mask(:, end))
    error('ACM mask touches the image border for %s.', label);
end
if bwconncomp(mask, 8).NumObjects ~= 1
    error('ACM mask is not a single component for %s.', label);
end
end


function row = make_primary_row(image_id, method, alignment, image, truth, ...
    predicted, shift_magnitude, iterations, smooth_factor, metrics)
row.image_id = image_id;
row.method = string(method);
row.alignment = string(alignment);
row.mean_intensity_0_255 = mean(image, 'all') * 255;
row.std_intensity_0_255 = std(image, 0, 'all') * 255;
row.acm_iterations = iterations;
row.smooth_factor = smooth_factor;
row.centroid_shift_px = shift_magnitude;
row.truth_area_fraction = nnz(truth) / numel(truth);
row.pred_area_fraction = nnz(predicted) / numel(predicted);
row = add_metrics(row, metrics);
end


function row = make_sensitivity_row(image_id, preset, method, image, truth, ...
    predicted, shift_magnitude, iterations, smooth_factor, metrics)
row.image_id = image_id;
row.preset = string(preset);
row.method = string(method);
row.alignment = "translation_only";
row.mean_intensity_0_255 = mean(image, 'all') * 255;
row.std_intensity_0_255 = std(image, 0, 'all') * 255;
row.acm_iterations = iterations;
row.smooth_factor = smooth_factor;
row.centroid_shift_px = shift_magnitude;
row.truth_area_fraction = nnz(truth) / numel(truth);
row.pred_area_fraction = nnz(predicted) / numel(predicted);
row = add_metrics(row, metrics);
end


function row = add_metrics(row, metrics)
row.iou = metrics.iou;
row.dice = metrics.dice;
row.mean_boundary_distance_px = metrics.mean_boundary_distance_px;
row.hd95_px = metrics.hd95_px;
row.area_error_pct = metrics.area_error_pct;
row.perimeter_error_pct = metrics.perimeter_error_pct;
row.truth_circularity = metrics.truth_circularity;
row.pred_circularity = metrics.pred_circularity;
row.circularity_abs_error = metrics.circularity_abs_error;
end


function [aligned, shift_magnitude] = align_mask_translation(predicted, truth)
truth_props = regionprops(truth, 'Centroid');
pred_props = regionprops(predicted, 'Centroid');
truth_centroid = truth_props(1).Centroid;
pred_centroid = pred_props(1).Centroid;
shift_float = truth_centroid - pred_centroid;
shift = round(shift_float);
shift_magnitude = norm(shift_float);
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


function metrics = contour_metrics(truth, predicted)
intersection = nnz(truth & predicted);
union = nnz(truth | predicted);
metrics.iou = intersection / union;
metrics.dice = 2 * intersection / (nnz(truth) + nnz(predicted));

truth_edge = bwperim(truth, 8);
pred_edge = bwperim(predicted, 8);
distance_to_truth = bwdist(truth_edge);
distance_to_pred = bwdist(pred_edge);
boundary_distances = [distance_to_truth(pred_edge); distance_to_pred(truth_edge)];
metrics.mean_boundary_distance_px = mean(boundary_distances);
metrics.hd95_px = prctile(boundary_distances, 95);

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
