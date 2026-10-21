clear; close all; clc;

rootDir = fileparts(mfilename('fullpath'));
evalDir = fullfile(rootDir, 'evaluation');
outDir = fullfile(evalDir, 'figures_matlab');
if ~exist(outDir, 'dir')
    mkdir(outDir);
end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Times New Roman');
set(groot, 'defaultTextFontName', 'Times New Roman');
set(groot, 'defaultAxesFontSize', 8.5);
set(groot, 'defaultTextFontSize', 8.5);
set(groot, 'defaultAxesLineWidth', 0.75);

preferredMethods = ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"];

cdPath = fullfile(evalDir, 'circular_cd_sharpness', 'circular_feature_cd_intervals.csv');
cdSummaryPath = fullfile(evalDir, 'circular_cd_sharpness', 'circular_feature_method_summary.csv');
dispPath = fullfile(evalDir, 'displacement', 'displacement_summary.csv');
lineSharpPath = fullfile(evalDir, 'line', 'tables', 'line_sharpness_summary.csv');
lineDispPath = fullfile(evalDir, 'line', 'tables', 'line_displacement_pooled.csv');
runtimePath = fullfile(evalDir, 'runtime', 'computational_performance.csv');

if isfile(cdPath)
    cdTable = readtable(cdPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    for magnification = ["50x", "20x"]
        for morphology = ["pillar", "via"]
            plotCdIntervals(cdTable, magnification, morphology, preferredMethods, outDir);
        end
    end
end

if isfile(cdSummaryPath)
    circularSummary = readtable(cdSummaryPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    plotCircularMetric(circularSummary, "50x", "mean_cd_interval_width_nm", ...
        "35%-65% CD interval width (nm)", "50x CD threshold sensitivity", ...
        preferredMethods, fullfile(outDir, '07_50x_cd_interval_width.png'));
    plotCircularMetric(circularSummary, "20x", "mean_cd_interval_width_nm", ...
        "35%-65% CD interval width (nm)", "20x CD threshold sensitivity", ...
        preferredMethods, fullfile(outDir, '08_20x_cd_interval_width.png'));
end

if isfile(cdSummaryPath) && isfile(lineSharpPath)
    lineSharp = readtable(lineSharpPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    plotEdgeWidth50x(circularSummary, lineSharp, preferredMethods, ...
        fullfile(outDir, '09_50x_three_morphology_edge_width.png'));
    plotEdgeWidth20x(circularSummary, preferredMethods, ...
        fullfile(outDir, '10_20x_circular_edge_width.png'));
    plotRinging(circularSummary, "50x", preferredMethods, ...
        fullfile(outDir, '11_50x_circular_ringing.png'));
    plotRinging(circularSummary, "20x", preferredMethods, ...
        fullfile(outDir, '12_20x_circular_ringing.png'));
end

if isfile(dispPath)
    displacement = readtable(dispPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    for morphology = ["pillar", "via"]
        prefix = "13";
        if morphology == "via"
            prefix = "16";
        end
        plotDisplacementMetric(displacement, morphology, "error_sd_nm", ...
            "Step-error SD (nm)", morphology + " displacement stability", ...
            preferredMethods, fullfile(outDir, prefix + "_" + morphology + "_displacement_stability.png"));
        plotDisplacementMetric(displacement, morphology, "mae_nm", ...
            "Mean absolute error vs PI reference (nm)", morphology + " displacement accuracy", ...
            preferredMethods, fullfile(outDir, string(str2double(prefix)+1) + "_" + morphology + "_displacement_mae.png"));
        plotDisplacementMetric(displacement, morphology, "mean_within_grid_nm", ...
            "Mean within-grid disagreement (nm)", morphology + " nine-feature consistency", ...
            preferredMethods, fullfile(outDir, string(str2double(prefix)+2) + "_" + morphology + "_within_grid.png"));
    end
end

if isfile(lineDispPath)
    lineDisplacement = readtable(lineDispPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    plotLineDisplacement(lineDisplacement, preferredMethods, ...
        fullfile(outDir, '19_line_displacement_accuracy.png'));
end

if isfile(runtimePath)
    runtime = readtable(runtimePath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
    plotRuntimeMetric(runtime, "full_median_ms", "Median latency per 2048 x 1536 frame (ms)", ...
        "Full-frame reconstruction latency", preferredMethods, ...
        fullfile(outDir, '20_full_frame_latency.png'));
    plotRuntimeMetric(runtime, "full_peak_gpu_memory_mb", "Peak allocated GPU memory (MB)", ...
        "Full-frame GPU memory", preferredMethods, ...
        fullfile(outDir, '21_full_frame_gpu_memory.png'));
    plotRuntimeMetric(runtime, "parameter_count", "Model parameters (million)", ...
        "Model size", preferredMethods, fullfile(outDir, '22_model_parameter_count.png'), 1e-6);
end

fprintf('MATLAB figures written to: %s\n', outDir);


function plotCdIntervals(T, magnification, morphology, preferred, outDir)
    S = T(T.magnification == magnification & T.morphology == morphology, :);
    methods = orderedPresentMethods(S.method, preferred);
    featureIDs = unique(S.feature_id, 'stable');
    nFeatures = numel(featureIDs);
    nMethods = numel(methods);
    if nFeatures == 0 || nMethods == 0
        return;
    end
    sem = nan(nFeatures, 1);
    for k = 1:nFeatures
        row = S(S.feature_id == featureIDs(k), :);
        sem(k) = row.sem_cd_nm(1) / 1000;
    end
    f = newFigure(17.0, 9.2);
    ax = axes(f); hold(ax, 'on');
    plot(ax, 1:nFeatures, sem, '--o', 'Color', [0.12 0.12 0.12], ...
        'MarkerFaceColor', 'w', 'MarkerSize', 4.0, 'LineWidth', 1.0, ...
        'DisplayName', 'SEM reference');
    offsets = linspace(-0.27, 0.27, nMethods);
    colors = methodColors(methods);
    for m = 1:nMethods
        midpoint = nan(nFeatures, 1);
        lower = nan(nFeatures, 1);
        upper = nan(nFeatures, 1);
        for k = 1:nFeatures
            row = S(S.method == methods(m) & S.feature_id == featureIDs(k), :);
            if ~isempty(row)
                midpoint(k) = row.cd_interval_midpoint_nm(1) / 1000;
                lower(k) = row.cd_lower_nm(1) / 1000;
                upper(k) = row.cd_upper_nm(1) / 1000;
            end
        end
        errorbar(ax, (1:nFeatures) + offsets(m), midpoint, midpoint-lower, upper-midpoint, ...
            'o', 'Color', colors(m,:), 'MarkerFaceColor', colors(m,:), ...
            'MarkerSize', 3.5, 'CapSize', 3, 'LineWidth', 0.9, ...
            'DisplayName', methods(m));
    end
    title(ax, magnification + " " + morphology + " apparent CD range", 'FontWeight', 'normal');
    subtitle(ax, 'Fixed 35%-65% local-contrast thresholds');
    xlabel(ax, upperFirst(morphology) + " identity");
    ylabel(ax, 'Apparent CD (µm)');
    xticks(ax, 1:nFeatures); xticklabels(ax, featureIDs);
    xlim(ax, [0.45 nFeatures+0.55]);
    grid(ax, 'on'); ax.XGrid = 'off';
    legend(ax, 'Location', 'northoutside', 'NumColumns', min(3, nMethods+1), 'Box', 'off');
    styleAxes(ax);
    index = "01";
    if magnification == "50x" && morphology == "via"; index = "02"; end
    if magnification == "20x" && morphology == "pillar"; index = "03"; end
    if magnification == "20x" && morphology == "via"; index = "04"; end
    exportgraphics(f, fullfile(outDir, index + "_" + magnification + "_" + morphology + "_cd_interval.png"), 'Resolution', 300);
    close(f);
end


function plotCircularMetric(T, magnification, variable, yLabel, titleText, preferred, outPath)
    S = T(T.magnification == magnification, :);
    methods = orderedPresentMethods(S.method, preferred);
    morphologies = ["pillar", "via"];
    values = nan(numel(morphologies), numel(methods));
    for c = 1:numel(morphologies)
        for m = 1:numel(methods)
            row = S(S.morphology == morphologies(c) & S.method == methods(m), :);
            if ~isempty(row); values(c,m) = row.(variable)(1); end
        end
    end
    groupedBar(morphologies, values, methods, yLabel, titleText, outPath);
end


function plotEdgeWidth50x(C, L, preferred, outPath)
    methods = orderedPresentMethods(intersect(unique(C.method), unique(L.method), 'stable'), preferred);
    categories = ["Pillar", "Via", "Vertical lines", "Horizontal lines"];
    values = nan(numel(categories), numel(methods));
    for m = 1:numel(methods)
        p = C(C.magnification == "50x" & C.morphology == "pillar" & C.method == methods(m), :);
        v = C(C.magnification == "50x" & C.morphology == "via" & C.method == methods(m), :);
        vl = L(L.orientation == "vertical_lines" & L.method == methods(m), :);
        hl = L(L.orientation == "horizontal_lines" & L.method == methods(m), :);
        if ~isempty(p); values(1,m) = p.mean_edge_width_nm(1); end
        if ~isempty(v); values(2,m) = v.mean_edge_width_nm(1); end
        if ~isempty(vl); values(3,m) = vl.median_transition_width_nm(1); end
        if ~isempty(hl); values(4,m) = hl.median_transition_width_nm(1); end
    end
    groupedBar(categories, values, methods, '10%-90% edge width (nm)', ...
        '50x edge-transition width across three morphologies', outPath);
end


function plotEdgeWidth20x(C, preferred, outPath)
    S = C(C.magnification == "20x", :);
    methods = orderedPresentMethods(S.method, preferred);
    categories = ["Pillar", "Via"];
    values = nan(2, numel(methods));
    for m = 1:numel(methods)
        p = S(S.morphology == "pillar" & S.method == methods(m), :);
        v = S(S.morphology == "via" & S.method == methods(m), :);
        if ~isempty(p); values(1,m) = p.mean_edge_width_nm(1); end
        if ~isempty(v); values(2,m) = v.mean_edge_width_nm(1); end
    end
    groupedBar(categories, values, methods, '10%-90% edge width (nm)', ...
        '20x circular-feature edge-transition width', outPath);
end


function plotRinging(T, magnification, preferred, outPath)
    S = T(T.magnification == magnification, :);
    methods = orderedPresentMethods(S.method, preferred);
    morphologies = ["Pillar", "Via"];
    values = nan(2, numel(methods));
    for c = 1:2
        for m = 1:numel(methods)
            row = S(S.morphology == lower(morphologies(c)) & S.method == methods(m), :);
            if ~isempty(row); values(c,m) = row.mean_ringing_ratio(1); end
        end
    end
    groupedBar(morphologies, values, methods, 'Mean ringing ratio', ...
        magnification + " circular-feature ringing", outPath);
end


function plotDisplacementMetric(T, morphology, variable, yLabel, titleText, preferred, outPath)
    population = "common-valid intersection within Raw-selected top 30";
    S = T(T.morphology == morphology & T.population == population & T.sequence ~= "all_four_sequences", :);
    methods = orderedPresentMethods(S.method, preferred);
    sequences = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"];
    labels = ["50x, 0.5 µm", "50x, 1.0 µm", "20x, 0.5 µm", "20x, 1.0 µm"];
    values = nan(numel(sequences), numel(methods));
    for s = 1:numel(sequences)
        for m = 1:numel(methods)
            row = S(S.sequence == sequences(s) & S.method == methods(m), :);
            if ~isempty(row); values(s,m) = row.(variable)(1); end
        end
    end
    groupedBar(labels, values, methods, yLabel, upperFirst(titleText), outPath);
end


function plotLineDisplacement(T, preferred, outPath)
    methods = orderedPresentMethods(T.method, preferred);
    values = nan(2, numel(methods));
    for m = 1:numel(methods)
        row = T(T.method == methods(m), :);
        if ~isempty(row)
            values(1,m) = row.boundary_mae_nm(1);
            values(2,m) = row.boundary_error_sd_nm(1);
        end
    end
    groupedBar(["MAE", "Error SD"], values, methods, 'Displacement error (nm)', ...
        '50x line-pattern displacement', outPath);
end


function plotRuntimeMetric(T, variable, yLabel, titleText, preferred, outPath, scale)
    if nargin < 7; scale = 1; end
    methods = orderedPresentMethods(T.method, preferred);
    values = nan(numel(methods), 1);
    for m = 1:numel(methods)
        row = T(T.method == methods(m), :);
        if ~isempty(row); values(m) = row.(variable)(1) * scale; end
    end
    f = newFigure(13.5, 8.2); ax = axes(f);
    b = bar(ax, values, 0.68, 'FaceColor', 'flat', 'EdgeColor', 'none');
    b.CData = methodColors(methods);
    xticks(ax, 1:numel(methods)); xticklabels(ax, methods);
    ylabel(ax, yLabel); title(ax, titleText, 'FontWeight', 'normal');
    grid(ax, 'on'); ax.XGrid = 'off'; styleAxes(ax);
    addBarLabels(ax, values);
    exportgraphics(f, outPath, 'Resolution', 300); close(f);
end


function groupedBar(categories, values, methods, yLabel, titleText, outPath)
    f = newFigure(16.5, 8.8); ax = axes(f);
    b = bar(ax, values, 'grouped', 'EdgeColor', 'none');
    colors = methodColors(methods);
    for m = 1:numel(b); b(m).FaceColor = colors(m,:); end
    xticks(ax, 1:numel(categories)); xticklabels(ax, categories);
    ylabel(ax, yLabel); title(ax, titleText, 'FontWeight', 'normal');
    grid(ax, 'on'); ax.XGrid = 'off'; styleAxes(ax);
    legend(ax, methods, 'Location', 'northoutside', 'NumColumns', min(numel(methods), 5), 'Box', 'off');
    exportgraphics(f, outPath, 'Resolution', 300); close(f);
end


function methods = orderedPresentMethods(values, preferred)
    present = unique(string(values), 'stable');
    methods = preferred(ismember(preferred, present));
end


function colors = methodColors(methods)
    names = ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"];
    palette = [0.33 0.33 0.33; 0.62 0.62 0.62; 0.78 0.45 0.16; 0.45 0.36 0.62; 0.00 0.45 0.74];
    colors = zeros(numel(methods), 3);
    for k = 1:numel(methods)
        index = find(names == methods(k), 1);
        colors(k,:) = palette(index,:);
    end
end


function f = newFigure(widthCm, heightCm)
    f = figure('Units', 'centimeters', 'Position', [2 2 widthCm heightCm], ...
        'PaperPositionMode', 'auto', 'Visible', 'off', 'Color', 'w');
end


function styleAxes(ax)
    ax.Box = 'off';
    ax.TickDir = 'out';
    ax.Layer = 'top';
    ax.GridColor = [0.82 0.82 0.82];
    ax.GridAlpha = 0.65;
    ax.LineWidth = 0.75;
end


function addBarLabels(ax, values)
    ymax = max(values, [], 'omitnan');
    if isempty(ymax) || ~isfinite(ymax) || ymax <= 0; return; end
    for k = 1:numel(values)
        text(ax, k, values(k) + 0.025*ymax, sprintf('%.2f', values(k)), ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', 'FontSize', 7.5);
    end
    ylim(ax, [0 ymax*1.16]);
end


function output = upperFirst(input)
    textValue = char(string(input));
    if isempty(textValue); output = string(textValue); return; end
    textValue(1) = upper(textValue(1));
    output = string(textValue);
end
