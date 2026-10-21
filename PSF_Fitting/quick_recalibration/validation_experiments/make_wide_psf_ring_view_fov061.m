function make_wide_psf_ring_view_fov061()
% Create a wider PSF view for L0 Round1 FOV #61 so the diffraction rings are visible.

validationDir = fileparts(mfilename('fullpath'));
quickDir = fileparts(validationDir);
outDir = fullfile(quickDir, ...
    'slide_ready_L0_L1_single_images_20260625', ...
    '08_PSF_fit_result_single_images');

roundName = 'L0_newdata_round1';
fovList = [1 6 11 56 61 66 111 116 121];
fov = 61;
cropSize = 81;
scale = 16;
gammaValue = 0.35;
ringRadii = [16.5 27.5];

if ~exist(outDir, 'dir')
    error('Output directory does not exist: %s', outDir);
end

psf = median_psf_from_trials(validationDir, roundName, fov, fovList);
crop = center_crop(psf, cropSize);
normalized = normalize01(crop);
enhanced = normalized .^ gammaValue;

cleanRgb = psf_to_parula_pixel_rgb(enhanced, scale);
cleanPath = fullfile(outDir, 'l0_round1_median_psf_fov061_wide_crop81_ring_enhanced.png');
imwrite(cleanRgb, cleanPath);
write_sidecar(cleanPath, cropSize, scale, gammaValue, false);

annotatedPath = fullfile(outDir, 'l0_round1_median_psf_fov061_wide_crop81_ring_annotated.png');
write_annotated(cleanRgb, annotatedPath, cropSize, scale, ringRadii);
write_sidecar(annotatedPath, cropSize, scale, gammaValue, true);

linearRgb = psf_to_parula_pixel_rgb(normalized, scale);
linearPath = fullfile(outDir, 'l0_round1_median_psf_fov061_wide_crop81_linear_reference.png');
imwrite(linearRgb, linearPath);
write_linear_sidecar(linearPath, cropSize, scale);

linearAnnotatedPath = fullfile(outDir, 'l0_round1_median_psf_fov061_wide_crop81_linear_annotated.png');
write_annotated(linearRgb, linearAnnotatedPath, cropSize, scale, ringRadii);
write_linear_annotated_sidecar(linearAnnotatedPath, cropSize, scale);

summary = struct();
summary.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
summary.source_round = roundName;
summary.source_fov = fov;
summary.source_trials = 15;
summary.crop_size = cropSize;
summary.scale = scale;
summary.gamma_for_ring_enhanced_view = gammaValue;
summary.ring_radii_pixels_from_radial_profile = ringRadii;
summary.clean_ring_enhanced = cleanPath;
summary.annotated_ring_enhanced = annotatedPath;
summary.linear_reference = linearPath;
summary.linear_annotated = linearAnnotatedPath;

summaryPath = fullfile(outDir, 'WIDE_PSF_RING_VIEW_FOV061_SUMMARY.json');
fid = fopen(summaryPath, 'w');
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s', jsonencode(summary, 'PrettyPrint', true));
delete(cleanup);

fprintf('Created wide PSF ring-view images:\n');
fprintf('  %s\n', cleanPath);
fprintf('  %s\n', annotatedPath);
fprintf('  %s\n', linearPath);
fprintf('  %s\n', linearAnnotatedPath);
end

function psf = median_psf_from_trials(validationDir, roundName, fov, fovList)
fovIdx = find(fovList == fov, 1);
if isempty(fovIdx)
    error('FOV %d is not in the fitted FOV list.', fov);
end

trialDirs = dir(fullfile(validationDir, roundName, 'outputs', 'trial_*'));
trialDirs = trialDirs([trialDirs.isdir]);
[~, order] = sort({trialDirs.name});
trialDirs = trialDirs(order);

if isempty(trialDirs)
    error('No trial folders found for %s.', roundName);
end

stack = [];
for k = 1:numel(trialDirs)
    matPath = fullfile(trialDirs(k).folder, trialDirs(k).name, 'PSF_fitted_2D_FOVstack.mat');
    if ~exist(matPath, 'file')
        error('Missing PSF result file: %s', matPath);
    end
    data = load(matPath, 'psf_grid');
    raw = double(squeeze(data.psf_grid(:, :, 1, fovIdx)));
    if isempty(stack)
        stack = nan([size(raw), numel(trialDirs)]);
    end
    stack(:, :, k) = raw;
end

psf = median(stack, 3, 'omitnan');
end

function crop = center_crop(img, cropSize)
[h, w] = size(img);
half = floor(cropSize / 2);
cy = ceil(h / 2);
cx = ceil(w / 2);
y = (cy - half):(cy + half);
x = (cx - half):(cx + half);
crop = img(y, x);
end

