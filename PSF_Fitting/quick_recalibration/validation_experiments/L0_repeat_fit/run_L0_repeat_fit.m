% run_L0_repeat_fit.m
%
% L0 實驗:同一組 FOV 影像、同一起點 (x0=[0,...,0,1])、BADS 跑 N 次,
% 量出 Zernike 係數的「演算法 noise floor」。
%
% 設計參考:
%   PSF_Fitting/quick_recalibration/DESIGN_TW.md §10.2 (L0 層)
%   PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/README_TW.md
%
% 執行前提:
%   - MATLAB Current Folder 設為 d:\GMM_2_Final\PSF_Fitting\
%   - addpath('SimulatePSF') 已執行
%   - bads-1.1.3/ 在 path(底層 fitter 會自己 addpath,但保險起見)

clear; clc;

%% ===== 配置區(改這裡就好) =====
fov_indices = [1, 5, 10, 41, 45, 50, 91, 95, 100];   % 9 點:角落 + 中心 + 邊中
trial_range = [1, 15];                                % 從 trial_01 跑到 trial_15
                                                      % DESIGN §10.2 寫 N=5,但發現 5 輪不夠
                                                      % 抓出對稱解跳躍是稀有 vs 固定機率,擴增到 15
seed_base   = 0;                                      % rng(seed_base + trial_idx),確保可重現
skip_existing = true;                                 % 已有 stack.mat 的 trial 目錄跳過,保留前次心血

% 輸出根目錄(相對 PSF_Fitting/)
output_root = fullfile('quick_recalibration', 'validation_experiments', ...
                       'L0_repeat_fit', 'outputs');

% 衍生(別動下方)
n_trials = trial_range(2);   % manifest 紀錄總 trial 數

%% ===== 從 script 自身位置反推 PSF_Fitting/,並切過去 =====
% 注意:MATLAB 的 run() 會把 cwd 設為 script 所在目錄(L0_repeat_fit/),
% 不是 caller 的 cwd。所以不能依賴 pwd,要自己定位 project_root。
%
% script 位置:.../PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/run_L0_repeat_fit.m
% project_root = 三層 parent 上去 = .../PSF_Fitting/
script_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(script_dir)));

expected_marker = fullfile(project_root, 'HDR_fitting_2D_WholeFOV_impl.m');
if ~isfile(expected_marker)
    error('反推 project_root 失敗:%s 找不到 HDR_fitting_2D_WholeFOV_impl.m', project_root);
end

cd(project_root);
fprintf('project_root: %s\n', project_root);

if ~exist(output_root, 'dir')
    mkdir(output_root);
end

