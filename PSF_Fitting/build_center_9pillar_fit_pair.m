function pair = build_center_9pillar_fit_pair(image_path, detection, cd_nm, varargin)
%BUILD_CENTER_9PILLAR_FIT_PAIR Build a nine-pillar-only captured/GT pair.
parser = inputParser;
parser.addParameter('CanvasSize', 301, @(x) isnumeric(x) && isscalar(x) && mod(x, 2) == 1 && x >= 201);
parser.addParameter('CameraPixelUm', 3.45, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('PatchHalfPx', [], @(x) isempty(x) || (isnumeric(x) && isscalar(x) && x >= 8 && x == round(x)));
parser.addParameter('LossRadiusPx', [], @(x) isempty(x) || (isnumeric(x) && isscalar(x) && x >= 6 && x == round(x)));
parser.parse(varargin{:});
opts = parser.Results;

image_data = im2double(im2gray(imread(image_path)));
canvas_size = double(opts.CanvasSize);
axis_centers = round(linspace(70, canvas_size - 69, 3));
[tile_x, tile_y] = meshgrid(axis_centers, axis_centers);
tile_centers = [tile_x(:), tile_y(:)];
tile_centers = reshape(permute(reshape(tile_centers, 3, 3, 2), [2, 1, 3]), 9, 2);

fit_input = zeros(canvas_size, canvas_size, 'double');
loss_mask = false(canvas_size, canvas_size);
pitch_px = detection.pitch_px;
half_patch = max(8, floor(0.44 * pitch_px));
mask_radius = max(6, half_patch - 2);
if ~isempty(opts.PatchHalfPx), half_patch = double(opts.PatchHalfPx); end
if ~isempty(opts.LossRadiusPx), mask_radius = double(opts.LossRadiusPx); end
if mask_radius >= half_patch
    error('center9:InvalidLossRadius', 'Loss radius must stay inside the extracted patch.');
end
[canvas_x, canvas_y] = meshgrid(1:canvas_size, 1:canvas_size);

global_low = prctile(image_data(:), 2);
global_high = prctile(image_data(:), 98);
global_contrast = max(global_high - global_low, eps);

for pillar_idx = 1:9
    source_center = detection.selected_centers(pillar_idx, :);
    offsets = -half_patch:half_patch;
    [offset_x, offset_y] = meshgrid(offsets, offsets);
    query_x = source_center(1) + offset_x;
    query_y = source_center(2) + offset_y;

    radius_map = hypot(offset_x, offset_y);
    annulus = radius_map >= 0.40 * pitch_px & radius_map <= 0.48 * pitch_px;
    source_patch = interp2(image_data, query_x, query_y, 'linear', NaN);
    local_background = median(source_patch(annulus & isfinite(source_patch)));
    source_patch(~isfinite(source_patch)) = local_background;

    if strcmp(detection.polarity, 'bright')
        normalized_patch = (source_patch - local_background) / global_contrast;
    else
        normalized_patch = (local_background - source_patch) / global_contrast;
    end
    normalized_patch = min(max(normalized_patch, 0), 1);

    target_center = tile_centers(pillar_idx, :);
    target_rows = (target_center(2) - half_patch):(target_center(2) + half_patch);
    target_cols = (target_center(1) - half_patch):(target_center(1) + half_patch);
    fit_input(target_rows, target_cols) = normalized_patch;
    loss_mask = loss_mask | hypot(canvas_x - target_center(1), canvas_y - target_center(2)) <= mask_radius;
end

[gt, gt_metadata] = render_center_9pillar_gt([canvas_size, canvas_size], tile_centers, ...
    cd_nm, detection.magnification, opts.CameraPixelUm, 8);

if isfield(detection, 'pillar_junction_corner')
    sample_center_index = corner_row_major_index(detection.pillar_junction_corner);
    gt_metadata.sample_center_cd_nm = reshape(cd_nm.', [], 1);
    gt_metadata.sample_center_cd_nm = gt_metadata.sample_center_cd_nm(sample_center_index);
    gt_metadata.sample_center_xy = tile_centers(sample_center_index, :);
    gt_metadata.sample_center_index = sample_center_index;
    gt_metadata.orientation = sprintf('image rows top-to-bottom, columns left-to-right; sample center is %s', ...
        detection.pillar_junction_corner);
end

pair = struct();
pair.fit_input = fit_input;
pair.gt = gt;
pair.loss_mask = loss_mask;
pair.metadata = gt_metadata;
pair.metadata.tile_centers = tile_centers;
pair.metadata.patch_size = 2 * half_patch + 1;
pair.metadata.mask_radius = mask_radius;
pair.metadata.source_centers = detection.selected_centers;
pair.metadata.source_radii = detection.selected_radii;
pair.metadata.global_normalization_low = global_low;
pair.metadata.global_normalization_high = global_high;
pair.metadata.source_polarity = detection.polarity;
end

function index = corner_row_major_index(corner_name)
switch string(corner_name)
    case "top-left"
        index = 1;
    case "top-right"
        index = 3;
    case "bottom-left"
        index = 7;
    case "bottom-right"
        index = 9;
    otherwise
        error('center9:UnsupportedCorner', 'Unsupported corner: %s', corner_name);
end
end
