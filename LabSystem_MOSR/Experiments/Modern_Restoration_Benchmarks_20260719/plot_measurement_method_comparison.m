PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
% Candidate figures for comparing the original gradient-peak displacement
% estimator with the multi-threshold isocontour estimator.
% The thesis document is not edited by this script.

clear; clc; close all;

rootDir = fullfile(PROJECT_ROOT, 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/measurement_method_comparison_20260724');
outDir = fullfile(rootDir, 'figures_matlab');
if ~isfolder(outDir); mkdir(outDir); end

trajectoryPath = fullfile(rootDir, 'new_isocontour_trajectories.csv');
summaryPath = fullfile(rootDir, 'measurement_summary_by_segment.csv');
pairedPath = fullfile(rootDir, 'paired_edsr_mosr_by_measurement.csv');
agreementPath = fullfile(rootDir, 'matched_step_measurement_agreement.csv');
thresholdPath = fullfile(rootDir, 'new_isocontour_threshold_sensitivity.csv');
syntheticPath = fullfile(rootDir, 'synthetic_known_shift_summary.csv');

T = readtable(trajectoryPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
S = readtable(summaryPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
P = readtable(pairedPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
A = readtable(agreementPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
H = readtable(thresholdPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
Y = readtable(syntheticPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');

methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
sequenceOrder = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
morphologies = ["pillar", "via"];

% Use a shared y range for pillar and via within each magnification/step pair.
trajectoryLimits = containers.Map('KeyType', 'char', 'ValueType', 'any');
for sequence = sequenceOrder
    q = T(T.sequence == sequence, :);
    values = [q.measured_amplitude_um; q.pi_reference_amplitude_um];
    centerValue = median(q.pi_reference_amplitude_um);
    extent = max(abs(values - centerValue));
    padding = max(0.004, extent * 0.12);
    trajectoryLimits(char(sequence)) = [min(values) - padding, max(values) + padding];
end

trajectorySpecs = {
    "pillar", "50x_x_0p5um", "01_50x_pillar_0p5um_isocontour_trajectory";
    "pillar", "50x_x_1um",   "02_50x_pillar_1p0um_isocontour_trajectory";
    "pillar", "20x_0p5um",   "03_20x_pillar_0p5um_isocontour_trajectory";
    "pillar", "20x_1um",     "04_20x_pillar_1p0um_isocontour_trajectory";
    "via",    "50x_x_0p5um", "05_50x_via_0p5um_isocontour_trajectory";
    "via",    "50x_x_1um",   "06_50x_via_1p0um_isocontour_trajectory";
    "via",    "20x_0p5um",   "07_20x_via_0p5um_isocontour_trajectory";
    "via",    "20x_1um",     "08_20x_via_1p0um_isocontour_trajectory";
};
for i = 1:size(trajectorySpecs, 1)
    plotTrajectory( ...
        T, trajectorySpecs{i,1}, trajectorySpecs{i,2}, ...
        trajectoryLimits(char(trajectorySpecs{i,2})), ...
        outDir, trajectorySpecs{i,3});
end

plotSummaryMetric( ...
    S, "pillar", "error_sd_nm", "", "", ...
    '步距殘差標準差 (nm)', outDir, ...
    "09_pillar_isocontour_error_sd_50x20x", false);
plotSummaryMetric( ...
    S, "pillar", "mae_nm", "mae_ci95_low_nm", "mae_ci95_high_nm", ...
    '相對PI平台實際回授位移的平均絕對誤差 (nm)', outDir, ...
    "10_pillar_isocontour_mae_50x20x", true);
plotSummaryMetric( ...
    S, "via", "error_sd_nm", "", "", ...
    '步距殘差標準差 (nm)', outDir, ...
    "11_via_isocontour_error_sd_50x20x", false);
plotSummaryMetric( ...
    S, "via", "mae_nm", "mae_ci95_low_nm", "mae_ci95_high_nm", ...
    '相對PI平台實際回授位移的平均絕對誤差 (nm)', outDir, ...
    "12_via_isocontour_mae_50x20x", true);

plotPairedAdvantage(P, outDir, "13_original_new_mosr_advantage");
plotMeasurementDisagreement(A, outDir, "14_original_new_measurement_disagreement");

thresholdSpecs = {
    "pillar", "50x", "15_50x_pillar_threshold_sensitivity";
    "pillar", "20x", "16_20x_pillar_threshold_sensitivity";
    "via",    "50x", "17_50x_via_threshold_sensitivity";
    "via",    "20x", "18_20x_via_threshold_sensitivity";
};
for i = 1:size(thresholdSpecs, 1)
    plotThresholdSensitivity( ...
        H, thresholdSpecs{i,1}, thresholdSpecs{i,2}, ...
        outDir, thresholdSpecs{i,3});
end

plotSynthetic(Y, "mae_px", '平均絕對位移誤差 (pixel)', ...
    outDir, "19_synthetic_known_shift_mae");
plotSynthetic(Y, "p95_absolute_error_px", '第95百分位位移誤差 (pixel)', ...
    outDir, "20_synthetic_known_shift_p95");

fprintf('Exported 20 candidate figures to %s\n', outDir);


function plotTrajectory(T, morphology, sequence, yLimits, outDir, fileStem)
    methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
    labels = ["Raw", "NAFNet", "EDSR-x1", "MOSR"];
    colors = [
        0.67 0.31 0.12;
        0.82 0.49 0.05;
        0.45 0.36 0.66;
        0.00 0.42 0.69
    ];
    markers = {'s', '^', 'd', 'o'};
    markerFaces = {'w', colors(2,:), 'w', colors(4,:)};
    q = T(T.morphology == morphology & T.sequence == sequence, :);
    if height(q) ~= 120
        error('Expected 120 rows for %s / %s.', morphology, sequence);
    end

    f = createFigure();
    ax = axes(f); hold(ax, 'on');
    reference = q(q.method == "Raw", :);
    reference = sortrows(reference, "selected_step");
    handles = gobjects(1, 5);
    handles(1) = plot(ax, reference.selected_step, reference.pi_reference_amplitude_um, ...
        '--', 'Color', [0.42 0.42 0.42], 'LineWidth', 1.4);
    for j = 1:numel(methods)
        row = q(q.method == methods(j), :);
        row = sortrows(row, "selected_step");
        handles(j+1) = plot(ax, row.selected_step, row.measured_amplitude_um, ...
            '-', 'Color', colors(j,:), 'LineWidth', 1.35, ...
            'Marker', markers{j}, 'MarkerSize', 5.0, ...
            'MarkerFaceColor', markerFaces{j}, ...
            'MarkerEdgeColor', colors(j,:));
    end
    formatAxes(ax);
    xlim(ax, [1 30]);
    xticks(ax, [1 5 10 15 20 25 30]);
    ylim(ax, yLimits);
    xlabel(ax, '共同選取步次', 'FontSize', 13);
    ylabel(ax, '量測位移幅度 (\mum)', 'FontSize', 14);
    legend(ax, handles, ["PI平台實際回授位移", labels], ...
        'Location', 'northoutside', 'Orientation', 'horizontal', ...
        'NumColumns', 3, 'Box', 'off', 'FontSize', 11);
    exportFigure(f, outDir, fileStem);
end


function plotSummaryMetric(S, morphology, metricName, lowName, highName, ...
        yLabelText, outDir, fileStem, showCI)
    methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
    labels = ["Raw", "NAFNet", "EDSR-x1", "MOSR"];
    magnifications = ["50x", "20x"];
    colors = [
        0.67 0.31 0.12;
        0.82 0.49 0.05;
        0.45 0.36 0.66;
        0.00 0.42 0.69
    ];
    q = S(S.measurement == "new_isocontour" & S.morphology == morphology, :);
    values = nan(2, 4);
    lower = nan(2, 4);
    upper = nan(2, 4);
    for i = 1:2
        for j = 1:4
            row = q(q.magnification == magnifications(i) & q.method == methods(j), :);
            if height(row) ~= 1
                error('Missing summary row for %s / %s / %s.', ...
                    morphology, magnifications(i), methods(j));
            end
            values(i,j) = row.(metricName);
            if showCI
                lower(i,j) = row.(lowName);
                upper(i,j) = row.(highName);
            end
        end
    end

    f = createFigure();
    ax = axes(f); hold(ax, 'on');
    b = bar(ax, 1:2, values, 'grouped', 'BarWidth', 0.82);
    for j = 1:4
        b(j).FaceColor = colors(j,:);
        b(j).EdgeColor = 'none';
        if showCI
            errorbar(ax, b(j).XEndPoints, values(:,j), ...
                values(:,j) - lower(:,j), upper(:,j) - values(:,j), ...
                'LineStyle', 'none', 'Color', [0.18 0.18 0.18], ...
                'LineWidth', 0.8, 'CapSize', 5);
        end
    end
    formatAxes(ax);
    ax.XTick = 1:2;
    ax.XTickLabel = {'50×', '20×'};
    ylabel(ax, yLabelText, 'FontSize', 14);
    xlabel(ax, '物鏡倍率；每組合併0.5與1.0 \mum序列', 'FontSize', 13);
    legend(ax, b, labels, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'NumColumns', 4, ...
        'Box', 'off', 'FontSize', 11);
    yMax = max(values(:));
    if showCI; yMax = max(upper(:)); end
    ylim(ax, [0, yMax * 1.18]);
    exportFigure(f, outDir, fileStem);
end


function plotPairedAdvantage(P, outDir, fileStem)
    measurements = ["original_gradient", "new_isocontour"];
    labels = ["原最大斜率法", "新跨閾值法"];
    colors = [0.48 0.48 0.48; 0.00 0.42 0.69];
    scopes = {
        "pillar", "50x";
        "pillar", "20x";
        "via",    "50x";
        "via",    "20x"
    };
    values = nan(4,2);
    lower = nan(4,2);
    upper = nan(4,2);
    for i = 1:4
        for j = 1:2
            row = P(P.measurement == measurements(j) ...
                & P.morphology == scopes{i,1} ...
                & P.magnification == scopes{i,2}, :);
            values(i,j) = row.advantage_for_mosr_nm;
            lower(i,j) = row.ci95_low_nm;
            upper(i,j) = row.ci95_high_nm;
        end
    end

    f = createFigure();
    ax = axes(f); hold(ax, 'on');
    b = bar(ax, 1:4, values, 'grouped', 'BarWidth', 0.78);
    for j = 1:2
        b(j).FaceColor = colors(j,:);
        b(j).EdgeColor = 'none';
        errorbar(ax, b(j).XEndPoints, values(:,j), ...
            values(:,j) - lower(:,j), upper(:,j) - values(:,j), ...
            'LineStyle', 'none', 'Color', [0.15 0.15 0.15], ...
            'LineWidth', 0.9, 'CapSize', 6);
    end
    yline(ax, 0, '-', 'Color', [0.20 0.20 0.20], 'LineWidth', 1.0);
    formatAxes(ax);
    ax.XTick = 1:4;
    ax.XTickLabel = {'50×柱狀結構', '20×柱狀結構', ...
        '50×通孔結構', '20×通孔結構'};
    ylabel(ax, 'MAE差值：EDSR-x1−MOSR (nm)', 'FontSize', 14);
    legend(ax, b, labels, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'Box', 'off', 'FontSize', 11);
    limit = max(abs([lower(:); upper(:)]));
    ylim(ax, [-1 1] * max(0.5, limit * 1.15));
    exportFigure(f, outDir, fileStem);
end


function plotMeasurementDisagreement(A, outDir, fileStem)
    methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
    labels = ["Raw", "NAFNet", "EDSR-x1", "MOSR"];
    colors = [
        0.67 0.31 0.12;
        0.82 0.49 0.05;
        0.45 0.36 0.66;
        0.00 0.42 0.69
    ];
    scopes = {
        "pillar", "50x";
        "pillar", "20x";
        "via",    "50x";
        "via",    "20x"
    };
    values = nan(4,4);
    for i = 1:4
        for j = 1:4
            row = A(A.morphology == scopes{i,1} ...
                & A.magnification_new == scopes{i,2} ...
                & A.method == methods(j), :);
            values(i,j) = median(row.absolute_method_disagreement_nm);
        end
    end

    f = createFigure();
    ax = axes(f); hold(ax, 'on');
    b = bar(ax, 1:4, values, 'grouped', 'BarWidth', 0.82);
    for j = 1:4
        b(j).FaceColor = colors(j,:);
        b(j).EdgeColor = 'none';
    end
    formatAxes(ax);
    ax.XTick = 1:4;
    ax.XTickLabel = {'50×柱狀結構', '20×柱狀結構', ...
        '50×通孔結構', '20×通孔結構'};
    ylabel(ax, '兩種量測法的位移差異中位數 (nm)', 'FontSize', 14);
    legend(ax, b, labels, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'NumColumns', 4, ...
        'Box', 'off', 'FontSize', 11);
    ylim(ax, [0, max(values(:)) * 1.18]);
    exportFigure(f, outDir, fileStem);
end


function plotThresholdSensitivity(H, morphology, magnification, outDir, fileStem)
    methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
    labels = ["Raw", "NAFNet", "EDSR-x1", "MOSR"];
    colors = [
        0.67 0.31 0.12;
        0.82 0.49 0.05;
        0.45 0.36 0.66;
        0.00 0.42 0.69
    ];
    markers = {'s', '^', 'd', 'o'};
    markerFaces = {'w', colors(2,:), 'w', colors(4,:)};
    q = H(H.morphology == morphology & H.magnification == magnification, :);

    f = createFigure();
    ax = axes(f); hold(ax, 'on');
    handles = gobjects(1,4);
    for j = 1:4
        row = sortrows(q(q.method == methods(j), :), "level");
        handles(j) = plot(ax, row.level * 100, row.mae_nm, ...
            '-', 'Color', colors(j,:), 'LineWidth', 1.5, ...
            'Marker', markers{j}, 'MarkerSize', 5.5, ...
            'MarkerFaceColor', markerFaces{j}, ...
            'MarkerEdgeColor', colors(j,:));
    end
    formatAxes(ax);
    xlim(ax, [28 72]);
    xticks(ax, 30:10:70);
    xlabel(ax, '局部對比閾值 (%)', 'FontSize', 13);
    ylabel(ax, '平均絕對位移誤差 (nm)', 'FontSize', 14);
    legend(ax, handles, labels, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'NumColumns', 4, ...
        'Box', 'off', 'FontSize', 11);
    exportFigure(f, outDir, fileStem);
end


function plotSynthetic(Y, metricName, yLabelText, outDir, fileStem)
    measurements = ["original_gradient", "new_isocontour"];
    labels = ["原最大斜率法", "新跨閾值法"];
    colors = [0.42 0.42 0.42; 0.00 0.42 0.69];
    styles = {'--s', '-o'};
    f = createFigure();
    ax = axes(f); hold(ax, 'on');
    handles = gobjects(1,2);
    for j = 1:2
        row = sortrows(Y(Y.measurement == measurements(j), :), "ringing_strength");
        faceColor = colors(j,:);
        if j == 1; faceColor = 'w'; end
        handles(j) = plot(ax, row.ringing_strength, row.(metricName), styles{j}, ...
            'Color', colors(j,:), 'LineWidth', 1.6, 'MarkerSize', 6, ...
            'MarkerFaceColor', faceColor);
    end
    formatAxes(ax);
    xlim(ax, [-0.08 1.68]);
    xticks(ax, [0 0.8 1.6]);
    xlabel(ax, '合成振鈴強度', 'FontSize', 13);
    ylabel(ax, yLabelText, 'FontSize', 14);
    legend(ax, handles, labels, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'Box', 'off', 'FontSize', 11);
    exportFigure(f, outDir, fileStem);
end


function f = createFigure()
    f = figure('Visible', 'off', 'Color', 'w', ...
        'Position', [80 80 1000 610], ...
        'Renderer', 'painters');
end


function formatAxes(ax)
    grid(ax, 'on');
    ax.GridColor = [0.83 0.83 0.83];
    ax.GridAlpha = 0.78;
    ax.Box = 'off';
    ax.FontName = 'Microsoft JhengHei';
    ax.FontSize = 12;
    ax.LineWidth = 0.9;
    ax.TickDir = 'out';
    ax.XColor = [0.18 0.18 0.18];
    ax.YColor = [0.18 0.18 0.18];
end


function exportFigure(f, outDir, fileStem)
    drawnow;
    exportgraphics(f, fullfile(outDir, fileStem + ".png"), 'Resolution', 300);
    exportgraphics(f, fullfile(outDir, fileStem + ".pdf"), 'ContentType', 'vector');
    savefig(f, fullfile(outDir, fileStem + ".fig"));
    close(f);
end
