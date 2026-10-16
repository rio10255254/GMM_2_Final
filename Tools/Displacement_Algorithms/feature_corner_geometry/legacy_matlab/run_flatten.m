% 清除變數和圖窗
clear all; close all;

% 指定輸入目錄和GT圖像路徑
input_dir = "D:\NonSystemFiles\GMM2\0416_crop\0416_crop_corrected\"; % 修改為您的輸入目錄
gt_path = "D:\NonSystemFiles\GMM2\GT.bmp"; % GT圖像保持不變

% 創建結果目錄
result_dir = 'D:\NonSystemFiles\GMM2\0416_crop\BADS_Results';  % 使用絕對路徑
if ~exist(result_dir, 'dir')
    mkdir(result_dir);
    fprintf('創建了結果目錄: %s\n', result_dir);
end

% 定義輸出目錄 (在呼叫函數前先定義)
output_dir = result_dir;

% 確認目錄和GT文件存在
if ~exist(input_dir, 'dir')
    error('輸入目錄不存在: %s', input_dir);
end
if ~exist(gt_path, 'file')
    error('GT圖像不存在: %s', gt_path);
end

% 獲取目錄中的所有圖像文件
img_files = dir(fullfile(input_dir, '*.bmp'));
img_files = [img_files; dir(fullfile(input_dir, '*.jpg'))];
img_files = [img_files; dir(fullfile(input_dir, '*.png'))];
img_files = [img_files; dir(fullfile(input_dir, '*.tif'))];

% 檢查是否找到了圖像文件
if isempty(img_files)
    error('在指定目錄中未找到圖像文件: %s', input_dir);
end

% 顯示使用的路徑和將處理的文件數量
fprintf('輸入目錄: %s\n', input_dir);
fprintf('GT圖像: %s\n', gt_path);
fprintf('輸出目錄: %s\n', output_dir);
fprintf('將處理 %d 個圖像文件\n', length(img_files));

% 將GT路徑轉換為字符數組
gt_path_char = char(gt_path);

% 創建結果記錄
results_log = cell(length(img_files), 5);
header = {'檔案名', '原始MSE', '校正後MSE', 'MSE改善(%)', '成功'};

% 處理每個圖像文件
for i = 1:length(img_files)
    img_path = fullfile(img_files(i).folder, img_files(i).name);
    [~, name, ext] = fileparts(img_files(i).name);
    fprintf('\n處理圖像 %d/%d: %s\n', i, length(img_files), img_files(i).name);
    
    results_log{i, 1} = img_files(i).name;
    
    try
        % 將圖像路徑轉換為字符數組
        img_path_char = char(img_path);
        
        % 呼叫校正函數 (現在output_dir已定義)
        corrected_img = autoFlattenCheckerboard3(img_path_char, gt_path_char, output_dir);
        
        % 保存校正後的圖像到結果目錄
        save_path = fullfile(result_dir, [name, '_flat_bads', ext]);
        imwrite(corrected_img, save_path);
        fprintf('校正後的圖像已保存為: %s\n', save_path);

        
        % 計算原始圖像與校正後圖像的MSE
        try
            % 載入原始圖像與GT圖像
            orig_img = imread(img_path);
            gt_img = imread(gt_path);
            
            % 調整GT圖像大小以匹配原始圖像
            gt_resized_orig = imresize(gt_img, size(orig_img, [1, 2]));
            
            % 計算原始圖像的MSE
            if size(orig_img, 3) == 3 && size(gt_resized_orig, 3) == 3
                orig_mse = mean(mean(mean((double(orig_img) - double(gt_resized_orig)).^2)));
            else
                orig_mse = mean(mean((double(orig_img) - double(gt_resized_orig)).^2));
            end
            
            % 調整GT圖像大小以匹配校正後圖像
            gt_resized_corr = imresize(gt_img, size(corrected_img, [1, 2]));
            
            % 計算校正後圖像的MSE
            if size(corrected_img, 3) == 3 && size(gt_resized_corr, 3) == 3
                corr_mse = mean(mean(mean((double(corrected_img) - double(gt_resized_corr)).^2)));
            else
                corr_mse = mean(mean((double(corrected_img) - double(gt_resized_corr)).^2));
            end
            
            % 計算MSE改善百分比
            mse_improvement = (orig_mse - corr_mse) / orig_mse * 100;
            
            % 將結果儲存到記錄中
            results_log{i, 2} = orig_mse;
            results_log{i, 3} = corr_mse;
            results_log{i, 4} = mse_improvement;
            results_log{i, 5} = 'Yes';
            
            fprintf('MSE分析: 原始=%.2f, 校正後=%.2f, 改善=%.2f%%\n', ...
                orig_mse, corr_mse, mse_improvement);
        catch err_mse
            fprintf('計算MSE時發生錯誤: %s\n', err_mse.message);
            results_log{i, 5} = 'Yes (MSE計算失敗)';
        end
        
    catch err
        % 顯示詳細錯誤訊息
        fprintf('處理圖像 %s 時發生錯誤: %s\n', img_files(i).name, err.message);
        fprintf('跳過此圖像並繼續下一個\n');
        
        % 更新結果記錄
        results_log{i, 5} = 'No';
    end
end

% 將結果記錄保存為CSV檔案
results_table = cell2table(results_log, 'VariableNames', header);
writetable(results_table, fullfile(result_dir, 'processing_results.csv'));

fprintf('\n批量處理完成！總共處理了 %d 個圖像文件\n', length(img_files));
fprintf('結果摘要已保存至: %s\n', fullfile(result_dir, 'processing_results.csv'));