function Run_Thesis_3Mag_EdgePhase_SelectROI(varargin)
% Open this file in MATLAB and press Run.
% It builds the thesis 50x/20x/5x manual ROI edge-phase displacement package.

clc;

scriptDir = fileparts(mfilename('fullpath'));
legacyDir = fullfile(scriptDir, 'phase_correlation_dft', 'legacy_matlab');
addpath(legacyDir);

cfg = parseInputs(varargin{:});
if exist(legacyDir, 'dir') ~= 7 || exist('dftregistration', 'file') ~= 2
    error('Cannot find dftregistration.m under: %s', legacyDir);
end

cases = buildCases();
cases = keepExistingCases(cases);
if isempty(cases)
    error('No valid image cases were found.');
end
if isfinite(cfg.maxCases)
    cases = cases(1:min(numel(cases), cfg.maxCases));
end

prepareOutputFolders(cfg.outputRoot);

fprintf('\n=== Thesis 3-magnification edge-phase displacement package ===\n');
fprintf('Output root : %s\n', cfg.outputRoot);
fprintf('Cases       : %d\n', numel(cases));
fprintf('ROI mode    : %s\n\n', roiModeLabel(cfg));

roiByKey = containers.Map('KeyType', 'char', 'ValueType', 'any');
summaryRows = struct([]);
runResults = struct([]);
resultIndex = 0;

