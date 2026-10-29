function tests = test_psf_figure_outputs
tests = functiontests(localfunctions);
end

function test_final_outputs(testCase)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
root = fullfile(PROJECT_ROOT,'Thesis_MOSR_Evidence', ...
    'Final_Data_Figures','03_PSF_EXPERIMENT_RESULTS','01_global_bads_fit');
fig = fullfile(root,'figures','center9_pillar_fit_20x_50x');
src = fullfile(root,'source_data','center9_pillar_fit_20x_50x','psf_analysis');
files = [case_files(fig,'20x'); case_files(fig,'50x'); ...
    fullfile(fig,'comparison',{'01_center_profile_comparison.png'; ...
    '02_encircled_energy_comparison.png';'03_mtf_comparison.png'})];
verifyEqual(testCase,numel(files),13);
for k=1:numel(files)
    verifyEqual(testCase,exist(files{k},'file'),2);
    info=imfinfo(files{k});
    verifyGreaterThan(testCase,info.Width,1200);
    verifyGreaterThan(testCase,info.Height,1000);
end
manifest=jsondecode(fileread(fullfile(src,'psf_analysis_manifest.json')));
verifyEqual(testCase,manifest.generator,'MATLAB');
verifyEqual(testCase,manifest.figure_count,13);
verifyEqual(testCase,manifest.heatmap_physical_limits_um(:)',[-3,3]);
verifyEqual(testCase,manifest.typography.title_pt,14);
verifyEqual(testCase,manifest.typography.subtitle_pt,10);
verifyEqual(testCase,manifest.typography.axis_tick_pt,9.5);
verifyEqual(testCase,manifest.typography.axis_label_pt,10.5);
verifyEqual(testCase,manifest.typography.legend_pt,9.5);
verifyEqual(testCase,manifest.typography.colorbar_tick_pt,9);
verifyEqual(testCase,manifest.typography.annotation_pt,9);
verifyEqual(testCase,exist(fullfile(src,'psf_analysis_metrics.csv'),'file'),2);
verifyEqual(testCase,exist(fullfile(src,'psf_analysis_data.mat'),'file'),2);
end

function files=case_files(root,label)
names={'15_normalized_fitted_psf_halfmax_contour.png'; ...
 '16_fitted_psf_center_profiles_fwhm.png'; ...
 '17_fitted_psf_encircled_energy.png';'18_fitted_psf_mtf.png'; ...
 '19_forward_fit_residual.png'};
files=fullfile(root,label,names);
end
