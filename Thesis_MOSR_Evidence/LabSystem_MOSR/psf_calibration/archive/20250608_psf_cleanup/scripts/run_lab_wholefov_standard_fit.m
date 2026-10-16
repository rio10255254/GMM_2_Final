% Run LabSystem_MOSR PSF fitting with the copied project-standard Whole-FOV fitter.
%
% This is only a thin lab entry point. The fitting logic lives in
% scripts/standard_wholefov/, copied from D:/GMM_2_Final/PSF_Fitting.

clear; clc;

script_dir = fileparts(mfilename('fullpath'));
psf_root = fileparts(script_dir);
lab_root = fileparts(psf_root);
standard_dir = fullfile(script_dir, 'standard_wholefov');

input_folder = fullfile(psf_root, 'inputs', '20250605_standard_wholefov', 'measured');
gt_path = fullfile(psf_root, 'inputs', '20250605_standard_wholefov', 'GT', 'LAB_GT_REQUIRED.bmp');
output_root = fullfile(psf_root, 'results', '20250605_standard_wholefov');
dependency_root = 'D:/GMM_2_Final/PSF_Fitting';
psf_basis_path = fullfile(dependency_root, 'SimulatePSF', 'psf_multi.mat');

addpath(standard_dir);

if ~isfolder(input_folder)
    error('Lab measurement input folder not found: %s', input_folder);
end
image_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
if numel(image_list) ~= 25
    error('Expected 25 lab measurement BMP files, found %d in %s', numel(image_list), input_folder);
end
if ~isfile(gt_path)
    error(['Lab GT is missing: %s\n' ...
        'Do not use the old industry-project GT. Place the lab-system clean GT at this path first.'], gt_path);
end
if ~isfile(psf_basis_path)
    error('Project theoretical PSF basis missing: %s', psf_basis_path);
end

summary = HDR_fitting_2D_WholeFOV_impl( ...
    'subset_indices', 1:25, ...
    'grid_rows', 5, ...
    'grid_cols', 5, ...
    'source_grid_cols', 5, ...
    'input_folder', input_folder, ...
    'gt_path', gt_path, ...
    'psf_basis_path', psf_basis_path, ...
    'dependency_root', dependency_root, ...
    'output_root', output_root, ...
    'warm_start', true, ...
    'pre_alignment', true, ...
    'lock_tilt', true);

fprintf('LabSystem_MOSR standard Whole-FOV PSF fitting completed.\n');
fprintf('Batch results: %s\n', summary.batch_results_path);
fprintf('PSF stack: %s\n', summary.stack_path);
