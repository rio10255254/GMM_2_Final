function run_matlab_smoke_tests()
tests_root = fileparts(mfilename('fullpath'));
addpath(genpath(fullfile(tests_root, 'matlab')));

test_names = {
    'test_wholefov_formal_script_smoke'
    'test_wholefov_formal_compat_smoke'
    'test_wholefov_formal_reuse_candidate_smoke'
    'test_validation_lab_smoke'
    'test_validation_lab_rep16_configs'
    'test_validation_lab_aggregate_smoke'
    'test_validation_lab_aggregate_dynamic_templates'
    'test_validation_lab_aggregate_prefers_quarter_candidate'
    'test_subpixel_prealign_smoke'
    'test_candidate_flow_smoke'
    'test_reasonable_flow_smoke'
};

for idx = 1:numel(test_names)
    fprintf('[%d/%d] Running %s...\n', idx, numel(test_names), test_names{idx});
    feval(test_names{idx});
end

fprintf('All MATLAB smoke tests completed.\n');
end
