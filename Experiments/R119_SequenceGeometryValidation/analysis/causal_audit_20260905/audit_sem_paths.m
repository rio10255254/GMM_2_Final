function audit_sem_paths()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
root=fullfile(PROJECT_ROOT, 'Experiments/R119_SequenceGeometryValidation');
out=fullfile(root,'analysis','causal_audit_20260905','sem_paths');
saved=load(fullfile(root,'results','formal_sem','results','masks','acm_primary_masks.mat'));
names={'Raw','base','no_detail','no_width','no_shift','attenuation'};
method=strings(216,1);pillar=zeros(216,1);boundary=zeros(216,1);signed_area=zeros(216,1);parity=zeros(216,1);
k=0;
for m=1:numel(names)
    image=imread(fullfile(out,[names{m} '.png']));
    for r=1:6
        for c=1:6
            k=k+1; id=saved.global_index(r,c); center=saved.opt_centers((r-1)*6+c,:);
            cell=extract_padded_cell(image,center,52);
            mask=segment_acm(cell,40,200,1.0,45);
            truth=saved.truth_masks(:,:,id);
            [aligned,~]=align_mask_translation(mask,truth);
            metrics=contour_metrics(truth,aligned,saved.opt_pitch);
            method(k)=string(names{m});pillar(k)=id;boundary(k)=metrics.mean_distance_pitch_pct;
            signed_area(k)=100*(nnz(mask)-nnz(truth))/nnz(truth);
            if m==1
                parity(k)=nnz(mask~=saved.raw_masks(:,:,id,1));
            elseif m==2
                parity(k)=nnz(mask~=saved.recon_masks(:,:,id,1));
            else
                parity(k)=NaN;
            end
        end
    end
end
t=table(method,pillar,boundary,signed_area,parity);
writetable(t,fullfile(out,'acm_paths_amplitude.csv'));
assert(all(parity(1:72)==0),'Raw/base mask protocol reproduction failed');
disp(groupsummary(t,'method','median',{'boundary','signed_area'}));
end

function centers = sort_grid_centers(centers, rows, cols)
[~, y_order] = sort(centers(:, 2));
centers = centers(y_order, :);
sorted = zeros(size(centers));
for r = 1:rows
    block = centers((r-1)*cols+1:r*cols, :);
    [~, x_order] = sort(block(:, 1));
    sorted((r-1)*cols+1:r*cols, :) = block(x_order, :);
end
centers = sorted;
end


function pitch = estimate_grid_pitch(centers, rows, cols)
x_grid = reshape(centers(:, 1), cols, rows).';
y_grid = reshape(centers(:, 2), cols, rows).';
dx = diff(x_grid, 1, 2);
dy = diff(y_grid, 1, 1);
pitch = median([dx(:); dy(:)]);
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
% Prevent a neighboring pillar that is only partially visible at the cell
% edge from joining the target component. This is an ROI guard, not a shape
% fit: the allowed radius is materially larger than every detected pillar.
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


function [cleaned, was_cleaned] = remove_sem_edge_artifacts(mask)
% Some SEM tiles show a sliver from the neighbouring acquisition at a cell
% edge. Trigger only when the ACM mask reaches the outer 12 pixels, then
% remove the affected 15-pixel strip and retain the centre component.
trigger_width = 12;
trim_width = 15;
cleaned = mask;
was_cleaned = false;
if any(cleaned(1:trigger_width, :), 'all')
    cleaned(1:trim_width, :) = false; was_cleaned = true;
end
if any(cleaned(end-trigger_width+1:end, :), 'all')
    cleaned(end-trim_width+1:end, :) = false; was_cleaned = true;
end
if any(cleaned(:, 1:trigger_width), 'all')
    cleaned(:, 1:trim_width) = false; was_cleaned = true;
end
if any(cleaned(:, end-trigger_width+1:end), 'all')
    cleaned(:, end-trim_width+1:end) = false; was_cleaned = true;
end
if was_cleaned
    cleaned = select_center_component(cleaned);
    cleaned = imfill(cleaned, 'holes');
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
% MATLAB's Circularity property includes the digital-grid correction needed
% to keep a pixelated boundary within the physical 0-to-1 range.
metrics.truth_circularity = truth_props(1).Circularity;
metrics.pred_circularity = pred_props(1).Circularity;
metrics.circularity_abs_error = abs(metrics.pred_circularity - metrics.truth_circularity);
end
