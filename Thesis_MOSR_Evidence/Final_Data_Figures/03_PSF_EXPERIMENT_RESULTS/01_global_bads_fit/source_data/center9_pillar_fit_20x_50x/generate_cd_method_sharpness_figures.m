function generate_cd_method_sharpness_figures()
%GENERATE_CD_METHOD_SHARPNESS_FIGURES
% Generate thesis figures for the center-nine-pillar CD method and
% deconvolution sharpness validation. The plotted CD and edge-width values
% are read from the audited per-pillar table produced by analyze_cd.py.

close all;

root = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit';
figureRoot = fullfile(root, 'figures', 'center9_pillar_fit_20x_50x');
tableRoot = fullfile(root, 'tables', 'center9_pillar_fit_20x_50x');
sourceRoot = fullfile(root, 'source_data', 'center9_pillar_fit_20x_50x');
deconvRoot = fullfile(sourceRoot, 'psf_deconvolution_cd');
fitRoot = 'D:\GMM_2_Final\PSF_Fitting\output\deconvolution_baseline_psf_20260715';
outDir = fullfile(figureRoot, 'comparison');
auditDir = fullfile(sourceRoot, 'sharpness_validation');

if ~isfolder(outDir), mkdir(outDir); end
if ~isfolder(auditDir), mkdir(auditDir); end

fontName = 'Microsoft JhengHei';
set(groot, 'defaultAxesFontName', fontName, ...
    'defaultTextFontName', fontName, ...
    'defaultAxesFontSize', 8.5, ...
    'defaultAxesLineWidth', 0.75, ...
    'defaultLineLineWidth', 1.4);

blue = [0.12, 0.40, 0.70];
gray = [0.42, 0.44, 0.47];
dark = [0.16, 0.17, 0.18];
gold = [0.90, 0.56, 0.05];
teal = [0.05, 0.57, 0.58];
lightBlue = [0.76, 0.86, 0.95];

perPillar = readtable(fullfile(tableRoot, 'cd_before_after_per_pillar.csv'), ...
    'VariableNamingRule', 'preserve');
sensitivity = readtable(fullfile(tableRoot, 'cd_threshold_sensitivity.csv'), ...
    'VariableNamingRule', 'preserve');
summary = readtable(fullfile(tableRoot, 'cd_before_after_summary.csv'), ...
    'VariableNamingRule', 'preserve');

labels = {'20x', '50x'};
plotPayload = load(fullfile(auditDir, 'matlab_cd_sharpness_plot_data.mat'));
profileData = struct();
metricRows = cell(numel(labels), 10);

for k = 1:numel(labels)
    label = labels{k};
    fieldName = ['m' label];
    rawProfiles = profile_from_payload(plotPayload, fieldName, 'raw');
    deconvProfiles = profile_from_payload(plotPayload, fieldName, 'deconvolved');
    centers = plotPayload.([fieldName '_centers_xy']);
    pitchPx = double(plotPayload.([fieldName '_pitch_px']));
    pixelUm = double(plotPayload.([fieldName '_pixel_um']));
    profileData.(fieldName).raw = rawProfiles;
    profileData.(fieldName).deconv = deconvProfiles;
    profileData.(fieldName).centers = centers;
    profileData.(fieldName).pitchPx = pitchPx;
    profileData.(fieldName).pixelUm = pixelUm;
    profileData.(fieldName).rawImage = double(plotPayload.([fieldName '_raw_image']));

    rows = perPillar(strcmp(string(perPillar.magnification), label), :);
    rawWidthUm = rows.raw_edge_width_px .* pixelUm;
    deconvWidthUm = rows.deconvolved_edge_width_px .* pixelUm;
    rawMean = mean(rawWidthUm);
    deconvMean = mean(deconvWidthUm);
    reductionPct = 100 * (1 - deconvMean / rawMean);
    improved = sum(deconvWidthUm < rawWidthUm);
    rawSharpness = 1 / rawMean;
    deconvSharpness = 1 / deconvMean;
    sharpnessGain = 100 * (deconvSharpness / rawSharpness - 1);

    metricRows(k, :) = {label, pixelUm, rawMean, deconvMean, reductionPct, ...
        improved, height(rows), rawSharpness, deconvSharpness, sharpnessGain};

    % Cross-check that the plot data came from the same audited measurements.
    rawDifference = max(abs(rawProfiles.edgeWidthPx(:) - rows.raw_edge_width_px(:)));
    deconvDifference = max(abs(deconvProfiles.edgeWidthPx(:) - rows.deconvolved_edge_width_px(:)));
    assert(rawDifference < 1e-9, ...
        '%s raw edge-width reproduction exceeded tolerance: %.6f px.', label, rawDifference);
    assert(deconvDifference < 1e-9, ...
        '%s deconvolved edge-width reproduction exceeded tolerance: %.6f px.', label, deconvDifference);
