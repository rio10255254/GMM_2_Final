% MATLAB trajectory figures for the 30-step Raw / EDSR-x1 / NAFNet / MOSR comparison.
% The figure surface intentionally contains only the reference, methods, axes, and markers.

clear; clc; close all;

rootDir = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\Modern_Restoration_Benchmarks_20260719\evaluation\displacement_50x20x_edrs_nafnet_refresh_20260724\modern_50x20x_report\trajectory_figures';
dataPath = fullfile(rootDir, 'modern_model_displacement_trajectories.csv');
outDir = fullfile(rootDir, 'figures_matlab');
if ~isfolder(outDir); mkdir(outDir); end
T = readtable(dataPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');

for morphology = ["pillar", "via"]
    plotTrajectory(T, morphology, "50x_x_0p5um", "01", outDir);
    plotTrajectory(T, morphology, "50x_x_1um", "02", outDir);
    plotTrajectory(T, morphology, "20x_0p5um", "03", outDir);
    plotTrajectory(T, morphology, "20x_1um", "04", outDir);
end

function plotTrajectory(T, morphology, sequence, prefix, outDir)
    methods = ["Raw", "EDSR-x1", "NAFNet", "MOSR"];
    colors = [0.65 0.30 0.10; 0.46 0.36 0.65; 0.80 0.47 0.10; 0.00 0.45 0.74];
    markers = {'s', 'd', '^', 'o'};
    S = T(T.morphology == morphology & T.sequence == sequence, :);
    if height(S) ~= 120
        error('Expected 120 rows for %s / %s, found %d.', morphology, sequence, height(S));
    end
    raw = S(S.method == "Raw", :);
    raw = sortrows(raw, 'selected_step');
    piReference = raw.pi_reference_amplitude_um(1);

    f = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 940 590]);
    ax = axes(f); hold(ax, 'on');
    hRef = yline(ax, piReference, '--', 'Color', [0.35 0.35 0.35], 'LineWidth', 1.35);
    h = gobjects(numel(methods), 1);
    allValues = piReference;
    for i = 1:numel(methods)
        M = S(S.method == methods(i), :);
        M = sortrows(M, 'selected_step');
        h(i) = plot(ax, M.selected_step, M.measured_amplitude_um, '-', ...
            'Color', colors(i,:), 'LineWidth', 1.65, 'Marker', markers{i}, ...
            'MarkerSize', 5.5, 'MarkerFaceColor', 'w', 'MarkerEdgeColor', colors(i,:));
        if methods(i) == "NAFNet" || methods(i) == "MOSR"
            h(i).MarkerFaceColor = colors(i,:);
        end
        allValues = [allValues; M.measured_amplitude_um(~isnan(M.measured_amplitude_um))]; %#ok<AGROW>
    end
    xlim(ax, [1 30]);
    xticks(ax, [1 5 10 15 20 25 30]);
    xlabel(ax, '共同選取步次', 'FontName', 'Microsoft JhengHei', 'FontSize', 13);
    ylabel(ax, '量測位移幅度 (\mum)', 'FontName', 'Microsoft JhengHei', 'FontSize', 14);
    valuesMin = min(allValues);
    valuesMax = max(allValues);
    spread = max(valuesMax - valuesMin, 0.002);
    ylim(ax, [valuesMin - 0.18 * spread, valuesMax + 0.18 * spread]);
    grid(ax, 'on');
    ax.GridColor = [0.82 0.82 0.82];
    ax.GridAlpha = 0.8;
    ax.Box = 'off';
    ax.LineWidth = 0.9;
    ax.FontName = 'Microsoft JhengHei';
    ax.FontSize = 12;
    ax.TickDir = 'out';
    legend(ax, [hRef; h], ["PI 平台實際回授位移", methods], ...
        'Location', 'northoutside', 'Orientation', 'horizontal', 'NumColumns', 3, ...
        'Box', 'off', 'FontName', 'Microsoft JhengHei', 'FontSize', 11);
    drawnow;
    magnification = extractBefore(sequence, "_");
    stepSize = replace(extractAfter(sequence, "x_"), "p", ".");
    stem = prefix + "_" + magnification + "_" + morphology + "_" + stepSize + "_modern_model_trajectory";
    exportgraphics(f, fullfile(outDir, stem + ".png"), 'Resolution', 300);
    exportgraphics(f, fullfile(outDir, stem + ".pdf"), 'ContentType', 'vector');
    savefig(f, fullfile(outDir, stem + ".fig"));
    close(f);
end
