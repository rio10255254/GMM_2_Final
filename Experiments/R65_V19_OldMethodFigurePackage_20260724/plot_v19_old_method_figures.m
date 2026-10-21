function plot_v19_old_method_figures()
% V19 thesis figure package using the original maximum-gradient displacement method.

outputRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\07_V19_OLD_METHOD_FIGURE_PACKAGE_20260724";
experimentRoot = "D:\GMM_2_Final\Experiments\R63_CausalBoundaryMotionAblation\results\evaluation";
neuralRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS";
modernRoot = fullfile(neuralRoot, "modern_baseline_three_morphology_20260719");

dirs.displacement = fullfile(outputRoot, "01_displacement_improvement");
dirs.ablation = fullfile(outputRoot, "02_ablation");
dirs.models = fullfile(outputRoot, "03_model_comparison");
dirs.retained = fullfile(outputRoot, "04_retained_existing");
dirs.qa = fullfile(outputRoot, "99_qa");
names = fieldnames(dirs);
for i = 1:numel(names)
    ensure_dir(dirs.(names{i}));
end

set(groot, "defaultAxesFontName", "Microsoft JhengHei");
set(groot, "defaultTextFontName", "Microsoft JhengHei");
set(groot, "defaultLegendFontName", "Microsoft JhengHei");
set(groot, "defaultAxesFontSize", 10.5);
set(groot, "defaultTextFontSize", 10.5);
set(groot, "defaultLineLineWidth", 1.6);

colors.Raw = [0.66 0.31 0.15];
colors.Wiener = [0.81 0.51 0.05];
colors.NAFNet = [0.88 0.48 0.08];
colors.EDSR = [0.45 0.37 0.67];
colors.MOSR = [0.05 0.38 0.67];
colors.Reference = [0.35 0.35 0.35];
colors.ShiftSafe = [0.05 0.38 0.67];
colors.Standard = [0.82 0.42 0.12];
colors.Grid = [0.86 0.86 0.86];

plot_displacement_improvement(neuralRoot, dirs.displacement, colors);
plot_ablation(experimentRoot, dirs.ablation, colors);
plot_model_comparison(modernRoot, dirs.models, colors);
copy_retained_figures(neuralRoot, dirs.retained);

write_package_manifest(outputRoot);
end


