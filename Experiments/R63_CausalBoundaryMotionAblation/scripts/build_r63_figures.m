function build_r63_figures()
%BUILD_R63_FIGURES Export standalone English MATLAB figures for R63.

scriptDir = fileparts(mfilename('fullpath'));
experimentDir = fileparts(scriptDir);
aggregateDir = fullfile(experimentDir, 'results', 'evaluation', 'aggregate');
protectionDir = fullfile(experimentDir, 'results', 'evaluation', 'output_protection', 'aggregate');
tableDir = fullfile(experimentDir, 'results', 'tables');
figureDir = fullfile(experimentDir, 'figures');
if ~exist(figureDir, 'dir'); mkdir(figureDir); end

factorial = readtable(fullfile(aggregateDir, 'factorial_effects.csv'), 'TextType', 'string');
architecture = readtable(fullfile(aggregateDir, 'architecture_effects.csv'), 'TextType', 'string');
components = readtable(fullfile(aggregateDir, 'component_effects.csv'), 'TextType', 'string');
candidate = readtable(fullfile(aggregateDir, 'candidate_seed_summary.csv'), 'TextType', 'string');
fullVsRaw = readtable(fullfile(aggregateDir, 'full_vs_raw_context.csv'), 'TextType', 'string');
protection = readtable(fullfile(protectionDir, 'output_protection_effects.csv'), 'TextType', 'string');
training = readtable(fullfile(tableDir, 'training_runs.csv'), ...
    'Delimiter', ',', 'ReadVariableNames', true, ...
    'VariableNamingRule', 'preserve', 'TextType', 'string');

style = chart_style();

% 01 Geometry anchoring and SEM-referenced CD.
rows = factorial(factorial.mechanism == "geometry_anchor" & ...
    factorial.metric == "cd_median_abs_error_nm" & ...
    ismember(factorial.stratum, ["50x", "20x"]), :);
rows = order_rows(rows, ["50x", "20x"]);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["50x", "20x"]);
ylabel(ax, 'Removal penalty in median CD error (nm)');
title(ax, 'Static geometry anchoring and SEM-referenced CD error');
subtitle(ax, 'Positive values indicate lower error when geometry anchoring is retained');
finish_axes(ax); export_pair(fig, figureDir, '01_geometry_anchor_cd_error');

% 02 Motion consistency and step variability.
order = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
rows = factorial(factorial.mechanism == "motion_consistency" & ...
    factorial.metric == "displacement_step_magnitude_nm" & ...
    ismember(factorial.stratum, order), :);
rows = order_rows(rows, order);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9, ...
    'HandleVisibility', 'off');
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Removal penalty in step SD (nm)');
title(ax, 'Relative-motion consistency and step variability');
subtitle(ax, 'Thirty Raw-ranked steps per sequence; two matched seeds');
finish_axes(ax); export_pair(fig, figureDir, '02_motion_consistency_step_sd');

% 03 Motion consistency and within-grid disagreement.
rows = factorial(factorial.mechanism == "motion_consistency" & ...
    factorial.metric == "displacement_within_grid_nm" & ...
    ismember(factorial.stratum, order), :);
rows = order_rows(rows, order);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Removal penalty in grid disagreement (nm)');
title(ax, 'Relative-motion consistency and nine-pillar agreement');
subtitle(ax, 'Positive values indicate more consistent pillar motion with the constraint retained');
finish_axes(ax); export_pair(fig, figureDir, '03_motion_consistency_grid_agreement');

% 04 Static-geometry components on the independent 50x CD check.
geometryComponents = ["shape_geometry", "global_boundary_position", ...
    "identity_boundary_guard", "region_boundary_teacher"];
geometryLabels = ["Shape geometry", "Global edge position", ...
    "Identity-boundary guard", "Boundary-region teacher"];
rows = components(components.metric == "cd_median_abs_error_nm" & ...
    components.stratum == "50x" & ismember(components.component, geometryComponents), :);
