function run_acm_multimethod(experiment_root)
% Extract closed Chan-Vese contours for Raw, R79 epoch 23, and epoch 100.
% Exact generator masks are the primary geometry truth; ACM on clean labels
% is retained only as an extraction-quality audit.

if nargin < 1 || strlength(string(experiment_root)) == 0
    experiment_root = fileparts(fileparts(mfilename('fullpath')));
end
experiment_root = char(experiment_root);
cfg = jsondecode(fileread(fullfile(experiment_root, 'config', 'experiment.json')));
inference = jsondecode(fileread(fullfile(experiment_root, 'results', 'inference_manifest.json')));
data_root = char(cfg.dataset.root);
table_dir = fullfile(experiment_root, 'results', 'tables');
mask_dir = fullfile(experiment_root, 'results', 'masks');
if ~exist(table_dir, 'dir'), mkdir(table_dir); end
if ~exist(mask_dir, 'dir'), mkdir(mask_dir); end

families = cfg.dataset.families;
per_family = double(cfg.dataset.images_per_family);
image_count = double(cfg.dataset.total_images);
primary_iterations = double(cfg.acm.iterations);
primary_smooth = double(cfg.acm.smooth_factor);
contraction_bias = double(cfg.acm.contraction_bias);
initialization_mode = 'automatic_otsu';
if isfield(cfg.acm, 'initialization_mode'), initialization_mode = char(cfg.acm.initialization_mode); end
seed_radius_fraction = 0.20;
if isfield(cfg.acm, 'seed_radius_fraction'), seed_radius_fraction = double(cfg.acm.seed_radius_fraction); end
method_names = {'Raw', 'R79E23', 'R79E100'};

first_stage = char(families(1).stage);
first_exact = read_mask(fullfile(data_root, 'mask', first_stage, '0000.bmp'));
[image_height, image_width] = size(first_exact);
exact_masks = false(image_height, image_width, image_count);
truth_acm_masks = false(image_height, image_width, image_count);
raw_masks = false(image_height, image_width, image_count);
e23_masks = false(image_height, image_width, image_count);
e100_masks = false(image_height, image_width, image_count);
filenames = strings(image_count, 1);
family_names = strings(image_count, 1);
primary_rows = struct([]);
truth_qa_rows = struct([]);

global_index = 0;
fprintf('%s primary ACM: %d images across %d families.\n', char(cfg.experiment_id), image_count, numel(families));
for family_index = 1:numel(families)
    family_name = char(families(family_index).name);
    family_label_tw = char(families(family_index).label_tw);
    stage = char(families(family_index).stage);
    raw_dir = fullfile(data_root, 'src', stage);
    truth_dir = fullfile(data_root, 'lbl', stage);
    exact_dir = fullfile(data_root, 'mask', stage);
    e23_dir = char(inference.output_dirs_e23.(family_name));
    e100_dir = char(inference.output_dirs_e100.(family_name));
    for local_index = 0:(per_family - 1)
        global_index = global_index + 1;
        filename = sprintf('%04d.bmp', local_index);
        image_id = sprintf('%s/%04d', family_name, local_index);
        exact_mask = read_mask(fullfile(exact_dir, filename));
        truth_image = read_gray(fullfile(truth_dir, filename));
        raw_image = read_gray(fullfile(raw_dir, filename));
        e23_image = read_gray(fullfile(e23_dir, filename));
        e100_image = read_gray(fullfile(e100_dir, filename));

        fprintf('  primary image %s\n', image_id);
        try
            truth_acm = segment_acm(truth_image, primary_iterations, primary_smooth, contraction_bias, initialization_mode, seed_radius_fraction);
            raw_acm = segment_acm(raw_image, primary_iterations, primary_smooth, contraction_bias, initialization_mode, seed_radius_fraction);
            e23_acm = segment_acm(e23_image, primary_iterations, primary_smooth, contraction_bias, initialization_mode, seed_radius_fraction);
            e100_acm = segment_acm(e100_image, primary_iterations, primary_smooth, contraction_bias, initialization_mode, seed_radius_fraction);
        catch ME
            error('ACM segmentation failed for %s.\n%s', image_id, getReport(ME, 'extended'));
        end
        validate_mask(truth_acm, sprintf('truth %s', image_id));
        validate_mask(raw_acm, sprintf('Raw %s', image_id));
        validate_mask(e23_acm, sprintf('R79E23 %s', image_id));
        validate_mask(e100_acm, sprintf('R79E100 %s', image_id));

        exact_masks(:, :, global_index) = exact_mask;
        truth_acm_masks(:, :, global_index) = truth_acm;
        raw_masks(:, :, global_index) = raw_acm;
        e23_masks(:, :, global_index) = e23_acm;
        e100_masks(:, :, global_index) = e100_acm;
        filenames(global_index) = string(filename);
        family_names(global_index) = string(family_name);

        truth_metrics = contour_metrics(exact_mask, truth_acm);
        truth_row = base_row(image_id, family_name, family_label_tw, filename, 'TruthACM', ...
            'fixed_pixel_coordinates', truth_image, exact_mask, truth_acm, 0, ...
            primary_iterations, primary_smooth, truth_metrics);
        truth_qa_rows = append_row(truth_qa_rows, truth_row);

        method_images = {raw_image, e23_image, e100_image};
        method_masks = {raw_acm, e23_acm, e100_acm};
        for method_index = 1:3
            [translated_mask, shift_magnitude] = align_mask_translation(method_masks{method_index}, exact_mask);
            alignment_names = {'fixed_pixel_coordinates', 'translation_only'};
            masks_for_scoring = {method_masks{method_index}, translated_mask};
            for alignment_index = 1:2
                metrics = contour_metrics(exact_mask, masks_for_scoring{alignment_index});
                row = base_row(image_id, family_name, family_label_tw, filename, ...
                    method_names{method_index}, alignment_names{alignment_index}, ...
                    method_images{method_index}, exact_mask, masks_for_scoring{alignment_index}, ...
                    shift_magnitude, primary_iterations, primary_smooth, metrics);
                primary_rows = append_row(primary_rows, row);
            end
        end
    end
    fprintf('  completed %s (%d/%d families)\n', family_name, family_index, numel(families));