end

metrics = cell2table(metricRows, 'VariableNames', { ...
    'magnification', 'object_pixel_um', 'raw_mean_edge_width_um', ...
    'deconvolved_mean_edge_width_um', 'edge_width_reduction_percent', ...
    'pillars_sharpened', 'pillar_count', 'raw_sharpness_um_inverse', ...
    'deconvolved_sharpness_um_inverse', 'sharpness_gain_percent'});
writetable(metrics, fullfile(auditDir, 'sharpness_validation_metrics.csv'));

write_method_parameters(fullfile(auditDir, 'cd_measurement_parameters.csv'));
write_profile_table(profileData, labels, fullfile(auditDir, 'aligned_edge_profiles.csv'));

make_cd_method_figure(profileData.m50x, outDir, gold, teal, dark, gray, lightBlue);
make_sharpness_figure(perPillar, profileData, metrics, outDir, blue, gray, dark);
make_cd_pointwise_figure(perPillar, outDir, blue, gray, dark);
make_single_edge_profile(profileData.m20x, '20×', outDir, blue, gray, '07_edge_profile_20x.png');
make_single_edge_profile(profileData.m50x, '50×', outDir, blue, gray, '08_edge_profile_50x.png');
make_edge_width_summary(metrics, outDir, blue, gray);
make_cd_mae_summary(summary, outDir, blue, gray);
make_threshold_sensitivity(sensitivity, '20x', outDir, blue, gray, '11_threshold_sensitivity_20x.png');
make_threshold_sensitivity(sensitivity, '50x', outDir, blue, gray, '12_threshold_sensitivity_50x.png');
make_ringing_summary(summary, outDir, blue, gray);

fprintf('Generated and verified ten thesis figures in:\n%s\n', outDir);
disp(metrics);
end


function make_single_edge_profile(data, label, outDir, blue, grayColor, fileName)
fig = figure('Color', 'white', 'Units', 'centimeters', 'Position', [2, 2, 15.8, 9.8]);
ax = axes(fig); hold(ax, 'on');
plot(ax, data.raw.distanceUm, data.raw.alignedMedian, '-', 'Color', grayColor, ...
    'LineWidth', 1.6, 'DisplayName', 'Raw');
plot(ax, data.deconv.distanceUm, data.deconv.alignedMedian, '-', 'Color', blue, ...
    'LineWidth', 1.8, 'DisplayName', 'Wiener');
yline(ax, 0.10, ':', 'Color', [0.65 0.65 0.65], 'HandleVisibility', 'off');
yline(ax, 0.90, ':', 'Color', [0.65 0.65 0.65], 'HandleVisibility', 'off');
xline(ax, 0, '--', 'Color', [0.72 0.72 0.72], 'HandleVisibility', 'off');
xlabel(ax, 'Position relative to the 50% boundary (µm)');
ylabel(ax, 'Normalized intensity');
title(ax, sprintf('%s radial pillar-edge profile', label), 'FontWeight', 'normal');
subtitle(ax, 'Median of nine pillars and 360 directions per pillar');
if strcmp(label, '20×'), xlim(ax, [-0.80, 0.55]); else, xlim(ax, [-0.60, 0.55]); end
ylim(ax, [-0.18, 1.25]);
grid(ax, 'on'); ax.XGrid = 'off'; ax.GridAlpha = 0.16;
legend(ax, 'Location', 'southeast', 'Box', 'off');
exportgraphics(fig, fullfile(outDir, fileName), 'Resolution', 600);
close(fig);
end