rows = order_component_rows(rows, geometryComponents);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, geometryLabels);
ylabel(ax, 'Removal penalty in median CD error (nm)');
title(ax, 'Static-geometry components and 50x SEM-referenced CD');
subtitle(ax, 'Package-manifest-unseen capture; positive values favor retaining the component');
finish_axes(ax); export_pair(fig, figureDir, '04_geometry_components_50x_cd');

% 05 Static-geometry components on the same-domain 20x supporting check.
rows = components(components.metric == "cd_median_abs_error_nm" & ...
    components.stratum == "20x" & ismember(components.component, geometryComponents), :);
rows = order_component_rows(rows, geometryComponents);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, geometryLabels);
ylabel(ax, 'Removal penalty in median CD error (nm)');
title(ax, 'Static-geometry components and 20x SEM-referenced CD');
subtitle(ax, 'Same-domain supporting check; positive values favor retaining the component');
finish_axes(ax); export_pair(fig, figureDir, '05_geometry_components_20x_cd');

% 06 Motion components and step variability.
motionComponents = ["adjacent_frame_consistency", "known_shift_motion", "shift_equivariance"];
rows = components(components.metric == "displacement_step_magnitude_nm" & ...
    ismember(components.component, motionComponents) & ...
    ismember(components.stratum, order), :);
rows = order_rows_by_component(rows, order, motionComponents);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_grouped_component_intervals(ax, rows, order, motionComponents, style);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9, ...
    'HandleVisibility', 'off');
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Removal penalty in step SD (nm)');
title(ax, 'Motion-supervision components and step variability');
subtitle(ax, 'Positive values favor retaining the component; thirty Raw-ranked steps per sequence');
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
finish_axes(ax); export_pair(fig, figureDir, '06_motion_components_step_sd');

% 07 Shift-safe versus ordinary upsampling on known shifts.
rows = candidate(candidate.metric == "synthetic_vector_error_px" & ...
    ismember(candidate.variant, ["shift_safe_matched", "standard_upsample_matched"]), :);
magnitudes = [0.08, 0.4, 0.8, 2.0, 8.0];
sourceLabels = string(magnitudes) + "px";
displayLabels = string(magnitudes) + " px";
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_architecture_series(ax, rows, "shift_safe_matched", sourceLabels, style.blue, 'o', 'Shift-safe');
plot_architecture_series(ax, rows, "standard_upsample_matched", sourceLabels, style.orange, 's', 'Ordinary');
set_category_axis(ax, displayLabels);
ylabel(ax, 'Median translation-vector error (px)');
title(ax, 'Known-shift translation fidelity by upsampling method');
subtitle(ax, 'Nine package-manifest-unseen 50x pillars, eight directions, two matched seeds');
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
finish_axes(ax); export_pair(fig, figureDir, '07_upsampling_translation_fidelity');

% 08 Architecture penalty in edge-radius stability.
rows = architecture(architecture.metric == "synthetic_edge_radius_change_px" & ...
    ismember(architecture.stratum, sourceLabels), :);
rows = order_rows(rows, sourceLabels);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_arch_effect_intervals(ax, rows, style.orange);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, displayLabels);
ylabel(ax, 'Ordinary-minus-shift-safe penalty (px)');
title(ax, 'Upsampling method and apparent edge-radius stability');
subtitle(ax, 'Positive values indicate greater edge-position variation with ordinary upsampling');
finish_axes(ax); export_pair(fig, figureDir, '08_upsampling_edge_radius_stability');

% 09 Output-protection effects on within-grid disagreement.
rows = protection(protection.metric == "displacement_within_grid_nm", :);
ablations = ["no_boundary", "no_anchor", "no_gate", "no_all"];
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
for i = 1:numel(ablations)
    values = rows.ablation_minus_full(rows.ablation == ablations(i));
    x = i + linspace(-0.12, 0.12, numel(values));
    scatter(ax, x, values, 28, style.lightGray, 'filled', ...
        'MarkerEdgeColor', style.midGray, 'HandleVisibility', 'off');
    plot(ax, i, mean(values), 'o', 'MarkerSize', 7, ...
        'MarkerFaceColor', style.blue, 'MarkerEdgeColor', style.blue, ...
        'HandleVisibility', 'off');
