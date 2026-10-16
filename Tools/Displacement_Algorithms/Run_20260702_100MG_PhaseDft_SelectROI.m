function Run_20260702_100MG_PhaseDft_SelectROI(varargin)
% Open this file in MATLAB and press Run.
% It measures the 20260702 100MG displacement sequences with DFT registration.

clc;

scriptDir = fileparts(mfilename('fullpath'));
legacyDir = fullfile(scriptDir, 'phase_correlation_dft', 'legacy_matlab');
addpath(legacyDir);

cfg = parseInputs(varargin{:});
if exist(cfg.dataRoot, 'dir') ~= 7
    error('Data root does not exist: %s', cfg.dataRoot);
end
if exist(legacyDir, 'dir') ~= 7 || exist('dftregistration', 'file') ~= 2
    error('Cannot find dftregistration.m under: %s', legacyDir);
end

sequenceDirs = findSequenceDirs(cfg.dataRoot);
if isempty(sequenceDirs)
    error('No image sequence folders were found under: %s', cfg.dataRoot);
end
if isfinite(cfg.maxSequences)
    sequenceDirs = sequenceDirs(1:min(numel(sequenceDirs), cfg.maxSequences));
end

if exist(cfg.outputRoot, 'dir') ~= 7
    mkdir(cfg.outputRoot);
end

fprintf('\n=== 20260702 100MG phase DFT displacement measurement ===\n');
fprintf('Data root : %s\n', cfg.dataRoot);
fprintf('Output    : %s\n', cfg.outputRoot);
fprintf('Sequences : %d\n\n', numel(sequenceDirs));

runResults = struct([]);
summaryRows = struct([]);
previousRoi = [];

for sequenceIndex = 1:numel(sequenceDirs)
    sequenceDir = sequenceDirs{sequenceIndex};
    imageFiles = listImageFiles(sequenceDir);
    sequenceName = lastPathPart(sequenceDir);
    rootName = lastPathPart(cfg.dataRoot);
    caseName = safeName(sprintf('%s__%s', rootName, sequenceName));
    caseOutputDir = fullfile(cfg.outputRoot, caseName);
    if exist(caseOutputDir, 'dir') ~= 7
        mkdir(caseOutputDir);
    end

    firstImage = readGrayDouble(fullfile(imageFiles(1).folder, imageFiles(1).name));
    if isempty(cfg.autoRoi)
        roi = selectRoiFromImage(firstImage, sequenceName, previousRoi);
    else
        roi = cfg.autoRoi;
    end
    roi = clipRoi(roi, size(firstImage));
    previousRoi = roi;

    fprintf('Running %s (%d images), ROI = [%d %d %d %d]\n', ...
        sequenceName, numel(imageFiles), roi(1), roi(2), roi(3), roi(4));

    expectedStepUm = inferExpectedStepUm(sequenceName);
    [stepsTable, summary] = measureSequence( ...
        imageFiles, roi, cfg.pixelSizeUm, cfg.upsampleFactor, cfg.useHann, expectedStepUm);

    stepsCsv = fullfile(caseOutputDir, 'phase_dft_steps.csv');
    summaryJson = fullfile(caseOutputDir, 'phase_dft_summary.json');
    roiPreviewPng = fullfile(caseOutputDir, 'roi_preview.png');
    plotPng = fullfile(caseOutputDir, 'phase_dft_plot.png');

    writetable(stepsTable, stepsCsv);
    writeJsonFile(summaryJson, summary);
    writeRoiPreview(firstImage, roi, roiPreviewPng);
    writeSequencePlot(stepsTable, expectedStepUm, plotPng, sequenceName);

    runResults(sequenceIndex).case = caseName;
    runResults(sequenceIndex).sequence_dir = sequenceDir;
    runResults(sequenceIndex).image_count = numel(imageFiles);
    runResults(sequenceIndex).roi_x_y_width_height = roi;
    runResults(sequenceIndex).expected_step_um = expectedStepUm;
    runResults(sequenceIndex).steps_csv = stepsCsv;
    runResults(sequenceIndex).summary_json = summaryJson;
    runResults(sequenceIndex).roi_preview = roiPreviewPng;
    runResults(sequenceIndex).plot_png = plotPng;

    summaryRows(sequenceIndex).case = string(caseName);
    summaryRows(sequenceIndex).sequence = string(sequenceName);
    summaryRows(sequenceIndex).images = numel(imageFiles);
    summaryRows(sequenceIndex).expected_step_um = expectedStepUm;
    summaryRows(sequenceIndex).mean_step_distance_um = summary.mean_step_distance_um;
    summaryRows(sequenceIndex).std_step_distance_um = summary.std_step_distance_um;
    summaryRows(sequenceIndex).mean_dx_px = summary.mean_dx_px;
    summaryRows(sequenceIndex).std_dx_px = summary.std_dx_px;
    summaryRows(sequenceIndex).mean_dy_px = summary.mean_dy_px;
    summaryRows(sequenceIndex).std_dy_px = summary.std_dy_px;
