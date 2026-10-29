function make_clean_720_direction_cd_schematic()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))))))));
%MAKE_CLEAN_720_DIRECTION_CD_SCHEMATIC
% Clean two-panel explanatory figure. The supplied annotated P29 image is
% placed unchanged at left; the right panel uses the actual current radial
% averaging rule on the corresponding Raw image.

annotatedImagePath = 'C:\Users\Rio\AppData\Local\Temp\codex-clipboard-ebcfb69b-f3cf-4756-b66f-7d1e574941fb.png';
rawImagePath = fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp');
outputDir = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_work/radial_cd_illustration_20260726');
outputPath = fullfile(outputDir, '720_direction_radial_cd_clean_schematic_50x_P29.png');
if ~isfolder(outputDir), mkdir(outputDir); end

annotated = imread(annotatedImagePath);
raw = imread(rawImagePath);
if ndims(raw) == 3, raw = rgb2gray(raw); end

center = [1173.5, 714.5];
referenceRadiusPx = 19.5;
pixelUm = 0.069;
[radii, radialMean, coreLevel, backgroundLevel, edgeRadius] = ...
    currentRadialMean(double(raw), center, referenceRadiusPx, 0.50);
normalized = (radialMean - backgroundLevel) ./ max(coreLevel - backgroundLevel, eps);

blue = [0.08, 0.34, 0.62];
orange = [0.88, 0.40, 0.08];
charcoal = [0.16, 0.16, 0.16];
gridColor = [0.86, 0.86, 0.86];

fig = figure('Color', 'w', 'Units', 'centimeters', 'Position', [2, 2, 17.2, 8.4]);
t = tiledlayout(fig, 1, 2, 'Padding', 'compact', 'TileSpacing', 'compact');

ax1 = nexttile(t, 1);
image(ax1, annotated);
axis(ax1, 'image');
axis(ax1, 'off');
text(ax1, 0.02, 0.97, '(a)', 'Units', 'normalized', 'Color', charcoal, ...
    'FontSize', 9, 'FontWeight', 'bold', 'VerticalAlignment', 'top');

ax2 = nexttile(t, 2);
hold(ax2, 'on');
rUm = radii * pixelUm;
edgeUm = edgeRadius * pixelUm;
plot(ax2, rUm, normalized, '-', 'Color', blue, 'LineWidth', 1.85, ...
    'DisplayName', '角向平均徑向剖面');
yline(ax2, 0.50, '--', 'Color', orange, 'LineWidth', 1.15, ...
    'DisplayName', '相對閾值 f = 0.50');
plot(ax2, [edgeUm, edgeUm], [-0.04, 0.50], '--', 'Color', orange, ...
    'LineWidth', 1.15, 'HandleVisibility', 'off');
plot(ax2, edgeUm, 0.50, 'o', 'Color', orange, 'MarkerFaceColor', 'w', ...
    'LineWidth', 1.2, 'MarkerSize', 5.2, 'HandleVisibility', 'off');
text(ax2, edgeUm + 0.045, 0.43, 'r_f', 'Color', orange, 'FontSize', 9, ...
    'FontWeight', 'bold', 'Interpreter', 'tex');
xlabel(ax2, '徑向距離 (\mum)', 'Interpreter', 'tex');
ylabel(ax2, '正規化強度');
xlim(ax2, [0, rUm(end)]);
ylim(ax2, [-0.08, 1.12]);
yticks(ax2, 0:0.2:1.0);
grid(ax2, 'on');
ax2.XGrid = 'off';
ax2.GridColor = gridColor;
ax2.GridAlpha = 0.65;
ax2.Box = 'off';
ax2.TickDir = 'out';
ax2.FontName = 'Microsoft JhengHei';
ax2.FontSize = 9;
ax2.XColor = charcoal;
ax2.YColor = charcoal;
legend(ax2, 'Location', 'southwest', 'Box', 'off', 'FontSize', 8.3);
text(ax2, 0.02, 0.97, '(b)', 'Units', 'normalized', 'Color', charcoal, ...
    'FontSize', 9, 'FontWeight', 'bold', 'VerticalAlignment', 'top');

exportgraphics(fig, outputPath, 'Resolution', 400, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', outputPath);
end

function [radii, profile, high, low, edgeRadius] = currentRadialMean(imageData, center, referenceRadiusPx, fraction)
margin = max(28.0, referenceRadiusPx * 1.35);
requestedLimit = referenceRadiusPx + margin;
availableLimit = min([center(1), center(2), ...
    size(imageData, 2) - 1.0 - center(1), ...
    size(imageData, 1) - 1.0 - center(2)]) - 0.25;
radialLimit = min(requestedLimit, availableLimit);
radii = 0.0:0.25:radialLimit;
angles = linspace(0.0, 2*pi, 721); angles(end) = [];
sampleX = center(1) + cos(angles(:)) * radii;
sampleY = center(2) + sin(angles(:)) * radii;
darkness = 1.0 - imageData / 255.0;
samples = interp2(darkness, sampleX, sampleY, 'linear');
profile = mean(samples, 1);
centerMask = radii <= max(3.0, referenceRadiusPx * 0.42);
backgroundMask = radii >= referenceRadiusPx * 1.45;
high = prctile(profile(centerMask), 80);
low = prctile(profile(backgroundMask), 20);
threshold = low + fraction * (high - low);
candidates = find(profile(1:end-1) >= threshold & profile(2:end) < threshold);
[~, nearest] = min(abs(radii(candidates) - referenceRadiusPx));
index = candidates(nearest);
alpha = (threshold - profile(index)) / (profile(index+1) - profile(index));
edgeRadius = radii(index) + alpha * (radii(index+1) - radii(index));
end
