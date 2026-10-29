function build_wiener_baseline_dataset()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
%BUILD_WIENER_BASELINE_DATASET Create a fixed-PSF Wiener baseline.

packageRoot = fileparts(fileparts(mfilename('fullpath')));
projectRoot = fullfile(PROJECT_ROOT, 'PSF_Fitting');
fitRoot = fullfile(projectRoot, 'output', 'deconvolution_baseline_psf_20260715');
sourcePackage = fullfile(fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence'), ...
    'Final_Data_Figures', '01_CURRENT_THESIS_RESULTS_V42_CENTER9');
configPath = fullfile(sourcePackage, 'config', 'sequence_center9_50x20x.json');
outputRoot = fullfile(packageRoot, 'source_validation', 'wiener_baseline_20260715');
figureRoot = fullfile(outputRoot, 'calibration_figures');
tableRoot = fullfile(outputRoot, 'tables');
reconstructionRoot = fullfile(outputRoot, 'reconstructions');
staticRoot = fullfile(outputRoot, 'static_cd');
mkdir_if_needed(outputRoot);
mkdir_if_needed(figureRoot);
mkdir_if_needed(tableRoot);
mkdir_if_needed(reconstructionRoot);
mkdir_if_needed(staticRoot);

cases = struct( ...
    'label', {'20x', '50x'}, ...
    'pitchPx', {28.9855072463768, 72.4637681159420}, ...
    'objectUmPerPx', {0.1725, 0.0690}, ...
    'calibrationFrame', {25, 19}, ...
    'calibrationSequence', {'20x_1um', '50x_x_1um'});
fixedNsr = 0.050;
candidateNsr = [0.020; 0.025; 0.032; 0.040; fixedNsr; 0.063; 0.080; 0.100; 0.125];

sweepRows = table();
selectedRows = table();
caseData = struct();
for caseIndex = 1:numel(cases)
    item = cases(caseIndex);
    metaPath = fullfile(fitRoot, item.label, 'selected_frame.json');
    psfPath = fullfile(fitRoot, item.label, 'fit_result', 'PSF_fitted_2D_FOVstack.mat');
    metadata = jsondecode(fileread(metaPath));
    loaded = load(psfPath, 'psf_grid');
    psf = squeeze(double(loaded.psf_grid));
    psf = psf ./ sum(psf(:));
    calibrationImage = read_gray_double(metadata.selected_image);
    centers = double(metadata.pillar_centers_xy);
    cropRect = centers_crop_rect(centers, item.pitchPx, size(calibrationImage), 1.30);
    [calibrationCrop, centersLocal] = crop_with_centers(calibrationImage, centers, cropRect);
    noiseNsr = estimate_image_nsr(calibrationCrop, centersLocal, item.pitchPx);
    rawMetrics = measure_grid(calibrationCrop, centersLocal, item.pitchPx);

    candidateRestored = cell(numel(candidateNsr), 1);
    localRows = table();
    for candidateIndex = 1:numel(candidateNsr)
        nsr = candidateNsr(candidateIndex);
        restored = restore_dark_pillar_roi(calibrationCrop, psf, nsr, item.pitchPx);
        candidateRestored{candidateIndex} = restored;
        metrics = measure_grid(restored, centersLocal, item.pitchPx);
        safe = ~metrics.anyInverted && metrics.validPillars == 9;
        row = table(string(item.label), noiseNsr, nsr, rawMetrics.medianEdgeWidthPx, ...
            metrics.medianEdgeWidthPx, metrics.maxRingingRatio, ...
            metrics.anyInverted, safe, ...
            'VariableNames', {'magnification','noise_estimated_nsr','candidate_nsr', ...
            'raw_median_edge_width_px','restored_median_edge_width_px', ...
            'restored_max_ringing_ratio','restored_any_inverted','safe_candidate'});
        localRows = [localRows; row]; %#ok<AGROW>
    end
    selectedIndex = find(abs(localRows.candidate_nsr - fixedNsr) < 1e-12, 1, 'first');
    assert(~isempty(selectedIndex) && localRows.safe_candidate(selectedIndex), ...
        'The fixed visually sharp Wiener setting must preserve all nine dark pillars.');
    selectionStatus = "fixed_nsr_0p05_visual_sharpness_baseline";
    selectedNsr = localRows.candidate_nsr(selectedIndex);
    localRows.selected = false(height(localRows), 1);
    localRows.selected(selectedIndex) = true;
    localRows.selection_status = repmat(selectionStatus, height(localRows), 1);
    sweepRows = [sweepRows; localRows]; %#ok<AGROW>
    selectedRows = [selectedRows; table(string(item.label), ...
        string(item.calibrationSequence), item.calibrationFrame, ...
        string(metadata.selected_image), mean(centers(:, 1)), mean(centers(:, 2)), ...
        noiseNsr, selectedNsr, string(selectionStatus), ...
        'VariableNames', {'magnification','calibration_sequence','calibration_frame', ...
        'calibration_image','pillar_center_x_px','pillar_center_y_px', ...
        'noise_estimated_nsr','selected_nsr','selection_status'})]; %#ok<AGROW>

    make_calibration_figure(calibrationCrop, candidateRestored{selectedIndex}, ...
        localRows, selectedIndex, item, fullfile(figureRoot, ...
        sprintf('%s_wiener_calibration.png', item.label)));
    caseKey = ['m' item.label];
    caseData.(caseKey) = struct('psf', psf, 'nsr', selectedNsr, ...
        'pitchPx', item.pitchPx, 'meta', metadata);
