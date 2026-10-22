clc; clear; close all;

%% Part 1 & 2: 收集檔案與平行處理 (維持不變)
% ... (為節省空間，此處省略 Part 1 和 Part 2 的程式碼，請沿用上一版的)
% ... 執行完 Part 2 後，我們應有 'results', 'resultCount', 'allCenters' 等變數

%% Part 1: 收集檔案並排序
imageFolder = "C:\Users\Rio\Desktop\TestImage\ConcentricCircle";
filePattern = fullfile(imageFolder, '*.bmp');
files = dir(filePattern);
[~, idx] = sort({files.name}); 
files = files(idx);
numFiles = numel(files); 
if numFiles == 0; error('在指定路徑 %s 中找不到 "*.bmp" 檔案。', imageFolder); end

%% Part 2: 平行處理找出所有圓心
scale = 0.25; sens = 0.92;
centers_all = nan(numFiles, 2); found = false(numFiles, 1);
p = gcp('nocreate'); if isempty(p); parpool('local'); end
fprintf('開始平行處理 %d 張影像...\n', numFiles);
parfor k = 1:numFiles
    try
        filename = fullfile(imageFolder, files(k).name);
        img = imread(filename);
        if size(img, 3) > 1; img = rgb2gray(img); end
        img_small = imresize(img, scale);
        minR = max(5, round(50 * scale));
        maxR = round(min(size(img_small)) / 12);
        [centers, radii, metric] = imfindcircles(img_small, [minR, maxR], ...
            'ObjectPolarity', 'bright', 'Sensitivity', sens);
        if ~isempty(centers)
            [~, idxBest] = max(metric);
            center_small = centers(idxBest, :);
            centers_all(k, :) = center_small / scale;
            found(k) = true;
        else
            found(k) = false;
        end
    catch ex
        fprintf('處理第 %d 張影像 "%s" 時發生錯誤: %s\n', k, files(k).name, ex.message);
        found(k) = false;
    end
end
fprintf('--- 所有影像平行處理完畢 ---\n\n');
valid_indices = find(found);
results = struct('FileName', {}, 'Center', {});
for i = 1:length(valid_indices)
    idx = valid_indices(i);
    results(i).FileName = files(idx).name;
    results(i).Center = centers_all(idx, :);
end
resultCount = length(results);
fprintf('共成功找到 %d 個圓心。\n\n', resultCount);
if resultCount < 2; disp('圓心數量不足，無法進行分群。'); return; end
allCenters = vertcat(results.Center);


%% Part 3: 2D 空間分群 (全新 DBSCAN 演算法)

% --- DBSCAN 參數設定 ---
% 這是您唯一需要調整的關鍵參數！
% epsilon: 一個點周圍多大的半徑(pixel)內算是「鄰居」。
%          這個值決定了點團的密集程度。您可以從 50 開始嘗試。
%          如果點團被錯誤地拆成多個，請「加大」此值。
%          如果不同的點團被錯誤地合併成一個，請「減小」此值。
epsilon = 50; 

% minpts: 至少要有幾個點 (包含自己) 才算是一個核心群組。
%         設為 2 表示只要有兩個點靠得夠近，就可以開始形成一個群組。
minpts = 2; 
% -------------------------

fprintf('開始使用 DBSCAN 進行 2D 空間分群...\n');
fprintf('Epsilon = %.1f, MinPts = %d\n', epsilon, minpts);

% 執行 DBSCAN 演算法
% idx 是一個向量，每個元素代表對應的點被分到第幾群。-1 代表雜訊。
cluster_indices = dbscan(allCenters, epsilon, minpts);

% 分析分群結果
unique_clusters = unique(cluster_indices(cluster_indices > 0));
num_clusters = length(unique_clusters);
num_noise = sum(cluster_indices == -1);

fprintf('分群完成！\n');
fprintf('共找到 %d 個密集點群，以及 %d 個離散雜訊點。\n\n', num_clusters, num_noise);


%% Part 4: 選取代表影像、複製檔案與視覺化

% --- 建立輸出資料夾 ---
[parentFolder, ~] = fileparts(imageFolder);
outputFolder = fullfile(parentFolder, 'Representative_Clusters_Output');
if ~exist(outputFolder, 'dir'); mkdir(outputFolder); end
fprintf('代表影像將被複製到: %s\n\n', outputFolder);

% --- 視覺化準備 ---
figure('Name', 'DBSCAN 2D 點群分群結果');
hold on;
cmap = lines(num_clusters);

% --- 處理每一個找到的點群 ---
fprintf('--- 開始選取各點群的代表影像 ---\n');
for i = 1:num_clusters
    cluster_id = unique_clusters(i);
    
    % 找出屬於目前這個點群的所有點的索引
    point_indices_in_this_cluster = find(cluster_indices == cluster_id);
    
    % 取得這些點的座標和檔案資訊
    cluster_coords = allCenters(point_indices_in_this_cluster, :);
    cluster_file_info = results(point_indices_in_this_cluster);
    
    % 1. 計算點群的幾何中心 (Centroid)
    centroid = mean(cluster_coords, 1);
    
    % 2. 找出距離中心點最近的那個點的索引
    % vecnorm 計算每一列(點)到中心點的歐幾里得距離
    distances_to_centroid = vecnorm(cluster_coords - centroid, 2, 2);
    [~, representative_local_idx] = min(distances_to_centroid);
    
    % 3. 取得代表點的檔案資訊
    representative_file_info = cluster_file_info(representative_local_idx);
    representative_filename = representative_file_info.FileName;
    
    fprintf('點群 %d (共 %d 個點) 的代表影像: "%s"\n', ...
        cluster_id, length(point_indices_in_this_cluster), representative_filename);
    
    % 4. 複製代表檔案
    source_path = fullfile(imageFolder, representative_filename);
    dest_path = fullfile(outputFolder, representative_filename);
    if exist(source_path, 'file'); copyfile(source_path, dest_path); end
    
    % 5. 在圖上繪製這個點群
    plot(cluster_coords(:,1), cluster_coords(:,2), 'o', ...
        'MarkerFaceColor', cmap(i,:), 'MarkerEdgeColor', cmap(i,:), ...
        'DisplayName', sprintf('點群 %d', cluster_id));
        
    % 6. 特別標示出被選為代表的那個點
    representative_point = cluster_coords(representative_local_idx, :);
    plot(representative_point(1), representative_point(2), 'ko', ...
        'MarkerSize', 12, 'LineWidth', 1.5, ...
        'HandleVisibility', 'off'); % 在圖例中隱藏星號
end

% 繪製被標記為雜訊的點
noise_points = allCenters(cluster_indices == -1, :);
if ~isempty(noise_points)
    plot(noise_points(:,1), noise_points(:,2), 'x', ...
        'MarkerEdgeColor', [0.5 0.5 0.5], ...
        'DisplayName', '雜訊點');
end

hold off;
axis([0 5120 0 5120]); 
pbaspect([1 1 1]);
grid on;
legend('show', 'Location', 'eastoutside');
title('DBSCAN 2D 點群分群與代表點選取結果');
xlabel('X 座標');
ylabel('Y 座標');

fprintf('\n--- 所有操作完成 ---\n');