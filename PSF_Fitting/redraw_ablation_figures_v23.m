function redraw_ablation_figures_v23()
% Redraw the complete thesis ablation section in English.

evaluationRoot = "D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results\evaluation";
outputRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\09_V23_ABLATION_COMPLETE_ENGLISH_20260727";
figureDir = fullfile(outputRoot, "figures");
tableDir = fullfile(outputRoot, "tables");
ensure_dir(outputRoot);
ensure_dir(figureDir);
ensure_dir(tableDir);

summaryPath = fullfile(evaluationRoot, "aggregate", "candidate_seed_summary.csv");
summary = readtable(summaryPath, "VariableNamingRule", "preserve", "TextType", "string");

colors.Blue = [0.05 0.38 0.67];
colors.Orange = [0.82 0.42 0.12];
colors.Reference = [0.34 0.34 0.34];
colors.Grid = [0.86 0.86 0.86];
colors.Text = [0.18 0.18 0.18];

scopes = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um", "all_sequences"];
scopeLabels = ["50x, 0.5 µm", "50x, 1.0 µm", "20x, 0.5 µm", "20x, 1.0 µm", "All sequences"];

shiftVariants = ["shift_safe_matched", "standard_upsample_matched"];
shiftLabels = ["Anti-aliased upsampling", "Standard upsampling"];
anchorVariants = ["full_control", "no_raw_position_anchor"];
anchorLabels = ["Full model", "Without Raw-position anchor"];

stepSd = select_summary(summary, "displacement_step_magnitude_nm", scopes, shiftVariants);
writetable(stepSd, fullfile(tableDir, "01_shift_safe_step_sd_source.csv"));
plot_grouped_absolute(stepSd, scopes, scopeLabels, shiftVariants, shiftLabels, ...
    "Step-displacement standard deviation (nm)", [0 18], colors, ...
    fullfile(figureDir, "01_shift_safe_step_sd_absolute"));

positionMetrics = select_summary(summary, ...
    ["displacement_within_grid_nm", "displacement_command_abs_error_nm"], ...
    scopes, shiftVariants);
writetable(positionMetrics, fullfile(tableDir, "02_shift_safe_position_metrics_source.csv"));
plot_two_position_metrics(positionMetrics, scopes, scopeLabels, shiftVariants, ...
    shiftLabels, colors, fullfile(figureDir, "02_shift_safe_position_metrics_absolute"));

sequences = scopes(1:4);
for i = 1:numel(sequences)
    plot_step_trace(evaluationRoot, sequences(i), colors, ...
        fullfile(figureDir, sprintf("%02d_%s_upsampling_step_trace", i + 2, char(sequences(i)))));
end

anchorMetrics = select_summary(summary, ...
    ["displacement_step_magnitude_nm", "displacement_within_grid_nm", ...
    "displacement_command_abs_error_nm"], scopes, anchorVariants);
writetable(anchorMetrics, fullfile(tableDir, "07_raw_anchor_displacement_source.csv"));
plot_anchor_displacement(anchorMetrics, scopes, scopeLabels, anchorVariants, ...
    anchorLabels, colors, fullfile(figureDir, "07_raw_anchor_displacement_three_metrics"));

perPillar = collect_raw_anchor_per_pillar(evaluationRoot);
writetable(perPillar, fullfile(tableDir, "08_raw_anchor_per_pillar_source.csv"));
plot_raw_anchor_per_pillar(perPillar, colors, ...
    fullfile(figureDir, "08_raw_anchor_per_pillar_both_magnifications"));

write_thesis_summary(summary, scopes, shiftVariants, anchorVariants, ...
    fullfile(tableDir, "09_ablation_displacement_summary.csv"));

