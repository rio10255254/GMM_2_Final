function plot_multimodel_displacement_complete_english()
% Complete English multi-model displacement figure package.
% The step traces use the Raw-selected top 30 steps. Summary charts use the
% common-valid intersection so every method is evaluated on identical steps.

sourceRoot = "Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/modern_baseline_three_morphology_20260719";
outputRoot = "Thesis_MOSR_Evidence/Final_Data_Figures/14_V27_MULTIMODEL_DISPLACEMENT_COMPLETE_ENGLISH_20260727";
figureDir = fullfile(outputRoot, "figures");
tableDir = fullfile(outputRoot, "tables");
ensure_dir(outputRoot);
ensure_dir(figureDir);
ensure_dir(tableDir);

stepPath = fullfile(sourceRoot, "tables", "displacement", "displacement_step_measurements.csv");
summaryPath = fullfile(sourceRoot, "tables", "displacement", "displacement_summary.csv");
steps = readtable(stepPath, "VariableNamingRule", "preserve", "TextType", "string");
summary = readtable(summaryPath, "VariableNamingRule", "preserve", "TextType", "string");

methods = ["Raw", "NAFNet", "EDSR", "MOSR"];
methodLabels = ["Raw", "NAFNet", "EDSR-x1", "MOSR"];
steps = steps(ismember(steps.method, methods), :);
summary = summary(ismember(summary.method, methods), :);
commonSummary = summary(summary.population == ...
    "common-valid intersection within Raw-selected top 30", :);

writetable(steps, fullfile(tableDir, "multimodel_displacement_step_measurements.csv"));
writetable(commonSummary, fullfile(tableDir, "multimodel_displacement_summary_common_valid.csv"));

colors.Raw = [0.67 0.29 0.09];
colors.NAFNet = [0.91 0.45 0.05];
colors.EDSR = [0.45 0.36 0.67];
colors.MOSR = [0.03 0.38 0.68];
colors.Reference = [0.35 0.35 0.35];
colors.Grid = [0.86 0.86 0.86];
methodColors = [colors.Raw; colors.NAFNet; colors.EDSR; colors.MOSR];
markers = ["s", "^", "d", "o"];

set(groot, "defaultAxesFontName", "Times New Roman");
set(groot, "defaultTextFontName", "Times New Roman");
set(groot, "defaultLegendFontName", "Times New Roman");
set(groot, "defaultAxesFontSize", 12);
set(groot, "defaultTextFontSize", 12);
set(groot, "defaultLineLineWidth", 2.0);

sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
sequenceNames = ["50x_0p5um", "50x_1um", "20x_0p5um", "20x_1um"];
morphologies = ["pillar", "via"];
manifestName = strings(0, 1);
manifestType = strings(0, 1);
manifestMorphology = strings(0, 1);
manifestNominal = strings(0, 1);
manifestMetric = strings(0, 1);

