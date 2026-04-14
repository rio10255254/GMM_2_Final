function test_validation_lab_aggregate_prefers_quarter_candidate()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

output_root = vlab_test_output_root(lab_root);
summary = vlab_aggregate_existing_results(lab_root, ...
    'experiment_names', string({'baseline_rep16', 'alignment_rep16', 'alignment_subpixel_rep16', 'alignment_quarter_rep16', 'alignment_tilt_rep16'}), ...
    'output_root', output_root);

summary_text = fileread(summary.validation_summary_path);
recommendation_text = fileread(summary.next_recommendation_path);
candidate_text = fileread(summary.candidate_flow_path);

assert(contains(summary_text, 'alignment_quarter_rep16'), ...
    'Validation summary should promote alignment_quarter_rep16 when it has the best score.');
assert(contains(summary_text, '0.500 px'), ...
    'Validation summary should report the improved 0.500 px peak-offset result.');
assert(contains(recommendation_text, 'alignment_quarter_rep16'), ...
    'Recommendation should promote alignment_quarter_rep16 as the formal candidate.');
assert(contains(candidate_text, 'prealign_step = 0.25'), ...
    'Candidate flow doc should state the 0.25px default prealignment step.');
assert(contains(candidate_text, 'warm_start + refined pre_alignment + tilt locked'), ...
    'Candidate flow doc should describe the refined 0.25px candidate mechanism.');
assert(~contains(candidate_text, 'prealign_step = 0.5'), ...
    'Candidate flow doc should no longer describe 0.5px as the default candidate.');
end
