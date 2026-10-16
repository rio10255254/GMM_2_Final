%% English, compact MATLAB figures for displacement acquisition.
% Outputs four single-condition figures and two 30-position motion figures.
% Raw images are displayed in the native 8-bit range [0, 255].

clear; close all; clc;

outputDir = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Slide_Assets\Displacement_Acquisition_Concept\english_compact_figures';
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
        '01_50x_0p5um_single_step', ...
        '02_50x_1p0um_single_step', ...
        '03_20x_0p5um_single_step', ...
        '04_20x_1p0um_single_step'});

fontName = 'Arial';
blue = [0.08, 0.38, 0.68];
orange = [0.90, 0.34, 0.08];
ink = [0.12, 0.14, 0.16];
muted = [0.38, 0.41, 0.44];
lightLine = [0.80, 0.82, 0.84];

metadata = struct([]);

%% Four compact, single-condition figures
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
    measuredMagnitude = hypot(measuredShift(1), measuredShift(2));

    fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [40, 40, 1800, 980], ...
        'Renderer', 'painters');
    ax = axes(fig, 'Position', [0.075, 0.15, 0.59, 0.72]);
    imshow(zoomA, [0, 255], 'Parent', ax, 'InitialMagnification', 'fit');
    axis(ax, 'image');
    axis(ax, 'on');
    box(ax, 'on');
    formatAxes(ax, fontName, ink, 16);
    xlabel(ax, 'x (pixel)', 'FontName', fontName, 'FontSize', 18, 'Color', ink);
    ylabel(ax, 'y (pixel)', 'FontName', fontName, 'FontSize', 18, 'Color', ink);

    hold(ax, 'on');
    thresholdA = graythresh(zoomA) * 255;
    thresholdB = graythresh(zoomB) * 255;
    contour(ax, double(zoomA), [thresholdA, thresholdA], ...
        'Color', blue, 'LineWidth', 2.8, 'LineStyle', '-');
    contour(ax, double(zoomB), [thresholdB, thresholdB], ...
        'Color', orange, 'LineWidth', 2.8, 'LineStyle', '--');
    plot(ax, localCenterA(1), localCenterA(2), 'o', ...
        'MarkerSize', 11, 'LineWidth', 2.4, 'Color', blue, 'MarkerFaceColor', 'w');
    plot(ax, localCenterB(1), localCenterB(2), 's', ...
        'MarkerSize', 11, 'LineWidth', 2.4, 'Color', orange, 'MarkerFaceColor', 'w');
    dx = localCenterB(1) - localCenterA(1);
    dy = localCenterB(2) - localCenterA(2);
    quiver(ax, localCenterA(1), localCenterA(2), dx, dy, 0, ...
        'Color', ink, 'LineWidth', 3.0, 'MaxHeadSize', 2.1);
    hold(ax, 'off');

    title(ax, sprintf('%s Objective — Consecutive-Frame Displacement', conditions(i).magnification), ...
        'FontName', fontName, 'FontSize', 23, 'FontWeight', 'bold', 'Color', ink);

    infoAx = axes(fig, 'Position', [0.715, 0.16, 0.245, 0.68]); %#ok<LAXES>
    axis(infoAx, [0, 1, 0, 1]);
    axis(infoAx, 'off');
    hold(infoAx, 'on');
    plot(infoAx, [0, 1], [0.93, 0.93], '-', 'Color', lightLine, 'LineWidth', 1.2);
    text(infoAx, 0, 0.86, 'PHYSICAL STAGE STEP', 'FontName', fontName, ...
        'FontSize', 14, 'Color', muted, 'FontWeight', 'bold');
    text(infoAx, 0, 0.75, sprintf('%.1f µm', conditions(i).physicalStep), ...
        'FontName', fontName, 'FontSize', 31, 'Color', ink, 'FontWeight', 'bold');
    plot(infoAx, [0, 1], [0.66, 0.66], '-', 'Color', lightLine, 'LineWidth', 1.2);
    text(infoAx, 0, 0.58, 'OBJECT-SPACE SAMPLING', 'FontName', fontName, ...
        'FontSize', 14, 'Color', muted, 'FontWeight', 'bold');
    text(infoAx, 0, 0.48, sprintf('%.4f µm/pixel', conditions(i).sampling), ...
        'FontName', fontName, 'FontSize', 22, 'Color', ink, 'FontWeight', 'bold');
    plot(infoAx, [0, 1], [0.39, 0.39], '-', 'Color', lightLine, 'LineWidth', 1.2);
    text(infoAx, 0, 0.31, 'EQUIVALENT IMAGE SHIFT', 'FontName', fontName, ...
        'FontSize', 14, 'Color', muted, 'FontWeight', 'bold');
    text(infoAx, 0, 0.20, sprintf('%.3f pixels', conditions(i).pixelStep), ...
        'FontName', fontName, 'FontSize', 28, 'Color', orange, 'FontWeight', 'bold');
    text(infoAx, 0, 0.08, sprintf('Tracked: %.3f pixels', measuredMagnitude), ...
        'FontName', fontName, 'FontSize', 16, 'Color', ink);
    hold(infoAx, 'off');

    annotation(fig, 'textbox', [0.075, 0.045, 0.885, 0.045], ...
        'String', 'Blue solid: frame t    Orange dashed: frame t+1    Native 8-bit display (0–255); no contrast stretching.', ...
        'FontName', fontName, 'FontSize', 15, 'Color', muted, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'LineStyle', 'none', 'Interpreter', 'none');

    exportAll(fig, outputDir, conditions(i).fileStem);
    close(fig);

    metadata(i).type = 'single_step'; %#ok<SAGROW>
    metadata(i).magnification = conditions(i).magnification;
    metadata(i).physicalStepUm = conditions(i).physicalStep;
    metadata(i).samplingUmPerPixel = conditions(i).sampling;
    metadata(i).equivalentPixelStep = conditions(i).pixelStep;
    metadata(i).trackedPixelShift = measuredMagnitude;
    metadata(i).frameA = frameAName;
    metadata(i).frameB = frameBName;
