function test_validation_lab_aggregate_dynamic_templates()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

summary = vlab_aggregate_existing_results(lab_root, ...
    'experiment_names', "alignment_subpixel_rep16");

summary_text = fileread(summary.validation_summary_path);
candidate_text = fileread(summary.candidate_flow_path);

assert(~contains(summary_text, 'alignment_tilt_rep16'), ...
    'Partial aggregate should not mention missing tilt experiment.');
assert(~contains(summary_text, 'alignment_rep16'), ...
    'Partial aggregate should not mention missing integer-alignment experiment.');
assert(~contains(summary_text, 'baseline_rep16'), ...
    'Partial aggregate should not mention missing baseline experiment.');
assert(~contains(summary_text, '從  px'), ...
    'Summary should not contain blank numeric placeholders.');
assert(~contains(summary_text, '只小幅改善 '), ...
    'Summary should not contain incomplete comparison clauses.');

assert(~contains(candidate_text, 'alignment_tilt_rep16'), ...
    'Candidate flow should not mention missing tilt experiment.');
assert(~contains(candidate_text, 'alignment_rep16'), ...
    'Candidate flow should not mention missing integer-alignment experiment.');
assert(~contains(candidate_text, 'baseline_rep16'), ...
    'Candidate flow should not mention missing baseline experiment.');
assert(~contains(candidate_text, '小 ，且'), ...
    'Candidate flow should not contain blank numeric placeholders.');
end
