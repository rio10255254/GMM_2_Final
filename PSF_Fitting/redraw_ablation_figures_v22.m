function redraw_ablation_figures_v22()
% Redraw the thesis ablation figures with direct absolute comparisons.

evaluationRoot = "D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results\evaluation";
outputRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\08_V22_ABLATION_REDESIGN_20260727";
figureDir = fullfile(outputRoot, "figures");
tableDir = fullfile(outputRoot, "tables");
ensure_dir(outputRoot);
ensure_dir(figureDir);
ensure_dir(tableDir);

summaryPath = fullfile(evaluationRoot, "aggregate", "candidate_seed_summary.csv");
componentPath = fullfile(evaluationRoot, "aggregate", "component_effects.csv");
summary = readtable(summaryPath, "VariableNamingRule", "preserve", "TextType", "string");
components = readtable(componentPath, "VariableNamingRule", "preserve", "TextType", "string");

colors.Blue = [0.05 0.38 0.67];
colors.Orange = [0.82 0.42 0.12];
colors.Gray = [0.42 0.42 0.42];
colors.Grid = [0.86 0.86 0.86];
colors.Text = [0.18 0.18 0.18];

scopes = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um", "all_sequences"];
scopeLabels = ["50倍 0.5 µm", "50倍 1.0 µm", "20倍 0.5 µm", "20倍 1.0 µm", "四序列合併"];

within = select_summary(summary, "displacement_within_grid_nm", scopes);
writetable(within, fullfile(tableDir, "01_shift_safe_within_grid_source.csv"));
plot_absolute_architecture(within, scopes, scopeLabels, ...
    "九顆pillar位移離散度 (nm)", [0 14], colors, ...
    fullfile(figureDir, "01_shift_safe_within_grid_absolute"));

command = select_summary(summary, "displacement_command_abs_error_nm", scopes);
writetable(command, fullfile(tableDir, "02_shift_safe_command_mae_source.csv"));
plot_absolute_architecture(command, scopes, scopeLabels, ...
    "相對PI平台回授的平均絕對偏差 (nm)", [0 14], colors, ...
    fullfile(figureDir, "02_shift_safe_command_mae_absolute"));

anchorDisplacement = select_anchor_displacement(summary, scopes);
writetable(anchorDisplacement, fullfile(tableDir, "03_raw_anchor_displacement_source.csv"));
plot_raw_anchor_displacement(anchorDisplacement, scopes, scopeLabels, colors, ...
    fullfile(figureDir, "03_raw_anchor_displacement_both_metrics"));

anchorEffects = components(components.component == "raw_position_anchor" & ...
    ismember(components.stratum, ["50x", "20x"]) & ...
    ismember(components.metric, ["cd_median_abs_error_nm", ...
    "edge_width_10_90_nm", "outer_ringing_energy"]), :);
writetable(anchorEffects, fullfile(tableDir, "04_raw_anchor_effects_source.csv"));
plot_raw_anchor_tradeoff(anchorEffects, colors, ...
    fullfile(figureDir, "04_raw_anchor_tradeoff_both_magnifications"));

perPillar = collect_raw_anchor_per_pillar(evaluationRoot);
writetable(perPillar, fullfile(tableDir, "05_raw_anchor_per_pillar_source.csv"));
plot_raw_anchor_per_pillar(perPillar, colors, ...
    fullfile(figureDir, "05_raw_anchor_per_pillar_both_magnifications"));

metadata.generated_at = char(datetime("now", "Format", "yyyy-MM-dd HH:mm:ss"));
metadata.source_summary = summaryPath;
metadata.source_component_effects = componentPath;
metadata.figure_count = 5;
metadata.note = "All bars and lines use the two fixed-initialization ablation outputs; no values were visually rescaled or selectively omitted.";
fid = fopen(fullfile(outputRoot, "analysis_metadata.json"), "w", "n", "UTF-8");
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, "%s", jsonencode(metadata, "PrettyPrint", true));
end


function selected = select_anchor_displacement(summary, scopes)
selected = summary(ismember(summary.variant, ["full_control", "no_raw_position_anchor"]) & ...
    ismember(summary.metric, ["displacement_within_grid_nm", ...
    "displacement_command_abs_error_nm"]) & ismember(summary.stratum, scopes), :);
selected.variant = categorical(selected.variant, ...
    ["full_control", "no_raw_position_anchor"], ...
    ["Full model", "Without Raw-position anchor"]);
end


function plot_raw_anchor_displacement(data, scopes, scopeLabels, colors, outputBase)
metrics = ["displacement_within_grid_nm", "displacement_command_abs_error_nm"];
yLabels = ["九顆pillar位移離散度 (nm)", "相對PI平台回授的平均絕對偏差 (nm)"];
panelLabels = ["(a)", "(b)"];
variants = ["Full model", "Without Raw-position anchor"];

