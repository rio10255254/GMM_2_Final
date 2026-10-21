function corrected_img = autoFlattenCheckerboard2(img_path, gt_path, output_dir)
    % 檢查是否提供了圖像路徑
    if nargin < 1 || isempty(img_path)
        % 讓用戶選擇檔案
        [filename, pathname] = uigetfile({'*.bmp;*.jpg;*.png;*.tif', '圖像檔案 (*.bmp, *.jpg, *.png, *.tif)'}, '選擇棋盤格圖像');
        if filename == 0
            error('未選擇任何檔案。');
        end
        img_path = fullfile(pathname, filename);
    end
    
    % 提取文件名和路徑，用於後續保存結果
    [filepath, name, ext] = fileparts(img_path);
    
    % 確定輸出目錄
    if nargin < 3 || isempty(output_dir)
        % 如果未提供輸出目錄，則在輸入圖像所在目錄下創建BADS_Results目錄
        results_dir = fullfile(filepath, 'BADS_Results');
    else
        % 使用提供的輸出目錄
        results_dir = output_dir;
    end
    
    % 創建結果保存目錄（如果是在批處理模式中調用）
    if ~exist(results_dir, 'dir')
        mkdir(results_dir);
        fprintf('已創建結果目錄: %s\n', results_dir);
    end
    
    % 創建圖形保存目錄
    figure_dir = fullfile(results_dir, 'analysis_figures');
    if ~exist(figure_dir, 'dir')
        mkdir(figure_dir);
        fprintf('已創建圖形分析結果目錄: %s\n', figure_dir);
    end
    
    % 清除所有之前的圖形窗口
    close all;
    
    % 檢查是否提供了GT路徑
    has_gt = (nargin >= 2) && ~isempty(gt_path);
    if has_gt
        try
            gt_img = imread(gt_path);
        catch e
            warning('無法載入GT圖像，將不進行比較: %s', e.message);
            has_gt = false;
        end
    end
        
    % 檢查BADS是否已安裝
    if ~exist('bads', 'file')
        error('請先安裝BADS優化工具。可從 https://github.com/acerbilab/bads 下載。');
    end
    
    % 載入圖像
    try
        img = imread(img_path);
        if size(img, 3) == 3
            img_gray = rgb2gray(img);
        else
            img_gray = img;
            img = repmat(img_gray, [1, 1, 3]);
        end
    catch e
        error('無法載入圖像，請檢查路徑: %s', e.message);
    end
    
    % 如果有GT圖像，載入它
    if has_gt
        try
            gt_img = imread(gt_path);
            if size(gt_img, 3) == 3
                gt_img_gray = rgb2gray(gt_img);
            else
                gt_img_gray = gt_img;
                gt_img = repmat(gt_img_gray, [1, 1, 3]);
            end
        catch e
            warning('無法載入GT圖像，將不進行比較: %s', e.message);
            has_gt = false;
        end
    end
    
    % 創建圖形佈局 - 使用固定的Figure句柄以便後續引用
    h_fig1 = figure(1);
    set(h_fig1, 'Name', '棋盤格校正處理', 'Position', [100, 100, 1200, 800]);
    
    % 顯示原始圖像
    subplot(2, 3, 1);
    imshow(img);
    title('原始圖像');
    drawnow; % 確保立即更新
    
    % 檢測外部角點
    disp('正在檢測棋盤格外部角點...');
    [corners, vis_img] = detect_outer_corners(img_gray, img);
    
    % 顯示檢測結果
    subplot(2, 3, 2);
    imshow(vis_img);
    title('檢測到的棋盤格角點');
    drawnow; % 確保立即更新
    
    % 定義棋盤格網格大小 (内角點的行數和列數)
    rows_grid = 5; 
    cols_grid = 5;
    
    % 基於四個角點生成完整網格
    grid_points = generate_grid_from_corners(corners, rows_grid, cols_grid);
    
    % 顯示網格點
    subplot(2, 3, 3);
    imshow(img);
    hold on;
    plot(grid_points(:,1), grid_points(:,2), 'ro', 'MarkerSize', 6);
    title('基於檢測角點生成的網格');
    drawnow; % 確保立即更新
    
    % 定義BADS優化的成本函數
    function cost = edge_length_cost(params)
        % 參數解釋:
        % params(1): horizontal_scale - 水平縮放因子
        % params(2): vertical_scale - 垂直縮放因子
        % params(3): perspective_x - x方向透視因子
        % params(4): perspective_y - y方向透視因子
        
        % 獲取四個角點
        tl = corners(1,:);
        tr = corners(2,:);
        bl = corners(3,:);
        br = corners(4,:);
        
        % 計算原始中心點
        center_x = mean([tl(1), tr(1), bl(1), br(1)]);
        center_y = mean([tl(2), tr(2), bl(2), br(2)]);
        
        % 應用參數調整
        h_scale = params(1);
        v_scale = params(2);
        persp_x = params(3);
        persp_y = params(4);
        
        % 創建變換矩陣
        T = [h_scale, 0, 0; 
             0, v_scale, 0; 
             persp_x, persp_y, 1];
        
        % 轉換為齊次坐標
        tl_h = [tl - [center_x, center_y], 1] * T;
        tr_h = [tr - [center_x, center_y], 1] * T;
        bl_h = [bl - [center_x, center_y], 1] * T;
        br_h = [br - [center_x, center_y], 1] * T;
        
        % 從齊次坐標轉回
        tl_new = [tl_h(1)/tl_h(3), tl_h(2)/tl_h(3)] + [center_x, center_y];
        tr_new = [tr_h(1)/tr_h(3), tr_h(2)/tr_h(3)] + [center_x, center_y];
        bl_new = [bl_h(1)/bl_h(3), bl_h(2)/bl_h(3)] + [center_x, center_y];
        br_new = [br_h(1)/br_h(3), br_h(2)/br_h(3)] + [center_x, center_y];
        
        % 計算轉換後的四邊長度
        top_edge = norm(tr_new - tl_new);
        bottom_edge = norm(br_new - bl_new);
        left_edge = norm(bl_new - tl_new);
        right_edge = norm(br_new - tr_new);
        
        % 計算邊長差異的成本
        edges = [top_edge, bottom_edge, left_edge, right_edge];
        avg_edge = mean(edges);
        edge_diffs = abs(edges - avg_edge);
        
        % 基本成本 - 邊長差異越小越好
        edge_cost = sum(edge_diffs);
        
        % 添加對角線比例作為附加約束
        diag1 = norm(br_new - tl_new);
        diag2 = norm(bl_new - tr_new);
        diag_ratio = max(diag1/diag2, diag2/diag1);
        
        % 理想的對角線比例應為1
        diag_cost = abs(diag_ratio - 1) * 100;
        
        % 幾何約束成本
        geo_cost = edge_cost + diag_cost;
        
        % 初始化總成本
        cost = geo_cost;
        
        % 額外成本組件: 如果有GT圖像，加入MSE
        if has_gt
            try
                % 計算透視變換矩陣(從優化後的角點到完美正方形)
                sourcePoints = double([tl_new; tr_new; bl_new; br_new]);
                
                % 創建目標正方形
                square_tl = [center_x - avg_edge/2, center_y - avg_edge/2];
                square_tr = [center_x + avg_edge/2, center_y - avg_edge/2];
                square_bl = [center_x - avg_edge/2, center_y + avg_edge/2];
                square_br = [center_x + avg_edge/2, center_y + avg_edge/2];
                
                targetPoints = double([square_tl; square_tr; square_bl; square_br]);
                
                tform = fitgeotrans(sourcePoints, targetPoints, 'projective');
                temp_corrected = imwarp(img, tform, 'OutputView', imref2d(size(img)));
                
                % 調整GT圖像大小以與校正圖像匹配
                temp_gt_resized = imresize(gt_img, size(temp_corrected, [1, 2]));
                
                % 計算MSE
                if size(temp_corrected, 3) == 3 && size(temp_gt_resized, 3) == 3
                    mse_val = mean(mean(mean((double(temp_corrected) - double(temp_gt_resized)).^2)));
                else
                    mse_val = mean(mean((double(temp_corrected) - double(temp_gt_resized)).^2));
                end
                
                % 計算原始MSE作為參考
                orig_gt_resized = imresize(gt_img, size(img, [1, 2]));
                if size(img, 3) == 3 && size(orig_gt_resized, 3) == 3
                    orig_mse = mean(mean(mean((double(img) - double(orig_gt_resized)).^2)));
                else
                    orig_mse = mean(mean((double(img) - double(orig_gt_resized)).^2));
                end
                
                % 只有在MSE優於原始值時才使用幾何約束，否則以MSE為主
                if mse_val <= orig_mse
                    % MSE較好，可以兼顧幾何約束
                    cost = geo_cost + mse_val * 0.1;  % 較小權重
                else
                    % MSE較差，優先考慮MSE
                    mse_improvement = (orig_mse - mse_val) / orig_mse;  % 改善百分比
                    % 如果MSE變差，給予嚴重懲罰
                    cost = geo_cost + (1 - mse_improvement) * 1000;  
                end
                
            catch
                % 若變換失敗，給予嚴重懲罰
                cost = cost + 10000;
            end
        end
    end

    % 設定BADS優化參數
    disp('正在使用多起始點BADS優化透視變換參數...');
    
    % 參數硬性上下限
    lb = [0.1, 0.1, -0.001, -0.001];  % 下限
    ub = [3.0, 3.0, 0.001, 0.001];    % 上限
    
    % 參數合理上下限（比硬性界限更窄）
    plb = [0.8, 0.8, -0.0008, -0.0008];  % 合理下限
    pub = [1.2, 1.2, 0.0008, 0.0008];    % 合理上限
    
    % 設定多個起始點數量
    num_starts = 8;  % 稍微減少起始點數量，增加成功率
    
    % 定義多個起始點
    start_points = cell(num_starts, 1);
    start_points{1} = [1.0, 1.0, 0, 0];             % 預設
    start_points{2} = [0.95, 1.05, 0, 0];           % 略微縮放差異
    start_points{3} = [1.0, 1.0, 0.0005, 0.0005];   % 略微透視
    start_points{4} = [1.05, 0.95, -0.0005, 0.0005]; % 混合變化
    start_points{5} = [1.1, 0.9, 0, 0];             % 較溫和的縮放
    start_points{6} = [0.9, 1.1, 0, 0];             % 反向溫和縮放
    start_points{7} = [1.0, 1.0, -0.0005, -0.0005]; % 反向透視
    start_points{8} = [1.0, 1.0, 0.0001, -0.0001];  % 混合透視
    
    % 設置BADS基本選項（刪除可能有問題的選項）
    options = bads('defaults');
    options.MaxIter = 500;         % 最大迭代次數
    options.MaxFunEvals = 1000;    % 最大函數評估次數
    options.Display = 'iter';      % 顯示優化過程
    
    % 運行多個BADS優化，嘗試不同起始點
    best_fval = inf;
    best_x_opt = [];
    
    for i = 1:num_starts
        disp(['開始BADS優化運行 ' num2str(i) '/' num2str(num_starts)]);
        disp(['起始參數: ' mat2str(start_points{i})]);
        
        try
            % 使用簡化版的BADS調用，確保兼容性
            [x_opt, fval] = bads(@edge_length_cost, start_points{i}, lb, ub, plb, pub);
            
            disp(['運行 ' num2str(i) ' 完成。成本: ' num2str(fval)]);
            
            % 檢查這是否是迄今為止最佳結果
            if fval < best_fval
                best_fval = fval;
                best_x_opt = x_opt;
                disp(['發現新的最佳參數: ' mat2str(best_x_opt)]);
                disp(['新的最佳成本: ' num2str(best_fval)]);
            end
        catch e
            warning(['優化運行 ' num2str(i) ' 失敗: ' e.message]);
            continue; % 跳到下一個起始點
        end
    end
    
    % 如果所有運行都失敗，使用默認值
    if isempty(best_x_opt)
        warning('所有優化運行都失敗了。使用默認參數。');
        best_x_opt = [1.0, 1.0, 0, 0];
        best_fval = inf;
    end
    
    x_opt = best_x_opt;
    fval = best_fval;
    
    disp('優化完成。最佳參數:');
    disp(x_opt);
    disp(['最終成本: ', num2str(fval)]);
    
    % 應用最佳參數進行校正
    % 獲取四個角點
    tl = corners(1,:);
    tr = corners(2,:);
    bl = corners(3,:);
    br = corners(4,:);
    
    % 計算原始中心點
    center_x = mean([tl(1), tr(1), bl(1), br(1)]);
    center_y = mean([tl(2), tr(2), bl(2), br(2)]);
    
    % 應用最佳參數調整
    h_scale = x_opt(1);
    v_scale = x_opt(2);
    persp_x = x_opt(3);
    persp_y = x_opt(4);
    
    % 創建變換矩陣
    T = [h_scale, 0, 0; 
         0, v_scale, 0; 
         persp_x, persp_y, 1];
    
    % 轉換為齊次坐標
    tl_h = [tl - [center_x, center_y], 1] * T;
    tr_h = [tr - [center_x, center_y], 1] * T;
    bl_h = [bl - [center_x, center_y], 1] * T;
    br_h = [br - [center_x, center_y], 1] * T;
    
    % 從齊次坐標轉回
    tl_new = [tl_h(1)/tl_h(3), tl_h(2)/tl_h(3)] + [center_x, center_y];
    tr_new = [tr_h(1)/tr_h(3), tr_h(2)/tr_h(3)] + [center_x, center_y];
    bl_new = [bl_h(1)/bl_h(3), bl_h(2)/bl_h(3)] + [center_x, center_y];
    br_new = [br_h(1)/br_h(3), br_h(2)/br_h(3)] + [center_x, center_y];
    
    % 計算轉換後的四邊長度
    top_edge = norm(tr_new - tl_new);
    bottom_edge = norm(br_new - bl_new);
    left_edge = norm(bl_new - tl_new);
    right_edge = norm(br_new - tr_new);
    
    % 計算平均邊長作為目標正方形大小
    avg_edge = mean([top_edge, bottom_edge, left_edge, right_edge]);
    
    % 創建目標正方形
    square_tl = [center_x - avg_edge/2, center_y - avg_edge/2];
    square_tr = [center_x + avg_edge/2, center_y - avg_edge/2];
    square_bl = [center_x - avg_edge/2, center_y + avg_edge/2];
    square_br = [center_x + avg_edge/2, center_y + avg_edge/2];
    
    % 計算透視變換矩陣 (從優化後的角點到完美正方形)
    sourcePoints = double([tl_new; tr_new; bl_new; br_new]);
    targetPoints = double([square_tl; square_tr; square_bl; square_br]);
    
    tform = fitgeotrans(sourcePoints, targetPoints, 'projective');
    
    % 應用變換
    outputView = imref2d(size(img_gray));
    corrected_img = imwarp(img, tform, 'OutputView', outputView);


    % 填充校正後圖像中的黑色區域
    % 檢測黑色（或接近黑色）的像素
    black_mask = false(size(corrected_img, 1), size(corrected_img, 2));
    if size(corrected_img, 3) == 3
        % 對於RGB圖像，檢查所有通道是否接近零
        black_mask = all(corrected_img < 10, 3);
    else
        % 對於灰度圖像
        black_mask = corrected_img < 10;
    end
    
    % 確定背景顏色，通過採樣圖像邊緣區域
    border_width = 20;
    border_mask = false(size(corrected_img, 1), size(corrected_img, 2));
    border_mask(1:border_width, :) = true;  % 上邊框
    border_mask(end-border_width+1:end, :) = true;  % 下邊框
    border_mask(:, 1:border_width) = true;  % 左邊框
    border_mask(:, end-border_width+1:end) = true;  % 右邊框
    
    % 只考慮邊框中非黑色的像素作為背景顏色採樣
    border_mask = border_mask & ~black_mask;
    
    % 計算背景顏色
    if size(corrected_img, 3) == 3
        % 對於RGB圖像
        bg_color = zeros(1, 1, 3);
        for c = 1:3
            channel = corrected_img(:,:,c);
            bg_color(1, 1, c) = median(double(channel(border_mask)));
        end
    else
        % 對於灰度圖像
        bg_color = median(double(corrected_img(border_mask)));
    end
    
    % 用背景顏色填充黑色區域
    if size(corrected_img, 3) == 3
        % 對於RGB圖像
        for c = 1:3
            channel = corrected_img(:,:,c);
            channel(black_mask) = bg_color(1, 1, c);
            corrected_img(:,:,c) = channel;
        end
    else
        % 對於灰度圖像
        corrected_img(black_mask) = bg_color;
    end
    
    fprintf('已填充 %d 個黑色像素（%.2f%%的圖像）\n', sum(black_mask(:)), sum(black_mask(:))/numel(black_mask)*100);  
    
    % 顯示校正結果
    subplot(2, 3, 4);
    imshow(corrected_img);
    title('校正後的圖像');
    drawnow; % 立即更新顯示
    
    % 顯示優化前後的四邊長度
    subplot(2, 3, 5);
    
    % 原始邊長
    orig_edges = [norm(tr - tl), norm(br - bl), norm(bl - tl), norm(br - tr)];
    
    % 優化後的邊長
    opt_edges = [top_edge, bottom_edge, left_edge, right_edge];
    
    % 最終校正後的邊長 (理論上都是avg_edge)
    final_edges = [avg_edge, avg_edge, avg_edge, avg_edge];
    
    % 創建條形圖
    bar([orig_edges; opt_edges; final_edges]');
    set(gca, 'XTickLabel', {'上邊', '下邊', '左邊', '右邊'});
    legend('原始', '優化中間值', '最終校正');
    title('四邊長度對比 (像素)');
    ylabel('長度');
    grid on;
    drawnow; % 立即更新顯示
    
    % 顯示校正效果分析
    subplot(2, 3, 6);
    text(0.1, 0.9, '校正效果分析:', 'FontSize', 12, 'FontWeight', 'bold');
    
    % 計算原始對角線比例
    orig_diag1 = norm(br - tl);
    orig_diag2 = norm(bl - tr);
    orig_diag_ratio = orig_diag1 / orig_diag2;
    
    % 計算校正後對角線比例 (理論上為1)
    text(0.1, 0.8, sprintf('原始對角線比例: %.4f', orig_diag_ratio), 'FontSize', 10);
    text(0.1, 0.7, '校正後對角線比例: 1.0000', 'FontSize', 10);
    
    % 計算原始最大邊長差異
    orig_max_diff = max(orig_edges) - min(orig_edges);
    text(0.1, 0.5, sprintf('原始最大邊長差異: %.2f px', orig_max_diff), 'FontSize', 10);
    text(0.1, 0.4, '校正後邊長差異: 0.0 px', 'FontSize', 10);
    
    % 顯示BADS優化訊息
    text(0.1, 0.2, sprintf('BADS優化迭代 (多起始點): %d x %d', options.MaxIter, num_starts), 'FontSize', 10);
    text(0.1, 0.1, sprintf('最終成本: %.6f', fval), 'FontSize', 10);
    
    axis off;
    drawnow; % 立即更新顯示
    
    % 保存校正分析圖形
    fig1_filename = fullfile(figure_dir, [name, '_correction_analysis.png']);
    saveas(h_fig1, fig1_filename);
    fprintf('校正分析圖已保存為: %s\n', fig1_filename);
    
    % 保存校正後的圖像
    output_path = fullfile(results_dir, [name, '_flat_bads', ext]);
    imwrite(corrected_img, output_path);
    fprintf('校正後的圖像已保存為: %s\n', output_path);
    
    % 如果有GT圖像，計算並顯示MSE和差異圖
    if has_gt
        % 創建新圖形顯示GT比較 - 改為2x3佈局以容納校正前後比較
        h_fig2 = figure(2);
        set(h_fig2, 'Name', '與Ground Truth比較', 'Position', [100, 100, 1200, 800]);
        
        % === 第一行：原始圖像與GT的比較 ===
        % 顯示GT圖像
        subplot(2, 3, 1);
        imshow(gt_img);
        title('Ground Truth圖像');
        drawnow; % 立即更新顯示
        
        % 顯示原始圖像
        subplot(2, 3, 2);
        imshow(img);
        title('原始圖像');
        drawnow; % 立即更新顯示
        
        % 調整GT圖像大小以便與原始圖像比較
        gt_img_resized_orig = imresize(gt_img, size(img, [1, 2]));
        
        % 計算原始圖像與GT的MSE
        if size(img, 3) == 3 && size(gt_img_resized_orig, 3) == 3
            mse_val_orig = mean(mean(mean((double(img) - double(gt_img_resized_orig)).^2)));
        else
            mse_val_orig = mean(mean((double(img) - double(gt_img_resized_orig)).^2));
        end
        
        % 顯示原始圖像與GT的差異圖
        subplot(2, 3, 3);
        diff_img_orig = abs(double(img) - double(gt_img_resized_orig));
        if size(diff_img_orig, 3) == 3
            diff_img_orig = mean(diff_img_orig, 3); % 轉為灰度差異
        end
        diff_img_orig = diff_img_orig / max(diff_img_orig(:) + eps); % 正規化以便顯示
        imshow(diff_img_orig);
        colormap(gca, 'jet');
        colorbar;
        title(sprintf('原始與GT差異 (MSE: %.4f)', mse_val_orig));
        drawnow; % 立即更新顯示
        
        % === 第二行：校正後圖像與GT的比較 ===
        % 顯示GT圖像
        subplot(2, 3, 4);
        imshow(gt_img);
        title('Ground Truth圖像');
        drawnow; % 立即更新顯示
        
        % 顯示校正後圖像
        subplot(2, 3, 5);
        imshow(corrected_img);
        title('校正後圖像');
        drawnow; % 立即更新顯示
        
        % 調整GT圖像大小以便與校正後圖像比較
        gt_img_resized = imresize(gt_img, size(corrected_img, [1, 2]));
        
        % 計算校正後圖像與GT的MSE
        if size(corrected_img, 3) == 3 && size(gt_img_resized, 3) == 3
            mse_val = mean(mean(mean((double(corrected_img) - double(gt_img_resized)).^2)));
        else
            mse_val = mean(mean((double(corrected_img) - double(gt_img_resized)).^2));
        end
        
        % 顯示校正後圖像與GT的差異圖
        subplot(2, 3, 6);
        diff_img = abs(double(corrected_img) - double(gt_img_resized));
        if size(diff_img, 3) == 3
            diff_img = mean(diff_img, 3); % 轉為灰度差異
        end
        diff_img = diff_img / max(diff_img(:) + eps); % 正規化以便顯示
        imshow(diff_img);
        colormap(gca, 'jet');
        colorbar;
        title(sprintf('校正後與GT差異 (MSE: %.4f)', mse_val));
        drawnow; % 立即更新顯示
        
        % 保存GT比較圖形
        fig2_filename = fullfile(figure_dir, [name, '_gt_comparison.png']);
        saveas(h_fig2, fig2_filename);
        fprintf('GT比較圖已保存為: %s\n', fig2_filename);
        
        % 顯示比較結果
        fprintf('與Ground Truth比較:\n');
        fprintf('  原始圖像 MSE: %.4f\n', mse_val_orig);
        fprintf('  校正後圖像 MSE: %.4f\n', mse_val);
        fprintf('  MSE改善量: %.4f (%.2f%%)\n', mse_val_orig - mse_val, (mse_val_orig - mse_val) / mse_val_orig * 100);
        
        % 計算SSIM (結構相似性指數)
        if exist('ssim', 'file')
            % 計算原始圖像與GT的SSIM
            if size(img, 3) == 3 && size(gt_img_resized_orig, 3) == 3
                ssim_val_orig = ssim(rgb2gray(img), rgb2gray(gt_img_resized_orig));
            else
                ssim_val_orig = ssim(img, gt_img_resized_orig);
            end
            
            % 計算校正後圖像與GT的SSIM
            if size(corrected_img, 3) == 3 && size(gt_img_resized, 3) == 3
                ssim_val = ssim(rgb2gray(corrected_img), rgb2gray(gt_img_resized));
            else
                ssim_val = ssim(corrected_img, gt_img_resized);
            end
            
            fprintf('  原始圖像 SSIM: %.4f\n', ssim_val_orig);
            fprintf('  校正後圖像 SSIM: %.4f\n', ssim_val);
            fprintf('  SSIM改善量: %.4f (%.2f%%)\n', ssim_val - ssim_val_orig, (ssim_val - ssim_val_orig) / ssim_val_orig * 100);
        end
        
        % 計算PSNR (峰值信噪比)
        % 計算原始圖像與GT的PSNR
        if size(img, 3) == 3 && size(gt_img_resized_orig, 3) == 3
            psnr_val_orig = psnr(img, gt_img_resized_orig);
        else
            psnr_val_orig = psnr(img, gt_img_resized_orig);
        end
        
        % 計算校正後圖像與GT的PSNR
        if size(corrected_img, 3) == 3 && size(gt_img_resized, 3) == 3
            psnr_val = psnr(corrected_img, gt_img_resized);
        else
            psnr_val = psnr(corrected_img, gt_img_resized);
        end
        
        fprintf('  原始圖像 PSNR: %.4f dB\n', psnr_val_orig);
        fprintf('  校正後圖像 PSNR: %.4f dB\n', psnr_val);
        fprintf('  PSNR改善量: %.4f dB (%.2f%%)\n', psnr_val - psnr_val_orig, (psnr_val - psnr_val_orig) / psnr_val_orig * 100);
    end
    
    % 如果是批處理模式，在完成一個圖像的處理後暫停一下，讓使用者有機會查看結果
    if isempty(findobj('Type', 'figure', 'Tag', 'BatchProcessing'))
        pause(0.1);
    end
end

% 輔助函數: 檢測圖像中大正方形的外部角點
function [corners, vis_img] = detect_outer_corners(gray_img, color_img)
    % 創建可視化圖像
    if size(color_img, 3) == 3
        vis_img = color_img;
    else
        vis_img = repmat(mat2gray(gray_img), [1, 1, 3]);
    end
    
    % 方法1: 嘗試使用棋盤格檢測函數
    try
        [points, boardSize] = detectCheckerboardPoints(gray_img);
        
        if ~isempty(points) && ~isempty(boardSize)
            % 在可視化圖像上繪製檢測到的點
            vis_img = insertMarker(vis_img, points, 'o', 'Color', 'green', 'Size', 5);
            
            % 如果檢測到的是内部點，擴展到外部角點
            if any(boardSize > 1)  % 確保至少檢測到了一個完整的棋盤格
                % 尋找四個極值點（最左上、最右上、最左下、最右下）
                % 計算每個點的 x+y 和 x-y 值
                sum_coords = points(:,1) + points(:,2);
                diff_coords = points(:,1) - points(:,2);
                
                % 選出四個極值點
                [~, tl_inner_idx] = min(sum_coords);
                [~, br_inner_idx] = max(sum_coords);
                [~, bl_inner_idx] = min(diff_coords);
                [~, tr_inner_idx] = max(diff_coords);
                
                % 獲取内部的四個極值點
                tl_inner = points(tl_inner_idx, :);
                tr_inner = points(tr_inner_idx, :);
                bl_inner = points(bl_inner_idx, :);
                br_inner = points(br_inner_idx, :);
                
                % 在可視化圖像上標記這四個内部點
                vis_img = insertMarker(vis_img, [tl_inner; tr_inner; bl_inner; br_inner], 'x', 'Color', 'blue', 'Size', 10);
                
                % 計算單元格大小（假設棋盤格是均勻的）
                % 可以使用檢測到的點的平均間距
                cell_width = 0;
                cell_height = 0;
                count = 0;
                
                % 計算水平和垂直方向的平均間距
                for i = 1:size(points, 1)
                    for j = i+1:size(points, 1)
                        dx = abs(points(i,1) - points(j,1));
                        dy = abs(points(i,2) - points(j,2));
                        
                        if dx < 50 && dy < 50 && dx > 5 && dy > 5  % 排除距離太遠或太近的點
                            if dx > dy  % 水平相鄰點
                                cell_width = cell_width + dx;
                                count = count + 1;
                            elseif dy > dx  % 垂直相鄰點
                                cell_height = cell_height + dy;
                                count = count + 1;
                            end
                        end
                    end
                end
                
                if count > 0
                    cell_width = cell_width / count;
                    cell_height = cell_height / count;
                else
                    % 若無法計算間距，使用一個估計值
                    cell_width = min(size(gray_img, 2), size(gray_img, 1)) / 10;
                    cell_height = cell_width;
                end
                
                % 估計外部角點位置（向外擴展一個單元格）
                tl = tl_inner - [cell_width, cell_height];
                tr = tr_inner - [-cell_width, cell_height];
                bl = bl_inner - [cell_width, -cell_height];
                br = br_inner - [-cell_width, -cell_height];
                
                % 限制在圖像範圍内
                tl = max(tl, [1, 1]);
                tl = min(tl, [size(gray_img, 2), size(gray_img, 1)]);
                tr = max(tr, [1, 1]);
                tr = min(tr, [size(gray_img, 2), size(gray_img, 1)]);
                bl = max(bl, [1, 1]);
                bl = min(bl, [size(gray_img, 2), size(gray_img, 1)]);
                br = max(br, [1, 1]);
                br = min(br, [size(gray_img, 2), size(gray_img, 1)]);
                
                % 在可視化圖像上繪製估計的外部角點
                vis_img = insertMarker(vis_img, [tl; tr; bl; br], '+', 'Color', 'red', 'Size', 10);
                
                % 返回按左上、右上、左下、右下順序的角點
                corners = double([tl; tr; bl; br]);
                return;
            end
        end
    catch
        % 如果棋盤格檢測失敗，繼續使用其他方法
    end
    
    % 方法2: 使用霍夫變換和角點檢測的組合方法
    % 增強對比度
    gray_img_enhanced = imadjust(gray_img);
    
    % 邊緣檢測
    edges = edge(gray_img_enhanced, 'Canny', [0.1 0.2]);
    
    % 將邊緣疊加到可視化圖像
    edge_vis = vis_img;
    for c = 1:3
        channel = edge_vis(:,:,c);
        channel(edges) = 1;
        edge_vis(:,:,c) = channel;
    end
    vis_img = edge_vis;
    
    % 使用霍夫變換檢測直線
    [H, theta, rho] = hough(edges);
    peaks = houghpeaks(H, 20, 'Threshold', 0.3*max(H(:)));
    lines = houghlines(edges, theta, rho, peaks, 'FillGap', 20, 'MinLength', 30);
    
    % 在可視化圖像上繪製檢測到的線
    for i = 1:length(lines)
        line = lines(i);
        vis_img = insertShape(vis_img, 'Line', [line.point1, line.point2], 'Color', 'blue', 'LineWidth', 2);
    end
    
    % 尋找線的交點
    intersections = [];
    for i = 1:length(lines)
        for j = i+1:length(lines)
            line1 = lines(i);
            line2 = lines(j);
            
            % 檢查兩條線是否近似垂直
            angle_diff = abs(line1.theta - line2.theta);
            if (abs(angle_diff - 90) < 20) || (abs(angle_diff - 270) < 20)
                % 計算交點
                p1 = line1.point1;
                p2 = line1.point2;
                p3 = line2.point1;
                p4 = line2.point2;
                
                % 線1: y = m1*x + b1
                if p2(1) ~= p1(1)
                    m1 = (p2(2) - p1(2)) / (p2(1) - p1(1));
                    b1 = p1(2) - m1 * p1(1);
                else
                    % 垂直線
                    m1 = Inf;
                    b1 = p1(1);
                end
                
                % 線2: y = m2*x + b2
                if p4(1) ~= p3(1)
                    m2 = (p4(2) - p3(2)) / (p4(1) - p3(1));
                    b2 = p3(2) - m2 * p3(1);
                else
                    % 垂直線
                    m2 = Inf;
                    b2 = p3(1);
                end
                
                % 計算交點
                if m1 == Inf && m2 ~= Inf
                    % 線1是垂直線
                    x = b1;
                    y = m2 * x + b2;
                elseif m1 ~= Inf && m2 == Inf
                    % 線2是垂直線
                    x = b2;
                    y = m1 * x + b1;
                elseif m1 ~= Inf && m2 ~= Inf
                    % 兩條線都不是垂直線
                    x = (b2 - b1) / (m1 - m2);
                    y = m1 * x + b1;
                else
                    % 兩條線都是垂直線，不會相交
                    continue;
                end
                
                % 檢查交點是否在圖像範圍内
                if x > 0 && x <= size(gray_img, 2) && y > 0 && y <= size(gray_img, 1)
                    intersections = [intersections; x, y];
                end
            end
        end
    end
    
    % 在可視化圖像上繪製交點
    if ~isempty(intersections)
        for i = 1:size(intersections, 1)
            vis_img = insertMarker(vis_img, intersections(i,:), 'x', 'Color', 'magenta', 'Size', 8);
        end
    end
    
    % 如果找到足夠的交點
    if size(intersections, 1) >= 4
        % 合併相近的交點
        merged_intersections = [];
        remaining_intersections = intersections;
        
        while size(remaining_intersections, 1) > 0
            % 取出第一個點
            pt = remaining_intersections(1,:);
            remaining_intersections(1,:) = [];
            
            % 查找與當前點相近的點
            if size(remaining_intersections, 1) > 0
                dists = sqrt(sum((remaining_intersections - repmat(pt, size(remaining_intersections, 1), 1)).^2, 2));
                near_pts_idx = dists < 20;
                
                % 如果有相近的點，計算平均值
                if any(near_pts_idx)
                    near_pts = remaining_intersections(near_pts_idx, :);
                    avg_pt = mean([pt; near_pts], 1);
                    
                    % 刪除已合併的點
                    remaining_intersections(near_pts_idx, :) = [];
                    
                    merged_intersections = [merged_intersections; avg_pt];
                else
                    % 沒有相近的點，保留原點
                    merged_intersections = [merged_intersections; pt];
                end
            else
                % 沒有更多點需要比較
                merged_intersections = [merged_intersections; pt];
            end
        end
        
        intersections = merged_intersections;
        
        % 在可視化圖像上繪製合併後的交點
        if ~isempty(intersections)
            for i = 1:size(intersections, 1)
                vis_img = insertMarker(vis_img, intersections(i,:), 's', 'Color', 'yellow', 'Size', 8);
            end
        end
    end
    
    % 方法3: 如果霍夫方法沒有找到足夠的交點，使用Harris角點檢測作為補充
    if size(intersections, 1) < 4
        % 使用Harris角點檢測
        corners_obj = detectHarrisFeatures(gray_img, 'MinQuality', 0.01);
        
        % 確保corners_obj不為空
        if ~isempty(corners_obj.Location)
            corner_pts = corners_obj.selectStrongest(30).Location;
            
            % 在可視化圖像上繪製角點
            for i = 1:size(corner_pts, 1)
                vis_img = insertMarker(vis_img, corner_pts(i,:), '*', 'Color', 'cyan', 'Size', 8);
            end
            
            % 合併所有可能的角點
            all_pts = [intersections; corner_pts];
        else
            % 如果沒有檢測到Harris角點，只使用已有的交點
            all_pts = intersections;
            
            % 如果交點太少，添加四個圖像角點作為備選
            if size(all_pts, 1) < 4
                img_corners = [
                    1, 1;                               % 左上
                    size(gray_img, 2), 1;              % 右上
                    1, size(gray_img, 1);              % 左下
                    size(gray_img, 2), size(gray_img, 1) % 右下
                ];
                all_pts = [all_pts; img_corners];
            end
        end
    else
        all_pts = intersections;
    end
    
    % 從所有點中選擇四個角點
    % 計算每個點的 x+y 和 x-y 值
    sum_coords = all_pts(:,1) + all_pts(:,2);
    diff_coords = all_pts(:,1) - all_pts(:,2);
    
    % 找出四個極值點
    [~, tl_idx] = min(sum_coords);  % 左上 = 最小 x+y
    [~, br_idx] = max(sum_coords);  % 右下 = 最大 x+y
    [~, bl_idx] = min(diff_coords); % 左下 = 最小 x-y
    [~, tr_idx] = max(diff_coords); % 右上 = 最大 x-y
    
    % 提取四個角點
    tl = all_pts(tl_idx, :);
    tr = all_pts(tr_idx, :);
    bl = all_pts(bl_idx, :);
    br = all_pts(br_idx, :);
    
    % 在可視化圖像上繪製最終選擇的角點
    vis_img = insertMarker(vis_img, [tl; tr; bl; br], '+', 'Color', 'red', 'Size', 10);
    vis_img = insertText(vis_img, tl+[10, 0], '1', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    vis_img = insertText(vis_img, tr+[10, 0], '2', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    vis_img = insertText(vis_img, bl+[10, 0], '3', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    vis_img = insertText(vis_img, br+[10, 0], '4', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    
    % 返回按左上、右上、左下、右下順序的角點
    corners = double([tl; tr; bl; br]);
end

% 輔助函數: 基於四個角點生成網格
function grid_points = generate_grid_from_corners(corners, rows, cols)
    % 獲取四個角點
    tl = corners(1,:);
    tr = corners(2,:);
    bl = corners(3,:);
    br = corners(4,:);
    
    % 初始化網格點
    grid_points = zeros((rows+1) * (cols+1), 2);
    
    % 生成網格點
    for r = 0:rows
        for c = 0:cols
            % 計算網格中的相對位置
            u = c / cols;
            v = r / rows;
            
            % 雙線性插值計算實際位置
            top = tl * (1-u) + tr * u;
            bottom = bl * (1-u) + br * u;
            point = top * (1-v) + bottom * v;
            
            % 存儲點坐標
            idx = r * (cols+1) + c + 1;
            grid_points(idx, :) = point;
        end
    end
end