end
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["No boundary adapter", "No raw anchor", "No quality gate", "All bypassed"]);
ylabel(ax, 'Change from full output path (nm)');
title(ax, 'Inference-only output protection and grid disagreement');
subtitle(ax, 'Gray points are the four sequences; blue markers are sequence means');
finish_axes(ax); export_pair(fig, figureDir, '09_output_protection_grid_disagreement');

% 10 Selected checkpoint epoch by condition and seed.
variantOrder = ["full_control", "no_geometry_anchor", "no_motion_consistency", ...
    "no_geometry_no_motion", "no_shape_geometry", "no_global_boundary_position", ...
    "no_identity_boundary_guard", "no_region_boundary_teacher", ...
    "no_sequence_consistency", "no_known_shift_motion", "no_shift_equivariance", ...
    "no_boundary_residual_adapter", "no_raw_position_anchor", "no_quality_gate", ...
    "shift_safe_matched", "standard_upsample_matched"];
displayOrder = ["Full", "No geometry", "No motion", "Neither", "No shape", ...
    "No global position", "No identity guard", "No region teacher", ...
    "No sequence", "No shift pairs", "No shift equivariance", ...
    "No boundary adapter", "No raw anchor", "No quality gate", ...
    "Shift-safe", "Ordinary"];
fig = new_wide_figure(); ax = axes(fig); hold(ax, 'on');
hSeed1 = gobjects(1); hSeed2 = gobjects(1);
for i = 1:numel(variantOrder)
    subset = training(training.variant == variantOrder(i), :);
    subset = sortrows(subset, 'seed');
    h1 = scatter(ax, i - 0.08, subset.selected_epoch(1), 42, 'o', ...
        'MarkerFaceColor', style.blue, 'MarkerEdgeColor', style.blue);
    h2 = scatter(ax, i + 0.08, subset.selected_epoch(2), 42, 's', ...
        'MarkerFaceColor', 'none', 'MarkerEdgeColor', style.orange, 'LineWidth', 1.2);
    if i == 1
        hSeed1 = h1; hSeed2 = h2;
    else
        h1.HandleVisibility = 'off'; h2.HandleVisibility = 'off';
    end
end
budget = mode(training.epochs);
yline(ax, budget, '--', 'Color', style.midGray, 'LineWidth', 0.9, ...
    'HandleVisibility', 'off');
ylim(ax, [20, budget + 2]);
set_category_axis(ax, displayOrder);
ax.XTickLabelRotation = 20;
ylabel(ax, 'Selected checkpoint epoch');
title(ax, 'Selected checkpoint epoch across matched conditions');
subtitle(ax, 'Late selections are interpreted with the pre-registered global convergence gate');
legend(ax, [hSeed1, hSeed2], {'Seed 1261200', 'Seed 1261217'}, ...
    'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
finish_axes(ax); export_pair(fig, figureDir, '10_selected_checkpoint_epoch');

% 11 Retrained boundary-residual adapter removal and static CD.
rows = components(components.component == "boundary_residual_adapter" & ...
    components.metric == "cd_median_abs_error_nm" & ...
    ismember(components.stratum, ["50x", "20x"]), :);
rows = order_rows(rows, ["50x", "20x"]);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["50x", "20x"]);
ylabel(ax, 'Removal penalty in median CD error (nm)');
title(ax, 'Boundary-residual adapter and SEM-referenced CD');
subtitle(ax, 'Matched retraining without the adapter; positive values favor retaining it');
finish_axes(ax); export_pair(fig, figureDir, '11_boundary_adapter_cd_error');

% 12 Retrained raw-position anchor removal and step variability.
rows = components(components.component == "raw_position_anchor" & ...
    components.metric == "displacement_step_magnitude_nm" & ...
    ismember(components.stratum, order), :);
