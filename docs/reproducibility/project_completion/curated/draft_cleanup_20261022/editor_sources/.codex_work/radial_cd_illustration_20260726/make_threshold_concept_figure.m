function make_threshold_concept_figure()
%MAKE_THRESHOLD_CONCEPT_FIGURE
% Single-page thesis illustration using actual P29 data and the current
% 720-direction arithmetic-mean radial profile rule.  It is explanatory
% only; no source measurement code or result is changed.

inputPath = 'D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_0p5um\bmp\frame_0000.bmp';
outputDir = 'D:\GMM_2_Final\PSF_Fitting\.codex_work\radial_cd_illustration_20260726';
outputPath = fullfile(outputDir, 'relative_threshold_concept_P29_radial_profile_v2.png');
if ~isfolder(outputDir), mkdir(outputDir); end

I = imread(inputPath);
if ndims(I) == 3, I = rgb2gray(I); end
I = double(I);

% Raw-defined P29 in the 50x centre-nine grid; same position and sampling
% convention as the previously audited 720-direction CD demonstration.
centre = [1173.5, 714.5];
referenceRadiusPx = 19.5;
pixelUm = 0.069;
halfRangePx = 52;

[rPx, profile, high, low, edges] = radialProfileAndEdges(I, centre, referenceRadiusPx);
normalised = (profile - low) ./ max(high - low, eps);
levels = 0.35:0.05:0.65;
focusLevels = [0.35, 0.50, 0.65];
focusEdges = edges(ismember(round(levels, 2), focusLevels));

% Restrained colours: the 50% operating point is the primary blue; the
% two sensitivity endpoints use warm/cool accents.
c35 = [0.76, 0.33, 0.10];
c50 = [0.06, 0.34, 0.61];
c65 = [0.16, 0.48, 0.31];
accent = [c35; c50; c65];
grayLine = [0.73, 0.73, 0.73];
textGray = [0.18, 0.18, 0.18];

fig = figure('Color', 'w', 'Units', 'centimeters', 'Position', [2, 2, 19.0, 8.4], ...
    'Renderer', 'painters');
t = tiledlayout(fig, 1, 2, 'Padding', 'compact', 'TileSpacing', 'compact');

% (a) Actual measured P29 image: only three representative contours.
ax1 = nexttile(t, 1);
imagesc(ax1, I, [0, 255]);
axis(ax1, 'image');
colormap(ax1, gray(256));
xlim(ax1, centre(1) + [-halfRangePx, halfRangePx]);
ylim(ax1, centre(2) + [-halfRangePx, halfRangePx]);
set(ax1, 'YDir', 'reverse', 'XTick', [], 'YTick', []);
hold(ax1, 'on');
theta = linspace(0, 2*pi, 361);
contourHandles = gobjects(1, numel(focusLevels));
for q = 1:numel(focusLevels)
    r = focusEdges(q);
    style = '-'; if focusLevels(q) == 0.50, style = '--'; end
    contourHandles(q) = plot(ax1, centre(1) + r*cos(theta), centre(2) + r*sin(theta), style, ...
        'Color', accent(q,:), 'LineWidth', 1.35, 'DisplayName', sprintf('%d%% threshold', round(100*focusLevels(q))));
end
plot(ax1, centre(1), centre(2), 'o', 'MarkerSize', 5.3, 'LineWidth', 1.2, ...
    'MarkerEdgeColor', 'w', 'MarkerFaceColor', c50, 'HandleVisibility', 'off');

% Panel tag, compact contour key, specimen label, and true 2 um scale bar.
text(ax1, 0.03, 0.95, '(a)', 'Units', 'normalized', 'Color', textGray, ...
    'FontSize', 10.5, 'FontWeight', 'bold', 'VerticalAlignment', 'top');
legend(ax1, contourHandles, {'35% threshold', '50% threshold', '65% threshold'}, ...
    'Location', 'northeast', 'Box', 'off', 'FontName', 'Times New Roman', ...
    'FontSize', 7.6, 'TextColor', textGray);
text(ax1, 0.03, 0.06, 'P29', 'Units', 'normalized', 'Color', 'w', ...
    'FontSize', 8.6, 'FontWeight', 'bold', 'BackgroundColor', [0.10 0.10 0.10], 'Margin', 2);
scaleLengthPx = 2.0 / pixelUm;
scaleY = centre(2) + 43;
scaleX2 = centre(1) + 45;
scaleX1 = scaleX2 - scaleLengthPx;
plot(ax1, [scaleX1 scaleX2], [scaleY scaleY], '-', 'Color', [0.08 0.08 0.08], ...
    'LineWidth', 2.2, 'HandleVisibility', 'off');