figureNumber = 1;
for morphology = morphologies
    for s = 1:numel(sequences)
        subset = steps(steps.morphology == morphology & steps.sequence == sequences(s), :);
        nominalNm = 500;
        nominalLabel = "0.5 um";
        if contains(sequences(s), "1um")
            nominalNm = 1000;
            nominalLabel = "1.0 um";
        end

        f = new_figure([120 120 1320 790]);
        ax = axes(f);
        hold(ax, "on");
        yline(ax, nominalNm, "--", "Color", colors.Reference, "LineWidth", 1.5, ...
            "DisplayName", "PI-stage feedback");
        plottedValues = nominalNm;
        for m = 1:numel(methods)
            part = subset(subset.method == methods(m), :);
            part = sortrows(part, "end_frame_index");
            y = 1000 * abs(part.signed_step_um);
            valid = logical_values(part.evaluable);
            y(~valid) = NaN;
            plottedValues = [plottedValues; y(isfinite(y))]; %#ok<AGROW>
            plot(ax, 1:height(part), y, "-", ...
                "Color", methodColors(m, :), "Marker", markers(m), ...
                "MarkerSize", 5.3, "MarkerFaceColor", "white", ...
                "LineWidth", 2.0, "DisplayName", methodLabels(m));
        end
        xlabel(ax, "Step index");
        ylabel(ax, "Measured displacement magnitude (nm)");
        xlim(ax, [1 30]);
        xticks(ax, [1 5 10 15 20 25 30]);
        apply_trace_limits(ax, plottedValues, nominalNm);
        style_axes(ax, colors.Grid);
        lgd = legend(ax, "Location", "northoutside", "Orientation", "horizontal", ...
            "NumColumns", 5, "Box", "off");
        lgd.FontSize = 11.5;
        ax.Position = [0.09 0.12 0.88 0.73];

        baseName = sprintf("%02d_%s_%s_model_step_trace", figureNumber, ...
            char(morphology), char(sequenceNames(s)));
        export_figure(f, figureDir, baseName);
        close(f);

        manifestName(end + 1, 1) = baseName; %#ok<AGROW>
        manifestType(end + 1, 1) = "step trace"; %#ok<AGROW>
        manifestMorphology(end + 1, 1) = morphology; %#ok<AGROW>
        manifestNominal(end + 1, 1) = nominalLabel; %#ok<AGROW>
        manifestMetric(end + 1, 1) = "measured displacement magnitude"; %#ok<AGROW>
        figureNumber = figureNumber + 1;
    end
end

categoryMorphology = ["pillar", "pillar", "via", "via"];
categoryMagnification = ["50x", "20x", "50x", "20x"];
categoryLabels = ["50x pillar", "20x pillar", "50x via", "20x via"];
metrics = ["signed_step_sd_nm", "mae_nm", "mean_within_grid_nm"];
metricLabels = ["Step-displacement standard deviation (nm)", ...
    "Displacement mean absolute error (nm)", ...
    "Nine-feature displacement disagreement (nm)"];
metricNames = ["step_sd", "displacement_mae", "within_feature_disagreement"];

for nominalIndex = 1:2
    if nominalIndex == 1
        sequenceByMagnification = ["50x_x_0p5um", "20x_0p5um"];
        nominalFileLabel = "0p5um";
        nominalLabel = "0.5 um";
    else
        sequenceByMagnification = ["50x_x_1um", "20x_1um"];
        nominalFileLabel = "1um";
        nominalLabel = "1.0 um";
    end

    for metricIndex = 1:numel(metrics)
        values = nan(numel(categoryLabels), numel(methods));
        sampleCounts = nan(numel(categoryLabels), numel(methods));
        for c = 1:numel(categoryLabels)
            sequence = sequenceByMagnification(1);
            if categoryMagnification(c) == "20x"
                sequence = sequenceByMagnification(2);
            end
            for m = 1:numel(methods)
                row = commonSummary(commonSummary.morphology == categoryMorphology(c) & ...
                    commonSummary.sequence == sequence & commonSummary.method == methods(m), :);
                assert(height(row) == 1, "Expected one summary row for %s/%s/%s.", ...
                    categoryMorphology(c), sequence, methods(m));
                values(c, m) = row.(metrics(metricIndex))(1);
                sampleCounts(c, m) = row.n(1);
            end
        end

        f = grouped_bar_figure(values, categoryLabels, methodLabels, methodColors, ...
            metricLabels(metricIndex), colors.Grid);
        baseName = sprintf("%02d_%s_%s", figureNumber, char(nominalFileLabel), ...
            char(metricNames(metricIndex)));
        export_figure(f, figureDir, baseName);
        close(f);

        manifestName(end + 1, 1) = baseName; %#ok<AGROW>
        manifestType(end + 1, 1) = "summary bar"; %#ok<AGROW>
        manifestMorphology(end + 1, 1) = "pillar and via"; %#ok<AGROW>
        manifestNominal(end + 1, 1) = nominalLabel; %#ok<AGROW>
        manifestMetric(end + 1, 1) = metricLabels(metricIndex); %#ok<AGROW>
        figureNumber = figureNumber + 1;
    end
end

