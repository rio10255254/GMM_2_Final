function [selected_centers, info] = select_pillar_3x3_at_corner(centers, pitch_px, corner_name, varargin)
%SELECT_PILLAR_3X3_AT_CORNER Select a complete 3x3 lattice at one image corner.
parser = inputParser;
parser.addParameter('TolerancePx', 0.16 * pitch_px, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.parse(varargin{:});
tolerance_px = double(parser.Results.TolerancePx);
corner_name = string(corner_name);

validateattributes(centers, {'numeric'}, {'2d', 'ncols', 2, 'finite'});
validateattributes(pitch_px, {'numeric'}, {'scalar', 'positive', 'finite'});
if ~ismember(corner_name, ["top-left", "top-right", "bottom-left", "bottom-right"])
    error('center9:UnsupportedCorner', 'Unsupported corner: %s', corner_name);
end

[x_sign, y_sign] = corner_directions(corner_name);
[col_offsets, row_offsets] = meshgrid(0:2, 0:2);
offsets = [x_sign * col_offsets(:), y_sign * row_offsets(:)] * pitch_px;
target_corner = component_corner(centers, corner_name);

best_score = Inf;
best_selected = [];
best_residuals = [];
best_anchor = [];
for candidate_idx = 1:size(centers, 1)
    anchor = centers(candidate_idx, :);
    targets = anchor + offsets;
    [indices, residuals] = nearest_unique(centers, targets);
    if isempty(indices) || any(residuals > tolerance_px)
        continue
    end
    score = norm(anchor - target_corner) + 5 * mean(residuals);
    if score < best_score
        best_score = score;
        best_selected = centers(indices, :);
        best_residuals = residuals;
        best_anchor = anchor;
    end
end

if isempty(best_selected)
    error('center9:CornerGridNotFound', 'Could not find a complete 3x3 grid at %s.', corner_name);
end

selected_centers = sort_image_row_major(best_selected);
info = struct();
info.corner = corner_name;
info.anchor_xy = best_anchor;
info.mean_grid_residual_px = mean(best_residuals);
info.max_grid_residual_px = max(best_residuals);
info.pitch_px = pitch_px;
end

function [x_sign, y_sign] = corner_directions(corner_name)
if contains(corner_name, "left"), x_sign = 1; else, x_sign = -1; end
if contains(corner_name, "top"), y_sign = 1; else, y_sign = -1; end
end

function corner = component_corner(centers, corner_name)
if contains(corner_name, "left"), x = min(centers(:, 1)); else, x = max(centers(:, 1)); end
if contains(corner_name, "top"), y = min(centers(:, 2)); else, y = max(centers(:, 2)); end
corner = [x, y];
end

function sorted = sort_image_row_major(centers)
[~, y_order] = sort(centers(:, 2));
centers = centers(y_order, :);
sorted = zeros(size(centers));
for row = 1:3
    indices = (row - 1) * 3 + (1:3);
    row_centers = centers(indices, :);
    [~, x_order] = sort(row_centers(:, 1));
    sorted(indices, :) = row_centers(x_order, :);
end
end

function [indices, residuals] = nearest_unique(centers, targets)
indices = zeros(size(targets, 1), 1);
residuals = zeros(size(targets, 1), 1);
for idx = 1:size(targets, 1)
    distances = vecnorm(centers - targets(idx, :), 2, 2);
    [residuals(idx), indices(idx)] = min(distances);
end
if numel(unique(indices)) ~= numel(indices)
    indices = [];
    residuals = [];
end
end