for caseIndex = 1:numel(cases)
    item = cases(caseIndex);
    imageFiles = listImageFiles(item.imageDir);
    caseOutputDir = fullfile(cfg.outputRoot, 'manual_roi_runs', item.caseName);
    if exist(caseOutputDir, 'dir') ~= 7
        mkdir(caseOutputDir);
    end
    stepsCsv = fullfile(caseOutputDir, 'edge_phase_steps.csv');
    summaryJson = fullfile(caseOutputDir, 'edge_phase_summary.json');
    roiPreviewPng = fullfile(caseOutputDir, 'roi_preview.png');
    plotPng = fullfile(caseOutputDir, 'edge_phase_steps.png');

    if cfg.resumeExisting && exist(stepsCsv, 'file') == 2 && exist(summaryJson, 'file') == 2
        summary = readJsonFile(summaryJson);
        if isfield(summary, 'roi_x_y_width_height')
            roiByKey(item.group) = double(summary.roi_x_y_width_height(:).');
        end
        resultIndex = resultIndex + 1;
        currentRunResult = makeRunResult(item, summary, stepsCsv, summaryJson, roiPreviewPng, plotPng);
        currentSummaryRow = makeSummaryRow(item, summary);
        if resultIndex == 1
            runResults = currentRunResult;
            summaryRows = currentSummaryRow;
        else
            runResults(resultIndex) = currentRunResult;
            summaryRows(resultIndex) = currentSummaryRow;
        end
        fprintf('[%02d/%02d] %s | existing result found, skipped and reused\n', ...
            caseIndex, numel(cases), item.caseName);
        continue;
    end

    firstImage = readGrayDouble(fullfile(imageFiles(1).folder, imageFiles(1).name));
    roiKey = item.group;
    if cfg.selectRoiPerVariant
        roiKey = item.caseName;
    end

    if ~isempty(cfg.autoRoi)
        roi = cfg.autoRoi;
    elseif isKey(roiByKey, roiKey)
        roi = roiByKey(roiKey);
    else
        fprintf('[%02d/%02d] Waiting for manual ROI selection: %s\n', ...
            caseIndex, numel(cases), item.caseName);
        roi = selectRoiFromImage(firstImage, item.caseName, cfg.showFigures);
        roiByKey(roiKey) = roi;
    end
    roi = clipRoi(roi, size(firstImage));
    roiByKey(roiKey) = roi;

    fprintf('[%02d/%02d] %s | images=%d | ROI=[%d %d %d %d]\n', ...
        caseIndex, numel(cases), item.caseName, numel(imageFiles), roi(1), roi(2), roi(3), roi(4));

    [stepsTable, summary] = measureEdgePhaseSequence(imageFiles, roi, item, cfg);

    writetable(stepsTable, stepsCsv);
    writeJsonFile(summaryJson, summary);
    writeRoiPreview(firstImage, roi, roiPreviewPng);
    writeSequencePlot(stepsTable, item.expectedStepUm, plotPng, item.caseName);

    resultIndex = resultIndex + 1;
    currentRunResult = makeRunResult(item, summary, stepsCsv, summaryJson, roiPreviewPng, plotPng);
    currentSummaryRow = makeSummaryRow(item, summary);
    if resultIndex == 1
        runResults = currentRunResult;
        summaryRows = currentSummaryRow;
    else
        runResults(resultIndex) = currentRunResult;
        summaryRows(resultIndex) = currentSummaryRow;
    end
end

summaryTable = struct2table(summaryRows);
summaryCsv = fullfile(cfg.outputRoot, 'final_tables', 'edge_phase_summary.csv');
writetable(summaryTable, summaryCsv);

comparisonTable = buildRawVsR61Comparison(summaryTable);
comparisonCsv = fullfile(cfg.outputRoot, 'final_tables', 'edge_phase_raw_vs_r61_comparison.csv');
writetable(comparisonTable, comparisonCsv);

writeSummaryFigure(summaryTable, fullfile(cfg.outputRoot, 'figures', 'edge_phase_summary.png'));
writeSourceCases(cases, fullfile(cfg.outputRoot, 'source_manifest', 'source_cases.csv'));
writeReadme(cfg.outputRoot);

manifest = struct();
manifest.algorithm = 'manual ROI edge-enhanced MATLAB dftregistration';
manifest.output_root = cfg.outputRoot;
manifest.case_count = numel(cases);
manifest.upsample_factor = cfg.upsampleFactor;
manifest.hann_window = cfg.useHann;
manifest.edge_sigma_px = cfg.edgeSigmaPx;
manifest.gap_limit_seconds = cfg.gapLimitSeconds;
manifest.select_roi_per_variant = cfg.selectRoiPerVariant;
manifest.resume_existing = cfg.resumeExisting;
manifest.results = runResults;
manifest.summary_csv = summaryCsv;
manifest.comparison_csv = comparisonCsv;
writeJsonFile(fullfile(cfg.outputRoot, 'source_manifest', 'run_manifest.json'), manifest);

fprintf('\nFinished. Thesis package output:\n%s\n', cfg.outputRoot);
fprintf('Main summary table:\n%s\n', summaryCsv);
fprintf('Raw/R61 comparison table:\n%s\n\n', comparisonCsv);
end

function cfg = parseInputs(varargin)
    PROJECT_ROOT = fileparts(fileparts(fileparts(mfilename('fullpath'))));
p = inputParser;
p.addParameter('outputRoot', fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Displacement_3Mag_ManualRun_20260705'));
p.addParameter('upsampleFactor', 100);
p.addParameter('useHann', true);
p.addParameter('edgeSigmaPx', 1.0);
p.addParameter('gapLimitSeconds', 30);
p.addParameter('selectRoiPerVariant', false);
p.addParameter('autoRoi', []);
p.addParameter('maxCases', Inf);
p.addParameter('showFigures', true);
p.addParameter('resumeExisting', true);
p.parse(varargin{:});
cfg = p.Results;
if ~isempty(cfg.autoRoi)
    cfg.autoRoi = round(double(cfg.autoRoi(:).'));
    if numel(cfg.autoRoi) ~= 4
        error('autoRoi must be [x y width height].');
    end
end
end

function label = roiModeLabel(cfg)
if ~isempty(cfg.autoRoi)
    label = 'fixed autoRoi test mode';
elseif cfg.selectRoiPerVariant
    label = 'manual ROI for every Raw/R61 case';
else
    label = 'manual ROI on the first case of each group, reused for matching Raw/R61';
end
end

function prepareOutputFolders(outputRoot)
folders = {
    outputRoot
    fullfile(outputRoot, 'source_manifest')
    fullfile(outputRoot, 'manual_roi_runs')
    fullfile(outputRoot, 'final_tables')
    fullfile(outputRoot, 'figures')
    };
for idx = 1:numel(folders)
    if exist(folders{idx}, 'dir') ~= 7
        mkdir(folders{idx});
    end
end
end

function cases = buildCases()
    PROJECT_ROOT = fileparts(fileparts(fileparts(mfilename('fullpath'))));
cases = makeCase('50x_1um', 50, 1.0, 'raw', 'Raw', ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/input_mapping.csv'), 'x_1um');
cases(end + 1) = makeCase('50x_1um', 50, 1.0, 'r61_v16_psfoff', 'R61 v16 PSF-off', ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/r61_v16_psfoff_x_1um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/input_mapping.csv'), 'x_1um');
cases(end + 1) = makeCase('50x_0p5um', 50, 0.5, 'raw', 'Raw', ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/input_mapping.csv'), 'x_0p5um');
cases(end + 1) = makeCase('50x_0p5um', 50, 0.5, 'r61_v16_psfoff', 'R61 v16 PSF-off', ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/r61_v16_psfoff_x_0p5um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/input_mapping.csv'), 'x_0p5um');

cases(end + 1) = makeCase('20x_1um', 20, 1.0, 'raw', 'Raw', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '20x_1um');
cases(end + 1) = makeCase('20x_1um', 20, 1.0, 'r61_v16_psfoff', 'R61 v16 PSF-off', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/r61_v16_psfoff_20x_1um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '20x_1um');
cases(end + 1) = makeCase('20x_0p5um', 20, 0.5, 'raw', 'Raw', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/raw_inputs/20x_0p5um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '20x_0p5um');
cases(end + 1) = makeCase('20x_0p5um', 20, 0.5, 'r61_v16_psfoff', 'R61 v16 PSF-off', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/r61_v16_psfoff_20x_0p5um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '20x_0p5um');

cases(end + 1) = makeCase('5x_1um', 5, 1.0, 'raw', 'Raw', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/raw_inputs/5x_1um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '5x_1um');
cases(end + 1) = makeCase('5x_1um', 5, 1.0, 'r61_v16_psfoff', 'R61 v16 PSF-off', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/r61_v16_psfoff_5x_1um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '5x_1um');
cases(end + 1) = makeCase('5x_0p5um', 5, 0.5, 'raw', 'Raw', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/raw_inputs/5x_0p5um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '5x_0p5um');
cases(end + 1) = makeCase('5x_0p5um', 5, 0.5, 'r61_v16_psfoff', 'R61 v16 PSF-off', ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/r61_v16_psfoff_5x_0p5um/bmp'), ...
    fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/input_mapping.csv'), '5x_0p5um');
end

function item = makeCase(group, magnification, expectedStepUm, variant, imageLabel, imageDir, mappingCsv, mappingGroup)
cameraPixelUm = 3.45;
item = struct();
item.group = group;
item.magnification = magnification;
item.expectedStepUm = expectedStepUm;
item.variant = variant;
item.imageLabel = imageLabel;
item.imageDir = imageDir;
item.mappingCsv = mappingCsv;
item.mappingGroup = mappingGroup;
item.pixelSizeUm = cameraPixelUm / magnification;
item.expectedDxPx = expectedStepUm / item.pixelSizeUm;
item.caseName = safeName(sprintf('%s_%s', group, variant));
end

function result = makeRunResult(item, summary, stepsCsv, summaryJson, roiPreviewPng, plotPng)
result = struct();
result.case = item.caseName;
result.group = item.group;
result.magnification = item.magnification;
result.variant = item.variant;
result.image_dir = item.imageDir;
result.image_count = fieldOr(summary, 'image_count', NaN);
result.roi_x_y_width_height = fieldOr(summary, 'roi_x_y_width_height', [NaN, NaN, NaN, NaN]);
result.steps_csv = stepsCsv;
result.summary_json = summaryJson;
result.roi_preview = roiPreviewPng;
result.plot_png = plotPng;
end

function row = makeSummaryRow(item, summary)
roi = fieldOr(summary, 'roi_x_y_width_height', [NaN, NaN, NaN, NaN]);
roi = double(roi(:).');
if numel(roi) < 4
    roi = [NaN, NaN, NaN, NaN];
end

row = struct();
row.case = string(item.caseName);
row.group = string(item.group);
row.magnification = item.magnification;
row.variant = string(item.variant);
row.image_label = string(item.imageLabel);
row.image_count = fieldOr(summary, 'image_count', NaN);
row.valid_step_count = fieldOr(summary, 'valid_step_count', NaN);
row.gap30_step_count = fieldOr(summary, 'gap30_step_count', NaN);
row.pixel_size_um = item.pixelSizeUm;
row.expected_step_um = item.expectedStepUm;
row.median_abs_dx_um_gap30 = fieldOr(summary, 'median_abs_dx_um_gap30', NaN);
row.mean_abs_dx_um_gap30 = fieldOr(summary, 'mean_abs_dx_um_gap30', NaN);
row.std_abs_dx_um_gap30 = fieldOr(summary, 'std_abs_dx_um_gap30', NaN);
row.median_abs_error_um_gap30 = fieldOr(summary, 'median_abs_error_um_gap30', NaN);
row.median_abs_dy_um_gap30 = fieldOr(summary, 'median_abs_dy_um_gap30', NaN);
row.median_abs_dx_px_gap30 = fieldOr(summary, 'median_abs_dx_px_gap30', NaN);
row.std_abs_dx_px_gap30 = fieldOr(summary, 'std_abs_dx_px_gap30', NaN);
row.roi_x = roi(1);
row.roi_y = roi(2);
row.roi_width = roi(3);
row.roi_height = roi(4);
end

function value = fieldOr(payload, fieldName, fallback)
if isstruct(payload) && isfield(payload, fieldName)
    value = payload.(fieldName);
else
    value = fallback;
end
end

function cases = keepExistingCases(cases)
keep = false(1, numel(cases));
for idx = 1:numel(cases)
    keep(idx) = exist(cases(idx).imageDir, 'dir') == 7 && numel(listImageFiles(cases(idx).imageDir)) >= 2;
    if ~keep(idx)
        warning('Skipping missing or too-small case: %s', cases(idx).imageDir);
    end
end
cases = cases(keep);
end

function files = listImageFiles(folder)
patterns = {'*.bmp', '*.png', '*.jpg', '*.jpeg', '*.tif', '*.tiff'};
files = [];
for idx = 1:numel(patterns)
    found = dir(fullfile(folder, patterns{idx}));
    files = [files; found(:)]; %#ok<AGROW>
end
if isempty(files)
    files = struct('name', {}, 'folder', {}, 'date', {}, 'bytes', {}, 'isdir', {}, 'datenum', {});
    return;
end
[~, order] = sort(lower(string({files.name})));
files = files(order);
end

function image = readGrayDouble(path)
raw = imread(path);
if ndims(raw) == 3
    image = mean(double(raw), 3);
else
    image = double(raw);
end
end

function roi = selectRoiFromImage(image, caseName, showFigures)
if ~showFigures
    error('Interactive ROI selection requires showFigures=true or a supplied autoRoi.');
end
fig = figure('Name', sprintf('Select ROI - %s', caseName), 'Color', 'w');
try
    movegui(fig, 'center');
    figure(fig);
catch
end
if exist('imshow', 'file') == 2
    imshow(image, []);
else
    imagesc(image);
    axis image off;
    colormap gray;
end
title(sprintf('%s: drag ROI and release mouse to confirm', caseName), 'Interpreter', 'none');
drawnow;
try
    roi = round(getrect(gca));
catch err
    if isvalid(fig)
        close(fig);
    end
    rethrow(err);
end
if numel(roi) ~= 4 || roi(3) <= 0 || roi(4) <= 0
    if isvalid(fig)
        close(fig);
    end
    error('ROI selection was cancelled or empty for %s.', caseName);
end
if isvalid(fig)
    close(fig);
end
end

function roi = clipRoi(roi, imageSize)
imageHeight = imageSize(1);
imageWidth = imageSize(2);
x = max(1, min(round(roi(1)), imageWidth));
y = max(1, min(round(roi(2)), imageHeight));
w = max(1, round(roi(3)));
h = max(1, round(roi(4)));
w = min(w, imageWidth - x + 1);
h = min(h, imageHeight - y + 1);
roi = [x, y, w, h];
end

function [stepsTable, summary] = measureEdgePhaseSequence(files, roi, item, cfg)
n = numel(files);
frameIndex = (0:n - 1).';
filename = strings(n, 1);
refFilename = strings(n, 1);
timeGapS = nan(n, 1);
gapLe30s = true(n, 1);
dxPx = nan(n, 1);
dyPx = nan(n, 1);
absDxPx = nan(n, 1);
absDyPx = nan(n, 1);
absDxUm = nan(n, 1);
absDyUm = nan(n, 1);
signedDxUm = nan(n, 1);
stepDistancePx = nan(n, 1);
stepDistanceUm = nan(n, 1);
cumulativeDxPx = nan(n, 1);
cumulativeDyPx = nan(n, 1);
registrationError = nan(n, 1);
phaseDiff = nan(n, 1);
status = strings(n, 1);
message = strings(n, 1);

timestampByName = loadTimestampMap(item.mappingCsv, item.mappingGroup);
firstImage = prepareEdgeImage(fullfile(files(1).folder, files(1).name), roi, cfg);
previousImage = firstImage;
cumulativeDx = 0;
cumulativeDy = 0;

filename(1) = string(files(1).name);
refFilename(1) = "";
timeGapS(1) = 0;
gapLe30s(1) = true;
dxPx(1) = 0;
dyPx(1) = 0;
absDxPx(1) = 0;
absDyPx(1) = 0;
absDxUm(1) = 0;
absDyUm(1) = 0;
signedDxUm(1) = 0;
stepDistancePx(1) = 0;
stepDistanceUm(1) = 0;
cumulativeDxPx(1) = 0;
cumulativeDyPx(1) = 0;
registrationError(1) = 0;
phaseDiff(1) = 0;
status(1) = "reference";
message(1) = "";

for idx = 2:n
    currentPath = fullfile(files(idx).folder, files(idx).name);
    currentImage = prepareEdgeImage(currentPath, roi, cfg);
    filename(idx) = string(files(idx).name);
    refFilename(idx) = string(files(idx - 1).name);
    timeGapS(idx) = timestampGap(timestampByName, files(idx - 1).name, files(idx).name);
    gapLe30s(idx) = isnan(timeGapS(idx)) || timeGapS(idx) <= cfg.gapLimitSeconds;
    try
        [dx, dy, err, ph] = dftDisplacement(previousImage, currentImage, cfg.upsampleFactor);
        cumulativeDx = cumulativeDx + dx;
        cumulativeDy = cumulativeDy + dy;

        dxPx(idx) = dx;
        dyPx(idx) = dy;
        absDxPx(idx) = abs(dx);
        absDyPx(idx) = abs(dy);
        absDxUm(idx) = abs(dx) * item.pixelSizeUm;
        absDyUm(idx) = abs(dy) * item.pixelSizeUm;
        signedDxUm(idx) = dx * item.pixelSizeUm;
        stepDistancePx(idx) = hypot(dx, dy);
        stepDistanceUm(idx) = stepDistancePx(idx) * item.pixelSizeUm;
        cumulativeDxPx(idx) = cumulativeDx;
        cumulativeDyPx(idx) = cumulativeDy;
        registrationError(idx) = err;
        phaseDiff(idx) = ph;
        status(idx) = "ok";
        message(idx) = "";
    catch err
        status(idx) = "error";
        message(idx) = string(err.message);
    end
    previousImage = currentImage;
end

expectedStepUm = repmat(item.expectedStepUm, n, 1);
expectedDxPx = repmat(item.expectedDxPx, n, 1);
absErrorUm = abs(absDxUm - expectedStepUm);

stepsTable = table(frameIndex, filename, refFilename, timeGapS, gapLe30s, ...
    dxPx, dyPx, absDxPx, absDyPx, absDxUm, absDyUm, signedDxUm, ...
    stepDistancePx, stepDistanceUm, cumulativeDxPx, cumulativeDyPx, ...
    registrationError, phaseDiff, expectedStepUm, expectedDxPx, absErrorUm, ...
    status, message);
stepsTable.Properties.VariableNames = {'frame_index', 'filename', 'ref_filename', ...
    'time_gap_s', 'gap_le_30s', 'dx_px', 'dy_px', 'abs_dx_px', 'abs_dy_px', ...
    'abs_dx_um', 'abs_dy_um', 'signed_dx_um', 'step_distance_px', ...
    'step_distance_um', 'cumulative_dx_px', 'cumulative_dy_px', ...
    'registration_error', 'phase_diff', 'expected_step_um', 'expected_dx_px', ...
    'abs_error_um', 'status', 'message'};

valid = status == "ok" & frameIndex > 0;
gapValid = valid & gapLe30s;
summary = struct();
summary.case = item.caseName;
summary.group = item.group;
summary.magnification = item.magnification;
summary.variant = item.variant;
summary.image_label = item.imageLabel;
summary.image_count = n;
summary.valid_step_count = sum(valid);
summary.gap30_step_count = sum(gapValid);
summary.pixel_size_um = item.pixelSizeUm;
summary.expected_step_um = item.expectedStepUm;
summary.expected_dx_px = item.expectedDxPx;
summary.roi_x_y_width_height = roi;
summary.upsample_factor = cfg.upsampleFactor;
summary.hann_window = cfg.useHann;
summary.edge_sigma_px = cfg.edgeSigmaPx;
summary.gap_limit_seconds = cfg.gapLimitSeconds;
summary.median_abs_dx_px_gap30 = median(absDxPx(gapValid), 'omitnan');
summary.mean_abs_dx_px_gap30 = mean(absDxPx(gapValid), 'omitnan');
summary.std_abs_dx_px_gap30 = std(absDxPx(gapValid), 'omitnan');
summary.median_abs_dx_um_gap30 = median(absDxUm(gapValid), 'omitnan');
summary.mean_abs_dx_um_gap30 = mean(absDxUm(gapValid), 'omitnan');
summary.std_abs_dx_um_gap30 = std(absDxUm(gapValid), 'omitnan');
summary.median_abs_error_um_gap30 = median(absErrorUm(gapValid), 'omitnan');
summary.mean_abs_error_um_gap30 = mean(absErrorUm(gapValid), 'omitnan');
summary.median_abs_dy_um_gap30 = median(absDyUm(gapValid), 'omitnan');
summary.mean_abs_dy_um_gap30 = mean(absDyUm(gapValid), 'omitnan');
summary.std_abs_dy_um_gap30 = std(absDyUm(gapValid), 'omitnan');
end

function image = prepareEdgeImage(path, roi, cfg)
image = readGrayDouble(path);
x = roi(1);
y = roi(2);
w = roi(3);
h = roi(4);
image = image(y:y + h - 1, x:x + w - 1);
image = edgeEnhance(image, cfg.edgeSigmaPx);
image = image - mean(image(:), 'omitnan');
scale = std(image(:), 'omitnan');
if scale > 1e-9
    image = image / scale;
end
if cfg.useHann
    wy = localHann(size(image, 1));
    wx = localHann(size(image, 2)).';
    image = image .* (wy * wx);
end
end

function edgeImage = edgeEnhance(image, sigmaPx)
image = double(image);
if sigmaPx > 0
    kernel = gaussianKernel1d(sigmaPx);
    image = conv2(conv2(image, kernel, 'same'), kernel.', 'same');
end
sobelX = [-1 0 1; -2 0 2; -1 0 1] / 8;
sobelY = sobelX.';
gx = conv2(image, sobelX, 'same');
gy = conv2(image, sobelY, 'same');
edgeImage = hypot(gx, gy);
end

function kernel = gaussianKernel1d(sigmaPx)
radius = max(1, ceil(3 * sigmaPx));
x = -radius:radius;
kernel = exp(-(x .^ 2) / (2 * sigmaPx ^ 2));
kernel = kernel / sum(kernel);
kernel = kernel(:);
end

function [dx, dy, registrationError, phaseDifference] = dftDisplacement(referenceImage, movingImage, upsampleFactor)
output = dftregistration(fft2(referenceImage), fft2(movingImage), upsampleFactor);
registrationError = output(1);
phaseDifference = output(2);
alignDy = output(3);
alignDx = output(4);
dy = -alignDy;
dx = -alignDx;
end

function w = localHann(n)
if n <= 1
    w = ones(n, 1);
else
    k = (0:n - 1).';
    w = 0.5 - 0.5 * cos(2 * pi * k / (n - 1));
end
end

function timestampByName = loadTimestampMap(mappingCsv, mappingGroup)
timestampByName = containers.Map('KeyType', 'char', 'ValueType', 'any');
if exist(mappingCsv, 'file') ~= 2
    return;
end
try
    mapping = readtable(mappingCsv, 'TextType', 'string');
catch
    return;
end
required = {'group', 'work_name', 'timestamp'};
if ~all(ismember(required, mapping.Properties.VariableNames))
    return;
end
rows = mapping.group == string(mappingGroup);
mapping = mapping(rows, :);
for idx = 1:height(mapping)
    name = char(mapping.work_name(idx));
    stamp = char(mapping.timestamp(idx));
    if isempty(name) || isempty(stamp)
        continue;
    end
    try
        timestampByName(name) = datetime(stamp, 'InputFormat', 'yyyy-MM-dd HH:mm:ss');
    catch
    end
end
end

function gapS = timestampGap(timestampByName, previousName, currentName)
gapS = NaN;
if ~isKey(timestampByName, previousName) || ~isKey(timestampByName, currentName)
    return;
end
try
    gapS = seconds(timestampByName(currentName) - timestampByName(previousName));
catch
    gapS = NaN;
end
end

function tableOut = buildRawVsR61Comparison(summaryTable)
groups = unique(summaryTable.group, 'stable');
rows = struct([]);
rowIndex = 0;
for idx = 1:numel(groups)
    group = groups(idx);
    rawRows = summaryTable(summaryTable.group == group & summaryTable.variant == "raw", :);
    r61Rows = summaryTable(summaryTable.group == group & summaryTable.variant == "r61_v16_psfoff", :);
    if isempty(rawRows) || isempty(r61Rows)
        continue;
    end
    raw = rawRows(1, :);
    r61 = r61Rows(1, :);
    rowIndex = rowIndex + 1;
    rows(rowIndex).group = group;
    rows(rowIndex).magnification = raw.magnification;
    rows(rowIndex).expected_step_um = raw.expected_step_um;
    rows(rowIndex).raw_median_step_um = raw.median_abs_dx_um_gap30;
    rows(rowIndex).r61_median_step_um = r61.median_abs_dx_um_gap30;
    rows(rowIndex).raw_std_um = raw.std_abs_dx_um_gap30;
    rows(rowIndex).r61_std_um = r61.std_abs_dx_um_gap30;
    rows(rowIndex).std_change_pct_r61_vs_raw = pctChange(raw.std_abs_dx_um_gap30, r61.std_abs_dx_um_gap30);
    rows(rowIndex).raw_abs_error_um = raw.median_abs_error_um_gap30;
    rows(rowIndex).r61_abs_error_um = r61.median_abs_error_um_gap30;
    rows(rowIndex).abs_error_change_um_r61_minus_raw = r61.median_abs_error_um_gap30 - raw.median_abs_error_um_gap30;
    rows(rowIndex).raw_y_drift_um = raw.median_abs_dy_um_gap30;
    rows(rowIndex).r61_y_drift_um = r61.median_abs_dy_um_gap30;
    rows(rowIndex).raw_steps = raw.gap30_step_count;
    rows(rowIndex).r61_steps = r61.gap30_step_count;
end
if rowIndex == 0
    tableOut = table();
else
    tableOut = struct2table(rows);
end
end

function value = pctChange(beforeValue, afterValue)
if isnan(beforeValue) || beforeValue == 0
    value = NaN;
else
    value = (afterValue / beforeValue - 1) * 100;
end
end

function writeSummaryFigure(summaryTable, outputPath)
if isempty(summaryTable)
    return;
end
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 1300, 820]);
tiledlayout(fig, 2, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
labels = strings(height(summaryTable), 1);
for idx = 1:height(summaryTable)
    labels(idx) = summaryTable.group(idx) + newline + summaryTable.image_label(idx);
end
colors = zeros(height(summaryTable), 3);
for idx = 1:height(summaryTable)
    if summaryTable.variant(idx) == "raw"
        colors(idx, :) = [0.78, 0.28, 0.30];
    else
        colors(idx, :) = [0.28, 0.43, 0.68];
    end
end

nexttile;
b = bar(summaryTable.median_abs_dx_um_gap30);
b.FaceColor = 'flat';
b.CData = colors;
hold on;
for idx = 1:height(summaryTable)
    plot(idx, summaryTable.expected_step_um(idx), 'k_', 'MarkerSize', 18, 'LineWidth', 1.5);
end
hold off;
grid on;
ylabel('Median X step (um)');
title('Manual ROI edge-phase displacement');
xticks(1:height(summaryTable));
xticklabels(labels);

nexttile;
b = bar(summaryTable.std_abs_dx_um_gap30);
b.FaceColor = 'flat';
b.CData = colors;
grid on;
ylabel('Step spread (um)');
title('Step-to-step spread after gaps > 30 s are excluded');
xticks(1:height(summaryTable));
xticklabels(labels);

try
    exportgraphics(fig, outputPath, 'Resolution', 160);
catch
    saveas(fig, outputPath);
end
close(fig);
end

function writeSequencePlot(stepsTable, expectedStepUm, outputPath, caseName)
validRows = stepsTable.frame_index > 0 & stepsTable.status == "ok";
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 1150, 720]);
tiledlayout(fig, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

nexttile;
plot(stepsTable.frame_index(validRows), stepsTable.abs_dx_um(validRows), '-o', 'LineWidth', 1.2);
yline(expectedStepUm, '--', 'Expected');
grid on;
xlabel('Step index');
ylabel('|dx| (um)');
title('X displacement');

nexttile;
plot(stepsTable.frame_index(validRows), stepsTable.abs_dy_um(validRows), '-o', 'LineWidth', 1.2);
grid on;
xlabel('Step index');
ylabel('|dy| (um)');
title('Y drift');

nexttile;
plot(stepsTable.frame_index(validRows), stepsTable.abs_error_um(validRows), '-o', 'LineWidth', 1.2);
grid on;
xlabel('Step index');
ylabel('abs error (um)');
title('X displacement error');

nexttile;
plot(stepsTable.frame_index(validRows), stepsTable.registration_error(validRows), '-o', 'LineWidth', 1.2);
grid on;
xlabel('Step index');
ylabel('registration error');
title('Registration diagnostic');

sgtitle(sprintf('Edge-phase result - %s', caseName), 'Interpreter', 'none');
try
    exportgraphics(fig, outputPath, 'Resolution', 160);
catch
    saveas(fig, outputPath);
end
close(fig);
end

function writeRoiPreview(image, roi, outputPath)
gray = imageToUint8(image);
rgb = repmat(gray, 1, 1, 3);
x1 = roi(1);
y1 = roi(2);
x2 = roi(1) + roi(3) - 1;
y2 = roi(2) + roi(4) - 1;
for offset = 0:2
    xa = max(1, x1 + offset);
    xb = min(size(rgb, 2), x2 - offset);
    ya = max(1, y1 + offset);
    yb = min(size(rgb, 1), y2 - offset);
    if xa <= xb && ya <= yb
        rgb(ya, xa:xb, :) = 0;
        rgb(yb, xa:xb, :) = 0;
        rgb(ya:yb, xa, :) = 0;
        rgb(ya:yb, xb, :) = 0;
        rgb(ya, xa:xb, 1) = 255;
        rgb(yb, xa:xb, 1) = 255;
        rgb(ya:yb, xa, 1) = 255;
        rgb(ya:yb, xb, 1) = 255;
    end
end
imwrite(rgb, outputPath);
end

function image8 = imageToUint8(image)
image = double(image);
minValue = min(image(:));
maxValue = max(image(:));
if maxValue <= minValue
    image8 = zeros(size(image), 'uint8');
else
    image8 = uint8(255 * (image - minValue) / (maxValue - minValue));
end
end

function writeSourceCases(cases, outputPath)
rows = struct([]);
for idx = 1:numel(cases)
    rows(idx).case = string(cases(idx).caseName);
    rows(idx).group = string(cases(idx).group);
    rows(idx).magnification = cases(idx).magnification;
    rows(idx).variant = string(cases(idx).variant);
    rows(idx).image_label = string(cases(idx).imageLabel);
    rows(idx).image_dir = string(cases(idx).imageDir);
    rows(idx).pixel_size_um = cases(idx).pixelSizeUm;
    rows(idx).expected_step_um = cases(idx).expectedStepUm;
    rows(idx).expected_dx_px = cases(idx).expectedDxPx;
end
writetable(struct2table(rows), outputPath);
end

function writeReadme(outputRoot)
path = fullfile(outputRoot, 'README.md');
lines = {
    '# Thesis 3-Magnification Manual ROI Edge-Phase Package'
    ''
    'This folder is generated by Run_Thesis_3Mag_EdgePhase_SelectROI.m.'
    ''
    'Main idea: manually choose an ROI on each magnification/step group, then measure displacement with edge-enhanced phase registration.'
    ''
    'Important folders:'
    '- source_manifest: source paths, pixel scale, and run manifest.'
    '- manual_roi_runs: per-case ROI preview, step table, summary JSON, and plot.'
    '- final_tables: compact thesis tables.'
    '- figures: summary figure.'
    ''
    'Primary table: final_tables/edge_phase_summary.csv'
    'Raw vs R61 table: final_tables/edge_phase_raw_vs_r61_comparison.csv'
    ''
    'Scale assumptions: Basler camera pixel is 3.45 um. Object-plane pixel size is 3.45 / magnification.'
    };
fid = fopen(path, 'w', 'n', 'UTF-8');
if fid < 0
    error('Cannot write README: %s', path);
end
cleanup = onCleanup(@() fclose(fid));
for idx = 1:numel(lines)
    fprintf(fid, '%s\n', lines{idx});
end
clear cleanup;
end

function writeJsonFile(path, payload)
try
    text = jsonencode(payload, PrettyPrint=true);
catch
    text = jsonencode(payload);
end
fid = fopen(path, 'w', 'n', 'UTF-8');
if fid < 0
    error('Cannot write JSON file: %s', path);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s', text);
clear cleanup;
end

function payload = readJsonFile(path)
text = fileread(path);
payload = jsondecode(text);
end

function name = safeName(name)
name = regexprep(name, '[<>:"/\\|?*]', '_');
end
