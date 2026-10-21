%% Export one clean MATLAB figure for each displacement condition.
% The displayed image uses the native 8-bit range [0, 255] without contrast stretching.

clear; close all; clc;

outputDir = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Slide_Assets\Displacement_Acquisition_Concept\single_condition_figures';
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

conditions = struct( ...
    'magnification', {'50×', '50×', '20×', '20×'}, ...
    'physicalStep', {0.5, 1.0, 0.5, 1.0}, ...
    'sampling', {0.0690, 0.0690, 0.1725, 0.1725}, ...
    'pixelStep', {7.246, 14.493, 2.899, 5.797}, ...
    'directory', { ...
        'D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_0p5um\bmp', ...
        'D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_1um\bmp', ...
        'D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\20x_0p5um\bmp', ...
        'D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\20x_1um\bmp'}, ...
    'frameIndex', {9, 32, 34, 27}, ...
    'roi', { ...
        [1150, 100, 600, 600], ...
        [1150, 100, 600, 600], ...
        [720, 70, 600, 600], ...
        [720, 70, 600, 600]}, ...
    'polarity', {'dark', 'dark', 'bright', 'bright'}, ...
    'featureRadius', {24, 24, 12, 12}, ...
    'zoomSize', {150, 160, 92, 100}, ...
    'fileStem', { ...
        '01_50x_0p5um_displacement', ...
        '02_50x_1p0um_displacement', ...
        '03_20x_0p5um_displacement', ...
        '04_20x_1p0um_displacement'});

fontName = 'Microsoft JhengHei UI';
blue = [0.10, 0.43, 0.72];
orange = [0.90, 0.38, 0.10];
ink = [0.12, 0.14, 0.16];
muted = [0.38, 0.41, 0.44];

