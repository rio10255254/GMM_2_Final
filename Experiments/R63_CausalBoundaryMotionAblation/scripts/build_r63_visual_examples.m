function build_r63_visual_examples()
%BUILD_R63_VISUAL_EXAMPLES Export the predeclared fixed P29 illustration.

scriptDir = fileparts(mfilename('fullpath'));
experimentDir = fileparts(scriptDir);
repoDir = fileparts(fileparts(experimentDir));
figureDir = fullfile(experimentDir, 'figures');
if ~exist(figureDir, 'dir'); mkdir(figureDir); end

sourceTable = fullfile(repoDir, 'Thesis_MOSR_Evidence', 'Final_Data_Figures', ...
    '01_CURRENT_THESIS_RESULTS_V42_CENTER9', 'cd', 'tables', ...
    'center9_cd_per_pillar.csv');
sem = readtable(sourceTable, 'Delimiter', ',', 'ReadVariableNames', true, ...
    'VariableNamingRule', 'preserve', 'TextType', 'string');
row = sem(sem.sem_index == 29, :);
if height(row) ~= 1; error('Expected exactly one SEM P29 row.'); end

rawPath = char(row.raw_source_image);
[~, rawName, rawExt] = fileparts(rawPath);
rawFile = [rawName rawExt];
fullPath = fullfile(experimentDir, 'results', 'evaluation', 'reconstructions', ...
    'full_control', 'seed1261200', 'static_50x_sem', rawFile);
noGeometryPath = fullfile(experimentDir, 'results', 'evaluation', 'reconstructions', ...
    'no_geometry_anchor', 'seed1261200', 'static_50x_sem', rawFile);

raw = read_gray(rawPath);
fullImage = read_gray(fullPath);
noGeometry = read_gray(noGeometryPath);
if ~isequal(size(raw), size(fullImage), size(noGeometry))
    error('Fixed visual-example images do not share one image grid.');
end

cx = double(row.raw_x_px);
cy = double(row.raw_y_px);
pixelUm = 0.069;
halfWidthPx = 60;
% Source coordinates are zero-based image coordinates; MATLAB indices are one-based.
centerColumn = round(cx) + 1;
centerRow = round(cy) + 1;
xIndex = centerColumn + (-halfWidthPx:halfWidthPx);
yIndex = centerRow + (-halfWidthPx:halfWidthPx);
if min(xIndex) < 1 || max(xIndex) > size(raw, 2) || ...
        min(yIndex) < 1 || max(yIndex) > size(raw, 1)
    error('Fixed P29 crop extends outside the image.');
end

crops = {
    raw(yIndex, xIndex), 'Raw image', '21_fixed_p29_raw';
    fullImage(yIndex, xIndex), 'Full MOSR recipe', '22_fixed_p29_full';
    noGeometry(yIndex, xIndex), 'MOSR without static geometry anchoring', '23_fixed_p29_no_geometry'
};
rawCrop = crops{1, 1};
displayLimits = prctile(rawCrop(:), [1, 99]);
if displayLimits(2) <= displayLimits(1)
    displayLimits = [min(rawCrop(:)), max(rawCrop(:))];
end
coordinateUm = (-halfWidthPx:halfWidthPx) * pixelUm;
for index = 1:size(crops, 1)
    export_crop(crops{index, 1}, coordinateUm, displayLimits, ...
        crops{index, 2}, figureDir, crops{index, 3});
end

stripHalfHeight = 3;
profileY = centerRow + (-stripHalfHeight:stripHalfHeight);
profileX = centerColumn + (-halfWidthPx:halfWidthPx);
rawProfile = normalize_dark_profile(raw(profileY, profileX));
fullProfile = normalize_dark_profile(fullImage(profileY, profileX));
noGeometryProfile = normalize_dark_profile(noGeometry(profileY, profileX));

fig = new_figure();
ax = axes(fig); hold(ax, 'on');
plot(ax, coordinateUm, rawProfile, '--', 'Color', [0.35, 0.35, 0.35], ...
    'LineWidth', 1.1, 'DisplayName', 'Raw');
plot(ax, coordinateUm, fullProfile, '-', 'Color', [0.00, 0.447, 0.741], ...
    'LineWidth', 1.35, 'DisplayName', 'Full MOSR');
plot(ax, coordinateUm, noGeometryProfile, '-', 'Color', [0.850, 0.325, 0.098], ...
    'LineWidth', 1.25, 'DisplayName', 'No static geometry');
semRadiusUm = double(row.sem_diameter_um) / 2.0;
xline(ax, -semRadiusUm, ':', 'Color', [0.15, 0.15, 0.15], ...
    'LineWidth', 1.0, 'HandleVisibility', 'off');
xline(ax, semRadiusUm, ':', 'Color', [0.15, 0.15, 0.15], ...
    'LineWidth', 1.0, 'DisplayName', 'SEM reference boundary');
yline(ax, 0.5, ':', '50% local contrast', 'Color', [0.55, 0.55, 0.55], ...
    'LabelHorizontalAlignment', 'left', 'HandleVisibility', 'off');
xlabel(ax, 'Position relative to P29 center (um)');
ylabel(ax, 'Normalized local darkness');
title(ax, 'Fixed central-pillar boundary profile');
subtitle(ax, 'Each curve is normalized by its own local plateau levels for boundary comparison only');
legend(ax, 'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
finish_axes(ax);
export_pair(fig, figureDir, '24_fixed_p29_boundary_profile');

manifest = table( ...
    string(rawPath), string(fullPath), string(noGeometryPath), ...
    cx, cy, halfWidthPx, pixelUm, displayLimits(1), displayLimits(2), ...
    'VariableNames', {'raw_path', 'full_path', 'no_geometry_path', ...
    'center_x_px', 'center_y_px', 'half_width_px', 'object_um_per_px', ...
    'shared_display_low', 'shared_display_high'});
writetable(manifest, fullfile(figureDir, 'fixed_p29_visual_manifest.csv'));
fprintf('R63 fixed P29 visual examples written to %s\n', figureDir);
end

function image = read_gray(path)
if ~isfile(path); error('Missing image: %s', path); end
image = imread(path);
if ndims(image) == 3; image = rgb2gray(image); end
image = double(image);
end

function profile = normalize_dark_profile(strip)
profile = 255.0 - median(double(strip), 1);
low = prctile(profile, 5);
high = prctile(profile, 95);
profile = (profile - low) ./ max(high - low, eps);
profile = min(max(profile, 0), 1);
end

function export_crop(crop, coordinateUm, displayLimits, titleText, folder, stem)
fig = figure('Color', 'w', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [100, 100, 720, 650]);
ax = axes(fig);
imagesc(ax, coordinateUm, coordinateUm, crop, displayLimits);
axis(ax, 'image');
colormap(ax, gray(256));
xlabel(ax, 'x relative to P29 center (um)');
ylabel(ax, 'y relative to P29 center (um)');
title(ax, titleText);
ax.FontName = 'Times New Roman';
ax.FontSize = 10;
ax.LineWidth = 0.8;
ax.Box = 'off';
ax.TickDir = 'out';
exportgraphics(fig, fullfile(folder, [stem '.png']), 'Resolution', 300);
exportgraphics(fig, fullfile(folder, [stem '.pdf']), 'ContentType', 'image');
close(fig);
end

function fig = new_figure()
fig = figure('Color', 'w', 'Visible', 'off', 'Units', 'pixels', ...
    'Position', [100, 100, 900, 650]);
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
