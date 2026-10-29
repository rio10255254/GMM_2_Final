function make_720_direction_cd_illustration()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))))))));
%MAKE_720_DIRECTION_CD_ILLUSTRATION
% Read-only explanatory figure for the current 720-direction radial CD rule.

inputPath = fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp');
outputDir = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_work/radial_cd_illustration_20260726');
outputPath = fullfile(outputDir, '720_direction_radial_cd_method_50x_P29.png');
if ~isfolder(outputDir), mkdir(outputDir); end

imageData = imread(inputPath);
if ndims(imageData) == 3, imageData = rgb2gray(imageData); end
imageData = double(imageData);

% P29 in the Raw-defined 50x center-nine grid.
center = [1173.5, 714.5];
referenceRadiusPx = 19.5;
pixelUm = 0.069;
halfRangePx = 58;

[radii, radialMean, coreLevel, backgroundLevel, threshold, edgeRadius] = ...
    calculateRadialMean(imageData, center, referenceRadiusPx);
normalized = (radialMean - backgroundLevel) ./ max(coreLevel - backgroundLevel, eps);

darkBlue = [0.08, 0.34, 0.62];
lightBlue = [0.22, 0.62, 0.82];
orange = [0.88, 0.40, 0.08];
teal = [0.04, 0.55, 0.52];
darkGray = [0.34, 0.34, 0.34];

fig = figure('Color', 'w', 'Units', 'centimeters', 'Position', [2, 2, 18.0, 8.4]);
t = tiledlayout(fig, 1, 2, 'Padding', 'compact', 'TileSpacing', 'compact');

% (a) Actual image and sampling geometry.
ax1 = nexttile(t, 1);
imagesc(ax1, imageData, [0, 255]);
axis(ax1, 'image');
colormap(ax1, gray(256));
xlim(ax1, center(1) + [-halfRangePx, halfRangePx]);
ylim(ax1, center(2) + [-halfRangePx, halfRangePx]);
set(ax1, 'YDir', 'reverse', 'XTick', [], 'YTick', []);
hold(ax1, 'on');

% A small subset is drawn only to keep the sampling fan legible.
displayAngles = deg2rad(0:10:350);
for theta = displayAngles
    plot(ax1, center(1) + [0, 1.45 * referenceRadiusPx] * cos(theta), ...
        center(2) + [0, 1.45 * referenceRadiusPx] * sin(theta), '-', ...
        'Color', 0.22*lightBlue + 0.78*[1, 1, 1], 'LineWidth', 0.5, 'HandleVisibility', 'off');
end
theta = linspace(0, 2*pi, 361);
coreRadiusPx = max(3.0, 0.42 * referenceRadiusPx);
backgroundInnerPx = 1.45 * referenceRadiusPx;
radialLimitPx = radii(end);
plot(ax1, center(1) + coreRadiusPx*cos(theta), center(2) + coreRadiusPx*sin(theta), ...
    '--', 'Color', teal, 'LineWidth', 1.15, 'DisplayName', '核心灰階區');
plot(ax1, center(1) + backgroundInnerPx*cos(theta), center(2) + backgroundInnerPx*sin(theta), ...
    ':', 'Color', teal, 'LineWidth', 1.10, 'HandleVisibility', 'off');
plot(ax1, center(1) + radialLimitPx*cos(theta), center(2) + radialLimitPx*sin(theta), ...
    ':', 'Color', teal, 'LineWidth', 1.10, 'DisplayName', '背景取樣區');
plot(ax1, center(1) + referenceRadiusPx*cos(theta), center(2) + referenceRadiusPx*sin(theta), ...
    '--', 'Color', darkBlue, 'LineWidth', 1.05, 'DisplayName', '參考半徑 R');

exampleAngle = deg2rad(25);
plot(ax1, center(1) + [0, radialLimitPx] * cos(exampleAngle), ...
    center(2) + [0, radialLimitPx] * sin(exampleAngle), '-', ...
    'Color', orange, 'LineWidth', 1.6, 'DisplayName', '單一方向示例');
plot(ax1, center(1), center(2), '+', 'Color', darkBlue, 'LineWidth', 1.9, ...
    'MarkerSize', 10, 'DisplayName', '固定局部中心');
plot(ax1, center(1) + edgeRadius*cos(exampleAngle), ...
    center(2) + edgeRadius*sin(exampleAngle), 'o', 'Color', orange, ...
    'MarkerFaceColor', 'w', 'MarkerSize', 4.5, 'HandleVisibility', 'off');
