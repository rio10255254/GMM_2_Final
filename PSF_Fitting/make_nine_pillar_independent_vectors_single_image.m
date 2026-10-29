PROJECT_ROOT = fileparts(fileparts(mfilename('fullpath')));
%% Single-image schematic: nine independently estimated displacement vectors.

clear; close all; clc;

sourcePath = fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp');
outputDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Slide_Assets/Nine_Pillar_Displacement_Dispersion');
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

rawImage = imread(sourcePath);
if ndims(rawImage) == 3, rawImage = rgb2gray(rawImage); end
if ~isa(rawImage, 'uint8'), rawImage = im2uint8(rawImage); end

roi = [1150, 100, 600, 600];
pillarField = rawImage(roi(2):(roi(2) + roi(4) - 1), roi(1):(roi(1) + roi(3) - 1));
centerSeed = locateDarkFeature(double(pillarField), [300, 300], 42, 24);

pitchX = 73;
pitchY = 72;
centers = zeros(9, 2);
index = 0;
for row = -1:1
    for col = -1:1
        index = index + 1;
        seed = centerSeed + [col * pitchX, row * pitchY];
        centers(index, :) = locateDarkFeature(double(pillarField), seed, 20, 24);
    end
end

% Conceptual vector differences: common translation direction with local variation.
% These vectors illustrate the measurement concept and are intentionally not to scale.
vectorLength = [17.0, 21.5, 18.8, 23.0, 16.0, 20.2, 18.0, 22.0, 19.3];
vectorDy = [1.4, -1.2, 0.4, -1.7, 1.0, -0.6, 1.3, -1.0, 0.2];
vectors = [-vectorLength(:), vectorDy(:)];
boundaryRadius = zeros(9, 1);
for j = 1:9
    boundaryRadius(j) = estimateDarkHalfHeightRadius(double(pillarField), centers(j, :), 36);
end

% Crop from the complete geometry rather than only the initial centers so
% shifted boundaries, arrowheads, and labels cannot be clipped.
endCenters = centers + vectors;
xGeometryMin = min([centers(:, 1) - boundaryRadius; endCenters(:, 1) - boundaryRadius]);
xGeometryMax = max([centers(:, 1) + boundaryRadius; endCenters(:, 1) + boundaryRadius]);
yGeometryMin = min([centers(:, 2) - boundaryRadius; endCenters(:, 2) - boundaryRadius; centers(:, 2) - 34]);
yGeometryMax = max([centers(:, 2) + boundaryRadius; endCenters(:, 2) + boundaryRadius]);
x0 = max(1, floor(xGeometryMin - 6));
x1 = min(size(pillarField, 2), ceil(xGeometryMax + 6));
y0 = max(1, floor(yGeometryMin - 4));
y1 = min(size(pillarField, 1), ceil(yGeometryMax + 6));
displayImage = pillarField(y0:y1, x0:x1);
localCenters = centers - [x0 - 1, y0 - 1];

blue = [0.08, 0.38, 0.68];
orange = [0.90, 0.34, 0.08];
ink = [0.12, 0.14, 0.16];
muted = [0.38, 0.41, 0.44];
fontName = 'Arial';

fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [50, 40, 1080, 990], ...
    'Renderer', 'painters');

