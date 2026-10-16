function prepare_wide_patches()
%PREPARE_WIDE_PATCHES Preserve default parity and extend real optical tails.
here = fileparts(mfilename('fullpath'));
run_root = fileparts(here);
psf_root = fileparts(fileparts(run_root));
repo_root = fileparts(psf_root);
addpath(psf_root);
locations = readtable(fullfile(run_root, 'center9_locations.csv'), TextType='string');
assert(height(locations) == 225);
cd_nm = flipud(center_9pillar_sem_cd());
input_root = fullfile(here, 'wide_input');
gt_root = fullfile(input_root, 'GT');
if ~exist(gt_root, 'dir'), mkdir(gt_root); end
for image_index = 1:25
    rows = locations(locations.image_index == image_index, :);
    assert(height(rows) == 9);
    source_path = fullfile(repo_root, '20260924', char(rows.image(1)));
    detection = struct( ...
        'selected_centers', [rows.x rows.y], ...
        'selected_radii', repmat(7.6, 9, 1), ...
        'pitch_px', 5 / (3.45 / 20), ...
        'polarity', 'dark', ...
        'magnification', 20, ...
        'pillar_junction_corner', "top-left");
    original_pair = build_center_9pillar_fit_pair(source_path, detection, cd_nm);
    existing_input = imread(fullfile(run_root, 'fit_input', sprintf('fit_input_%02d.bmp', image_index)));
    assert(isequal(uint8(round(original_pair.fit_input * 255)), existing_input), ...
        'Default crop changed at image %d.', image_index);
    wide_pair = build_center_9pillar_fit_pair(source_path, detection, cd_nm, ...
        'PatchHalfPx', 17, 'LossRadiusPx', 12);
    assert(isequal(wide_pair.gt, original_pair.gt), 'SEM target changed.');
    imwrite(uint8(round(wide_pair.fit_input * 255)), ...
        fullfile(input_root, sprintf('fit_input_%02d.bmp', image_index)));
    if image_index == 1
        imwrite(uint8(round(wide_pair.gt * 255)), fullfile(gt_root, 'gt_sem_cd.bmp'));
        imwrite(uint8(wide_pair.loss_mask) * 255, fullfile(input_root, 'loss_mask.bmp'));
    end
end
fprintf('Prepared 25 wide crops; 25 default crops reproduced exactly.\n');
end
