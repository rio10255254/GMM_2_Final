function outputs = make_base_unet_retest_figures(resultsRoot)
%MAKE_BASE_UNET_RETEST_FIGURES Export plain MATLAB-style retest figures.

if nargin < 1 || strlength(string(resultsRoot)) == 0
    resultsRoot = fullfile(fileparts(mfilename('fullpath')), ...
        'results_full_data_fixed_psf_tiled_e30');
end
resultsRoot = char(resultsRoot);
analysisDir = fullfile(resultsRoot, 'analysis');
figureDir = fullfile(resultsRoot, 'figures');
if ~isfolder(figureDir), mkdir(figureDir); end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Times New Roman');
set(groot, 'defaultTextFontName', 'Times New Roman');
set(groot, 'defaultAxesFontSize', 8.5);
set(groot, 'defaultAxesLineWidth', 0.8);
set(groot, 'defaultLineLineWidth', 1.25);

rawColor = [0.64, 0.33, 0.18];
baseColor = [0.35, 0.35, 0.35];
mosrColor = [0.10, 0.42, 0.67];
gridColor = [0.86, 0.86, 0.86];

edge = readtable(fullfile(analysisDir, 'base_unet_edge_width_summary_top30.csv'), ...
    'VariableNamingRule', 'preserve');
hypothesis = readtable(fullfile(analysisDir, 'base_unet_smoothing_hypothesis_summary.csv'), ...
    'VariableNamingRule', 'preserve');
methods = ["Raw", "Base U-Net", "MOSR"];
magnifications = ["50x", "20x"];

widthValues = nan(2, 3);
for magIndex = 1:2
    for methodIndex = 1:3
        row = edge(string(edge.magnification) == magnifications(magIndex) & ...
            string(edge.method) == methods(methodIndex), :);
        assert(height(row) == 1, 'Missing edge-width summary row.');
        widthValues(magIndex, methodIndex) = row.median_transition_width_nm;
    end
end

fig = figure('Visible', 'off', 'Units', 'inches', 'Position', [1, 1, 6.2, 3.7]);
ax = axes(fig); b = bar(ax, widthValues, 'grouped', 'EdgeColor', 'none');
b(1).FaceColor = rawColor; b(2).FaceColor = baseColor; b(3).FaceColor = mosrColor;
set(ax, 'XTickLabel', {'50\times', '20\times'}, 'TickLabelInterpreter', 'tex');
ylabel(ax, 'Median 10--90% edge width (nm)');
title(ax, 'Pillar-edge width over the locked 30-step populations', ...
    'FontSize', 10.5, 'FontWeight', 'normal');
subtitle(ax, 'Nine pillars per frame; identical radial rule and native grayscale', 'FontSize', 8);
legend(ax, cellstr(methods), 'Location', 'northoutside', 'Orientation', 'horizontal', ...
    'Box', 'off', 'NumColumns', 3);
ylim(ax, [0, max(widthValues(:)) * 1.28]);
for methodIndex = 1:3
    text(ax, b(methodIndex).XEndPoints, b(methodIndex).YEndPoints + 0.025 * max(widthValues(:)), ...
        compose('%.0f', b(methodIndex).YEndPoints), 'HorizontalAlignment', 'center', ...
        'FontSize', 7.5);
end
styleAxes(ax, gridColor);
edgePath = fullfile(figureDir, 'base_unet_retest_edge_width_top30.png');
exportFigure(fig, edgePath);

width = nan(3, 1); disagreement = nan(3, 1);
for methodIndex = 1:3
    row = hypothesis(string(hypothesis.method) == methods(methodIndex), :);
    assert(height(row) == 1, 'Missing smoothing-hypothesis row.');
    width(methodIndex) = row.median_transition_width_nm;
    disagreement(methodIndex) = row.mean_within_grid_nm;
end
fig = figure('Visible', 'off', 'Units', 'inches', 'Position', [1, 1, 5.5, 3.9]);
ax = axes(fig); hold(ax, 'on');
colors = [rawColor; baseColor; mosrColor];
for methodIndex = 1:3
    scatter(ax, width(methodIndex), disagreement(methodIndex), 52, colors(methodIndex, :), ...
        'filled', 'MarkerEdgeColor', 'w', 'LineWidth', 0.8);
    text(ax, width(methodIndex), disagreement(methodIndex), "  " + methods(methodIndex), ...
        'FontSize', 8, 'VerticalAlignment', 'middle');
