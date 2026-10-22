clear; close all; clc;

csvPath = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\Modern_Restoration_Benchmarks_20260719\evaluation\circular_cd_sharpness\circular_feature_cd_intervals.csv';
outDir = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS\modern_baseline_three_morphology_20260719\figures';
if ~exist(outDir, 'dir')
    mkdir(outDir);
end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Times New Roman');
set(groot, 'defaultTextFontName', 'Times New Roman');
set(groot, 'defaultAxesFontSize', 8.5);
set(groot, 'defaultTextFontSize', 8.5);
set(groot, 'defaultAxesLineWidth', 0.75);

T = readtable(csvPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
S = T(T.magnification == "20x" & T.morphology == "via", :);
methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
featureIDs = unique(S.feature_id, 'stable');
nFeatures = numel(featureIDs);
nMethods = numel(methods);

sem = nan(nFeatures, 1);
for k = 1:nFeatures
    row = S(S.feature_id == featureIDs(k), :);
    sem(k) = row.sem_cd_nm(1) / 1000;
end

f = figure('Units', 'pixels', 'Position', [40 40 1687 977], ...
    'PaperUnits', 'inches', 'PaperPosition', [0 0 16.87 9.77], ...
    'PaperSize', [16.87 9.77], 'PaperPositionMode', 'manual', ...
    'Visible', 'off', 'Color', 'w');
ax = axes(f); hold(ax, 'on');
plot(ax, 1:nFeatures, sem, '--o', 'Color', [0.12 0.12 0.12], ...
    'MarkerFaceColor', 'w', 'MarkerSize', 4.0, 'LineWidth', 1.0, ...
    'DisplayName', 'SEM reference');

offsets = linspace(-0.24, 0.24, nMethods);
palette = [0.33 0.33 0.33; 0.78 0.45 0.16; 0.45 0.36 0.62; 0.00 0.45 0.74];
for m = 1:nMethods
    midpoint = nan(nFeatures, 1);
    lowerBound = nan(nFeatures, 1);
    upperBound = nan(nFeatures, 1);
    for k = 1:nFeatures
        row = S(S.method == methods(m) & S.feature_id == featureIDs(k), :);
        if ~isempty(row)
            midpoint(k) = row.cd_interval_midpoint_nm(1) / 1000;
            lowerBound(k) = row.cd_lower_nm(1) / 1000;
            upperBound(k) = row.cd_upper_nm(1) / 1000;
        end
    end
    errorbar(ax, (1:nFeatures) + offsets(m), midpoint, ...
        midpoint-lowerBound, upperBound-midpoint, 'o', ...
        'Color', palette(m,:), 'MarkerFaceColor', palette(m,:), ...
        'MarkerSize', 3.5, 'CapSize', 3, 'LineWidth', 0.9, ...
        'DisplayName', methods(m));
end

title(ax, '20x via apparent CD range', 'FontWeight', 'normal');
subtitle(ax, 'Fixed 35%-65% local-contrast thresholds');
xlabel(ax, 'Via identity');
ylabel(ax, 'Apparent CD (\mum)');
xticks(ax, 1:nFeatures);
xticklabels(ax, featureIDs);
xlim(ax, [0.45 nFeatures+0.55]);
grid(ax, 'on');
ax.XGrid = 'off';
ax.Box = 'off';
ax.TickDir = 'out';
ax.Layer = 'top';
ax.GridColor = [0.82 0.82 0.82];
ax.GridAlpha = 0.65;
ax.LineWidth = 0.75;
legend(ax, 'Location', 'northoutside', 'NumColumns', 5, 'Box', 'off');

pngPath = fullfile(outDir, '04_20x_via_cd_interval_no_base_unet.png');
figPath = fullfile(outDir, '04_20x_via_cd_interval_no_base_unet.fig');
print(f, pngPath, '-dpng', '-r100');
savefig(f, figPath);
close(f);

fprintf('Wrote %s\n', pngPath);
fprintf('Wrote %s\n', figPath);
