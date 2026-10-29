PROJECT_ROOT = fileparts(fileparts(mfilename('fullpath')));
%% Slide-ready schematic for nine-pillar displacement dispersion.
% Uses a real 50x consecutive-frame pair and a compact symbolic summary.

clear; close all; clc;

sourceDir = fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp');
outputDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Slide_Assets/Nine_Pillar_Displacement_Dispersion');
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

frameA = imread(fullfile(sourceDir, 'frame_0000.bmp'));
frameB = imread(fullfile(sourceDir, 'frame_0001.bmp'));
if ndims(frameA) == 3, frameA = rgb2gray(frameA); end
if ndims(frameB) == 3, frameB = rgb2gray(frameB); end
if ~isa(frameA, 'uint8'), frameA = im2uint8(frameA); end
if ~isa(frameB, 'uint8'), frameB = im2uint8(frameB); end

% Center-nine region inside the actual 50x pillar field.
roi = [1150, 100, 600, 600];
imageA = frameA(roi(2):(roi(2) + roi(4) - 1), roi(1):(roi(1) + roi(3) - 1));
imageB = frameB(roi(2):(roi(2) + roi(4) - 1), roi(1):(roi(1) + roi(3) - 1));

centerSeed = locateDarkFeature(double(imageA), [300, 300], 42, 24);
pitchX = 73;
pitchY = 72;
expectedShiftPx = 0.5 / 0.0690;

centersA = zeros(9, 2);
centersB = zeros(9, 2);
index = 0;
for row = -1:1
    for col = -1:1
        index = index + 1;
        seedA = centerSeed + [col * pitchX, row * pitchY];
        centersA(index, :) = locateDarkFeature(double(imageA), seedA, 20, 24);
        seedB = centersA(index, :) + [-expectedShiftPx, 0];
        centersB(index, :) = locateDarkFeature(double(imageB), seedB, 8, 24);
    end
end

margin = 37;
x0 = floor(min(centersB(:, 1)) - margin);
x1 = ceil(max(centersA(:, 1)) + margin);
y0 = floor(min(centersA(:, 2)) - margin);
y1 = ceil(max(centersA(:, 2)) + margin);
x0 = max(1, x0); y0 = max(1, y0);
x1 = min(size(imageA, 2), x1); y1 = min(size(imageA, 1), y1);
displayImage = imageA(y0:y1, x0:x1);
localA = centersA - [x0 - 1, y0 - 1];
localB = centersB - [x0 - 1, y0 - 1];

blue = [0.08, 0.38, 0.68];
orange = [0.90, 0.34, 0.08];
ink = [0.12, 0.14, 0.16];
muted = [0.38, 0.41, 0.44];
lightLine = [0.80, 0.82, 0.84];
fontName = 'Arial';

fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [50, 30, 1050, 1100], ...
    'Renderer', 'painters');