f = compact_figure(7.4, 6.4);
layout = tiledlayout(f, 2, 1, "TileSpacing", "compact", "Padding", "compact");
handles = gobjects(1, 2);
for k = 1:2
    ax = nexttile(layout, k);
    hold(ax, "on");
    means = nan(numel(scopes), 2);
    lows = nan(numel(scopes), 2);
    highs = nan(numel(scopes), 2);
    for i = 1:numel(scopes)
        for j = 1:2
            mask = data.metric == metrics(k) & data.stratum == scopes(i) & ...
                string(data.variant) == variants(j);
            values = data.value(mask);
            means(i, j) = mean(values, "omitnan");
            lows(i, j) = means(i, j) - min(values);
            highs(i, j) = max(values) - means(i, j);
        end
    end
    b = bar(ax, means, "grouped", "BarWidth", 0.78);
    b(1).FaceColor = colors.Blue;
    b(1).EdgeColor = colors.Blue * 0.72;
    b(1).LineWidth = 1.0;
    b(2).FaceColor = colors.Orange;
    b(2).EdgeColor = colors.Orange * 0.72;
    b(2).LineWidth = 1.0;
    handles = b;
    for j = 1:2
        x = b(j).XEndPoints;
        errorbar(ax, x, means(:, j), lows(:, j), highs(:, j), ...
            "LineStyle", "none", "Color", colors.Text, "LineWidth", 1.15, ...
            "CapSize", 7, "HandleVisibility", "off");
        for i = 1:numel(x)
            if j == 1
                labelX = x(i) - 0.035;
                labelAlign = "right";
            else
                labelX = x(i) + 0.035;
                labelAlign = "left";
            end
            text(ax, labelX, means(i, j) + highs(i, j) + 0.22, ...
                sprintf("%.2f", means(i, j)), "HorizontalAlignment", labelAlign, ...
                "VerticalAlignment", "bottom", "FontSize", 11.0, ...
                "FontName", "Times New Roman", "Color", colors.Text);
        end
    end
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
lgd = legend(handles, ["完整模型", "移除Raw位置錨定"], ...
    "Orientation", "horizontal", "Box", "off", "FontSize", 12.5);
lgd.Layout.Tile = "north";
export_all(f, outputBase);
close(f);
end


function selected = select_summary(summary, metric, scopes)
selected = summary(ismember(summary.variant, ["shift_safe_matched", "standard_upsample_matched"]) & ...
    summary.metric == metric & ismember(summary.stratum, scopes), :);
selected.variant = categorical(selected.variant, ...
    ["shift_safe_matched", "standard_upsample_matched"], ...
    ["Anti-aliased upsampling", "Standard upsampling"]);
end


function plot_absolute_architecture(data, scopes, scopeLabels, yLabel, yLimits, colors, outputBase)
variants = ["Anti-aliased upsampling", "Standard upsampling"];
means = nan(numel(scopes), 2);
lows = nan(numel(scopes), 2);
highs = nan(numel(scopes), 2);
for i = 1:numel(scopes)
    for j = 1:numel(variants)
        mask = data.stratum == scopes(i) & string(data.variant) == variants(j);
        values = data.value(mask);
        means(i, j) = mean(values, "omitnan");
        lows(i, j) = means(i, j) - min(values);
        highs(i, j) = max(values) - means(i, j);
    end
end

f = compact_figure(7.4, 4.7);
ax = axes(f);
hold(ax, "on");
b = bar(ax, means, "grouped", "BarWidth", 0.78);
b(1).FaceColor = colors.Blue;
b(1).EdgeColor = colors.Blue * 0.72;
b(1).LineWidth = 1.0;
b(2).FaceColor = colors.Orange;
b(2).EdgeColor = colors.Orange * 0.72;
b(2).LineWidth = 1.0;

for j = 1:2
    x = b(j).XEndPoints;
    errorbar(ax, x, means(:, j), lows(:, j), highs(:, j), ...
        "LineStyle", "none", "Color", colors.Text, "LineWidth", 1.15, ...
        "CapSize", 7, "HandleVisibility", "off");
    for i = 1:numel(x)
        if j == 1
            labelX = x(i) - 0.035;
            labelAlign = "right";
        else
            labelX = x(i) + 0.035;
            labelAlign = "left";
        end
        text(ax, labelX, means(i, j) + highs(i, j) + 0.25, ...
            sprintf("%.2f", means(i, j)), "HorizontalAlignment", labelAlign, ...
            "VerticalAlignment", "bottom", "FontSize", 11.5, ...
            "FontName", "Times New Roman", "Color", colors.Text);
    end
end

xticks(ax, 1:numel(scopes));
xticklabels(ax, scopeLabels);
xtickangle(ax, 0);
xlim(ax, [0.45 numel(scopes) + 0.55]);
ylim(ax, yLimits);
ylabel(ax, yLabel);
legend(ax, [b(1), b(2)], ["抗混疊上取樣", "一般上取樣"], ...
    "Location", "northoutside", "Orientation", "horizontal", "Box", "off", ...
    "FontSize", 12.5);