figureManifest = table(manifestName, manifestType, manifestMorphology, ...
    manifestNominal, manifestMetric, 'VariableNames', ...
    {'figure_name', 'figure_type', 'morphology', 'nominal_step', 'metric'});
writetable(figureManifest, fullfile(tableDir, "figure_manifest.csv"));

metadata = struct();
metadata.created_at = char(datetime("now", "Format", "yyyy-MM-dd HH:mm:ss"));
metadata.measurement_method = "Original maximum-gradient boundary displacement method";
metadata.step_selection = "Raw-selected top 30 steps";
metadata.trace_rule = "All selected steps are shown; method-invalid observations are plotted as gaps";
metadata.summary_rule = "Common-valid intersection within each Raw-selected top-30 condition";
metadata.models = cellstr(methodLabels);
metadata.figure_count = height(figureManifest);
metadata.source_step_table = char(stepPath);
metadata.source_summary_table = char(summaryPath);
fid = fopen(fullfile(outputRoot, "analysis_metadata.json"), "w", "n", "UTF-8");
assert(fid > 0, "Could not open metadata output file.");
fprintf(fid, "%s", jsonencode(metadata, "PrettyPrint", true));
fclose(fid);

fprintf("Created %d figures in %s\n", height(figureManifest), figureDir);
end


function f = grouped_bar_figure(values, categoryLabels, methodLabels, methodColors, yLabel, gridColor)
f = new_figure([120 120 1420 820]);
ax = axes(f);
hold(ax, "on");
b = bar(ax, values, "grouped", "BarWidth", 0.82);
for m = 1:numel(b)
    b(m).FaceColor = methodColors(m, :);
    b(m).EdgeColor = "none";
    b(m).DisplayName = methodLabels(m);
end

maxValue = max(values, [], "all", "omitnan");
ylim(ax, [0, maxValue * 1.24]);
for m = 1:numel(b)
    text(ax, b(m).XEndPoints, b(m).YEndPoints + maxValue * 0.025, ...
        compose("%.2f", b(m).YData), "HorizontalAlignment", "center", ...
        "VerticalAlignment", "bottom", "FontSize", 10.2, ...
        "Color", [0.18 0.18 0.18]);
end
xticks(ax, 1:numel(categoryLabels));
xticklabels(ax, categoryLabels);
ylabel(ax, yLabel);
style_axes(ax, gridColor);
lgd = legend(ax, "Location", "northoutside", "Orientation", "horizontal", ...
    "NumColumns", 4, "Box", "off");
lgd.FontSize = 11.5;
ax.Position = [0.09 0.13 0.88 0.72];
end


function apply_trace_limits(ax, values, nominalNm)
values = values(isfinite(values));
low = min(values);
high = max(values);
span = max(high - low, max(8, nominalNm * 0.018));
padding = span * 0.16;
ylim(ax, [low - padding, high + padding]);
end


function style_axes(ax, gridColor)
ax.FontName = "Times New Roman";
ax.FontSize = 12;
ax.LineWidth = 1.15;
ax.Box = "off";
ax.TickDir = "out";
ax.XGrid = "off";
ax.YGrid = "on";
ax.GridColor = gridColor;
ax.GridAlpha = 1.0;
ax.Layer = "top";
end


function f = new_figure(position)
f = figure("Color", "white", "Position", position, "Visible", "off", ...
    "Renderer", "painters");
end


function export_figure(f, outputDir, baseName)
pngPath = fullfile(outputDir, baseName + ".png");
pdfPath = fullfile(outputDir, baseName + ".pdf");
figPath = fullfile(outputDir, baseName + ".fig");
exportgraphics(f, pngPath, "Resolution", 300, "BackgroundColor", "white");
exportgraphics(f, pdfPath, "ContentType", "vector", "BackgroundColor", "white");
savefig(f, figPath);
end


function ensure_dir(path)
if ~isfolder(path)
    mkdir(path);
end
end


function result = logical_values(values)
if islogical(values)
    result = values;
elseif isnumeric(values)
    result = values ~= 0;
else
    textValues = lower(strtrim(string(values)));
    result = ismember(textValues, ["true", "1", "yes"]);
end
end
