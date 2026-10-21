function [selected_centers, info] = select_center_9pillar_grid(centers, pitch_px, image_center_xy, varargin)
%SELECT_CENTER_9PILLAR_GRID Select the bottom-left 3x3 block of a circle lattice.
parser = inputParser;
parser.addParameter('TolerancePx', 0.20 * pitch_px, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.parse(varargin{:});
tolerance_px = double(parser.Results.TolerancePx);

validateattributes(centers, {'numeric'}, {'2d', 'ncols', 2, 'finite'});
validateattributes(pitch_px, {'numeric'}, {'scalar', 'positive', 'finite'});
validateattributes(image_center_xy, {'numeric'}, {'vector', 'numel', 2, 'finite'});

offsets = [
    0, -2; 1, -2; 2, -2
    0, -1; 1, -1; 2, -1
    0,  0; 1,  0; 2,  0] * pitch_px;

best_score = Inf;
best_selected = [];
best_residuals = [];
best_corner = [];

for candidate_idx = 1:size(centers, 1)
    corner = centers(candidate_idx, :);
    targets = corner + offsets;
    [nearest_idx, residuals] = nearest_unique_centers(centers, targets);
    if isempty(nearest_idx) || any(residuals > tolerance_px)
        continue
    end

    corner_distance = norm(corner - reshape(image_center_xy, 1, 2));
    score = corner_distance + 5 * mean(residuals);
    if score < best_score
        best_score = score;
        best_selected = centers(nearest_idx, :);
        best_residuals = residuals;
        best_corner = corner;
    end
end

if isempty(best_selected)
    error('center9:GridNotFound', 'Could not find a complete bottom-left 3x3 pillar grid.');
end

selected_centers = best_selected;
info = struct();
info.sample_center_pillar_xy = selected_centers(7, :);
info.detected_corner_xy = best_corner;
info.mean_grid_residual_px = mean(best_residuals);
info.max_grid_residual_px = max(best_residuals);
info.pitch_px = pitch_px;
end

function [nearest_idx, residuals] = nearest_unique_centers(centers, targets)
nearest_idx = zeros(size(targets, 1), 1);
residuals = zeros(size(targets, 1), 1);
for target_idx = 1:size(targets, 1)
    distances = vecnorm(centers - targets(target_idx, :), 2, 2);
    [residuals(target_idx), nearest_idx(target_idx)] = min(distances);
end
if numel(unique(nearest_idx)) ~= numel(nearest_idx)
    nearest_idx = [];
    residuals = [];
end
end