text(ax1, 0.03, 0.04, {'示意僅顯示每 10° 一條方向線', ...
    '實際取樣：720 條方向，間隔 0.5°'}, ...
    'Units', 'normalized', 'FontSize', 8.2, 'Color', darkGray, ...
    'VerticalAlignment', 'bottom', 'BackgroundColor', 'w', 'Margin', 3);
legend(ax1, 'Location', 'southoutside', 'Box', 'off', 'NumColumns', 2, 'FontSize', 8.2);

% (b) The single averaged profile actually used for radial CD.
ax2 = nexttile(t, 2);
hold(ax2, 'on');
rUm = radii * pixelUm;
plot(ax2, rUm, normalized, '-', 'Color', darkBlue, 'LineWidth', 1.8, ...
    'DisplayName', '720 方向算術平均剖面');
levels = 0.35:0.05:0.65;
for level = levels
    yline(ax2, level, ':', 'Color', [0.72, 0.72, 0.72], ...
        'LineWidth', 0.7, 'HandleVisibility', 'off');
end
yline(ax2, 0.50, '--', 'Color', orange, 'LineWidth', 1.15, ...
    'DisplayName', '50% 相對閾值');
plot(ax2, [edgeRadius, edgeRadius] * pixelUm, [-0.05, 0.50], '--', ...
    'Color', orange, 'LineWidth', 1.15, 'HandleVisibility', 'off');
plot(ax2, edgeRadius * pixelUm, 0.50, 'o', 'Color', orange, ...
    'MarkerFaceColor', 'w', 'MarkerSize', 5, 'HandleVisibility', 'off');
xlabel(ax2, '距固定中心的徑向距離 (\mum)', 'Interpreter', 'tex');
ylabel(ax2, '局部正規化強度');
xlim(ax2, [0, radialLimitPx * pixelUm]);
ylim(ax2, [-0.10, 1.15]);
yticks(ax2, 0:0.2:1.0);
grid(ax2, 'on');
ax2.XGrid = 'off';
ax2.GridAlpha = 0.15;
text(ax2, 0.04, 0.96, { ...
    'θ_k = 2πk / 720，k = 0, …, 719', ...
    '720 個方向的算術平均剖面', ...
    '僅在此單一平均剖面找交點；CD_f = 2r_f'}, ...
    'Units', 'normalized', 'VerticalAlignment', 'top', 'FontSize', 7.6, ...
    'BackgroundColor', 'w', 'Margin', 4, 'Interpreter', 'none');
legend(ax2, 'Location', 'southwest', 'Box', 'off', 'FontSize', 8.2);

for ax = [ax1, ax2]
    ax.FontName = 'Microsoft JhengHei';
    ax.FontSize = 9;
    ax.Box = 'off';
    ax.TickDir = 'out';
    ax.XColor = [0.16, 0.16, 0.16];
    ax.YColor = [0.16, 0.16, 0.16];
end
exportgraphics(fig, outputPath, 'Resolution', 400, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', outputPath);
end

function [radii, profile, high, low, threshold, edgeRadius] = ...
    calculateRadialMean(imageData, center, referenceRadiusPx)
margin = max(28.0, referenceRadiusPx * 1.35);
requestedLimit = referenceRadiusPx + margin;
availableLimit = min([center(1), center(2), ...
    size(imageData, 2) - 1.0 - center(1), ...
    size(imageData, 1) - 1.0 - center(2)]) - 0.25;
radialLimit = min(requestedLimit, availableLimit);
radii = 0.0:0.25:radialLimit;
angles = linspace(0.0, 2*pi, 720 + 1);
angles(end) = [];
sampleX = center(1) + cos(angles(:)) * radii;
sampleY = center(2) + sin(angles(:)) * radii;
darkness = 1.0 - imageData / 255.0;
samples = interp2(darkness, sampleX, sampleY, 'linear');
profile = mean(samples, 1);
centerMask = radii <= max(3.0, referenceRadiusPx * 0.42);
backgroundMask = radii >= referenceRadiusPx * 1.45;
high = prctile(profile(centerMask), 80);
low = prctile(profile(backgroundMask), 20);
threshold = low + 0.50 * (high - low);
candidates = find(profile(1:end-1) >= threshold & profile(2:end) < threshold);
[~, nearest] = min(abs(radii(candidates) - referenceRadiusPx));
idx = candidates(nearest);
fraction = (threshold - profile(idx)) / (profile(idx+1) - profile(idx));
edgeRadius = radii(idx) + fraction * (radii(idx+1) - radii(idx));
end
