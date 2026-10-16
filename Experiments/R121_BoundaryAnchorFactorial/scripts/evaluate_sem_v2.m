function evaluate_sem_v2()
root='D:/GMM_2_Final/Experiments/R121_BoundaryAnchorFactorial';out=fullfile(root,'results','sem');
assert(isfile(fullfile(out,'render_manifest.json')));assert(~isfile(fullfile(out,'measurements.csv')));
old=load('D:/GMM_2_Final/Experiments/R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat');
alt=load(fullfile(root,'results/pitch_matched_reference.mat'));
matrix=jsondecode(fileread(fullfile(root,'results/matrix_finished_v2.json'))); method_names=cell(1,9);method_names{1}='Raw';for j=1:8,method_names{j+1}=matrix.runs(j).run_id;end
refs={'historical','pitch_matched'};n=9*12*36*2;method=strings(n,1);reference=strings(n,1);exposure=zeros(n,1);pillar=zeros(n,1);valid=false(n,1);failure=strings(n,1);
boundary=nan(n,1);signed_area=nan(n,1);hd95=nan(n,1);k=0;raw_parity=zeros(36,12);masks=false(104,104,36,12,9);
for m=1:9
 for e=1:12
  exp=e+12;
  if m==1,source=sprintf('D:/GMM_2_Final/Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/%d.bmp',exp);
  else,source=fullfile(out,'recon',method_names{m},[num2str(exp) '.png']);end
  image=imread(source);
  for r=1:6
   for c=1:6
    id=double(old.global_index(r,c));center=old.opt_centers((r-1)*6+c,:);
    mask=[];problem="";
    try
     cell=extract_padded_cell(image,center,52);mask=segment_acm(cell,40,200,1.,45);masks(:,:,id,e,m)=mask;
     if m==1,raw_parity(id,e)=nnz(mask~=old.raw_masks(:,:,id,e));end
    catch ME
     problem=string(ME.message);
    end
    for f=1:2
     k=k+1;method(k)=string(method_names{m});reference(k)=string(refs{f});exposure(k)=exp;pillar(k)=id;
     if strlength(problem)>0,failure(k)=problem;continue;end
     try
      if f==1,truth=old.truth_masks(:,:,id);else,truth=alt.truth_masks(:,:,id);end
      aligned=align_mask_translation(mask,truth);metric=contour_metrics(truth,aligned,old.opt_pitch);
      boundary(k)=metric.mean_distance_pitch_pct;hd95(k)=metric.hd95_pitch_pct;signed_area(k)=100*(nnz(mask)-nnz(truth))/nnz(truth);valid(k)=true;
     catch ME
      failure(k)=string(ME.message);
     end
    end
   end
  end
  fprintf('%s exposure %d done\n',method_names{m},exp);
 end
end
assert(k==n);t=table(method,reference,exposure,pillar,valid,failure,boundary,signed_area,hd95);writetable(t,fullfile(out,'measurements.csv'));
save(fullfile(out,'masks.mat'),'masks','method_names','refs','raw_parity','-v7');
assert(all(raw_parity==0,'all'),'Raw protocol changed');
fprintf('Measurements %d; failures %d\n',n,nnz(~valid));
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