end

primary_table = struct2table(primary_rows);
truth_qa_table = struct2table(truth_qa_rows);
writetable(primary_table, fullfile(table_dir, 'primary_contour_metrics.csv'));
writetable(truth_qa_table, fullfile(table_dir, 'truth_acm_geometry_qa.csv'));

presets = cfg.acm.sensitivity_presets;
sensitivity_filenames = cellstr(string(cfg.acm.sensitivity_filenames));
sensitivity_rows = struct([]);
fprintf('%s ACM sensitivity: %d families, %d images each, %d presets.\n', char(cfg.experiment_id), ...
    numel(families), numel(sensitivity_filenames), numel(presets));
for preset_index = 1:numel(presets)
    preset = presets(preset_index);
    for family_index = 1:numel(families)
        family_name = char(families(family_index).name);
        family_label_tw = char(families(family_index).label_tw);
        stage = char(families(family_index).stage);
        raw_dir = fullfile(data_root, 'src', stage);
        exact_dir = fullfile(data_root, 'mask', stage);
        e23_dir = char(inference.output_dirs_e23.(family_name));
        e100_dir = char(inference.output_dirs_e100.(family_name));
        for selected_index = 1:numel(sensitivity_filenames)
            filename = sensitivity_filenames{selected_index};
            image_id = sprintf('%s/%s', family_name, erase(filename, '.bmp'));
            exact_mask = read_mask(fullfile(exact_dir, filename));
            method_images = {read_gray(fullfile(raw_dir, filename)), ...
                read_gray(fullfile(e23_dir, filename)), read_gray(fullfile(e100_dir, filename))};
            for method_index = 1:3
                predicted = segment_acm(method_images{method_index}, double(preset.iterations), ...
                    double(preset.smooth_factor), contraction_bias, initialization_mode, seed_radius_fraction);
                validate_mask(predicted, sprintf('%s %s %s', char(preset.name), method_names{method_index}, image_id));
                [translated, shift_magnitude] = align_mask_translation(predicted, exact_mask);
                metrics = contour_metrics(exact_mask, translated);
                row = base_row(image_id, family_name, family_label_tw, filename, ...
                    method_names{method_index}, 'translation_only', method_images{method_index}, ...
                    exact_mask, translated, shift_magnitude, double(preset.iterations), ...
                    double(preset.smooth_factor), metrics);
                row.preset = string(preset.name);
                sensitivity_rows = append_row(sensitivity_rows, row);
            end
        end
    end
    fprintf('  completed sensitivity preset %s\n', char(preset.name));