for i = 1:numel(conditions)
    frameAName = sprintf('frame_%04d.bmp', conditions(i).frameIndex);
    frameBName = sprintf('frame_%04d.bmp', conditions(i).frameIndex + 1);
    imageA = cropGrayRaw(fullfile(conditions(i).directory, frameAName), conditions(i).roi);
    imageB = cropGrayRaw(fullfile(conditions(i).directory, frameBName), conditions(i).roi);

    centerA = locateFeature(double(imageA), [300, 300], conditions(i).polarity, ...
        42, conditions(i).featureRadius);
    predictedCenterB = centerA + [-conditions(i).pixelStep, 0];
    centerB = locateFeature(double(imageB), predictedCenterB, conditions(i).polarity, ...
        max(7, ceil(conditions(i).pixelStep / 2) + 3), conditions(i).featureRadius);

    midpoint = 0.5 * (centerA + centerB);
    [zoomA, origin] = fixedCrop(imageA, midpoint, conditions(i).zoomSize);
    [zoomB, ~] = fixedCrop(imageB, midpoint, conditions(i).zoomSize);
    localCenterA = centerA - origin + [1, 1];
    localCenterB = centerB - origin + [1, 1];
    measuredShift = centerB - centerA;

    fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [50, 50, 1750, 1300], ...
        'Renderer', 'painters');
    ax = axes(fig, 'Position', [0.14, 0.18, 0.72, 0.69]);
    imshow(zoomA, [0, 255], 'Parent', ax, 'InitialMagnification', 'fit');
    axis(ax, 'image');
    axis(ax, 'on');
    box(ax, 'on');
    ax.FontName = fontName;
    ax.FontSize = 13;
    ax.LineWidth = 1.0;
    ax.TickDir = 'out';
    ax.XColor = ink;
    ax.YColor = ink;
    xlabel(ax, 'x（pixel）', 'FontName', fontName, 'FontSize', 14, 'Color', ink);
    ylabel(ax, 'y（pixel）', 'FontName', fontName, 'FontSize', 14, 'Color', ink);

    hold(ax, 'on');
    thresholdA = graythresh(zoomA) * 255;
    thresholdB = graythresh(zoomB) * 255;
    [~, contourBefore] = contour(ax, double(zoomA), [thresholdA, thresholdA], ...
        'Color', blue, 'LineWidth', 2.4, 'LineStyle', '-');
    [~, contourAfter] = contour(ax, double(zoomB), [thresholdB, thresholdB], ...
        'Color', orange, 'LineWidth', 2.4, 'LineStyle', '--');

    plot(ax, localCenterA(1), localCenterA(2), 'o', ...
        'MarkerSize', 10, 'LineWidth', 2.2, 'Color', blue, 'MarkerFaceColor', 'w');
    plot(ax, localCenterB(1), localCenterB(2), 's', ...
        'MarkerSize', 10, 'LineWidth', 2.2, 'Color', orange, 'MarkerFaceColor', 'w');

    dx = localCenterB(1) - localCenterA(1);
    dy = localCenterB(2) - localCenterA(2);
    quiver(ax, localCenterA(1), localCenterA(2), dx, dy, 0, ...
        'Color', ink, 'LineWidth', 2.5, 'MaxHeadSize', 1.9);

    labelX = 0.5 * (localCenterA(1) + localCenterB(1));
    labelY = 0.5 * (localCenterA(2) + localCenterB(2)) - 0.10 * conditions(i).zoomSize;
    text(ax, labelX, labelY, sprintf('%.2f pixels', hypot(dx, dy)), ...
        'FontName', fontName, 'FontSize', 13, 'FontWeight', 'bold', ...
        'Color', ink, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'BackgroundColor', 'w', 'Margin', 4, 'EdgeColor', [0.78, 0.80, 0.82]);
    hold(ax, 'off');

    titleLine = sprintf('%s 物鏡，設定位移 %.1f µm', ...
        conditions(i).magnification, conditions(i).physicalStep);
    equationLine = sprintf('%.1f µm ÷ %.4f µm/pixel = %.3f pixels', ...
        conditions(i).physicalStep, conditions(i).sampling, conditions(i).pixelStep);
    title(ax, {titleLine; equationLine}, 'FontName', fontName, ...
        'FontSize', 17, 'FontWeight', 'normal', 'Color', ink);

    legend(ax, [contourBefore, contourAfter], {'移動前邊界', '移動後邊界'}, ...
        'FontName', fontName, 'FontSize', 12.5, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'Box', 'off');

    annotation(fig, 'textbox', [0.12, 0.055, 0.76, 0.04], ...
        'String', '影像採用原始 8-bit 灰階範圍（0–255），未進行對比拉伸。', ...
        'FontName', fontName, 'FontSize', 12.5, 'Color', muted, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'LineStyle', 'none', 'Interpreter', 'none');

    pngPath = fullfile(outputDir, [conditions(i).fileStem, '.png']);
    pdfPath = fullfile(outputDir, [conditions(i).fileStem, '.pdf']);
    figPath = fullfile(outputDir, [conditions(i).fileStem, '.fig']);
    exportgraphics(fig, pngPath, 'Resolution', 220);
    exportgraphics(fig, pdfPath, 'ContentType', 'image', 'Resolution', 220);
    savefig(fig, figPath);
    close(fig);

    conditions(i).frameAName = frameAName;
    conditions(i).frameBName = frameBName;
    conditions(i).measuredDx = measuredShift(1);
    conditions(i).measuredDy = measuredShift(2);
    conditions(i).measuredMagnitude = hypot(measuredShift(1), measuredShift(2));
    fprintf('%s | raw display [0,255] | measured shift %.3f px | %s\n', ...
        conditions(i).fileStem, conditions(i).measuredMagnitude, pngPath);
end

metadataPath = fullfile(outputDir, 'single_condition_figures_metadata.json');
fid = fopen(metadataPath, 'w', 'n', 'UTF-8');
if fid < 0
    error('Could not write metadata: %s', metadataPath);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(conditions, PrettyPrint=true));

function image = cropGrayRaw(path, roi)
    image = imread(path);
    if ndims(image) == 3
        image = rgb2gray(image);
    end
    if ~isa(image, 'uint8')
        image = im2uint8(image);
    end
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
    center = [sum(weights .* gridX, 'all') / weightSum, ...
              sum(weights .* gridY, 'all') / weightSum];
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