metadata.generated_at = char(datetime("now", "Format", "yyyy-MM-dd HH:mm:ss"));
metadata.source_summary = summaryPath;
metadata.figure_count = 8;
metadata.figure_language = "English";
metadata.seed_count = 2;
metadata.note = "Figures use all four predeclared 30-step sequences. Bars show the two-seed mean and range; traces show the two-seed envelope. No visual rescaling or selective condition removal was applied.";
fid = fopen(fullfile(outputRoot, "analysis_metadata.json"), "w", "n", "UTF-8");
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, "%s", jsonencode(metadata, "PrettyPrint", true));
end


function selected = select_summary(summary, metrics, scopes, variants)
selected = summary(ismember(summary.variant, variants) & ...
    ismember(summary.metric, metrics) & ismember(summary.stratum, scopes), :);
end


function plot_grouped_absolute(data, scopes, scopeLabels, variants, legendLabels, ...
        yLabel, yLimits, colors, outputBase)
[means, lows, highs] = mean_range_matrix(data, scopes, variants);
f = compact_figure(7.4, 4.7);
ax = axes(f);
hold(ax, "on");
b = bar(ax, means, "grouped", "BarWidth", 0.78);
format_bars(b, colors);
add_range_bars(ax, b, means, lows, highs, colors);
xticks(ax, 1:numel(scopes));
xticklabels(ax, scopeLabels);
xlim(ax, [0.45 numel(scopes) + 0.55]);
ylim(ax, yLimits);
ylabel(ax, yLabel);
legend(ax, b, legendLabels, "Location", "northoutside", ...
    "Orientation", "horizontal", "Box", "off", "FontSize", 12.5);
style_axes(ax, colors);
export_png_fig(f, outputBase);
close(f);
end


function plot_two_position_metrics(data, scopes, scopeLabels, variants, legendLabels, colors, outputBase)
metrics = ["displacement_within_grid_nm", "displacement_command_abs_error_nm"];
yLabels = ["Within-grid disagreement (nm)", "Command-referenced MAE (nm)"];
panelLabels = ["(a) Within-grid disagreement", "(b) Command-referenced error"];

f = compact_figure(7.4, 6.2);
layout = tiledlayout(f, 2, 1, "TileSpacing", "compact", "Padding", "compact");
handles = gobjects(1, 2);
for k = 1:2
    ax = nexttile(layout, k);
    part = data(data.metric == metrics(k), :);
    [means, lows, highs] = mean_range_matrix(part, scopes, variants);
    hold(ax, "on");
    b = bar(ax, means, "grouped", "BarWidth", 0.78);
    format_bars(b, colors);
    add_range_bars(ax, b, means, lows, highs, colors);
    handles = b;
    xticks(ax, 1:numel(scopes));
    xticklabels(ax, scopeLabels);
    xlim(ax, [0.45 numel(scopes) + 0.55]);
    ylim(ax, [0 14]);
    ylabel(ax, yLabels(k));
    text(ax, 0.015, 0.93, panelLabels(k), "Units", "normalized", ...
        "FontName", "Times New Roman", "FontSize", 12.5, ...
        "FontWeight", "bold", "Color", colors.Text);
    style_axes(ax, colors);
