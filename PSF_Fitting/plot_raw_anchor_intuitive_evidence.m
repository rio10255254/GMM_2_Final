PROJECT_ROOT = fileparts(fileparts(mfilename('fullpath')));
clear; close all; clc;

outRoot = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures/11_V24_RAW_ANCHOR_INTUITIVE_FIGURES_20260727');
figureDir = fullfile(outRoot, 'figures');
tableDir = fullfile(outRoot, 'tables');
if ~exist(figureDir, 'dir'), mkdir(figureDir); end
if ~exist(tableDir, 'dir'), mkdir(tableDir); end

summaryPath = fullfile(PROJECT_ROOT, 'Experiments/R63_CausalBoundaryMotionAblation/results/evaluation/aggregate/candidate_seed_summary.csv');
centerPath = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/cd/tables/center9_cd_per_pillar.csv');
reconRoot = fullfile(PROJECT_ROOT, 'Experiments/R63_CausalBoundaryMotionAblation/results/evaluation/reconstructions');
seeds = [1261200, 1261217];

blue = [0.075, 0.365, 0.650];
orange = [0.835, 0.335, 0.075];
gray = [0.36, 0.36, 0.36];
lightGray = [0.83, 0.83, 0.83];
fontName = 'Times New Roman';

%% Figure 1: actual P29 radial profile and outer-region ringing detail.
centers = readtable(centerPath, 'Delimiter', ',', 'VariableNamingRule', 'preserve', 'TextType', 'string');
p29 = centers(centers.sem_index == 29, :);
assert(height(p29) == 1, 'P29 center record was not found uniquely.');
cx = p29.raw_x_px(1);
cy = p29.raw_y_px(1);
semRadiusPx = p29.reference_radius_px(1);
objectUmPerPx = 0.069;
rawPath = string(p29.raw_source_image(1));
[~, imageStem, imageExt] = fileparts(rawPath);
imageName = imageStem + imageExt;

radiiPx = 0:0.05:max(18.0, semRadiusPx * 2.2);
angles = linspace(0, 2*pi, 721); angles(end) = [];
rawProfile = radial_mean_darkness(read_darkness(rawPath), cx, cy, radiiPx, angles);
fullSeedProfiles = zeros(numel(seeds), numel(radiiPx));
noAnchorSeedProfiles = zeros(numel(seeds), numel(radiiPx));
for k = 1:numel(seeds)
    fullPath = fullfile(reconRoot, 'full_control', sprintf('seed%d', seeds(k)), 'static_50x_sem', imageName);
    noAnchorPath = fullfile(reconRoot, 'no_raw_position_anchor', sprintf('seed%d', seeds(k)), 'static_50x_sem', imageName);
    assert(isfile(fullPath), 'Missing full-model image: %s', fullPath);
    assert(isfile(noAnchorPath), 'Missing no-anchor image: %s', noAnchorPath);
    fullSeedProfiles(k, :) = radial_mean_darkness(read_darkness(fullPath), cx, cy, radiiPx, angles);
    noAnchorSeedProfiles(k, :) = radial_mean_darkness(read_darkness(noAnchorPath), cx, cy, radiiPx, angles);
end
fullProfile = mean(fullSeedProfiles, 1);
noAnchorProfile = mean(noAnchorSeedProfiles, 1);
offsetUm = (radiiPx - semRadiusPx) * objectUmPerPx;

backgroundMask = offsetUm >= 0.90;
rawResidual = rawProfile - median(rawProfile(backgroundMask));
fullResidual = fullProfile - median(fullProfile(backgroundMask));
noAnchorResidual = noAnchorProfile - median(noAnchorProfile(backgroundMask));

profileTable = table(offsetUm(:), rawProfile(:), fullProfile(:), noAnchorProfile(:), ...
    rawResidual(:), fullResidual(:), noAnchorResidual(:), ...
    'VariableNames', {'radial_offset_from_sem_edge_um', 'raw_darkness', ...
    'full_model_darkness_two_seed_mean', 'without_anchor_darkness_two_seed_mean', ...
    'raw_background_subtracted_darkness', 'full_model_background_subtracted_darkness', ...
    'without_anchor_background_subtracted_darkness'});
