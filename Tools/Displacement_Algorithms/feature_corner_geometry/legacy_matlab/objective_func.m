function mse = objective_func(params)
% OBJECTIVE_FUNC BADS优化的目标函数 - 使用像素精度MSE
% 使用全局变量访问数据

global captured groundtruth tform outputView;
global gt_gray valid_mask_var bg_color;
global best_mse best_tform found_better h_waitbar;

% 使用静态变量记录评估次数
persistent eval_count;
if isempty(eval_count)
    eval_count = 0;
end
eval_count = eval_count + 1;

% 更新进度条
if ishandle(h_waitbar)
    waitbar(min(eval_count/500, 0.99), h_waitbar, ...
            sprintf('BADS优化进度: 已评估 %d 个参数组合', eval_count));
end

% 提取参数
tx = params(1);
ty = params(2);
rot = params(3);
scale = params(4);

% 创建调整矩阵
adjustment = eye(3);

% 应用缩放
scaling_matrix = [scale 0 0; 0 scale 0; 0 0 1];
adjustment = adjustment * scaling_matrix;

% 应用旋转（围绕图像中心）
img_center = [size(groundtruth, 2)/2; size(groundtruth, 1)/2; 1];
rot_rad = rot * pi / 180;
rot_matrix = [cos(rot_rad) -sin(rot_rad) 0; 
              sin(rot_rad) cos(rot_rad) 0; 
              0 0 1];

% 平移到原点，旋转，再平移回来
to_origin = [1 0 -img_center(1); 0 1 -img_center(2); 0 0 1];
from_origin = [1 0 img_center(1); 0 1 img_center(2); 0 0 1];
rotation_around_center = from_origin * rot_matrix * to_origin;
adjustment = adjustment * rotation_around_center;

% 应用平移
translation_matrix = [1 0 tx; 0 1 ty; 0 0 1];
adjustment = adjustment * translation_matrix;

% 将调整应用到当前变换
combined_matrix = adjustment * tform.T;
adjusted_tform = projective2d(combined_matrix);

% 应用变换
adjusted_corrected = imwarp(captured, adjusted_tform, 'OutputView', outputView);

% 计算MSE（仅在有效区域）
if size(adjusted_corrected, 3) == 3
    adjusted_gray = double(rgb2gray(adjusted_corrected));
else
    adjusted_gray = double(adjusted_corrected);
end

% 只比较有内容的区域 - 同时考虑原始和调整后的有效区域
adjusted_mask = adjusted_gray > 0;
combined_mask = valid_mask_var & adjusted_mask;

% 确保有足够的重叠区域 - 更严格的要求
overlap_percentage = sum(combined_mask(:)) / sum(valid_mask_var(:)) * 100;

% 简化的MSE计算 - 仅使用像素精度
if overlap_percentage > 95  % 要求至少95%的重叠
    % 基本MSE计算
    diff_squared = (gt_gray(combined_mask) - adjusted_gray(combined_mask)).^2;
    current_mse = mean(diff_squared);
    
    % 添加轻微的重叠惩罚
    if overlap_percentage < 99
        overlap_penalty = (100 - overlap_percentage) * 0.2;
        current_mse = current_mse * (1 + overlap_penalty/100);
    end
    
    % 返回MSE值
    mse = current_mse;
    
    % 如果找到更好的结果，更新状态并显示
    if current_mse < best_mse
        % 更新全局变量
        best_mse = current_mse;
        best_tform = adjusted_tform;
        found_better = true;
        
        % 显示每次找到更好的结果时的参数
        disp(['找到更好的结果: tx=', num2str(tx), ', ty=', num2str(ty), ...
              ', rot=', num2str(rot), ', scale=', num2str(scale), ...
              ', MSE=', num2str(current_mse), ...
              ', 重叠=', num2str(overlap_percentage), '%']);
        
        % 立即可视化当前最佳结果
        figure(99);
        best_corrected = imwarp(captured, adjusted_tform, 'OutputView', outputView);
        
        % 填充背景
        if size(best_corrected, 3) == 3
            black_mask = (best_corrected(:,:,1) == 0) & ...
                       (best_corrected(:,:,2) == 0) & ...
                       (best_corrected(:,:,3) == 0);
            
            best_filled = best_corrected;
            for c = 1:3
                channel = best_filled(:,:,c);
                channel(black_mask) = bg_color(c);
                best_filled(:,:,c) = channel;
            end
        else
            black_mask = (best_corrected == 0);
            best_filled = best_corrected;
            best_filled(black_mask) = bg_color;
        end
        
        % 更新可视化
        subplot(1,3,1); imshow(groundtruth); title('Ground Truth');
        subplot(1,3,2); imshow(captured); title('待校正图像');
        subplot(1,3,3); imshow(best_filled); 
        title(['优化中 (MSE: ', num2str(current_mse), ')']);
        drawnow;
    end
else
    % 重叠不足，使用惩罚值 - 根据重叠程度调整惩罚
    if overlap_percentage > 80
        % 80-95%重叠给予渐进惩罚
        overlap_factor = (95 - overlap_percentage) / 15; % 0-1之间的因子
        mse = 10000 * overlap_factor + 2000;
    else
        % 低于80%重叠给予极高惩罚
        mse = 10000;
    end
end
end