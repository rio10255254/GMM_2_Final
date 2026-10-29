PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
% Clean MATLAB figures for the refreshed 50x/20x modern-model displacement comparison.
% Figure bodies intentionally contain only legend, axes, tick labels, and CI marks.

clear; clc; close all;

rootDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report');
summaryPath = fullfile(rootDir, 'modern_displacement_by_magnification.csv');
outDir = fullfile(rootDir, 'figures_matlab');
if ~isfolder(outDir); mkdir(outDir); end

T = readtable(summaryPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
methods = ["Raw", "EDSR-x1", "NAFNet", "MOSR"];
magnifications = ["50x", "20x"];
colors = [0.35 0.35 0.35; 0.46 0.36 0.65; 0.80 0.47 0.10; 0.00 0.45 0.74];

plotMetric(T, "pillar", "step_error_sd_nm", "step_error_sd_ci95_low_nm", "step_error_sd_ci95_high_nm", ...
    '步距殘差標準差 (nm)', '01_pillar_step_error_sd_50x20x');
plotMetric(T, "pillar", "mae_nm", "mae_ci95_low_nm", "mae_ci95_high_nm", ...
    '相對 PI 回授位置的平均絕對誤差 (nm)', '02_pillar_displacement_mae_50x20x');
plotMetric(T, "via", "step_error_sd_nm", "step_error_sd_ci95_low_nm", "step_error_sd_ci95_high_nm", ...
    '步距殘差標準差 (nm)', '03_via_step_error_sd_50x20x');
plotMetric(T, "via", "mae_nm", "mae_ci95_low_nm", "mae_ci95_high_nm", ...
    '相對 PI 回授位置的平均絕對誤差 (nm)', '04_via_displacement_mae_50x20x');

function plotMetric(T, morphology, metricName, lowName, highName, yLabelText, fileStem)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
    methods = ["Raw", "EDSR-x1", "NAFNet", "MOSR"];
    magnifications = ["50x", "20x"];
    colors = [0.35 0.35 0.35; 0.46 0.36 0.65; 0.80 0.47 0.10; 0.00 0.45 0.74];
    S = T(T.morphology == morphology, :);
    values = nan(numel(magnifications), numel(methods));
    lower = nan(size(values));
    upper = nan(size(values));
    n = nan(numel(magnifications), 1);
    for i = 1:numel(magnifications)
        for j = 1:numel(methods)
            row = S(S.magnification == magnifications(i) & S.method == methods(j), :);
            if height(row) ~= 1
                error('Expected one row for %s / %s / %s.', morphology, magnifications(i), methods(j));
            end
            values(i,j) = row.(metricName);
            lower(i,j) = row.(lowName);
            upper(i,j) = row.(highName);
            n(i) = row.common_valid_n;
        end
    end

    f = figure('Visible', 'off', 'Color', 'w', 'Position', [80 80 1000 610]);
    ax = axes(f); hold(ax, 'on');
    b = bar(ax, 1:numel(magnifications), values, 'grouped', 'BarWidth', 0.82);
    for j = 1:numel(methods)
        b(j).FaceColor = colors(j,:);
        b(j).EdgeColor = 'none';
        lo = values(:,j) - lower(:,j);
        hi = upper(:,j) - values(:,j);
        errorbar(ax, b(j).XEndPoints, values(:,j), lo, hi, ...
            'LineStyle', 'none', 'Color', [0.15 0.15 0.15], 'LineWidth', 0.8, 'CapSize', 6);
    end
    grid(ax, 'on');
    ax.GridColor = [0.82 0.82 0.82];
    ax.GridAlpha = 0.8;
    ax.Box = 'off';
    ax.FontName = 'Microsoft JhengHei';
    ax.FontSize = 12;
    ax.LineWidth = 0.9;
    ax.TickDir = 'out';
    ax.XTick = 1:numel(magnifications);
    labels = replace(magnifications, 'x', '×') + " (n=" + string(round(n')) + ")";
    ax.XTickLabel = cellstr(labels);
    ylabel(ax, yLabelText, 'FontName', 'Microsoft JhengHei', 'FontSize', 14);
    xlabel(ax, '物鏡倍率；每組合併 0.5 與 1.0 \mum 序列', 'FontName', 'Microsoft JhengHei', 'FontSize', 13);
    legend(ax, b, methods, 'Location', 'northoutside', 'Orientation', 'horizontal', ...
        'Box', 'off', 'FontName', 'Arial', 'FontSize', 12);
    yMin = 0;
    upperValues = values + (upper - values);
    yMax = max(upperValues(:));
    ylim(ax, [yMin, yMax * 1.15]);
    drawnow;
    rootDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/displacement_50x20x_edrs_nafnet_refresh_20260724/modern_50x20x_report');
    outDir = fullfile(rootDir, 'figures_matlab');
    exportgraphics(f, fullfile(outDir, fileStem + ".png"), 'Resolution', 300);
    exportgraphics(f, fullfile(outDir, fileStem + ".pdf"), 'ContentType', 'vector');
    savefig(f, fullfile(outDir, fileStem + ".fig"));
    close(f);
end
