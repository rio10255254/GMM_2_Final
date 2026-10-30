% LabSystem_MOSR formal PSF runner for the inner-circle ROI batch.
% Reuses the copied project-standard Whole-FOV Zernike/BADS fitter.

this_file = mfilename('fullpath');
psf_root = fileparts(fileparts(this_file));
project_root = fileparts(fileparts(fileparts(psf_root)));

standard_dir = fullfile(psf_root, 'scripts', 'standard_wholefov');
input_folder = fullfile(psf_root, 'inputs', '20250605_inner_circle_roi', 'measured');
gt_path = fullfile(psf_root, 'inputs', '20250605_inner_circle_roi', 'GT', 'LAB_INNER_CIRCLE_GT_901.bmp');
dependency_root = fullfile(project_root, 'PSF_Fitting');
psf_basis_path = fullfile(dependency_root, 'SimulatePSF', 'psf_multi.mat');
output_root = fullfile(psf_root, 'results', '20250605_inner_circle_roi_standard_fit');

addpath(standard_dir);

if ~isfolder(input_folder)
    error('Lab inner-circle ROI input folder not found: %s', input_folder);
end
image_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
if numel(image_list) ~= 25
    error('Expected 25 lab ROI BMP files, found %d in %s', numel(image_list), input_folder);
end
if ~isfile(gt_path)
    error('Lab inner-circle GT is missing: %s', gt_path);
end
if ~isfile(psf_basis_path)
    error('Project PSF basis is missing: %s', psf_basis_path);
end

HDR_fitting_2D_WholeFOV_impl( ...
    'subset_indices', 1:25, ...
    'grid_rows', 5, ...
    'grid_cols', 5, ...
    'source_grid_cols', 5, ...
    'input_folder', input_folder, ...
    'gt_path', gt_path, ...
    'psf_basis_path', psf_basis_path, ...
    'dependency_root', dependency_root, ...
    'output_root', output_root, ...
    'prealign_crop_size', 257);
