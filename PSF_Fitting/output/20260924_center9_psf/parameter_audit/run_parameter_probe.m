function run_parameter_probe(case_name, frames, mask_filename, output_name)
%RUN_PARAMETER_PROBE Probe existing BADS fitter without replacing accepted PSFs.
if nargin < 2, frames = [1 13 25]; end
if nargin < 3, mask_filename = 'loss_mask_train6.bmp'; end
case_name = char(case_name);
if nargin < 4, output_name = case_name; end
here = fileparts(mfilename('fullpath'));
run_root = fileparts(here);
psf_root = fileparts(fileparts(run_root));
addpath(psf_root);
addpath(fullfile(psf_root, 'PSF_Fitting_ValidationLab', 'scripts'));
addpath(fullfile(psf_root, 'SimulatePSF'));
addpath(genpath(fullfile(psf_root, 'bads-1.1.3')));

gradient_weight = 8e4;
rho_divisor = 2;
fix_tilt = true;
fix_amplitude = false;
profile_gain = false;
plausible_fraction = 1;
bads_options = struct('Display', 'off', 'UncertaintyHandling', false);

switch case_name
    case 'original'
        fix_tilt = false;
        bads_options = struct();
    case 'tilt_fixed'
        % Same objective and bounds, but tell BADS that locked tilt is fixed.
    case 'bads_restarts'
        plausible_fraction = 0.5;
        bads_options.Restarts = 2;
        bads_options.MaxFunEvals = 3000;
    case 'weight_0p1'
        gradient_weight = 0.1;
    case 'weight_1'
        gradient_weight = 1;
    case 'weight_0'
        gradient_weight = 0;
    case 'rho_full'
        gradient_weight = 0.1;
        rho_divisor = 1;
    case 'rho_full_legacyweight'
        rho_divisor = 1;
    case 'amp_fixed'
        gradient_weight = 0.1;
        fix_amplitude = true;
    case 'profile_gain_0'
        gradient_weight = 0;
        fix_amplitude = true;
        profile_gain = true;
    case 'profile_gain_0p1'
        gradient_weight = 0.1;
        fix_amplitude = true;
        profile_gain = true;
    otherwise
        error('Unknown parameter probe: %s', case_name);
end

input_root = fullfile(run_root, 'fit_input');
output_root = fullfile(here, char(output_name));
if startsWith(string(output_name), "confirm_")
    rng(20260924, 'twister');
end
result = HDR_fitting_2D_WholeFOV_reasonable_v1( ...
    'subset_indices', frames, ...
    'input_folder', input_root, ...
    'gt_path', fullfile(input_root, 'GT', 'gt_sem_cd.bmp'), ...
    'loss_mask_path', fullfile(input_root, char(mask_filename)), ...
    'grid_rows', 5, 'grid_cols', 5, ...
    'image_pattern', 'fit_input_*.bmp', ...
    'warm_start', false, ...
    'pre_alignment', false, ...
    'lock_tilt', true, ...
    'psf_scale', 0.125 / (3.45 / 20), ...
    'aberration_bound_scale', 2, ...
    'gradient_weight', gradient_weight, ...
    'rho_divisor', rho_divisor, ...
    'fix_locked_tilt_in_bads', fix_tilt, ...
    'fix_amplitude_in_bads', fix_amplitude, ...
    'profile_gain', profile_gain, ...
    'plausible_bound_fraction', plausible_fraction, ...
    'bads_options', bads_options, ...
    'output_root', output_root, ...
    'use_gpu', false);
assert(result.num_images == numel(frames), 'Incomplete parameter probe.');
fprintf('Completed %s with %d frames.\n', case_name, result.num_images);
end