rows = order_rows(rows, order);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Removal penalty in step SD (nm)');
title(ax, 'Raw-position anchor and displacement stability');
subtitle(ax, 'Matched retraining without the anchor; thirty Raw-ranked steps per sequence');
finish_axes(ax); export_pair(fig, figureDir, '12_raw_position_anchor_step_sd');

% 13 Retrained quality-gate removal and nine-pillar agreement.
rows = components(components.component == "quality_gate" & ...
    components.metric == "displacement_within_grid_nm" & ...
    ismember(components.stratum, order), :);
rows = order_rows(rows, order);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Removal penalty in grid disagreement (nm)');
title(ax, 'Quality gate and nine-pillar displacement agreement');
subtitle(ax, 'Matched retraining without the gate; positive values favor retaining it');
finish_axes(ax); export_pair(fig, figureDir, '13_quality_gate_grid_agreement');

% 14 Retrained quality-gate removal and threshold sensitivity.
rows = components(components.component == "quality_gate" & ...
    components.metric == "cd_bound_width_nm" & ...
    ismember(components.stratum, ["50x", "20x"]), :);
rows = order_rows(rows, ["50x", "20x"]);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9);
set_category_axis(ax, ["50x", "20x"]);
ylabel(ax, 'Removal penalty in CD bound width (nm)');
title(ax, 'Quality gate and threshold-robust CD bounds');
subtitle(ax, 'Positive values indicate narrower threshold sensitivity with the gate retained');
finish_axes(ax); export_pair(fig, figureDir, '14_quality_gate_cd_bound_width');

% 15 MOSR versus Raw on SEM-referenced CD accuracy.
rows = fullVsRaw(fullVsRaw.metric == "cd_median_abs_error_nm" & ...
    ismember(fullVsRaw.stratum, ["50x", "20x"]), :);
rows = order_full_vs_raw(rows, ["50x", "20x"]);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_full_vs_raw_bars(ax, rows, ["50x", "20x"], style);
set_category_axis(ax, ["50x", "20x"]);
ylabel(ax, 'Median absolute CD error (nm)');
title(ax, 'MOSR and SEM-referenced CD accuracy');
subtitle(ax, 'Lower values are better; markers show two repeated training runs');
finish_axes(ax); export_pair(fig, figureDir, '15_full_vs_raw_cd_error');

% 16 MOSR versus Raw on step variability.
rows = fullVsRaw(fullVsRaw.metric == "displacement_step_magnitude_nm" & ...
    ismember(fullVsRaw.stratum, order), :);
rows = order_full_vs_raw(rows, order);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_full_vs_raw_bars(ax, rows, order, style);
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Step SD (nm)');
title(ax, 'MOSR and real-sequence step stability');
subtitle(ax, 'Thirty fixed steps selected from Raw images; lower values are better');
finish_axes(ax); export_pair(fig, figureDir, '16_full_vs_raw_step_stability');

% 17 MOSR versus Raw on nine-pillar agreement.
rows = fullVsRaw(fullVsRaw.metric == "displacement_within_grid_nm" & ...
    ismember(fullVsRaw.stratum, order), :);
rows = order_full_vs_raw(rows, order);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_full_vs_raw_bars(ax, rows, order, style);
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Within-grid disagreement (nm)');
title(ax, 'MOSR and nine-pillar displacement agreement');
subtitle(ax, 'Lower values indicate more spatially consistent pillar motion');
finish_axes(ax); export_pair(fig, figureDir, '17_full_vs_raw_grid_agreement');

% 18 Input-referenced output removal and CD accuracy.
rows = components(components.component == "raw_position_anchor" & ...
    components.metric == "cd_median_abs_error_nm" & ...
    ismember(components.stratum, ["50x", "20x"]), :);
rows = order_rows(rows, ["50x", "20x"]);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_effect_intervals(ax, rows, style.blue);
yline(ax, 0, '-', 'Color', style.charcoal, 'LineWidth', 0.9, ...
    'HandleVisibility', 'off');
