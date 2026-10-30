function plot_subpixel_results()
% MATLAB-only thesis figures for the locked subpixel translation experiment.

rootDir = fileparts(mfilename('fullpath'));
tableDir = fullfile(rootDir, 'analysis', 'tables');
figureDir = fullfile(rootDir, 'figures');
if ~exist(figureDir, 'dir')
    mkdir(figureDir);
end

cluster = readtable(fullfile(tableDir, 'cluster_translation_metrics.csv'), ...
    'VariableNamingRule', 'preserve');
primaryFlag = ismember(lower(string(cluster.primary_endpoint)), ["true","1"]);
validFlag = ismember(lower(string(cluster.valid)), ["true","1"]);
primary = cluster(primaryFlag & validFlag, :);
overall = readtable(fullfile(tableDir, 'primary_translation_summary_by_method.csv'), ...
    'VariableNamingRule', 'preserve');
byShift = readtable(fullfile(tableDir, 'primary_translation_summary_by_shift.csv'), ...
    'VariableNamingRule', 'preserve');
equiv = readtable(fullfile(tableDir, 'image_equivariance_summary.csv'), ...
    'VariableNamingRule', 'preserve');
sharp = readtable(fullfile(tableDir, 'sharpness_summary.csv'), ...
    'VariableNamingRule', 'preserve');
crossAxis = readtable(fullfile(tableDir, 'cross_axis_summary.csv'), ...
    'VariableNamingRule', 'preserve');

keys = {'raw','base_unet','edsr','nafnet','mosr'};
labels = {'Raw','Base U-Net','EDSR','NAFNet','MOSR'};
colors = [0.35 0.35 0.35; 0.64 0.32 0.17; 0.85 0.52 0.05; 0.38 0.55 0.35; 0.09 0.39 0.64];

set(groot, 'defaultAxesFontName', 'Times New Roman');
set(groot, 'defaultTextFontName', 'Times New Roman');
set(groot, 'defaultAxesFontSize', 8.5);
set(groot, 'defaultTextFontSize', 8.5);
set(groot, 'defaultAxesLineWidth', 0.75);

%% 1. Primary boundary localization error
med = nan(1, numel(keys)); p95 = med; ciLo = med; ciHi = med;
for i = 1:numel(keys)
    row = overall(strcmp(overall.method_key, keys{i}), :);
    med(i) = row.median_absolute_error_px;
    p95(i) = row.p95_absolute_error_px;
    ciLo(i) = row.median_absolute_error_px_ci_low;
    ciHi(i) = row.median_absolute_error_px_ci_high;
end
fig = thesisFigure();
hold on;
for i = 1:numel(keys)
    plot([i i], [med(i) p95(i)], '-', 'Color', [0.35 0.35 0.35], 'LineWidth', 1.0);
    plot([i-0.09 i+0.09], [p95(i) p95(i)], '-', 'Color', [0.20 0.20 0.20], 'LineWidth', 1.0);
    errorbar(i, med(i), med(i)-ciLo(i), ciHi(i)-med(i), 'o', ...
        'Color', colors(i,:), 'MarkerFaceColor', colors(i,:), ...
        'MarkerSize', 5.2, 'LineWidth', 1.0, 'CapSize', 6);
end
xlim([0.45 5.55]); ylim([0 max(p95)*1.15]);
xticks(1:5); xticklabels(labels);
ylabel('Absolute translation error (pixel)');
title('Boundary localization under controlled subpixel translations', 'FontWeight', 'normal');
subtitle('Marker: median with 95% bootstrap interval; cap: 95th percentile');
grid on; box on;
exportFigure(fig, figureDir, '01_primary_boundary_localization_error');

%% 2. Error versus imposed shift magnitude
fig = thesisFigure();
hold on;
for i = 1:numel(keys)
    rows = byShift(strcmp(byShift.method_key, keys{i}), :);
    rows = sortrows(rows, 'shift_magnitude_px');
    plot(rows.shift_magnitude_px, rows.median_absolute_error_px, '-o', ...
        'Color', colors(i,:), 'MarkerFaceColor', colors(i,:), ...
        'LineWidth', 1.15, 'MarkerSize', 4.2, 'DisplayName', labels{i});
end
xlim([0.06 1.04]);
xticks([0.1 0.25 0.5 0.75 1.0]);
xlabel('Imposed translation magnitude (pixel)');
ylabel('Median absolute error (pixel)');
title('Localization error across translation magnitudes', 'FontWeight', 'normal');
legend('Location', 'northwest', 'NumColumns', 2, 'Box', 'off');
grid on; box on;
exportFigure(fig, figureDir, '02_error_vs_translation_magnitude');

%% 3. Physical P95 error by magnification
magnifications = {'50x','20x'};
physicalP95 = nan(2, numel(keys));
for m = 1:2
    for i = 1:numel(keys)
        mask = strcmp(primary.magnification, magnifications{m}) & ...
            strcmp(primary.method_key, keys{i});
        physicalP95(m,i) = prctile(primary.absolute_error_nm(mask), 95);
    end
end
fig = thesisFigure();
b = bar(physicalP95, 'grouped', 'BarWidth', 0.76);
for i = 1:numel(keys)
    b(i).FaceColor = colors(i,:);
    b(i).EdgeColor = 'none';
end
xticks(1:2);
xticklabels({'50x','20x'});
xtickangle(0);
xlim([0.5 2.5]);
xlabel('Objective magnification');
ylabel('95th-percentile absolute error (nm)');
title('Upper-tail localization error in object space', 'FontWeight', 'normal');
legend(labels, 'Location', 'northwest', 'NumColumns', 2, 'Box', 'off');
grid on; box on;
exportFigure(fig, figureDir, '03_p95_error_by_magnification');