end
sensitivity_table = struct2table(sensitivity_rows);
writetable(sensitivity_table, fullfile(table_dir, 'acm_sensitivity_metrics.csv'));

save(fullfile(mask_dir, 'acm_primary_masks.mat'), 'exact_masks', 'truth_acm_masks', ...
    'raw_masks', 'e23_masks', 'e100_masks', 'filenames', 'family_names', ...
    'primary_iterations', 'primary_smooth', 'contraction_bias');

summary = struct();
summary.experiment_id = char(cfg.experiment_id);
summary.image_count = image_count;
summary.family_count = numel(families);
summary.methods = method_names;
summary.image_shape = [image_height image_width];
summary.primary_iterations = primary_iterations;
summary.primary_smooth_factor = primary_smooth;
if strcmp(initialization_mode, 'fixed_center_disk')
    summary.initialization = sprintf('fixed centered disk; radius fraction %.4f; no truth geometry', seed_radius_fraction);
else
    summary.initialization = 'polarity-independent Otsu inner seed; border regions removed; largest valid component eroded by 3 px';
end
summary.initialization_uses_truth_shape = false;
summary.primary_truth = 'exact generator geometry mask';
summary.primary_alignment = 'translation_only';
summary.secondary_alignment = 'fixed_pixel_coordinates';
summary.scale_fitting = false;
summary.rotation_fitting = false;
summary.primary_row_count = height(primary_table);
summary.truth_qa_row_count = height(truth_qa_table);
summary.sensitivity_row_count = height(sensitivity_table);
summary.generated_at = char(datetime('now', 'TimeZone', 'Asia/Taipei', 'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
fid = fopen(fullfile(table_dir, 'acm_extraction_summary.json'), 'w', 'n', 'UTF-8');
if fid < 0, error('Could not write ACM summary JSON.'); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(summary, PrettyPrint=true), 'char');
fprintf('%s ACM extraction complete.\n', char(cfg.experiment_id));
end


function rows = append_row(rows, row)
if isempty(rows)
    rows = row;
else
    row = orderfields(row, rows(1));
    rows(end+1, 1) = row; %#ok<AGROW>
end
end


function image = read_gray(path)
if ~exist(path, 'file'), error('Missing image: %s', path); end
image = imread(path);
if ndims(image) == 3, image = rgb2gray(image); end
image = im2double(image);
end


function mask = read_mask(path)
mask = read_gray(path) > 0.5;
if bwconncomp(mask, 8).NumObjects ~= 1, error('Exact mask is not one component: %s', path); end
end


function mask = segment_acm(image, iterations, smooth_factor, contraction_bias, initialization_mode, seed_radius_fraction)
image = mat2gray(image);
limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1), image = imadjust(image, limits, [0 1]); end
initial_mask = initial_seed(image, initialization_mode, seed_radius_fraction);
mask = activecontour(image, initial_mask, iterations, 'Chan-Vese', ...
    'SmoothFactor', smooth_factor, 'ContractionBias', contraction_bias);
mask = select_largest_component(mask);
mask = imfill(mask, 'holes');
mask = bwareaopen(mask, 128);
mask = select_largest_component(mask);
end


function seed = initial_seed(image, initialization_mode, seed_radius_fraction)
if strcmp(initialization_mode, 'fixed_center_disk')
    [height, width] = size(image);
    [x, y] = meshgrid(1:width, 1:height);
    radius = seed_radius_fraction * min(height, width);
    seed = (x - (width + 1) / 2).^2 + (y - (height + 1) / 2).^2 <= radius.^2;
elseif strcmp(initialization_mode, 'smoothed_otsu')
    try
        seed = automatic_inner_seed(imgaussfilt(image, 3.0));
    catch
        [height, width] = size(image);
        [x, y] = meshgrid(1:width, 1:height);
        radius = seed_radius_fraction * min(height, width);
        seed = (x - (width + 1) / 2).^2 + (y - (height + 1) / 2).^2 <= radius.^2;
    end
else
    seed = automatic_inner_seed(image);
end
end


