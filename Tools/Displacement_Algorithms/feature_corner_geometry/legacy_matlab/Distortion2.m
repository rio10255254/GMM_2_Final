%% 棋盤格直角檢測與精確對應 - 含背景填充與MSE評估
% clear all;
close all;
clc;

%% 步驟1: 加載圖像
groundtruth = imread("D:\NonSystemFiles\GMM2\GT.bmp");
captured = imread("D:\NonSystemFiles\GMM2\0416_crop\0416_crop\2.bmp");

% 轉換為灰度圖
if size(groundtruth, 3) == 3
    groundtruth_gray = rgb2gray(groundtruth);
else
    groundtruth_gray = groundtruth;
end

if size(captured, 3) == 3
    captured_gray = rgb2gray(captured);
else
    captured_gray = captured;
end

% 顯示原始圖像
figure('Name', '原始圖像');
subplot(1,2,1); imshow(groundtruth); title('Ground Truth');
subplot(1,2,2); imshow(captured); title('待校正圖像');

%% 步驟2: 二值化處理 - 突出棋盤格結構
% 使用自適應閾值進行二值化，更好地保留棋盤格結構
gt_binary = imbinarize(groundtruth_gray, 'adaptive', 'Sensitivity', 0.5);
cap_binary = imbinarize(captured_gray, 'adaptive', 'Sensitivity', 0.5);

% 顯示二值化結果
figure('Name', '二值化處理');
subplot(1,2,1); imshow(gt_binary); title('Ground Truth 二值化');
subplot(1,2,2); imshow(cap_binary); title('待校正圖像二值化');

%% 自动检测棋盘格大正方形的四个角点函数
% 替换原始代码中的步骤3和步骤4，自动检测棋盘格大正方形的四个角点

%% 步骤3: 自动检测棋盘格大正方形的四个角点
disp('自动检测棋盘格大正方形的四个角点...');

% 自动检测角点
[gt_corners, gt_vis] = detect_outer_corners(groundtruth_gray, groundtruth);
[cap_corners, cap_vis] = detect_outer_corners(captured_gray, captured);

% 显示检测过程和结果
figure('Name', '角点检测过程和结果'); 
subplot(2,2,1); imshow(gt_vis); title('Ground Truth 检测过程');
subplot(2,2,2); imshow(cap_vis); title('待校正图像检测过程');

subplot(2,2,3); 
imshow(groundtruth);
hold on;
plot(gt_corners(:,1), gt_corners(:,2), 'ro', 'MarkerSize', 10, 'LineWidth', 2);
for i = 1:4
    text(gt_corners(i,1)+10, gt_corners(i,2), num2str(i), 'Color', 'yellow', 'FontSize', 12);
end
title('Ground Truth 最终角点');

subplot(2,2,4); 
imshow(captured);
hold on;
plot(cap_corners(:,1), cap_corners(:,2), 'ro', 'MarkerSize', 10, 'LineWidth', 2);
for i = 1:4
    text(cap_corners(i,1)+10, cap_corners(i,2), num2str(i), 'Color', 'yellow', 'FontSize', 12);
end
title('待校正图像最终角点');

%% 步骤4: 在四个角落点之间建立网格
% 定义棋盘格网格大小 (内角点的行数和列数)
rows = 5; 
cols = 5;

% 基于四个角落点生成完整网格点
gt_points = generate_grid_from_corners(gt_corners, rows, cols);
cap_points = generate_grid_from_corners(cap_corners, rows, cols);

% 显示网格点
figure('Name', '基于四角生成的网格点');
subplot(1,2,1);
imshow(groundtruth);
hold on;
plot(gt_points(:,1), gt_points(:,2), 'ro', 'MarkerSize', 8);
for i = 1:size(gt_points, 1)
    text(gt_points(i,1)+5, gt_points(i,2), num2str(i), 'Color', 'yellow', 'FontSize', 10);
end
title('Ground Truth 网格点');

subplot(1,2,2);
imshow(captured);
hold on;
plot(cap_points(:,1), cap_points(:,2), 'ro', 'MarkerSize', 8);
for i = 1:size(cap_points, 1)
    text(cap_points(i,1)+5, cap_points(i,2), num2str(i), 'Color', 'yellow', 'FontSize', 10);
