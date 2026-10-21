function make_matlab_style_psf_heatmaps()
% Rebuild slide-ready PSF heatmaps in a MATLAB-like pixel-grid style.

validationDir = fileparts(mfilename('fullpath'));
quickDir = fileparts(validationDir);
outDir = fullfile(quickDir, ...
    'slide_ready_L0_L1_single_images_20260625', ...
    '08_PSF_fit_result_single_images');

fovList = [1 6 11 56 61 66 111 116 121];
cropSize = 31;
scale = 32;

items = {
    'l0_round1_median_psf_fov001_heatmap.png', 'L0_newdata_round1', 1,   'L0 Round1 FOV #1';
    'l0_round1_median_psf_fov006_heatmap.png', 'L0_newdata_round1', 6,   'L0 Round1 FOV #6';
    'l0_round1_median_psf_fov011_heatmap.png', 'L0_newdata_round1', 11,  'L0 Round1 FOV #11';
    'l0_round1_median_psf_fov056_heatmap.png', 'L0_newdata_round1', 56,  'L0 Round1 FOV #56';
    'l0_round1_median_psf_fov061_heatmap.png', 'L0_newdata_round1', 61,  'L0 Round1 FOV #61';
    'l0_round1_median_psf_fov066_heatmap.png', 'L0_newdata_round1', 66,  'L0 Round1 FOV #66';
    'l0_round1_median_psf_fov111_heatmap.png', 'L0_newdata_round1', 111, 'L0 Round1 FOV #111';
    'l0_round1_median_psf_fov116_heatmap.png', 'L0_newdata_round1', 116, 'L0 Round1 FOV #116';
    'l0_round1_median_psf_fov121_heatmap.png', 'L0_newdata_round1', 121, 'L0 Round1 FOV #121';
    'l1_round1_median_psf_fov061_heatmap.png', 'L0_newdata_round1', 61, 'L1 Round1 FOV #61';
    'l1_round2_median_psf_fov061_heatmap.png', 'L0_newdata_round2', 61, 'L1 Round2 FOV #61';
    'l1_round3_median_psf_fov061_heatmap.png', 'L0_newdata_round3', 61, 'L1 Round3 FOV #61';
    'l1_yellow_round1_median_psf_fov011_heatmap.png', 'L0_newdata_round1', 11, 'L1 yellow-signal FOV #11';
    'l1_yellow_round1_median_psf_fov066_heatmap.png', 'L0_newdata_round1', 66, 'L1 yellow-signal FOV #66';
};

if ~exist(outDir, 'dir')
    error('Output directory does not exist: %s', outDir);
end

backupDir = fullfile(outDir, ['backup_heatmaps_before_matlab_style_' datestr(now, 'yyyymmdd_HHMMSS')]);
mkdir(backupDir);
for i = 1:size(items, 1)
    oldPath = fullfile(outDir, items{i, 1});
    if exist(oldPath, 'file')
        copyfile(oldPath, fullfile(backupDir, items{i, 1}));
    end
end

summary = struct();
summary.output_dir = outDir;
summary.backup_dir = backupDir;
summary.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
summary.crop_size = cropSize;
summary.scale = scale;
summary.style = 'MATLAB parula pixel grid, center crop, nearest-neighbor enlargement';
summary.files = strings(size(items, 1), 1);

for i = 1:size(items, 1)
    fileName = items{i, 1};
    roundName = items{i, 2};
    fov = items{i, 3};
    label = items{i, 4};

    psf = median_psf_from_trials(validationDir, roundName, fov, fovList);
    crop = center_crop(psf, cropSize);
    rgb = psf_to_parula_pixel_rgb(crop, scale);

    outPath = fullfile(outDir, fileName);
    imwrite(rgb, outPath);
    write_sidecar(outPath, label, roundName, fov, cropSize);
    summary.files(i) = string(outPath);
end

summaryPath = fullfile(outDir, 'MATLAB_STYLE_REPLACEMENT_SUMMARY.json');
fid = fopen(summaryPath, 'w');
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s', jsonencode(summary, 'PrettyPrint', true));
delete(cleanup);

fprintf('Rebuilt %d MATLAB-style PSF heatmaps.\n', size(items, 1));
fprintf('Output: %s\n', outDir);
fprintf('Backup: %s\n', backupDir);
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

function rgbBig = psf_to_parula_pixel_rgb(img, scale)
img = double(img);
img = img - min(img(:));
mx = max(img(:));
if mx > 0
    img = img ./ mx;
end
img = min(max(img, 0), 1);

cmap = parula(256);
idx = floor(img * 255) + 1;
rgb = zeros([size(idx), 3]);
for ch = 1:3
    channel = reshape(cmap(idx(:), ch), size(idx));
    rgb(:, :, ch) = channel;
end
rgbBig = repelem(rgb, scale, scale, 1);
end

function write_sidecar(outPath, label, roundName, fov, cropSize)
txtPath = [outPath '.txt'];
fid = fopen(txtPath, 'w', 'n', 'UTF-8');
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', label);
fprintf(fid, '這張圖是由 %s 的 15 次 PSF 擬合結果取中位數後產生。\n', roundName);
fprintf(fid, '呈現方式已改成 Matlab 風格的像素格圖：使用 parula 色盤、中心 %d x %d 裁切、最近鄰放大，不做平滑處理。\n', cropSize, cropSize);
fprintf(fid, '它適合用來展示擬合後 PSF 本身的形狀，而不是拿來看原始圓形影像。\n');
fprintf(fid, '對應 FOV: #%d\n', fov);
delete(cleanup);
end