function make_edge_width_summary(metrics, outDir, blue, grayColor)
fig = figure('Color', 'white', 'Units', 'centimeters', 'Position', [2, 2, 15.8, 9.8]);
ax = axes(fig);
values = [metrics.raw_mean_edge_width_um, metrics.deconvolved_mean_edge_width_um];
b = bar(ax, values, 'grouped', 'BarWidth', 0.76);
b(1).FaceColor = grayColor; b(2).FaceColor = blue;
b(1).DisplayName = 'Raw'; b(2).DisplayName = 'Wiener';
xticks(ax, 1:2); xticklabels(ax, {'20×', '50×'});
ylabel(ax, 'Mean 10–90% edge width (µm)');
title(ax, 'Pillar-edge transition width', 'FontWeight', 'normal');
subtitle(ax, 'Lower values indicate a narrower intensity transition');
grid(ax, 'on'); ax.XGrid = 'off'; ax.GridAlpha = 0.16;
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
ylim(ax, [0, 1.15 * max(values, [], 'all')]);
for series = 1:2
    for k = 1:2
        text(ax, b(series).XEndPoints(k), b(series).YEndPoints(k), ...
            sprintf('%.3f', values(k, series)), 'HorizontalAlignment', 'center', ...
            'VerticalAlignment', 'bottom', 'FontSize', 8);
    end
end
exportgraphics(fig, fullfile(outDir, '09_edge_width_summary.png'), 'Resolution', 600);
close(fig);
end


function make_cd_mae_summary(summary, outDir, blue, grayColor)
fig = figure('Color', 'white', 'Units', 'centimeters', 'Position', [2, 2, 15.8, 9.8]);
ax = axes(fig);
values = [summary.raw_mae_nm, summary.deconvolved_mae_nm];
b = bar(ax, values, 'grouped', 'BarWidth', 0.76);
b(1).FaceColor = grayColor; b(2).FaceColor = blue;
b(1).DisplayName = 'Raw'; b(2).DisplayName = 'Wiener';
xticks(ax, 1:2); xticklabels(ax, {'20×', '50×'});
ylabel(ax, 'Mean absolute CD error (nm)');
title(ax, 'CD error at the predefined 50% boundary', 'FontWeight', 'normal');
subtitle(ax, 'Known SEM diameter is used as a consistency reference');
grid(ax, 'on'); ax.XGrid = 'off'; ax.GridAlpha = 0.16;
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
ylim(ax, [0, 1.22 * max(values, [], 'all')]);
for series = 1:2
    for k = 1:2
        text(ax, b(series).XEndPoints(k), b(series).YEndPoints(k), ...
            sprintf('%.1f', values(k, series)), 'HorizontalAlignment', 'center', ...
            'VerticalAlignment', 'bottom', 'FontSize', 8);
    end
end
exportgraphics(fig, fullfile(outDir, '10_cd_mae_summary.png'), 'Resolution', 600);
close(fig);
end


function make_threshold_sensitivity(sensitivity, label, outDir, blue, grayColor, fileName)
rows = sensitivity(strcmp(string(sensitivity.magnification), label), :);
fig = figure('Color', 'white', 'Units', 'centimeters', 'Position', [2, 2, 15.8, 9.8]);
ax = axes(fig); hold(ax, 'on');
x = 100 .* rows.contrast_fraction;
plot(ax, x, rows.raw_mae_nm, '-o', 'Color', grayColor, 'MarkerFaceColor', 'white', ...
    'LineWidth', 1.6, 'DisplayName', 'Raw');
plot(ax, x, rows.deconvolved_mae_nm, '-o', 'Color', blue, 'MarkerFaceColor', blue, ...
    'LineWidth', 1.8, 'DisplayName', 'Wiener');
xlabel(ax, 'Relative edge threshold (%)');
ylabel(ax, 'Mean absolute CD error (nm)');
title(ax, sprintf('%s CD threshold sensitivity', strrep(label, 'x', '×')), ...
    'FontWeight', 'normal');