end
writetable(sweepRows, fullfile(tableRoot, 'wiener_nsr_calibration_sweep.csv'));
writetable(selectedRows, fullfile(tableRoot, 'wiener_selected_nsr.csv'));

configPayload = jsondecode(fileread(configPath));
sequenceNames = fieldnames(configPayload.sequences);
for sequenceIndex = 1:numel(sequenceNames)
    sequenceName = sequenceNames{sequenceIndex};
    sequence = configPayload.sequences.(sequenceName);
    label = char(sequence.magnification);
    data = caseData.(['m' label]);
    outputDir = fullfile(reconstructionRoot, sequenceName);
    mkdir_if_needed(outputDir);
    centers0 = centers_from_json(sequence.centers);
    expectedShift = [double(sequence.expected_signed_dx_px), 0];
    frameCount = double(sequence.frame_count);
    roiRect = sequence_sweep_rect(centers0, expectedShift, frameCount, ...
        data.pitchPx, [1536 2048]);
    for frameIndex = 0:(frameCount - 1)
        imagePath = fullfile(PROJECT_ROOT, sequence.raw_dir, sprintf('frame_%04d.bmp', frameIndex));
        imageData = read_gray_double(imagePath);
        restored = restore_fixed_roi(imageData, roiRect, data.psf, data.nsr, data.pitchPx);
        imwrite(im2uint8(min(max(restored, 0), 1)), ...
            fullfile(outputDir, sprintf('frame_%04d.bmp', frameIndex)));
    end
end

staticRawPath = fullfile(fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence'), ...
    '20260618_100MG', 'Image__2026-06-18__17-10-31.bmp');
staticTablePath = fullfile(sourcePackage, 'cd', 'tables', 'center9_cd_per_pillar.csv');
staticTable = readtable(staticTablePath, 'Delimiter', ',', 'TextType', 'string', ...
    'VariableNamingRule', 'preserve');
staticCenters = [double(staticTable.("raw_x_px")), double(staticTable.("raw_y_px"))];
staticRaw = read_gray_double(staticRawPath);
staticRect = centers_crop_rect(staticCenters, caseData.m50x.pitchPx, size(staticRaw), 2.0);
staticRestored = restore_fixed_roi(staticRaw, staticRect, caseData.m50x.psf, ...
    caseData.m50x.nsr, caseData.m50x.pitchPx);
staticOutputPath = fullfile(staticRoot, 'Image__2026-06-18__17-10-31_wiener.bmp');
imwrite(im2uint8(min(max(staticRestored, 0), 1)), staticOutputPath);

manifest = struct();
manifest.method = ['background-normalized Wiener deconvolution with symmetric padding, ', ...
    'edge tapering, and a nonnegative restored-contrast constraint'];
manifest.psf_rule = ['One designated calibration-frame PSF per magnification; ', ...
    'the same PSF is used for both displacement amplitudes.'];
manifest.nsr_rule = ['Use fixed NSR 0.05 for both magnifications after a calibration-only ', ...
    'visual sharpness sweep. Moderate ringing is intentionally retained as a visible ', ...
    'traditional-deconvolution limitation; no CD or displacement result enters selection.'];
manifest.evaluation_scope = ['Calibration frames are outside the formal top-30 displacement lists, ', ...
    'and no CD or displacement result is used for PSF or NSR selection. ', ...
    'The comparison is a same-system consistency validation, not a cross-domain generalization test.'];
