function run_contour_check()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
root=fullfile(PROJECT_ROOT, 'Experiments/R128_SourceOnlyFullTraining');out=fullfile(root,'results','full_contour');
assert(isfile(fullfile(out,'plan.json')));assert(~isfile(fullfile(out,'measurements.csv')));
input=load(fullfile(out,'inputs.mat'));
old=load(fullfile(PROJECT_ROOT, 'Experiments/R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat'));
alt=load(fullfile(PROJECT_ROOT, 'Experiments/R121_BoundaryAnchorFactorial/results/pitch_matched_reference.mat'));
names={'Raw','R128_PNG','R128_float'};reference_names={'historical','global_pitch_matched'};preset_names={'primary','less_smooth','more_smooth'};
iterations=[200 150 250];smoothness=[1.0 0.5 2.0];exps=[13 14 15];
refs=cat(4,old.truth_masks,alt.truth_masks);sem_cells=cat(4,old.truth_cells,alt.truth_cells);
masks=false(104,104,36,3,3,3);cells=zeros(104,104,36,3,3);raw_parity=zeros(36,3);
shifts=zeros(36,3,2,2);rows=cell(1944,19);k=0;
for preset=1:3
 for e=1:3
  images={input.raw_images(:,:,e),input.candidate_u8_images(:,:,e),input.candidate_float_images(:,:,e)};
  for gy=1:6
   for gx=1:6
    id=double(old.global_index(gy,gx));center=old.opt_centers((gy-1)*6+gx,:);
    for m=1:3
     valid=true;problem="";mask=false(104);touch=0;
     try
      im=extract_padded_cell(images{m},center,52);
      mask=segment_acm(im,40,iterations(preset),smoothness(preset),45);
      masks(:,:,id,e,m,preset)=mask;
      if preset==1,cells(:,:,id,e,m)=im;end
      [xx,yy]=meshgrid(1:104,1:104);touch=nnz(mask & ((xx-52.5).^2+(yy-52.5).^2>=44^2));
      if m==1 && preset==1,raw_parity(id,e)=nnz(mask~=old.raw_masks(:,:,id,exps(e)-12));end
     catch ME
      valid=false;problem=string(ME.message);
     end
     for ref=1:2
      k=k+1;vals=nan(1,8);dx=nan;dy=nan;
      if valid
       truth=refs(:,:,id,ref);tp=regionprops(truth,'Centroid');rp=regionprops(old.raw_masks(:,:,id,exps(e)-12),'Centroid');
       shift=round(tp(1).Centroid-rp(1).Centroid);dx=shift(1);dy=shift(2);shifts(id,e,ref,:)=[dx dy];
       aligned=shift_binary(mask,dx,dy);met=contour_metrics(truth,aligned,old.opt_pitch);
       vals=[met.mean_distance_px,met.mean_distance_pitch_pct,met.hd95_px,met.iou,met.dice,met.area_error_pct,met.perimeter_error_pct,met.circularity_abs_error];
      end
      rows(k,:)={string(preset_names{preset}),string(reference_names{ref}),exps(e),id,gy,gx,string(names{m}),valid,problem,vals(1),vals(2),vals(3),vals(4),vals(5),vals(6),vals(7),vals(8),dx,dy};
     end
     if touch>0,fprintf('Support contact %d: preset %d exposure %d pillar %d method %d\n',touch,preset,exps(e),id,m);end
    end
   end
  end
  fprintf('Preset %s exposure %d complete\n',preset_names{preset},exps(e));
 end
end
assert(k==1944);
table_out=cell2table(rows,'VariableNames',{'preset','reference','exposure','pillar','grid_row','grid_col','method','valid','failure','mean_boundary_px','mean_boundary_pitch_pct','hd95_px','iou','dice','area_error_pct','perimeter_error_pct','circularity_error','Raw_shift_x','Raw_shift_y'});
writetable(table_out,fullfile(out,'measurements.csv'));
truth_masks=refs;opt_pitch=old.opt_pitch;global_index=old.global_index;opt_centers=old.opt_centers;
save(fullfile(out,'masks.mat'),'masks','cells','truth_masks','sem_cells','shifts','raw_parity','opt_pitch','global_index','opt_centers','exps','names','preset_names','reference_names','-v7');
summary=struct('extraction_complete',true,'metric_rows',k,'Raw_primary_mismatched_pixels',sum(raw_parity,'all'),'Raw_primary_exact',all(raw_parity==0,'all'),'matlab_version',version,'image_processing_toolbox',ver('images'));
fid=fopen(fullfile(out,'extraction_summary.json'),'w');fprintf(fid,'%s',jsonencode(summary,PrettyPrint=true));fclose(fid);
assert(all(raw_parity==0,'all'),'Raw primary mask parity failed; old expected evidence must not be rebaselined');
fprintf('Complete: %d metric rows; Raw primary masks reproduce exactly.\n',k);
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
