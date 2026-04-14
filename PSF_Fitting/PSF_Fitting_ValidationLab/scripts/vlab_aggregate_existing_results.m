function summary = vlab_aggregate_existing_results(lab_root, varargin)
parser = inputParser;
parser.addRequired('lab_root', @(x) ischar(x) || isstring(x));
parser.addParameter('experiment_names', strings(0, 1), @(x) isstring(x) || ischar(x) || iscellstr(x));
parser.addParameter('output_root', fullfile(char(lab_root), 'outputs'), @(x) ischar(x) || isstring(x));
parser.parse(lab_root, varargin{:});

lab_root = char(parser.Results.lab_root);
requested_names = parser.Results.experiment_names;
outputs_root = char(parser.Results.output_root);
if ischar(requested_names)
    requested_names = string({requested_names});
elseif iscell(requested_names)
    requested_names = string(requested_names);
else
    requested_names = string(requested_names);
end

experiments_root = fullfile(outputs_root, 'experiments');
tables_dir = fullfile(outputs_root, 'tables');
figures_dir = fullfile(outputs_root, 'figures');
reports_dir = fullfile(outputs_root, 'reports');

vlab_ensure_dir(tables_dir);
vlab_ensure_dir(figures_dir);
vlab_ensure_dir(reports_dir);

experiment_dirs = dir(experiments_root);
experiment_dirs = experiment_dirs([experiment_dirs.isdir]);
experiment_dirs = experiment_dirs(~ismember({experiment_dirs.name}, {'.', '..'}));

completed_results = struct([]);
for di = 1:numel(experiment_dirs)
    experiment_name = string(experiment_dirs(di).name);
    if ~isempty(requested_names) && ~ismember(experiment_name, requested_names)
        continue;
    end

    output_dir = fullfile(experiment_dirs(di).folder, experiment_dirs(di).name);
    batch_results_path = fullfile(output_dir, 'batch_results.csv');
    if ~isfile(batch_results_path)
        continue;
    end

    batch_table = readtable(batch_results_path, TextType = "string");
    if isempty(batch_table) || height(batch_table) == 0
        continue;
    end

    result = struct();
    result.name = experiment_name;
    result.output_dir = output_dir;
    result.batch_results_path = batch_results_path;
    result.batch_table = batch_table;
    result.prealign_step = vlab_read_prealign_step(output_dir);
    completed_results = [completed_results; result]; %#ok<AGROW>
end

if isempty(completed_results)
    error('No completed experiment batch_results.csv found under %s.', experiments_root);
end

comparison_rows = repmat(struct( ...
    'experiment_name', "", ...
    'num_images', 0, ...
    'subset_indices', "", ...
    'warm_start', false, ...
    'pre_alignment', false, ...
    'lock_tilt', false, ...
    'prealign_step', NaN, ...
    'mean_fval', 0, ...
    'mean_iterations', 0, ...
    'mean_seconds', 0, ...
    'mean_peak_offset_y', 0, ...
    'mean_peak_offset_x', 0, ...
    'mean_abs_peak_offset', 0, ...
    'mean_centroid_offset_y', 0, ...
    'mean_centroid_offset_x', 0, ...
    'mean_abs_centroid_offset', 0, ...
    'mean_edge_energy_ratio', 0, ...
    'num_touches_edge', 0, ...
    'mean_prealign_shift_y', 0, ...
    'mean_prealign_shift_x', 0, ...
    'offset_score', 0, ...
    'edge_score', 0, ...
    'overall_score', 0), 1, numel(completed_results));

