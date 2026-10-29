function prepare_normal_sem_cells()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
root=fullfile(PROJECT_ROOT, 'Experiments/R128_SourceOnlyFullTraining');
out=fullfile(root,'results/thesis_v34_review_20260912/normal_sem_fine_v2');
assert(~isfolder(out));mkdir(out);
d=load(fullfile(root,'results/full_contour/masks.mat'),'cells');
old=load(fullfile(PROJECT_ROOT, 'Experiments/R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat'),'raw_cells');
raw_cells=zeros(104,104,36,3,'uint8');r128_cells=raw_cells;
for e=1:3
 for i=1:36
  % Exact historical R69/R70 cell representation; no new contrast tuning.
  raw_cells(:,:,i,e)=im2uint8(mat2gray(d.cells(:,:,i,e,1)));
  r128_cells(:,:,i,e)=im2uint8(mat2gray(d.cells(:,:,i,e,2)));
 end
end
assert(isequal(raw_cells,old.raw_cells(:,:,:,1:3)),'Raw cell parity must match original thesis input');
save(fullfile(out,'input_cells.mat'),'raw_cells','r128_cells','-v7');
fprintf('All108Rawcells reproduce the original thesis cell representation exactly.\n');
end
