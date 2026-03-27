function test_validation_lab_rep16_configs()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

configs = vlab_get_experiment_configs(lab_root, 'profile_name', 'rep16');
config_names = string({configs.name});

expected_names = ["baseline_rep16", "alignment_rep16", "alignment_subpixel_rep16", "alignment_quarter_rep16", "alignment_tilt_rep16"];
assert(isequal(config_names, expected_names), 'rep16 profile should expose the expected experiment names.');

expected_subset = [1 4 6 10 31 34 36 40 51 54 56 60 91 94 96 100];
for i = 1:numel(configs)
    assert(isequal(configs(i).subset_indices, expected_subset), 'rep16 subset indices should match the representative 16-point grid.');
end

alignment_row = configs(config_names == "alignment_rep16");
assert(alignment_row.lock_tilt, 'alignment_rep16 should keep tilt locked.');
assert(alignment_row.pre_alignment, 'alignment_rep16 should enable prealignment.');
assert(alignment_row.prealign_step == 1.0, 'alignment_rep16 should keep integer-step prealignment.');

alignment_subpixel_row = configs(config_names == "alignment_subpixel_rep16");
assert(alignment_subpixel_row.lock_tilt, 'alignment_subpixel_rep16 should keep tilt locked.');
assert(alignment_subpixel_row.pre_alignment, 'alignment_subpixel_rep16 should enable prealignment.');
assert(alignment_subpixel_row.prealign_step == 0.5, 'alignment_subpixel_rep16 should use 0.5px search step.');

alignment_quarter_row = configs(config_names == "alignment_quarter_rep16");
assert(alignment_quarter_row.lock_tilt, 'alignment_quarter_rep16 should keep tilt locked.');
assert(alignment_quarter_row.pre_alignment, 'alignment_quarter_rep16 should enable prealignment.');
assert(alignment_quarter_row.prealign_step == 0.25, 'alignment_quarter_rep16 should use 0.25px search step.');

alignment_tilt_row = configs(config_names == "alignment_tilt_rep16");
assert(~alignment_tilt_row.lock_tilt, 'alignment_tilt_rep16 should release tilt.');
assert(alignment_tilt_row.pre_alignment, 'alignment_tilt_rep16 should enable prealignment.');
end
