function result = detect_pillar_via_junction_in_image(image_path, magnification, varargin)
%DETECT_PILLAR_VIA_JUNCTION_IN_IMAGE Classify HS-100MG pillar/via regions.
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
config = orientation_config(magnification, image_w, image_h);

pillar_detection = detect_grid(image_data, config.pillar_roi, pitch_px, 'dark', config.pillar_corner);
via_detection = detect_grid(image_data, config.via_roi, pitch_px, 'bright', config.via_corner);

[pillar_inside, pillar_background] = region_intensity(image_data, pillar_detection.selected_centers, pitch_px);
[via_inside, via_background] = region_intensity(image_data, via_detection.selected_centers, pitch_px);
if pillar_inside >= pillar_background
    error('center9:PillarPolarityMismatch', 'Pillar candidates are not dark circles on a bright background.');
end
if via_inside <= via_background
    error('center9:ViaPolarityMismatch', 'Via candidates are not bright circles on a dark background.');
end

result = struct();
result.image_path = string(image_path);
result.image_size = [image_h, image_w];
result.magnification = magnification;
result.object_pixel_um = opts.CameraPixelUm / magnification;
result.pitch_px = pitch_px;
result.pillar_polarity = "dark";
result.via_polarity = "bright";
result.pillar_junction_corner = config.pillar_corner;
result.via_junction_corner = config.via_corner;
result.pillar_centers = pillar_detection.selected_centers;
result.pillar_radii = pillar_detection.selected_radii;
result.pillar_metrics = pillar_detection.selected_metrics;
result.pillar_grid_info = pillar_detection.grid_info;
result.pillar_anchor_xy = pillar_detection.grid_info.anchor_xy;
result.via_centers = via_detection.selected_centers;
result.via_radii = via_detection.selected_radii;
result.via_metrics = via_detection.selected_metrics;
result.via_grid_info = via_detection.grid_info;
result.via_anchor_xy = via_detection.grid_info.anchor_xy;
result.junction_xy = mean([result.pillar_anchor_xy; result.via_anchor_xy], 1);
result.pillar_mean_inside = pillar_inside;
result.pillar_mean_background = pillar_background;
result.via_mean_inside = via_inside;
result.via_mean_background = via_background;
result.pillar_roi_xyxy = config.pillar_roi;
result.via_roi_xyxy = config.via_roi;
end

function config = orientation_config(magnification, image_w, image_h)
if magnification <= 25
    config = struct( ...
        'pillar_roi', normalized_roi([0.76, 0.43, 1.00, 1.00], image_w, image_h), ...
        'via_roi', normalized_roi([0.15, 0.00, 0.96, 0.58], image_w, image_h), ...
        'pillar_corner', "top-left", ...
        'via_corner', "bottom-right");
else
    config = struct( ...
        'pillar_roi', normalized_roi([0.34, 0.00, 1.00, 0.56], image_w, image_h), ...
        'via_roi', normalized_roi([0.00, 0.44, 0.50, 1.00], image_w, image_h), ...
        'pillar_corner', "bottom-left", ...
        'via_corner', "top-right");
end
end

function roi = normalized_roi(fractions, image_w, image_h)
roi = [max(1, floor(fractions(1) * image_w)), max(1, floor(fractions(2) * image_h)), ...
    min(image_w, ceil(fractions(3) * image_w)), min(image_h, ceil(fractions(4) * image_h))];
end

function detection = detect_grid(image_data, roi_xyxy, pitch_px, polarity, corner_name)
x1 = roi_xyxy(1); y1 = roi_xyxy(2); x2 = roi_xyxy(3); y2 = roi_xyxy(4);
roi = image_data(y1:y2, x1:x2);
radius_range = [max(4, floor(0.16 * pitch_px)), ceil(0.45 * pitch_px)];
[centers, radii, metrics] = imfindcircles(roi, radius_range, ...
    'ObjectPolarity', polarity, 'Sensitivity', 0.94);
centers = centers + [x1 - 1, y1 - 1];
if size(centers, 1) < 9
    error('center9:TooFewCandidates', 'Only %d %s-circle candidates were detected.', size(centers, 1), polarity);
end

[selected, grid_info] = select_pillar_3x3_at_corner(centers, pitch_px, corner_name, ...
    'TolerancePx', 0.18 * pitch_px);
selected_indices = zeros(9, 1);
for idx = 1:9
    [~, selected_indices(idx)] = min(vecnorm(centers - selected(idx, :), 2, 2));
end
detection = struct('selected_centers', selected, 'selected_radii', radii(selected_indices), ...
    'selected_metrics', metrics(selected_indices), 'grid_info', grid_info);
end

function [inside_mean, background_mean] = region_intensity(image_data, centers, pitch_px)
image_double = im2double(image_data);
[x_grid, y_grid] = meshgrid(1:size(image_double, 2), 1:size(image_double, 1));
inside_values = [];
background_values = [];
for idx = 1:size(centers, 1)
    radius = hypot(x_grid - centers(idx, 1), y_grid - centers(idx, 2));
    inside_values = [inside_values; image_double(radius <= 0.18 * pitch_px)]; %#ok<AGROW>
    background_values = [background_values; image_double(radius >= 0.38 * pitch_px & radius <= 0.48 * pitch_px)]; %#ok<AGROW>
end
inside_mean = mean(inside_values);
background_mean = mean(background_values);
end