end

%% Two multi-position motion figures (0.5 µm sequence, first 30 positions)
multiConfigs = struct( ...
    'magnification', {'50×', '20×'}, ...
    'directory', {conditions(1).directory, conditions(3).directory}, ...
    'roi', {conditions(1).roi, conditions(3).roi}, ...
    'polarity', {'dark', 'bright'}, ...
    'featureRadius', {24, 12}, ...
    'pixelStep', {7.246, 2.899}, ...
    'sampling', {0.0690, 0.1725}, ...
    'pitch', {[73, 72], [30, 30]}, ...
    'viewMargin', {[38, 92], [25, 48]}, ...
    'fileStem', {'05_50x_30_position_motion', '06_20x_30_position_motion'});

snapshotIndices = [1, 8, 15, 22, 30];
snapshotColors = [ ...
    0.08, 0.28, 0.55; ...
    0.13, 0.45, 0.72; ...
    0.32, 0.62, 0.78; ...
    0.93, 0.58, 0.18; ...
    0.88, 0.27, 0.08];

for i = 1:numel(multiConfigs)
    [trajectory, background] = buildCalibratedThirtyPositionPath(multiConfigs(i));
    pitchX = multiConfigs(i).pitch(1);
    pitchY = multiConfigs(i).pitch(2);
    xMargin = multiConfigs(i).viewMargin(1);
    yMargin = multiConfigs(i).viewMargin(2);
    xMin = max(1, floor(min(trajectory(:, 1)) - xMargin));
    xMax = min(size(background, 2), ceil(max(trajectory(:, 1)) + xMargin));
    yMin = max(1, floor(trajectory(1, 2) - pitchY - yMargin));
    yMax = min(size(background, 1), ceil(trajectory(1, 2) + pitchY + yMargin));
    viewImage = background(yMin:yMax, xMin:xMax);
    localTrajectory = trajectory - [xMin - 1, yMin - 1];

    fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [40, 40, 1800, 980], ...
        'Renderer', 'painters');
    ax = axes(fig, 'Position', [0.075, 0.15, 0.69, 0.72]);
    imshow(viewImage, [0, 255], 'Parent', ax, 'InitialMagnification', 'fit');
    axis(ax, 'image');
    axis(ax, 'on');
    box(ax, 'on');
    formatAxes(ax, fontName, ink, 16);
    xlabel(ax, 'x (pixel)', 'FontName', fontName, 'FontSize', 18, 'Color', ink);
    ylabel(ax, 'y (pixel)', 'FontName', fontName, 'FontSize', 18, 'Color', ink);
    title(ax, sprintf('%s Objective — 30-Position Field Translation', multiConfigs(i).magnification), ...
        'FontName', fontName, 'FontSize', 23, 'FontWeight', 'bold', 'Color', ink);

    hold(ax, 'on');
    offsets = [0, -pitchY; 0, 0; 0, pitchY];
    for p = 1:size(offsets, 1)
        path = localTrajectory + offsets(p, :);
        plot(ax, path(:, 1), path(:, 2), '-', 'Color', [0.76, 0.78, 0.80], 'LineWidth', 1.2);
        for s = 1:numel(snapshotIndices)
            idx = snapshotIndices(s);
            plot(ax, path(idx, 1), path(idx, 2), 'o', ...
                'MarkerSize', 6.5, 'MarkerFaceColor', snapshotColors(s, :), ...
                'MarkerEdgeColor', 'w', 'LineWidth', 0.8);
        end
    end
    centralPath = localTrajectory;
    plot(ax, centralPath(:, 1), centralPath(:, 2), '-', 'Color', ink, 'LineWidth', 2.3);
    quiver(ax, centralPath(1, 1), centralPath(1, 2), ...
        centralPath(end, 1) - centralPath(1, 1), ...
        centralPath(end, 2) - centralPath(1, 2), 0, ...
        'Color', ink, 'LineWidth', 3.0, 'MaxHeadSize', 0.45);

    legendHandles = gobjects(1, numel(snapshotIndices));
    for s = 1:numel(snapshotIndices)
        legendHandles(s) = plot(ax, NaN, NaN, 'o', 'MarkerSize', 8, ...
            'MarkerFaceColor', snapshotColors(s, :), 'MarkerEdgeColor', 'w');
    end
    legendLabels = arrayfun(@(v) sprintf('Position %d', v), snapshotIndices, 'UniformOutput', false);
    legend(ax, legendHandles, legendLabels, 'Location', 'northoutside', ...
        'Orientation', 'horizontal', 'Box', 'off', 'FontName', fontName, 'FontSize', 14);
    hold(ax, 'off');

    infoAx = axes(fig, 'Position', [0.805, 0.22, 0.16, 0.56]); %#ok<LAXES>
    axis(infoAx, [0, 1, 0, 1]);
    axis(infoAx, 'off');
    hold(infoAx, 'on');
    text(infoAx, 0, 0.87, 'SEQUENCE', 'FontName', fontName, 'FontSize', 14, ...
        'Color', muted, 'FontWeight', 'bold');
    text(infoAx, 0, 0.76, '30 positions', 'FontName', fontName, 'FontSize', 25, ...
        'Color', ink, 'FontWeight', 'bold');
    plot(infoAx, [0, 1], [0.66, 0.66], '-', 'Color', lightLine, 'LineWidth', 1.2);
    text(infoAx, 0, 0.57, 'STAGE STEP', 'FontName', fontName, 'FontSize', 14, ...
        'Color', muted, 'FontWeight', 'bold');
    text(infoAx, 0, 0.46, '0.5 µm', 'FontName', fontName, 'FontSize', 25, ...
        'Color', ink, 'FontWeight', 'bold');
    plot(infoAx, [0, 1], [0.36, 0.36], '-', 'Color', lightLine, 'LineWidth', 1.2);
    text(infoAx, 0, 0.27, 'PER-POSITION SHIFT', 'FontName', fontName, 'FontSize', 14, ...
        'Color', muted, 'FontWeight', 'bold');
    text(infoAx, 0, 0.16, sprintf('%.3f pixels', multiConfigs(i).pixelStep), ...
        'FontName', fontName, 'FontSize', 23, 'Color', orange, 'FontWeight', 'bold');
    hold(infoAx, 'off');
    axis(infoAx, 'off');

    annotation(fig, 'textbox', [0.075, 0.045, 0.89, 0.045], ...
        'String', 'Colored markers show selected positions along the 30-position trajectory; all structures translate together.', ...
        'FontName', fontName, 'FontSize', 15, 'Color', muted, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'LineStyle', 'none', 'Interpreter', 'none');

    exportAll(fig, outputDir, multiConfigs(i).fileStem);
    close(fig);

    m = numel(metadata) + 1;
    metadata(m).type = 'multi_position';
    metadata(m).magnification = multiConfigs(i).magnification;
    metadata(m).positions = 30;
    metadata(m).physicalStepUm = 0.5;
    metadata(m).samplingUmPerPixel = multiConfigs(i).sampling;
    metadata(m).equivalentPixelStep = multiConfigs(i).pixelStep;
    metadata(m).trackedStart = trajectory(1, :);
    metadata(m).trackedEnd = trajectory(end, :);
