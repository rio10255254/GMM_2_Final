function run_mixture_bads(fold_name, observation_mode)
%RUN_MIXTURE_BADS Fit a centered core-plus-halo PSF with the bundled BADS.
fold_name = char(fold_name);
if nargin < 2, observation_mode = 'center'; end
observation_mode = char(observation_mode);
root = fileparts(mfilename('fullpath'));
run_root = fileparts(root);
psf_root = fileparts(fileparts(run_root));
addpath(genpath(fullfile(psf_root, 'bads-1.1.3')));
input_root = fullfile(run_root, 'fit_input');
truth = load(fullfile(root, 'sem_truth_float.mat'), 'gt');
gt = double(truth.gt);
if strcmp(fold_name, 'A')
    frames = [1 13 25];
    mask_path = fullfile(input_root, 'loss_mask_train6.bmp');
elseif strcmp(fold_name, 'B')
    frames = [4 7 12 18 23];
    mask_path = fullfile(input_root, 'loss_mask_train6_B.bmp');
elseif strcmp(fold_name, 'C')
    frames = [3 8 14 20 22];
    mask_path = fullfile(root, 'loss_mask_train6_C.bmp');
elseif strcmp(fold_name, 'D')
    frames = [2 6 10 15 17 24];
    mask_path = fullfile(root, 'full_train6_D.bmp');
elseif strcmp(fold_name, 'E')
    frames = [5 9 11 16 19 21];
    mask_path = fullfile(root, 'full_train6_E.bmp');
elseif strcmp(fold_name, 'ALL')
    frames = 1:25;
    mask_path = fullfile(root, 'full_all9.bmp');
else
    error('Unknown fold: %s', fold_name);
end
if strcmp(observation_mode, 'full')
    input_root = fullfile(run_root, 'parameter_audit', 'wide_input');
    if strcmp(fold_name, 'ALL')
        mask_path = fullfile(root, 'full_all9.bmp');
    else
        mask_path = fullfile(root, ['full_train6_' fold_name '.bmp']);
    end
elseif ~strcmp(observation_mode, 'center')
    error('Unknown observation mode: %s', observation_mode);
end
mask = imread(mask_path) > 0;
if strcmp(observation_mode, 'full')
    if strcmp(fold_name, 'ALL')
        assert(nnz(mask) == 9 * 625);
    else
        assert(nnz(mask) == 6 * 625);
    end
else
    assert(nnz(mask) == 6 * 317);
end
lower = [0.6, 0.2, 0.1];
upper = [5.0, 22.0, 0.95];
plausible_lower = [1.0, 3.0, 0.2];
plausible_upper = [2.0, 8.0, 0.7];
initial = [1.3, 4.7, 0.42];
options = struct('Display', 'off', 'UncertaintyHandling', false, ...
    'MaxFunEvals', 1000, 'TolFun', 1e-7, 'Restarts', 1);
if strcmp(observation_mode, 'full')
    out = fullfile(root, ['mixture_full_' fold_name]);
else
    out = fullfile(root, ['mixture_bads_' fold_name]);
end
if ~exist(out, 'dir'), mkdir(out); end
psf_grid = zeros(101, 101, 1, numel(frames));
coefficient_grid = zeros(3, 1, numel(frames));
rows = repmat(struct('frame', 0, 'sigma_core_px', 0, 'sigma_halo_px', 0, ...
    'core_energy_weight', 0, 'train_mse', 0, 'exitflag', 0, ...
    'seconds', 0, 'peak_offset_px', 0, 'centroid_offset_px', 0), numel(frames), 1);
for index = 1:numel(frames)
    frame = frames(index);
    img = im2double(imread(fullfile(input_root, sprintf('fit_input_%02d.bmp', frame))));
    objective_handle = @(x) mixture_loss(x, gt, img, mask);
    rng(20260924 + frame, 'twister');
    t = tic;
    [coef, fval, exitflag] = bads(objective_handle, initial, lower, upper, ...
        plausible_lower, plausible_upper, [], options);
    elapsed = toc(t);
    psf = mixture_kernel(coef);
    [cy, cx] = find(psf == max(psf, [], 'all'), 1);
    [X, Y] = meshgrid(1:101, 1:101);
    centroid_x = sum(X .* psf, 'all') - 51;
    centroid_y = sum(Y .* psf, 'all') - 51;
    psf_grid(:, :, 1, index) = psf;
    coefficient_grid(:, 1, index) = coef(:);
    rows(index).frame = frame;
    rows(index).sigma_core_px = coef(1);
    rows(index).sigma_halo_px = coef(1) + coef(2);
    rows(index).core_energy_weight = coef(3);
    rows(index).train_mse = fval;
    rows(index).exitflag = exitflag;
    rows(index).seconds = elapsed;
    rows(index).peak_offset_px = hypot(cx - 51, cy - 51);
    rows(index).centroid_offset_px = hypot(centroid_x, centroid_y);
    fprintf('Mixture fold %s frame %d: loss=%g exitflag=%d seconds=%.2f\n', ...
        fold_name, frame, fval, exitflag, elapsed);
end
save(fullfile(out, 'PSF_fitted_mixture.mat'), 'psf_grid', 'coefficient_grid', 'frames', '-v7');
writetable(struct2table(rows), fullfile(out, 'batch_results.csv'));
config = struct('fold', fold_name, 'observation_mode', observation_mode, 'frames', frames, 'gt_path', fullfile(root, 'sem_truth_float.mat'), ...
    'input_folder', input_root, 'mask_path', mask_path, 'lower', lower, 'upper', upper, ...
    'plausible_lower', plausible_lower, 'plausible_upper', plausible_upper, ...
    'initial', initial, 'bads_options', options, 'kernel', 'unit-sum centered isotropic Gaussian core plus Gaussian halo');
fid = fopen(fullfile(out, 'config.json'), 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(config, PrettyPrint=true));
assert(all([rows.exitflag] > 0), 'At least one BADS mixture fit did not converge.');
end

function loss = mixture_loss(coef, gt, img, mask)
psf = mixture_kernel(coef);
prediction = conv2(gt, psf, 'same');
target = img(mask);
source = prediction(mask);
gain = max(0, sum(target .* source) / max(sum(source .^ 2), eps));
loss = mean((target - gain * source) .^ 2);
end

function psf = mixture_kernel(coef)
core = coef(1);
halo = core + coef(2);
core_weight = coef(3);
[x, y] = meshgrid(-50:50, -50:50);
radius2 = x.^2 + y.^2;
psf = core_weight * exp(-radius2 / (2 * core^2)) / (2 * pi * core^2) + ...
    (1-core_weight) * exp(-radius2 / (2 * halo^2)) / (2 * pi * halo^2);
psf = psf / sum(psf, 'all');
end
