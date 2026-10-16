% Check whether fixed Chan-Vese ACM is stable when geometry is unchanged.

script_path = mfilename('fullpath');
root = fileparts(fileparts(script_path));
input_dir = fullfile(root, 'results', 'acm_photometric_inputs');
manifest_path = fullfile(input_dir, 'manifest.csv');
output_csv = fullfile(root, 'results', 'acm_photometric_metrics.csv');
output_json = fullfile(root, 'results', 'acm_photometric_audit.json');

if ~isfile(manifest_path)
    error('Missing ACM input manifest: %s', manifest_path);
end

manifest = readtable(manifest_path, 'TextType', 'string');
smoothness = [0.75, 1.0, 1.5];
preset_names = ["low_smooth", "primary", "high_smooth"];
iterations = 100;
row_count = height(manifest) * numel(smoothness);

image_id = strings(row_count, 1);
shape_index = zeros(row_count, 1);
variant = strings(row_count, 1);
bright_foreground = false(row_count, 1);
preset = strings(row_count, 1);
smooth_factor = zeros(row_count, 1);
iou = zeros(row_count, 1);
boundary_distance_px = zeros(row_count, 1);
signed_area_error_fraction = zeros(row_count, 1);
centroid_error_px = zeros(row_count, 1);
component_error = zeros(row_count, 1);

cursor = 0;
[xx, yy] = meshgrid(1:256, 1:256);
seed = ((xx - 128.5).^2 + (yy - 128.5).^2) <= 34^2;

for index = 1:height(manifest)
    image = im2double(imread(fullfile(input_dir, manifest.image_file(index))));
    truth = imread(fullfile(input_dir, manifest.mask_file(index))) > 127;
    if ndims(image) == 3
        image = rgb2gray(image);
    end
    image = mat2gray(image);
    limits = stretchlim(image, [0.01 0.99]);
    image = imadjust(image, limits, []);
    for setting = 1:numel(smoothness)
        cursor = cursor + 1;
        prediction = activecontour( ...
            image, seed, iterations, 'Chan-Vese', ...
            'SmoothFactor', smoothness(setting), 'ContractionBias', 0);
        overlap = nnz(prediction & truth);
        total = nnz(prediction | truth);
        iou(cursor) = (overlap + eps) / (total + eps);
        boundary_distance_px(cursor) = symmetric_boundary_distance(prediction, truth);
        signed_area_error_fraction(cursor) = (nnz(prediction) - nnz(truth)) / max(nnz(truth), 1);
        predicted_centroid = safe_centroid(prediction);
        truth_centroid = safe_centroid(truth);
        centroid_error_px(cursor) = hypot(predicted_centroid(1) - truth_centroid(1), predicted_centroid(2) - truth_centroid(2));
        component_error(cursor) = abs(bwconncomp(prediction, 8).NumObjects - bwconncomp(truth, 8).NumObjects);
        image_id(cursor) = manifest.image_id(index);
        shape_index(cursor) = manifest.shape_index(index);
        variant(cursor) = manifest.variant(index);
        bright_foreground(cursor) = logical(manifest.bright_foreground(index));
        preset(cursor) = preset_names(setting);
        smooth_factor(cursor) = smoothness(setting);
    end
end

metrics = table(image_id, shape_index, variant, bright_foreground, preset, smooth_factor, ...
    iou, boundary_distance_px, signed_area_error_fraction, centroid_error_px, component_error);
writetable(metrics, output_csv);

variant_names = unique(metrics.variant, 'stable');
variant_summary = struct( ...
    'preset', {}, 'variant', {}, 'count', {}, 'median_iou', {}, ...
    'minimum_iou', {}, 'median_boundary_distance_px', {}, ...
    'median_abs_area_error_fraction', {}, 'median_centroid_error_px', {});
for setting = 1:numel(preset_names)
    for item = 1:numel(variant_names)
        selected = metrics.preset == preset_names(setting) & metrics.variant == variant_names(item);
        row = struct();
        row.preset = char(preset_names(setting));
        row.variant = char(variant_names(item));
        row.count = nnz(selected);
        row.median_iou = median(metrics.iou(selected));
        row.minimum_iou = min(metrics.iou(selected));
        row.median_boundary_distance_px = median(metrics.boundary_distance_px(selected));
        row.median_abs_area_error_fraction = median(abs(metrics.signed_area_error_fraction(selected)));
        row.median_centroid_error_px = median(metrics.centroid_error_px(selected));
        variant_summary(end + 1) = row; %#ok<AGROW>
    end
end