set_category_axis(ax, ["50x", "20x"]);
ylabel(ax, 'Removal penalty in median CD error (nm)');
title(ax, 'Input-referenced output and SEM-referenced CD accuracy');
subtitle(ax, 'Positive values favor retaining the input reference; the response depends on magnification');
finish_axes(ax); export_pair(fig, figureDir, '18_raw_position_anchor_cd_error');

% 19 Anti-aliased versus conventional upsampling on real-sequence grid agreement.
rows = candidate(candidate.metric == "displacement_within_grid_nm" & ...
    ismember(candidate.variant, ["shift_safe_matched", "standard_upsample_matched"]) & ...
    ismember(candidate.stratum, order), :);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_variant_bars(ax, rows, order, style);
set_category_axis(ax, ["50x, 0.5 um", "50x, 1.0 um", "20x, 0.5 um", "20x, 1.0 um"]);
ylabel(ax, 'Within-grid disagreement (nm)');
title(ax, 'Upsampling method and nine-pillar displacement agreement');
subtitle(ax, 'Lower values are better; equal parameter count and two repeated training runs');
finish_axes(ax); export_pair(fig, figureDir, '19_upsampling_grid_agreement');

% 20 MOSR versus Raw ringing trade-off.
rows = fullVsRaw(fullVsRaw.metric == "outer_ringing_energy" & ...
    ismember(fullVsRaw.stratum, ["50x", "20x"]), :);
rows = order_full_vs_raw(rows, ["50x", "20x"]);
fig = new_figure(); ax = axes(fig); hold(ax, 'on');
plot_full_vs_raw_bars(ax, rows, ["50x", "20x"], style);
set_category_axis(ax, ["50x", "20x"]);
ylabel(ax, 'Outer ringing energy');
title(ax, 'MOSR outer-ringing trade-off');
subtitle(ax, 'The 50x improvement in edge localization is accompanied by increased ringing');
finish_axes(ax); export_pair(fig, figureDir, '20_full_vs_raw_ringing_tradeoff');

fprintf('R63 figures written to %s\n', figureDir);
end

function style = chart_style()
style.blue = [0.00, 0.447, 0.741];
style.orange = [0.850, 0.325, 0.098];
style.charcoal = [0.18, 0.18, 0.18];
style.midGray = [0.50, 0.50, 0.50];
style.lightGray = [0.78, 0.78, 0.78];
end

function fig = new_figure()
fig = figure('Color', 'w', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [100, 100, 900, 650]);
end

function fig = new_wide_figure()
fig = figure('Color', 'w', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [100, 100, 1200, 650]);
end

function rows = order_rows(rows, order)
[tf, location] = ismember(rows.stratum, order);
if ~all(tf); error('Unexpected stratum in source table.'); end
[~, index] = sort(location);
rows = rows(index, :);
end

function rows = order_component_rows(rows, order)
[tf, location] = ismember(rows.component, order);
if ~all(tf); error('Unexpected component in source table.'); end
[~, index] = sort(location);
rows = rows(index, :);
end

function rows = order_rows_by_component(rows, stratumOrder, componentOrder)
[tfS, locationS] = ismember(rows.stratum, stratumOrder);
[tfC, locationC] = ismember(rows.component, componentOrder);
if ~all(tfS) || ~all(tfC); error('Unexpected component or stratum in source table.'); end
[~, index] = sortrows([locationS, locationC], [1, 2]);
rows = rows(index, :);
end

function rows = order_full_vs_raw(rows, stratumOrder)
[tf, location] = ismember(rows.stratum, stratumOrder);
if ~all(tf); error('Unexpected full-versus-Raw stratum.'); end
[~, index] = sortrows([location, rows.seed], [1, 2]);
rows = rows(index, :);
end

function plot_full_vs_raw_bars(ax, rows, stratumOrder, style)
rawMeans = nan(1, numel(stratumOrder));
fullMeans = nan(1, numel(stratumOrder));
rawValues = cell(1, numel(stratumOrder));
fullValues = cell(1, numel(stratumOrder));
for i = 1:numel(stratumOrder)
    subset = rows(rows.stratum == stratumOrder(i), :);
    subset = sortrows(subset, 'seed');
    rawValues{i} = subset.raw_value;
    fullValues{i} = subset.full_value;
    rawMeans(i) = mean(rawValues{i});
    fullMeans(i) = mean(fullValues{i});