end
lgd = legend(handles, legendLabels, "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 12.5);
lgd.Layout.Tile = "north";
export_png_fig(f, outputBase);
close(f);
end


function plot_step_trace(evaluationRoot, sequence, colors, outputBase)
[frameIds, shiftValues] = load_variant_seed_series(evaluationRoot, "shift_safe_matched", sequence);
[standardIds, standardValues] = load_variant_seed_series(evaluationRoot, "standard_upsample_matched", sequence);
common = intersect(frameIds, standardIds, "stable");
[~, ia] = ismember(common, frameIds);
[~, ib] = ismember(common, standardIds);
shiftValues = shiftValues(ia, :);
standardValues = standardValues(ib, :);
[common, order] = sort(common);
shiftValues = shiftValues(order, :);
standardValues = standardValues(order, :);
assert(numel(common) == 30, "Each displacement trace must contain exactly 30 selected steps.");

nominal = 500;
if contains(sequence, "1um")
    nominal = 1000;
end
x = 1:numel(common);
f = compact_figure(7.4, 4.7);
ax = axes(f);
hold(ax, "on");
yline(ax, nominal, "--", "Color", colors.Reference, "LineWidth", 1.45, ...
    "DisplayName", "PI-stage feedback");
h1 = plot_band(ax, x, shiftValues, colors.Blue, "o", "Anti-aliased upsampling");
h2 = plot_band(ax, x, standardValues, colors.Orange, "s", "Standard upsampling");
xlabel(ax, "Step index");
ylabel(ax, "Measured displacement magnitude (nm)");
xlim(ax, [1 30]);
xticks(ax, [1 5 10 15 20 25 30]);
allValues = [shiftValues(:); standardValues(:); nominal];
margin = max(12, 0.16 * range(allValues));
ylim(ax, [min(allValues) - margin, max(allValues) + margin]);
style_axes(ax, colors);
legend(ax, [findobj(ax, "Type", "ConstantLine"), h1, h2], ...
    ["PI-stage feedback", "Anti-aliased upsampling", "Standard upsampling"], ...
    "Location", "northoutside", "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 11.5);
export_png_fig(f, outputBase);
close(f);
end


function plot_anchor_displacement(data, scopes, scopeLabels, variants, legendLabels, colors, outputBase)
metrics = ["displacement_step_magnitude_nm", "displacement_within_grid_nm", ...
    "displacement_command_abs_error_nm"];
yLabels = ["Step standard deviation (nm)", "Within-grid disagreement (nm)", ...
    "Command-referenced MAE (nm)"];
panelLabels = ["(a) Step standard deviation", "(b) Within-grid disagreement", ...
    "(c) Command-referenced error"];

f = compact_figure(7.4, 8.2);
layout = tiledlayout(f, 3, 1, "TileSpacing", "compact", "Padding", "compact");
handles = gobjects(1, 2);
for k = 1:3
    ax = nexttile(layout, k);
    part = data(data.metric == metrics(k), :);
    [means, lows, highs] = mean_range_matrix(part, scopes, variants);
    hold(ax, "on");
    b = bar(ax, means, "grouped", "BarWidth", 0.78);
    format_bars(b, colors);
    add_range_bars(ax, b, means, lows, highs, colors);
    handles = b;
    xticks(ax, 1:numel(scopes));
    xticklabels(ax, scopeLabels);
    xlim(ax, [0.45 numel(scopes) + 0.55]);
    ylim(ax, [0 17]);
    ylabel(ax, yLabels(k));
    text(ax, 0.015, 0.92, panelLabels(k), "Units", "normalized", ...
        "FontName", "Times New Roman", "FontSize", 12.0, ...
        "FontWeight", "bold", "Color", colors.Text);
    style_axes(ax, colors);
end
lgd = legend(handles, legendLabels, "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 12.5);
lgd.Layout.Tile = "north";
export_png_fig(f, outputBase);
close(f);
end


function result = collect_raw_anchor_per_pillar(evaluationRoot)
variants = ["full_control", "no_raw_position_anchor"];
seeds = [1261200, 1261217];
magnifications = ["50x", "20x"];
result = table();
for m = 1:numel(magnifications)
    for v = 1:numel(variants)
        for s = 1:numel(seeds)
            path = fullfile(evaluationRoot, "metrics", variants(v), ...
                "seed" + seeds(s), "static_cd", "static_cd_per_measurement.csv");
            data = readtable(path, "VariableNamingRule", "preserve", "TextType", "string");
            data = data(data.magnification == magnifications(m) & ...
                data.method == "Method" & data.status == "ok", :);
            pillars = unique(data.pillar_id, "sorted");
            for p = 1:numel(pillars)
                mask = data.pillar_id == pillars(p);
                row = table(magnifications(m), variants(v), seeds(s), pillars(p), ...
                    median(data.abs_error_nm(mask), "omitnan"), ...
                    'VariableNames', {'magnification', 'variant', 'seed', ...
                    'pillar_id', 'median_abs_error_nm'});
                result = [result; row]; %#ok<AGROW>
            end
        end
    end
end
end


function plot_raw_anchor_per_pillar(data, colors, outputBase)
f = compact_figure(7.4, 6.4);
layout = tiledlayout(f, 2, 1, "TileSpacing", "compact", "Padding", "compact");
magnifications = ["50x", "20x"];
panelLabels = ["(a) 50x", "(b) 20x"];
variants = ["full_control", "no_raw_position_anchor"];
lineHandles = gobjects(1, 2);
for m = 1:2
    ax = nexttile(layout, m);
    hold(ax, "on");
    part = data(data.magnification == magnifications(m), :);
    pillarIds = unique(part.pillar_id, "sorted");
    means = nan(numel(pillarIds), 2);
    spreads = nan(numel(pillarIds), 2);
    for p = 1:numel(pillarIds)
        for v = 1:2
            values = part.median_abs_error_nm(part.pillar_id == pillarIds(p) & ...
                part.variant == variants(v));
            means(p, v) = mean(values, "omitnan");
            spreads(p, v) = 0.5 * (max(values) - min(values));
        end
    end
    lineHandles(1) = errorbar(ax, 1:numel(pillarIds), means(:, 1), spreads(:, 1), ...
        "-o", "Color", colors.Blue, "MarkerFaceColor", colors.Blue, ...
        "MarkerSize", 6.5, "LineWidth", 2.25, "CapSize", 7);
    lineHandles(2) = errorbar(ax, 1:numel(pillarIds), means(:, 2), spreads(:, 2), ...
        "-s", "Color", colors.Orange, "MarkerFaceColor", "white", ...
        "MarkerSize", 6.5, "LineWidth", 2.25, "CapSize", 7);
    xticks(ax, 1:numel(pillarIds));
    xticklabels(ax, "P" + string(pillarIds));
    xlim(ax, [0.65 numel(pillarIds) + 0.35]);
    if m == 1
        ylim(ax, [0 150]);
    else
        ylim(ax, [0 350]);
    end
    ylabel(ax, "Median absolute CD error (nm)");
    text(ax, 0.02, 0.92, panelLabels(m), "Units", "normalized", ...
        "FontName", "Times New Roman", "FontSize", 13.0, ...
        "FontWeight", "bold", "Color", colors.Text);
    style_axes(ax, colors);
end
xlabel(layout, "SEM pillar identity", "FontName", "Times New Roman", "FontSize", 13.0);
lgd = legend(lineHandles, ["Full model", "Without Raw-position anchor"], ...
    "Orientation", "horizontal", "Box", "off", "FontSize", 12.5);
lgd.Layout.Tile = "north";
export_png_fig(f, outputBase);
close(f);
end


function [frameIds, values] = load_variant_seed_series(evaluationRoot, variant, sequence)
seeds = [1261200 1261217];
tables = cell(1, numel(seeds));
for i = 1:numel(seeds)
    path = fullfile(evaluationRoot, "metrics", variant, "seed" + seeds(i), ...
        "displacement", "displacement_per_step_top30.csv");
    tableNow = readtable(path, "VariableNamingRule", "preserve", "TextType", "string");
    tableNow = tableNow(tableNow.sequence == sequence & is_true(tableNow.method_valid), ...
        ["end_frame_index", "method_boundary_dx_um"]);
    tableNow.Properties.VariableNames{2} = char("value_" + seeds(i));
    tables{i} = tableNow;
end
joined = innerjoin(tables{1}, tables{2}, "Keys", "end_frame_index");
frameIds = joined.end_frame_index;
values = 1000 * abs([joined.("value_" + seeds(1)), joined.("value_" + seeds(2))]);
end


function [means, lows, highs] = mean_range_matrix(data, scopes, variants)
means = nan(numel(scopes), numel(variants));
lows = nan(size(means));
highs = nan(size(means));
for i = 1:numel(scopes)
    for j = 1:numel(variants)
        values = data.value(data.stratum == scopes(i) & data.variant == variants(j));
        assert(numel(values) == 2, "Expected exactly two fixed-initialization values.");
        means(i, j) = mean(values, "omitnan");
        lows(i, j) = means(i, j) - min(values);
        highs(i, j) = max(values) - means(i, j);
    end
end
end


function format_bars(b, colors)
b(1).FaceColor = colors.Blue;
b(1).EdgeColor = colors.Blue * 0.72;
b(1).LineWidth = 1.0;
b(2).FaceColor = colors.Orange;
b(2).EdgeColor = colors.Orange * 0.72;
b(2).LineWidth = 1.0;
end


function add_range_bars(ax, b, means, lows, highs, colors)
for j = 1:numel(b)
    errorbar(ax, b(j).XEndPoints, means(:, j), lows(:, j), highs(:, j), ...
        "LineStyle", "none", "Color", colors.Text, "LineWidth", 1.15, ...
        "CapSize", 7, "HandleVisibility", "off");
end
end


function handle = plot_band(ax, x, values, color, marker, label)
lo = min(values, [], 2)';
hi = max(values, [], 2)';
meanValues = mean(values, 2, "omitnan")';
fill(ax, [x fliplr(x)], [lo fliplr(hi)], color, ...
    "FaceAlpha", 0.13, "EdgeColor", "none", "HandleVisibility", "off");
handle = plot(ax, x, meanValues, "Color", color, "Marker", marker, ...
    "MarkerFaceColor", "white", "MarkerSize", 4.8, "LineWidth", 1.9, ...
    "DisplayName", label);
end


function write_thesis_summary(summary, scopes, shiftVariants, anchorVariants, outputPath)
metrics = ["displacement_step_magnitude_nm", "displacement_within_grid_nm", ...
    "displacement_command_abs_error_nm"];
rows = table();
for pairName = ["Anti-aliased vs standard", "Raw-position anchor"]
    if pairName == "Anti-aliased vs standard"
        variants = shiftVariants;
    else
        variants = anchorVariants;
    end
    for metric = metrics
        for scope = scopes
            values = nan(1, 2);
            for v = 1:2
                part = summary(summary.metric == metric & summary.stratum == scope & ...
                    summary.variant == variants(v), :);
                assert(height(part) == 2, "Missing two-seed ablation summary.");
                values(v) = mean(part.value, "omitnan");
            end
            row = table(pairName, metric, scope, variants(1), values(1), ...
                variants(2), values(2), values(2) - values(1), ...
                100 * (values(2) - values(1)) / values(1), ...
                'VariableNames', {'comparison', 'metric', 'stratum', ...
                'reference_variant', 'reference_mean_nm', 'comparison_variant', ...
                'comparison_mean_nm', 'comparison_minus_reference_nm', ...
                'comparison_minus_reference_pct'});
            rows = [rows; row]; %#ok<AGROW>
        end
    end
end
writetable(rows, outputPath);
end


function f = compact_figure(widthIn, heightIn)
f = figure("Color", "white", "Units", "inches", ...
    "Position", [0.7 0.7 widthIn heightIn], "Renderer", "painters");
end


function style_axes(ax, colors)
ax.FontName = "Times New Roman";
ax.FontSize = 12.0;
ax.LineWidth = 1.15;
ax.TickDir = "out";
ax.TickLength = [0.012 0.012];
ax.Box = "off";
ax.XColor = colors.Text;
ax.YColor = colors.Text;
ax.YGrid = "on";
ax.XGrid = "off";
ax.GridColor = colors.Grid;
ax.GridAlpha = 1.0;
ax.Layer = "top";
end


function export_png_fig(f, outputBase)
drawnow;
exportgraphics(f, outputBase + ".png", "Resolution", 300, "BackgroundColor", "white");
savefig(f, outputBase + ".fig");
end


function ensure_dir(path)
if ~isfolder(path)
    mkdir(path);
end
end


function result = is_true(values)
result = ismember(lower(string(values)), ["true", "1"]);
end
