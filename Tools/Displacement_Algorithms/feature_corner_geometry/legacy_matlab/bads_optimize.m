%% BADS优化脚本 - 使用像素精度MSE版本
% 创建此文件作为独立脚本使用

% 声明全局变量
global captured groundtruth tform outputView;
global gt_gray valid_mask_var bg_color;
global best_mse best_tform found_better h_waitbar;

% 计算初始MSE作为参考
disp('开始使用BADS进行精细MSE优化...');
outputView = imref2d(size(groundtruth));
initial_corrected = imwarp(captured, tform, 'OutputView', outputView);

if size(groundtruth, 3) == 3
    gt_gray = double(rgb2gray(groundtruth));
    initial_gray = double(rgb2gray(initial_corrected));
else
    gt_gray = double(groundtruth);
    initial_gray = double(initial_corrected);
end

% 创建有效区域掩码
valid_mask_var = initial_gray > 0;
initial_mse = mean((gt_gray(valid_mask_var) - initial_gray(valid_mask_var)).^2);
disp(['初始MSE: ', num2str(initial_mse)]);

% 初始化全局最佳值变量
global_best_mse = initial_mse;
global_best_tform = tform;
global_best_params = [0, 0, 0, 1];
any_improvement = false;

% 创建进度显示框
h_waitbar = waitbar(0, '正在使用BADS进行优化...', 'Name', 'BADS优化进度');

% 创建可视化窗口
figure(99);
subplot(1,3,1); imshow(groundtruth); title('Ground Truth');
subplot(1,3,2); imshow(captured); title('待校正图像');
subplot(1,3,3); imshow(initial_corrected); 
title(['初始校正 (MSE: ', num2str(initial_mse), ')']);
drawnow;

%% 第一阶段：多起点粗略优化
disp('===== 第一阶段：多起点粗略优化 =====');

% 设置搜索范围
lb_coarse = [-8, -8, -5, 0.95];    % 粗略阶段下界
ub_coarse = [8, 8, 5, 1.05];      % 粗略阶段上界

% 定义多个起点
start_points = [
    0, 0, 0, 1;       % 原点
    -1, -1, 0, 0.99;  % 左上+缩小
    1, -1, 0, 0.99;   % 右上+缩小
    -1, 1, 0, 0.99;   % 左下+缩小
    1, 1, 0, 0.99;    % 右下+缩小
    0, 0, 0.5, 1.01;  % 正旋转+放大
    0, 0, -0.5, 1.01; % 负旋转+放大
    0.5, 0.5, 0.25, 1.005; % 附加起点
    -0.5, 0.5, -0.25, 0.995; % 附加起点
];

% 粗略阶段BADS选项
options_coarse = bads('defaults');
options_coarse.Display = 'iter';
options_coarse.UncertaintyHandling = true;
options_coarse.MaxIter = 40;       % 增加迭代次数
options_coarse.MaxFunEvals = 150;  % 增加评估次数
options_coarse.TolMesh = 1e-3;