function seed = automatic_inner_seed(image)
level = graythresh(image);
candidates = {image >= level, image <= level};
best_area = -inf;
seed = false(size(image));
for candidate_index = 1:2
    candidate = imclearborder(candidates{candidate_index}, 8);
    components = bwconncomp(candidate, 8);
    if components.NumObjects == 0, continue; end
    [area, best] = max(cellfun(@numel, components.PixelIdxList));
    area_fraction = area / numel(image);
    if area_fraction >= 0.05 && area_fraction <= 0.65 && area > best_area
        selected = false(size(image));
        selected(components.PixelIdxList{best}) = true;
        seed = selected;
        best_area = area;
    end
end
if best_area < 0, error('Could not derive a valid automatic ACM seed.'); end
seed = imerode(imfill(seed, 'holes'), strel('disk', 3));
if ~any(seed, 'all'), error('Automatic ACM seed became empty.'); end
end


function selected = select_largest_component(mask)
components = bwconncomp(mask, 8);
if components.NumObjects == 0, error('ACM returned an empty mask.'); end
[~, best] = max(cellfun(@numel, components.PixelIdxList));
selected = false(size(mask)); selected(components.PixelIdxList{best}) = true;
end


function validate_mask(mask, label)
area_fraction = nnz(mask) / numel(mask);
if area_fraction < 0.02 || area_fraction > 0.80
    error('Implausible ACM area fraction %.4f for %s.', area_fraction, label);
end
if bwconncomp(mask, 8).NumObjects ~= 1, error('ACM mask is not one component for %s.', label); end
end


function row = base_row(image_id, family, family_label_tw, filename, method, alignment, ...
    image, truth, predicted, shift_magnitude, iterations, smooth_factor, metrics)
row.image_id = string(image_id);
row.family = string(family);
row.family_label_tw = string(family_label_tw);
row.filename = string(filename);
row.method = string(method);
row.alignment = string(alignment);
row.mean_intensity_0_255 = mean(image, 'all') * 255;
row.std_intensity_0_255 = std(image, 0, 'all') * 255;
row.acm_iterations = iterations;
row.smooth_factor = smooth_factor;
row.centroid_shift_px = shift_magnitude;
row.truth_area_fraction = nnz(truth) / numel(truth);
row.pred_area_fraction = nnz(predicted) / numel(predicted);
row.iou = metrics.iou;
row.dice = metrics.dice;
row.mean_boundary_distance_px = metrics.mean_boundary_distance_px;
row.hd95_px = metrics.hd95_px;
row.area_error_pct = metrics.area_error_pct;
row.perimeter_error_pct = metrics.perimeter_error_pct;
row.solidity_abs_error = metrics.solidity_abs_error;
row.roughness_abs_error = metrics.roughness_abs_error;
end


function [aligned, shift_magnitude] = align_mask_translation(predicted, truth)
truth_props = regionprops(truth, 'Centroid'); pred_props = regionprops(predicted, 'Centroid');
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


function metrics = contour_metrics(truth, predicted)
intersection = nnz(truth & predicted); union = nnz(truth | predicted);
metrics.iou = intersection / union;
metrics.dice = 2 * intersection / (nnz(truth) + nnz(predicted));
truth_edge = bwperim(truth, 8); pred_edge = bwperim(predicted, 8);
distance_to_truth = bwdist(truth_edge); distance_to_pred = bwdist(pred_edge);
distances = [distance_to_truth(pred_edge); distance_to_pred(truth_edge)];
metrics.mean_boundary_distance_px = mean(distances);
metrics.hd95_px = prctile(distances, 95);
truth_props = regionprops(truth, 'Area', 'Perimeter', 'Solidity');
pred_props = regionprops(predicted, 'Area', 'Perimeter', 'Solidity');
truth_area = truth_props(1).Area; pred_area = pred_props(1).Area;
truth_perimeter = truth_props(1).Perimeter; pred_perimeter = pred_props(1).Perimeter;
metrics.area_error_pct = 100 * abs(pred_area - truth_area) / truth_area;
metrics.perimeter_error_pct = 100 * abs(pred_perimeter - truth_perimeter) / truth_perimeter;
metrics.solidity_abs_error = abs(pred_props(1).Solidity - truth_props(1).Solidity);
metrics.roughness_abs_error = abs(pred_perimeter / sqrt(pred_area) - truth_perimeter / sqrt(truth_area));
end
