function plot_100mg_linewidth_generalization
% Publication-style figures for the 100MG line-pattern generalization audit.

scriptDir = fileparts(mfilename('fullpath'));
rootDir = fileparts(scriptDir);
tableDir = fullfile(rootDir, 'tables');
imageDir = fullfile(rootDir, 'images');
figureDir = fullfile(rootDir, 'figures');
if ~exist(figureDir, 'dir')
    mkdir(figureDir);
end

frameT = readtable(fullfile(tableDir, 'line_frame_metrics.csv'), ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
stepT = readtable(fullfile(tableDir, 'line_displacement_per_step.csv'), ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
agreementT = readtable(fullfile(tableDir, ...
    'line_displacement_all_available_reconstruction_vs_raw.csv'), ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
frameT.median_overshoot_percent = 100 .* frameT.median_overshoot_ratio;

methods = ["Raw", "Base U-Net", "MOSR"];
orientations = ["vertical_lines", "horizontal_lines"];
orientationLabels = ["Vertical lines", "Horizontal lines"];
colors = [0.60 0.29 0.13; 0.35 0.35 0.35; 0.07 0.38 0.66];
markers = {'s', '^', 'o'};
lineStyles = {'--', '-.', '-'};

plotRoiMap(rootDir, figureDir);
plotNativeCrops(imageDir, figureDir, methods, orientations, colors);

plotGroupedMedianIqr(frameT, methods, orientations, orientationLabels, colors, ...
    'median_transition_width_nm', '10--90% transition width (nm)', ...
    'Line-edge transition width', ...
    'Median and interquartile range across 60 selected frames; lower is sharper', ...
    '07_edge_transition_width.png', figureDir, '%.0f');

plotGroupedMedianIqr(frameT, methods, orientations, orientationLabels, colors, ...
    'median_normalized_slope_per_px', 'Normalized edge slope (pixel^{-1})', ...
    'Normalized line-edge slope', ...
    'Median and interquartile range across 60 selected frames; higher is steeper', ...
    '08_normalized_edge_slope.png', figureDir, '%.3f');

plotGroupedMedianIqr(frameT, methods, orientations, orientationLabels, colors, ...
    'median_native_contrast_8bit', 'Native edge contrast (8-bit levels)', ...
    'Native line-edge contrast', ...
    'No per-image contrast stretching; median and interquartile range across 60 frames', ...
    '09_native_edge_contrast.png', figureDir, '%.0f');

plotGroupedMedianIqr(frameT, methods, orientations, orientationLabels, colors, ...
    'median_overshoot_percent', 'Local edge overshoot (%)', ...
    'Local overshoot near the line edge', ...
    'Median and interquartile range across 60 selected frames; lower indicates less ringing', ...
    '09b_local_edge_overshoot.png', figureDir, '%.2f');

plotDistribution(frameT, methods, orientations, orientationLabels, colors, ...
    'apparent_dark_line_width_um', 'Apparent dark-line width (\mum)', ...
    'Apparent line width at the 50% crossing', ...
    'Optical measurement only; no SEM line-width reference is available', ...
    '10_apparent_line_width_distribution.png', figureDir);

plotDistribution(frameT, methods, orientations, orientationLabels, colors, ...
    'apparent_pitch_um', 'Apparent pitch (\mum)', ...
    'Apparent line-pattern pitch', ...
    'Median-profile measurement across the same 60 selected frames', ...
    '11_apparent_pitch_distribution.png', figureDir);

plotStepTrace(stepT, '50x_x_0p5um', 0.5, methods, colors, markers, lineStyles, ...
    '12_displacement_trace_0p5um.png', figureDir);
plotStepTrace(stepT, '50x_x_1um', 1.0, methods, colors, markers, lineStyles, ...
    '13_displacement_trace_1p0um.png', figureDir);

plotDisplacementBars(stepT, methods, colors, 'boundary_abs_error_nm', ...
    'Mean absolute error (nm)', 'Shared-edge displacement error', ...
    'Individual 50% line-edge crossings; 30 pre-locked steps per sequence', ...
    '14_boundary_displacement_mae.png', figureDir);

plotDisplacementBars(stepT, methods, colors, 'profile_abs_error_nm', ...
    'Mean absolute error (nm)', 'Full-profile displacement error', ...
    'Independent subpixel profile correlation; 30 pre-locked steps per sequence', ...
    '15_profile_displacement_mae.png', figureDir);

plotDisplacementBars(stepT, methods, colors, 'within_edge_mad_nm', ...
    'Median within-frame edge disagreement (nm)', ...
    'Agreement among individual line edges', ...
    'Median absolute deviation across usable edges; lower is more internally consistent', ...
    '16_within_edge_disagreement.png', figureDir);

plotAllStepAgreement(agreementT, colors, ...
    '17_all_step_reconstruction_vs_raw_agreement.png', figureDir);

fprintf('Exported %d PNG figures to %s\n', numel(dir(fullfile(figureDir, '*.png'))), figureDir);
end


function plotRoiMap(rootDir, figureDir)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))))));
rawPath = fullfile(fileparts(fileparts(fileparts(fileparts(rootDir)))), ...
    '20260702_100MG_displacement_analysis', 'raw_inputs', 'x_0p5um', 'bmp', 'frame_0000.bmp');
