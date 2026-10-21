%% Build an image-based acquisition concept figure from the real raw sequences.
% The figure intentionally focuses on the four acquisition conditions only.

clear; close all; clc;

outputDir = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Slide_Assets\Displacement_Acquisition_Concept';
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

conditions = struct( ...
    'label', { ...
        '50×｜設定位移 0.5 µm｜等效像素位移 7.246 pixels', ...
        '50×｜設定位移 1.0 µm｜等效像素位移 14.493 pixels', ...
        '20×｜設定位移 0.5 µm｜等效像素位移 2.899 pixels', ...
        '20×｜設定位移 1.0 µm｜等效像素位移 5.797 pixels'}, ...
    'sampling', { ...
        '物體空間取樣：0.0690 µm/pixel', ...
        '物體空間取樣：0.0690 µm/pixel', ...
        '物體空間取樣：0.1725 µm/pixel', ...
        '物體空間取樣：0.1725 µm/pixel'}, ...
    'directory', { ...
        'D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_0p5um\bmp', ...
        'D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_1um\bmp', ...
        'D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\20x_0p5um\bmp', ...
        'D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\20x_1um\bmp'}, ...
    'expectedShift', {7.246, 14.493, 2.899, 5.797}, ...
    'roi', { ...
        [1150, 100, 600, 600], ...
        [1150, 100, 600, 600], ...
        [720, 70, 600, 600], ...
        [720, 70, 600, 600]});

for i = 1:numel(conditions)
    files = dir(fullfile(conditions(i).directory, 'frame_*.bmp'));
    if numel(files) < 2
        error('Not enough frames in %s', conditions(i).directory);
    end
    [~, order] = sort({files.name});
    files = files(order);

    [pairIndex, dx, dy, corrValue] = selectRepresentativePair( ...
        conditions(i).directory, files, conditions(i).roi, conditions(i).expectedShift);

    imageA = cropGray(fullfile(conditions(i).directory, files(pairIndex).name), conditions(i).roi);
    imageB = cropGray(fullfile(conditions(i).directory, files(pairIndex + 1).name), conditions(i).roi);
    [displayA, displayB] = sharedRobustDisplay(imageA, imageB);

    overlay = zeros([size(displayA), 3]);
    overlay(:, :, 1) = displayB;
    overlay(:, :, 2) = displayA;
    overlay(:, :, 3) = displayA;

    conditions(i).frameA = files(pairIndex).name;
    conditions(i).frameB = files(pairIndex + 1).name;
    conditions(i).estimatedDx = dx;
    conditions(i).estimatedDy = dy;
    conditions(i).alignedCorrelation = corrValue;
    conditions(i).displayA = displayA;
    conditions(i).displayB = displayB;
    conditions(i).overlay = overlay;
end

fontName = 'Microsoft JhengHei UI';
fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [40, 40, 2400, 1320], ...
    'Renderer', 'painters');

