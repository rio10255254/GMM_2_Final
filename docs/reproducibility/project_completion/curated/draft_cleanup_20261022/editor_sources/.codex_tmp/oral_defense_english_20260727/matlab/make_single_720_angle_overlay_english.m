function make_single_720_angle_overlay_english()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
%MAKE_SINGLE_720_ANGLE_OVERLAY_ENGLISH
% One clean P29 sampling schematic based directly on the supplied image.

inputPath = 'C:\Users\Rio\AppData\Local\Temp\codex-clipboard-ebcfb69b-f3cf-4756-b66f-7d1e574941fb.png';
outputDir = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_tmp/oral_defense_english_20260727/assets_english/custom');
outputPath = fullfile(outputDir, '720_equal_angle_sampling_P29_english.png');
if ~isfolder(outputDir), mkdir(outputDir); end

imageData = imread(inputPath);
imageHeight = size(imageData, 1);
imageWidth = size(imageData, 2);

% Coordinates of the existing Raw-defined P29 centre and reference circle
% in the supplied exported image.
center = [339.5, 339.5];
referenceRadius = 140.0;
tickInnerRadius = 153.0;
tickOuterRadius = 161.0;
angles = (0:719) * (2*pi/720);

lightBlue = [0.31, 0.67, 0.86];
darkBlue = [0.00, 0.40, 0.70];
charcoal = [0.14, 0.14, 0.14];

fig = figure('Color', 'w', 'Units', 'pixels', ...
    'Position', [100, 100, imageWidth, imageHeight]);
ax = axes(fig, 'Position', [0, 0, 1, 1]);
image(ax, imageData);
axis(ax, 'image');
axis(ax, 'off');
hold(ax, 'on');

% The short annular ticks represent all 720 actual angular sample positions.
for index = 1:numel(angles)
    theta = angles(index);
    plot(ax, center(1) + [tickInnerRadius, tickOuterRadius] * cos(theta), ...
        center(2) + [tickInnerRadius, tickOuterRadius] * sin(theta), '-', ...
        'Color', lightBlue, 'LineWidth', 0.24, 'HandleVisibility', 'off');
end

% Minimal labels: refer only to the geometry used by the current code.
text(ax, 28, 47, {'720 Angular Directions', '\Delta\theta = 0.5^\circ'}, ...
    'Color', charcoal, 'FontName', 'Times New Roman', 'FontSize', 13, ...
    'FontWeight', 'bold', 'VerticalAlignment', 'top', 'Interpreter', 'tex', ...
    'BackgroundColor', 'w', 'Margin', 2);
text(ax, center(1) + referenceRadius + 12, center(2) - 9, 'R', ...
    'Color', darkBlue, 'FontName', 'Times New Roman', 'FontSize', 15, ...
    'FontWeight', 'bold', 'Interpreter', 'tex');

exportgraphics(fig, outputPath, 'Resolution', 300, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', outputPath);
end
