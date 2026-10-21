function plot_isocontour_reanalysis()
root = "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\06_DISPLACEMENT_EXPERIMENTS_ISOCONTOUR_20260724";
fontName = "Microsoft JhengHei";
set(groot, "defaultAxesFontName", fontName);
set(groot, "defaultTextFontName", fontName);
set(groot, "defaultLegendFontName", fontName);
set(groot, "defaultAxesFontSize", 11);
set(groot, "defaultTextFontSize", 11);
set(groot, "defaultLineLineWidth", 1.65);

colors.Raw = [0.66 0.31 0.15];
colors.Wiener = [0.81 0.51 0.05];
colors.MOSR = [0.05 0.38 0.67];
colors.Control = [0.05 0.38 0.67];
colors.Ablated = [0.82 0.42 0.12];
colors.Geometry = [0.42 0.34 0.61];
colors.Motion = [0.78 0.49 0.08];
colors.Reference = [0.25 0.25 0.25];
colors.Grid = [0.86 0.86 0.86];

plot_improvement(root, colors);
plot_ablation(root, colors);
end


function plot_improvement(root, colors)
base = fullfile(root, "01_displacement_improvement");
tablesDir = fullfile(base, "tables");
figDir = fullfile(base, "figures_matlab");
ensure_dir(figDir);
steps = readtable(fullfile(tablesDir, "displacement_per_step.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
steps.common_valid = ismember(lower(string(steps.common_valid)), ["true", "1"]);
summary = readtable(fullfile(tablesDir, "displacement_summary_by_sequence.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
pooled = readtable(fullfile(tablesDir, "displacement_summary_by_magnification.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");

sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
sequenceLabels = ["50倍，0.5 µm", "50倍，1.0 µm", "20倍，0.5 µm", "20倍，1.0 µm"];
methods = ["Raw", "Wiener", "MOSR"];
methodLabels = ["Raw", "Wiener", "MOSR"];
methodColors = [colors.Raw; colors.Wiener; colors.MOSR];
markers = ["s", "^", "o"];

figureNumber = 1;
for morphology = "pillar"
    for s = 1:numel(sequences)
        mask = steps.morphology == morphology & steps.sequence == sequences(s) & steps.common_valid == 1;
        subset = steps(mask, :);
        f = new_figure();
        hold on;
        reference = 1000 * subset.reference_step_um(1);
        yline(reference, "--", ...
            "Color", colors.Reference, "LineWidth", 1.35, ...
            "DisplayName", "PI平台實際回授位移");
        for m = 1:numel(methods)
            part = subset(subset.method == methods(m), :);
            part = sortrows(part, "end_frame_index");
            plot(1:height(part), 1000 * part.measured_step_um, ...
                "Color", methodColors(m, :), "Marker", markers(m), ...
                "MarkerSize", 4.7, "MarkerFaceColor", "white", ...
                "DisplayName", methodLabels(m));
        end
        xlabel("步次");
        ylabel("量測位移幅度 (nm)");
        xlim([1 30]);
        xticks([1 5 10 15 20 25 30]);
        style_axes(colors.Grid);
        legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
        name = sprintf("%02d_pillar_%s_trajectory", figureNumber, char(sequences(s)));
        export_figure(f, figDir, name);
        figureNumber = figureNumber + 1;
    end
end

metricSpecs = {
    "mae_nm", "位移平均絕對誤差 (nm)", "sequence_mae";
    "step_sd_nm", "逐步位移標準差 (nm)", "sequence_step_sd";
    "mean_within_grid_mad_nm", "九顆結構位移離散度 (nm)", "sequence_within_grid";
    "median_threshold_sensitivity_nm", "跨門檻位移敏感度 (nm)", "sequence_threshold_sensitivity"
};
for morphology = "pillar"
    for k = 1:size(metricSpecs, 1)
        values = nan(numel(sequences), numel(methods));
        for s = 1:numel(sequences)
            for m = 1:numel(methods)
                row = summary(summary.morphology == morphology & ...
                    summary.sequence == sequences(s) & summary.method == methods(m), :);
                values(s, m) = row.(metricSpecs{k, 1})(1);
            end
        end
        f = grouped_bar(values, sequenceLabels, methodLabels, methodColors, ...
            metricSpecs{k, 2}, colors.Grid);
        name = sprintf("%02d_%s_%s", figureNumber, char(morphology), metricSpecs{k, 3});
        export_figure(f, figDir, name);
        figureNumber = figureNumber + 1;
    end
end

for morphology = "pillar"
    for metric = ["mae_nm", "mean_within_grid_mad_nm"]
        values = nan(2, numel(methods));
        mags = ["50x", "20x"];
        for a = 1:2
            for m = 1:numel(methods)
                row = pooled(pooled.morphology == morphology & pooled.magnification == mags(a) & ...
                    pooled.method == methods(m), :);
                values(a, m) = row.(metric)(1);
            end
        end
        if metric == "mae_nm"
            yLabel = "位移平均絕對誤差 (nm)";
            suffix = "pooled_mae";
        else
            yLabel = "九顆結構位移離散度 (nm)";
            suffix = "pooled_within_grid";
        end
        f = grouped_bar(values, ["50倍", "20倍"], methodLabels, methodColors, yLabel, colors.Grid);
        name = sprintf("%02d_%s_%s", figureNumber, char(morphology), suffix);
        export_figure(f, figDir, name);
        figureNumber = figureNumber + 1;
    end
end
end


function plot_ablation(root, colors)
base = fullfile(root, "02_ablation");
tablesDir = fullfile(base, "tables");
figDir = fullfile(base, "figures_matlab");
ensure_dir(figDir);
steps = readtable(fullfile(tablesDir, "ablation_displacement_per_step.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
steps.common_valid = ismember(lower(string(steps.common_valid)), ["true", "1"]);
effects = readtable(fullfile(tablesDir, "ablation_removal_effects.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");

sequenceScopes = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um", "all_sequences"];
sequenceLabels = ["50倍，0.5 µm", "50倍，1.0 µm", "20倍，0.5 µm", "20倍，1.0 µm", "四序列合併"];
figureNumber = 1;

for metric = ["within_grid_nm", "step_sd_nm"]
    part = effects(effects.comparison == "shift_safe_upsampling" & ...
        effects.metric == metric & ismember(effects.scope, sequenceScopes), :);
    [part, order] = order_scope(part, sequenceScopes);
    if metric == "within_grid_nm"
        yLabel = "一般上取樣相對抗混疊上取樣之離散度增加量 (nm)";
        suffix = "shift_safe_within_grid_penalty";
    else
        yLabel = "一般上取樣相對抗混疊上取樣之標準差增加量 (nm)";
        suffix = "shift_safe_step_sd_penalty";
    end
    f = interval_figure(part.mean_removal_penalty(order), ...
        part.bootstrap_ci_low(order), part.bootstrap_ci_high(order), ...
        sequenceLabels, yLabel, colors.Ablated, colors.Grid);
    export_figure(f, figDir, sprintf("%02d_%s", figureNumber, suffix));
    figureNumber = figureNumber + 1;
end

primaryComparisons = ["geometry_anchor", "motion_consistency", ...
    "raw_position_anchor", "shift_safe_upsampling"];
primaryLabels = ["幾何錨定", "位移一致性", "Raw位置錨定", "抗混疊上取樣"];
for metric = ["step_sd_nm", "within_grid_nm"]
    part = effects(effects.scope == "all_sequences" & effects.metric == metric & ...
        ismember(effects.comparison, primaryComparisons), :);
    [part, order] = order_scope(part, primaryComparisons, "comparison");
    if metric == "step_sd_nm"
        yLabel = "移除或替換後的標準差變化 (nm)";
        suffix = "primary_mechanisms_step_sd";
    else
        yLabel = "移除或替換後的九宮格離散度變化 (nm)";
        suffix = "primary_mechanisms_within_grid";
    end
    f = interval_figure(part.mean_removal_penalty(order), ...
        part.bootstrap_ci_low(order), part.bootstrap_ci_high(order), ...
        primaryLabels, yLabel, colors.Geometry, colors.Grid);
    export_figure(f, figDir, sprintf("%02d_%s", figureNumber, suffix));
    figureNumber = figureNumber + 1;
end

motionComparisons = ["adjacent_frame_consistency", "known_shift_motion", "shift_equivariance"];
motionLabels = ["相鄰影格一致性", "已知位移監督", "平移等變限制"];
for metric = ["step_sd_nm", "within_grid_nm"]
    part = effects(effects.scope == "all_sequences" & effects.metric == metric & ...
        ismember(effects.comparison, motionComparisons), :);
    [part, order] = order_scope(part, motionComparisons, "comparison");
    if metric == "step_sd_nm"
        yLabel = "移除後的標準差變化 (nm)";
        suffix = "motion_components_step_sd";
    else
        yLabel = "移除後的九宮格離散度變化 (nm)";
        suffix = "motion_components_within_grid";
    end
    f = interval_figure(part.mean_removal_penalty(order), ...
        part.bootstrap_ci_low(order), part.bootstrap_ci_high(order), ...
        motionLabels, yLabel, colors.Motion, colors.Grid);
    export_figure(f, figDir, sprintf("%02d_%s", figureNumber, suffix));
    figureNumber = figureNumber + 1;
end

boundaryComparisons = ["shape_geometry", "global_boundary_position", ...
    "identity_boundary_guard", "region_boundary_teacher", ...
    "boundary_residual_adapter", "raw_position_anchor", "quality_gate"];
boundaryLabels = ["形狀幾何", "全域邊界位置", "低偏差邊界保護", ...
    "邊界區域教師", "邊界殘差分支", "Raw位置錨定", "品質調節"];
for metric = ["within_grid_nm", "threshold_sensitivity_nm"]
    part = effects(effects.scope == "all_sequences" & effects.metric == metric & ...
        ismember(effects.comparison, boundaryComparisons), :);
    [part, order] = order_scope(part, boundaryComparisons, "comparison");
    if metric == "within_grid_nm"
        yLabel = "移除後的九宮格離散度變化 (nm)";
        suffix = "boundary_components_within_grid";
    else
        yLabel = "移除後的跨門檻敏感度變化 (nm)";
        suffix = "boundary_components_threshold_sensitivity";
    end
    f = interval_figure(part.mean_removal_penalty(order), ...
        part.bootstrap_ci_low(order), part.bootstrap_ci_high(order), ...
        boundaryLabels, yLabel, colors.Geometry, colors.Grid);
    export_figure(f, figDir, sprintf("%02d_%s", figureNumber, suffix));
    figureNumber = figureNumber + 1;
end

for comparison = ["geometry_anchor", "motion_consistency", "raw_position_anchor"]
    for metric = ["step_sd_nm", "within_grid_nm"]
        part = effects(effects.comparison == comparison & effects.metric == metric & ...
            ismember(effects.scope, sequenceScopes), :);
        [part, order] = order_scope(part, sequenceScopes);
        if metric == "step_sd_nm"
            yLabel = "移除後的標準差變化 (nm)";
            metricSuffix = "step_sd";
        else
            yLabel = "移除後的九宮格離散度變化 (nm)";
            metricSuffix = "within_grid";
        end
        f = interval_figure(part.mean_removal_penalty(order), ...
            part.bootstrap_ci_low(order), part.bootstrap_ci_high(order), ...
            sequenceLabels, yLabel, colors.Ablated, colors.Grid);
        export_figure(f, figDir, sprintf("%02d_%s_%s", ...
            figureNumber, char(comparison), metricSuffix));
        figureNumber = figureNumber + 1;
    end
end

sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
trajectoryPairs = {
    "shift_safe_matched", "standard_upsample_matched", "抗混疊上取樣", "一般上取樣", "upsampling";
    "full_control", "no_raw_position_anchor", "完整模型", "移除Raw位置錨定", "raw_anchor"
};
for pairIndex = 1:size(trajectoryPairs, 1)
    control = trajectoryPairs{pairIndex, 1};
    ablated = trajectoryPairs{pairIndex, 2};
    controlLabel = trajectoryPairs{pairIndex, 3};
    ablatedLabel = trajectoryPairs{pairIndex, 4};
    suffix = trajectoryPairs{pairIndex, 5};
    for s = 1:numel(sequences)
        subset = steps(steps.sequence == sequences(s) & ...
            ismember(steps.variant, [string(control), string(ablated)]) & steps.common_valid == 1, :);
        f = new_figure();
        hold on;
        reference = 1000 * subset.reference_step_um(1);
        yline(reference, "--", ...
            "Color", colors.Reference, "LineWidth", 1.35, ...
            "DisplayName", "PI平台實際回授位移");
        plot_seed_mean(subset, control, controlLabel, colors.Control, "o");
        plot_seed_mean(subset, ablated, ablatedLabel, colors.Ablated, "s");
        xlabel("步次");
        ylabel("量測位移幅度 (nm)");
        xlim([1 30]);
        xticks([1 5 10 15 20 25 30]);
        style_axes(colors.Grid);
        legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
        export_figure(f, figDir, sprintf("%02d_%s_%s_trajectory", ...
            figureNumber, suffix, char(sequences(s))));
        figureNumber = figureNumber + 1;
    end
end
end


function plot_seed_mean(subset, variant, displayName, color, marker)
part = subset(subset.variant == string(variant), :);
frames = unique(part.end_frame_index);
frames = sort(frames);
values = nan(numel(frames), 1);
for i = 1:numel(frames)
    values(i) = mean(1000 * part.measured_step_um(part.end_frame_index == frames(i)));
end
plot(1:numel(frames), values, "Color", color, "Marker", marker, ...
    "MarkerSize", 5, "MarkerFaceColor", "white", "DisplayName", displayName);
end


function [part, order] = order_scope(part, desired, variable)
if nargin < 3
    variable = "scope";
end
order = zeros(numel(desired), 1);
for i = 1:numel(desired)
    idx = find(part.(variable) == desired(i), 1);
    if isempty(idx)
        error("Missing %s value %s", variable, desired(i));
    end
    order(i) = idx;
end
end


function f = interval_figure(values, low, high, labels, yLabel, color, gridColor)
f = new_figure();
hold on;
x = 1:numel(values);
errorbar(x, values, values - low, high - values, "o", ...
    "Color", color, "MarkerFaceColor", "white", "MarkerSize", 6, ...
    "CapSize", 8, "LineWidth", 1.5);
yline(0, "-", "Color", [0.25 0.25 0.25], "LineWidth", 1.05);
xlim([0.5 numel(values) + 0.5]);
xticks(x);
xticklabels(labels);
xtickangle(18);
ylabel(yLabel);
style_axes(gridColor);
end


function f = grouped_bar(values, labels, legendLabels, barColors, yLabel, gridColor)
f = new_figure();
b = bar(values, "grouped", "BarWidth", 0.78);
for i = 1:numel(b)
    b(i).FaceColor = barColors(i, :);
    b(i).EdgeColor = barColors(i, :) * 0.75;
    b(i).LineWidth = 0.8;
end
xticks(1:numel(labels));
xticklabels(labels);
ylabel(yLabel);
style_axes(gridColor);
legend(legendLabels, "Location", "northoutside", ...
    "Orientation", "horizontal", "Box", "off");
end


function f = new_figure()
f = figure("Color", "white", "Position", [80 80 920 580], ...
    "Renderer", "painters");
end


function style_axes(gridColor)
ax = gca;
ax.Box = "off";
ax.LineWidth = 1.05;
ax.TickDir = "out";
ax.XColor = [0.20 0.20 0.20];
ax.YColor = [0.20 0.20 0.20];
ax.GridColor = gridColor;
ax.GridAlpha = 1;
grid on;
ax.XMinorGrid = "off";
ax.YMinorGrid = "off";
end


function export_figure(f, figDir, name)
drawnow;
exportgraphics(f, fullfile(figDir, name + ".png"), "Resolution", 300);
exportgraphics(f, fullfile(figDir, name + ".pdf"), "ContentType", "vector");
savefig(f, fullfile(figDir, name + ".fig"));
close(f);
end


function ensure_dir(path)
if ~exist(path, "dir")
    mkdir(path);
end
end