end
xlabel(ax, 'Median 10--90% edge width (nm)');
ylabel(ax, 'Mean nine-pillar disagreement (nm)');
title(ax, 'Edge width versus displacement consistency', ...
    'FontSize', 10.5, 'FontWeight', 'normal');
subtitle(ax, 'Lower values are preferable on both axes', 'FontSize', 8);
xlim(ax, [max(0, min(width) * 0.86), max(width) * 1.16]);
ylim(ax, [0, max(disagreement) * 1.25]);
styleAxes(ax, gridColor);
tradeoffPath = fullfile(figureDir, 'base_unet_retest_edge_width_vs_disagreement.png');
exportFigure(fig, tradeoffPath);

summary = readtable(fullfile(analysisDir, 'learning_baseline_method_summary.csv'), ...
    'VariableNamingRule', 'preserve');
metricNames = {'cd_50x_median_abs_error_nm', 'cd_20x_median_abs_error_nm', ...
    'displacement_reference_mae_nm', 'nine_pillar_inconsistency_mean_nm'};
metricTitles = {'50\times CD median absolute error', '20\times CD median absolute error', ...
    'PI-feedback displacement mean absolute error', 'Nine-pillar displacement disagreement'};
metricFiles = {'base_unet_retest_cd_50x.png', 'base_unet_retest_cd_20x.png', ...
    'base_unet_retest_displacement_error.png', 'base_unet_retest_displacement_disagreement.png'};
metricOutputs = strings(4, 1);
for metricIndex = 1:4
    values = summary.(metricNames{metricIndex});
    labels = string(summary.method);
    fig = figure('Visible', 'off', 'Units', 'inches', 'Position', [1, 1, 5.6, 3.55]);
    ax = axes(fig); bars = bar(ax, values, 0.62, 'FaceColor', 'flat', 'EdgeColor', 'none');
    bars.CData = [rawColor; [0.78, 0.52, 0.08]; baseColor; mosrColor];
    set(ax, 'XTick', 1:height(summary), 'XTickLabel', cellstr(labels));
    ylabel(ax, 'Error (nm)');
    title(ax, metricTitles{metricIndex}, 'FontSize', 10.5, 'FontWeight', 'normal', ...
        'Interpreter', 'tex');
    ylim(ax, [0, max(values) * 1.25]);
    text(ax, 1:height(summary), values + 0.025 * max(values), compose('%.1f', values), ...
        'HorizontalAlignment', 'center', 'FontSize', 7.5);
    styleAxes(ax, gridColor);
    metricOutputs(metricIndex) = fullfile(figureDir, metricFiles{metricIndex});
    exportFigure(fig, metricOutputs(metricIndex));
end

history = readtable(fullfile(resultsRoot, 'training_history.csv'), ...
    'VariableNamingRule', 'preserve');
fig = figure('Visible', 'off', 'Units', 'inches', 'Position', [1, 1, 5.8, 3.55]);
ax = axes(fig); hold(ax, 'on');
plot(ax, history.epoch, history.train_loss, '-', 'Color', baseColor, ...
    'DisplayName', 'Training');
valid = isfinite(history.val_loss);
plot(ax, history.epoch(valid), history.val_loss(valid), '-o', 'Color', mosrColor, ...
    'MarkerFaceColor', 'w', 'MarkerSize', 4, 'DisplayName', 'Validation');
xlabel(ax, 'Epoch'); ylabel(ax, 'Reconstruction loss');
title(ax, 'Base U-Net training and validation history', ...
    'FontSize', 10.5, 'FontWeight', 'normal');
legend(ax, 'Location', 'northeast', 'Box', 'off');
xlim(ax, [1, max(history.epoch)]); ylim(ax, [0, max([history.train_loss; history.val_loss(valid)]) * 1.12]);
styleAxes(ax, gridColor);
historyPath = fullfile(figureDir, 'base_unet_retest_training_history.png');
exportFigure(fig, historyPath);