annotation(fig, 'textbox', [0.17, 0.952, 0.31, 0.026], ...
    'String', '○  Frame t center', 'FontName', fontName, 'FontSize', 14.5, ...
    'Color', blue, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');
annotation(fig, 'textbox', [0.52, 0.952, 0.31, 0.026], ...
    'String', '□  Frame t+1 center', 'FontName', fontName, 'FontSize', 14.5, ...
    'Color', orange, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

ax = axes(fig, 'Position', [0.105, 0.350, 0.79, 0.575]);
imshow(displayImage, [0, 255], 'Parent', ax, 'InitialMagnification', 'fit');
axis(ax, 'image', 'off');
hold(ax, 'on');
for j = 1:9
    dx = localB(j, 1) - localA(j, 1);
    dy = localB(j, 2) - localA(j, 2);
    plot(ax, localA(j, 1), localA(j, 2), 'o', ...
        'MarkerSize', 9, 'LineWidth', 2.0, 'Color', blue, 'MarkerFaceColor', 'w');
    plot(ax, localB(j, 1), localB(j, 2), 's', ...
        'MarkerSize', 8, 'LineWidth', 2.0, 'Color', orange, 'MarkerFaceColor', 'w');
    quiver(ax, localA(j, 1), localA(j, 2), dx, dy, 0, ...
        'Color', ink, 'LineWidth', 2.2, 'MaxHeadSize', 2.0);

    labelX = 0.5 * (localA(j, 1) + localB(j, 1));
    labelY = localA(j, 2) - 26;
    text(ax, labelX, labelY, sprintf('d_{t,%d}', j), ...
        'Interpreter', 'tex', 'FontName', fontName, 'FontSize', 14, ...
        'FontWeight', 'bold', 'Color', ink, 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle', 'BackgroundColor', 'w', ...
        'Margin', 2, 'EdgeColor', 'none');
end
rectangle(ax, 'Position', [0.5, 0.5, size(displayImage, 2) - 1, size(displayImage, 1) - 1], ...
    'EdgeColor', [0.25, 0.27, 0.29], 'LineWidth', 0.9);
hold(ax, 'off');

% Compact symbolic summary: nine local estimates produce two complementary outputs.
annotation(fig, 'textbox', [0.08, 0.275, 0.84, 0.032], ...
    'String', 'Nine local measurements are summarized in two complementary ways', ...
    'FontName', fontName, 'FontSize', 14.5, 'Color', muted, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

annotation(fig, 'textbox', [0.09, 0.105, 0.245, 0.115], ...
    'String', 'd_{t,1},  ... ,  d_{t,9}', 'Interpreter', 'tex', ...
    'FontName', fontName, 'FontSize', 18, 'FontWeight', 'bold', 'Color', ink, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'BackgroundColor', [0.97, 0.975, 0.98], 'EdgeColor', lightLine, 'LineWidth', 1.2);

annotation(fig, 'arrow', [0.35, 0.48], [0.188, 0.188], ...
    'Color', muted, 'LineWidth', 1.8, 'HeadLength', 10, 'HeadWidth', 10);
annotation(fig, 'arrow', [0.35, 0.48], [0.137, 0.137], ...
    'Color', muted, 'LineWidth', 1.8, 'HeadLength', 10, 'HeadWidth', 10);

annotation(fig, 'textbox', [0.50, 0.160, 0.41, 0.078], ...
    'String', {'Median'; 'Representative displacement'}, ...
    'FontName', fontName, 'FontSize', 15.5, 'FontWeight', 'bold', 'Color', blue, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'BackgroundColor', [0.95, 0.975, 0.995], 'EdgeColor', blue, 'LineWidth', 1.5, ...
    'Interpreter', 'none');
annotation(fig, 'textbox', [0.50, 0.070, 0.41, 0.078], ...
    'String', {'Scaled MAD'; 'Cross-position dispersion'}, ...
    'FontName', fontName, 'FontSize', 15.5, 'FontWeight', 'bold', 'Color', orange, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'BackgroundColor', [1.00, 0.965, 0.94], 'EdgeColor', orange, 'LineWidth', 1.5, ...
    'Interpreter', 'none');

annotation(fig, 'textbox', [0.08, 0.018, 0.84, 0.032], ...
    'String', 'Lower scaled MAD indicates stronger spatial consistency.', ...
    'FontName', fontName, 'FontSize', 14.5, 'FontWeight', 'bold', 'Color', ink, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

fileStem = 'nine_pillar_displacement_dispersion_slide_ready';
pngPath = fullfile(outputDir, [fileStem, '.png']);
pdfPath = fullfile(outputDir, [fileStem, '.pdf']);
figPath = fullfile(outputDir, [fileStem, '.fig']);
exportgraphics(fig, pngPath, 'Resolution', 220);
exportgraphics(fig, pdfPath, 'ContentType', 'image', 'Resolution', 220);
savefig(fig, figPath);

metadata = struct();
metadata.source_frame_t = fullfile(sourceDir, 'frame_0000.bmp');
metadata.source_frame_t_plus_1 = fullfile(sourceDir, 'frame_0001.bmp');
metadata.object_space_sampling_um_per_pixel = 0.0690;
metadata.nominal_stage_step_um = 0.5;
metadata.local_displacements_px = centersB - centersA;
metadata.display_range = [0, 255];
metadata.contrast_stretching = false;
metadataPath = fullfile(outputDir, 'nine_pillar_displacement_dispersion_schematic_metadata.json');
fid = fopen(metadataPath, 'w', 'n', 'UTF-8');
if fid < 0, error('Could not write metadata file.'); end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(metadata, PrettyPrint=true));

fprintf('Created: %s\n', pngPath);

function center = locateDarkFeature(image, seed, searchRadius, featureRadius)
    smoothed = imgaussfilt(image, 2);
    x0 = max(1, floor(seed(1) - searchRadius));
    x1 = min(size(image, 2), ceil(seed(1) + searchRadius));
    y0 = max(1, floor(seed(2) - searchRadius));
    y1 = min(size(image, 1), ceil(seed(2) + searchRadius));
    searchImage = smoothed(y0:y1, x0:x1);
    [~, linearIndex] = min(searchImage, [], 'all', 'linear');
    [localY, localX] = ind2sub(size(searchImage), linearIndex);
    peakX = x0 + localX - 1;
    peakY = y0 + localY - 1;

    patchX0 = max(1, peakX - featureRadius);
    patchX1 = min(size(image, 2), peakX + featureRadius);
    patchY0 = max(1, peakY - featureRadius);
    patchY1 = min(size(image, 1), peakY + featureRadius);
    patch = smoothed(patchY0:patchY1, patchX0:patchX1);
    weights = max(median(patch, 'all') - patch, 0);
    [gridX, gridY] = meshgrid(patchX0:patchX1, patchY0:patchY1);
    weightSum = sum(weights, 'all');
    center = [sum(weights .* gridX, 'all') / weightSum, ...
              sum(weights .* gridY, 'all') / weightSum];
end