subtitle(ax, 'The same images, centers, and SEM diameters are used at every threshold');
xticks(ax, [40 50 60]); xlim(ax, [38 62]);
grid(ax, 'on'); ax.XGrid = 'off'; ax.GridAlpha = 0.16;
legend(ax, 'Location', 'north', 'Orientation', 'horizontal', 'Box', 'off');
exportgraphics(fig, fullfile(outDir, fileName), 'Resolution', 600);
close(fig);
end


function make_ringing_summary(summary, outDir, blue, grayColor)
fig = figure('Color', 'white', 'Units', 'centimeters', 'Position', [2, 2, 15.8, 9.8]);
ax = axes(fig);
values = 100 .* [summary.raw_max_ringing_ratio, summary.deconvolved_max_ringing_ratio];
b = bar(ax, values, 'grouped', 'BarWidth', 0.76);
b(1).FaceColor = grayColor; b(2).FaceColor = blue;
b(1).DisplayName = 'Raw'; b(2).DisplayName = 'Wiener';
xticks(ax, 1:2); xticklabels(ax, {'20×', '50×'});
ylabel(ax, 'Maximum ringing ratio (%)');
title(ax, 'Strongest local ringing around the nine pillars', 'FontWeight', 'normal');
subtitle(ax, 'Ratio of reverse radial variation to the outward edge rise');
grid(ax, 'on'); ax.XGrid = 'off'; ax.GridAlpha = 0.16;
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
ylim(ax, [0, 1.18 * max(values, [], 'all')]);
for series = 1:2
    for k = 1:2
        text(ax, b(series).XEndPoints(k), b(series).YEndPoints(k), ...
            sprintf('%.1f%%', values(k, series)), 'HorizontalAlignment', 'center', ...
            'VerticalAlignment', 'bottom', 'FontSize', 8);
    end
end
exportgraphics(fig, fullfile(outDir, '13_ringing_summary.png'), 'Resolution', 600);
close(fig);
end


function data = profile_from_payload(payload, fieldName, kind)
prefix = [fieldName '_' kind '_'];
data.distanceUm = payload.([prefix 'distance_um'])(:);
data.alignedMedian = payload.([prefix 'aligned_median'])(:);
data.edgeWidthPx = payload.([prefix 'edge_width_px'])(:);
data.radii = payload.([prefix 'radii_px'])(:).';
data.angles = payload.([prefix 'angles_rad'])(:);

r10 = payload.([prefix 'r10_px']);
r50 = payload.([prefix 'r50_px']);
r90 = payload.([prefix 'r90_px']);
medianProfiles = payload.([prefix 'median_profile']);
nPillars = size(r50, 1);
data.r10 = cell(nPillars, 1);
data.r50 = cell(nPillars, 1);
data.r90 = cell(nPillars, 1);
data.medianProfiles = cell(nPillars, 1);
for p = 1:nPillars
    data.r10{p} = r10(p, :).';
    data.r50{p} = r50(p, :).';
    data.r90{p} = r90(p, :).';
    data.medianProfiles{p} = medianProfiles(p, :);
end
end


function data = sample_all_pillars(image, centers, pitchPx, pixelUm)
radialStep = 0.05;
radii = 0:radialStep:(0.38 * pitchPx);
angles = (0:359)' * pi / 180;
commonDistanceUm = (-1.20:0.005:1.20)';
kernel = gaussian_kernel(6.0);

nPillars = size(centers, 1);
aligned = nan(numel(commonDistanceUm), 360 * nPillars);
edgeWidthPx = nan(nPillars, 1);
allR50 = cell(nPillars, 1);
allR10 = cell(nPillars, 1);
allR90 = cell(nPillars, 1);
medianProfiles = cell(nPillars, 1);