%% 4. Image translation-equivariance residual
eqMedian = nan(1, numel(keys)); eqP95 = eqMedian;
for i = 1:numel(keys)
    row = equiv(strcmp(equiv.method_key, keys{i}), :);
    eqMedian(i) = row.median_normalized_rmse;
    eqP95(i) = row.p95_normalized_rmse;
end
fig = thesisFigure();
hold on;
for i = 1:numel(keys)
    plot([i i], [eqMedian(i) eqP95(i)], '-', 'Color', [0.35 0.35 0.35], 'LineWidth', 1.0);
    plot(i, eqMedian(i), 'o', 'Color', colors(i,:), ...
        'MarkerFaceColor', colors(i,:), 'MarkerSize', 5.2);
    plot(i, eqP95(i), '_', 'Color', [0.20 0.20 0.20], 'MarkerSize', 8, 'LineWidth', 1.1);
end
set(gca, 'YScale', 'log');
xlim([0.45 5.55]); xticks(1:5); xticklabels(labels);
ylabel('Normalized reconstruction residual');
title('Image-level translation equivariance', 'FontWeight', 'normal');
subtitle('Marker: median; cap: 95th percentile; lower is better');
grid on; box on;
exportFigure(fig, figureDir, '04_image_translation_equivariance');

%% 5. Edge transition width (sharpness guardrail)
sharpMedian = nan(1, numel(keys)); sharpP95 = sharpMedian;
for i = 1:numel(keys)
    row = sharp(strcmp(sharp.method_key, keys{i}), :);
    sharpMedian(i) = row.median_transition_width_px;
    sharpP95(i) = row.p95_transition_width_px;
end
fig = thesisFigure();
hold on;
bars = bar(1:5, sharpMedian, 0.62, 'FaceColor', 'flat', 'EdgeColor', 'none');
bars.CData = colors;
for i = 1:numel(keys)
    plot([i i], [sharpMedian(i) sharpP95(i)], '-', 'Color', [0.25 0.25 0.25], 'LineWidth', 0.9);
    plot([i-0.08 i+0.08], [sharpP95(i) sharpP95(i)], '-', 'Color', [0.20 0.20 0.20], 'LineWidth', 1.0);
end
xlim([0.45 5.55]); xticks(1:5); xticklabels(labels);
ylabel('10-90% edge transition width (pixel)');
title('Boundary sharpness after reconstruction', 'FontWeight', 'normal');
subtitle('Bar: median; cap: 95th percentile; lower is sharper');
grid on; box on;
exportFigure(fig, figureDir, '05_edge_transition_width');

%% 6. Cross-axis drift
crossMedian = nan(1, numel(keys)); crossP95 = crossMedian;
for i = 1:numel(keys)
    row = crossAxis(strcmp(crossAxis.method_key, keys{i}), :);
    crossMedian(i) = row.median_absolute_cross_axis_px;
    crossP95(i) = row.p95_absolute_cross_axis_px;
end
fig = thesisFigure();
hold on;
for i = 1:numel(keys)
    plot([i i], [crossMedian(i) crossP95(i)], '-', 'Color', [0.35 0.35 0.35], 'LineWidth', 1.0);
    plot(i, crossMedian(i), 'o', 'Color', colors(i,:), ...
        'MarkerFaceColor', colors(i,:), 'MarkerSize', 5.2);
    plot(i, crossP95(i), '_', 'Color', [0.20 0.20 0.20], 'MarkerSize', 8, 'LineWidth', 1.1);
end
xlim([0.45 5.55]); xticks(1:5); xticklabels(labels);
ylabel('Absolute cross-axis displacement (pixel)');
title('Unintended cross-axis boundary drift', 'FontWeight', 'normal');
subtitle('Marker: median; cap: 95th percentile; lower is better');
grid on; box on;
exportFigure(fig, figureDir, '06_cross_axis_boundary_drift');

%% 7. Diagnostic sharpness-stability trade-off
fig = thesisFigure();
hold on;
for i = 1:numel(keys)
    plot(sharpMedian(i), med(i), 'o', 'Color', colors(i,:), ...
        'MarkerFaceColor', colors(i,:), 'MarkerSize', 6.5);
    text(sharpMedian(i), med(i), ['  ' labels{i}], 'VerticalAlignment', 'middle');
end
xlim([min(sharpMedian)-0.4 max(sharpMedian)+0.9]);
xlabel('Median 10-90% transition width (pixel)');
ylabel('Median absolute translation error (pixel)');
title('Sharpness and boundary stability', 'FontWeight', 'normal');
grid on; box on;
exportFigure(fig, figureDir, '07_sharpness_stability_tradeoff');

fprintf('Exported 7 MATLAB figures to %s\n', figureDir);
end


function fig = thesisFigure()
fig = figure('Color', 'w', 'Units', 'centimeters', ...
    'Position', [2 2 15.8 9.8], 'Visible', 'off');
ax = axes(fig);
set(ax, 'FontName', 'Times New Roman', 'FontSize', 8.5, ...
    'LineWidth', 0.75, 'TickDir', 'out', 'Layer', 'top');
hold(ax, 'on');
end


function exportFigure(fig, figureDir, stem)
pngPath = fullfile(figureDir, [stem '.png']);
figPath = fullfile(figureDir, [stem '.fig']);
exportgraphics(fig, pngPath, 'Resolution', 400, 'BackgroundColor', 'white');
savefig(fig, figPath);
close(fig);
end
