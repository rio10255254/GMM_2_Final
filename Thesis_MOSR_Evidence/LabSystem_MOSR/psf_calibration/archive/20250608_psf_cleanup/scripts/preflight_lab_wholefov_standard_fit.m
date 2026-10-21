% Preflight checks for the LabSystem_MOSR copied project-standard PSF fitter.

clear; clc;

script_dir = fileparts(mfilename('fullpath'));
psf_root = fileparts(script_dir);
standard_dir = fullfile(script_dir, 'standard_wholefov');
input_folder = fullfile(psf_root, 'inputs', '20250605_standard_wholefov', 'measured');
gt_path = fullfile(psf_root, 'inputs', '20250605_standard_wholefov', 'GT', 'LAB_GT_REQUIRED.bmp');
dependency_root = 'D:/GMM_2_Final/PSF_Fitting';
psf_basis_path = fullfile(dependency_root, 'SimulatePSF', 'psf_multi.mat');

required_files = {
    fullfile(standard_dir, 'HDR_fitting_2D_WholeFOV_impl.m')
    fullfile(standard_dir, 'HDR_fitting_2D_WholeFOV_reasonable_v1.m')
    fullfile(standard_dir, 'HDR_fitting_2D_WholeFOV_candidate_prealign.m')
    fullfile(standard_dir, 'vlab_translate_image.m')
    psf_basis_path
};

for idx = 1:numel(required_files)
    assert(isfile(required_files{idx}), 'Required file missing: %s', required_files{idx});
end

image_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
assert(numel(image_list) == 25, 'Expected 25 standard-named lab measurement BMP files.');

if isfile(gt_path)
    fprintf('Preflight PASS: lab GT exists and standard fitter can be run.\n');
else
    fprintf('Preflight BLOCKED: lab GT missing at:\n  %s\n', gt_path);
    fprintf('This is expected until the lab-system clean GT is prepared.\n');
end
