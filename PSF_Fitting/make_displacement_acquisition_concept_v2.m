PROJECT_ROOT = fileparts(fileparts(mfilename('fullpath')));
%% Clear image-based explanation of the four displacement conditions.
% Each card follows one physical feature from frame t to frame t+1.

clear; close all; clc;

outputDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Slide_Assets/Displacement_Acquisition_Concept');
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

conditions = struct( ...
    'magnification', {'50×', '50×', '20×', '20×'}, ...
    'physicalStep', {0.5, 1.0, 0.5, 1.0}, ...
    'sampling', {0.0690, 0.0690, 0.1725, 0.1725}, ...
    'pixelStep', {7.246, 14.493, 2.899, 5.797}, ...
    'directory', { ...
        fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp'), ...
        fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp'), ...
        fullfile(PROJECT_ROOT, 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_0p5um/bmp'), ...
        fullfile(PROJECT_ROOT, 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp')}, ...
    'frameIndex', {9, 32, 34, 27}, ...
    'roi', { ...
        [1150, 100, 600, 600], ...
        [1150, 100, 600, 600], ...
        [720, 70, 600, 600], ...
        [720, 70, 600, 600]}, ...
    'polarity', {'dark', 'dark', 'bright', 'bright'}, ...
    'featureRadius', {24, 24, 12, 12}, ...
    'zoomSize', {120, 130, 72, 78});

for i = 1:numel(conditions)
    frameAName = sprintf('frame_%04d.bmp', conditions(i).frameIndex);
    frameBName = sprintf('frame_%04d.bmp', conditions(i).frameIndex + 1);
    imageA = cropGray(fullfile(conditions(i).directory, frameAName), conditions(i).roi);
    imageB = cropGray(fullfile(conditions(i).directory, frameBName), conditions(i).roi);

    centerA = locateFeature(imageA, [300, 300], conditions(i).polarity, ...
        42, conditions(i).featureRadius);
    predictedCenterB = centerA + [-conditions(i).pixelStep, 0];
    centerB = locateFeature(imageB, predictedCenterB, conditions(i).polarity, ...
        max(7, ceil(conditions(i).pixelStep / 2) + 3), conditions(i).featureRadius);

    midpoint = 0.5 * (centerA + centerB);
    [zoomA, origin] = fixedCrop(imageA, midpoint, conditions(i).zoomSize);
    [zoomB, ~] = fixedCrop(imageB, midpoint, conditions(i).zoomSize);
    [displayA, displayB] = sharedRobustDisplay(zoomA, zoomB);

    conditions(i).frameAName = frameAName;
    conditions(i).frameBName = frameBName;
    conditions(i).centerA = centerA;
    conditions(i).centerB = centerB;
    conditions(i).measuredShift = centerB - centerA;
    conditions(i).localCenterA = centerA - origin + [1, 1];
    conditions(i).localCenterB = centerB - origin + [1, 1];
    conditions(i).displayA = displayA;
    conditions(i).displayB = displayB;
end

fontName = 'Microsoft JhengHei UI';
blue = [0.10, 0.43, 0.72];
orange = [0.90, 0.38, 0.10];
ink = [0.13, 0.15, 0.17];
muted = [0.39, 0.42, 0.45];
border = [0.80, 0.82, 0.84];
cardFill = [0.985, 0.988, 0.990];

fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [30, 30, 2400, 1350], ...
    'Renderer', 'painters');

annotation(fig, 'textbox', [0.02, 0.945, 0.96, 0.040], ...
    'String', '設定的物體位移如何轉換成影像中的像素移動', ...
    'FontName', fontName, 'FontSize', 25, 'FontWeight', 'bold', ...
    'Color', ink, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');
annotation(fig, 'textbox', [0.02, 0.912, 0.96, 0.026], ...
    'String', '每組均使用實際相鄰影格，並放大追蹤同一個結構', ...
    'FontName', fontName, 'FontSize', 13, 'Color', muted, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

cardLeft = [0.025, 0.515, 0.025, 0.515];
cardBottom = [0.505, 0.505, 0.055, 0.055];
cardWidth = 0.46;
cardHeight = 0.385;
imageGap = 0.011;
imageWidth = (cardWidth - 4 * imageGap) / 3;
imageHeight = 0.225;

for i = 1:numel(conditions)
    x0 = cardLeft(i);
    y0 = cardBottom(i);

    annotation(fig, 'rectangle', [x0, y0, cardWidth, cardHeight], ...
        'Color', border, 'LineWidth', 1.1);

    % Visual conversion strip: magnification -> physical step -> pixel step.
    annotation(fig, 'textbox', [x0 + 0.014, y0 + cardHeight - 0.064, 0.066, 0.041], ...
        'String', conditions(i).magnification, 'FontName', fontName, 'FontSize', 17, ...
        'FontWeight', 'bold', 'Color', 'w', 'BackgroundColor', blue, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'EdgeColor', blue, 'LineWidth', 1, 'Interpreter', 'none');
    annotation(fig, 'textbox', [x0 + 0.092, y0 + cardHeight - 0.064, 0.110, 0.041], ...
        'String', sprintf('設定 %.1f µm', conditions(i).physicalStep), ...
        'FontName', fontName, 'FontSize', 15, 'FontWeight', 'bold', 'Color', ink, ...
        'BackgroundColor', [0.94, 0.95, 0.96], 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle', 'EdgeColor', [0.83, 0.85, 0.87], ...
        'LineWidth', 1, 'Interpreter', 'none');
    annotation(fig, 'textbox', [x0 + 0.210, y0 + cardHeight - 0.060, 0.030, 0.032], ...
        'String', '→', 'FontName', fontName, 'FontSize', 20, 'FontWeight', 'bold', ...
        'Color', muted, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'LineStyle', 'none', 'Interpreter', 'none');
    annotation(fig, 'textbox', [x0 + 0.248, y0 + cardHeight - 0.064, 0.194, 0.041], ...
        'String', sprintf('影像中 %.3f pixels', conditions(i).pixelStep), ...
        'FontName', fontName, 'FontSize', 15, 'FontWeight', 'bold', 'Color', orange, ...
        'BackgroundColor', [1.00, 0.95, 0.91], 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle', 'EdgeColor', [0.95, 0.73, 0.57], ...
        'LineWidth', 1, 'Interpreter', 'none');

    equation = sprintf('%.1f µm  ÷  %.4f µm/pixel  =  %.3f pixels', ...
        conditions(i).physicalStep, conditions(i).sampling, conditions(i).pixelStep);
    annotation(fig, 'textbox', [x0 + 0.018, y0 + cardHeight - 0.103, cardWidth - 0.036, 0.026], ...
        'String', equation, 'FontName', fontName, 'FontSize', 12.5, 'Color', muted, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'LineStyle', 'none', 'Interpreter', 'none');

    for j = 1:3
        axX = x0 + imageGap + (j - 1) * (imageWidth + imageGap);
        axY = y0 + 0.058;
        ax = axes(fig, 'Position', [axX, axY, imageWidth, imageHeight]); %#ok<LAXES>
        if j == 1
            imshow(conditions(i).displayA, 'Parent', ax);
            addCenterMarker(ax, conditions(i).localCenterA, blue, 'o');
        elseif j == 2
            imshow(conditions(i).displayB, 'Parent', ax);
            addCenterMarker(ax, conditions(i).localCenterB, orange, 's');
        else
            background = 0.5 * (conditions(i).displayA + conditions(i).displayB);
            imshow(background, 'Parent', ax);
            hold(ax, 'on');
            thresholdA = graythresh(conditions(i).displayA);
            thresholdB = graythresh(conditions(i).displayB);
            contour(ax, conditions(i).displayA, [thresholdA, thresholdA], ...
                'Color', blue, 'LineWidth', 2.2, 'LineStyle', '-');
            contour(ax, conditions(i).displayB, [thresholdB, thresholdB], ...
                'Color', orange, 'LineWidth', 2.2, 'LineStyle', '--');
            plot(ax, conditions(i).localCenterA(1), conditions(i).localCenterA(2), ...
                'o', 'MarkerSize', 8, 'LineWidth', 2, 'Color', blue, 'MarkerFaceColor', 'w');
            plot(ax, conditions(i).localCenterB(1), conditions(i).localCenterB(2), ...
                's', 'MarkerSize', 8, 'LineWidth', 2, 'Color', orange, 'MarkerFaceColor', 'w');
            dx = conditions(i).localCenterB(1) - conditions(i).localCenterA(1);
            dy = conditions(i).localCenterB(2) - conditions(i).localCenterA(2);
            quiver(ax, conditions(i).localCenterA(1), conditions(i).localCenterA(2), ...
                dx, dy, 0, 'Color', ink, 'LineWidth', 2.4, 'MaxHeadSize', 1.8);
            hold(ax, 'off');
        end
        axis(ax, 'image', 'off');
        hold(ax, 'on');
        rectangle(ax, 'Position', [0.5, 0.5, size(conditions(i).displayA, 2) - 1, size(conditions(i).displayA, 1) - 1], ...
            'EdgeColor', [0.25, 0.27, 0.29], 'LineWidth', 0.8);
        hold(ax, 'off');
    end

    labels = {'移動前', '移動後', '邊界位移'};
    for j = 1:3
        axX = x0 + imageGap + (j - 1) * (imageWidth + imageGap);
        labelColor = ink;
        if j == 1, labelColor = blue; end
        if j == 2, labelColor = orange; end
        annotation(fig, 'textbox', [axX, y0 + 0.018, imageWidth, 0.029], ...
            'String', labels{j}, 'FontName', fontName, 'FontSize', 13, ...
            'FontWeight', 'bold', 'Color', labelColor, ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
            'LineStyle', 'none', 'Interpreter', 'none');
    end
end

annotation(fig, 'textbox', [0.02, 0.010, 0.96, 0.027], ...
    'String', '藍色實線與圓點：移動前　　橘色虛線與方點：移動後　　箭頭：影像中的移動方向', ...
    'FontName', fontName, 'FontSize', 12.5, 'Color', muted, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

pngPath = fullfile(outputDir, '02_four_condition_displacement_acquisition_concept_clear.png');
pdfPath = fullfile(outputDir, '02_four_condition_displacement_acquisition_concept_clear.pdf');
figPath = fullfile(outputDir, '02_four_condition_displacement_acquisition_concept_clear.fig');
exportgraphics(fig, pngPath, 'Resolution', 220);
exportgraphics(fig, pdfPath, 'ContentType', 'image', 'Resolution', 220);
savefig(fig, figPath);

metadata = rmfield(conditions, {'displayA', 'displayB'});
jsonPath = fullfile(outputDir, '02_four_condition_displacement_acquisition_concept_clear_metadata.json');
fid = fopen(jsonPath, 'w', 'n', 'UTF-8');
if fid < 0
    error('Could not write metadata file: %s', jsonPath);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(metadata, PrettyPrint=true));

fprintf('\nCreated: %s\n', pngPath);
for i = 1:numel(conditions)
    fprintf('%s %.1f um | %s -> %s | tracked shift = (%+.3f, %+.3f) px\n', ...
        conditions(i).magnification, conditions(i).physicalStep, ...
        conditions(i).frameAName, conditions(i).frameBName, ...
        conditions(i).measuredShift(1), conditions(i).measuredShift(2));
end

function image = cropGray(path, roi)
    image = imread(path);
    if ndims(image) == 3
        image = rgb2gray(image);
    end
    image = im2double(image);
    x = roi(1); y = roi(2); w = roi(3); h = roi(4);
    image = image(y:(y + h - 1), x:(x + w - 1));
end

function center = locateFeature(image, seed, polarity, searchRadius, featureRadius)
    smoothed = imgaussfilt(image, 2);
    x0 = max(1, floor(seed(1) - searchRadius));
    x1 = min(size(image, 2), ceil(seed(1) + searchRadius));
    y0 = max(1, floor(seed(2) - searchRadius));
    y1 = min(size(image, 1), ceil(seed(2) + searchRadius));
    searchImage = smoothed(y0:y1, x0:x1);
    if strcmpi(polarity, 'dark')
        [~, index] = min(searchImage, [], 'all', 'linear');
    else
        [~, index] = max(searchImage, [], 'all', 'linear');
    end
    [localY, localX] = ind2sub(size(searchImage), index);
    peakX = x0 + localX - 1;
    peakY = y0 + localY - 1;

    patchX0 = max(1, peakX - featureRadius);
    patchX1 = min(size(image, 2), peakX + featureRadius);
    patchY0 = max(1, peakY - featureRadius);
    patchY1 = min(size(image, 1), peakY + featureRadius);
    patch = smoothed(patchY0:patchY1, patchX0:patchX1);
    localMedian = median(patch, 'all');
    if strcmpi(polarity, 'dark')
        weights = max(localMedian - patch, 0);
    else
        weights = max(patch - localMedian, 0);
    end
    [gridX, gridY] = meshgrid(patchX0:patchX1, patchY0:patchY1);
    weightSum = sum(weights, 'all');
    if weightSum <= eps
        center = [peakX, peakY];
    else
        center = [sum(weights .* gridX, 'all') / weightSum, ...
                  sum(weights .* gridY, 'all') / weightSum];
    end
end

function [patch, origin] = fixedCrop(image, center, cropSize)
    halfSize = floor(cropSize / 2);
    x0 = round(center(1)) - halfSize;
    y0 = round(center(2)) - halfSize;
    x0 = min(max(1, x0), size(image, 2) - cropSize + 1);
    y0 = min(max(1, y0), size(image, 1) - cropSize + 1);
    patch = image(y0:(y0 + cropSize - 1), x0:(x0 + cropSize - 1));
    origin = [x0, y0];
end

function [displayA, displayB] = sharedRobustDisplay(imageA, imageB)
    values = sort([imageA(:); imageB(:)]);
    n = numel(values);
    lowValue = values(max(1, round(0.005 * n)));
    highValue = values(min(n, round(0.995 * n)));
    if highValue <= lowValue
        lowValue = min(values);
        highValue = max(values);
    end
    displayA = min(max((imageA - lowValue) ./ max(highValue - lowValue, eps), 0), 1);
    displayB = min(max((imageB - lowValue) ./ max(highValue - lowValue, eps), 0), 1);
end

function addCenterMarker(ax, center, color, marker)
    hold(ax, 'on');
    plot(ax, center(1), center(2), marker, 'MarkerSize', 9, 'LineWidth', 2.2, ...
        'Color', color, 'MarkerFaceColor', 'w');
    crossSize = 5;
    plot(ax, [center(1) - crossSize, center(1) + crossSize], [center(2), center(2)], ...
        '-', 'Color', color, 'LineWidth', 1.5);
    plot(ax, [center(1), center(1)], [center(2) - crossSize, center(2) + crossSize], ...
        '-', 'Color', color, 'LineWidth', 1.5);
    hold(ax, 'off');
end