for p = 1:nPillars
    x = centers(p, 1) + cos(angles) * radii;
    y = centers(p, 2) + sin(angles) * radii;
    samples = interp2(image, x, y, 'cubic');

    coreMask = radii <= 0.07 * pitchPx;
    backgroundMask = radii >= 0.30 * pitchPx & radii <= 0.36 * pitchPx;
    coreLevel = median(samples(:, coreMask), 'all', 'omitnan');
    backgroundLevel = median(samples(:, backgroundMask), 'all', 'omitnan');
    normalized = (samples - coreLevel) ./ max(backgroundLevel - coreLevel, eps);

    smoothed = smooth_rows_replicate(normalized, kernel);
    r10 = first_upward_crossing(smoothed, radii, 0.10);
    r50 = first_upward_crossing(smoothed, radii, 0.50);
    r90 = first_upward_crossing(smoothed, radii, 0.90);
    widths = r90 - r10;
    valid = isfinite(widths) & widths >= 0;
    assert(sum(valid) >= 324, 'Pillar %d has fewer than 90%% valid edge traces.', p);
    edgeWidthPx(p) = median(widths(valid));

    for a = 1:360
        if isfinite(r50(a))
            signedDistanceUm = (radii - r50(a)) * pixelUm;
            aligned(:, (p - 1) * 360 + a) = interp1(signedDistanceUm, ...
                smoothed(a, :), commonDistanceUm, 'linear', NaN);
        end
    end

    allR10{p} = r10;
    allR50{p} = r50;
    allR90{p} = r90;
    medianProfiles{p} = median(smoothed, 1, 'omitnan');
end

data.distanceUm = commonDistanceUm;
data.alignedMedian = median(aligned, 2, 'omitnan');
data.edgeWidthPx = edgeWidthPx;
data.radii = radii;
data.angles = angles;
data.r10 = allR10;
data.r50 = allR50;
data.r90 = allR90;
data.medianProfiles = medianProfiles;
end


function kernel = gaussian_kernel(sigma)
halfWidth = ceil(4 * sigma);
x = -halfWidth:halfWidth;
kernel = exp(-0.5 * (x / sigma).^2);
kernel = kernel / sum(kernel);
end


function out = smooth_rows_replicate(in, kernel)
halfWidth = floor(numel(kernel) / 2);
left = repmat(in(:, 1), 1, halfWidth);
right = repmat(in(:, end), 1, halfWidth);
padded = [left, in, right];
out = conv2(padded, kernel, 'valid');
end


function crossings = first_upward_crossing(profiles, radii, threshold)
crossings = nan(size(profiles, 1), 1);
for row = 1:size(profiles, 1)
    profile = profiles(row, :);
    idx = find(profile(1:end-1) < threshold & profile(2:end) >= threshold, 1, 'first');
    if isempty(idx), continue; end
    y0 = profile(idx);
    y1 = profile(idx + 1);
    if y1 == y0
        crossings(row) = radii(idx);
    else
        fraction = (threshold - y0) / (y1 - y0);
        crossings(row) = radii(idx) + fraction * (radii(idx + 1) - radii(idx));
    end
end
end


function make_cd_method_figure(data, outDir, gold, teal, dark, grayColor, lightBlue)
fig = figure('Color', 'white', 'Units', 'centimeters', ...
    'Position', [2, 2, 18.2, 8.4]);