end

manifest = struct();
manifest.algorithm = 'MATLAB dftregistration';
manifest.data_root = cfg.dataRoot;
manifest.output_root = cfg.outputRoot;
manifest.pixel_size_um = cfg.pixelSizeUm;
manifest.upsample_factor = cfg.upsampleFactor;
manifest.hann_window = cfg.useHann;
manifest.sequence_count = numel(runResults);
manifest.results = runResults;
writeJsonFile(fullfile(cfg.outputRoot, 'phase_dft_run_manifest.json'), manifest);

if ~isempty(summaryRows)
    writetable(struct2table(summaryRows), fullfile(cfg.outputRoot, 'phase_dft_summary_table.csv'));
end

fprintf('\nFinished. Main output folder:\n%s\n', cfg.outputRoot);
fprintf('Open phase_dft_summary_table.csv for the compact result table.\n\n');
end

function cfg = parseInputs(varargin)
p = inputParser;
p.addParameter('dataRoot', 'D:\GMM_2_Final\20260702_100MG_位移');
p.addParameter('outputRoot', 'D:\GMM_2_Final\20260702_100MG_phase_dft_analysis_matlab');
p.addParameter('pixelSizeUm', 3.45 / 50);
p.addParameter('upsampleFactor', 100);
p.addParameter('useHann', true);
p.addParameter('autoRoi', []);
p.addParameter('maxSequences', Inf);
p.parse(varargin{:});
cfg = p.Results;
if ~isempty(cfg.autoRoi)
    cfg.autoRoi = round(double(cfg.autoRoi(:).'));
    if numel(cfg.autoRoi) ~= 4
        error('autoRoi must be [x y width height].');
    end
end
end

function sequenceDirs = findSequenceDirs(dataRoot)
sequenceDirs = cell(1, 1);
sequenceCount = 0;
rootFiles = listImageFiles(dataRoot);
if numel(rootFiles) >= 2
    sequenceCount = sequenceCount + 1;
    sequenceDirs{sequenceCount} = dataRoot;
end
entries = dir(dataRoot);
entries = entries([entries.isdir]);
sequenceDirs(max(1, numel(entries) + sequenceCount)) = {[]};
names = {entries.name};
for idx = 1:numel(entries)
    name = names{idx};
    if strcmp(name, '.') || strcmp(name, '..')
        continue;
    end
    folder = fullfile(entries(idx).folder, entries(idx).name);
    if numel(listImageFiles(folder)) >= 2
        sequenceCount = sequenceCount + 1;
        sequenceDirs{sequenceCount} = folder;
    end
end
sequenceDirs = sequenceDirs(1:sequenceCount);
[~, order] = sort(lower(string(sequenceDirs)));
sequenceDirs = sequenceDirs(order);
end

function files = listImageFiles(folder)
patterns = {'*.bmp', '*.png', '*.jpg', '*.jpeg', '*.tif', '*.tiff'};
files = [];
for idx = 1:numel(patterns)
    found = dir(fullfile(folder, patterns{idx}));
    files = [files; found(:)]; %#ok<AGROW>
end
if isempty(files)
    files = struct('name', {}, 'folder', {}, 'date', {}, 'bytes', {}, ...
        'isdir', {}, 'datenum', {});
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

function roi = selectRoiFromImage(image, sequenceName, initialRoi)
fig = figure('Name', sprintf('Select ROI - %s', sequenceName), 'Color', 'w');
if exist('imshow', 'file') == 2
    imshow(image, []);
else
    imagesc(image);
    axis image off;
    colormap gray;
end
title(sprintf('%s: drag ROI, double-click/press Enter to confirm', sequenceName), ...
    'Interpreter', 'none');

try
    if exist('drawrectangle', 'file') == 2 || exist('drawrectangle', 'class') == 8
        if isempty(initialRoi)
            roiHandle = drawrectangle('Color', 'r');
        else
            roiHandle = drawrectangle('Color', 'r', 'Position', initialRoi);
        end
        wait(roiHandle);
        roi = round(roiHandle.Position);
    else
        if ~isempty(initialRoi)
            rectangle('Position', initialRoi, 'EdgeColor', 'r', 'LineWidth', 1.5);
        end
        roi = round(getrect(gca));
    end
catch err
    if isvalid(fig)
        close(fig);
    end
    rethrow(err);
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

function [stepsTable, summary] = measureSequence(files, roi, pixelSizeUm, upsampleFactor, useHann, expectedStepUm)
n = numel(files);
frameIndex = (0:n - 1).';
filename = strings(n, 1);
refFilename = strings(n, 1);
dxPx = nan(n, 1);
dyPx = nan(n, 1);
stepDistancePx = nan(n, 1);
stepDistanceUm = nan(n, 1);
cumulativeDxPx = nan(n, 1);
cumulativeDyPx = nan(n, 1);
cumulativeDistancePx = nan(n, 1);
cumulativeDistanceUm = nan(n, 1);
directFirstDxPx = nan(n, 1);
directFirstDyPx = nan(n, 1);
directFirstDistancePx = nan(n, 1);
directFirstDistanceUm = nan(n, 1);
registrationError = nan(n, 1);
phaseDiff = nan(n, 1);
status = strings(n, 1);
message = strings(n, 1);

firstImage = prepareImage(fullfile(files(1).folder, files(1).name), roi, useHann);
previousImage = firstImage;
cumulativeDx = 0;
cumulativeDy = 0;

filename(1) = string(files(1).name);
refFilename(1) = "";
dxPx(1) = 0;
dyPx(1) = 0;
stepDistancePx(1) = 0;
stepDistanceUm(1) = 0;
cumulativeDxPx(1) = 0;
cumulativeDyPx(1) = 0;
cumulativeDistancePx(1) = 0;
cumulativeDistanceUm(1) = 0;
directFirstDxPx(1) = 0;
directFirstDyPx(1) = 0;
directFirstDistancePx(1) = 0;
directFirstDistanceUm(1) = 0;
registrationError(1) = 0;
phaseDiff(1) = 0;
status(1) = "reference";
message(1) = "";

for idx = 2:n
    currentPath = fullfile(files(idx).folder, files(idx).name);
    currentImage = prepareImage(currentPath, roi, useHann);
    filename(idx) = string(files(idx).name);
    refFilename(idx) = string(files(idx - 1).name);
    try
        [dx, dy, err, ph] = dftDisplacement(previousImage, currentImage, upsampleFactor);
        [directDx, directDy] = dftDisplacement(firstImage, currentImage, upsampleFactor);
        cumulativeDx = cumulativeDx + dx;
        cumulativeDy = cumulativeDy + dy;

        dxPx(idx) = dx;
        dyPx(idx) = dy;
        stepDistancePx(idx) = hypot(dx, dy);
        stepDistanceUm(idx) = stepDistancePx(idx) * pixelSizeUm;
        cumulativeDxPx(idx) = cumulativeDx;
        cumulativeDyPx(idx) = cumulativeDy;
        cumulativeDistancePx(idx) = hypot(cumulativeDx, cumulativeDy);
        cumulativeDistanceUm(idx) = cumulativeDistancePx(idx) * pixelSizeUm;
        directFirstDxPx(idx) = directDx;
        directFirstDyPx(idx) = directDy;
        directFirstDistancePx(idx) = hypot(directDx, directDy);
        directFirstDistanceUm(idx) = directFirstDistancePx(idx) * pixelSizeUm;
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

stepsTable = table(frameIndex, filename, refFilename, dxPx, dyPx, ...
    stepDistancePx, stepDistanceUm, cumulativeDxPx, cumulativeDyPx, ...
    cumulativeDistancePx, cumulativeDistanceUm, directFirstDxPx, ...
    directFirstDyPx, directFirstDistancePx, directFirstDistanceUm, ...
    registrationError, phaseDiff, status, message);

stepsTable.Properties.VariableNames = {'frame_index', 'filename', 'ref_filename', ...
    'dx_px', 'dy_px', 'step_distance_px', 'step_distance_um', ...
    'cumulative_dx_px', 'cumulative_dy_px', 'cumulative_distance_px', ...
    'cumulative_distance_um', 'direct_first_dx_px', 'direct_first_dy_px', ...
    'direct_first_distance_px', 'direct_first_distance_um', ...
    'registration_error', 'phase_diff', 'status', 'message'};

valid = status == "ok";
summary = struct();
summary.algorithm = 'MATLAB dftregistration';
summary.image_count = n;
summary.valid_step_count = sum(valid);
summary.pixel_size_um = pixelSizeUm;
summary.upsample_factor = upsampleFactor;
summary.hann_window = useHann;
summary.roi_x_y_width_height = roi;
summary.expected_step_um = expectedStepUm;
summary.mean_dx_px = mean(dxPx(valid), 'omitnan');
summary.std_dx_px = std(dxPx(valid), 'omitnan');
summary.mean_dy_px = mean(dyPx(valid), 'omitnan');
summary.std_dy_px = std(dyPx(valid), 'omitnan');
summary.mean_step_distance_px = mean(stepDistancePx(valid), 'omitnan');
summary.std_step_distance_px = std(stepDistancePx(valid), 'omitnan');
summary.mean_step_distance_um = mean(stepDistanceUm(valid), 'omitnan');
summary.std_step_distance_um = std(stepDistanceUm(valid), 'omitnan');
summary.rms_step_distance_um = sqrt(mean(stepDistanceUm(valid).^2, 'omitnan'));
if ~isnan(expectedStepUm)
    stepErrorUm = stepDistanceUm(valid) - expectedStepUm;
    summary.mean_step_error_um = mean(stepErrorUm, 'omitnan');
    summary.std_step_error_um = std(stepErrorUm, 'omitnan');
else
    summary.mean_step_error_um = NaN;
    summary.std_step_error_um = NaN;
end
end

function image = prepareImage(path, roi, useHann)
image = readGrayDouble(path);
x = roi(1);
y = roi(2);
w = roi(3);
h = roi(4);
image = image(y:y + h - 1, x:x + w - 1);
image = image - mean(image(:), 'omitnan');
if useHann
    wy = localHann(size(image, 1));
    wx = localHann(size(image, 2)).';
    image = image .* (wy * wx);
end
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

function expectedStepUm = inferExpectedStepUm(sequenceName)
tokens = regexp(sequenceName, '([0-9]+(?:\.[0-9]+)?)\s*um', 'tokens', 'once');
if isempty(tokens)
    expectedStepUm = NaN;
else
    expectedStepUm = str2double(tokens{1});
end
end

function name = lastPathPart(path)
path = char(path);
path = regexprep(path, '[\\/]+$', '');
parts = regexp(path, '[\\/]', 'split');
name = parts{end};
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

function writeSequencePlot(stepsTable, expectedStepUm, outputPath, sequenceName)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 1100, 750]);
tiledlayout(fig, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

validRows = stepsTable.frame_index > 0 & stepsTable.status == "ok";
stepNo = stepsTable.frame_index(validRows);

nexttile;
plot(stepNo, stepsTable.step_distance_um(validRows), '-o', 'LineWidth', 1.2);
if ~isnan(expectedStepUm)
    yline(expectedStepUm, '--', 'Expected');
end
xlabel('Step');
ylabel('Step distance (um)');
title('Step distance');

nexttile;
plot(stepNo, stepsTable.dx_px(validRows), '-o', 'LineWidth', 1.2);
hold on;
plot(stepNo, stepsTable.dy_px(validRows), '-s', 'LineWidth', 1.2);
hold off;
legend('dx', 'dy', 'Location', 'best');
xlabel('Step');
ylabel('Pixels');
title('X/Y displacement');

nexttile;
plot(stepsTable.frame_index, stepsTable.cumulative_distance_um, '-o', 'LineWidth', 1.2);
xlabel('Frame');
ylabel('Cumulative distance (um)');
title('Cumulative displacement');

nexttile;
if ~isnan(expectedStepUm)
    plot(stepNo, stepsTable.step_distance_um(validRows) - expectedStepUm, '-o', 'LineWidth', 1.2);
    yline(0, '--');
    ylabel('Measured - expected (um)');
else
    plot(stepNo, stepsTable.step_distance_um(validRows), '-o', 'LineWidth', 1.2);
    ylabel('Step distance (um)');
end
xlabel('Step');
title('Step error');

sgtitle(sprintf('Phase DFT result - %s', sequenceName), 'Interpreter', 'none');
try
    exportgraphics(fig, outputPath, 'Resolution', 160);
catch
    saveas(fig, outputPath);
end
close(fig);
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

function name = safeName(name)
name = regexprep(name, '[<>:"/\\|?*]', '_');
end