if ~exist(rawPath, 'file')
    rawPath = fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp');
end
I = imread(rawPath);
fig = newFigure([980 760]);
imshow(I, [0 255]); hold on;
rectangle('Position', [101 91 700 560], 'EdgeColor', [0.85 0.38 0.05], 'LineWidth', 2.2);
rectangle('Position', [1051 851 700 560], 'EdgeColor', [0.15 0.48 0.22], 'LineWidth', 2.2);
text(118, 126, 'Vertical-line region', 'Color', [0.85 0.38 0.05], ...
    'FontName', 'Times New Roman', 'FontSize', 10, 'FontWeight', 'bold', ...
    'BackgroundColor', [1 1 1], 'Margin', 2);
text(1068, 886, 'Horizontal-line region', 'Color', [0.15 0.48 0.22], ...
    'FontName', 'Times New Roman', 'FontSize', 10, 'FontWeight', 'bold', ...
    'BackgroundColor', [1 1 1], 'Margin', 2);
title('100MG line-pattern validation regions', 'FontName', 'Times New Roman', ...
    'FontSize', 12, 'FontWeight', 'normal');
exportFigure(fig, fullfile(figureDir, '00_line_pattern_roi_locations.png'));
end


function plotNativeCrops(imageDir, figureDir, methods, orientations, colors) %#ok<INUSD>
fileMethods = ["raw", "base_u_net", "mosr"];
methodLabels = ["Raw", "Base U-Net", "MOSR"];
orientationLabels = ["Vertical-line region", "Horizontal-line region"];
index = 1;
for oi = 1:numel(orientations)
    for mi = 1:numel(methods)
        source = fullfile(imageDir, orientations(oi) + "_" + fileMethods(mi) + ".png");
        I = imread(source);
        fig = newFigure([840 700]);
        imagesc(I); axis image off; colormap(gray(256)); clim([0 255]); hold on;
        [height, width] = size(I);
        scaleLength = 10 / 0.069;
        x2 = width - 25;
        x1 = x2 - scaleLength;
        y = height - 28;
        plot([x1 x2], [y y], '-', 'Color', [0 0 0], 'LineWidth', 5.0);
        plot([x1 x2], [y y], '-', 'Color', [1 1 1], 'LineWidth', 2.5);
        text((x1+x2)/2, y-14, '10 \mum', 'Color', [1 1 1], ...
            'HorizontalAlignment', 'center', 'FontName', 'Times New Roman', ...
            'FontSize', 9, 'FontWeight', 'bold', 'BackgroundColor', [0 0 0], 'Margin', 1);
        title(sprintf('%s: %s', orientationLabels(oi), methodLabels(mi)), ...
            'FontName', 'Times New Roman', 'FontSize', 12, 'FontWeight', 'normal', ...
            'Color', [0.12 0.12 0.12]);
        filename = sprintf('%02d_%s_%s.png', index, char(orientations(oi)), char(fileMethods(mi)));
        exportFigure(fig, fullfile(figureDir, filename));
        index = index + 1;
    end
end
end


function plotGroupedMedianIqr(T, methods, orientations, orientationLabels, colors, ...
    metric, yLabel, chartTitle, chartSubtitle, filename, figureDir, valueFormat)
[medianValues, lowerErrors, upperErrors] = groupedStats(T, methods, orientations, metric);
fig = newFigure([900 620]);
x = categorical(cellstr(orientationLabels));
x = reordercats(x, cellstr(orientationLabels));
b = bar(x, medianValues, 'grouped', 'BarWidth', 0.76); hold on;
for mi = 1:numel(methods)
    b(mi).FaceColor = colors(mi,:);
    b(mi).EdgeColor = [0.20 0.20 0.20];
    b(mi).LineWidth = 0.7;