manifest.roi_rule = ['A fixed sequence ROI covers the full nominal pillar path; ', ...
    'pixels outside that ROI remain Raw and are not used by the center-nine measurement.'];
manifest.psf_root = fitRoot;
manifest.config_path = configPath;
manifest.static_cd_raw = staticRawPath;
manifest.static_cd_wiener = staticOutputPath;
manifest.selected_nsr_table = fullfile(tableRoot, 'wiener_selected_nsr.csv');
manifest.calibration_sweep_table = fullfile(tableRoot, 'wiener_nsr_calibration_sweep.csv');
manifest.generated_at = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
write_json(fullfile(outputRoot, 'wiener_manifest.json'), manifest);
fprintf('Wiener baseline dataset completed: %s\n', outputRoot);
end

function rect = sequence_sweep_rect(centers0, expectedShift, frameCount, pitchPx, imageSize)
lastCenters = centers0 + (frameCount - 1) .* expectedShift;
allCenters = [centers0; lastCenters];
rect = centers_crop_rect(allCenters, pitchPx, imageSize, 2.0);
end

function rect = centers_crop_rect(centers, pitchPx, imageSize, marginPitch)
margin = marginPitch * pitchPx;
x1 = max(1, floor(min(centers(:, 1)) - margin));
x2 = min(imageSize(2), ceil(max(centers(:, 1)) + margin));
y1 = max(1, floor(min(centers(:, 2)) - margin));
y2 = min(imageSize(1), ceil(max(centers(:, 2)) + margin));
rect = [x1 y1 x2 y2];
end

function restored = restore_fixed_roi(imageData, rect, psf, nsr, pitchPx)
x1 = rect(1); y1 = rect(2); x2 = rect(3); y2 = rect(4);
roi = imageData(y1:y2, x1:x2);
restoredRoi = restore_dark_pillar_roi(roi, psf, nsr, pitchPx);
restored = imageData;
restored(y1:y2, x1:x2) = restoredRoi;
end

function restored = restore_dark_pillar_roi(imageData, psf, nsr, pitchPx)
backgroundRadius = max(2, ceil(0.36 * pitchPx));
background = imclose(imageData, strel('disk', backgroundRadius));
contrast = max(background - imageData, 0);
contrastScale = prctile(contrast(:), 99.5);
contrast = contrast ./ max(contrastScale, eps);
padY = floor(size(psf, 1) / 2);
padX = floor(size(psf, 2) / 2);
padded = padarray(contrast, [padY padX], 'symmetric', 'both');
padded = edgetaper(padded, psf);
restoredPadded = deconvwnr(padded, psf, nsr);
restoredContrast = restoredPadded(padY + 1:padY + size(imageData, 1), ...
    padX + 1:padX + size(imageData, 2));
restoredContrast = min(max(restoredContrast, 0), 1.25);
restored = background - contrastScale .* restoredContrast;
end

function metrics = measure_grid(imageData, centers, pitchPx)
radialStep = 0.05;
radii = 0:radialStep:(0.38 * pitchPx);
angles = linspace(0, 2 * pi, 361); angles(end) = [];
widths = nan(size(centers, 1), 1);
ringing = nan(size(centers, 1), 1);
inverted = false(size(centers, 1), 1);
for centerIndex = 1:size(centers, 1)
    x = centers(centerIndex, 1) + cos(angles(:)) .* radii;
    y = centers(centerIndex, 2) + sin(angles(:)) .* radii;
    samples = interp2(imageData, x, y, 'cubic');
    samples = smoothdata(samples, 2, 'gaussian', 13);
    coreLevel = median(samples(:, radii <= 0.07 * pitchPx), 'all');
    backgroundLevel = median(samples(:, radii >= 0.30 * pitchPx & radii <= 0.36 * pitchPx), 'all');
    inverted(centerIndex) = coreLevel >= backgroundLevel;
    r10 = crossing_radii(samples, radii, coreLevel + 0.10 * (backgroundLevel - coreLevel));
    r90 = crossing_radii(samples, radii, coreLevel + 0.90 * (backgroundLevel - coreLevel));
    valid = isfinite(r10) & isfinite(r90) & r90 >= r10;
    if nnz(valid) >= 324
        widths(centerIndex) = median(r90(valid) - r10(valid));
    end
    medianProfile = median(samples, 1);
    normalized = (medianProfile - coreLevel) ./ max(backgroundLevel - coreLevel, eps);
    changes = diff(normalized(radii <= 0.30 * pitchPx));
    outwardRise = sum(changes(changes > 0));
    inwardDip = -sum(changes(changes < 0));
    ringing(centerIndex) = inwardDip ./ max(outwardRise, eps);