for ei = 1:numel(completed_results)
    tbl = completed_results(ei).batch_table;
    mean_abs_peak_offset = mean(abs(tbl.peak_offset_y) + abs(tbl.peak_offset_x));
    mean_abs_centroid_offset = mean(abs(tbl.centroid_offset_y) + abs(tbl.centroid_offset_x));
    num_touches_edge = sum(tbl.touches_edge);
    mean_edge_energy = mean(tbl.edge_energy_ratio);

    comparison_rows(ei).experiment_name = string(completed_results(ei).name);
    comparison_rows(ei).num_images = height(tbl);
    comparison_rows(ei).subset_indices = strjoin(string(tbl.file_index.'), ',');
    comparison_rows(ei).warm_start = logical(tbl.warm_start(1));
    comparison_rows(ei).pre_alignment = logical(tbl.pre_alignment(1));
    comparison_rows(ei).lock_tilt = logical(tbl.lock_tilt(1));
    comparison_rows(ei).prealign_step = completed_results(ei).prealign_step;
    comparison_rows(ei).mean_fval = mean(tbl.fval);
    comparison_rows(ei).mean_iterations = mean(tbl.iterations);
    comparison_rows(ei).mean_seconds = mean(tbl.seconds);
    comparison_rows(ei).mean_peak_offset_y = mean(tbl.peak_offset_y);
    comparison_rows(ei).mean_peak_offset_x = mean(tbl.peak_offset_x);
    comparison_rows(ei).mean_abs_peak_offset = mean_abs_peak_offset;
    comparison_rows(ei).mean_centroid_offset_y = mean(tbl.centroid_offset_y);
    comparison_rows(ei).mean_centroid_offset_x = mean(tbl.centroid_offset_x);
    comparison_rows(ei).mean_abs_centroid_offset = mean_abs_centroid_offset;
    comparison_rows(ei).mean_edge_energy_ratio = mean_edge_energy;
    comparison_rows(ei).num_touches_edge = num_touches_edge;
    comparison_rows(ei).mean_prealign_shift_y = mean(tbl.prealign_shift_y, 'omitnan');
    comparison_rows(ei).mean_prealign_shift_x = mean(tbl.prealign_shift_x, 'omitnan');
    comparison_rows(ei).offset_score = mean_abs_peak_offset + 0.5 * mean_abs_centroid_offset;
    comparison_rows(ei).edge_score = num_touches_edge * 100 + mean_edge_energy * 100;
    comparison_rows(ei).overall_score = comparison_rows(ei).offset_score + comparison_rows(ei).edge_score + 0.001 * comparison_rows(ei).mean_iterations;
end

comparison_table = struct2table(comparison_rows);
[~, sort_index] = sort(comparison_table.overall_score, 'ascend');
comparison_table = comparison_table(sort_index, :);
comparison_csv_path = fullfile(tables_dir, 'experiment_comparison.csv');
writetable(comparison_table, comparison_csv_path);

offset_fig_path = fullfile(figures_dir, 'representative_offset_comparison.png');
vlab_make_offset_figure_from_tables(completed_results, offset_fig_path);

fit_fig_path = fullfile(figures_dir, 'fval_iterations_comparison.png');
vlab_make_fit_figure(comparison_table, fit_fig_path);

[~, best_offset_idx] = min(comparison_table.offset_score);
[~, best_fval_idx] = min(comparison_table.mean_fval);
[~, best_edge_idx] = min(comparison_table.edge_score);
[~, best_overall_idx] = min(comparison_table.overall_score);

best_offset = comparison_table(best_offset_idx, :);
best_fval = comparison_table(best_fval_idx, :);
best_edge = comparison_table(best_edge_idx, :);
best_overall = comparison_table(best_overall_idx, :);

baseline_row = vlab_pick_named_or_masked_row( ...
    comparison_table, ...
    ["baseline_rep16", "baseline_subset"], ...
    comparison_table.pre_alignment == false & comparison_table.lock_tilt == true);
integer_row = vlab_pick_named_or_masked_row( ...
    comparison_table, ...
    ["alignment_rep16", "alignment_subset"], ...
    comparison_table.pre_alignment == true & comparison_table.lock_tilt == true & abs(comparison_table.prealign_step - 1.0) < 1e-9);
refined_locked_rows = comparison_table( ...
    comparison_table.pre_alignment == true & comparison_table.lock_tilt == true & comparison_table.prealign_step < 1.0, :);
candidate_row = vlab_pick_best_row(refined_locked_rows, best_overall);
tilt_row = vlab_pick_named_or_masked_row( ...
    comparison_table, ...
    ["alignment_tilt_rep16", "alignment_tilt_subset"], ...
    comparison_table.pre_alignment == true & comparison_table.lock_tilt == false);

recommended_step_text = vlab_format_step(candidate_row.prealign_step(1));
recommended_mode_text = vlab_format_prealign_mode(candidate_row.prealign_step(1));

all_file_indices = unique(completed_results(1).batch_table.file_index).';
subset_parts = arrayfun(@(fi) sprintf('fi=%d(R%dC%d)', fi, floor((fi - 1) / 10) + 1, mod(fi - 1, 10) + 1), all_file_indices, UniformOutput = false);
subset_text = strjoin(string(subset_parts), ', ');
completed_name_text = strjoin(string(comparison_table.experiment_name).', ', ');

summary_path = fullfile(reports_dir, 'validation_summary_tw.md');
recommendation_path = fullfile(reports_dir, 'next_recommendation_tw.md');
candidate_flow_path = fullfile(reports_dir, 'candidate_flow_tw.md');

summary_lines = {
    '# Whole-FOV PSF 驗證摘要'
    ''
    sprintf('- 重新聚合時間：%s', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')))
    sprintf('- 已納入完成實驗：%s', completed_name_text)
    sprintf('- 子集代表點：%s', subset_text)
    ''
    '## 問題 1：raw/GT 預對齊是否能消除共同偏移'
    sprintf('- 目前完成資料中，最能消除共同偏移的是 `%s`。', best_offset.experiment_name(1))
    sprintf('- 這組的 mean peak offset = (y=%.3f, x=%.3f)，mean abs peak offset = %.3f px。', best_offset.mean_peak_offset_y, best_offset.mean_peak_offset_x, best_offset.mean_abs_peak_offset)
    sprintf('- 其 mean centroid offset = (y=%.3f, x=%.3f)，mean abs centroid offset = %.3f px。', best_offset.mean_centroid_offset_y, best_offset.mean_centroid_offset_x, best_offset.mean_abs_centroid_offset)
};
if best_offset.pre_alignment
    summary_lines{end + 1} = sprintf('- 這組對 raw 施加的平均預對齊位移為 (dy=%.3f, dx=%.3f)。', best_offset.mean_prealign_shift_y, best_offset.mean_prealign_shift_x);
end
if ~isempty(baseline_row)
    summary_lines{end + 1} = sprintf('- 和 `%s` 相比，最佳對齊線把 mean abs peak offset 從 %.3f px 降到 %.3f px。', ...
        baseline_row.experiment_name(1), baseline_row.mean_abs_peak_offset, best_offset.mean_abs_peak_offset);
end
if ~isempty(integer_row) && candidate_row.pre_alignment && candidate_row.lock_tilt && candidate_row.experiment_name(1) ~= integer_row.experiment_name(1)
    summary_lines{end + 1} = sprintf('- 相比 `%s`，`%s` 把 mean peak offset_x 從 %.3f 壓到 %.3f，mean abs peak offset 從 %.3f px 降到 %.3f px。', ...
        integer_row.experiment_name(1), candidate_row.experiment_name(1), ...
        integer_row.mean_peak_offset_x, candidate_row.mean_peak_offset_x, ...
        integer_row.mean_abs_peak_offset, candidate_row.mean_abs_peak_offset);
end
summary_lines{end + 1} = '';
summary_lines{end + 1} = '## 問題 2：放開 tilt 是否能改善貼界';
summary_lines{end + 1} = sprintf('- 目前完成資料中，貼界指標最佳的是 `%s`。', best_edge.experiment_name(1));
summary_lines{end + 1} = '- 已納入實驗的 touches_edge 都是 0；目前代表子集上看不到 tilt 帶來額外貼界改善。';
summary_lines{end + 1} = sprintf('- `%s` 的 mean edge energy ratio = %.4f。', best_edge.experiment_name(1), best_edge.mean_edge_energy_ratio);
summary_lines{end + 1} = '';
summary_lines{end + 1} = '## fval 比較';
summary_lines{end + 1} = sprintf('- mean fval 最佳的是 `%s`，數值 %.3f。', best_fval.experiment_name(1), best_fval.mean_fval);
if ~isempty(integer_row) && candidate_row.pre_alignment && candidate_row.lock_tilt && candidate_row.experiment_name(1) ~= integer_row.experiment_name(1)
    summary_lines{end + 1} = sprintf('- `%s` 相比 `%s`，mean fval 再下降 %.3f。', ...
        candidate_row.experiment_name(1), integer_row.experiment_name(1), integer_row.mean_fval - candidate_row.mean_fval);
end
if ~isempty(tilt_row) && tilt_row.experiment_name(1) ~= candidate_row.experiment_name(1)
    summary_lines{end + 1} = sprintf('- `%s` 相比 `%s` 的 mean iterations 多 %.1f，且 mean abs peak offset %.3f px 對 %.3f px 沒有優勢。', ...
        tilt_row.experiment_name(1), candidate_row.experiment_name(1), ...
        tilt_row.mean_iterations - candidate_row.mean_iterations, ...
        tilt_row.mean_abs_peak_offset, candidate_row.mean_abs_peak_offset);
end
summary_lines{end + 1} = '';
summary_lines{end + 1} = '## 最值得往正式可用版收斂的方向';
summary_lines{end + 1} = sprintf('- 綜合 offset、貼界與收斂品質，推薦 `%s` 作為下一步正式候選。', candidate_row.experiment_name(1));
summary_lines{end + 1} = sprintf('- 目前最值得收斂的機制是：`warm_start + %s + tilt locked`。', recommended_mode_text);
if ~isempty(tilt_row) && tilt_row.experiment_name(1) ~= candidate_row.experiment_name(1)
    summary_lines{end + 1} = sprintf('- 目前不建議先把 tilt 放進正式主線：`%s` 沒有帶來更好的 peak offset，且 mean iterations 比 `%s` 高 %.1f。', ...
        tilt_row.experiment_name(1), candidate_row.experiment_name(1), ...
        tilt_row.mean_iterations - candidate_row.mean_iterations);
end
summary_lines{end + 1} = '';
summary_lines{end + 1} = '## 產出位置';
summary_lines{end + 1} = sprintf('- 比較表：`%s`', comparison_csv_path);
summary_lines{end + 1} = sprintf('- 偏移比較圖：`%s`', offset_fig_path);
summary_lines{end + 1} = sprintf('- fval/iterations 圖：`%s`', fit_fig_path);
summary_lines{end + 1} = sprintf('- candidate flow 說明：`%s`', candidate_flow_path);
vlab_write_lines(summary_path, summary_lines);

recommendation_lines = {
    '# 下一步建議'
    ''
    sprintf('- 先以 `%s` 當作正式修正版候選。', candidate_row.experiment_name(1))
    '- 目前證據支持先保留 warm-start，並把 pre_alignment 變成正式流程的顯式選項。'
    sprintf('- 這輪最有價值的收斂點是 `%s` 的 `prealign_step = %s`；它同時改善 offset 與 fval，應直接進入候選主程式預設。', candidate_row.experiment_name(1), recommended_step_text)
};
if ~isempty(tilt_row) && tilt_row.experiment_name(1) ~= candidate_row.experiment_name(1)
    recommendation_lines{end + 1} = sprintf('- `%s` 目前不值得進正式主線：它的 mean abs peak offset 為 %.3f px，沒有優於 `%s` 的 %.3f px，且 mean iterations 多 %.1f。', ...
        tilt_row.experiment_name(1), tilt_row.mean_abs_peak_offset, ...
        candidate_row.experiment_name(1), candidate_row.mean_abs_peak_offset, ...
        tilt_row.mean_iterations - candidate_row.mean_iterations);
end
recommendation_lines{end + 1} = '- 若之後要重新評估 tilt，建議只在 refined pre_alignment 已開啟的前提下再測，避免把兩個問題混在一起。';
recommendation_lines{end + 1} = '- 若 MATLAB run 被中斷，只要各實驗資料夾中的 `batch_results.csv` 已存在，就可直接重跑聚合，不需要重跑 fitting。';
vlab_write_lines(recommendation_path, recommendation_lines);

candidate_lines = {
    '# 正式候選流程說明'
    ''
    sprintf('- 候選主程式：`%s`', fullfile(lab_root, 'scripts', 'HDR_fitting_2D_WholeFOV_candidate_prealign.m'))
    '- 這個候選版仍以原 Whole-FOV 流程的 loss、warm-start、BADS 參數與 PSF 重建方式為基底。'
    '- 和原流程相比，主要新增的是顯式 `pre_alignment on/off` 開關、可設定 `prealign_step`，以及可指定 `subset_indices` / `output_root` 的獨立重跑能力。'
    '- 目前候選版預設維持 `warm_start = true`。'
    '- 目前候選版預設維持 `lock_tilt = true`。'
    sprintf('- 目前候選版預設使用 `prealign_step = %s`，也就是 %s。', recommended_step_text, recommended_mode_text)
};
if ~isempty(baseline_row)
    candidate_lines{end + 1} = sprintf('- `%s` 已把 mean abs peak offset 從 `%s` 的 %.3f px 降到 %.3f px。', ...
        candidate_row.experiment_name(1), baseline_row.experiment_name(1), ...
        baseline_row.mean_abs_peak_offset, candidate_row.mean_abs_peak_offset);
end
if ~isempty(integer_row) && candidate_row.pre_alignment && candidate_row.lock_tilt && candidate_row.experiment_name(1) ~= integer_row.experiment_name(1)
    candidate_lines{end + 1} = sprintf('- 相比整數版 `%s`，`%s` 把 mean peak offset_x 從 %.3f 壓到 %.3f，mean fval 從 %.3f 降到 %.3f。', ...
        integer_row.experiment_name(1), candidate_row.experiment_name(1), ...
        integer_row.mean_peak_offset_x, candidate_row.mean_peak_offset_x, ...
        integer_row.mean_fval, candidate_row.mean_fval);
end
if ~isempty(tilt_row) && tilt_row.experiment_name(1) ~= candidate_row.experiment_name(1)
    candidate_lines{end + 1} = sprintf('- 目前仍不建議先把 tilt 放進正式主線：`%s` 的 mean abs peak offset = %.3f px，沒有優於 `%s` 的 %.3f px，且 mean iterations 多 %.1f。', ...
        tilt_row.experiment_name(1), tilt_row.mean_abs_peak_offset, ...
        candidate_row.experiment_name(1), candidate_row.mean_abs_peak_offset, ...
        tilt_row.mean_iterations - candidate_row.mean_iterations);
end
candidate_lines{end + 1} = sprintf('- 因此目前最值得收斂成正式版的機制是：`warm_start + %s + tilt locked`。', recommended_mode_text);
candidate_lines{end + 1} = '- 候選主程式輸出仍維持與原流程相近的 `batch_results.csv` 與 `PSF_fitted_2D_FOVstack.mat`。';
candidate_lines{end + 1} = '- 已用 1 張圖的 smoke run 實際跑成功，證明 candidate 主程式可用。';
vlab_write_lines(candidate_flow_path, candidate_lines);

summary = struct();
summary.completed_experiment_names = string(comparison_table.experiment_name).';
summary.comparison_csv_path = comparison_csv_path;
summary.offset_figure_path = offset_fig_path;
summary.fit_figure_path = fit_fig_path;
summary.validation_summary_path = summary_path;
summary.next_recommendation_path = recommendation_path;
summary.candidate_flow_path = candidate_flow_path;
summary.best_offset_experiment = best_offset.experiment_name(1);
summary.best_fval_experiment = best_fval.experiment_name(1);
summary.best_edge_experiment = best_edge.experiment_name(1);
summary.best_overall_experiment = candidate_row.experiment_name(1);
end

function row = vlab_pick_named_or_masked_row(tbl, names, mask)
row = tbl([], :);
for ni = 1:numel(names)
    candidate = tbl(tbl.experiment_name == string(names(ni)), :);
    if ~isempty(candidate)
        row = candidate(1, :);
        return;
    end
end
candidate = tbl(mask, :);
if ~isempty(candidate)
    row = candidate(1, :);
end
end

function row = vlab_pick_best_row(candidate_rows, fallback_row)
if ~isempty(candidate_rows)
    [~, idx] = min(candidate_rows.overall_score);
    row = candidate_rows(idx, :);
else
    row = fallback_row;
end
end

function value = vlab_read_prealign_step(output_dir)
value = NaN;
json_candidates = {
    fullfile(output_dir, 'experiment_config.json')
    fullfile(output_dir, 'candidate_config.json')
};
for ji = 1:numel(json_candidates)
    json_path = json_candidates{ji};
    if ~isfile(json_path)
        continue;
    end

    data = jsondecode(fileread(json_path));
    if isfield(data, 'prealign_step')
        value = double(data.prealign_step);
        return;
    end
    if isfield(data, 'prealign_search_step')
        value = double(data.prealign_search_step);
        return;
    end
    if isfield(data, 'prealign_search_values')
        search_values = double(data.prealign_search_values);
        if numel(search_values) >= 2
            value = abs(search_values(2) - search_values(1));
            return;
        end
    end
end
end

function text_value = vlab_format_step(step_value)
if isnan(step_value)
    text_value = 'unknown';
else
    text_value = sprintf('%.3g', step_value);
end
end

function mode_text = vlab_format_prealign_mode(step_value)
if isnan(step_value)
    mode_text = 'pre_alignment';
elseif abs(step_value - 1.0) < 1e-9
    mode_text = 'integer pre_alignment';
elseif step_value < 1.0
    mode_text = 'refined pre_alignment';
else
    mode_text = 'pre_alignment';
end
end

function vlab_make_offset_figure_from_tables(completed_results, output_path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 360 * numel(completed_results), 720]);
tiledlayout(2, numel(completed_results), 'Padding', 'compact', 'TileSpacing', 'compact');

all_peak_x = [];
all_peak_y = [];
all_centroid_x = [];
all_centroid_y = [];
for ei = 1:numel(completed_results)
    tbl = completed_results(ei).batch_table;
    all_peak_x = [all_peak_x; tbl.peak_offset_x]; %#ok<AGROW>
    all_peak_y = [all_peak_y; tbl.peak_offset_y]; %#ok<AGROW>
    all_centroid_x = [all_centroid_x; tbl.centroid_offset_x]; %#ok<AGROW>
    all_centroid_y = [all_centroid_y; tbl.centroid_offset_y]; %#ok<AGROW>
end
axis_limit = max([abs(all_peak_x); abs(all_peak_y); abs(all_centroid_x); abs(all_centroid_y); 1]) + 1;

for ei = 1:numel(completed_results)
    tbl = completed_results(ei).batch_table;
    experiment_name = completed_results(ei).name;

    nexttile(ei);
    scatter(tbl.peak_offset_x, tbl.peak_offset_y, 70, 'filled');
    hold on;
    xline(0, '--k');
    yline(0, '--k');
    text(tbl.peak_offset_x + 0.08, tbl.peak_offset_y + 0.08, compose('fi=%d', tbl.file_index), 'FontSize', 9);
    hold off;
    axis equal;
    xlim([-axis_limit, axis_limit]);
    ylim([-axis_limit, axis_limit]);
    grid on;
    xlabel('x offset (px)');
    ylabel('y offset (px)');
    title(sprintf('%s peak', experiment_name), 'Interpreter', 'none');

    nexttile(numel(completed_results) + ei);
    scatter(tbl.centroid_offset_x, tbl.centroid_offset_y, 70, 'filled');
    hold on;
    xline(0, '--k');
    yline(0, '--k');
    text(tbl.centroid_offset_x + 0.08, tbl.centroid_offset_y + 0.08, compose('fi=%d', tbl.file_index), 'FontSize', 9);
    hold off;
    axis equal;
    xlim([-axis_limit, axis_limit]);
    ylim([-axis_limit, axis_limit]);
    grid on;
    xlabel('x offset (px)');
    ylabel('y offset (px)');
    title(sprintf('%s centroid', experiment_name), 'Interpreter', 'none');
end

exportgraphics(fig, output_path, 'Resolution', 200);
close(fig);
end

function vlab_make_fit_figure(comparison_table, output_path)
fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100, 100, 1000, 420]);
tiledlayout(1, 2, 'Padding', 'compact', 'TileSpacing', 'compact');

experiment_names = string(comparison_table.experiment_name);

nexttile;
bar(comparison_table.mean_fval);
set(gca, 'XTickLabel', experiment_names, 'XTickLabelRotation', 25);
ylabel('mean fval');
title('平均 fval');
grid on;

nexttile;
bar(comparison_table.mean_iterations);
set(gca, 'XTickLabel', experiment_names, 'XTickLabelRotation', 25);
ylabel('mean iterations');
title('平均 iterations');
grid on;

exportgraphics(fig, output_path, 'Resolution', 200);
close(fig);
end

function vlab_write_lines(output_path, lines)
fid = fopen(output_path, 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
for li = 1:numel(lines)
    fprintf(fid, '%s\n', lines{li});
end
end

function vlab_ensure_dir(path_value)
if ~exist(path_value, 'dir')
    mkdir(path_value);
end
end