end
b = bar(ax, [rawMeans(:), fullMeans(:)], 'grouped', 'BarWidth', 0.72);
b(1).FaceColor = style.lightGray; b(1).EdgeColor = style.midGray;
b(2).FaceColor = style.blue; b(2).EdgeColor = style.blue;
b(1).DisplayName = 'Raw'; b(2).DisplayName = 'MOSR';
drawnow;
for i = 1:numel(stratumOrder)
    rawX = b(1).XEndPoints(i) + linspace(-0.025, 0.025, numel(rawValues{i}))';
    fullX = b(2).XEndPoints(i) + linspace(-0.025, 0.025, numel(fullValues{i}))';
    scatter(ax, rawX, rawValues{i}, ...
        24, 'o', 'MarkerFaceColor', 'w', 'MarkerEdgeColor', style.charcoal, ...
        'HandleVisibility', 'off');
    scatter(ax, fullX, fullValues{i}, ...
        24, 's', 'MarkerFaceColor', 'w', 'MarkerEdgeColor', style.charcoal, ...
        'HandleVisibility', 'off');
end
legend(ax, b, {'Raw', 'MOSR'}, 'Location', 'northoutside', ...
    'Orientation', 'horizontal', 'Box', 'off');
end

function plot_variant_bars(ax, rows, stratumOrder, style)
variants = ["shift_safe_matched", "standard_upsample_matched"];
means = nan(numel(stratumOrder), 2);
values = cell(numel(stratumOrder), 2);
for i = 1:numel(stratumOrder)
    for j = 1:2
        subset = rows(rows.stratum == stratumOrder(i) & rows.variant == variants(j), :);
        subset = sortrows(subset, 'seed');
        values{i, j} = subset.value;
        means(i, j) = mean(values{i, j});
    end
end
b = bar(ax, means, 'grouped', 'BarWidth', 0.72);
b(1).FaceColor = style.blue; b(1).EdgeColor = style.blue;
b(2).FaceColor = 'w'; b(2).EdgeColor = style.orange; b(2).LineWidth = 1.1;
b(1).DisplayName = 'Anti-aliased'; b(2).DisplayName = 'Conventional';
drawnow;
for i = 1:numel(stratumOrder)
    for j = 1:2
        pointX = b(j).XEndPoints(i) + linspace(-0.025, 0.025, numel(values{i, j}))';
        scatter(ax, pointX, values{i, j}, ...
            24, ternary(j == 1, 'o', 's'), 'MarkerFaceColor', 'w', ...
            'MarkerEdgeColor', style.charcoal, 'HandleVisibility', 'off');
    end
end
legend(ax, b, {'Anti-aliased', 'Conventional'}, 'Location', 'northoutside', ...
    'Orientation', 'horizontal', 'Box', 'off');
end

function plot_grouped_component_intervals(ax, rows, stratumOrder, componentOrder, style)
colors = {style.blue, style.orange, style.midGray};
markers = {'o', 's', '^'};
names = {'Adjacent-frame consistency', 'Known-shift motion pairs', 'Shift equivariance'};
offsets = [-0.18, 0, 0.18];
for c = 1:numel(componentOrder)
    subset = rows(rows.component == componentOrder(c), :);
    subset = order_rows(subset, stratumOrder);
    x = (1:height(subset)) + offsets(c);
    y = subset.mean_removal_penalty;
    low = y - subset.bootstrap_ci_low;
    high = subset.bootstrap_ci_high - y;
    errorbar(ax, x, y, low, high, markers{c}, 'Color', colors{c}, ...
        'MarkerFaceColor', colors{c}, 'MarkerEdgeColor', colors{c}, ...
        'LineWidth', 1.2, 'CapSize', 6, 'DisplayName', names{c});
    scatter(ax, x - 0.035, subset.effect_seed1261200, 20, markers{c}, ...
        'MarkerFaceColor', 'w', 'MarkerEdgeColor', colors{c}, 'HandleVisibility', 'off');
    scatter(ax, x + 0.035, subset.effect_seed1261217, 20, markers{c}, ...
        'MarkerFaceColor', 'w', 'MarkerEdgeColor', colors{c}, 'HandleVisibility', 'off');