annotation(fig, 'textbox', [0.10, 0.950, 0.36, 0.034], ...
    'String', '—  Initial boundary', 'FontName', fontName, 'FontSize', 18, ...
    'Color', blue, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');
annotation(fig, 'textbox', [0.54, 0.950, 0.36, 0.034], ...
    'String', '--  Local boundary', 'FontName', fontName, 'FontSize', 18, ...
    'Color', orange, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

ax = axes(fig, 'Position', [0.038, 0.066, 0.924, 0.866]);
imshow(displayImage, [0, 255], 'Parent', ax, 'InitialMagnification', 'fit');
axis(ax, 'image', 'off');
hold(ax, 'on');

for j = 1:9
    startPoint = localCenters(j, :);
    endPoint = startPoint + vectors(j, :);

    theta = linspace(0, 2 * pi, 240);
    plot(ax, startPoint(1) + boundaryRadius(j) * cos(theta), ...
        startPoint(2) + boundaryRadius(j) * sin(theta), ...
        '-', 'Color', blue, 'LineWidth', 2.3);
    plot(ax, endPoint(1) + boundaryRadius(j) * cos(theta), ...
        endPoint(2) + boundaryRadius(j) * sin(theta), ...
        '--', 'Color', orange, 'LineWidth', 2.3);

    drawFilledArrow(ax, startPoint, endPoint, ink, 3.3, 7.0, 6.8);
    plot(ax, startPoint(1), startPoint(2), 'o', ...
        'MarkerSize', 13, 'LineWidth', 1.8, 'Color', 'w', 'MarkerFaceColor', blue);
    plot(ax, endPoint(1), endPoint(2), 's', ...
        'MarkerSize', 11, 'LineWidth', 1.8, 'Color', 'w', 'MarkerFaceColor', orange);

    labelX = 0.5 * (startPoint(1) + endPoint(1));
    labelY = startPoint(2) - 27;
    text(ax, labelX, labelY, sprintf('d_{t,%d}', j), ...
        'Interpreter', 'tex', 'FontName', fontName, 'FontSize', 18, ...
        'FontWeight', 'bold', 'Color', ink, 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle', 'BackgroundColor', 'w', ...
        'Margin', 2, 'EdgeColor', 'none');
end

rectangle(ax, 'Position', [0.5, 0.5, size(displayImage, 2) - 1, size(displayImage, 1) - 1], ...
    'EdgeColor', [0.24, 0.26, 0.28], 'LineWidth', 1.0);
hold(ax, 'off');

annotation(fig, 'textbox', [0.045, 0.012, 0.91, 0.034], ...
    'String', 'Independent local displacement vectors; differences are enlarged for visual explanation.', ...
    'FontName', fontName, 'FontSize', 15, 'Color', muted, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

fileStem = 'nine_pillar_independent_displacement_boundary_overlay';
pngPath = fullfile(outputDir, [fileStem, '.png']);
pdfPath = fullfile(outputDir, [fileStem, '.pdf']);
figPath = fullfile(outputDir, [fileStem, '.fig']);
exportgraphics(fig, pngPath, 'Resolution', 220);
exportgraphics(fig, pdfPath, 'ContentType', 'image', 'Resolution', 220);
savefig(fig, figPath);

metadata = struct();
metadata.source_image = sourcePath;
metadata.display_range = [0, 255];
metadata.contrast_stretching = false;
metadata.vector_type = 'conceptual_not_to_scale';
metadata.visual_vectors_px = vectors;
metadata.half_height_boundary_radius_px = boundaryRadius;
metadataPath = fullfile(outputDir, [fileStem, '_metadata.json']);
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

function radius = estimateDarkHalfHeightRadius(image, center, maxRadius)
    [gridX, gridY] = meshgrid(1:size(image, 2), 1:size(image, 1));
    radialDistance = hypot(gridX - center(1), gridY - center(2));
    centerMask = radialDistance <= 5;
    backgroundMask = radialDistance >= (maxRadius - 5) & radialDistance <= maxRadius;
    centerLevel = mean(image(centerMask), 'all');
    backgroundLevel = median(image(backgroundMask), 'all');
    halfLevel = 0.5 * (centerLevel + backgroundLevel);

    radialMean = nan(maxRadius, 1);
    for r = 1:maxRadius
        annulus = radialDistance >= (r - 0.5) & radialDistance < (r + 0.5);
        radialMean(r) = mean(image(annulus), 'all');
    end
    crossing = find(radialMean >= halfLevel, 1, 'first');
    if isempty(crossing)
        radius = 24;
    else
        radius = crossing;
    end
end

function drawFilledArrow(ax, startPoint, endPoint, color, shaftWidth, headLength, headHalfWidth)
    direction = endPoint - startPoint;
    vectorLength = hypot(direction(1), direction(2));
    if vectorLength <= eps
        return;
    end

    unitDirection = direction / vectorLength;
    normalDirection = [-unitDirection(2), unitDirection(1)];
    headLength = min(headLength, 0.42 * vectorLength);
    headBase = endPoint - headLength * unitDirection;

    plot(ax, [startPoint(1), headBase(1)], [startPoint(2), headBase(2)], '-', ...
        'Color', color, 'LineWidth', shaftWidth);
    patch(ax, ...
        [endPoint(1), headBase(1) + headHalfWidth * normalDirection(1), ...
         headBase(1) - headHalfWidth * normalDirection(1)], ...
        [endPoint(2), headBase(2) + headHalfWidth * normalDirection(2), ...
         headBase(2) - headHalfWidth * normalDirection(2)], ...
        color, 'EdgeColor', color, 'LineWidth', 0.8);
end