end
metrics = struct('medianEdgeWidthPx', median(widths, 'omitnan'), ...
    'maxRingingRatio', max(ringing, [], 'omitnan'), ...
    'anyInverted', any(inverted), 'validPillars', nnz(isfinite(widths)));
end

function crossings = crossing_radii(samples, radii, threshold)
crossings = nan(size(samples, 1), 1);
for rowIndex = 1:size(samples, 1)
    profile = samples(rowIndex, :);
    index = find(profile >= threshold, 1, 'first');
    if isempty(index) || index == 1, continue; end
    y0 = profile(index - 1); y1 = profile(index);
    if y1 == y0
        crossings(rowIndex) = radii(index);
    else
        fraction = (threshold - y0) ./ (y1 - y0);
        crossings(rowIndex) = radii(index - 1) + fraction .* (radii(index) - radii(index - 1));
    end
end
end

function nsr = estimate_image_nsr(imageData, centers, pitchPx)
[yy, xx] = ndgrid(1:size(imageData, 1), 1:size(imageData, 2));
backgroundMask = true(size(imageData));
excludeRadius = 0.27 * pitchPx;
for centerIndex = 1:size(centers, 1)
    backgroundMask = backgroundMask & ((xx - centers(centerIndex, 1)).^2 + ...
        (yy - centers(centerIndex, 2)).^2 > excludeRadius^2);
end
dx = imageData(:, 2:end) - imageData(:, 1:end-1);
mx = backgroundMask(:, 2:end) & backgroundMask(:, 1:end-1);
dy = imageData(2:end, :) - imageData(1:end-1, :);
my = backgroundMask(2:end, :) & backgroundMask(1:end-1, :);
differences = [dx(mx); dy(my)];
differenceMedian = median(differences);
noiseSigma = median(abs(differences - differenceMedian)) / 0.6744897501960817 / sqrt(2);
signalVariance = max(var(imageData(:), 1) - noiseSigma^2, eps);
nsr = noiseSigma^2 / signalVariance;
end

function make_calibration_figure(rawImage, restoredImage, rows, selectedIndex, item, outputPath)
figureHandle = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1240 420]);
tiledlayout(figureHandle, 1, 3, 'TileSpacing', 'compact', 'Padding', 'compact');
    nexttile; imagesc(rawImage, [0 1]); axis image off; colormap gray;
    title(sprintf('%s held-out calibration image', strrep(item.label, 'x', ' x ')));
    nexttile; imagesc(restoredImage, [0 1]); axis image off;
    title(sprintf('Selected Wiener result (NSR %.4g)', rows.candidate_nsr(selectedIndex)));
nexttile;
yyaxis left;
semilogx(rows.candidate_nsr, rows.restored_median_edge_width_px, '-o', ...
    'Color', [0.10 0.45 0.70], 'LineWidth', 1.5, 'MarkerFaceColor', [0.10 0.45 0.70]);
ylabel('Median 10-90% width (pixels)');
yyaxis right;
semilogx(rows.candidate_nsr, rows.restored_max_ringing_ratio, '-s', ...
    'Color', [0.70 0.25 0.10], 'LineWidth', 1.5, 'MarkerFaceColor', [0.70 0.25 0.10]);
    ylabel('Maximum ringing ratio'); xlabel('Wiener NSR'); grid on;
xline(rows.candidate_nsr(selectedIndex), ':', 'Selected', 'LineWidth', 1.3);
title('Calibration-only regularization sweep');
set(findall(figureHandle, '-property', 'FontName'), 'FontName', 'Times New Roman');
set(findall(figureHandle, '-property', 'FontSize'), 'FontSize', 10);
exportgraphics(figureHandle, outputPath, 'Resolution', 220);
close(figureHandle);
end

function [crop, centersLocal] = crop_with_centers(imageData, centers, rect)
crop = imageData(rect(2):rect(4), rect(1):rect(3));
centersLocal = centers - [rect(1) - 1, rect(2) - 1];
end

function centers = centers_from_json(payload)
values = double(payload);
centers = values(:, 2:3);
end

function imageData = read_gray_double(path)
imageData = im2double(imread(path));
if size(imageData, 3) > 1, imageData = rgb2gray(imageData); end
end

function mkdir_if_needed(path)
if ~exist(path, 'dir'), mkdir(path); end
end

function write_json(path, payload)
fid = fopen(path, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(payload, PrettyPrint = true));
end
