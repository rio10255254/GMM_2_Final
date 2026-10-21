% make_psf_parameter_gifs_imagesc_pixels.m
%
% Generate presentation GIFs for one-parameter PSF sweeps.
% Frames are computed by the real ValidationLab MATLAB PSF pipeline and are
% exported as nearest-neighbor pixel maps, not smoothed/interpolated images.

clear; clc;

script_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(script_dir));
addpath(fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts'));

output_root = fullfile(script_dir, 'PSF_SAF_sensitivity_20260625', 'parameter_gifs_imagesc_pixels');
eval_root = fullfile(output_root, 'matlab_eval_parameter_sweep_unlocked');
raw_dir = fullfile(output_root, 'raw_psf_gifs');
diff_dir = fullfile(output_root, 'diff_gifs');
enhanced_diff_dir = fullfile(output_root, 'diff_gifs_enhanced_per_parameter');
shared_diff_010_dir = fullfile(output_root, 'diff_gifs_shared_enhanced_0p10pct');
shared_diff_002_dir = fullfile(output_root, 'diff_gifs_shared_enhanced_0p02pct');
matlab_style_dir = fullfile(output_root, 'matlab_style_heatmap_gifs');
matlab_style_fixed_dir = fullfile(output_root, 'matlab_style_heatmap_fixed_scale_gifs');
preview_dir = fullfile(output_root, 'preview_png');
ensure_dir(output_root);
ensure_dir(raw_dir);
ensure_dir(diff_dir);
ensure_dir(enhanced_diff_dir);
ensure_dir(shared_diff_010_dir);
ensure_dir(shared_diff_002_dir);
ensure_dir(matlab_style_dir);
ensure_dir(matlab_style_fixed_dir);
ensure_dir(preview_dir);

input_folder = fullfile(script_dir, 'L0_newdata_round1', 'inputs_primary');
gt_path = fullfile(input_folder, 'GT', 'GT_901_with_Block_proc.bmp');
loss_mask_path = fullfile(input_folder, 'GT', 'circle_edge_mask.bmp');
coef_csv_path = fullfile(output_root, 'parameter_sweep_cases.csv');

labels = {
    'x1_Z2_Y_tilt', 'x2_Z3_X_tilt', 'x3_Z4_astig_45deg', ...
    'x4_Z5_defocus', 'x5_Z6_astig_0deg', 'x6_Z7_trefoil', ...
    'x7_Z8_coma_Y', 'x8_Z9_coma_X', 'x9_Z10_trefoil', ...
    'x10_Z11_quadrafoil', 'x11_Z12_sec_astig', ...
    'x12_Z13_spherical', 'x13_Z14_sec_astig', ...
    'x14_Z15_quadrafoil', 'x15_AC_amplitude'};

display_labels = {
    'x1 / Z2 Y-tilt', 'x2 / Z3 X-tilt', 'x3 / Z4 astig 45deg', ...
    'x4 / Z5 defocus', 'x5 / Z6 astig 0deg', 'x6 / Z7 trefoil', ...
    'x7 / Z8 coma Y', 'x8 / Z9 coma X', 'x9 / Z10 trefoil', ...
    'x10 / Z11 quadrafoil', 'x11 / Z12 sec astig', ...
    'x12 / Z13 spherical', 'x13 / Z14 sec astig', ...
    'x14 / Z15 quadrafoil', 'x15 / AC amplitude'};

shape_values = [-0.02 -0.015 -0.01 -0.005 0 0.005 0.01 0.015 0.02 0.015 0.01 0.005 0 -0.005 -0.01 -0.015 -0.02];
amp_values = [0.80 0.85 0.90 0.95 1.00 1.05 1.10 1.15 1.20 1.15 1.10 1.05 1.00 0.95 0.90 0.85 0.80];
num_frames = numel(shape_values);

fprintf('Writing coefficient sweep cases: %s\n', coef_csv_path);
[case_table, case_meta] = build_cases(labels, shape_values, amp_values);
writetable(case_table, coef_csv_path);
writetable(case_meta, fullfile(output_root, 'parameter_sweep_case_metadata.csv'));

fprintf('Evaluating sweep cases with real MATLAB PSF pipeline...\n');
if exist(eval_root, 'dir')
    rmdir(eval_root, 's');
end
ensure_dir(eval_root);
HDR_fitting_2D_WholeFOV_candidate_prealign( ...
    'mode', 'evaluate_coefficients', ...
    'coefficient_csv_path', coef_csv_path, ...
    'input_folder', input_folder, ...
    'gt_path', gt_path, ...
    'loss_mask_path', loss_mask_path, ...
    'grid_rows', 11, ...
    'grid_cols', 11, ...
    'pre_alignment', false, ...
    'lock_tilt', false, ...
    'use_gpu', false, ...
    'output_root', eval_root);

eval_table = readtable(fullfile(eval_root, 'coefficient_evaluation.csv'), TextType = "string");
stack = load(fullfile(eval_root, 'PSF_evaluated_coefficients.mat'), 'psf_grid');
psf_grid = stack.psf_grid;

baseline_idx = find(eval_table.case_id == "baseline_ideal", 1);
if isempty(baseline_idx)
    error('Missing baseline_ideal case.');
end
baseline_psf = double(psf_grid(:, :, 1, baseline_idx));
baseline_norm = baseline_psf ./ sum(baseline_psf(:));

raw_global_max = max(psf_grid(:));
diff_global_max = 0;
for param_idx = 1:14
    frame_indices = find_frame_indices(eval_table, param_idx, num_frames);
    for fi = 1:num_frames
        psf = double(psf_grid(:, :, 1, frame_indices(fi)));
        psf_norm = psf ./ sum(psf(:));
        diff_pct = (psf_norm - baseline_norm) ./ max(baseline_norm(:)) .* 100;
        diff_global_max = max(diff_global_max, max(abs(diff_pct(:))));
    end
end
diff_global_max = max(diff_global_max, eps);

raw_cmap = hot(256);
diff_cmap = blue_white_red(256);
matlab_style_cmap = parula(256);
scale_factor = 4;
matlab_style_crop_size = 31;
matlab_style_scale_factor = 32;
delay_time = 0.10;

heatmap_global_max = 0;
for case_idx = 1:size(psf_grid, 4)
    crop = center_crop(double(psf_grid(:, :, 1, case_idx)), matlab_style_crop_size);
    heatmap_global_max = max(heatmap_global_max, max(crop(:)));
end

summary_rows = repmat(struct( ...
    'parameter_number', 0, 'label', "", 'matlab_style_heatmap_gif', "", ...
    'matlab_style_fixed_heatmap_gif', "", 'raw_gif', "", 'diff_gif', "", ...
    'shared_diff_0p10_gif', "", 'shared_diff_0p02_gif', "", ...
    'enhanced_diff_gif', "", 'max_abs_diff_pct_of_peak', 0, 'raw_scale_max', 0, ...
    'diff_scale_abs_max_pct', 0, 'matlab_style_crop_size', 0, ...
    'matlab_style_scale_factor', 0), 1, 15);

fprintf('Writing GIFs...\n');
for param_idx = 1:15
    frame_indices = find_frame_indices(eval_table, param_idx, num_frames);
    raw_frames = cell(1, num_frames);
    diff_frames = cell(1, num_frames);
    heatmap_frames = cell(1, num_frames);
    max_abs_diff = 0;

    for fi = 1:num_frames
        psf = double(psf_grid(:, :, 1, frame_indices(fi)));
        raw_frames{fi} = psf;
        heatmap_frames{fi} = center_crop(psf, matlab_style_crop_size);

        if param_idx == 15
            diff_pct = (psf - baseline_psf) ./ max(baseline_psf(:)) .* 100;
        else
            psf_norm = psf ./ sum(psf(:));
            diff_pct = (psf_norm - baseline_norm) ./ max(baseline_norm(:)) .* 100;
        end
        diff_frames{fi} = diff_pct;
        max_abs_diff = max(max_abs_diff, max(abs(diff_pct(:))));
    end

    base_name = sprintf('%02d_%s', param_idx, labels{param_idx});
    matlab_style_gif = fullfile(matlab_style_dir, [base_name '_matlab_style_heatmap.gif']);
    matlab_style_fixed_gif = fullfile(matlab_style_fixed_dir, [base_name '_matlab_style_fixed_scale_heatmap.gif']);
    raw_gif = fullfile(raw_dir, [base_name '_raw_psf.gif']);
    diff_gif = fullfile(diff_dir, [base_name '_diff_vs_baseline.gif']);
    shared_diff_010_gif = fullfile(shared_diff_010_dir, [base_name '_shared_enhanced_0p10pct.gif']);
    shared_diff_002_gif = fullfile(shared_diff_002_dir, [base_name '_shared_enhanced_0p02pct.gif']);
    enhanced_diff_gif = fullfile(enhanced_diff_dir, [base_name '_diff_enhanced.gif']);
    matlab_style_png = fullfile(preview_dir, [base_name '_matlab_style_extreme.png']);
    matlab_style_fixed_png = fullfile(preview_dir, [base_name '_matlab_style_fixed_extreme.png']);
    raw_png = fullfile(preview_dir, [base_name '_raw_middle.png']);
    diff_png = fullfile(preview_dir, [base_name '_diff_middle.png']);

    this_diff_scale = diff_global_max;
    if param_idx == 15
        this_diff_scale = max(max_abs_diff, eps);
    end

    write_matlab_style_heatmap_gif(heatmap_frames, matlab_style_gif, matlab_style_cmap, matlab_style_scale_factor, true, 0, 1, delay_time);
    write_matlab_style_heatmap_gif(heatmap_frames, matlab_style_fixed_gif, matlab_style_cmap, matlab_style_scale_factor, false, 0, heatmap_global_max, delay_time);
    write_scalar_gif(raw_frames, raw_gif, raw_cmap, 0, raw_global_max, scale_factor, delay_time);
    write_scalar_gif(diff_frames, diff_gif, diff_cmap, -this_diff_scale, this_diff_scale, scale_factor, delay_time);
    write_scalar_gif(diff_frames, shared_diff_010_gif, diff_cmap, -0.10, 0.10, scale_factor, delay_time);
    write_scalar_gif(diff_frames, shared_diff_002_gif, diff_cmap, -0.02, 0.02, scale_factor, delay_time);
    write_scalar_gif(diff_frames, enhanced_diff_gif, diff_cmap, -max(max_abs_diff, eps), max(max_abs_diff, eps), scale_factor, delay_time);
    write_matlab_style_heatmap_png(heatmap_frames{1}, matlab_style_png, matlab_style_cmap, matlab_style_scale_factor, true, 0, 1);
    write_matlab_style_heatmap_png(heatmap_frames{1}, matlab_style_fixed_png, matlab_style_cmap, matlab_style_scale_factor, false, 0, heatmap_global_max);
    write_scalar_png(raw_frames{ceil(num_frames / 2)}, raw_png, raw_cmap, 0, raw_global_max, scale_factor);
    write_scalar_png(diff_frames{3}, diff_png, diff_cmap, -this_diff_scale, this_diff_scale, scale_factor);

    summary_rows(param_idx).parameter_number = param_idx;
    summary_rows(param_idx).label = string(display_labels{param_idx});
    summary_rows(param_idx).matlab_style_heatmap_gif = string(matlab_style_gif);
    summary_rows(param_idx).matlab_style_fixed_heatmap_gif = string(matlab_style_fixed_gif);
    summary_rows(param_idx).raw_gif = string(raw_gif);
    summary_rows(param_idx).diff_gif = string(diff_gif);
    summary_rows(param_idx).shared_diff_0p10_gif = string(shared_diff_010_gif);
    summary_rows(param_idx).shared_diff_0p02_gif = string(shared_diff_002_gif);
    summary_rows(param_idx).enhanced_diff_gif = string(enhanced_diff_gif);
    summary_rows(param_idx).max_abs_diff_pct_of_peak = max_abs_diff;
    summary_rows(param_idx).raw_scale_max = raw_global_max;
    summary_rows(param_idx).diff_scale_abs_max_pct = this_diff_scale;
    summary_rows(param_idx).matlab_style_crop_size = matlab_style_crop_size;
    summary_rows(param_idx).matlab_style_scale_factor = matlab_style_scale_factor;
end

summary_table = struct2table(summary_rows);
writetable(summary_table, fullfile(output_root, 'parameter_gif_summary.csv'));
write_html_gallery(output_root, raw_dir, diff_dir, enhanced_diff_dir, shared_diff_010_dir, shared_diff_002_dir, matlab_style_dir, matlab_style_fixed_dir, summary_table);
write_readme(output_root, raw_global_max, diff_global_max, heatmap_global_max, matlab_style_crop_size, matlab_style_scale_factor);

fprintf('Done. GIF output root: %s\n', output_root);


function [case_table, case_meta] = build_cases(labels, shape_values, amp_values)
    rows = {};
    meta_rows = {};
    baseline = zeros(1, 15);
    baseline(15) = 1;
    [rows, meta_rows] = append_case(rows, meta_rows, "baseline_ideal", 61, baseline, 0, 0, "baseline");

    for param_idx = 1:15
        if param_idx == 15
            values = amp_values;
        else
            values = shape_values;
        end
        for frame_idx = 1:numel(values)
            coef = zeros(1, 15);
            coef(15) = 1;
            coef(param_idx) = values(frame_idx);
            case_id = sprintf('x%02d_frame%03d', param_idx, frame_idx);
            [rows, meta_rows] = append_case(rows, meta_rows, string(case_id), 61, coef, param_idx, frame_idx, string(labels{param_idx}));
        end
    end

    var_names = [{'case_id', 'file_index'}, arrayfun(@(idx) sprintf('x%d', idx), 1:15, UniformOutput = false)];
    case_table = cell2table(rows, VariableNames = var_names);
    case_table.case_id = string(case_table.case_id);
    if iscell(case_table.file_index)
        case_table.file_index = cell2mat(case_table.file_index);
    end
    for idx = 1:15
        col_name = sprintf('x%d', idx);
        if iscell(case_table.(col_name))
            case_table.(col_name) = cell2mat(case_table.(col_name));
        end
    end

    case_meta = cell2table(meta_rows, VariableNames = {'case_id', 'parameter_number', 'frame_index', 'parameter_label'});
    case_meta.case_id = string(case_meta.case_id);
    if iscell(case_meta.parameter_number)
        case_meta.parameter_number = cell2mat(case_meta.parameter_number);
    end
    if iscell(case_meta.frame_index)
        case_meta.frame_index = cell2mat(case_meta.frame_index);
    end
    case_meta.parameter_label = string(case_meta.parameter_label);
end


function [rows, meta_rows] = append_case(rows, meta_rows, case_id, file_index, coef, param_idx, frame_idx, label)
    rows(end + 1, :) = [{case_id}, {file_index}, num2cell(coef)]; %#ok<AGROW>
    meta_rows(end + 1, :) = [{case_id}, {param_idx}, {frame_idx}, {label}]; %#ok<AGROW>
end


function frame_indices = find_frame_indices(eval_table, param_idx, num_frames)
    frame_indices = nan(1, num_frames);
    for frame_idx = 1:num_frames
        case_id = string(sprintf('x%02d_frame%03d', param_idx, frame_idx));
        idx = find(eval_table.case_id == case_id, 1);
        if isempty(idx)
            error('Missing case %s in evaluation table.', case_id);
        end
        frame_indices(frame_idx) = idx;
    end
end


function write_scalar_gif(frames, output_path, cmap, vmin, vmax, scale_factor, delay_time)
    if exist(output_path, 'file')
        delete(output_path);
    end
    for idx = 1:numel(frames)
        indexed = scalar_to_indexed(frames{idx}, vmin, vmax, scale_factor);
        if idx == 1
            imwrite(indexed, cmap, output_path, 'gif', LoopCount = Inf, DelayTime = delay_time);
        else
            imwrite(indexed, cmap, output_path, 'gif', WriteMode = 'append', DelayTime = delay_time);
        end
    end
end


function write_scalar_png(frame, output_path, cmap, vmin, vmax, scale_factor)
    indexed = scalar_to_indexed(frame, vmin, vmax, scale_factor);
    rgb = ind2rgb(indexed, cmap);
    imwrite(rgb, output_path);
end


function indexed = scalar_to_indexed(frame, vmin, vmax, scale_factor)
    frame = double(frame);
    if vmax <= vmin
        scaled = zeros(size(frame));
    else
        scaled = (frame - vmin) ./ (vmax - vmin);
    end
    scaled = min(max(scaled, 0), 1);
    indexed = uint8(round(scaled .* 255));
    indexed = repelem(indexed, scale_factor, scale_factor);
end


function write_matlab_style_heatmap_gif(frames, output_path, cmap, scale_factor, normalize_each_frame, vmin, vmax, delay_time)
    if exist(output_path, 'file')
        delete(output_path);
    end
    for idx = 1:numel(frames)
        indexed = matlab_style_heatmap_indexed(frames{idx}, scale_factor, normalize_each_frame, vmin, vmax);
        if idx == 1
            imwrite(indexed, cmap, output_path, 'gif', LoopCount = Inf, DelayTime = delay_time);
        else
            imwrite(indexed, cmap, output_path, 'gif', WriteMode = 'append', DelayTime = delay_time);
        end
    end
end


function write_matlab_style_heatmap_png(frame, output_path, cmap, scale_factor, normalize_each_frame, vmin, vmax)
    indexed = matlab_style_heatmap_indexed(frame, scale_factor, normalize_each_frame, vmin, vmax);
    rgb = ind2rgb(indexed, cmap);
    imwrite(rgb, output_path);
end


function indexed = matlab_style_heatmap_indexed(frame, scale_factor, normalize_each_frame, vmin, vmax)
    frame = double(frame);
    if normalize_each_frame
        frame = frame - min(frame(:));
        mx = max(frame(:));
        if mx > 0
            scaled = frame ./ mx;
        else
            scaled = zeros(size(frame));
        end
    elseif vmax > vmin
        scaled = (frame - vmin) ./ (vmax - vmin);
    else
        scaled = zeros(size(frame));
    end
    scaled = min(max(scaled, 0), 1);
    indexed = uint8(floor(scaled .* 255));
    indexed = repelem(indexed, scale_factor, scale_factor);
end


function crop = center_crop(img, crop_size)
    [h, w] = size(img);
    half = floor(crop_size / 2);
    cy = ceil(h / 2);
    cx = ceil(w / 2);
    y = (cy - half):(cy + half);
    x = (cx - half):(cx + half);
    crop = img(y, x);
end


function cmap = blue_white_red(n)
    half = floor(n / 2);
    blue = [0.16, 0.31, 0.78];
    white = [0.86, 0.86, 0.86];
    red = [0.78, 0.12, 0.16];
    lower = [linspace(blue(1), white(1), half)', linspace(blue(2), white(2), half)', linspace(blue(3), white(3), half)'];
    upper = [linspace(white(1), red(1), n - half)', linspace(white(2), red(2), n - half)', linspace(white(3), red(3), n - half)'];
    cmap = [lower; upper];
end


function ensure_dir(path)
    if ~exist(path, 'dir')
        mkdir(path);
    end
end


function write_html_gallery(output_root, raw_dir, diff_dir, enhanced_diff_dir, shared_diff_010_dir, shared_diff_002_dir, matlab_style_dir, matlab_style_fixed_dir, summary_table)
    html_path = fullfile(output_root, 'parameter_gif_gallery.html');
    fid = fopen(html_path, 'w');
    cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
    fprintf(fid, '<!doctype html><html><head><meta charset="utf-8">\n');
    fprintf(fid, '<title>PSF Parameter GIF Gallery</title>\n');
    fprintf(fid, '<style>body{font-family:Segoe UI,Arial,sans-serif;background:#fcfcfd;color:#1f2430;margin:24px;}');
    fprintf(fid, 'h1{font-size:24px;margin:0 0 6px;}p{color:#5f6678;max-width:980px;}');
    fprintf(fid, '.grid{display:grid;grid-template-columns:repeat(5, minmax(150px,1fr));gap:18px;margin-top:16px;}');
    fprintf(fid, '.card{border:1px solid #d9deea;background:white;padding:10px;}');
    fprintf(fid, '.card img{width:100%%;image-rendering:pixelated;}');
    fprintf(fid, '.label{font-weight:600;font-size:13px;margin:0 0 6px;}.value{font-size:12px;color:#6f768a;margin-top:6px;}');
    fprintf(fid, '</style></head><body>\n');
    fprintf(fid, '<h1>PSF parameter GIF gallery</h1>\n');
    fprintf(fid, '<p>The first two sections match the slide-ready MATLAB-style PSF heatmap look: center 31x31 crop, parula colormap, nearest-neighbor enlargement to 992x992. The shared enhanced difference sections use one common contrast scale for all parameters, so more small coefficients become visible without per-parameter rescaling. Difference sections are kept below for magnitude checks.</p>\n');
    fprintf(fid, '<h2>MATLAB-style normalized heatmap GIFs</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('matlab_style_heatmap_gifs', table_text(summary_table.matlab_style_heatmap_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"><div class="value">same style as reference heatmap</div></div>\n', label, rel);
    end
    fprintf(fid, '</div><h2>MATLAB-style fixed-scale heatmap GIFs</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('matlab_style_heatmap_fixed_scale_gifs', table_text(summary_table.matlab_style_fixed_heatmap_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"><div class="value">shared brightness scale</div></div>\n', label, rel);
    end
    fprintf(fid, '</div><h2>Shared enhanced difference GIFs: +/-0.10%% peak</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('diff_gifs_shared_enhanced_0p10pct', table_text(summary_table.shared_diff_0p10_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"><div class="value">common scale, mild boost</div></div>\n', label, rel);
    end
    fprintf(fid, '</div><h2>Shared enhanced difference GIFs: +/-0.02%% peak</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('diff_gifs_shared_enhanced_0p02pct', table_text(summary_table.shared_diff_0p02_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"><div class="value">common scale, strong boost</div></div>\n', label, rel);
    end
    fprintf(fid, '</div><h2>Difference GIFs</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('diff_gifs', table_text(summary_table.diff_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"><div class="value">max |diff| %.3g%% peak</div></div>\n', ...
            label, rel, summary_table.max_abs_diff_pct_of_peak(idx));
    end
    fprintf(fid, '</div><h2>Enhanced difference GIFs</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('diff_gifs_enhanced_per_parameter', table_text(summary_table.enhanced_diff_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"><div class="value">own scale max %.3g%% peak</div></div>\n', ...
            label, rel, summary_table.max_abs_diff_pct_of_peak(idx));
    end
    fprintf(fid, '</div><h2>Raw PSF GIFs</h2><div class="grid">\n');
    for idx = 1:height(summary_table)
        label = html_escape(table_text(summary_table.label, idx));
        rel = html_rel_path('raw_psf_gifs', table_text(summary_table.raw_gif, idx));
        fprintf(fid, '<div class="card"><div class="label">%s</div><img src="%s"></div>\n', label, rel);
    end
    fprintf(fid, '</div></body></html>\n');
end


function text = table_text(column, idx)
    if iscell(column)
        text = column{idx};
    elseif isstring(column)
        text = char(column(idx));
    else
        text = char(column(idx));
    end
end


function rel = html_rel_path(folder, path_text)
    [~, name, ext] = fileparts(path_text);
    rel = strrep(fullfile(folder, [name ext]), '\', '/');
end


function escaped = html_escape(text)
    escaped = char(text);
    escaped = strrep(escaped, '&', '&amp;');
    escaped = strrep(escaped, '<', '&lt;');
    escaped = strrep(escaped, '>', '&gt;');
    escaped = strrep(escaped, '"', '&quot;');
end


function write_readme(output_root, raw_global_max, diff_global_max, heatmap_global_max, matlab_style_crop_size, matlab_style_scale_factor)
    readme_path = fullfile(output_root, 'README_TW.md');
    fid = fopen(readme_path, 'w');
    cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
    fprintf(fid, '# PSF參數GIF說明\n\n');
    fprintf(fid, '- 這批GIF使用 MATLAB 正式 ValidationLab PSF 流程產生每一幀PSF。\n');
    fprintf(fid, '- x1 到 x14 每次只改一個參數，掃描 -0.02 到 +0.02，x15 固定為 1。\n');
    fprintf(fid, '- x15 單獨掃描 0.80 到 1.20，用來顯示亮度振幅，不代表PSF形狀變化。\n');
    fprintf(fid, '- matlab_style_heatmap_gifs 是最接近 slide-ready PSF heatmap 的版本：中心 %d x %d 裁切、parula 色盤、%d 倍最近鄰放大，每幀各自正規化。\n', matlab_style_crop_size, matlab_style_crop_size, matlab_style_scale_factor);
    fprintf(fid, '- matlab_style_heatmap_fixed_scale_gifs 使用同樣外觀，但全部共用固定亮度色階，max = %.12g；這組比較適合看 x15 亮度變化或不同幀的強弱差。\n', heatmap_global_max);
    fprintf(fid, '- raw_psf_gifs 是原始PSF強度動畫，固定強度色階，max = %.12g。\n', raw_global_max);
    fprintf(fid, '- diff_gifs 是相對 ideal PSF 的紅藍差異動畫；x1 到 x14 共用固定差異色階，abs max = %.12g%% of peak。\n', diff_global_max);
    fprintf(fid, '- diff_gifs_shared_enhanced_0p10pct 是公平的溫和增強版：所有參數共用 +/-0.10%% peak 色階，讓中小變化比較容易看見。\n');
    fprintf(fid, '- diff_gifs_shared_enhanced_0p02pct 是公平的強增強版：所有參數共用 +/-0.02%% peak 色階，能讓更小的變化顯現，但大參數會飽和。\n');
    fprintf(fid, '- x15 是亮度振幅，不是形狀參數，因此 x15 的 diff GIF 使用自己的振幅色階。\n');
    fprintf(fid, '- 影像用 nearest-neighbor pixel blocks 放大，沒有做平滑或插值。\n');
    fprintf(fid, '- 若要放進簡報並跟 l0_round1_median_psf_fov011_heatmap.png 那種風格一致，建議優先使用 matlab_style_heatmap_gifs。\n');
    fprintf(fid, '- 若要一頁內公平比較且讓多幾個參數露出來，建議使用 diff_gifs_shared_enhanced_0p10pct；若要強調小參數的存在感，使用 diff_gifs_shared_enhanced_0p02pct。\n');
    fprintf(fid, '- 若要保留完整大小排序，使用 diff_gifs；若要看單一小參數的變化形狀，使用 diff_gifs_enhanced_per_parameter，但這組不能拿來比較變化大小。\n');
end