try
    for i = 1:size(start_points, 1)
        % 更新进度条
        waitbar((i-1)/size(start_points, 1), h_waitbar, ...
                sprintf('第一阶段: 起点 %d/%d 粗略优化中', i, size(start_points, 1)));
        
        disp(['尝试起点 ', num2str(i), '/', num2str(size(start_points, 1)), ...
              ': [', num2str(start_points(i,:)), ']']);
        
        % 重置当前优化的最佳值
        best_mse = initial_mse;
        best_tform = tform;
        found_better = false;
        
        % 执行BADS优化
        [optimized_params, ~] = bads(@objective_func, start_points(i,:), ...
                                    lb_coarse, ub_coarse, [], [], [], options_coarse);
        
        % 更新全局最佳结果
        if best_mse < global_best_mse
            global_best_mse = best_mse;
            global_best_tform = best_tform;
            global_best_params = optimized_params;
            any_improvement = true;
            disp(['更新全局最佳结果: MSE = ', num2str(global_best_mse), ...
                  ', 参数 = [', num2str(global_best_params), ']']);
        end
    end
    
    %% 第二阶段：基于最佳结果的精细优化
    disp('===== 第二阶段：精细优化 =====');
    waitbar(0.7, h_waitbar, '第二阶段: 精细优化中...');
    
    % 设置精细优化范围 - 围绕最佳点的小范围
    lb_fine = global_best_params - [0.05, 0.05, 0.05, 0.001];
    ub_fine = global_best_params + [0.05, 0.05, 0.05, 0.001];
    
    % 保证边界合理
    lb_fine = max(lb_fine, [-8, -8, -5, 0.95]);
    ub_fine = min(ub_fine, [8, 8, 5, 1.05]);
    
    % 精细阶段BADS选项
    options_fine = bads('defaults');
    options_fine.Display = 'iter';
    options_fine.UncertaintyHandling = true;
    options_fine.MaxIter = 150;         % 增加迭代次数
    options_fine.MaxFunEvals = 600;     % 增加评估次数
    options_fine.TolMesh = 1e-6;
    options_fine.TolFun = 1e-6;
    options_fine.NoiseFinalSamples = 15; % 增加最终评估样本次数
    
    % 重置当前优化的最佳值，以便更好地追踪精细阶段的改进
    best_mse = global_best_mse;
    best_tform = global_best_tform;
    found_better = false;
    
    % 执行精细BADS优化
    [final_params, ~] = bads(@objective_func, global_best_params, ...
                            lb_fine, ub_fine, [], [], [], options_fine);
    
    % 更新全局最佳结果
    if best_mse < global_best_mse
        global_best_mse = best_mse;
        global_best_tform = best_tform;
        global_best_params = final_params;
        any_improvement = true;  % 重要：更新全局改进标志
        disp(['精细优化更新全局最佳结果: MSE = ', num2str(global_best_mse), ...
              ', 参数 = [', num2str(global_best_params), ']']);
    end
    
    %% 第三阶段：极精细优化
    disp('===== 第三阶段：极精细优化 =====');
    waitbar(0.9, h_waitbar, '第三阶段: 极精细优化中...');
    
    % 设置极精细优化范围 - 进一步缩小范围
    lb_ultrafine = global_best_params - [0.1, 0.1, 0.05, 0.001];
    ub_ultrafine = global_best_params + [0.1, 0.1, 0.05, 0.001];
    
    % 保证边界合理
    lb_ultrafine = max(lb_ultrafine, [-3, -3, -2, 0.98]);
    ub_ultrafine = min(ub_ultrafine, [3, 3, 2, 1.02]);
    
    % 极精细阶段BADS选项
    options_ultrafine = bads('defaults');
    options_ultrafine.Display = 'iter';
    options_ultrafine.UncertaintyHandling = true;
    options_ultrafine.MaxIter = 250;        % 很高的迭代次数
    options_ultrafine.MaxFunEvals = 800;    % 很高的评估次数
    options_ultrafine.TolMesh = 1e-9;       % 更精细的网格容差
    options_ultrafine.TolFun = 1e-9;        % 更精细的函数值容差
    options_ultrafine.NoiseFinalSamples = 30; % 大量最终评估样本
    
    % 重置当前优化的最佳值
    best_mse = global_best_mse;
    best_tform = global_best_tform;
    found_better = false;
    
    % 执行极精细BADS优化
    [final_params_ultra, ~] = bads(@objective_func, global_best_params, ...
                            lb_ultrafine, ub_ultrafine, [], [], [], options_ultrafine);
    
    % 更新全局最佳结果
    if best_mse < global_best_mse
        global_best_mse = best_mse;
        global_best_tform = best_tform;
        global_best_params = final_params_ultra;
        any_improvement = true;  % 重要：更新全局改进标志
        disp(['极精细优化更新全局最佳结果: MSE = ', num2str(global_best_mse), ...
              ', 参数 = [', num2str(global_best_params), ']']);
    end
    
    % 提取最佳参数
    tx_opt = global_best_params(1);
    ty_opt = global_best_params(2);
    rot_opt = global_best_params(3);
    scale_opt = global_best_params(4);
    
    disp(['BADS优化完成，最佳参数: tx=', num2str(tx_opt), ...
          ', ty=', num2str(ty_opt), ', rot=', num2str(rot_opt), ...
          ', scale=', num2str(scale_opt)]);
    
    % 检查是否找到更好的结果 - 关键修复点
    if any_improvement
        improvement = ((initial_mse - global_best_mse) / initial_mse) * 100;
        disp(['BADS精细优化成功! MSE从 ', num2str(initial_mse), ...
              ' 降低到 ', num2str(global_best_mse), ...
              ' (改善 ', num2str(improvement), '%)']);
        
        % 应用最佳变换
        optimized_corrected = imwarp(captured, global_best_tform, 'OutputView', outputView);
    else
        disp('BADS精细优化未能改善MSE，保持原始变换结果');
        optimized_corrected = initial_corrected;
        global_best_mse = initial_mse;
    end
    
    % 填充黑色区域
    if size(optimized_corrected, 3) == 3
        black_mask = (optimized_corrected(:,:,1) == 0) & ...
                    (optimized_corrected(:,:,2) == 0) & ...
                    (optimized_corrected(:,:,3) == 0);
    else
        black_mask = (optimized_corrected == 0);
    end
    
    optimized_filled = optimized_corrected;
    if size(optimized_corrected, 3) == 3
        for c = 1:3
            channel = optimized_filled(:,:,c);
            channel(black_mask) = bg_color(c);
            optimized_filled(:,:,c) = channel;
        end
    else
        optimized_filled(black_mask) = bg_color;
    end
    
    % 保存结果
    imwrite(optimized_filled, 'corrected_bads_optimized.png');
    
    % 显示最终结果
    figure('Name', 'BADS最终优化结果');
    subplot(1,3,1); imshow(groundtruth); title('Ground Truth');
    subplot(1,3,2); imshow(initial_corrected); title(['原始校正 (MSE: ', num2str(initial_mse), ')']);
    subplot(1,3,3); imshow(optimized_filled); title(['BADS优化 (MSE: ', num2str(global_best_mse), ')']);
    drawnow;
    
    %% 创建MSE比较视觉化 - 确保使用一致的像素精度MSE计算
    % 无论是否找到更好的结果，都创建比较图
    % 重新计算MSE，确保与优化过程使用相同的方法
    % 重新生成最终校正图像，确保一致性
    final_corrected = imwarp(captured, global_best_tform, 'OutputView', outputView);
    
    % 处理黑色背景
    if size(final_corrected, 3) == 3
        black_mask = (final_corrected(:,:,1) == 0) & ...
                    (final_corrected(:,:,2) == 0) & ...
                    (final_corrected(:,:,3) == 0);
        
        final_filled = final_corrected;
        for c = 1:3
            channel = final_filled(:,:,c);
            channel(black_mask) = bg_color(c);
            final_filled(:,:,c) = channel;
        end
        
        final_gray = double(rgb2gray(final_filled));
        init_gray = double(rgb2gray(initial_corrected));
    else
        black_mask = (final_corrected == 0);
        final_filled = final_corrected;
        final_filled(black_mask) = bg_color;
        
        final_gray = double(final_filled);
        init_gray = double(initial_corrected);
    end
    
    % 使用与优化过程完全相同的方法计算MSE
    % 原始图像有效掩码
    initial_mask = init_gray > 0;
    initial_combined_mask = valid_mask_var & initial_mask;
    init_squared_diff = (gt_gray(initial_combined_mask) - init_gray(initial_combined_mask)).^2;
    mse_original = mean(init_squared_diff);
    
    % 优化后图像有效掩码
    final_mask = final_gray > 0;
    final_combined_mask = valid_mask_var & final_mask;
    final_squared_diff = (gt_gray(final_combined_mask) - final_gray(final_combined_mask)).^2;
    mse_final = mean(final_squared_diff);
    
    % 计算RMSE
    rmse_original = sqrt(mse_original);
    rmse_final = sqrt(mse_final);
    
    % 计算改善百分比
    improvement_percent = ((mse_original - mse_final) / mse_original) * 100;
    
    % 创建差异图像 (热图)
    % 使用相同的色彩映射范围以便比较
    max_diff = max(max(init_squared_diff(:)), max(final_squared_diff(:)));
    
    % 创建完整尺寸的差异图 - 需要处理所有像素
    full_init_squared_diff = zeros(size(gt_gray));
    full_init_squared_diff(initial_combined_mask) = init_squared_diff;
    
    full_final_squared_diff = zeros(size(gt_gray));
    full_final_squared_diff(final_combined_mask) = final_squared_diff;
    
    normalized_diff_original = full_init_squared_diff / max_diff;
    normalized_diff_final = full_final_squared_diff / max_diff;
    
    % 显示MSE比较
    figure('Name', 'BADS最终MSE比较评估', 'Position', [100, 100, 1000, 700]);
    
    % 原始图像
    subplot(2,3,1); 
    imshow(initial_corrected); 
    title('初始校正图像');
    
    % 优化后图像
    subplot(2,3,2); 
    imshow(final_filled); 
    title('BADS优化后图像');
    
    % Ground Truth
    subplot(2,3,3); 
    imshow(groundtruth); 
    title('Ground Truth');
    
    % 原始图像的差异热图
    subplot(2,3,4); 
    imagesc(normalized_diff_original);
    colormap('jet');
    colorbar;
    title(sprintf('校正前 MSE = %.2f, RMSE = %.2f', mse_original, rmse_original));
    axis image;
    
    % 最终优化图像的差异热图
    subplot(2,3,5); 
    imagesc(normalized_diff_final);
    colormap('jet');
    colorbar;
    title(sprintf('BADS校正后 MSE = %.2f, RMSE = %.2f', mse_final, rmse_final));
    axis image;
    
    % 显示改善百分比
    subplot(2,3,6);
    bar([mse_original, mse_final]);
    set(gca, 'XTickLabel', {'校正前', 'BADS校正后'});
    ylabel('MSE值');
    title(sprintf('优化改善了 %.2f%%', improvement_percent));
    grid on;
    
    % 保存MSE比较图
    saveas(gcf, 'bads_mse_comparison.png');
    
    % 在命令窗口显示数值比较
    disp('======= BADS优化MSE比较结果 =======');
    disp(['校正前 MSE = ', num2str(mse_original)]);
    disp(['BADS校正后 MSE = ', num2str(mse_final)]);
    disp(['改善百分比 = ', num2str(improvement_percent), '%']);
    
catch ME
    % 如果BADS出错，显示错误信息
    warning(['BADS优化错误: ', ME.message]);
    disp(ME.stack(1));
    disp('回退到原始变换结果');
    optimized_corrected = initial_corrected;
end

% 关闭进度条
if ishandle(h_waitbar)
    close(h_waitbar);
end

% 最终报告
disp('BADS优化完成!');
if any_improvement
    disp(['最终MSE改善: ', num2str(initial_mse), ' -> ', num2str(global_best_mse), ...
          ' (', num2str(((initial_mse - global_best_mse) / initial_mse) * 100), '%)']);
    disp(['最佳参数: tx=', num2str(global_best_params(1)), ...
          ', ty=', num2str(global_best_params(2)), ...
          ', rot=', num2str(global_best_params(3)), ...
          ', scale=', num2str(global_best_params(4))]);
else
    disp('未找到更好的变换参数，使用原始校正结果');
end