end

metadataPath = fullfile(outputDir, 'figure_metadata.json');
fid = fopen(metadataPath, 'w', 'n', 'UTF-8');
if fid < 0
    error('Could not write metadata: %s', metadataPath);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(metadata, PrettyPrint=true));

fprintf('\nCreated six English compact figures in:\n%s\n', outputDir);

function [trajectory, background] = buildCalibratedThirtyPositionPath(config)
    frameName = 'frame_0000.bmp';
    background = cropGrayRaw(fullfile(config.directory, frameName), config.roi);
    center0 = locateFeature(double(background), [300, 300], config.polarity, ...
        42, config.featureRadius);
    trajectory = repmat(center0, 30, 1);
    trajectory(:, 1) = center0(1) - (0:29)' * config.pixelStep;
end

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

function formatAxes(ax, fontName, ink, fontSize)
    ax.FontName = fontName;
    ax.FontSize = fontSize;
    ax.LineWidth = 1.1;
    ax.TickDir = 'out';
    ax.XColor = ink;
    ax.YColor = ink;
end

function exportAll(fig, outputDir, fileStem)
    pngPath = fullfile(outputDir, [fileStem, '.png']);
    pdfPath = fullfile(outputDir, [fileStem, '.pdf']);
    figPath = fullfile(outputDir, [fileStem, '.fig']);
    exportgraphics(fig, pngPath, 'Resolution', 220);
    exportgraphics(fig, pdfPath, 'ContentType', 'image', 'Resolution', 220);
    savefig(fig, figPath);
end