% 把 ValidationLab/scripts 加到 path,reasonable_v1/candidate_prealign 才找得到
addpath(fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts'));
addpath(fullfile(project_root, 'SimulatePSF'));

%% ===== 執行 trials =====
trial_dirs = strings(1, n_trials);
trial_seconds = nan(1, n_trials);   % NaN = 此 trial 沒在這次跑(可能既存 skip)

fprintf('\n========================================\n');
fprintf(' L0 Repeat Fit — %d FOV points x trials %d-%d\n', ...
    numel(fov_indices), trial_range(1), trial_range(2));
fprintf('========================================\n');
fprintf(' FOV indices : %s\n', mat2str(fov_indices));
fprintf(' Output root : %s\n', output_root);
fprintf(' Skip exist  : %s\n', mat2str(skip_existing));
fprintf(' Started at  : %s\n', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')));
fprintf('----------------------------------------\n\n');

t_overall = tic;
new_trial_count = 0;

for trial_idx = trial_range(1):trial_range(2)
    trial_dir = fullfile(output_root, sprintf('trial_%02d', trial_idx));
    trial_dirs(trial_idx) = string(trial_dir);

    % 已存在跳過(idempotent)
    existing_stack = fullfile(trial_dir, 'PSF_fitted_2D_FOVstack.mat');
    if skip_existing && isfile(existing_stack)
        fprintf('--- Trial %d: 已存在,skip (%s)\n', trial_idx, trial_dir);
        continue
    end

    % --- Trial 開始 banner + ETA ---
    timestamp = char(datetime('now', 'Format', 'HH:mm:ss'));
    if new_trial_count == 0
        eta_str = '(ETA unknown until first new trial done)';
    else
        new_seconds = trial_seconds(~isnan(trial_seconds));
        avg_per_trial = mean(new_seconds);
        remaining_count = trial_range(2) - trial_idx + 1;
        % 估剩下幾個還沒跑的(扣除已 skip 的)
        eta_min = avg_per_trial * remaining_count / 60;
        eta_str = sprintf('(ETA ~%.1f min for remaining %d trials)', eta_min, remaining_count);
    end
    fprintf('\n>>> [%s] Trial %d / %d starting %s\n', timestamp, trial_idx, trial_range(2), eta_str);
    fprintf('    output: %s\n', trial_dir);
    fprintf('    seed:   rng(%d)  |  fov_indices: %s\n\n', seed_base + trial_idx, mat2str(fov_indices));

    % 強制換 random seed,確保 BADS 內部 initial design 隨機性會被打到
    rng(seed_base + trial_idx);

    % 用 reasonable_v1 而不是 impl,因為:
    %   - impl 預設 grid_rows=10, grid_cols=10,如果 subset 只跑 N 點,
    %     repack 後其他 (100-N) 格填 0,會污染 std 計算
    %   - reasonable_v1 = 真正的 fitter wrapper,輸出 subset-order
    %     (coef_grid shape = (15, 1, N),沒有空格子)
    t_trial = tic;
    HDR_fitting_2D_WholeFOV_reasonable_v1( ...
        'subset_indices', fov_indices, ...
        'output_root',    trial_dir);
    trial_seconds(trial_idx) = toc(t_trial);
    new_trial_count = new_trial_count + 1;

    % --- Trial 結束小結 ---
    timestamp = char(datetime('now', 'Format', 'HH:mm:ss'));
    csv_path = fullfile(trial_dir, 'batch_results.csv');
    if isfile(csv_path)
        try
            tbl = readtable(csv_path, TextType = "string");
            fval_min = min(tbl.fval);
            fval_max = max(tbl.fval);
            fval_mean = mean(tbl.fval);
            iter_mean = mean(tbl.iterations);
            fprintf('<<< [%s] Trial %d done in %.1f s (%.2f min)\n', ...
                timestamp, trial_idx, trial_seconds(trial_idx), trial_seconds(trial_idx)/60);
            fprintf('    fval: min=%.2f, mean=%.2f, max=%.2f  |  mean iters: %.0f\n', ...
                fval_min, fval_mean, fval_max, iter_mean);
        catch
            fprintf('<<< [%s] Trial %d done in %.1f s (csv read failed)\n', ...
                timestamp, trial_idx, trial_seconds(trial_idx));
        end
    else
        fprintf('<<< [%s] Trial %d done in %.1f s (no csv?)\n', ...
                timestamp, trial_idx, trial_seconds(trial_idx));
    end
end

total_seconds = toc(t_overall);

%% ===== 寫 manifest.json =====
% 這份檔記錄這次跑的所有選擇,讓 analyze_L0_noise_floor.py 知道要讀哪些 trial,
% 也讓未來重看 outputs/ 時知道當時的 git 狀態與 MATLAB 版本。
project_root = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
[git_status, git_commit] = system(sprintf('git -C "%s" rev-parse HEAD', project_root));
if git_status ~= 0
    git_commit = 'unknown';
else
    git_commit = strtrim(git_commit);
end
[git_status, git_branch] = system(sprintf('git -C "%s" rev-parse --abbrev-ref HEAD', project_root));
if git_status ~= 0
    git_branch = 'unknown';
else
    git_branch = strtrim(git_branch);
end

% gpuDeviceCount 在沒裝 Parallel Computing Toolbox 的環境會 throw,包起來
try
    gpu_available = gpuDeviceCount > 0;
catch
    gpu_available = false;
end

% 用 dot-assignment 而不是 struct(...) constructor,後者對 cell array 會
% 自動 broadcast 成 N-element struct array(不是 scalar struct with cell field),
% 之後再 dot-assign 會 throw "Scalar structure required for this assignment".
manifest = struct();
manifest.experiment    = 'L0_repeat_fit';
manifest.design_doc    = 'PSF_Fitting/quick_recalibration/DESIGN_TW.md';
manifest.fov_indices   = fov_indices;
manifest.n_trials      = n_trials;
manifest.seed_base     = seed_base;
manifest.rng_seeds     = seed_base + (1:n_trials);
manifest.trial_dirs    = cellstr(trial_dirs);
manifest.trial_seconds = trial_seconds;
manifest.total_seconds = total_seconds;
manifest.completed_at  = char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss'));
manifest.matlab_version = version;
manifest.gpu_available = gpu_available;
manifest.git_commit    = git_commit;
manifest.git_branch    = git_branch;
manifest.project_root  = project_root;

% started_at = completed_at - total_seconds(回推)
started_dt = datetime('now') - seconds(total_seconds);
started_dt.Format = 'yyyy-MM-dd HH:mm:ss';
manifest.started_at = char(started_dt);

manifest_path = fullfile(output_root, 'manifest.json');
fid = fopen(manifest_path, 'w');
fprintf(fid, '%s\n', jsonencode(manifest, 'PrettyPrint', true));
fclose(fid);

fprintf('========================================\n');
fprintf(' Done. Total: %.1f min\n', total_seconds / 60);
fprintf(' Manifest: %s\n', manifest_path);
fprintf('========================================\n');
fprintf('\n下一步:在 PowerShell 跑\n');
fprintf('  python PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/analyze_L0_noise_floor.py\n\n');