t = tiledlayout(fig, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

pillarIndex = 5;
center = data.centers(pillarIndex, :);
pitchPx = data.pitchPx;
image = data.rawImage;
r50 = data.raw.r50{pillarIndex};
angles = data.raw.angles;

ax1 = nexttile(t, 1);
halfRange = 0.43 * pitchPx;
imagesc(ax1, image);
axis(ax1, 'image');
colormap(ax1, gray(256));
xlim(ax1, center(1) + [-halfRange, halfRange]);
ylim(ax1, center(2) + [-halfRange, halfRange]);
set(ax1, 'YDir', 'reverse', 'XTick', [], 'YTick', []);
hold(ax1, 'on');

theta = linspace(0, 2*pi, 361);
plot(ax1, center(1) + r50 .* cos(angles), center(2) + r50 .* sin(angles), ...
    'Color', gold, 'LineWidth', 1.45, 'DisplayName', '50% contrast boundary');
plot(ax1, center(1) + 0.07*pitchPx*cos(theta), center(2) + 0.07*pitchPx*sin(theta), ...
    '--', 'Color', teal, 'LineWidth', 1.0, 'DisplayName', 'Core-level region');
plot(ax1, center(1) + 0.30*pitchPx*cos(theta), center(2) + 0.30*pitchPx*sin(theta), ...
    ':', 'Color', teal, 'LineWidth', 1.15, 'HandleVisibility', 'off');
plot(ax1, center(1) + 0.36*pitchPx*cos(theta), center(2) + 0.36*pitchPx*sin(theta), ...
    ':', 'Color', teal, 'LineWidth', 1.15, 'DisplayName', 'Background annulus');

pairAngle = 25;
oppositeAngle = pairAngle + 180;
p1 = center + r50(pairAngle + 1) * [cosd(pairAngle), sind(pairAngle)];
p2 = center + r50(oppositeAngle + 1) * [cosd(oppositeAngle), sind(oppositeAngle)];
plot(ax1, [p1(1), p2(1)], [p1(2), p2(2)], '-', 'Color', [0.95 0.95 0.95], ...
    'LineWidth', 1.3, 'DisplayName', 'Opposite-radius diameter');
plot(ax1, [p1(1), p2(1)], [p1(2), p2(2)], 'o', 'Color', [0.95 0.95 0.95], ...
    'MarkerFaceColor', dark, 'MarkerSize', 4, 'HandleVisibility', 'off');
title(ax1, '(a) Boundary determination on the image', 'FontWeight', 'normal');
legend(ax1, 'Location', 'southoutside', 'NumColumns', 2, 'FontSize', 7.4, ...
    'Box', 'off');

ax2 = nexttile(t, 2);
radiiUm = data.raw.radii * data.pixelUm;
profile = data.raw.medianProfiles{pillarIndex};
r10 = median(data.raw.r10{pillarIndex}, 'omitnan') * data.pixelUm;
r50m = median(data.raw.r50{pillarIndex}, 'omitnan') * data.pixelUm;
r90 = median(data.raw.r90{pillarIndex}, 'omitnan') * data.pixelUm;
hold(ax2, 'on');
patch(ax2, [r10 r90 r90 r10], [-0.15 -0.15 1.22 1.22], lightBlue, ...
    'FaceAlpha', 0.45, 'EdgeColor', 'none', 'DisplayName', '10–90% edge width');
plot(ax2, radiiUm, profile, 'Color', dark, 'LineWidth', 1.6, ...
    'DisplayName', 'Median of 360 radial profiles');
yline(ax2, 0.10, ':', '10%', 'Color', grayColor, 'LabelHorizontalAlignment', 'left', ...
    'HandleVisibility', 'off');
yline(ax2, 0.50, '--', '50%', 'Color', gold, 'LabelHorizontalAlignment', 'left', ...
    'HandleVisibility', 'off');
yline(ax2, 0.90, ':', '90%', 'Color', grayColor, 'LabelHorizontalAlignment', 'left', ...
    'HandleVisibility', 'off');
xline(ax2, r10, ':', 'Color', blue_color(), 'HandleVisibility', 'off');
xline(ax2, r50m, '--', 'Color', gold, 'HandleVisibility', 'off');
xline(ax2, r90, ':', 'Color', blue_color(), 'HandleVisibility', 'off');
xlabel(ax2, 'Radial distance from pillar center (µm)');
ylabel(ax2, 'Normalized intensity');
xlim(ax2, [0, 0.38 * pitchPx * data.pixelUm]);
ylim(ax2, [-0.12, 1.18]);
grid(ax2, 'on');
ax2.GridAlpha = 0.12;
title(ax2, '(b) 10%, 50%, and 90% contrast crossings', 'FontWeight', 'normal');
text(ax2, 0.03, 0.97, {'CD = r_{50}(\theta)+r_{50}(\theta+\pi)', ...
    'Edge width = r_{90}-r_{10}'}, ...
    'Units', 'normalized', 'VerticalAlignment', 'top', 'FontSize', 7.6, ...
    'BackgroundColor', 'white', 'Margin', 3, 'Interpreter', 'tex');
legend(ax2, 'Location', 'southeast', 'Box', 'off', 'FontSize', 7.4);

exportgraphics(fig, fullfile(outDir, '04_cd_measurement_method.png'), 'Resolution', 600);
exportgraphics(fig, fullfile(outDir, '04_cd_measurement_method.pdf'), 'ContentType', 'vector');
close(fig);
end


function make_sharpness_figure(perPillar, profileData, metrics, outDir, blue, gray, dark)
fig = figure('Color', 'white', 'Units', 'centimeters', ...
    'Position', [2, 2, 18.2, 13.2]);
t = tiledlayout(fig, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
labels = {'20x', '50x'};
panel = {'(a)', '(b)', '(c)', '(d)'};

for k = 1:2
    label = labels{k};
    fieldName = ['m' label];
    ax = nexttile(t, k);
    hold(ax, 'on');
    raw = profileData.(fieldName).raw;
    deconv = profileData.(fieldName).deconv;
    plot(ax, raw.distanceUm, raw.alignedMedian, '-', 'Color', gray, ...
        'LineWidth', 1.6, 'DisplayName', 'Captured');
    plot(ax, deconv.distanceUm, deconv.alignedMedian, '-', 'Color', blue, ...
        'LineWidth', 1.7, 'DisplayName', 'Deconvolved');
    yline(ax, 0.10, ':', 'Color', [0.65 0.65 0.65], 'HandleVisibility', 'off');
    yline(ax, 0.90, ':', 'Color', [0.65 0.65 0.65], 'HandleVisibility', 'off');
    xline(ax, 0, '--', 'Color', [0.75 0.75 0.75], 'HandleVisibility', 'off');
    xlabel(ax, 'Position relative to 50% boundary (µm)');
    ylabel(ax, 'Normalized intensity');
    if strcmp(label, '20x')
        xlim(ax, [-0.80, 0.55]);
    else
        xlim(ax, [-0.60, 0.55]);
    end
    ylim(ax, [-0.18, 1.25]);
    grid(ax, 'on');
    ax.GridAlpha = 0.12;
    title(ax, sprintf('%s %s mean edge profile', panel{k}, strrep(label, 'x', '×')), ...
        'FontWeight', 'normal');
    legend(ax, 'Location', 'southeast', 'Box', 'off', 'FontSize', 7.6);
end

for k = 1:2
    label = labels{k};
    fieldName = ['m' label];
    ax = nexttile(t, 2 + k);
    rows = perPillar(strcmp(string(perPillar.magnification), label), :);
    pixelUm = profileData.(fieldName).pixelUm;
    rawWidth = rows.raw_edge_width_px * pixelUm;
    deconvWidth = rows.deconvolved_edge_width_px * pixelUm;
    x = (1:height(rows))';
    hold(ax, 'on');
    for i = 1:height(rows)
        plot(ax, [x(i), x(i)], [rawWidth(i), deconvWidth(i)], '-', ...
            'Color', [0.78 0.80 0.82], 'LineWidth', 0.9, 'HandleVisibility', 'off');
    end
    scatter(ax, x, rawWidth, 24, 'o', 'MarkerEdgeColor', gray, ...
        'LineWidth', 1.0, 'DisplayName', 'Captured');
    scatter(ax, x, deconvWidth, 27, 'o', 'MarkerEdgeColor', blue, ...
        'MarkerFaceColor', blue, 'DisplayName', 'Deconvolved');
    xlabel(ax, 'Pillar index');
    ylabel(ax, '10–90% edge width (µm)');
    xlim(ax, [0.5, 9.5]);
    xticks(ax, 1:9);
    if strcmp(label, '20x')
        ylim(ax, [0.49, 0.86]);
    else
        ylim(ax, [0.47, 0.66]);
    end
    grid(ax, 'on');
    ax.GridAlpha = 0.12;
    metric = metrics(strcmp(string(metrics.magnification), label), :);
    title(ax, sprintf('%s %s per-pillar edge width (%d/%d narrowed)', ...
        panel{2+k}, strrep(label, 'x', '×'), metric.pillars_sharpened, metric.pillar_count), ...
        'FontWeight', 'normal');
end

exportgraphics(fig, fullfile(outDir, '05_sharpness_validation.png'), 'Resolution', 600);
exportgraphics(fig, fullfile(outDir, '05_sharpness_validation.pdf'), 'ContentType', 'vector');
close(fig);
end


function make_cd_pointwise_figure(perPillar, outDir, blue, gray, dark)
fig = figure('Color', 'white', 'Units', 'centimeters', ...
    'Position', [2, 2, 18.2, 7.4]);
t = tiledlayout(fig, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');
labels = {'20x', '50x'};

for k = 1:2
    label = labels{k};
    rows = perPillar(strcmp(string(perPillar.magnification), label), :);
    x = (1:height(rows))';
    sem = rows.sem_cd_nm / 1000;
    raw = rows.raw_cd_nm / 1000;
    deconv = rows.deconvolved_cd_nm / 1000;
    rawMae = mean(abs(raw - sem)) * 1000;
    deconvMae = mean(abs(deconv - sem)) * 1000;

    ax = nexttile(t, k);
    hold(ax, 'on');
    plot(ax, x, sem, '-s', 'Color', dark, 'MarkerFaceColor', 'white', ...
        'MarkerSize', 4.2, 'DisplayName', 'SEM');
    plot(ax, x, raw, '--o', 'Color', gray, 'MarkerFaceColor', 'white', ...
        'MarkerSize', 4.2, 'DisplayName', 'Captured');
    plot(ax, x, deconv, '-o', 'Color', blue, 'MarkerFaceColor', blue, ...
        'MarkerSize', 4.2, 'DisplayName', 'Deconvolved');
    xlabel(ax, 'Pillar index');
    ylabel(ax, 'CD (µm)');
    xlim(ax, [0.5, 9.5]);
    ylim(ax, [2.54, 2.71]);
    xticks(ax, 1:9);
    grid(ax, 'on');
    ax.GridAlpha = 0.13;
    title(ax, sprintf('(%c) %s per-pillar CD versus SEM', 'a' + k - 1, ...
        strrep(label, 'x', '×')), 'FontWeight', 'normal');
    text(ax, 0.03, 0.05, sprintf('MAE：%.1f → %.1f nm', rawMae, deconvMae), ...
        'Units', 'normalized', 'FontSize', 7.7, 'BackgroundColor', 'white', 'Margin', 3);
    if k == 2
        legend(ax, 'Location', 'northoutside', 'NumColumns', 3, ...
            'Box', 'off', 'FontSize', 7.6);
    end
end

exportgraphics(fig, fullfile(outDir, '06_cd_pointwise_validation.png'), 'Resolution', 600);
exportgraphics(fig, fullfile(outDir, '06_cd_pointwise_validation.pdf'), 'ContentType', 'vector');
close(fig);
end


function write_method_parameters(path)
parameter = {'radial_step_px'; 'angular_trace_count'; 'maximum_radius_pitch_fraction'; ...
    'core_radius_pitch_fraction'; 'background_inner_pitch_fraction'; ...
    'background_outer_pitch_fraction'; 'profile_gaussian_sigma_samples'; ...
    'main_contrast_fraction'; 'minimum_valid_trace_fraction'};
value = [0.05; 360; 0.38; 0.07; 0.30; 0.36; 6.0; 0.50; 0.90];
unit = {'px'; 'count'; 'fraction'; 'fraction'; 'fraction'; 'fraction'; ...
    'radial samples'; 'fraction'; 'fraction'};
writetable(table(parameter, value, unit), path);
end


function write_profile_table(profileData, labels, path)
out = table();
for k = 1:numel(labels)
    label = labels{k};
    fieldName = ['m' label];
    raw = profileData.(fieldName).raw;
    deconv = profileData.(fieldName).deconv;
    block = table(repmat(string(label), numel(raw.distanceUm), 1), raw.distanceUm, ...
        raw.alignedMedian, deconv.alignedMedian, 'VariableNames', ...
        {'magnification', 'distance_from_50pct_um', 'raw_normalized_intensity', ...
        'deconvolved_normalized_intensity'});
    out = [out; block]; %#ok<AGROW>
end
writetable(out, path);
end


function c = blue_color()
c = [0.12, 0.40, 0.70];
end
