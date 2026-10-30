function generate_v18_via_line_clean()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
%GENERATE_V17_VIA_LINE_ZH Rebuild the via and line figures in Chinese.

outDir = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_docx_work/v18/figures/cross_morphology');
if ~isfolder(outDir); mkdir(outDir); end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Microsoft JhengHei');
set(groot, 'defaultTextFontName', 'Microsoft JhengHei');
set(groot, 'defaultAxesFontSize', 14);
set(groot, 'defaultTextFontSize', 14);

draw_via(outDir);
draw_lines(outDir);
end

function draw_via(outDir)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
csvPath = fullfile(PROJECT_ROOT, 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/circular_cd_sharpness/circular_feature_cd_intervals.csv');
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

fig = figure('Color', 'w', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [100, 100, 1260, 760]);
ax = axes(fig); hold(ax, 'on');
plot(ax, 1:nFeatures, sem, '--o', 'Color', [0.12 0.12 0.12], ...
    'MarkerFaceColor', 'w', 'MarkerSize', 6.0, 'LineWidth', 1.5, ...
    'DisplayName', 'SEM 參考直徑');

offsets = linspace(-0.25, 0.25, nMethods);
palette = [0.33 0.33 0.33; 0.78 0.45 0.16; 0.45 0.36 0.62; 0.00 0.45 0.74];
for m = 1:nMethods
    midpoint = nan(nFeatures, 1);
    lowerBound = nan(nFeatures, 1);
    upperBound = nan(nFeatures, 1);
    for k = 1:nFeatures
        row = S(S.method == methods(m) & S.feature_id == featureIDs(k), :);
        assert(height(row) == 1, 'Expected one via interval row per method and feature.');
        midpoint(k) = row.cd_interval_midpoint_nm(1) / 1000;
        lowerBound(k) = row.cd_lower_nm(1) / 1000;
        upperBound(k) = row.cd_upper_nm(1) / 1000;
    end
    errorbar(ax, (1:nFeatures) + offsets(m), midpoint, ...
        midpoint-lowerBound, upperBound-midpoint, 'o', ...
        'Color', palette(m,:), 'MarkerFaceColor', palette(m,:), ...
        'MarkerSize', 5.2, 'CapSize', 6, 'LineWidth', 1.35, ...
        'DisplayName', methods(m));
end

title(ax, '20 倍 via 表觀 CD 範圍', 'FontSize', 18, 'FontWeight', 'normal');
subtitle(ax, '固定使用 35–65% 局部對比閾值', 'FontSize', 15);
xlabel(ax, 'Via 編號', 'FontSize', 15);
ylabel(ax, '表觀直徑 (\mum)', 'Interpreter', 'tex', 'FontSize', 15);
xticks(ax, 1:nFeatures); xticklabels(ax, featureIDs);
xlim(ax, [0.45 nFeatures+0.55]);
grid(ax, 'on'); ax.XGrid = 'off'; ax.Box = 'off'; ax.TickDir = 'out';
ax.Layer = 'top'; ax.GridColor = [0.84 0.84 0.84]; ax.GridAlpha = 0.7;
ax.LineWidth = 1.0; ax.FontName = 'Microsoft JhengHei'; ax.FontSize = 14;
legend(ax, 'Location', 'northoutside', 'NumColumns', 5, 'Box', 'off', 'FontSize', 14);

cleanFigure(fig); exportgraphics(fig, fullfile(outDir, 'fig6-53_zh.png'), ...
    'Resolution', 300, 'BackgroundColor', 'white');
savefig(fig, fullfile(outDir, 'fig6-53_zh.fig'));
close(fig);
end

function draw_lines(outDir)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
inputCsv = fullfile(PROJECT_ROOT, 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/line/tables/line_sharpness_summary.csv');
T = readtable(inputCsv, 'TextType', 'string');
orientations = ["horizontal_lines", "vertical_lines"];
methods = ["Raw", "MOSR"];
values = zeros(numel(orientations), numel(methods));
for i = 1:numel(orientations)
    for j = 1:numel(methods)
        idx = T.orientation == orientations(i) & T.method == methods(j);
        assert(nnz(idx) == 1, 'Expected one row for each orientation and method.');
        values(i, j) = T.median_transition_width_nm(idx);
    end
end

fig = figure('Color', 'w', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [100, 100, 1120, 700]);
ax = axes(fig);
b = bar(ax, values, 'grouped', 'BarWidth', 0.68);
b(1).FaceColor = [0.36, 0.36, 0.36]; b(1).EdgeColor = 'none';
b(2).FaceColor = [0.00, 0.45, 0.74]; b(2).EdgeColor = 'none';
ax.XTick = 1:2; ax.XTickLabel = {'水平線條', '垂直線條'};
ax.FontName = 'Microsoft JhengHei'; ax.FontSize = 13;
ax.LineWidth = 0.85; ax.Box = 'off'; ax.YGrid = 'on';
ax.GridColor = [0.84, 0.84, 0.84]; ax.GridAlpha = 0.7;
ax.YLim = [0, 800];
ylabel(ax, '10–90% 邊緣過渡寬度 (nm)', 'FontSize', 14);
title(ax, 'Raw 與 MOSR 線條邊緣過渡寬度', ...
    'FontSize', 17, 'FontWeight', 'normal');
subtitle(ax, '影像取樣尺寸維持不變；數值越低代表邊緣過渡越集中', 'FontSize', 14);
legend(ax, {'Raw', 'MOSR'}, 'Location', 'northoutside', ...
    'Orientation', 'horizontal', 'Box', 'off', 'FontSize', 13.5);

for j = 1:numel(b)
    text(ax, b(j).XEndPoints, b(j).YEndPoints + 18, compose('%.1f', b(j).YData), ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontName', 'Microsoft JhengHei', 'FontSize', 13, ...
        'Color', [0.15, 0.15, 0.15]);
end
cleanFigure(fig); exportgraphics(fig, fullfile(outDir, 'fig6-54_zh.png'), ...
    'Resolution', 300, 'BackgroundColor', 'white');
savefig(fig, fullfile(outDir, 'fig6-54_zh.fig'));
close(fig);
end


function cleanFigure(fig)
% Keep only axes labels, legends, ticks and visual marks.  Explanatory text
% is deliberately moved to the Word caption.
axesList = findall(fig, 'Type', 'axes');
for k = 1:numel(axesList)
    ax = axesList(k);
    if ~isa(ax, 'matlab.graphics.axis.Axes')
        continue;
    end
    axtoolbar(ax, {});
    ax.Title.String = '';
    ax.Title.Visible = 'off';
    if isprop(ax, 'Subtitle')
        ax.Subtitle.String = '';
        ax.Subtitle.Visible = 'off';
    end
    keep = [ax.XLabel, ax.YLabel, ax.ZLabel];
    notes = findall(ax, 'Type', 'text');
    for n = 1:numel(notes)
        if ~any(notes(n) == keep)
            delete(notes(n));
        end
    end
    refs = findall(ax, 'Type', 'ConstantLine');
    for n = 1:numel(refs)
        if isprop(refs(n), 'Label')
            refs(n).Label = '';
        end
    end
end
end