photometric_stability = struct( ...
    'shape_index', {}, 'iou_range_across_photometry', {}, ...
    'boundary_distance_range_px', {}, 'area_error_range_fraction', {}, ...
    'centroid_error_max_px', {});
primary = metrics(metrics.preset == "primary", :);
for shape = 0:7
    selected = primary.shape_index == shape;
    row = struct();
    row.shape_index = shape;
    row.iou_range_across_photometry = max(primary.iou(selected)) - min(primary.iou(selected));
    row.boundary_distance_range_px = max(primary.boundary_distance_px(selected)) - min(primary.boundary_distance_px(selected));
    row.area_error_range_fraction = max(primary.signed_area_error_fraction(selected)) - min(primary.signed_area_error_fraction(selected));
    row.centroid_error_max_px = max(primary.centroid_error_px(selected));
    photometric_stability(end + 1) = row; %#ok<AGROW>
end

smoothness_stability = struct( ...
    'image_id', {}, 'iou_range_across_smoothness', {}, ...
    'boundary_distance_range_px', {}, 'area_error_range_fraction', {});
for index = 1:height(manifest)
    selected = metrics.image_id == manifest.image_id(index);
    row = struct();
    row.image_id = char(manifest.image_id(index));
    row.iou_range_across_smoothness = max(metrics.iou(selected)) - min(metrics.iou(selected));
    row.boundary_distance_range_px = max(metrics.boundary_distance_px(selected)) - min(metrics.boundary_distance_px(selected));
    row.area_error_range_fraction = max(metrics.signed_area_error_fraction(selected)) - min(metrics.signed_area_error_fraction(selected));
    smoothness_stability(end + 1) = row; %#ok<AGROW>
end

payload = struct();
payload.status = 'complete';
payload.method = 'MATLAB activecontour Chan-Vese';
payload.preprocessing = 'mat2gray plus 1st-to-99th-percentile contrast normalization';
payload.initialization = 'fixed centered disk independent of truth and photometric variant';
payload.iterations = iterations;
payload.image_count = height(manifest);
payload.measurement_count = height(metrics);
payload.smoothness_presets = smoothness;
payload.primary_overall = struct( ...
    'median_iou', median(primary.iou), ...
    'minimum_iou', min(primary.iou), ...
    'fraction_iou_below_0_97', mean(primary.iou < 0.97), ...
    'median_boundary_distance_px', median(primary.boundary_distance_px), ...
    'maximum_boundary_distance_px', max(primary.boundary_distance_px), ...
    'median_abs_area_error_fraction', median(abs(primary.signed_area_error_fraction)), ...
    'maximum_centroid_error_px', max(primary.centroid_error_px));
payload.variant_summary = variant_summary;
payload.photometric_stability = photometric_stability;
payload.smoothness_stability = smoothness_stability;
payload.photometric_iou_range = numeric_summary([photometric_stability.iou_range_across_photometry]);
payload.photometric_boundary_range_px = numeric_summary([photometric_stability.boundary_distance_range_px]);
payload.smoothness_iou_range = numeric_summary([smoothness_stability.iou_range_across_smoothness]);
payload.smoothness_boundary_range_px = numeric_summary([smoothness_stability.boundary_distance_range_px]);
payload.interpretation_boundary = 'All images in a shape group have identical geometry. Any within-shape variation is measurement sensitivity, not a reconstruction difference.';

text = jsonencode(payload, 'PrettyPrint', true);
fid = fopen(output_json, 'w', 'n', 'UTF-8');
if fid < 0
    error('Could not open %s', output_json);
end
cleanup = onCleanup(@() fclose(fid));
fwrite(fid, text, 'char');
fprintf('ACM audit complete: %d images, %d measurements\n', height(manifest), height(metrics));


function distance = symmetric_boundary_distance(first, second)
first_boundary = bwperim(first, 8);
second_boundary = bwperim(second, 8);
if ~any(first_boundary, 'all') || ~any(second_boundary, 'all')
    distance = max(size(first));
    return;
end
to_second = bwdist(second_boundary);
to_first = bwdist(first_boundary);
distance = 0.5 * (mean(to_second(first_boundary)) + mean(to_first(second_boundary)));
end


function value = safe_centroid(mask)
properties = regionprops(mask, 'Area', 'Centroid');
if isempty(properties)
    value = [0, 0];
    return;
end
[~, index] = max([properties.Area]);
value = properties(index).Centroid;
end


function output = numeric_summary(values)
values = double(values(:));
output = struct( ...
    'count', numel(values), ...
    'mean', mean(values), ...
    'median', median(values), ...
    'p90', prctile(values, 90), ...
    'p95', prctile(values, 95), ...
    'maximum', max(values));
end
