function build_20x_noncalibration_cd_figure()
%BUILD_20X_NONCALIBRATION_CD_FIGURE Draw the supplementary 20x CD range chart.

packageRoot = fileparts(fileparts(mfilename('fullpath')));
sourceRoot = fullfile(packageRoot, 'source_validation', 'wiener_baseline_20260715', ...
    'supplementary_20x_cd');
tablePath = fullfile(sourceRoot, 'tables', '20x_frame49_cd_per_pillar_range.csv');
figureRoot = fullfile(packageRoot, 'figures');
localFigureRoot = fullfile(sourceRoot, 'figures');
if ~exist(localFigureRoot, 'dir'), mkdir(localFigureRoot); end

rows = readtable(tablePath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
summaryRows = readtable(fullfile(sourceRoot, 'tables', '20x_frame49_cd_summary.csv'), ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
caseOrder = ["raw", "wiener", "mosr"];
caseLabels = ["Raw", "Wiener", "MOSR"];
colors = [0.65 0.29 0.12; 0.80 0.48 0.00; 0.05 0.37 0.64];
markers = {'s', '^', 'o'};
offsets = [-0.18, 0, 0.18];

semRows = sortrows(rows(rows.case == "raw", :), 'center9_position');
x = (1:height(semRows))';
figure('Color', 'white', 'Position', [120 120 920 560]);
ax = axes(); hold(ax, 'on');
hSem = plot(ax, x, semRows.sem_diameter_um, '--o', 'Color', [0.12 0.12 0.12], ...
    'MarkerFaceColor', 'white', 'MarkerSize', 5.2, 'LineWidth', 1.2);
hMethods = gobjects(numel(caseOrder), 1);
for caseIndex = 1:numel(caseOrder)
    selected = sortrows(rows(rows.case == caseOrder(caseIndex), :), 'center9_position');
    center = selected.diameter_median_um;
    lower = center - selected.diameter_min_um;
    upper = selected.diameter_max_um - center;
    hMethods(caseIndex) = errorbar(ax, x + offsets(caseIndex), center, lower, upper, ...
        'LineStyle', 'none', 'Color', colors(caseIndex, :), 'LineWidth', 1.35, ...
        'CapSize', 7, 'Marker', markers{caseIndex}, 'MarkerSize', 5.6, ...
        'MarkerFaceColor', colors(caseIndex, :), 'MarkerEdgeColor', colors(caseIndex, :));
end

grid(ax, 'on'); box(ax, 'off');
ax.GridColor = [0.84 0.84 0.84];
ax.GridAlpha = 0.65;
ax.FontName = 'Times New Roman';
ax.FontSize = 9.5;
ax.LineWidth = 0.9;
xlim(ax, [0.55, 9.45]);
xticks(ax, x);
xticklabels(ax, "P" + string(semRows.sem_index));
xlabel(ax, 'SEM pillar identity');
ylabel(ax, 'Apparent diameter (mum)', 'Interpreter', 'tex');
title(ax, 'Supplementary 20x CD consistency on a non-calibration frame', ...
    'FontWeight', 'normal', 'FontSize', 11.0);
subtitle(ax, 'Range across 35-65% thresholds and two profile definitions', ...
    'FontSize', 8.5);
legend(ax, [hSem; hMethods], ["SEM reference"; caseLabels'], ...
    'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off', ...
    'NumColumns', 4);

outputName = '23_20x_noncalibration_cd_range.png';
exportFigure(gcf, fullfile(figureRoot, outputName));
copyfile(fullfile(figureRoot, outputName), fullfile(localFigureRoot, outputName), 'f');
fprintf('Supplementary 20x CD figure completed: %s\n', fullfile(figureRoot, outputName));

values = zeros(1, numel(caseOrder));
for caseIndex = 1:numel(caseOrder)
    selected = summaryRows(summaryRows.case == caseOrder(caseIndex), :);
    assert(height(selected) == 1, 'Expected one 20x CD summary row per method.');
    values(caseIndex) = selected.pooled_median_abs_error_nm;
end
figure('Color', 'white', 'Position', [150 150 760 500]);
ax = axes();
b = bar(ax, 1:numel(values), values, 0.62, 'FaceColor', 'flat', 'EdgeColor', 'none');
b.CData = colors;
grid(ax, 'on'); box(ax, 'off');
ax.YGrid = 'on'; ax.XGrid = 'off';
ax.GridColor = [0.84 0.84 0.84]; ax.GridAlpha = 0.65;
ax.FontName = 'Times New Roman'; ax.FontSize = 9.5; ax.LineWidth = 0.9;
xticks(ax, 1:numel(values)); xticklabels(ax, caseLabels);
ylabel(ax, 'Pooled median absolute CD error (nm)');
ylim(ax, [0, max(values) * 1.25]);
title(ax, 'Supplementary 20x CD consistency on a non-calibration frame', ...
    'FontWeight', 'normal', 'FontSize', 11.0);
subtitle(ax, '126 measurements per method: nine pillars, seven thresholds, and two profiles', ...
    'FontSize', 8.5);
for caseIndex = 1:numel(values)
    text(ax, caseIndex, values(caseIndex) + max(values) * 0.035, ...
        sprintf('%.1f nm', values(caseIndex)), 'HorizontalAlignment', 'center', ...
        'FontName', 'Times New Roman', 'FontSize', 9.0);
end
summaryName = '24_20x_noncalibration_cd_error_summary.png';
exportFigure(gcf, fullfile(figureRoot, summaryName));
copyfile(fullfile(figureRoot, summaryName), fullfile(localFigureRoot, summaryName), 'f');
fprintf('Supplementary 20x CD summary completed: %s\n', fullfile(figureRoot, summaryName));
end

function exportFigure(fig, path)
set(fig, 'Renderer', 'painters');
axesList = findall(fig, 'Type', 'axes');
for k = 1:numel(axesList), axtoolbar(axesList(k), {}); end
exportgraphics(fig, path, 'Resolution', 300, 'BackgroundColor', 'white');
close(fig);
end