end
drawnow;
for mi = 1:numel(methods)
    errorbar(b(mi).XEndPoints, medianValues(:,mi), lowerErrors(:,mi), upperErrors(:,mi), ...
        'Color', [0.12 0.12 0.12], 'LineStyle', 'none', 'LineWidth', 1.0, 'CapSize', 6);
    for oi = 1:numel(orientations)
        text(b(mi).XEndPoints(oi), medianValues(oi,mi) + upperErrors(oi,mi), ...
            sprintf(['  ' valueFormat], medianValues(oi,mi)), 'Rotation', 0, ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
            'FontName', 'Times New Roman', 'FontSize', 8, 'Color', [0.16 0.16 0.16]);
    end
end
ylabel(yLabel);
title(chartTitle, 'FontWeight', 'normal');
subtitle(chartSubtitle);
legend(cellstr(methods), 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
styleAxes(gca);
ylim([0, max(medianValues + upperErrors, [], 'all') * 1.22]);
exportFigure(fig, fullfile(figureDir, filename));
end


function plotDistribution(T, methods, orientations, orientationLabels, colors, ...
    metric, yLabel, chartTitle, chartSubtitle, filename, figureDir)
fig = newFigure([980 620]); hold on;
positions = 1:6;
labels = strings(1, 6);
allValues = [];
positionIndex = 0;
for oi = 1:numel(orientations)
    for mi = 1:numel(methods)
        positionIndex = positionIndex + 1;
        mask = T.orientation == orientations(oi) & T.method == methods(mi);
        values = T.(metric)(mask);
        values = values(isfinite(values));
        allValues = [allValues; values]; %#ok<AGROW>
        boxchart(repmat(positions(positionIndex), numel(values), 1), values, ...
            'BoxFaceColor', colors(mi,:), 'BoxFaceAlpha', 0.55, ...
            'MarkerColor', colors(mi,:), 'WhiskerLineColor', [0.25 0.25 0.25], ...
            'BoxWidth', 0.58);
        labels(positionIndex) = methods(mi);
    end
end
xline(3.5, '-', 'Color', [0.65 0.65 0.65], 'LineWidth', 0.8);
xlim([0.4 6.6]); xticks(positions); xticklabels(labels);
ylabel(yLabel);
title(chartTitle, 'FontWeight', 'normal');
subtitle(chartSubtitle);
styleAxes(gca);
spread = max(allValues) - min(allValues);
if spread <= 0, spread = max(abs(allValues)) * 0.02; end
ylim([min(allValues) - 0.22*spread, max(allValues) + 0.42*spread]);
limits = ylim;
text(2, limits(2) - 0.06*diff(limits), 'Vertical lines', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
    'FontName', 'Times New Roman', 'FontSize', 9, 'FontWeight', 'bold', ...
    'BackgroundColor', [1 1 1], 'Margin', 1);
text(5, limits(2) - 0.06*diff(limits), 'Horizontal lines', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'top', ...
    'FontName', 'Times New Roman', 'FontSize', 9, 'FontWeight', 'bold', ...
    'BackgroundColor', [1 1 1], 'Margin', 1);
exportFigure(fig, fullfile(figureDir, filename));
end


function plotStepTrace(T, sequenceName, nominalStep, methods, colors, markers, lineStyles, filename, figureDir)
fig = newFigure([940 620]); hold on;
for mi = 1:numel(methods)
    subset = T(T.sequence == sequenceName & T.method == methods(mi), :);
    subset = sortrows(subset, 'end_frame_index');
    plot(1:height(subset), subset.boundary_step_um, ...
        'Color', colors(mi,:), 'LineStyle', lineStyles{mi}, 'LineWidth', 1.25, ...
        'Marker', markers{mi}, 'MarkerSize', 4.2, 'MarkerFaceColor', colors(mi,:));
end
yline(nominalStep, ':', 'PI reference', 'Color', [0.12 0.12 0.12], ...
    'LineWidth', 1.3, 'LabelHorizontalAlignment', 'right');
xlim([1 30]); xticks([1 5 10 15 20 25 30]);
ylim([nominalStep-0.030, nominalStep+0.030]);
xlabel('Selected displacement step (1 to 30)');
ylabel('Measured step (\mum)');
title(sprintf('Line-edge displacement: %.1f µm sequence', nominalStep), 'FontWeight', 'normal');
subtitle('Same pre-locked 30 steps; vertical-line region; 50% crossing estimator');
legend(cellstr(methods), 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
styleAxes(gca);
exportFigure(fig, fullfile(figureDir, filename));
end


function plotAllStepAgreement(T, colors, filename, figureDir)
methods = ["Base U-Net", "MOSR"];
estimators = ["shared_edge", "full_profile"];
estimatorLabels = ["Shared edges", "Full profile"];
values = nan(2, 2);
for ei = 1:numel(estimators)
    for mi = 1:numel(methods)
        mask = T.scope == "pooled_all_available_steps" & ...
            T.estimator == estimators(ei) & T.candidate_method == methods(mi);
        values(ei,mi) = T.mean_absolute_difference_from_raw_nm(mask);
    end
end
fig = newFigure([840 600]);
x = categorical(cellstr(estimatorLabels));
x = reordercats(x, cellstr(estimatorLabels));
b = bar(x, values, 'grouped', 'BarWidth', 0.72); hold on;
b(1).FaceColor = colors(2,:);
b(2).FaceColor = colors(3,:);
for mi = 1:2
    b(mi).EdgeColor = [0.20 0.20 0.20];
    b(mi).LineWidth = 0.7;
end
drawnow;
for mi = 1:2
    for ei = 1:2
        text(b(mi).XEndPoints(ei), values(ei,mi), sprintf('  %.2f', values(ei,mi)), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
            'FontName', 'Times New Roman', 'FontSize', 8, 'Color', [0.16 0.16 0.16]);
    end
end
ylabel('Mean absolute difference from Raw (nm)');
title('Displacement retained after reconstruction', 'FontWeight', 'normal');
subtitle('All available steps: 98 shared-edge pairs and 99 full-profile pairs; agreement audit, not absolute accuracy');
legend(cellstr(methods), 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
styleAxes(gca);
ylim([0 max(values, [], 'all') * 1.35]);
exportFigure(fig, fullfile(figureDir, filename));
end


function plotDisplacementBars(T, methods, colors, metric, yLabel, chartTitle, chartSubtitle, filename, figureDir)
sequences = ["50x_x_0p5um", "50x_x_1um"];
sequenceLabels = ["0.5 \mum", "1.0 \mum"];
values = nan(2, numel(methods));
for si = 1:numel(sequences)
    for mi = 1:numel(methods)
        subset = T(T.sequence == sequences(si) & T.method == methods(mi), :);
        values(si,mi) = mean(subset.(metric), 'omitnan');
    end
end
fig = newFigure([880 610]);
x = categorical(cellstr(sequenceLabels));
x = reordercats(x, cellstr(sequenceLabels));
b = bar(x, values, 'grouped', 'BarWidth', 0.76); hold on;
for mi = 1:numel(methods)
    b(mi).FaceColor = colors(mi,:);
    b(mi).EdgeColor = [0.20 0.20 0.20];
    b(mi).LineWidth = 0.7;
end
drawnow;
for mi = 1:numel(methods)
    for si = 1:numel(sequences)
        text(b(mi).XEndPoints(si), values(si,mi), sprintf('  %.2f', values(si,mi)), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
            'FontName', 'Times New Roman', 'FontSize', 8, 'Color', [0.16 0.16 0.16]);
    end
end
ylabel(yLabel);
xlabel('PI displacement increment');
title(chartTitle, 'FontWeight', 'normal');
subtitle(chartSubtitle);
legend(cellstr(methods), 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
styleAxes(gca);
ylim([0 max(values, [], 'all') * 1.28]);
exportFigure(fig, fullfile(figureDir, filename));
end


function [medianValues, lowerErrors, upperErrors] = groupedStats(T, methods, orientations, metric)
medianValues = nan(numel(orientations), numel(methods));
lowerErrors = medianValues;
upperErrors = medianValues;
for oi = 1:numel(orientations)
    for mi = 1:numel(methods)
        values = T.(metric)(T.orientation == orientations(oi) & T.method == methods(mi));
        values = values(isfinite(values));
        q = prctile(values, [25 50 75]);
        medianValues(oi,mi) = q(2);
        lowerErrors(oi,mi) = q(2) - q(1);
        upperErrors(oi,mi) = q(3) - q(2);
    end
end
end


function fig = newFigure(pixelSize)
fig = figure('Color', 'white', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [80 80 pixelSize(1) pixelSize(2)]);
end


function styleAxes(ax)
ax.FontName = 'Times New Roman';
ax.FontSize = 9;
ax.LineWidth = 0.8;
ax.Box = 'off';
ax.TickDir = 'out';
ax.XColor = [0.18 0.18 0.18];
ax.YColor = [0.18 0.18 0.18];
ax.GridColor = [0.82 0.82 0.82];
ax.GridAlpha = 0.55;
grid(ax, 'on');
ax.Layer = 'top';
end


function exportFigure(fig, path)
set(fig, 'InvertHardcopy', 'off');
exportgraphics(fig, path, 'Resolution', 300, 'BackgroundColor', 'white');
close(fig);
end
