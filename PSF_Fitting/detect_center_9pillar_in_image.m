function result = detect_center_9pillar_in_image(image_path, magnification, varargin)
%DETECT_CENTER_9PILLAR_IN_IMAGE Find the 3x3 pillar block nearest the sample center.
parser = inputParser;
parser.addParameter('CameraPixelUm', 3.45, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('PitchUm', 5.0, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.parse(varargin{:});
opts = parser.Results;

if ~isfile(image_path)
    error('center9:ImageNotFound', 'Image not found: %s', image_path);
end
image_data = im2gray(imread(image_path));
[image_h, image_w] = size(image_data);
pitch_px = opts.PitchUm / (opts.CameraPixelUm / magnification);

if magnification <= 25
    radius_range = [max(4, 0.18 * pitch_px), 0.48 * pitch_px];
    polarity = 'bright';
    sensitivity = 0.90;
    minimum_metric = 0.20;
else
    radius_range = [0.16 * pitch_px, 0.42 * pitch_px];
    polarity = 'dark';
    sensitivity = 0.91;
    minimum_metric = 0.50;
end
radius_range = [floor(radius_range(1)), ceil(radius_range(2))];

x_limits = round([0.08, 0.68] * image_w);
y_limits = round([0.18, 0.58] * image_h);
x_limits(1) = max(1, x_limits(1));
y_limits(1) = max(1, y_limits(1));
x_limits(2) = min(image_w, x_limits(2));
y_limits(2) = min(image_h, y_limits(2));
roi = image_data(y_limits(1):y_limits(2), x_limits(1):x_limits(2));

[centers_roi, radii, metrics] = imfindcircles(roi, radius_range, ...
    'ObjectPolarity', polarity, 'Sensitivity', sensitivity);
keep = metrics >= minimum_metric;
centers_roi = centers_roi(keep, :);
radii = radii(keep);
metrics = metrics(keep);
centers = centers_roi + [x_limits(1) - 1, y_limits(1) - 1];

image_center_xy = [(image_w + 1) / 2, (image_h + 1) / 2];
upper_sample_half = centers(:, 2) <= image_center_xy(2) - 0.40 * pitch_px;
centers = centers(upper_sample_half, :);
radii = radii(upper_sample_half);
metrics = metrics(upper_sample_half);

if size(centers, 1) < 9
    error('center9:TooFewPillars', 'Only %d reliable pillar candidates were found in %s.', size(centers, 1), image_path);
end

[selected_centers, grid_info] = select_center_9pillar_grid(centers, pitch_px, image_center_xy, ...
    'TolerancePx', 0.14 * pitch_px);

selected_indices = zeros(9, 1);
for pillar_idx = 1:9
    [~, selected_indices(pillar_idx)] = min(vecnorm(centers - selected_centers(pillar_idx, :), 2, 2));
end

result = struct();
result.image_path = string(image_path);
result.image_size = [image_h, image_w];
result.magnification = magnification;
result.object_pixel_um = opts.CameraPixelUm / magnification;
result.pitch_px = pitch_px;
result.polarity = polarity;
result.selected_centers = selected_centers;
result.selected_radii = radii(selected_indices);
result.selected_metrics = metrics(selected_indices);
result.grid_info = grid_info;
result.roi_limits_xyxy = [x_limits(1), y_limits(1), x_limits(2), y_limits(2)];
result.all_centers = centers;
result.all_radii = radii;
result.all_metrics = metrics;
end