style_axes(ax, colors);
export_all(f, outputBase);
close(f);
end


function plot_raw_anchor_tradeoff(data, colors, outputBase)
magnifications = ["50x", "20x"];
metrics = ["cd_median_abs_error_nm", "edge_width_10_90_nm", "outer_ringing_energy"];
labels = ["CD中位絕對誤差", "10–90%邊緣寬度", "外圍振鈴能量"];
values = nan(2, 3);
for i = 1:numel(magnifications)
    for j = 1:numel(metrics)
        row = data(data.stratum == magnifications(i) & data.metric == metrics(j), :);
        assert(height(row) == 1, "Expected one raw-anchor effect row.");
        values(i, j) = row.effect_vs_full_pct;
    end
end

f = compact_figure(7.1, 4.9);
ax = axes(f);
hold(ax, "on");
b = bar(ax, values, "grouped", "BarWidth", 0.76);
barColors = [colors.Blue; colors.Gray; colors.Orange];
for j = 1:3
    b(j).FaceColor = barColors(j, :);
    b(j).EdgeColor = barColors(j, :) * 0.72;
    b(j).LineWidth = 1.0;
    for i = 1:2
        y = values(i, j);
        if y >= 0
            valign = "bottom";
            offset = 10;
        else
            valign = "top";
            offset = -10;
        end
        text(ax, b(j).XEndPoints(i), y + offset, sprintf("%+.1f%%", y), ...
            "HorizontalAlignment", "center", "VerticalAlignment", valign, ...
            "FontName", "Times New Roman", "FontSize", 11.5, ...
            "Color", colors.Text);
    end
end
yline(ax, 0, "-", "Color", colors.Text, "LineWidth", 1.2, "HandleVisibility", "off");
xticks(ax, 1:2);
xticklabels(ax, ["50倍", "20倍"]);
xlim(ax, [0.5 2.5]);
ylim(ax, [-125 440]);
ylabel(ax, "移除Raw位置錨定後的變化率 (%)");
legend(ax, b, labels, "Location", "northoutside", "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 12.0);
style_axes(ax, colors);
export_all(f, outputBase);
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
f = compact_figure(7.3, 6.5);
layout = tiledlayout(f, 2, 1, "TileSpacing", "compact", "Padding", "compact");
magnifications = ["50x", "20x"];
panelLabels = ["(a) 50倍", "(b) 20倍"];
lineHandles = gobjects(1, 2);

for m = 1:2
    ax = nexttile(layout, m);
    hold(ax, "on");
    part = data(data.magnification == magnifications(m), :);
    pillarIds = unique(part.pillar_id, "sorted");
    variants = ["full_control", "no_raw_position_anchor"];
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
        "MarkerSize", 6.7, "LineWidth", 2.25, "CapSize", 7);
    lineHandles(2) = errorbar(ax, 1:numel(pillarIds), means(:, 2), spreads(:, 2), ...
        "-s", "Color", colors.Orange, "MarkerFaceColor", "white", ...
        "MarkerSize", 6.7, "LineWidth", 2.25, "CapSize", 7);
    xticks(ax, 1:numel(pillarIds));
    xticklabels(ax, "P" + string(pillarIds));
    xlim(ax, [0.65 numel(pillarIds) + 0.35]);
    if m == 1
        ylim(ax, [0 150]);
    else
        ylim(ax, [0 350]);
    end
    ylabel(ax, "CD絕對誤差中位數 (nm)");
    text(ax, 0.02, 0.92, panelLabels(m), "Units", "normalized", ...
        "HorizontalAlignment", "left", "VerticalAlignment", "top", ...
        "FontName", "Microsoft JhengHei", "FontSize", 13.0, ...
        "FontWeight", "bold", "Color", colors.Text);
    style_axes(ax, colors);
end
xlabel(layout, "SEM pillar編號", "FontName", "Microsoft JhengHei", "FontSize", 13.5);
lgd = legend(lineHandles, ["完整模型", "移除Raw位置錨定"], ...
    "Orientation", "horizontal", "Box", "off", "FontSize", 12.5);
lgd.Layout.Tile = "north";
export_all(f, outputBase);
close(f);
end


function f = compact_figure(widthIn, heightIn)
f = figure("Color", "white", "Units", "inches", ...
    "Position", [0.7 0.7 widthIn heightIn], "Renderer", "painters");
end


function style_axes(ax, colors)
ax.FontName = "Microsoft JhengHei";
ax.FontSize = 12.5;
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


function export_all(f, outputBase)
exportgraphics(f, outputBase + ".png", "Resolution", 300, "BackgroundColor", "white");
exportgraphics(f, outputBase + ".pdf", "ContentType", "vector", "BackgroundColor", "white");
savefig(f, outputBase + ".fig");
end


function ensure_dir(path)
if ~isfolder(path)
    mkdir(path);
end
end