annotation(fig, 'textbox', [0.02, 0.945, 0.96, 0.045], ...
    'String', '四組位移條件之實際相鄰影像與位移示意', ...
    'FontName', fontName, 'FontSize', 24, 'FontWeight', 'bold', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

cardLeft = [0.025, 0.515, 0.025, 0.515];
cardBottom = [0.515, 0.515, 0.065, 0.065];
cardWidth = 0.46;
cardHeight = 0.405;
imageGap = 0.010;
imageWidth = (cardWidth - 4 * imageGap) / 3;
imageHeight = imageWidth * (2400 / 1320);

captions = {'影格 t', '影格 t+1', '紅青疊合'};

for i = 1:numel(conditions)
    x0 = cardLeft(i);
    y0 = cardBottom(i);

    annotation(fig, 'rectangle', [x0, y0, cardWidth, cardHeight], ...
        'Color', [0.78, 0.80, 0.82], 'LineWidth', 1.0);
    annotation(fig, 'textbox', [x0 + 0.008, y0 + cardHeight - 0.052, cardWidth - 0.016, 0.036], ...
        'String', conditions(i).label, 'FontName', fontName, 'FontSize', 16, ...
        'FontWeight', 'bold', 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle', 'LineStyle', 'none', 'Interpreter', 'none');
    annotation(fig, 'textbox', [x0 + 0.008, y0 + cardHeight - 0.085, cardWidth - 0.016, 0.030], ...
        'String', conditions(i).sampling, 'FontName', fontName, 'FontSize', 12.5, ...
        'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
        'Color', [0.25, 0.25, 0.25], 'LineStyle', 'none', 'Interpreter', 'none');

    images = {conditions(i).displayA, conditions(i).displayB, conditions(i).overlay};
    for j = 1:3
        axX = x0 + imageGap + (j - 1) * (imageWidth + imageGap);
        axY = y0 + 0.055;
        ax = axes(fig, 'Position', [axX, axY, imageWidth, imageHeight]); %#ok<LAXES>
        imshow(images{j}, 'Parent', ax);
        axis(ax, 'image', 'off');
        hold(ax, 'on');
        rectangle(ax, 'Position', [0.5, 0.5, size(images{j}, 2) - 1, size(images{j}, 1) - 1], ...
            'EdgeColor', [0.15, 0.15, 0.15], 'LineWidth', 0.8);
        hold(ax, 'off');

        annotation(fig, 'textbox', [axX, y0 + 0.016, imageWidth, 0.028], ...
            'String', captions{j}, 'FontName', fontName, 'FontSize', 12.5, ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
            'LineStyle', 'none', 'Interpreter', 'none');
    end
end

annotation(fig, 'textbox', [0.02, 0.012, 0.96, 0.030], ...
    'String', '疊合圖中，青色代表影格 t，紅色代表影格 t+1；重合區域呈灰白色。', ...
    'FontName', fontName, 'FontSize', 12.5, 'Color', [0.25, 0.25, 0.25], ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'LineStyle', 'none', 'Interpreter', 'none');

pngPath = fullfile(outputDir, '01_four_condition_displacement_acquisition_concept.png');
pdfPath = fullfile(outputDir, '01_four_condition_displacement_acquisition_concept.pdf');
figPath = fullfile(outputDir, '01_four_condition_displacement_acquisition_concept.fig');
exportgraphics(fig, pngPath, 'Resolution', 220);
exportgraphics(fig, pdfPath, 'ContentType', 'image', 'Resolution', 220);
savefig(fig, figPath);

metadata = rmfield(conditions, {'displayA', 'displayB', 'overlay'});
jsonPath = fullfile(outputDir, '01_four_condition_displacement_acquisition_concept_metadata.json');
fid = fopen(jsonPath, 'w', 'n', 'UTF-8');
if fid < 0
    error('Could not write metadata file: %s', jsonPath);
end
cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(metadata, PrettyPrint=true));

fprintf('\nCreated: %s\n', pngPath);
for i = 1:numel(conditions)
    fprintf('%s | %s -> %s | estimated shift = (%+.1f, %+.1f) px | aligned corr = %.4f\n', ...
        conditions(i).label, conditions(i).frameA, conditions(i).frameB, ...
        conditions(i).estimatedDx, conditions(i).estimatedDy, conditions(i).alignedCorrelation);
end

function [pairIndex, bestDx, bestDy, bestCorr] = selectRepresentativePair(directory, files, roi, expectedShift)
    firstCandidate = min(6, numel(files) - 1);
    lastCandidate = min(36, numel(files) - 1);
    pairIndex = firstCandidate;
    bestDx = NaN;
    bestDy = NaN;
    bestCorr = -Inf;
    bestCost = Inf;

    for k = firstCandidate:lastCandidate
        imageA = cropGray(fullfile(directory, files(k).name), roi);
        imageB = cropGray(fullfile(directory, files(k + 1).name), roi);
        [dx, dy] = integerPhaseShift(imageA, imageB, 24);
        corrValue = alignedCorrelation(imageA, imageB, dx, dy, 28);
        cost = abs(abs(dx) - expectedShift) + 0.45 * abs(dy) - 0.35 * corrValue;
        if cost < bestCost
            bestCost = cost;
            pairIndex = k;
            bestDx = dx;
            bestDy = dy;
            bestCorr = corrValue;
        end
    end
end

function image = cropGray(path, roi)
    image = imread(path);
    if ndims(image) == 3
        image = rgb2gray(image);
    end
    image = im2double(image);
    x = roi(1);
    y = roi(2);
    w = roi(3);
    h = roi(4);
    if x < 1 || y < 1 || x + w - 1 > size(image, 2) || y + h - 1 > size(image, 1)
        error('ROI exceeds image bounds for %s', path);
    end
    image = image(y:(y + h - 1), x:(x + w - 1));
end

function [displayA, displayB] = sharedRobustDisplay(imageA, imageB)
    values = sort([imageA(:); imageB(:)]);
    n = numel(values);
    lowIndex = max(1, round(0.005 * n));
    highIndex = min(n, round(0.995 * n));
    lowValue = values(lowIndex);
    highValue = values(highIndex);
    if highValue <= lowValue
        lowValue = min(values);
        highValue = max(values);
    end
    if highValue <= lowValue
        displayA = zeros(size(imageA));
        displayB = zeros(size(imageB));
        return;
    end
    displayA = min(max((imageA - lowValue) ./ (highValue - lowValue), 0), 1);
    displayB = min(max((imageB - lowValue) ./ (highValue - lowValue), 0), 1);
end

function [dx, dy] = integerPhaseShift(imageA, imageB, maxShift)
    [height, width] = size(imageA);
    wx = 0.5 - 0.5 * cos(2 * pi * (0:(width - 1)) / max(width - 1, 1));
    wy = 0.5 - 0.5 * cos(2 * pi * (0:(height - 1))' / max(height - 1, 1));
    window = wy * wx;
    a = (imageA - mean(imageA, 'all')) .* window;
    b = (imageB - mean(imageB, 'all')) .* window;
    spectrumA = fft2(a);
    spectrumB = fft2(b);
    crossPower = spectrumB .* conj(spectrumA);
    crossPower = crossPower ./ max(abs(crossPower), eps);
    correlation = real(fftshift(ifft2(crossPower)));
    centerY = floor(height / 2) + 1;
    centerX = floor(width / 2) + 1;
    yRange = (centerY - maxShift):(centerY + maxShift);
    xRange = (centerX - maxShift):(centerX + maxShift);
    searchArea = correlation(yRange, xRange);
    [~, linearIndex] = max(searchArea, [], 'all', 'linear');
    [peakY, peakX] = ind2sub(size(searchArea), linearIndex);
    dy = yRange(peakY) - centerY;
    dx = xRange(peakX) - centerX;
end

function value = alignedCorrelation(imageA, imageB, dx, dy, margin)
    shiftedB = circshift(imageB, [-dy, -dx]);
    rowRange = (1 + margin):(size(imageA, 1) - margin);
    colRange = (1 + margin):(size(imageA, 2) - margin);
    a = imageA(rowRange, colRange);
    b = shiftedB(rowRange, colRange);
    a = a - mean(a, 'all');
    b = b - mean(b, 'all');
    denominator = sqrt(sum(a.^2, 'all') * sum(b.^2, 'all'));
    if denominator <= eps
        value = 0;
    else
        value = sum(a .* b, 'all') / denominator;
    end
end
