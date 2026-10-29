function calibrate_raw_difficulty(experiment_root)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
if nargin < 1 || strlength(string(experiment_root)) == 0
    experiment_root = fileparts(fileparts(mfilename('fullpath')));
end
experiment_root = char(experiment_root);
if exist(fullfile(experiment_root, 'results', 'inference_manifest.json'), 'file')
    error('R61 outputs already exist. Raw difficulty calibration must precede reconstruction.');
end
cfg = jsondecode(fileread(fullfile(experiment_root, 'config', 'experiment.json')));
data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));
table_dir = fullfile(experiment_root, 'results', 'tables');
if ~exist(table_dir, 'dir'), mkdir(table_dir); end
rows = struct([]);
for family_index = 1:numel(cfg.dataset.families)
    family = cfg.dataset.families(family_index);
    stage = char(family.stage);
    for image_index = 0:(double(cfg.dataset.images_per_family)-1)
        filename = sprintf('%04d.bmp', image_index);
        image_id = sprintf('%s/%04d', char(family.name), image_index);
        image = read_gray(fullfile(data_root, 'src', stage, filename));
        truth_image = read_gray(fullfile(data_root, 'lbl', stage, filename));
        truth = read_gray(fullfile(data_root, 'mask', stage, filename)) > 0.5;
        predicted = segment_acm(image, double(cfg.acm.iterations), double(cfg.acm.smooth_factor), ...
            char(cfg.acm.initialization_mode), double(cfg.acm.seed_radius_fraction));
        predicted_truth = segment_acm(truth_image, double(cfg.acm.iterations), double(cfg.acm.smooth_factor), ...
            char(cfg.acm.initialization_mode), double(cfg.acm.seed_radius_fraction));
        [aligned, shift_magnitude] = align_mask_translation(predicted, truth);
        [aligned_truth, ~] = align_mask_translation(predicted_truth, truth);
        fixed_metrics = contour_metrics(truth, predicted);
        translated_metrics = contour_metrics(truth, aligned);
        truth_metrics = contour_metrics(truth, aligned_truth);
        row.image_id = string(image_id);
        row.family = string(family.name);
        row.family_label_tw = string(family.label_tw);
        row.filename = string(filename);
        row.raw_iou_fixed = fixed_metrics.iou;
        row.raw_iou_translation = translated_metrics.iou;
        row.raw_boundary_distance_fixed_px = fixed_metrics.mean_boundary_distance_px;
        row.raw_boundary_distance_translation_px = translated_metrics.mean_boundary_distance_px;
        row.truth_acm_iou_translation = truth_metrics.iou;
        row.truth_acm_boundary_distance_translation_px = truth_metrics.mean_boundary_distance_px;
        row.centroid_shift_px = shift_magnitude;
        row.truth_area_fraction = nnz(truth) / numel(truth);
        row.pred_area_fraction = nnz(predicted) / numel(predicted);
        row.mean_intensity_0_255 = mean(image, 'all') * 255;
        row.std_intensity_0_255 = std(image, 0, 'all') * 255;
        if isempty(rows), rows = row; else, rows(end+1, 1) = row; end %#ok<AGROW>
    end
    fprintf('Raw difficulty completed: %s\n', char(family.name));
end
result = struct2table(rows);
writetable(result, fullfile(table_dir, 'raw_difficulty_metrics.csv'));

overall_median = median(result.raw_iou_translation);
family_summary = groupsummary(result, 'family', {'median','min','max'}, {'raw_iou_translation','raw_boundary_distance_translation_px'});
writetable(family_summary, fullfile(table_dir, 'raw_difficulty_family_summary.csv'));
min_overall = double(cfg.statistics.raw_difficulty_overall_iou_min);
max_overall = double(cfg.statistics.raw_difficulty_overall_iou_max);
family_max = double(cfg.statistics.raw_difficulty_family_iou_max);
informative_min = double(cfg.statistics.raw_difficulty_informative_family_min);
informative_max = double(cfg.statistics.raw_difficulty_informative_family_max);
minimum_informative = double(cfg.statistics.raw_difficulty_minimum_informative_families);
family_medians = family_summary.median_raw_iou_translation;
informative_count = nnz(family_medians >= informative_min & family_medians <= informative_max);
minimum_truth_iou = min(result.truth_acm_iou_translation);
passed = overall_median >= min_overall && overall_median <= max_overall && ...
    all(family_medians < family_max) && informative_count >= minimum_informative && ...
    minimum_truth_iou >= double(cfg.statistics.truth_acm_minimum_iou);