writetable(profileTable, fullfile(tableDir, '01_edge_profile_50x_p29.csv'));
outerMask = offsetUm >= 0.12 & offsetUm <= 1.32;
outerTable = profileTable(outerMask, {'radial_offset_from_sem_edge_um', ...
    'raw_background_subtracted_darkness', 'full_model_background_subtracted_darkness', ...
    'without_anchor_background_subtracted_darkness'});
writetable(outerTable, fullfile(tableDir, '02_outer_ringing_50x_p29.csv'));

fig1 = figure('Color', 'w', 'Units', 'inches', 'Position', [1 1 7.25 4.35]);
ax = axes(fig1, 'Position', [0.11 0.15 0.86 0.74]);
hold(ax, 'on');
p1 = plot(ax, offsetUm, rawProfile, '-', 'Color', gray, 'LineWidth', 1.5);
p2 = plot(ax, offsetUm, fullProfile, '-o', 'Color', blue, 'LineWidth', 1.8, ...
    'MarkerIndices', 1:55:numel(offsetUm), 'MarkerSize', 3.8, 'MarkerFaceColor', 'w');
p3 = plot(ax, offsetUm, noAnchorProfile, '-s', 'Color', orange, 'LineWidth', 1.8, ...
    'MarkerIndices', 25:55:numel(offsetUm), 'MarkerSize', 3.6, 'MarkerFaceColor', 'w');
p4 = xline(ax, 0, '--', 'Color', [0.15 0.15 0.15], 'LineWidth', 1.1);
xlim(ax, [-0.80 1.40]);
profileY = [rawProfile(offsetUm >= -0.8 & offsetUm <= 1.4), ...
    fullProfile(offsetUm >= -0.8 & offsetUm <= 1.4), ...
    noAnchorProfile(offsetUm >= -0.8 & offsetUm <= 1.4)];
ylim(ax, [min(profileY)-0.015, max(profileY)+0.020]);
xlabel(ax, 'Radial offset from SEM reference edge (\mum)');
ylabel(ax, 'Radial mean darkness (a.u.)');
legend(ax, [p1 p2 p3 p4], {'Raw', 'Full model', 'Without Raw-position anchor', 'SEM reference edge'}, ...
    'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off', 'NumColumns', 2);
style_axes(ax, fontName);
export_figure(fig1, figureDir, '01_raw_anchor_edge_profile_50x_p29');

figOuter = figure('Color', 'w', 'Units', 'inches', 'Position', [1 1 7.25 4.20]);
axOuter = axes(figOuter, 'Position', [0.12 0.16 0.85 0.72]);
hold(axOuter, 'on');
q1 = plot(axOuter, offsetUm(outerMask), 1000*rawResidual(outerMask), '-', ...
    'Color', gray, 'LineWidth', 1.6);
q2 = plot(axOuter, offsetUm(outerMask), 1000*fullResidual(outerMask), '-o', ...
    'Color', blue, 'LineWidth', 1.8, 'MarkerIndices', 1:30:nnz(outerMask), ...
    'MarkerSize', 3.8, 'MarkerFaceColor', 'w');
q3 = plot(axOuter, offsetUm(outerMask), 1000*noAnchorResidual(outerMask), '-s', ...
    'Color', orange, 'LineWidth', 1.8, 'MarkerIndices', 15:30:nnz(outerMask), ...
    'MarkerSize', 3.8, 'MarkerFaceColor', 'w');
