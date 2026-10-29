function make_raw_anchor_panel_english()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
%MAKE_RAW_ANCHOR_PANEL_ENGLISH Preserve the three image panels and redraw labels.

inputPath = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_tmp/oral_defense_english_20260727/template-inspect/assets/ppt/media/image89.png');
outputDir = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_tmp/oral_defense_english_20260727/assets_english/custom');
outputPath = fullfile(outputDir, 'raw_anchor_visual_comparison_english.png');
if ~isfolder(outputDir), mkdir(outputDir); end

source = imread(inputPath);
[h, w, ~] = size(source);
labelBand = 72;

% The original figure already has a clean white label band. Preserve every
% scientific image pixel and replace only that band.
canvas = source;
canvas(1:labelBand, :, :) = 255;

fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [100, 100, w, labelBand + 120], ...
    'MenuBar', 'none', 'ToolBar', 'none', 'Resize', 'off');
ax = axes(fig, 'Units', 'pixels', 'Position', [0, 0, w, labelBand]);
xlim(ax, [0.5, w + 0.5]); ylim(ax, [0.5, labelBand + 0.5]);
set(ax, 'YDir', 'reverse'); axis(ax, 'off'); hold(ax, 'on');

text(ax, 443, 47, 'Raw', 'FontName', 'Times New Roman', 'FontSize', 23, ...
    'FontWeight', 'normal', 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle');
text(ax, 1608, 47, 'Full Model', 'FontName', 'Times New Roman', 'FontSize', 23, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle');
text(ax, 2768, 47, 'Without Raw-Position Anchor', 'FontName', 'Times New Roman', 'FontSize', 17, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle');

drawnow;
frame = getframe(ax);
labelStrip = frame.cdata;
if size(labelStrip, 1) ~= labelBand || size(labelStrip, 2) ~= w
    labelStrip = imresize(labelStrip, [labelBand, w]);
end
canvas(1:labelBand, :, :) = labelStrip;
imwrite(canvas, outputPath);
close(fig);
fprintf('%s\n', outputPath);
end