text(ax1, mean([scaleX1 scaleX2]), scaleY - 3.0, '2 \mum', 'Interpreter', 'tex', ...
    'Color', textGray, 'FontName', 'Times New Roman', 'FontSize', 7.8, ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom');

% (b) The true, single radial profile used by the 720-direction CD rule.
ax2 = nexttile(t, 2);
hold(ax2, 'on');
rUm = rPx * pixelUm;
plot(ax2, rUm, normalised, '-', 'Color', textGray, 'LineWidth', 1.65, ...
    'DisplayName', '720-direction mean radial profile');

% The four intermediate levels are deliberately quiet; only 35/50/65 are
% coloured because they correspond to the three image contours at left.
for f = levels
    isFocus = any(abs(f - focusLevels) < 1e-12);
    if ~isFocus
        yline(ax2, f, ':', 'Color', grayLine, 'LineWidth', 0.65, 'HandleVisibility', 'off');
    end
end
for q = 1:numel(focusLevels)
    f = focusLevels(q);
    edgeUm = focusEdges(q) * pixelUm;
    yline(ax2, f, '--', 'Color', accent(q,:), 'LineWidth', 0.95, 'HandleVisibility', 'off');
    plot(ax2, [edgeUm edgeUm], [0 f], ':', 'Color', accent(q,:), 'LineWidth', 0.9, 'HandleVisibility', 'off');
    plot(ax2, edgeUm, f, 'o', 'MarkerSize', 5.0, 'MarkerFaceColor', 'w', ...
        'MarkerEdgeColor', accent(q,:), 'LineWidth', 1.1, 'HandleVisibility', 'off');
    text(ax2, rUm(end)*0.99, f + 0.025, sprintf('%d%%', round(100*f)), ...
        'Color', accent(q,:), 'FontSize', 8.2, 'FontWeight', 'bold', 'HorizontalAlignment', 'right');
end

% A concise geometric consequence of the 50% radius crossing.
r50Um = focusEdges(focusLevels == 0.50) * pixelUm;
plot(ax2, [0 r50Um], [-0.070 -0.070], '-', 'Color', c50, 'LineWidth', 1.05, 'HandleVisibility', 'off');
plot(ax2, 0, -0.070, '<', 'Color', c50, 'MarkerFaceColor', c50, 'MarkerSize', 5, 'HandleVisibility', 'off');
plot(ax2, r50Um, -0.070, '>', 'Color', c50, 'MarkerFaceColor', c50, 'MarkerSize', 5, 'HandleVisibility', 'off');
text(ax2, r50Um/2, -0.120, 'r_{50}', 'Color', c50, 'FontSize', 9.2, ...
    'FontWeight', 'bold', 'HorizontalAlignment', 'center');
text(ax2, rUm(end)*0.985, 1.055, {'Relative threshold', 'T_f = L + f(H - L)', ...
    'f = 0.35:0.05:0.65', 'H = core;  L = background', 'CD_f = 2r_f'}, ...
    'Color', textGray, 'FontSize', 7.9, 'FontWeight', 'normal', ...
    'HorizontalAlignment', 'right', 'VerticalAlignment', 'top', ...
    'BackgroundColor', 'w', 'Margin', 3, 'Interpreter', 'tex');
text(ax2, 0.03, 0.95, '(b)', 'Units', 'normalized', ...
    'Color', textGray, 'FontSize', 10.5, 'FontWeight', 'bold', 'VerticalAlignment', 'top');
xlabel(ax2, 'Radial distance from the fixed center (\mum)', 'Interpreter', 'tex');
ylabel(ax2, 'Locally normalized darkness');
xlim(ax2, [0, rUm(end)]);
ylim(ax2, [-0.16, 1.12]);
yticks(ax2, 0:0.2:1.0);
yticklabels(ax2, {'0 (L)', '0.2', '0.4', '0.6', '0.8', '1.0 (H)'});
grid(ax2, 'on');
ax2.XGrid = 'off'; ax2.GridAlpha = 0.15;

for ax = [ax1 ax2]
    ax.FontName = 'Times New Roman';
    ax.FontSize = 10.0;
    ax.Box = 'off';
    ax.LineWidth = 0.75;
    ax.TickDir = 'out';
    ax.XColor = textGray;
    ax.YColor = textGray;
end

exportgraphics(fig, outputPath, 'Resolution', 500, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', outputPath);
end

function [radii, profile, high, low, edges] = radialProfileAndEdges(I, centre, referenceRadiusPx)
% Mirrors the current measurement rule: 720 independent directions are
% sampled bilinearly, then averaged before any of the seven thresholds is
% crossed.  Values are darkness, so a dark pillar has high core signal.
margin = max(28.0, referenceRadiusPx * 1.35);
requestedLimit = referenceRadiusPx + margin;
availableLimit = min([centre(1), centre(2), size(I,2)-1.0-centre(1), size(I,1)-1.0-centre(2)]) - 0.25;
radialLimit = min(requestedLimit, availableLimit);
radii = 0.0:0.25:radialLimit;
angles = linspace(0.0, 2*pi, 721); angles(end) = [];
sampleX = centre(1) + cos(angles(:)) * radii;
sampleY = centre(2) + sin(angles(:)) * radii;
darkness = 1.0 - I/255.0;
samples = interp2(darkness, sampleX, sampleY, 'linear');
profile = mean(samples, 1);
high = prctile(profile(radii <= max(3.0, 0.42 * referenceRadiusPx)), 80);
low = prctile(profile(radii >= 1.45 * referenceRadiusPx), 20);
levels = 0.35:0.05:0.65;
edges = nan(size(levels));
for q = 1:numel(levels)
    threshold = low + levels(q) * (high - low);
    candidates = find(profile(1:end-1) >= threshold & profile(2:end) < threshold);
    [~, k] = min(abs(radii(candidates) - referenceRadiusPx));
    idx = candidates(k);
    fraction = (threshold - profile(idx)) / (profile(idx+1) - profile(idx));
    edges(q) = radii(idx) + fraction * (radii(idx+1)-radii(idx));
end
end
