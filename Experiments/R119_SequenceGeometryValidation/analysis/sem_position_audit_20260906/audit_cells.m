function audit_cells()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
% Diagnose the original failed export check without editing any measurement.
% R69 run_acm_extraction.m lines 150-151 stores im2uint8(mat2gray(cell)).
% New measured_arrays.mat deliberately keeps original intensities for detail QA.
root=fullfile(PROJECT_ROOT, 'Experiments/R119_SequenceGeometryValidation');
out=fullfile(root,'analysis','sem_position_audit_20260906');
assert(~isfile(fullfile(out,'cell_export_diagnosis.csv')),'Preserve prior diagnostic');
old=load(fullfile(root,'results','formal_sem','results','masks','acm_primary_masks.mat'));
new=load(fullfile(out,'measured_arrays.mat'),'cells');
exposure=zeros(864,1);pillar=zeros(864,1);method=strings(864,1);
normalized_export_difference=zeros(864,1);original_intensity_crop_difference=zeros(864,1);
names={'Raw','base'};k=0;
for e=1:12
    exp=double(old.exposures(e));
    for m=1:2
        if m==1
            fullpath=fullfile(root,'..','R69_ACMContourSEMValidation','inputs','sem_paired_50x_exposure_stack',[num2str(exp) '.bmp']);
        else
            fullpath=fullfile(root,'results','formal_sem','reconstructions',[num2str(exp) '.bmp']);
        end
        image=im2double(imread(fullpath));padded=padarray(image,[52 52],'symmetric','both');
        for r=1:6
            for c=1:6
                k=k+1;id=double(old.global_index(r,c));center=old.opt_centers((r-1)*6+c,:);
                cx=round(center(1))+52;cy=round(center(2))+52;
                original_crop=padded(cy-52:cy+51,cx-52:cx+51);
                if m==1,prior=old.raw_cells(:,:,id,e);else,prior=old.recon_cells(:,:,id,e);end
                stored=new.cells(:,:,id,e,m);
                exposure(k)=exp;pillar(k)=id;method(k)=string(names{m});
                normalized_export_difference(k)=nnz(im2uint8(mat2gray(original_crop))~=prior);
                original_intensity_crop_difference(k)=nnz(im2uint8(original_crop)~=stored);
            end
        end
    end
end
writetable(table(exposure,pillar,method,normalized_export_difference,original_intensity_crop_difference),fullfile(out,'cell_export_diagnosis.csv'));
assert(all(normalized_export_difference==0) && all(original_intensity_crop_difference==0),'Known historical normalization failed to explain export mismatch');
fprintf('864/864 normalized historical exports and original-intensity crops reproduced exactly. Original failed measurements/log retained.\n');
end
