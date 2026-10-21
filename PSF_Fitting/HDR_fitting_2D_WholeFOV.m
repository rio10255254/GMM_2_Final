%% HDR fitting 2D - formal Whole-FOV PSF fitting
clearvars;
clc;
close all;

summary = run_psf_fitting_manual();
fprintf('Formal Whole-FOV fitting completed.\n');
fprintf('Outputs:\n');
fprintf('  %s\n', summary.batch_results_path);
fprintf('  %s\n', summary.stack_path);
