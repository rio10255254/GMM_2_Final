function summary_table = make_center_9pillar_psf_report(varargin)
%MAKE_CENTER_9PILLAR_PSF_REPORT Select, fit, and present center 3x3 pillars.
parser = inputParser;
parser.addParameter('OutputRoot', fullfile('output', 'pillar_via_junction_psf_20260713'), @(x) ischar(x) || isstring(x));
parser.addParameter('CandidatesPerFolder', 5, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('RunFitting', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('UseGpu', [], @(x) isempty(x) || islogical(x) || isnumeric(x));
parser.addParameter('Image20x', '', @(x) ischar(x) || isstring(x));
parser.addParameter('Image50x', '', @(x) ischar(x) || isstring(x));
parser.parse(varargin{:});
opts = parser.Results;

project_root = fileparts(mfilename('fullpath'));
output_root = resolve_output_path(project_root, char(opts.OutputRoot));
if ~exist(output_root, 'dir')
    mkdir(output_root);
end

addpath(project_root);
addpath(fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts'));
addpath(fullfile(project_root, 'SimulatePSF'));
addpath(genpath(fullfile(project_root, 'bads-1.1.3')));

cases = struct( ...
    'label', {'20x', '50x'}, ...
    'magnification', {20, 50}, ...
    'forced_image', {char(opts.Image20x), char(opts.Image50x)}, ...
    'folders', {{ ...
        'D:\GMM_2_Final\20260704_20x\0.5um', ...
        'D:\GMM_2_Final\20260704_20x\1um'}, { ...
        'D:\GMM_2_Final\20260702_100MG_位移_50x\x_0.5um', ...
        'D:\GMM_2_Final\20260702_100MG_位移_50x\x_1um'}});

radius_nm = center_9pillar_sem_radius_nm();
cd_nm = center_9pillar_sem_cd();
case_results = cell(1, numel(cases));
for case_idx = 1:numel(cases)
    case_results{case_idx} = process_case(cases(case_idx), cd_nm, output_root, opts);
end

summary_table = build_summary_table(case_results);
writetable(summary_table, fullfile(output_root, 'center_9pillar_psf_summary.csv'));
write_json(fullfile(output_root, 'center_9pillar_psf_manifest.json'), struct( ...
    'camera_model', 'Basler ace acA2040-120um', ...
    'camera_pixel_um', 3.45, ...
    'pillar_pitch_um', 5.0, ...
    'sem_radius_nm_top_to_bottom_left_to_right', radius_nm, ...
    'sem_cd_nm_top_to_bottom_left_to_right', cd_nm, ...
    'sem_source_workbook', 'D:\GMM_2_Final\Thesis_MOSR_Evidence\20260618_100MG\SEM_data\via_pilar.xlsx', ...
    'sem_source_range', 'SEM data!J8:L10', ...
    'sem_conversion', 'diameter_nm = 2 * fitted_radius_nm', ...
    'orientation', 'SEM bottom-left is the physical sample center; each capture is rotated into image orientation', ...
    'summary_csv', fullfile(output_root, 'center_9pillar_psf_summary.csv'), ...
    'generated_at', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'))));

combined_path = fullfile(output_root, 'PSF_20x_50x_center9_summary.png');
if isfile(combined_path), delete(combined_path); end
fprintf('Center nine-pillar report completed: %s\n', output_root);
end

function result = process_case(case_spec, cd_nm, output_root, opts)
case_root = fullfile(output_root, case_spec.label);
input_root = fullfile(case_root, 'fit_input');
fit_root = fullfile(case_root, 'fit_result');
if ~exist(input_root, 'dir'), mkdir(input_root); end
if ~exist(fit_root, 'dir'), mkdir(fit_root); end

if strlength(string(case_spec.forced_image)) > 0
    if ~isfile(case_spec.forced_image)
        error('center9:MissingForcedImage', 'Forced calibration image not found: %s', case_spec.forced_image);
    end
    candidate_paths = {case_spec.forced_image};
else
    candidate_paths = collect_candidate_paths(case_spec.folders, opts.CandidatesPerFolder);
end
candidate_rows = repmat(struct('path', "", 'mean_circle_metric', 0, ...
    'grid_residual_px', 0, ...
    'edge_score', 0, 'consistency_score', 0, ...
    'quality_score', -Inf, 'status', ""), numel(candidate_paths), 1);
valid = false(numel(candidate_paths), 1);
detections = cell(numel(candidate_paths), 1);
pairs = cell(numel(candidate_paths), 1);

for candidate_idx = 1:numel(candidate_paths)
    candidate_rows(candidate_idx).path = string(candidate_paths{candidate_idx});
    try
        junction = detect_pillar_via_junction_in_image(candidate_paths{candidate_idx}, case_spec.magnification);
        detection = fitting_detection(junction);
        image_cd_nm = orient_center_9pillar_cd(cd_nm, junction.pillar_junction_corner);
        pair = build_center_9pillar_fit_pair(candidate_paths{candidate_idx}, detection, image_cd_nm);
        [edge_score, consistency_score] = pair_quality_metrics(pair);
        mean_metric = mean(junction.pillar_metrics);
        residual = junction.pillar_grid_info.mean_grid_residual_px;
        quality_score = mean_metric + 0.25 * edge_score - 0.50 * consistency_score ...
            - 0.05 * residual;

        candidate_rows(candidate_idx).mean_circle_metric = mean_metric;
        candidate_rows(candidate_idx).grid_residual_px = residual;
        candidate_rows(candidate_idx).edge_score = edge_score;
        candidate_rows(candidate_idx).consistency_score = consistency_score;
        candidate_rows(candidate_idx).quality_score = quality_score;
        candidate_rows(candidate_idx).status = "ok";
        detections{candidate_idx} = detection;
        pairs{candidate_idx} = pair;
        valid(candidate_idx) = true;
    catch exception
        candidate_rows(candidate_idx).status = "rejected: " + string(exception.identifier);
    end
end

candidate_table = struct2table(candidate_rows);
writetable(candidate_table, fullfile(case_root, 'candidate_selection_scores.csv'));
if ~any(valid)
    error('center9:NoValidFrame', 'No valid frame was found for %s.', case_spec.label);
end
[~, best_local] = max(candidate_table.quality_score(valid));
valid_indices = find(valid);
best_idx = valid_indices(best_local);
detection = detections{best_idx};
pair = pairs{best_idx};
image_cd_nm = pair.metadata.cd_nm_by_display_row;

imwrite(uint8(round(pair.fit_input * 255)), fullfile(input_root, 'fit_input.bmp'));
gt_root = fullfile(input_root, 'GT');
if ~exist(gt_root, 'dir'), mkdir(gt_root); end
imwrite(uint8(round(pair.gt * 255)), fullfile(gt_root, 'gt_sem_cd.bmp'));
imwrite(uint8(pair.loss_mask) * 255, fullfile(input_root, 'loss_mask.bmp'));
write_json(fullfile(case_root, 'selected_frame.json'), struct( ...
    'magnification', case_spec.magnification, ...
    'selected_image', char(detection.image_path), ...
    'quality_score', candidate_table.quality_score(best_idx), ...
    'pillar_centers_xy', detection.selected_centers, ...
    'via_centers_xy', detection.via_centers, ...
    'junction_xy', detection.junction_xy, ...
    'pillar_polarity', detection.pillar_polarity, ...
    'via_polarity', detection.via_polarity, ...
    'pillar_junction_corner', detection.pillar_junction_corner, ...
    'sample_center_pillar_xy', detection.selected_centers(pair.metadata.sample_center_index, :), ...
    'object_pixel_um', detection.object_pixel_um, ...
    'pitch_px', detection.pitch_px, ...
    'physical_sem_radius_nm', cd_nm / 2, ...
    'physical_sem_cd_nm', cd_nm, ...
    'image_oriented_sem_radius_nm', image_cd_nm / 2, ...
    'image_oriented_sem_cd_nm', image_cd_nm, ...
    'sem_diameter_px', pair.metadata.diameter_px_by_display_row, ...
    'orientation', pair.metadata.orientation));

[overview_path, crop_path] = make_source_views(char(detection.image_path), detection, case_root, image_cd_nm, pair.metadata.sample_center_index);

if logical(opts.RunFitting)
    fit_summary = HDR_fitting_2D_WholeFOV_reasonable_v1( ...
        'subset_indices', 1, ...
        'input_folder', input_root, ...
        'gt_path', fullfile(gt_root, 'gt_sem_cd.bmp'), ...
        'loss_mask_path', fullfile(input_root, 'loss_mask.bmp'), ...
        'grid_rows', 1, ...
        'grid_cols', 1, ...
        'image_pattern', 'fit_input.bmp', ...
        'warm_start', false, ...
        'pre_alignment', false, ...
        'lock_tilt', true, ...
        'psf_scale', 0.125 / detection.object_pixel_um, ...
        'output_root', fit_root, ...
        'use_gpu', opts.UseGpu);
    fit_data = load(char(fit_summary.stack_path));
    fitted_psf = squeeze(fit_data.psf_grid(:, :, 1, 1));
    predicted = conv2(pair.gt, fitted_psf, 'same');
    fit_table = readtable(char(fit_summary.batch_results_path), TextType = "string");
    fit_loss = fit_table.fval(1);
    measured_values = pair.fit_input(pair.loss_mask);
    predicted_values = predicted(pair.loss_mask);
    fit_correlation = corr(measured_values, predicted_values);
    fit_nrmse = sqrt(mean((measured_values - predicted_values).^2)) / ...
        max(max(measured_values) - min(measured_values), eps);
else
    fitted_psf = nan(101, 101);
    predicted = nan(size(pair.gt));
    fit_loss = NaN;
    fit_correlation = NaN;
    fit_nrmse = NaN;
end

psf_metrics = measure_psf(fitted_psf, detection.object_pixel_um);
result = struct();
result.label = case_spec.label;
result.magnification = case_spec.magnification;
result.selected_image = char(detection.image_path);
result.object_pixel_um = detection.object_pixel_um;
result.pitch_px = detection.pitch_px;
result.detection = detection;
result.pair = pair;
result.fitted_psf = fitted_psf;
result.predicted = predicted;
result.fit_loss = fit_loss;
result.fit_correlation = fit_correlation;
result.fit_nrmse = fit_nrmse;
result.psf_metrics = psf_metrics;
result.overview_path = overview_path;
result.crop_path = crop_path;
result.case_root = case_root;

make_case_report(result, fullfile(case_root, sprintf('PSF_%s_center9_detail.png', case_spec.label)));
end

function paths = collect_candidate_paths(folders, candidates_per_folder)
paths = {};
for folder_idx = 1:numel(folders)
    files = dir(fullfile(folders{folder_idx}, '*.bmp'));
    files = files(~[files.isdir]);
    [~, order] = sort({files.name});
    files = files(order);
    if isempty(files), continue; end
    indices = unique(round(linspace(1, numel(files), min(candidates_per_folder, numel(files)))));
    for idx = indices
        paths{end + 1} = fullfile(files(idx).folder, files(idx).name); %#ok<AGROW>
    end
end
end

function [edge_score, consistency_score] = pair_quality_metrics(pair)
gradient_image = imgradient(pair.fit_input);
edge_score = mean(gradient_image(pair.loss_mask));
centers = pair.metadata.tile_centers;
radius = pair.metadata.mask_radius;
patches = zeros(2 * radius + 1, 2 * radius + 1, 9);
for idx = 1:9
    x = centers(idx, 1); y = centers(idx, 2);
    patch = pair.fit_input((y - radius):(y + radius), (x - radius):(x + radius));
    peak = max(patch(:));
    if peak > 0, patch = patch / peak; end
    patches(:, :, idx) = patch;
end
template = median(patches, 3);
consistency_score = mean(abs(patches - template), 'all');
end

function [overview_path, crop_path] = make_source_views(image_path, detection, case_root, cd_nm, sample_center_index)
source_image = imread(image_path);
centers = detection.selected_centers;
margin = 0.75 * detection.pitch_px;
x_min = max(1, floor(min(centers(:, 1)) - margin));
x_max = min(size(source_image, 2), ceil(max(centers(:, 1)) + margin));
y_min = max(1, floor(min(centers(:, 2)) - margin));
y_max = min(size(source_image, 1), ceil(max(centers(:, 2)) + margin));

overview_path = fullfile(case_root, 'selected_source_overview.png');
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [50, 50, 1200, 900]);
imshow(source_image, []); hold on;
rectangle('Position', [x_min, y_min, x_max - x_min, y_max - y_min], 'EdgeColor', [1, 0.15, 0.1], 'LineWidth', 4);
plot(centers(:, 1), centers(:, 2), 'ro', 'MarkerSize', 10, 'LineWidth', 2);
plot(detection.via_centers(:, 1), detection.via_centers(:, 2), 'bo', 'MarkerSize', 8, 'LineWidth', 1.5);
plot(detection.junction_xy(1), detection.junction_xy(2), 'yx', 'MarkerSize', 18, 'LineWidth', 3);
plot(centers(sample_center_index, 1), centers(sample_center_index, 2), 'ys', 'MarkerSize', 16, 'LineWidth', 3);
title(sprintf('%gx: red = pillar, blue = via, yellow X = junction', detection.magnification));
exportgraphics(fig, overview_path, 'Resolution', 180); close(fig);

crop_path = fullfile(case_root, 'selected_center_3x3_crop.png');
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [50, 50, 800, 800]);
imshow(source_image(y_min:y_max, x_min:x_max), []); hold on;
local_centers = centers - [x_min - 1, y_min - 1];
plot(local_centers(:, 1), local_centers(:, 2), 'r+', 'MarkerSize', 10, 'LineWidth', 1.5);
cd_row_major = reshape(cd_nm.', [], 1);
for idx = 1:9
    text(local_centers(idx, 1), local_centers(idx, 2), sprintf('%d', idx), ...
        'Color', 'y', 'FontWeight', 'bold', 'HorizontalAlignment', 'center');
end
plot(local_centers(sample_center_index, 1), local_centers(sample_center_index, 2), ...
    'ys', 'MarkerSize', 16, 'LineWidth', 2.5);
exportgraphics(fig, crop_path, 'Resolution', 220); close(fig);
end

function metrics = measure_psf(psf, object_pixel_um)
if all(~isfinite(psf), 'all')
    metrics = struct('fwhm_x_px', NaN, 'fwhm_y_px', NaN, 'fwhm_x_um', NaN, 'fwhm_y_um', NaN);
    return
end
[~, peak_idx] = max(psf(:));
[peak_y, peak_x] = ind2sub(size(psf), peak_idx);
fwhm_x_px = profile_fwhm(psf(peak_y, :));
fwhm_y_px = profile_fwhm(psf(:, peak_x));
metrics = struct('fwhm_x_px', fwhm_x_px, 'fwhm_y_px', fwhm_y_px, ...
    'fwhm_x_um', fwhm_x_px * object_pixel_um, 'fwhm_y_um', fwhm_y_px * object_pixel_um);
end

function width = profile_fwhm(profile)
profile = double(profile(:));
profile = profile / max(profile);
above = find(profile >= 0.5);
if isempty(above), width = NaN; else, width = above(end) - above(1) + 1; end
end

function table_out = build_summary_table(results)
rows = repmat(struct(), numel(results), 1);
for idx = 1:numel(results)
    result = results{idx};
    rows(idx).magnification = string(result.label);
    rows(idx).selected_image = string(result.selected_image);
    rows(idx).object_pixel_um = result.object_pixel_um;
    rows(idx).pillar_pitch_px = result.pitch_px;
    rows(idx).sem_cd_min_nm = min(result.pair.metadata.cd_nm_by_display_row, [], 'all');
    rows(idx).sem_cd_max_nm = max(result.pair.metadata.cd_nm_by_display_row, [], 'all');
    rows(idx).fit_loss = result.fit_loss;
    rows(idx).fit_correlation = result.fit_correlation;
    rows(idx).fit_nrmse = result.fit_nrmse;
    rows(idx).psf_fwhm_x_px = result.psf_metrics.fwhm_x_px;
    rows(idx).psf_fwhm_y_px = result.psf_metrics.fwhm_y_px;
    rows(idx).psf_fwhm_x_um = result.psf_metrics.fwhm_x_um;
    rows(idx).psf_fwhm_y_um = result.psf_metrics.fwhm_y_um;
end
table_out = struct2table(rows);
end

function make_case_report(result, output_path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [20, 20, 1800, 520]);
layout = tiledlayout(fig, 1, 4, 'Padding', 'compact', 'TileSpacing', 'compact');
show_panel(nexttile(layout), imread(result.crop_path), sprintf('%s captured pillar 3x3\nsample center #%d = %.3f nm', ...
    result.label, result.pair.metadata.sample_center_index, result.pair.metadata.sample_center_cd_nm));
show_panel(nexttile(layout), result.pair.gt, 'SEM-CD ground truth');
show_heatmap(nexttile(layout), result.fitted_psf, sprintf('Fitted PSF\nFWHM %.2f x %.2f um', ...
    result.psf_metrics.fwhm_x_um, result.psf_metrics.fwhm_y_um));
show_panel(nexttile(layout), result.predicted, sprintf('Forward reconstruction\ncorrelation %.2f', result.fit_correlation));
exportgraphics(fig, output_path, 'Resolution', 200); close(fig);
end

function show_panel(ax, image_data, panel_title)
if all(~isfinite(image_data), 'all')
    image_data = zeros(size(image_data));
end
imshow(image_data, [], 'Parent', ax);
axis(ax, 'image'); axis(ax, 'off');
if strlength(string(panel_title)) > 0
    title(ax, panel_title, 'Interpreter', 'none');
end
end

function detection = fitting_detection(junction)
detection = junction;
detection.selected_centers = junction.pillar_centers;
detection.selected_radii = junction.pillar_radii;
detection.selected_metrics = junction.pillar_metrics;
detection.grid_info = junction.pillar_grid_info;
detection.polarity = char(junction.pillar_polarity);
end

function show_heatmap(ax, image_data, panel_title)
if all(~isfinite(image_data), 'all')
    image_data = zeros(size(image_data));
end
imagesc(ax, image_data); axis(ax, 'image'); axis(ax, 'off'); colormap(ax, parula(256));
title(ax, panel_title, 'Interpreter', 'none'); colorbar(ax);
end

function write_json(path_out, payload)
fid = fopen(path_out, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonencode(payload, PrettyPrint = true));
end

function output_path = resolve_output_path(project_root, input_path)
if ~isempty(regexp(input_path, '^[A-Za-z]:[\\/]', 'once'))
    output_path = input_path;
else
    output_path = fullfile(project_root, input_path);
end
end