end
end

function plot_effect_intervals(ax, rows, color)
x = 1:height(rows);
y = rows.mean_removal_penalty;
low = y - rows.bootstrap_ci_low;
high = rows.bootstrap_ci_high - y;
errorbar(ax, x, y, low, high, 'o', 'Color', color, ...
    'MarkerFaceColor', color, 'MarkerEdgeColor', color, ...
    'LineWidth', 1.2, 'CapSize', 7, 'HandleVisibility', 'off');
scatter(ax, x - 0.08, rows.effect_seed1261200, 28, 'o', ...
    'MarkerFaceColor', 'w', 'MarkerEdgeColor', color, 'HandleVisibility', 'off');
scatter(ax, x + 0.08, rows.effect_seed1261217, 28, 's', ...
    'MarkerFaceColor', 'w', 'MarkerEdgeColor', color, 'HandleVisibility', 'off');
end

function plot_arch_effect_intervals(ax, rows, color)
x = 1:height(rows);
y = rows.mean_standard_penalty;
low = y - rows.bootstrap_ci_low;
high = rows.bootstrap_ci_high - y;
errorbar(ax, x, y, low, high, 'o', 'Color', color, ...
    'MarkerFaceColor', color, 'MarkerEdgeColor', color, ...
    'LineWidth', 1.2, 'CapSize', 7, 'HandleVisibility', 'off');
scatter(ax, x - 0.08, rows.effect_seed1261200, 28, 'o', ...
    'MarkerFaceColor', 'w', 'MarkerEdgeColor', color, 'HandleVisibility', 'off');
scatter(ax, x + 0.08, rows.effect_seed1261217, 28, 's', ...
    'MarkerFaceColor', 'w', 'MarkerEdgeColor', color, 'HandleVisibility', 'off');
end

function plot_architecture_series(ax, rows, variant, labels, color, marker, displayName)
subset = rows(rows.variant == variant, :);
means = nan(size(labels)); low = nan(size(labels)); high = nan(size(labels));
for i = 1:numel(labels)
    values = subset.value(subset.stratum == labels(i));
    means(i) = mean(values);
    low(i) = means(i) - min(values);
    high(i) = max(values) - means(i);
end
errorbar(ax, 1:numel(labels), means, low, high, ['-' marker], ...
    'Color', color, 'MarkerFaceColor', ternary(marker == 'o', color, 'w'), ...
    'MarkerEdgeColor', color, 'LineWidth', 1.25, 'CapSize', 6, ...
    'DisplayName', displayName);
end

function set_category_axis(ax, labels)
ax.XLim = [0.5, numel(labels) + 0.5];
ax.XTick = 1:numel(labels);
ax.XTickLabel = labels;
ax.XTickLabelRotation = 0;
end

function finish_axes(ax)
ax.FontName = 'Times New Roman';
ax.FontSize = 10;
ax.LineWidth = 0.8;
ax.Box = 'off';
ax.TickDir = 'out';
ax.XColor = [0.18, 0.18, 0.18];
ax.YColor = [0.18, 0.18, 0.18];
grid(ax, 'on');
ax.GridColor = [0.86, 0.86, 0.86];
ax.GridAlpha = 0.7;
end

function export_pair(fig, folder, stem)
exportgraphics(fig, fullfile(folder, [stem '.png']), 'Resolution', 300);
exportgraphics(fig, fullfile(folder, [stem '.pdf']), 'ContentType', 'vector');
close(fig);
end

function out = ternary(condition, yesValue, noValue)
if condition; out = yesValue; else; out = noValue; end
end