end
title('待校正图像网格点');

% 辅助函数: 检测图像中大正方形的外部角点
function [corners, vis_img] = detect_outer_corners(gray_img, color_img)
    % 创建可视化图像
    if size(color_img, 3) == 3
        vis_img = color_img;
    else
        vis_img = repmat(mat2gray(gray_img), [1, 1, 3]);
    end
    
    % 方法1: 尝试使用棋盘格检测函数
    try
        [points, boardSize] = detectCheckerboardPoints(gray_img);
        
        if ~isempty(points) && ~isempty(boardSize)
            % 在可视化图像上绘制检测到的点
            vis_img = insertMarker(vis_img, points, 'o', 'Color', 'green', 'Size', 5);
            
            % 如果检测到的是内部点，扩展到外部角点
            if any(boardSize > 1)  % 确保至少检测到了一个完整的棋盘格
                % 寻找四个极值点（最左上、最右上、最左下、最右下）
                % 计算每个点的 x+y 和 x-y 值
                sum_coords = points(:,1) + points(:,2);
                diff_coords = points(:,1) - points(:,2);
                
                % 选出四个极值点
                [~, tl_inner_idx] = min(sum_coords);
                [~, br_inner_idx] = max(sum_coords);
                [~, bl_inner_idx] = min(diff_coords);
                [~, tr_inner_idx] = max(diff_coords);
                
                % 获取内部的四个极值点
                tl_inner = points(tl_inner_idx, :);
                tr_inner = points(tr_inner_idx, :);
                bl_inner = points(bl_inner_idx, :);
                br_inner = points(br_inner_idx, :);
                
                % 在可视化图像上标记这四个内部点
                vis_img = insertMarker(vis_img, [tl_inner; tr_inner; bl_inner; br_inner], 'x', 'Color', 'blue', 'Size', 10);
                
                % 计算单元格大小（假设棋盘格是均匀的）
                % 可以使用检测到的点的平均间距
                cell_width = 0;
                cell_height = 0;
                count = 0;
                
                % 计算水平和垂直方向的平均间距
                for i = 1:size(points, 1)
                    for j = i+1:size(points, 1)
                        dx = abs(points(i,1) - points(j,1));
                        dy = abs(points(i,2) - points(j,2));
                        
                        if dx < 50 && dy < 50 && dx > 5 && dy > 5  % 排除距离太远或太近的点
                            if dx > dy  % 水平相邻点
                                cell_width = cell_width + dx;
                                count = count + 1;
                            elseif dy > dx  % 垂直相邻点
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
                    % 若无法计算间距，使用一个估计值
                    cell_width = min(size(gray_img, 2), size(gray_img, 1)) / 10;
                    cell_height = cell_width;
                end
                
                % 估计外部角点位置（向外扩展一个单元格）
                tl = tl_inner - [cell_width, cell_height];
                tr = tr_inner - [-cell_width, cell_height];
                bl = bl_inner - [cell_width, -cell_height];
                br = br_inner - [-cell_width, -cell_height];
                
                % 限制在图像范围内
                tl = max(tl, [1, 1]);
                tl = min(tl, [size(gray_img, 2), size(gray_img, 1)]);
                tr = max(tr, [1, 1]);
                tr = min(tr, [size(gray_img, 2), size(gray_img, 1)]);
                bl = max(bl, [1, 1]);
                bl = min(bl, [size(gray_img, 2), size(gray_img, 1)]);
                br = max(br, [1, 1]);
                br = min(br, [size(gray_img, 2), size(gray_img, 1)]);
                
                % 在可视化图像上绘制估计的外部角点
                vis_img = insertMarker(vis_img, [tl; tr; bl; br], '+', 'Color', 'red', 'Size', 10);
                
                % 返回按左上、右上、左下、右下顺序的角点
                corners = [tl; tr; bl; br];
                return;
            end
        end
    catch
        % 如果棋盘格检测失败，继续使用其他方法
    end
    
    % 方法2: 使用霍夫变换和角点检测的组合方法
    % 增强对比度
    gray_img_enhanced = imadjust(gray_img);
    
    % 边缘检测
    edges = edge(gray_img_enhanced, 'Canny', [0.1 0.2]);
    
    % 将边缘叠加到可视化图像
    edge_vis = vis_img;
    for c = 1:3
        channel = edge_vis(:,:,c);
        channel(edges) = 1;
        edge_vis(:,:,c) = channel;
    end
    vis_img = edge_vis;
    
    % 使用霍夫变换检测直线
    [H, theta, rho] = hough(edges);
    peaks = houghpeaks(H, 20, 'Threshold', 0.3*max(H(:)));
    lines = houghlines(edges, theta, rho, peaks, 'FillGap', 20, 'MinLength', 30);
    
    % 在可视化图像上绘制检测到的线
    for i = 1:length(lines)
        line = lines(i);
        vis_img = insertShape(vis_img, 'Line', [line.point1, line.point2], 'Color', 'blue', 'LineWidth', 2);
    end
    
    % 寻找线的交点
    intersections = [];
    for i = 1:length(lines)
        for j = i+1:length(lines)
            line1 = lines(i);
            line2 = lines(j);
            
            % 检查两条线是否近似垂直
            angle_diff = abs(line1.theta - line2.theta);
            if (abs(angle_diff - 90) < 20) || (abs(angle_diff - 270) < 20)
                % 计算交点
                p1 = line1.point1;
                p2 = line1.point2;
                p3 = line2.point1;
                p4 = line2.point2;
                
                % 线1: y = m1*x + b1
                if p2(1) ~= p1(1)
                    m1 = (p2(2) - p1(2)) / (p2(1) - p1(1));
                    b1 = p1(2) - m1 * p1(1);
                else
                    % 垂直线
                    m1 = Inf;
                    b1 = p1(1);
                end
                
                % 线2: y = m2*x + b2
                if p4(1) ~= p3(1)
                    m2 = (p4(2) - p3(2)) / (p4(1) - p3(1));
                    b2 = p3(2) - m2 * p3(1);
                else
                    % 垂直线
                    m2 = Inf;
                    b2 = p3(1);
                end
                
                % 计算交点
                if m1 == Inf && m2 ~= Inf
                    % 线1是垂直线
                    x = b1;
                    y = m2 * x + b2;
                elseif m1 ~= Inf && m2 == Inf
                    % 线2是垂直线
                    x = b2;
                    y = m1 * x + b1;
                elseif m1 ~= Inf && m2 ~= Inf
                    % 两条线都不是垂直线
                    x = (b2 - b1) / (m1 - m2);
                    y = m1 * x + b1;
                else
                    % 两条线都是垂直线，不会相交
                    continue;
                end
                
                % 检查交点是否在图像范围内
                if x > 0 && x <= size(gray_img, 2) && y > 0 && y <= size(gray_img, 1)
                    intersections = [intersections; x, y];
                end
            end
        end
    end
    
    % 在可视化图像上绘制交点
    for i = 1:size(intersections, 1)
        vis_img = insertMarker(vis_img, intersections(i,:), 'x', 'Color', 'magenta', 'Size', 8);
    end
    
    % 如果找到足够的交点
    if size(intersections, 1) >= 4
        % 合并相近的交点
        merged_intersections = [];
        while ~isempty(intersections)
            pt = intersections(1,:);
            intersections(1,:) = [];
            
            % 查找与当前点相近的点
            dists = sqrt(sum((intersections - pt).^2, 2));
            near_pts_idx = dists < 20;
            
            % 如果有相近的点，计算平均值
            if any(near_pts_idx)
                near_pts = intersections(near_pts_idx, :);
                avg_pt = mean([pt; near_pts], 1);
                
                % 删除已合并的点
                intersections(near_pts_idx, :) = [];
                
                merged_intersections = [merged_intersections; avg_pt];
            else
                % 没有相近的点，保留原点
                merged_intersections = [merged_intersections; pt];
            end
        end
        
        intersections = merged_intersections;
        
        % 在可视化图像上绘制合并后的交点
        for i = 1:size(intersections, 1)
            vis_img = insertMarker(vis_img, intersections(i,:), 's', 'Color', 'yellow', 'Size', 8);
        end
    end
    
    % 方法3: 如果霍夫方法没有找到足够的交点，使用Harris角点检测作为补充
    if size(intersections, 1) < 4
        % 使用Harris角点检测
        corners_obj = detectHarrisFeatures(gray_img, 'MinQuality', 0.01);
        
        % 确保corners_obj不为空
        if ~isempty(corners_obj.Location)
            corner_pts = corners_obj.selectStrongest(30).Location;
            
            % 在可视化图像上绘制角点
            for i = 1:size(corner_pts, 1)
                vis_img = insertMarker(vis_img, corner_pts(i,:), '*', 'Color', 'cyan', 'Size', 8);
            end
            
            % 合并所有可能的角点
            all_pts = [intersections; corner_pts];
        else
            % 如果没有检测到Harris角点，只使用已有的交点
            all_pts = intersections;
            
            % 如果交点太少，添加四个图像角点作为备选
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
    
    % 从所有点中选择四个角点
    % 计算每个点的 x+y 和 x-y 值
    sum_coords = all_pts(:,1) + all_pts(:,2);
    diff_coords = all_pts(:,1) - all_pts(:,2);
    
    % 找出四个极值点
    [~, tl_idx] = min(sum_coords);  % 左上 = 最小 x+y
    [~, br_idx] = max(sum_coords);  % 右下 = 最大 x+y
    [~, bl_idx] = min(diff_coords); % 左下 = 最小 x-y
    [~, tr_idx] = max(diff_coords); % 右上 = 最大 x-y
    
    % 提取四个角点
    tl = all_pts(tl_idx, :);
    tr = all_pts(tr_idx, :);
    bl = all_pts(bl_idx, :);
    br = all_pts(br_idx, :);
    
    % 在可视化图像上绘制最终选择的角点
    vis_img = insertMarker(vis_img, [tl; tr; bl; br], '+', 'Color', 'red', 'Size', 10);
    vis_img = insertText(vis_img, tl+[10, 0], '1', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    vis_img = insertText(vis_img, tr+[10, 0], '2', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    vis_img = insertText(vis_img, bl+[10, 0], '3', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    vis_img = insertText(vis_img, br+[10, 0], '4', 'FontSize', 12, 'TextColor', 'yellow', 'BoxOpacity', 0);
    
    % 返回按左上、右上、左下、右下顺序的角点
    corners = [tl; tr; bl; br];
end



%% 步驟5: 精細調整網格點位置到實際直角
% 使用局部搜索來調整網格點，使其落在實際的直角處
gt_refined = refine_corner_positions(groundtruth_gray, gt_points, 15);
cap_refined = refine_corner_positions(captured_gray, cap_points, 15);

% 顯示精細調整後的角點
figure('Name', '精細調整後的角點');
subplot(1,2,1);
imshow(groundtruth);
hold on;
plot(gt_refined(:,1), gt_refined(:,2), 'ro', 'MarkerSize', 8);
for i = 1:size(gt_refined, 1)
    text(gt_refined(i,1)+5, gt_refined(i,2), num2str(i), 'Color', 'yellow', 'FontSize', 10);
end
title('Ground Truth 精細角點');

subplot(1,2,2);
imshow(captured);
hold on;
plot(cap_refined(:,1), cap_refined(:,2), 'ro', 'MarkerSize', 8);
for i = 1:size(cap_refined, 1)
    text(cap_refined(i,1)+5, cap_refined(i,2), num2str(i), 'Color', 'yellow', 'FontSize', 10);
end
title('待校正圖像精細角點');

%% 步驟6: 計算並應用變換
tform = fitgeotrans(cap_refined, gt_refined, 'projective');

% 應用變換
outputView = imref2d(size(groundtruth));
corrected = imwarp(captured, tform, 'OutputView', outputView);

%% 步驟7: 背景填充 - 填充黑色區域
% 識別背景顏色 - 假設GT圖像角落的顏色是背景色
% 使用四個角落的平均值作為背景色
corner_size = 10;
TL_color = mean(mean(groundtruth(1:corner_size, 1:corner_size, :)));
TR_color = mean(mean(groundtruth(1:corner_size, end-corner_size:end, :)));
BL_color = mean(mean(groundtruth(end-corner_size:end, 1:corner_size, :)));
BR_color = mean(mean(groundtruth(end-corner_size:end, end-corner_size:end, :)));
bg_color = round(mean([TL_color; TR_color; BL_color; BR_color]));

% 創建黑色區域掩碼
if size(corrected, 3) == 3
    black_mask = (corrected(:,:,1) == 0) & (corrected(:,:,2) == 0) & (corrected(:,:,3) == 0);
else
    black_mask = (corrected == 0);
end

% 填充黑色區域
filled_corrected = corrected;
if size(corrected, 3) == 3
    for c = 1:3
        channel = filled_corrected(:,:,c);
        channel(black_mask) = bg_color(c);
        filled_corrected(:,:,c) = channel;
    end
else
    filled_corrected(black_mask) = bg_color;
end


%%

% 執行BADS優化
bads_optimize;


%%
% %% 修正版精細MSE優化
% disp('開始進行受限制的精細MSE優化...');
% 
% % 使用當前的校正結果作為基準
% best_tform = tform;
% best_mse = Inf;
% 
% % 設置更小的搜索範圍
% translations = -5:1:5;  % 平移範圍減小
% rotations = -5:0.5:5;   % 旋轉範圍減小
% scales = 0.9:0.05:1.1;  % 縮放範圍減小
% 
% % 初始化列表記錄每次調整的MSE和參數
% results = [];
% 
% % 計算初始MSE
% outputView = imref2d(size(groundtruth));
% initial_corrected = imwarp(captured, tform, 'OutputView', outputView);
% 
% if size(groundtruth, 3) == 3
%     gt_gray = double(rgb2gray(groundtruth));
%     initial_gray = double(rgb2gray(initial_corrected));
% else
%     gt_gray = double(groundtruth);
%     initial_gray = double(initial_corrected);
% end
% 
% % 創建有效區域掩碼 - 只在非黑色區域計算MSE
% valid_mask = initial_gray > 0;
% initial_mse = mean((gt_gray(valid_mask) - initial_gray(valid_mask)).^2);
% disp(['初始MSE: ', num2str(initial_mse)]);
% 
% % 初始化結果記錄和計數器
% results = [];
% count = 0;
% 
% % 創建進度條
% h_waitbar = waitbar(0, '正在搜索最佳變換參數...', 'Name', '精細優化進度');
% total_combinations = length(translations)^2 * length(rotations) * length(scales);
% 
% % 網格搜索 - 嘗試各種小調整組合
% for tx = translations
%     for ty = translations
%         for rot = rotations
%             for scale = scales
%                 % 更新計數器
%                 count = count + 1;
% 
%                 % 更新進度條 (每10次迭代更新一次)
%                 if mod(count, 10) == 0
%                     waitbar(count/total_combinations, h_waitbar, ...
%                         sprintf('進度: %.1f%% (%d/%d)', count/total_combinations*100, count, total_combinations));
%                 end
% 
%                 % 創建調整矩陣
%                 adjustment = eye(3);
% 
%                 % 應用縮放
%                 scaling_matrix = [scale 0 0; 0 scale 0; 0 0 1];
%                 adjustment = adjustment * scaling_matrix;
% 
%                 % 應用旋轉（圍繞圖像中心）
%                 img_center = [size(groundtruth, 2)/2; size(groundtruth, 1)/2; 1];
%                 rot_rad = rot * pi / 180;
%                 rot_matrix = [cos(rot_rad) -sin(rot_rad) 0; 
%                               sin(rot_rad) cos(rot_rad) 0; 
%                               0 0 1];
% 
%                 % 平移到原點，旋轉，再平移回來
%                 to_origin = [1 0 -img_center(1); 0 1 -img_center(2); 0 0 1];
%                 from_origin = [1 0 img_center(1); 0 1 img_center(2); 0 0 1];
%                 rotation_around_center = from_origin * rot_matrix * to_origin;
%                 adjustment = adjustment * rotation_around_center;
% 
%                 % 應用平移
%                 translation_matrix = [1 0 tx; 0 1 ty; 0 0 1];
%                 adjustment = adjustment * translation_matrix;
% 
%                 % 將調整應用到當前變換
%                 combined_matrix = adjustment * tform.T;
%                 adjusted_tform = projective2d(combined_matrix);
% 
%                 % 應用變換
%                 adjusted_corrected = imwarp(captured, adjusted_tform, 'OutputView', outputView);
% 
%                 % 計算MSE（僅在有效區域）
%                 if size(adjusted_corrected, 3) == 3
%                     adjusted_gray = double(rgb2gray(adjusted_corrected));
%                 else
%                     adjusted_gray = double(adjusted_corrected);
%                 end
% 
%                 % 只比較有內容的區域 - 同時考慮原始和調整後的有效區域
%                 adjusted_mask = adjusted_gray > 0;
%                 combined_mask = valid_mask & adjusted_mask;
% 
%                 % 確保有足夠的重疊區域
%                 overlap_percentage = sum(combined_mask(:)) / sum(valid_mask(:)) * 100;
% 
%                 if overlap_percentage > 50  % 要求至少80%的重疊
%                     current_mse = mean((gt_gray(combined_mask) - adjusted_gray(combined_mask)).^2);
% 
%                     % 記錄結果
%                     results = [results; tx ty rot scale current_mse overlap_percentage];
% 
%                     % 更新最佳結果
%                     if current_mse < best_mse && overlap_percentage > 80
%                         best_mse = current_mse;
%                         best_tform = adjusted_tform;
% 
%                         % 顯示每次找到更好的結果時的參數
%                         disp(['找到更好的結果: tx=', num2str(tx), ', ty=', num2str(ty), ...
%                               ', rot=', num2str(rot), ', scale=', num2str(scale), ...
%                               ', MSE=', num2str(current_mse), ...
%                               ', 重疊=', num2str(overlap_percentage), '%']);
% 
%                         % 立即可視化當前最佳結果
%                         figure(99);
%                         best_corrected = imwarp(captured, best_tform, 'OutputView', outputView);
% 
%                         % 填充背景
%                         if size(best_corrected, 3) == 3
%                             black_mask = (best_corrected(:,:,1) == 0) & ...
%                                         (best_corrected(:,:,2) == 0) & ...
%                                         (best_corrected(:,:,3) == 0);
%                         else
%                             black_mask = (best_corrected == 0);
%                         end
% 
%                         best_filled = best_corrected;
%                         if size(best_corrected, 3) == 3
%                             for c = 1:3
%                                 channel = best_filled(:,:,c);
%                                 channel(black_mask) = bg_color(c);
%                                 best_filled(:,:,c) = channel;
%                             end
%                         else
%                             best_filled(black_mask) = bg_color;
%                         end
% 
%                         subplot(1,3,1); imshow(groundtruth); title('Ground Truth');
%                         subplot(1,3,2); imshow(captured); title('待校正圖像');
%                         subplot(1,3,3); imshow(best_filled); 
%                         title(['優化中 (MSE: ', num2str(best_mse), ')']);
%                         drawnow;
%                     end
%                 end
%             end
%         end
%     end
% end
% 
% 
% % 關閉進度條
% close(h_waitbar);
% 
% % 如果有改進，應用最佳變換
% if best_mse < initial_mse
%     improvement = ((initial_mse - best_mse) / initial_mse) * 100;
%     disp(['精細優化成功! MSE從 ', num2str(initial_mse), ...
%           ' 降低到 ', num2str(best_mse), ...
%           ' (改善 ', num2str(improvement), '%)']);
% 
%     % 應用最佳變換
%     optimized_corrected = imwarp(captured, best_tform, 'OutputView', outputView);
% else
%     disp('精細優化未能改善MSE，保持原始變換結果');
%     optimized_corrected = initial_corrected;
%     best_mse = initial_mse;
% end
% 
% % 填充黑色區域
% if size(optimized_corrected, 3) == 3
%     black_mask = (optimized_corrected(:,:,1) == 0) & ...
%                 (optimized_corrected(:,:,2) == 0) & ...
%                 (optimized_corrected(:,:,3) == 0);
% else
%     black_mask = (optimized_corrected == 0);
% end
% 
% optimized_filled = optimized_corrected;
% if size(optimized_corrected, 3) == 3
%     for c = 1:3
%         channel = optimized_filled(:,:,c);
%         channel(black_mask) = bg_color(c);
%         optimized_filled(:,:,c) = channel;
%     end
% else
%     optimized_filled(black_mask) = bg_color;
% end
% 
% % 保存結果
% imwrite(optimized_filled, 'corrected_fine_tuned.png');
% 
% % 顯示最終結果
% figure('Name', '精細優化結果');
% subplot(1,3,1); imshow(groundtruth); title('Ground Truth');
% subplot(1,3,2); imshow(captured); title('待校正圖像');
% subplot(1,3,3); imshow(optimized_filled); title(['優化後 (MSE: ', num2str(best_mse), ')']);
% 
% % 保存比較圖
% set(gcf, 'Color', 'white');
% saveas(gcf, 'correction_comparison.png');
% 
% 
% disp('計算最終優化後的MSE比較...');
% 
% % 計算像素差異 - 使用三張關鍵圖像：Ground Truth、原始圖像和最終優化圖像
% if size(groundtruth, 3) == 3
%     % 彩色圖像 - 轉為灰度計算MSE
%     gt_for_mse = double(rgb2gray(groundtruth));
%     original_for_mse = double(rgb2gray(captured));
%     final_for_mse = double(rgb2gray(optimized_filled));
% else
%     % 灰度圖像
%     gt_for_mse = double(groundtruth);
%     original_for_mse = double(captured);
%     final_for_mse = double(optimized_filled);
% end
% 
% % 創建有效區域掩碼 - 忽略黑色區域
% valid_mask_original = original_for_mse > 0;
% valid_mask_final = final_for_mse > 0;
% valid_mask_combined = valid_mask_original & valid_mask_final;
% 
% % 計算原始圖像與GT的均方誤差 (MSE)
% squared_diff_original = (gt_for_mse - original_for_mse).^2;
% mse_original = mean(squared_diff_original(valid_mask_combined));
% rmse_original = sqrt(mse_original);
% 
% % 計算最終優化圖像與GT的均方誤差 (MSE)
% squared_diff_final = (gt_for_mse - final_for_mse).^2;
% mse_final = mean(squared_diff_final(valid_mask_combined));
% rmse_final = sqrt(mse_final);
% 
% % 計算改善百分比
% improvement_percent = ((mse_original - mse_final) / mse_original) * 100;
% 
% % 創建差異圖像 (熱圖)
% % 使用相同的色彩映射範圍以便比較
% max_diff = max(max(squared_diff_original(:)), max(squared_diff_final(:)));
% normalized_diff_original = squared_diff_original / max_diff;
% normalized_diff_final = squared_diff_final / max_diff;
% 
% % 顯示MSE比較
% figure('Name', '最終MSE比較評估', 'Position', [100, 100, 1000, 700]);
% 
% % 原始圖像
% subplot(2,3,1); 
% imshow(captured); 
% title('原始待校正圖像');
% 
% % 優化後圖像
% subplot(2,3,2); 
% imshow(optimized_filled); 
% title('最終優化後圖像');
% 
% % Ground Truth
% subplot(2,3,3); 
% imshow(groundtruth); 
% title('Ground Truth');
% 
% % 原始圖像的差異熱圖
% subplot(2,3,4); 
% imagesc(normalized_diff_original);
% colormap('jet');
% colorbar;
% title(sprintf('校正前 MSE = %.2f, RMSE = %.2f', mse_original, rmse_original));
% axis image;
% 
% % 最終優化圖像的差異熱圖
% subplot(2,3,5); 
% imagesc(normalized_diff_final);
% colormap('jet');
% colorbar;
% title(sprintf('最終校正後 MSE = %.2f, RMSE = %.2f', mse_final, rmse_final));
% axis image;
% 
% % 顯示改善百分比
% subplot(2,3,6);
% bar([mse_original, mse_final]);
% set(gca, 'XTickLabel', {'校正前', '最終校正後'});
% ylabel('MSE值');
% title(sprintf('校正改善了 %.2f%%', improvement_percent));
% grid on;
% 
% % 保存MSE比較圖
% saveas(gcf, 'final_mse_comparison.png');
% 
% % 在命令窗口顯示數值比較
% disp('======= 最終MSE比較結果 =======');
% disp(['校正前 MSE = ', num2str(mse_original)]);
% disp(['最終校正後 MSE = ', num2str(mse_final)]);
% disp(['改善百分比 = ', num2str(improvement_percent), '%']);

%% 步驟10: 顯示和儲存最終結果 (不使用export_fig)
% 創建一個新的圖像窗口，顯示三張圖並排
figure('Name', '校正結果比較', 'Position', [100, 100, 1200, 400]);

% 顯示三張圖像並排
subplot(1,3,1); 
imshow(groundtruth); 
title('Ground Truth', 'FontSize', 12);

subplot(1,3,2); 
imshow(captured); 
title('待校正圖像', 'FontSize', 12);

subplot(1,3,3); 
imshow(optimized_filled); % 使用優化後的結果
title('校正後圖像', 'FontSize', 12);

% 確保圖像保持原始比例
for i = 1:3
    subplot(1,3,i);
    axis image;
end

% 將整個窗口設置為白色背景
set(gcf, 'Color', 'white');

% 保存比較圖 - 使用內建函數
saveas(gcf, 'correction_comparison.png');

% 輸出信息
disp('校正完成！');
disp('單張校正圖像已保存為 corrected_optimized.png');
disp('比較圖已保存為 correction_comparison.png');

%% 輔助函數: 基於四個角落點生成網格
function grid_points = generate_grid_from_corners(corners, rows, cols)
    % 確保corners是按左上、右上、左下、右下的順序
    TL = corners(1,:);
    TR = corners(2,:);
    BL = corners(3,:);
    BR = corners(4,:);
    
    % 初始化結果網格
    grid_points = zeros((rows+1) * (cols+1), 2);
    
    % 計算每個網格點的位置
    for r = 0:rows
        for c = 0:cols
            % 計算當前點在網格中的歸一化位置 (0-1)
            u = c / cols;
            v = r / rows;
            
            % 使用雙線性插值計算實際坐標
            % 先插值頂部和底部邊緣
            top = TL + u * (TR - TL);
            bottom = BL + u * (BR - BL);
            
            % 然後在這兩點之間插值
            point = top + v * (bottom - top);
            
            % 保存到結果數組
            idx = r * (cols+1) + c + 1;
            grid_points(idx, :) = point;
        end
    end
end

%% 輔助函數: 精細調整角點位置到實際直角處
function refined_points = refine_corner_positions(img, points, window_size)
    refined_points = points;
    
    % 對每個點進行局部搜索
    for i = 1:size(points, 1)
        x = round(points(i, 1));
        y = round(points(i, 2));
        
        % 確保搜索窗口在圖像範圍內
        x_min = max(1, x - window_size);
        x_max = min(size(img, 2), x + window_size);
        y_min = max(1, y - window_size);
        y_max = min(size(img, 1), y + window_size);
        
        % 提取局部區域
        window = img(y_min:y_max, x_min:x_max);
        
        % 計算Harris角點響應
        corners = detectHarrisFeatures(window);
        
        % 如果檢測到角點，選擇最強的一個
        if ~isempty(corners.Location)
            strongest = corners.selectStrongest(1);
            
            % 將窗口內坐標轉換回全局坐標
            refined_x = strongest.Location(1) + x_min - 1;
            refined_y = strongest.Location(2) + y_min - 1;
            
            refined_points(i, :) = [refined_x, refined_y];
        end
        % 如果未檢測到角點，保留原始位置
    end
end