yline(axOuter, 0, '--', 'Color', [0.25 0.25 0.25], 'LineWidth', 1.0);
xlim(axOuter, [0.12 1.32]);
residualY = 1000*[rawResidual(outerMask), fullResidual(outerMask), noAnchorResidual(outerMask)];
pad = max(0.5, 0.08*(max(residualY)-min(residualY)));
ylim(axOuter, [min(residualY)-pad, max(residualY)+pad]);
xlabel(axOuter, 'Outer offset from SEM reference edge (\mum)');
ylabel(axOuter, 'Background-subtracted darkness (\times10^{-3})');
legend(axOuter, [q1 q2 q3], {'Raw', 'Full model', 'Without Raw-position anchor'}, ...
    'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
style_axes(axOuter, fontName);
export_figure(figOuter, figureDir, '02_raw_anchor_outer_ringing_50x_p29');

%% Figure 2: apparent CD change versus the ringing penalty.
summary = readtable(summaryPath, 'Delimiter', ',', 'VariableNamingRule', 'preserve', 'TextType', 'string');
magnifications = ["50x", "20x"];
variants = ["full_control", "no_raw_position_anchor"];
cdSeeds = nan(2, 2, numel(seeds));
ringSeeds = nan(2, 2, numel(seeds));
edgeWidthSeeds = nan(2, 2, numel(seeds));
for m = 1:2
    for v = 1:2
        for s = 1:numel(seeds)
            cdSeeds(m,v,s) = select_value(summary, 'cd_median_abs_error_nm', magnifications(m), variants(v), seeds(s));
            ringSeeds(m,v,s) = select_value(summary, 'outer_ringing_energy', magnifications(m), variants(v), seeds(s));
            edgeWidthSeeds(m,v,s) = select_value(summary, 'edge_width_10_90_nm', magnifications(m), variants(v), seeds(s));
        end
    end
end
cdMean = mean(cdSeeds, 3);
cdLow = cdMean - min(cdSeeds, [], 3);
cdHigh = max(cdSeeds, [], 3) - cdMean;
ringRelativeSeeds = 100 * ringSeeds ./ ringSeeds(:,1,:);
ringRelativeMean = zeros(2, 2);
ringRelativeMean(:,1) = 100;
ringRelativeMean(:,2) = 100 * mean(ringSeeds(:,2,:), 3) ./ mean(ringSeeds(:,1,:), 3);
ringRelativeLow = ringRelativeMean - min(ringRelativeSeeds, [], 3);
ringRelativeHigh = max(ringRelativeSeeds, [], 3) - ringRelativeMean;
edgeWidthMean = mean(edgeWidthSeeds, 3);

magColumn = repelem(magnifications(:), 2);
variantColumn = repmat(variants(:), 2, 1);
tradeoffTable = table(magColumn, variantColumn, reshape(cdMean.', [], 1), ...
    reshape(min(cdSeeds, [], 3).', [], 1), reshape(max(cdSeeds, [], 3).', [], 1), ...
    reshape(mean(ringSeeds, 3).', [], 1), reshape(ringRelativeMean.', [], 1), ...
    reshape(edgeWidthMean.', [], 1), 'VariableNames', {'magnification', 'variant', ...
    'cd_median_abs_error_nm_two_seed_mean', 'cd_two_seed_min_nm', 'cd_two_seed_max_nm', ...
    'outer_ringing_energy_two_seed_mean', 'outer_ringing_percent_of_full', ...
    'edge_width_10_90_nm_two_seed_mean'});
writetable(tradeoffTable, fullfile(tableDir, '03_cd_ringing_tradeoff.csv'));

fig2 = figure('Color', 'w', 'Units', 'inches', 'Position', [1 1 7.25 3.95]);
tl = tiledlayout(fig2, 1, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

ax1 = nexttile(tl, 1); hold(ax1, 'on');
b1 = bar(ax1, 1:2, cdMean, 'grouped', 'BarWidth', 0.78);
b1(1).FaceColor = blue; b1(1).EdgeColor = blue*0.65;
b1(2).FaceColor = orange; b1(2).EdgeColor = orange*0.65;
for v = 1:2
    errorbar(ax1, b1(v).XEndPoints, cdMean(:,v), cdLow(:,v), cdHigh(:,v), ...
        'Color', [0.18 0.18 0.18], 'LineStyle', 'none', 'LineWidth', 0.9, 'CapSize', 5);
    for m = 1:2
        text(ax1, b1(v).XEndPoints(m), cdMean(m,v)+cdHigh(m,v)+4.5, sprintf('%.2f', cdMean(m,v)), ...
            'HorizontalAlignment', 'center', 'FontName', fontName, 'FontSize', 9.2);
    end
end
set(ax1, 'XTick', 1:2, 'XTickLabel', {'50x', '20x'});
ylabel(ax1, 'Median absolute CD error (nm)');
ylim(ax1, [0, 245]);
style_axes(ax1, fontName);
text(ax1, 0.02, 0.97, '(a)', 'Units', 'normalized', 'FontName', fontName, ...
    'FontWeight', 'bold', 'FontSize', 11, 'VerticalAlignment', 'top');

ax2 = nexttile(tl, 2); hold(ax2, 'on');
b2 = bar(ax2, 1:2, ringRelativeMean, 'grouped', 'BarWidth', 0.78);
b2(1).FaceColor = blue; b2(1).EdgeColor = blue*0.65;
b2(2).FaceColor = orange; b2(2).EdgeColor = orange*0.65;
for v = 1:2
    errorbar(ax2, b2(v).XEndPoints, ringRelativeMean(:,v), ringRelativeLow(:,v), ringRelativeHigh(:,v), ...
        'Color', [0.18 0.18 0.18], 'LineStyle', 'none', 'LineWidth', 0.9, 'CapSize', 5);
    for m = 1:2
        text(ax2, b2(v).XEndPoints(m), ringRelativeMean(m,v)+ringRelativeHigh(m,v)+12, ...
            sprintf('%.1f%%', ringRelativeMean(m,v)), 'HorizontalAlignment', 'center', ...
            'FontName', fontName, 'FontSize', 9.2);
    end
end
set(ax2, 'XTick', 1:2, 'XTickLabel', {'50x', '20x'});
ylabel(ax2, 'Outer ringing energy (% of full model)');
ylim(ax2, [0, 565]);
style_axes(ax2, fontName);
text(ax2, 0.02, 0.97, '(b)', 'Units', 'normalized', 'FontName', fontName, ...
    'FontWeight', 'bold', 'FontSize', 11, 'VerticalAlignment', 'top');

lg = legend(ax1, [b1(1) b1(2)], {'Full model', 'Without Raw-position anchor'}, ...
    'Orientation', 'horizontal', 'Box', 'off');
lg.Layout.Tile = 'north';

export_figure(fig2, figureDir, '03_raw_anchor_cd_ringing_tradeoff');

metadata.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
metadata.profile_source = '50x center pillar P29; 720-direction radial mean; no profile smoothing; native 0-255 outputs converted to darkness';
metadata.model_aggregation = 'Full and no-anchor profiles are arithmetic means of fixed seeds 1261200 and 1261217';
metadata.tradeoff_source = summaryPath;
metadata.display_adjustment = 'No per-image contrast stretching; the separate outer-region figure only subtracts each profile far-background median';
fid = fopen(fullfile(outRoot, 'analysis_metadata.json'), 'w');
fprintf(fid, '%s', jsonencode(metadata, 'PrettyPrint', true));
fclose(fid);

disp('Generated raw-anchor evidence figures:');
disp(fullfile(figureDir, '01_raw_anchor_edge_profile_50x_p29.png'));
disp(fullfile(figureDir, '02_raw_anchor_outer_ringing_50x_p29.png'));
disp(fullfile(figureDir, '03_raw_anchor_cd_ringing_tradeoff.png'));

function darkness = read_darkness(path)
    image = imread(path);
    if ndims(image) == 3
        image = rgb2gray(image);
    end
    if isinteger(image)
        gray = double(image) / double(intmax(class(image)));
    else
        gray = double(image);
        if max(gray(:)) > 1, gray = gray / 255.0; end
    end
    darkness = 1.0 - gray;
end

function profile = radial_mean_darkness(darkness, cx, cy, radii, angles)
    [rr, aa] = meshgrid(radii, angles);
    xx = cx + cos(aa).*rr;
    yy = cy + sin(aa).*rr;
    samples = interp2(darkness, xx, yy, 'linear');
    profile = mean(samples, 1, 'omitnan');
end

function value = select_value(summary, metricName, magnification, variantName, seed)
    mask = string(summary.metric) == string(metricName) & ...
        string(summary.stratum) == string(magnification) & ...
        string(summary.variant) == string(variantName) & summary.seed == seed;
    assert(nnz(mask) == 1, 'Summary row was not found uniquely.');
    value = summary.value(mask);
end

function style_axes(ax, fontName)
    set(ax, 'FontName', fontName, 'FontSize', 10.5, 'LineWidth', 0.85, ...
        'Box', 'off', 'TickDir', 'out', 'Layer', 'top', 'Color', 'w');
    grid(ax, 'on');
    ax.GridColor = [0.82 0.82 0.82];
    ax.GridAlpha = 0.72;
    ax.MinorGridAlpha = 0.25;
end

function export_figure(fig, outDir, stem)
    exportgraphics(fig, fullfile(outDir, stem + ".png"), 'Resolution', 360);
    exportgraphics(fig, fullfile(outDir, stem + ".pdf"), 'ContentType', 'vector');
    savefig(fig, fullfile(outDir, stem + ".fig"));
end
