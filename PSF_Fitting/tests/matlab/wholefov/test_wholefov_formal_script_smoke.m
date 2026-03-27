function test_wholefov_formal_script_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
script_path = fullfile(project_root, 'HDR_fitting_2D_WholeFOV.m');
legacy_path = fullfile(project_root, 'legacy', 'HDR_fitting_2D_WholeFOV_legacy_pre_prealign_fix_20260325.m');

assert(isfile(script_path), 'Formal Whole-FOV script should exist at the original path.');
assert(isfile(legacy_path), 'Legacy Whole-FOV script should be archived.');
end
