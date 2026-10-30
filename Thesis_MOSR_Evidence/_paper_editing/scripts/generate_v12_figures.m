function generate_v12_figures
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
% Generate restrained MATLAB-style figures used by thesis v12.

inputCsv = fullfile(PROJECT_ROOT, 'LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/line/tables/line_sharpness_summary.csv');
outputDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/_paper_editing/v12_assets');

if ~isfolder(outputDir)
    mkdir(outputDir);
end

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

fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [100, 100, 1500, 900]);
ax = axes(fig);
b = bar(ax, values, 'grouped', 'BarWidth', 0.72);
b(1).FaceColor = [0.36, 0.36, 0.36];
b(1).EdgeColor = 'none';
b(2).FaceColor = [0.00, 0.45, 0.74];
b(2).EdgeColor = 'none';

ax.XTick = 1:2;
ax.XTickLabel = {'Horizontal lines', 'Vertical lines'};
ax.FontName = 'Times New Roman';
ax.FontSize = 18;
ax.LineWidth = 1.0;
ax.Box = 'off';
ax.YGrid = 'on';
ax.GridColor = [0.82, 0.82, 0.82];
ax.GridAlpha = 0.75;
ax.YLim = [0, 800];
ylabel(ax, '10%-90% edge-transition width (nm)', ...
    'FontName', 'Times New Roman', 'FontSize', 20);
title(ax, 'Line-edge concentration with preserved image sampling', ...
    'FontName', 'Times New Roman', 'FontSize', 21, 'FontWeight', 'normal');
legend(ax, {'Raw', 'MOSR'}, 'Location', 'northoutside', ...
    'Orientation', 'horizontal', 'Box', 'off', ...
    'FontName', 'Times New Roman', 'FontSize', 18);

for j = 1:numel(b)
    x = b(j).XEndPoints;
    y = b(j).YEndPoints;
    labels = compose('%.1f', b(j).YData);
    text(ax, x, y + 18, labels, 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'bottom', 'FontName', 'Times New Roman', ...
        'FontSize', 16, 'Color', [0.15, 0.15, 0.15]);
end

exportgraphics(fig, fullfile(outputDir, 'fig_v12_line_edge_width.png'), ...
    'Resolution', 300, 'BackgroundColor', 'white');
close(fig);

fprintf('Generated %s\n', fullfile(outputDir, 'fig_v12_line_edge_width.png'));
end