function img = normalize01(img)
img = double(img);
img = img - min(img(:));
mx = max(img(:));
if mx > 0
    img = img ./ mx;
end
img = min(max(img, 0), 1);
end

function rgbBig = psf_to_parula_pixel_rgb(img, scale)
img = min(max(double(img), 0), 1);
cmap = parula(256);
idx = floor(img * 255) + 1;
rgb = zeros([size(idx), 3]);
for ch = 1:3
    channel = reshape(cmap(idx(:), ch), size(idx));
    rgb(:, :, ch) = channel;
end
rgbBig = repelem(rgb, scale, scale, 1);
end

function write_annotated(rgb, outPath, cropSize, scale, ringRadii)
fig = figure('Visible', 'off', 'Color', 'w', 'Units', 'pixels', ...
    'Position', [100 100 size(rgb, 2) size(rgb, 1)]);
ax = axes(fig, 'Position', [0 0 1 1]);
image(ax, rgb);
axis(ax, 'image');
axis(ax, 'off');
hold(ax, 'on');

center = ((cropSize + 1) / 2 - 0.5) * scale + 0.5;
theta = linspace(0, 2*pi, 720);
labels = {'1st diffraction ring', '2nd diffraction ring'};
colors = [1.0 1.0 1.0; 1.0 0.88 0.22];
for i = 1:numel(ringRadii)
    r = ringRadii(i) * scale;
    x = center + r * cos(theta);
    y = center + r * sin(theta);
    plot(ax, x, y, '-', 'Color', colors(i, :), 'LineWidth', 2.6);
end

legendX = 36;
legendY = 42;
for i = 1:numel(labels)
    y = legendY + (i - 1) * 42;
    plot(ax, [legendX legendX + 34], [y y], '-', 'Color', colors(i, :), 'LineWidth', 4.0);
    text(ax, legendX + 48, y, labels{i}, ...
        'Color', colors(i, :), 'FontSize', 22, 'FontWeight', 'bold', ...
        'FontName', 'Arial', 'Interpreter', 'none', ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle');
end

exportgraphics(fig, outPath, 'Resolution', 160);
close(fig);
end

function write_sidecar(outPath, cropSize, scale, gammaValue, annotated)
txtPath = [outPath '.txt'];
fid = fopen(txtPath, 'w', 'n', 'UTF-8');
cleanup = onCleanup(@() fclose(fid));
if annotated
    fprintf(fid, 'L0 Round1 FOV #61 PSF wide view with ring annotations\n');
else
    fprintf(fid, 'L0 Round1 FOV #61 PSF wide ring-enhanced view\n');
end
fprintf(fid, '這張圖由 L0_newdata_round1 的 15 次 PSF fitting 結果取中位數後重畫。\n');
fprintf(fid, '視野從原本中心 31 x 31 擴大為中心 %d x %d，因此比較容易看到外圍繞射環。\n', cropSize, cropSize);
fprintf(fid, '顯示方式使用 Matlab parula 色盤、最近鄰像素格放大 %d 倍，並用 gamma %.2f 增強低強度區域。\n', scale, gammaValue);
fprintf(fid, '注意：這是為了看一級/二級繞射環的顯示增強版，不是線性強度比例圖。\n');
delete(cleanup);
end

function write_linear_sidecar(outPath, cropSize, scale)
txtPath = [outPath '.txt'];
fid = fopen(txtPath, 'w', 'n', 'UTF-8');
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, 'L0 Round1 FOV #61 PSF wide linear reference\n');
fprintf(fid, '這張圖由同一份 L0_newdata_round1 的 15 次 PSF fitting 中位數重畫。\n');
fprintf(fid, '視野為中心 %d x %d，最近鄰像素格放大 %d 倍，使用線性 0-1 正規化。\n', cropSize, cropSize, scale);
fprintf(fid, '它用來當強度比例參考；外圍繞射環會比 ring-enhanced 版本更不明顯。\n');
delete(cleanup);
end

function write_linear_annotated_sidecar(outPath, cropSize, scale)
txtPath = [outPath '.txt'];
fid = fopen(txtPath, 'w', 'n', 'UTF-8');
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, 'L0 Round1 FOV #61 PSF wide linear view with ring annotations\n');
fprintf(fid, '這張圖由同一份 L0_newdata_round1 的 15 次 PSF fitting 中位數重畫。\n');
fprintf(fid, '底圖是中心 %d x %d 的線性 0-1 正規化強度，最近鄰像素格放大 %d 倍。\n', cropSize, cropSize, scale);
fprintf(fid, '白色與黃色圓圈只用來標示一級與二級繞射環的位置，沒有增強底圖強度。\n');
fprintf(fid, '適合在簡報中說明：線性比例下外圍環很淡，但位置仍可用標示圈指出。\n');
delete(cleanup);
end