function plot_displacement_improvement(neuralRoot, outputDir, colors)
tablesDir = fullfile(neuralRoot, "tables");
steps = readtable(fullfile(tablesDir, "displacement_three_way_per_step.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
summary = readtable(fullfile(tablesDir, "displacement_three_way_summary.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");

sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
for s = 1:numel(sequences)
    part = steps(steps.sequence == sequences(s), :);
    part = sortrows(part, "end_frame_index");
    f = new_figure();
    hold on;
    reference = 1000 * part.nominal_step_um(1);
    yline(reference, "--", "Color", colors.Reference, "LineWidth", 1.3, ...
        "DisplayName", "PI平台實際回授位移");
    plot(1:height(part), 1000 * abs(part.raw_boundary_dx_um), "-s", ...
        "Color", colors.Raw, "MarkerFaceColor", "white", "MarkerSize", 4.6, ...
        "DisplayName", "Raw");
    plot(1:height(part), 1000 * abs(part.wiener_boundary_dx_um), "-^", ...
        "Color", colors.Wiener, "MarkerFaceColor", colors.Wiener, "MarkerSize", 4.8, ...
        "DisplayName", "Wiener");
    plot(1:height(part), 1000 * abs(part.v42_boundary_dx_um), "-o", ...
        "Color", colors.MOSR, "MarkerFaceColor", colors.MOSR, "MarkerSize", 4.6, ...
        "DisplayName", "MOSR");
    xlabel("步次");
    ylabel("量測位移幅度 (nm)");
    xlim([1 30]);
    xticks([1 5 10 15 20 25 30]);
    style_axes(colors.Grid);
    legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
    export_figure(f, outputDir, sprintf("%02d_%s_step_trace", s, char(sequences(s))));
end

methodLabels = ["Raw", "Wiener", "MOSR"];
methodColors = [colors.Raw; colors.Wiener; colors.MOSR];
categoryLabels = ["50倍，0.5 µm", "50倍，1.0 µm", "20倍，0.5 µm", "20倍，1.0 µm"];

mae = [summary.raw_command_mae_nm, summary.wiener_command_mae_nm, summary.v42_command_mae_nm];
f = grouped_bar(mae, categoryLabels, methodLabels, methodColors, ...
    "位移平均絕對誤差 (nm)", colors.Grid);
export_figure(f, outputDir, "05_sequence_displacement_mae");

stepSd = [summary.raw_step_sd_nm, summary.wiener_step_sd_nm, summary.v42_step_sd_nm];
f = grouped_bar(stepSd, categoryLabels, methodLabels, methodColors, ...
    "逐步位移標準差 (nm)", colors.Grid);
export_figure(f, outputDir, "06_sequence_step_sd");

within = [summary.raw_within_mean_nm, summary.wiener_within_mean_nm, summary.v42_within_mean_nm];
f = grouped_bar(within, categoryLabels, methodLabels, methodColors, ...
    "九顆pillar位移離散度 (nm)", colors.Grid);
export_figure(f, outputDir, "07_sequence_within_grid");
end


function plot_ablation(experimentRoot, outputDir, colors)
aggregateDir = fullfile(experimentRoot, "aggregate");
architecture = readtable(fullfile(aggregateDir, "architecture_effects.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
components = readtable(fullfile(aggregateDir, "component_effects.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");

scopes = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um", "all_sequences"];
scopeLabels = ["50倍，0.5 µm", "50倍，1.0 µm", "20倍，0.5 µm", "20倍，1.0 µm", "四序列合併"];

part = architecture(architecture.metric == "displacement_within_grid_nm" & ...
    architecture.comparison == "standard_minus_shift_safe", :);
part = order_rows(part, "stratum", scopes);
f = interval_figure(part.mean_standard_penalty, part.bootstrap_ci_low, ...
    part.bootstrap_ci_high, scopeLabels, ...
    "一般上取樣造成的九宮格離散度增加量 (nm)", colors.Standard, colors.Grid);
export_figure(f, outputDir, "01_shift_safe_within_grid_effect");

part = architecture(architecture.metric == "displacement_command_abs_error_nm" & ...
    architecture.comparison == "standard_minus_shift_safe", :);
part = order_rows(part, "stratum", scopes);
f = interval_figure(part.mean_standard_penalty, part.bootstrap_ci_low, ...
    part.bootstrap_ci_high, scopeLabels, ...
    "一般上取樣造成的位移誤差增加量 (nm)", colors.Standard, colors.Grid);
export_figure(f, outputDir, "02_shift_safe_mae_effect");

sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
for s = 1:numel(sequences)
    [frameIds, shiftValues] = load_variant_seed_series( ...
        experimentRoot, "shift_safe_matched", sequences(s));
    [standardIds, standardValues] = load_variant_seed_series( ...
        experimentRoot, "standard_upsample_matched", sequences(s));
    common = intersect(frameIds, standardIds, "stable");
    [~, ia] = ismember(common, frameIds);
    [~, ib] = ismember(common, standardIds);
    shiftValues = shiftValues(ia, :);
    standardValues = standardValues(ib, :);
    [common, order] = sort(common);
    shiftValues = shiftValues(order, :);
    standardValues = standardValues(order, :);

    f = new_figure();
    hold on;
    nominal = 500;
    if contains(sequences(s), "1um")
        nominal = 1000;
    end
    yline(nominal, "--", "Color", colors.Reference, "LineWidth", 1.3, ...
        "DisplayName", "PI平台實際回授位移");
    plot_band(1:numel(common), shiftValues, colors.ShiftSafe, "o", "抗混疊上取樣");
    plot_band(1:numel(common), standardValues, colors.Standard, "s", "一般上取樣");
    xlabel("步次");
    ylabel("量測位移幅度 (nm)");
    xlim([1 30]);
    xticks([1 5 10 15 20 25 30]);
    style_axes(colors.Grid);
    legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
    export_figure(f, outputDir, sprintf("%02d_%s_upsampling_step_trace", s + 2, char(sequences(s))));
end

rawAnchor = components(components.metric == "cd_median_abs_error_nm" & ...
    components.stratum == "20x" & components.component == "raw_position_anchor", :);
f = new_figure();
hold on;
errorbar(1, rawAnchor.mean_removal_penalty, ...
    rawAnchor.mean_removal_penalty - rawAnchor.bootstrap_ci_low, ...
    rawAnchor.bootstrap_ci_high - rawAnchor.mean_removal_penalty, "o", ...
    "Color", colors.Standard, "MarkerFaceColor", "white", ...
    "MarkerSize", 7, "CapSize", 12, "LineWidth", 1.6, ...
    "DisplayName", "平均值與95%區間");
scatter([0.92 1.08], [rawAnchor.effect_seed1261200 rawAnchor.effect_seed1261217], ...
    38, colors.MOSR, "filled", "DisplayName", "兩次訓練結果");
yline(0, "-", "Color", colors.Reference, "LineWidth", 1.0, ...
    "HandleVisibility", "off");
xlim([0.55 1.45]);
xticks(1);
xticklabels("20倍");
ylabel("移除Raw位置錨定後的CD誤差增加量 (nm)");
style_axes(colors.Grid);
legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
export_figure(f, outputDir, "07_raw_position_anchor_20x_cd_effect");

[pillarIds, fullValues, removedValues, fullSpread, removedSpread] = ...
    load_raw_anchor_per_pillar(experimentRoot);
f = new_figure();
hold on;
errorbar(1:numel(pillarIds), fullValues, fullSpread, "-o", ...
    "Color", colors.MOSR, "MarkerFaceColor", colors.MOSR, ...
    "MarkerSize", 4.8, "CapSize", 5, "DisplayName", "完整模型");
errorbar(1:numel(pillarIds), removedValues, removedSpread, "-s", ...
    "Color", colors.Standard, "MarkerFaceColor", "white", ...
    "MarkerSize", 4.8, "CapSize", 5, "DisplayName", "移除Raw位置錨定");
xlabel("SEM pillar編號");
ylabel("CD絕對誤差中位數 (nm)");
xticks(1:numel(pillarIds));
xticklabels(string(pillarIds));
style_axes(colors.Grid);
legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
export_figure(f, outputDir, "08_raw_position_anchor_20x_per_pillar_cd");
end


function plot_model_comparison(modernRoot, outputDir, colors)
stepsPath = fullfile(modernRoot, "tables", "displacement", "displacement_step_measurements.csv");
steps = readtable(stepsPath, "VariableNamingRule", "preserve", "TextType", "string");
steps = steps(ismember(steps.method, ["Raw", "NAFNet", "EDSR", "MOSR"]), :);

methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
methodLabels = ["Raw", "NAFNet", "EDSR-x1", "MOSR"];
methodColors = [colors.Raw; colors.NAFNet; colors.EDSR; colors.MOSR];
markers = ["s", "^", "d", "o"];
sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];

figureNumber = 1;
for morphology = ["pillar", "via"]
    for s = 1:numel(sequences)
        subset = steps(steps.morphology == morphology & steps.sequence == sequences(s), :);
        f = new_figure();
        hold on;
        nominal = 500;
        if contains(sequences(s), "1um")
            nominal = 1000;
        end
        yline(nominal, "--", "Color", colors.Reference, "LineWidth", 1.3, ...
            "DisplayName", "PI平台實際回授位移");
        for m = 1:numel(methods)
            part = subset(subset.method == methods(m), :);
            part = sortrows(part, "end_frame_index");
            plot(1:height(part), 1000 * abs(part.signed_step_um), ...
                "Color", methodColors(m, :), "Marker", markers(m), ...
                "MarkerSize", 4.2, "MarkerFaceColor", "white", ...
                "DisplayName", methodLabels(m));
        end
        xlabel("步次");
        ylabel("量測位移幅度 (nm)");
        xlim([1 30]);
        xticks([1 5 10 15 20 25 30]);
        style_axes(colors.Grid);
        legend("Location", "northoutside", "Orientation", "horizontal", "Box", "off");
        export_figure(f, outputDir, sprintf("%02d_%s_%s_model_step_trace", ...
            figureNumber, char(morphology), char(sequences(s))));
        figureNumber = figureNumber + 1;
    end
end

categories = ["50倍pillar", "20倍pillar", "50倍via", "20倍via"];
[maeValues, withinValues] = pooled_model_metrics(steps, methods);
f = grouped_bar(maeValues, categories, methodLabels, methodColors, ...
    "位移平均絕對誤差 (nm)", colors.Grid);
export_figure(f, outputDir, "09_model_displacement_mae");

f = grouped_bar(withinValues, categories, methodLabels, methodColors, ...
    "九顆結構位移離散度 (nm)", colors.Grid);
export_figure(f, outputDir, "10_model_within_grid");

sharpnessPath = fullfile(modernRoot, "tables", "circular_cd_sharpness", ...
    "circular_feature_method_summary.csv");
sharpness = readtable(sharpnessPath, "VariableNamingRule", "preserve", "TextType", "string");
edgeValues = nan(4, numel(methods));
categoryMorphology = ["pillar", "pillar", "via", "via"];
categoryMagnification = ["50x", "20x", "50x", "20x"];
for c = 1:4
    for m = 1:numel(methods)
        row = sharpness(sharpness.morphology == categoryMorphology(c) & ...
            sharpness.magnification == categoryMagnification(c) & ...
            sharpness.method == methods(m), :);
        edgeValues(c, m) = row.mean_edge_width_nm(1);
    end
end
f = grouped_bar(edgeValues, categories, methodLabels, methodColors, ...
    "平均邊界過渡寬度 (nm)", colors.Grid);
export_figure(f, outputDir, "11_model_edge_width");

runtimePath = fullfile(modernRoot, "tables", "runtime", "computational_performance.csv");
runtime = readtable(runtimePath, "VariableNamingRule", "preserve", "TextType", "string");
runtime = runtime(ismember(runtime.method, ["NAFNet", "EDSR", "MOSR"]), :);
runtime = order_rows(runtime, "method", ["NAFNet", "EDSR", "MOSR"]);
runtimeLabels = ["NAFNet", "EDSR-x1", "MOSR"];
runtimeColors = [colors.NAFNet; colors.EDSR; colors.MOSR];

f = simple_bar(runtime.full_median_ms / 1000, runtimeLabels, runtimeColors, ...
    "單張完整影像推論時間 (s)", colors.Grid, "%.2f");
export_figure(f, outputDir, "12_model_full_frame_runtime");

f = simple_bar(runtime.full_peak_gpu_memory_mb / 1024, runtimeLabels, runtimeColors, ...
    "完整影像峰值GPU記憶體 (GB)", colors.Grid, "%.2f");
export_figure(f, outputDir, "13_model_gpu_memory");

f = simple_bar(runtime.parameter_count / 1e6, runtimeLabels, runtimeColors, ...
    "模型參數量 (百萬)", colors.Grid, "%.2f");
export_figure(f, outputDir, "14_model_parameter_count");

unifiedCdRoot = fullfile(modernRoot, "tables", "unified_cd_protocol");
cdSummary = readtable(fullfile(unifiedCdRoot, "unified_cd_summary.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
cdFeatures = readtable(fullfile(unifiedCdRoot, "unified_cd_per_feature.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");

cdMedian = unified_cd_matrix(cdSummary, methods, ...
    "pooled_median_abs_error_nm");
f = grouped_bar(cdMedian, categories, methodLabels, methodColors, ...
    "跨門檻CD中位絕對誤差 (nm)", colors.Grid);
export_figure(f, outputDir, "15_model_cd_median_abs_error");

cdMean = unified_cd_matrix(cdSummary, methods, ...
    "pooled_mean_abs_error_nm");
f = grouped_bar(cdMean, categories, methodLabels, methodColors, ...
    "跨門檻CD平均絕對誤差 (nm)", colors.Grid);
export_figure(f, outputDir, "16_model_cd_mean_abs_error");

featureConditions = [
    "50x", "pillar";
    "20x", "pillar";
    "50x", "via";
    "20x", "via"
];
featureNames = [
    "17_50x_pillar_cd_range";
    "18_20x_pillar_cd_range";
    "19_50x_via_cd_range";
    "20_20x_via_cd_range"
];
for c = 1:size(featureConditions, 1)
    part = cdFeatures(cdFeatures.magnification == featureConditions(c, 1) & ...
        cdFeatures.morphology == featureConditions(c, 2), :);
    f = plot_feature_cd_range(part, methods, methodLabels, methodColors, colors);
    export_figure(f, outputDir, featureNames(c));
end
end


function [maeValues, withinValues] = pooled_model_metrics(steps, methods)
maeValues = nan(4, numel(methods));
withinValues = nan(4, numel(methods));
morphologies = ["pillar", "pillar", "via", "via"];
magnifications = ["50x", "20x", "50x", "20x"];
for c = 1:4
    for m = 1:numel(methods)
        mask = steps.morphology == morphologies(c) & steps.method == methods(m);
        if magnifications(c) == "50x"
            mask = mask & startsWith(steps.sequence, "50x");
        else
            mask = mask & startsWith(steps.sequence, "20x");
        end
        part = steps(mask & is_true(steps.evaluable), :);
        errorNm = 1000 * abs(abs(part.signed_step_um) - abs(part.expected_signed_step_um));
        maeValues(c, m) = mean(errorNm, "omitnan");
        withinValues(c, m) = mean(part.within_grid_nm, "omitnan");
    end
end
end


function values = unified_cd_matrix(summary, methods, metricName)
values = nan(4, numel(methods));
morphologies = ["pillar", "pillar", "via", "via"];
magnifications = ["50x", "20x", "50x", "20x"];
for c = 1:4
    for m = 1:numel(methods)
        row = summary(summary.magnification == magnifications(c) & ...
            summary.morphology == morphologies(c) & ...
            summary.method == methods(m), :);
        assert(height(row) == 1, "Unified CD summary row is missing or duplicated.");
        values(c, m) = row.(metricName)(1);
    end
end
end


function f = plot_feature_cd_range(data, methods, methodLabels, methodColors, colors)
f = new_figure();
hold on;
raw = sortrows(data(data.method == "Raw", :), "feature_position");
x = 1:height(raw);
plot(x, raw.sem_cd_nm, "--o", "Color", colors.Reference, ...
    "MarkerFaceColor", "white", "MarkerSize", 4.8, "LineWidth", 1.25, ...
    "DisplayName", "SEM參考直徑");
offsets = linspace(-0.24, 0.24, numel(methods));
markers = ["s", "^", "d", "o"];
for m = 1:numel(methods)
    part = sortrows(data(data.method == methods(m), :), "feature_position");
    assert(height(part) == height(raw), "Unified CD feature rows are incomplete.");
    center = part.median_diameter_nm;
    lower = center - part.cd_lower_nm;
    upper = part.cd_upper_nm - center;
    errorbar(x + offsets(m), center, lower, upper, ...
        "LineStyle", "none", "Color", methodColors(m, :), ...
        "Marker", markers(m), "MarkerFaceColor", "white", ...
        "MarkerSize", 4.8, "CapSize", 4, "LineWidth", 1.05, ...
        "DisplayName", methodLabels(m));
end
xlabel("結構編號");
ylabel("量測直徑 (nm)");
xticks(x);
xticklabels(raw.feature_id);
xlim([0.45 height(raw) + 0.55]);
style_axes(colors.Grid);
legend("Location", "northoutside", "Orientation", "horizontal", ...
    "NumColumns", 5, "Box", "off");
end


function [frameIds, values] = load_variant_seed_series(experimentRoot, variant, sequence)
seeds = [1261200 1261217];
tables = cell(1, numel(seeds));
for i = 1:numel(seeds)
    path = fullfile(experimentRoot, "metrics", variant, "seed" + seeds(i), ...
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


function [pillarIds, fullValues, removedValues, fullSpread, removedSpread] = ...
        load_raw_anchor_per_pillar(experimentRoot)
variants = ["full_control", "no_raw_position_anchor"];
seeds = [1261200 1261217];
allRows = table();
for v = 1:numel(variants)
    for s = 1:numel(seeds)
        path = fullfile(experimentRoot, "metrics", variants(v), "seed" + seeds(s), ...
            "static_cd", "static_cd_per_measurement.csv");
        data = readtable(path, "VariableNamingRule", "preserve", "TextType", "string");
        data = data(data.magnification == "20x" & data.method == "Method" & ...
            data.status == "ok", :);
        allRows = [allRows; data]; %#ok<AGROW>
    end
end
pillarIds = unique(allRows.pillar_id, "sorted");
fullBySeed = nan(numel(pillarIds), numel(seeds));
removedBySeed = nan(numel(pillarIds), numel(seeds));
for p = 1:numel(pillarIds)
    for s = 1:numel(seeds)
        fullMask = allRows.variant == "full_control" & allRows.seed == seeds(s) & ...
            allRows.pillar_id == pillarIds(p);
        removedMask = allRows.variant == "no_raw_position_anchor" & allRows.seed == seeds(s) & ...
            allRows.pillar_id == pillarIds(p);
        fullBySeed(p, s) = median(allRows.abs_error_nm(fullMask), "omitnan");
        removedBySeed(p, s) = median(allRows.abs_error_nm(removedMask), "omitnan");
    end
end
fullValues = mean(fullBySeed, 2, "omitnan");
removedValues = mean(removedBySeed, 2, "omitnan");
fullSpread = 0.5 * (max(fullBySeed, [], 2) - min(fullBySeed, [], 2));
removedSpread = 0.5 * (max(removedBySeed, [], 2) - min(removedBySeed, [], 2));
end


function plot_band(x, values, color, marker, label)
lo = min(values, [], 2)';
hi = max(values, [], 2)';
meanValues = mean(values, 2, "omitnan")';
fill([x fliplr(x)], [lo fliplr(hi)], color, ...
    "FaceAlpha", 0.13, "EdgeColor", "none", "HandleVisibility", "off");
plot(x, meanValues, "Color", color, "Marker", marker, ...
    "MarkerFaceColor", "white", "MarkerSize", 4.6, "DisplayName", label);
end


function ordered = order_rows(tableIn, variable, desired)
indices = zeros(numel(desired), 1);
for i = 1:numel(desired)
    found = find(tableIn.(variable) == desired(i), 1);
    if isempty(found)
        error("Missing %s value %s", variable, desired(i));
    end
    indices(i) = found;
end
ordered = tableIn(indices, :);
end


function f = interval_figure(values, low, high, labels, yLabel, color, gridColor)
f = new_figure();
hold on;
x = 1:numel(values);
errorbar(x, values, values - low, high - values, "o", ...
    "Color", color, "MarkerFaceColor", "white", "MarkerSize", 6, ...
    "CapSize", 8, "LineWidth", 1.5);
yline(0, "-", "Color", [0.25 0.25 0.25], "LineWidth", 1.0);
xlim([0.5 numel(values) + 0.5]);
xticks(x);
xticklabels(labels);
xtickangle(15);
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
ylim([0 max(values, [], "all", "omitnan") * 1.18]);
style_axes(gridColor);
legend(legendLabels, "Location", "northoutside", ...
    "Orientation", "horizontal", "Box", "off");
end


function f = simple_bar(values, labels, barColors, yLabel, gridColor, valueFormat)
f = new_figure();
hold on;
b = bar(values, 0.64, "FaceColor", "flat");
b.CData = barColors;
b.EdgeColor = "none";
xticks(1:numel(labels));
xticklabels(labels);
ylabel(yLabel);
top = max(values) * 1.20;
ylim([0 top]);
for i = 1:numel(values)
    text(i, values(i) + top * 0.025, sprintf(valueFormat, values(i)), ...
        "HorizontalAlignment", "center", "Color", [0.20 0.20 0.20]);
end
style_axes(gridColor);
end


function f = new_figure()
f = figure("Color", "white", "Position", [80 80 920 580], ...
    "Renderer", "painters");
end


function style_axes(gridColor)
ax = gca;
ax.Box = "off";
ax.LineWidth = 1.0;
ax.TickDir = "out";
ax.XColor = [0.20 0.20 0.20];
ax.YColor = [0.20 0.20 0.20];
ax.GridColor = gridColor;
ax.GridAlpha = 1;
grid on;
ax.XMinorGrid = "off";
ax.YMinorGrid = "off";
end


function export_figure(f, outputDir, name)
drawnow;
exportgraphics(f, fullfile(outputDir, name + ".png"), "Resolution", 300);
exportgraphics(f, fullfile(outputDir, name + ".pdf"), "ContentType", "vector");
savefig(f, fullfile(outputDir, name + ".fig"));
close(f);
end


function copy_retained_figures(neuralRoot, retainedDir)
sourceDir = fullfile(neuralRoot, "figures");
files = [
    "00a_50x_full_fov_pillar_locator.png"
    "00b_20x_full_fov_pillar_locator.png"
    "00c_signed_pillar_contrast.png"
    "01_50x_raw_center9.png"
    "02_50x_v42_center9.png"
    "02a_50x_wiener_center9.png"
    "03_50x_pillar_edge_profile.png"
    "04_20x_raw_center9.png"
    "05_20x_v42_center9.png"
    "05a_20x_wiener_center9.png"
    "06_20x_pillar_edge_profile.png"
    "07_center9_cd_per_pillar.png"
    "08_center9_cd_error_summary.png"
    "09a_cd_threshold_sensitivity_horizontal.png"
    "09b_cd_threshold_sensitivity_radial.png"
    "18a_50x_wiener_psf_distance_robustness.png"
    "18b_20x_wiener_psf_distance_robustness.png"
    "23_20x_noncalibration_cd_range.png"
    "23_training_loss_components.png"
    "24_20x_noncalibration_cd_error_summary.png"
    ];
for i = 1:numel(files)
    source = fullfile(sourceDir, files(i));
    if ~isfile(source)
        error("Retained source figure is missing: %s", source);
    end
    copyfile(source, fullfile(retainedDir, files(i)));
end
end


function write_package_manifest(outputRoot)
manifest = table( ...
    ["位移改善"; "消融實驗"; "多模型比較"; "保留既有圖"], ...
    [7; 8; 20; 20], ...
    ["舊版最大梯度量測，重新繪製"; ...
     "舊版消融數據，新增正式圖"; ...
     "排除Base U-Net；位移沿用舊版量測，CD改用統一門檻法"; ...
     "不需改動數據或版面的既有圖"], ...
    'VariableNames', {'category', 'png_count', 'status'});
writetable(manifest, fullfile(outputRoot, "figure_package_manifest.csv"));
end


function ensure_dir(path)
if ~exist(path, "dir")
    mkdir(path);
end
end


function result = is_true(values)
result = ismember(lower(string(values)), ["true", "1"]);
end
