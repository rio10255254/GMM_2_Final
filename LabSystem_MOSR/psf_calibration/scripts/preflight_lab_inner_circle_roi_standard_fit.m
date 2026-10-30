% Preflight checks for the lab inner-circle ROI Whole-FOV/BADS run.

this_file = mfilename('fullpath');
psf_root = fileparts(fileparts(this_file));
project_root = fileparts(fileparts(fileparts(psf_root)));

input_folder = fullfile(psf_root, 'inputs', '20250605_inner_circle_roi', 'measured');
gt_path = fullfile(psf_root, 'inputs', '20250605_inner_circle_roi', 'GT', 'LAB_INNER_CIRCLE_GT_901.bmp');
dependency_root = fullfile(project_root, 'PSF_Fitting');
psf_basis_path = fullfile(dependency_root, 'SimulatePSF', 'psf_multi.mat');

fprintf('Lab inner-circle ROI PSF preflight\n');
fprintf('Input folder: %s\n', input_folder);
fprintf('GT path: %s\n', gt_path);
fprintf('PSF basis: %s\n', psf_basis_path);

issues = {};
if ~isfolder(input_folder)
    issues{end + 1} = 'ROI input folder missing'; %#ok<AGROW>
else
    image_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
    fprintf('ROI image count: %d\n', numel(image_list));
    if numel(image_list) ~= 25
        issues{end + 1} = sprintf('Expected 25 ROI images, found %d', numel(image_list)); %#ok<AGROW>
    end
end
if ~isfile(gt_path)
    issues{end + 1} = 'Inner-circle GT missing'; %#ok<AGROW>
end
if ~isfile(psf_basis_path)
    issues{end + 1} = 'Original project PSF basis missing'; %#ok<AGROW>
end

if isempty(issues)
    fprintf('Preflight OK: inner-circle ROI batch is ready for the copied Whole-FOV/BADS fitter.\n');
else
    fprintf('Preflight BLOCKED:\n');
    for i = 1:numel(issues)
        fprintf('  - %s\n', issues{i});
    end
    error('Lab inner-circle ROI PSF preflight failed.');
end
