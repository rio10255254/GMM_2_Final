function outputs = make_base_unet_qualitative_figure(resultsRoot)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
%MAKE_BASE_UNET_QUALITATIVE_FIGURE Export fixed-scale 50x and 20x comparisons.

% The same crop and the native 0-255 grayscale range are used for Raw,
% Base U-Net, and MOSR so that apparent contrast is not independently
% stretched for any method.

if nargin < 1 || strlength(string(resultsRoot)) == 0
    resultsRoot = fullfile(fileparts(mfilename('fullpath')), ...
        'results_full_data_fixed_psf_v2');
end
resultsRoot = char(resultsRoot);

rawPath = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/20260618_100MG') filesep] ...
    'Image__2026-06-18__17-10-31.bmp'];
basePath = fullfile(resultsRoot, 'real_inference', 'static', ...
    'static_50x_center9_base_unet.bmp');
mosrPath = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '02_V42_E120_SOURCE_MATERIAL\reconstructions\100mg_static\' ...
    'Image__2026-06-18__17-10-31.bmp'];
centersPath = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '01_CURRENT_THESIS_RESULTS_V42_CENTER9\cd\tables\' ...
    'center9_cd_per_pillar.csv'];

required = {rawPath, basePath, mosrPath, centersPath};
for idx = 1:numel(required)
    assert(isfile(required{idx}), 'Missing required input: %s', required{idx});
end

raw = imread(rawPath);
base = imread(basePath);
mosr = imread(mosrPath);
if size(raw, 3) > 1, raw = rgb2gray(raw); end
if size(base, 3) > 1, base = rgb2gray(base); end
if size(mosr, 3) > 1, mosr = rgb2gray(mosr); end
assert(isequal(size(raw), size(base), size(mosr)), ...
    'Raw, Base U-Net, and MOSR images must have identical dimensions.');

centers = readtable(centersPath, 'Delimiter', ',', ...
    'VariableNamingRule', 'preserve');
margin = 38;
x1 = max(1, floor(min(centers.raw_x_px) - margin));
x2 = min(size(raw, 2), ceil(max(centers.raw_x_px) + margin));
y1 = max(1, floor(min(centers.raw_y_px) - margin));
y2 = min(size(raw, 1), ceil(max(centers.raw_y_px) + margin));

images = {raw(y1:y2, x1:x2), base(y1:y2, x1:x2), mosr(y1:y2, x1:x2)};
labels = {'(a) Raw', '(b) Base U-Net', '(c) MOSR'};

fig = figure('Visible', 'off', 'Color', 'w', 'Units', 'pixels', ...
    'Position', [100 100 1180 405]);
layout = tiledlayout(fig, 1, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
for idx = 1:3
    ax = nexttile(layout, idx);
    imshow(images{idx}, [0 255], 'Parent', ax, 'InitialMagnification', 'fit');
    title(ax, labels{idx}, 'FontName', 'Times New Roman', ...
        'FontSize', 10, 'FontWeight', 'normal');
    axis(ax, 'image');
end
title(layout, '50× center-nine pillars (common 0-255 grayscale)', ...
    'FontName', 'Times New Roman', 'FontSize', 10, 'FontWeight', 'normal');

outputDir = fullfile(resultsRoot, 'figures');
if ~isfolder(outputDir), mkdir(outputDir); end
outputPath = fullfile(outputDir, 'base_unet_50x_fixed_scale_comparison.png');
exportgraphics(fig, outputPath, 'Resolution', 300, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', outputPath);

raw20Path = [[fullfile(PROJECT_ROOT, 'Analyses/20260704_20x_5x_analysis/raw_inputs') filesep] ...
    '20x_1um\bmp\frame_0049.bmp'];
base20Path = fullfile(resultsRoot, 'real_inference', 'static', ...
    'static_20x_frame49_base_unet.bmp');
mosr20Path = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '02_V42_E120_SOURCE_MATERIAL\reconstructions\20x_1um\frame_0049.bmp'];
centers20Path = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '04_V42_NEURAL_NETWORK_RESULTS\source_validation\wiener_baseline_20260715\' ...
    'supplementary_20x_cd\tables\20x_frame49_cd_per_measurement.csv'];
required20 = {raw20Path, base20Path, mosr20Path, centers20Path};
for idx = 1:numel(required20)
    assert(isfile(required20{idx}), 'Missing required input: %s', required20{idx});
end
raw20 = imread(raw20Path); base20 = imread(base20Path); mosr20 = imread(mosr20Path);
if size(raw20, 3) > 1, raw20 = rgb2gray(raw20); end
if size(base20, 3) > 1, base20 = rgb2gray(base20); end
if size(mosr20, 3) > 1, mosr20 = rgb2gray(mosr20); end
assert(isequal(size(raw20), size(base20), size(mosr20)), ...
    'Raw, Base U-Net, and MOSR 20x images must have identical dimensions.');
centers20 = readtable(centers20Path, 'Delimiter', ',', 'VariableNamingRule', 'preserve');
centers20 = centers20(string(centers20.case) == "raw" & ...
    string(centers20.measurement_mode) == "horizontal_strip" & ...
    abs(centers20.threshold_fraction - 0.50) < 1e-8, :);
centers20 = sortrows(centers20, 'center9_position');
assert(height(centers20) == 9, 'Expected nine unique 20x centers.');
margin20 = 14;
x1 = max(1, floor(min(centers20.center_x_px) - margin20));
x2 = min(size(raw20, 2), ceil(max(centers20.center_x_px) + margin20));
y1 = max(1, floor(min(centers20.center_y_px) - margin20));
y2 = min(size(raw20, 1), ceil(max(centers20.center_y_px) + margin20));
images20 = {raw20(y1:y2, x1:x2), base20(y1:y2, x1:x2), mosr20(y1:y2, x1:x2)};
fig = figure('Visible', 'off', 'Color', 'w', 'Units', 'pixels', ...
    'Position', [100 100 1180 405]);
layout = tiledlayout(fig, 1, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
for idx = 1:3
    ax = nexttile(layout, idx);
    imshow(images20{idx}, [0 255], 'Parent', ax, 'InitialMagnification', 'fit');
    title(ax, labels{idx}, 'FontName', 'Times New Roman', ...
        'FontSize', 10, 'FontWeight', 'normal');
    axis(ax, 'image');
end
title(layout, '20× center-nine pillars (common 0-255 grayscale)', ...
    'FontName', 'Times New Roman', 'FontSize', 10, 'FontWeight', 'normal');
output20Path = fullfile(outputDir, 'base_unet_20x_fixed_scale_comparison.png');
exportgraphics(fig, output20Path, 'Resolution', 300, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', output20Path);
outputs = struct('comparison_50x', outputPath, 'comparison_20x', output20Path);
end
