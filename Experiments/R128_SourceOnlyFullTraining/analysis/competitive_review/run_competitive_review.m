function run_competitive_review()
root='D:/GMM_2_Final/Experiments/R128_SourceOnlyFullTraining';
out=fullfile(root,'results','competitive_review');
assert(isfile(fullfile(out,'plan.json')) && isfile(fullfile(out,'preparation.json')));
assert(~isfile(fullfile(out,'measurements.csv')));
d=load(fullfile(out,'inputs.mat'));
methods={'Raw','R61v16','R109_E48','R119_E42','R128_P_s1285002'};
refs={'historical','global_pitch_matched'};rows=cell(1080,19);k=0;
for r=1:2
 for e=1:3
  for i=1:36
   truth=d.truth_masks(:,:,i,r);dx=d.shifts(i,e,r,1);dy=d.shifts(i,e,r,2);
   for m=1:5
    mask=d.masks(:,:,i,e,m);components=bwconncomp(mask,8);assert(components.NumObjects==1);
    aligned=shift_binary(mask,dx,dy);assert(nnz(mask)==nnz(aligned),'Alignment clipped mask');
    met=contour_metrics(truth,aligned,d.opt_pitch);
    [gr,gc]=find(d.global_index==i);interior=gr>=2 && gr<=5 && gc>=2 && gc<=5;
    k=k+1;
    rows(k,:)={string(refs{r}),e+12,i,string(methods{m}),interior,met.mean_distance_px,met.mean_distance_pitch_pct,met.hd95_px,met.iou,met.dice,met.area_error_pct,met.perimeter_error_pct,met.circularity_abs_error,met.truth_circularity,met.pred_circularity,dx,dy,gr,gc};
   end
  end
  fprintf('%s exposure %d complete\n',refs{r},e+12);
 end
end
assert(k==1080);
t=cell2table(rows,'VariableNames',{'reference','exposure','pillar','method','fully_neural_interior','mean_boundary_px','mean_boundary_pitch_pct','hd95_px','iou','dice','area_error_pct','perimeter_error_pct','circularity_error','SEM_circularity','predicted_circularity','Raw_shift_x','Raw_shift_y','grid_row','grid_col'});
writetable(t,fullfile(out,'measurements.csv'));
info=struct('rows',k,'matlab_version',version,'all_masks_connected',true,'no_alignment_clipping',true);
fid=fopen(fullfile(out,'measurement_run.json'),'w');fprintf(fid,'%s',jsonencode(info,PrettyPrint=true));fclose(fid);
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