controlPath = fullfile(resultsRoot, 'smoothing_control', ...
    'gaussian_smoothing_control_summary.csv');
controlOutputs = strings(0, 1);
if isfile(controlPath)
    control = readtable(controlPath, 'VariableNamingRule', 'preserve');
    rawSummary = summary(string(summary.method) == "Raw", :);
    rawEdge50 = edge(string(edge.method) == "Raw" & string(edge.magnification) == "50x", :);
    rawEdge20 = edge(string(edge.method) == "Raw" & string(edge.magnification) == "20x", :);
    sigma = [0; control.sigma_px];
    edge50 = [rawEdge50.median_transition_width_nm; ...
        control.median_transition_width_nm_50x];
    edge20 = [rawEdge20.median_transition_width_nm; ...
        control.median_transition_width_nm_20x];
    disagreementControl = [rawSummary.nine_pillar_inconsistency_mean_nm; ...
        control.nine_pillar_inconsistency_mean_nm];

    controlOutputs(1) = fullfile(figureDir, 'gaussian_smoothing_edge_width_50x.png');
    plotControl(sigma, edge50, 'Gaussian smoothing applied to Raw: 50\times edge width', ...
        'Median 10--90% edge width (nm)', controlOutputs(1), rawColor, gridColor);
    controlOutputs(2) = fullfile(figureDir, 'gaussian_smoothing_edge_width_20x.png');
    plotControl(sigma, edge20, 'Gaussian smoothing applied to Raw: 20\times edge width', ...
        'Median 10--90% edge width (nm)', controlOutputs(2), rawColor, gridColor);
    controlOutputs(3) = fullfile(figureDir, ...
        'gaussian_smoothing_displacement_disagreement.png');
    plotControl(sigma, disagreementControl, ...
        'Gaussian smoothing applied to Raw: displacement consistency', ...
        'Mean nine-pillar disagreement (nm)', controlOutputs(3), rawColor, gridColor);
end

outputs = struct('edge_width', edgePath, 'tradeoff', tradeoffPath, ...
    'metrics', metricOutputs, 'training_history', historyPath, ...
    'smoothing_controls', controlOutputs);
end

function plotControl(sigma, values, titleText, yText, outputPath, color, gridColor)
fig = figure('Visible', 'off', 'Units', 'inches', 'Position', [1, 1, 5.7, 3.55]);
ax = axes(fig);
plot(ax, sigma, values, '-o', 'Color', color, 'MarkerFaceColor', 'w', ...
    'MarkerSize', 4.5, 'LineWidth', 1.25);
xlabel(ax, 'Gaussian standard deviation (pixel)'); ylabel(ax, yText);
title(ax, titleText, 'FontSize', 10.5, 'FontWeight', 'normal', 'Interpreter', 'tex');
subtitle(ax, 'The zero point is the unfiltered Raw image', 'FontSize', 8);
xlim(ax, [0, max(sigma) * 1.06]);
ylim(ax, [0, max(values) * 1.16]);
labelX = sigma;
labelX(1) = sigma(1) + 0.045 * max(sigma);
for index = 1:numel(values)
    text(ax, labelX(index), values(index) + 0.025 * max(values), compose('%.1f', values(index)), ...
        'HorizontalAlignment', 'center', 'FontSize', 7.5);
end
styleAxes(ax, gridColor);
exportFigure(fig, outputPath);
end

function styleAxes(ax, gridColor)
ax.Box = 'off'; ax.TickDir = 'out'; ax.Layer = 'top';
ax.XColor = [0.16, 0.16, 0.16]; ax.YColor = [0.16, 0.16, 0.16];
ax.GridColor = gridColor; ax.GridAlpha = 0.85; ax.XGrid = 'off'; ax.YGrid = 'on';
end

function exportFigure(fig, path)
set(fig, 'Renderer', 'painters');
axesList = findall(fig, 'Type', 'axes');
for index = 1:numel(axesList), axtoolbar(axesList(index), {}); end
exportgraphics(fig, path, 'Resolution', 300, 'BackgroundColor', 'white');
close(fig);
end