summary = struct();
summary.experiment_id = char(cfg.experiment_id);
summary.uses_r61 = false;
summary.image_count = height(result);
summary.overall_median_raw_iou = overall_median;
summary.overall_required_range = [min_overall max_overall];
summary.family_iou_maximum = family_max;
summary.informative_family_required_range = [informative_min informative_max];
summary.informative_family_count = informative_count;
summary.minimum_informative_family_count = minimum_informative;
summary.minimum_truth_acm_iou = minimum_truth_iou;
summary.minimum_truth_acm_iou_required = double(cfg.statistics.truth_acm_minimum_iou);
summary.passed = passed;
summary.family_summary = table2struct(family_summary);
summary.generated_at = char(datetime('now', 'TimeZone', 'Asia/Taipei', 'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
fid = fopen(fullfile(table_dir, 'raw_difficulty_summary.json'), 'w', 'n', 'UTF-8');
if fid < 0, error('Cannot write Raw difficulty summary.'); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(summary, PrettyPrint=true), 'char');
disp(family_summary(:, {'family','GroupCount','median_raw_iou_translation','median_raw_boundary_distance_translation_px'}));
fprintf('Overall Raw median IoU: %.6f; difficulty gate: %d\n', overall_median, passed);
end


function image = read_gray(path)
image = imread(path); if ndims(image) == 3, image = rgb2gray(image); end; image = im2double(image);
end


function mask = segment_acm(image, iterations, smooth_factor, initialization_mode, seed_radius_fraction)
image = mat2gray(image); limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1), image = imadjust(image, limits, [0 1]); end
seed = initial_seed(image, initialization_mode, seed_radius_fraction);
mask = activecontour(image, seed, iterations, 'Chan-Vese', 'SmoothFactor', smooth_factor, 'ContractionBias', 0);
mask = select_largest(mask); mask = imfill(mask, 'holes'); mask = bwareaopen(mask, 128); mask = select_largest(mask);
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
level = graythresh(image); candidates = {image >= level, image <= level};
best_area = -inf; seed = false(size(image));
for candidate_index = 1:2
    candidate = imclearborder(candidates{candidate_index}, 8);
    components = bwconncomp(candidate, 8);
    if components.NumObjects == 0, continue; end
    [area, best] = max(cellfun(@numel, components.PixelIdxList));
    fraction = area / numel(image);
    if fraction >= 0.05 && fraction <= 0.65 && area > best_area
        selected = false(size(image)); selected(components.PixelIdxList{best}) = true;
        seed = selected; best_area = area;
    end
end
if best_area < 0, error('Could not derive a valid automatic ACM seed.'); end
seed = imerode(imfill(seed, 'holes'), strel('disk', 3));
if ~any(seed, 'all'), error('Automatic ACM seed became empty.'); end
end


function selected = select_largest(mask)
components = bwconncomp(mask, 8); if components.NumObjects == 0, error('Empty ACM mask.'); end
[~, best] = max(cellfun(@numel, components.PixelIdxList)); selected = false(size(mask)); selected(components.PixelIdxList{best}) = true;
end


function [aligned, shift_magnitude] = align_mask_translation(predicted, truth)
t = regionprops(truth, 'Centroid'); p = regionprops(predicted, 'Centroid'); shift_float = t(1).Centroid - p(1).Centroid;
shift = round(shift_float); shift_magnitude = norm(shift_float); aligned = shift_binary(predicted, shift(1), shift(2));
end


function shifted = shift_binary(mask, dx, dy)
[height, width] = size(mask); shifted = false(size(mask));
sx1=max(1,1-dx); sx2=min(width,width-dx); sy1=max(1,1-dy); sy2=min(height,height-dy);
dx1=sx1+dx; dx2=sx2+dx; dy1=sy1+dy; dy2=sy2+dy;
if sx1<=sx2 && sy1<=sy2, shifted(dy1:dy2,dx1:dx2)=mask(sy1:sy2,sx1:sx2); end
end


function metrics = contour_metrics(truth, predicted)
metrics.iou = nnz(truth & predicted) / nnz(truth | predicted);
truth_edge = bwperim(truth, 8); pred_edge = bwperim(predicted, 8);
to_truth = bwdist(truth_edge); to_pred = bwdist(pred_edge);
metrics.mean_boundary_distance_px = mean([to_truth(pred_edge); to_pred(truth_edge)]);
end
