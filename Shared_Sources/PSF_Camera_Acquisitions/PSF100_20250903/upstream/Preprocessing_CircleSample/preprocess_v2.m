clc; clear; close all;

%% ========== 檔案設定 ========== 
in_folder   = 'D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle';
out_folder  = 'TestImage\\Crop_circle_901_v2\\';   % 若不想存檔可註解下面 imwrite
show_pause  = 0.08;                                % 每張顯示停留秒數
if ~exist(out_folder,'dir'); mkdir(out_folder); end
files  = dir(fullfile(in_folder, 'VisionTop_*.bmp'));
[~, idx] = sort({files.name}); files = files(idx);
numFiles = numel(files);

%% ========== 基本設定 ========== 
crop_size   = 901;          % 固定輸出大小
target_cx   = (crop_size+1)/2;   % = 451
target_cy   = (crop_size+1)/2;   % = 451
target_center = [target_cx, target_cy]; % 目標圓心位置 [x, y]
half_span   = (crop_size-1)/2;   % = 450

%% ========== 找圓參數（imfindcircles）========== 
scale_detect = 1;           % 先縮放再找圓 (=1 表示不縮放)
sens         = 0.92;        % 霍夫靈敏度
minR         = 300;         % 半徑搜尋下界（以原圖為基準）
maxR         = 450;         % 半徑搜尋上界

%% ========== 中心區域「黑塊」修補參數 ========== 
adapt_sens_center   = 1; % imbinarize(adaptive) 的靈敏度（越小越嚴）
inner_ratio_mask    = 0.65;  % 僅在 r*ratio 內偵測黑塊，避免外圈梯度
blend_inner_ratio   = 0.95;  % feather 僅做到 r*ratio 內
% feather（中心區域）
feather_dilate_px_c = 31;    % 遮罩外擴像素
feather_norm_px_c   = 31;    % 權重距離正規化
gaussian_sigma_c    = 31;    % 過渡模糊強度

%% ========== 四角亮點（白塊）修補參數 ========== 
inner_ratio_corner  = 1.02;  % 從外圓往外多少才開始偵測角落（>1 避開圓邊）
corner_margin       = 150;   % 四角偵測框寬高（像素）
tophat_radius       = 25;    % white top-hat 的結構元素半徑
alpha_otsu_corner   = 0.001; % Otsu 門檻縮放（<1 放寬、>1 加嚴），越小越寬鬆，抓到越多亮點
min_area_corner     = 9;     % 移除太小的白點
dilate_r_corner     = 3;     % 遮罩外擴半徑
% feather（四角）
feather_r_corner    = 4;     % 羽化帶寬
feather_sigma_corner= 3;     % 羽化模糊

%% ========== 結果容器 ========== 
centers_all = nan(numFiles, 2);   % [x, y]
radii_all   = nan(numFiles, 1);
found       = false(numFiles, 1);

fprintf('開始處理 %d 個檔案...\n', numFiles);

%% ========== 主流程 ========== 
for k = 1:numFiles
    try
        fprintf('處理第 %d/%d 個檔案: %s\n', k, numFiles, files(k).name);
        
        % 讀取影像並轉灰階
        fn   = fullfile(in_folder, files(k).name);
        imgU = imread(fn);
        imgG = im2gray(imgU);
        I    = im2double(imgG);

        %% ========== 使用 Claude_align 的圓心檢測方法 ========== 
        circle_center = findCircleCenter(imgG);
        
        if isempty(circle_center)
            fprintf('  警告: 未找到圓心，改用原始方法\n');
            
            % ---- 原始找圓方法（備用）----
            img_s = imresize(imgG, scale_detect);
            rmin  = round(minR * scale_detect);
            rmax  = round(maxR * scale_detect);
            [C, R, M] = imfindcircles(img_s, [rmin rmax], ...
                        'ObjectPolarity','bright','Sensitivity', sens);

            if isempty(C)
                fprintf('未找到圓: %s\n', files(k).name);
                continue;
            end

            % 取最強圓 → 轉回原尺寸座標
            [~, ib] = max(M);
            c_small = C(ib,:);    r_small = R(ib);
            cx0 = c_small(1) / scale_detect;     % x 座標
            cy0 = c_small(2) / scale_detect;     % y 座標
            r   = r_small      / scale_detect;
            circle_center = [cx0, cy0];
        else
            fprintf('  偵測到圓心: (%.2f, %.2f)\n', circle_center(1), circle_center(2));
            cx0 = circle_center(1);
            cy0 = circle_center(2);
            % 估算半徑（使用原方法獲得更準確的半徑）
            img_s = imresize(imgG, scale_detect);
            rmin  = round(minR * scale_detect);
            rmax  = round(maxR * scale_detect);
            [C, R, M] = imfindcircles(img_s, [rmin rmax], ...
                        'ObjectPolarity','bright','Sensitivity', sens);
            if ~isempty(R)
                [~, ib] = max(M);
                r = R(ib) / scale_detect;
            else
                r = (minR + maxR) / 2; % 預設半徑
            end
        end

        %% ========== 應用精確對位變換 ========== 
        % 計算需要的平移量
        dx = target_center(1) - circle_center(1);
        dy = target_center(2) - circle_center(2);
        
        fprintf('  平移量: dx=%.2f, dy=%.2f\n', dx, dy);
        
        % 將平移變換應用到彩色影像
        aligned_img = translateImage(imgU, dx, dy);
        
        % 轉灰階並轉為 double
        if size(aligned_img, 3) == 3
            I_aligned = im2double(rgb2gray(aligned_img));
        else
            I_aligned = im2double(aligned_img);
        end

        %% ========== 裁切成固定大小 ========== 
        [H0, W0] = size(I_aligned);
        x1 = round(target_cx - half_span);
        y1 = round(target_cy - half_span);
        x2 = x1 + crop_size - 1;
        y2 = y1 + crop_size - 1;

        % 邊界複製補邊，避免越界
        padL = max(0, 1 - x1);
        padT = max(0, 1 - y1);
        padR = max(0, x2 - W0);
        padB = max(0, y2 - H0);
        if any([padL padT padR padB] > 0)
            Ipad = padarray(I_aligned, [padT padL], 'replicate', 'pre');
            Ipad = padarray(Ipad, [padB padR], 'replicate', 'post');
            x1 = x1 + padL;  x2 = x2 + padL;
            y1 = y1 + padT;  y2 = y2 + padT;
        else
            Ipad = I_aligned;
        end

        I_crop = Ipad(y1:y2, x1:x2);      % 現在為 901×901
        cx = target_cx;  cy = target_cy;  % 中心鎖定
        centers_all(k,:) = [cx, cy];
        radii_all(k)     = r;
        found(k)         = true;

        %% ---- 中心區域：自適應偵測「黑塊」→ regionfill → feather ---- 
        [xx, yy]    = meshgrid(1:crop_size, 1:crop_size);
        circle_mask = (xx - cx).^2 + (yy - cy).^2 <= (inner_ratio_mask * r)^2;

        bw_center   = ~imbinarize(I_crop, 'adaptive', 'Sensitivity', adapt_sens_center);
        dark_mask   = bw_center & circle_mask;
        I_fill = I_crop;

        % 不遮中間方形就把這邊註解掉
        % I_fill = regionfill(I_crop, dark_mask);
        % if any(dark_mask(:))
        %     circle_limit = (xx - cx).^2 + (yy - cy).^2 <= (blend_inner_ratio * r)^2;
        %     blend_mask   = imdilate(dark_mask, strel('disk', feather_dilate_px_c)) & circle_limit;
        % 
        %     if any(blend_mask(:))
        %         D      = bwdist(~blend_mask);
        %         w      = min(D / feather_norm_px_c, 1) .* blend_mask;  % 權重範圍 0→1
        %         I_blur = imgaussfilt(I_fill, gaussian_sigma_c);
        %         I_fill = I_fill .* (1 - w) + I_blur .* w;
        %     end
        % end

        %% ---- 四角亮點：Top-hat/自動門檻 → regionfill → feather ---- 
        outer_mask = (xx - cx).^2 + (yy - cy).^2 >= (inner_ratio_corner * r)^2;

        corner_mask = false(crop_size, crop_size);
        cm = corner_margin;
        corner_mask(1:cm, 1:cm) = true;                              % 左上
        corner_mask(1:cm, end-cm+1:end) = true;                      % 右上
        corner_mask(end-cm+1:end, 1:cm) = true;                      % 左下
        corner_mask(end-cm+1:end, end-cm+1:end) = true;              % 右下

        search_mask = outer_mask & corner_mask;

        I_wh = imtophat(I_fill, strel('disk', tophat_radius));
        t    = graythresh(I_wh(search_mask));                        % Otsu 在 ROI 上
        bw_corner = (I_wh > alpha_otsu_corner * t) & search_mask;
        bw_corner = bwareaopen(bw_corner, min_area_corner);
        bw_corner = imdilate(bw_corner, strel('disk', dilate_r_corner));

        I_corner = regionfill(I_fill, bw_corner);

        if any(bw_corner(:))
            band      = imdilate(bw_corner, strel('disk', feather_r_corner));
            edge_zone = band & ~bw_corner;
            I_smooth  = imgaussfilt(I_corner, feather_sigma_corner);
            I_corner(edge_zone) = I_smooth(edge_zone);
        end

        I_out = I_corner;   % 最終影像

        % ---- 存檔/顯示 ---- 
        out_path = fullfile(out_folder, files(k).name);
        imwrite(im2uint8(I_out), out_path);

        % if k==1, hfig = figure('Name','精確對位 + 中心鎖定 901×901 + 補洞 + 四角修正'); end
        % figure(hfig); imshow(I_out); hold on;
        % plot(target_cx, target_cy, 'r+', 'MarkerSize', 10, 'LineWidth', 1.5);
        % viscircles([target_cx, target_cy], r, 'Color','g','LineWidth',0.8);
        % title(sprintf('Center=(%d,%d), R=%.1f | %s', target_cx, target_cy, r, files(k).name));
        % hold off; pause(show_pause);

        fprintf('  已保存到: %s\n', out_path);

    catch ME
        fprintf('失敗：%s | %s\n', files(k).name, ME.message);
    end
end

fprintf('所有檔案處理完成！共 %d / %d 張處理成功。\n', sum(found), numFiles);

%% ========== Claude_align 的圓心檢測函數 ========== 

function center = findCircleCenter(img)
    % 使用多種方法找到圓心
    center = [];
    
    % 方法1: 霍夫圓檢測
    try
        center = findCircleByHough(img);
        if ~isempty(center)
            return;
        end
    catch
        fprintf('    霍夫檢測失敗，嘗試其他方法\n');
    end
    
    % 方法2: 邊緣檢測 + 幾何中心
    try
        center = findCircleByEdge(img);
        if ~isempty(center)
            return;
        end
    catch
        fprintf('    邊緣檢測失敗，嘗試其他方法\n');
    end
    
    % 方法3: 質心法
    try
        center = findCircleByCentroid(img);
    catch
        fprintf('    質心法也失敗\n');
    end
end

function center = findCircleByHough(img)
    % 霍夫圓檢測
    center = [];
    
    % 邊緣檢測
    edges = edge(img, 'canny', [0.1 0.2]);
    
    % 霍夫圓偵測
    [centers, radii] = imfindcircles(edges, [50 400], ...
        'ObjectPolarity', 'bright', 'Sensitivity', 0.85, 'EdgeThreshold', 0.1);
    
    if ~isempty(centers)
        % 選擇最大圓
        [~, maxIdx] = max(radii);
        center = centers(maxIdx, :);
        fprintf('    霍夫檢測到圓心: (%.2f, %.2f), 半徑: %.2f\n', ...
            center(1), center(2), radii(maxIdx));
    end
end

function center = findCircleByEdge(img)
    % 邊緣檢測 + 區域分析
    center = [];
    
    % 二值化
    threshold = graythresh(img);
    bw = imbinarize(img, threshold);
    
    % 填補孔洞
    bw_filled = imfill(bw, 'holes');
    
    % 找最大連通區域
    cc = bwconncomp(bw_filled);
    if cc.NumObjects == 0
        return;
    end
    
    areas = cellfun(@numel, cc.PixelIdxList);
    [~, maxIdx] = max(areas);
    
    % 建立遮罩
    mask = false(size(bw));
    mask(cc.PixelIdxList{maxIdx}) = true;
    
    % 計算屬性
    props = regionprops(mask, 'Centroid', 'Area', 'Eccentricity');
    
    if ~isempty(props) && props.Eccentricity < 0.3 % 確保接近圓形
        center = props.Centroid; % [x, y]
        fprintf('    邊緣檢測到圓心: (%.2f, %.2f)\n', center(1), center(2));
    end
end

function center = findCircleByCentroid(img)
    % 加權質心法
    center = [];
    
    % 反轉影像（若圓為暗色）
    img_inv = imcomplement(img);
    
    % 高斯平滑
    img_smooth = imgaussfilt(double(img_inv), 2);
    
    % 門檻處理
    threshold = mean(img_smooth(:)) + std(img_smooth(:));
    mask = img_smooth > threshold;
    
    % 形態學處理
    se = strel('disk', 5);
    mask = imopen(mask, se);
    mask = imfill(mask, 'holes');
    
    % 找最大連通區域
    cc = bwconncomp(mask);
    if cc.NumObjects == 0
        return;
    end
    
    areas = cellfun(@numel, cc.PixelIdxList);
    [~, maxIdx] = max(areas);
    
    % 最大區域遮罩
    largest_mask = false(size(mask));
    largest_mask(cc.PixelIdxList{maxIdx}) = true;
    
    % 計算加權質心
    [y, x] = find(largest_mask);
    if ~isempty(x) && ~isempty(y)
        weights = double(img_smooth(largest_mask));
        center_x = sum(x .* weights) / sum(weights);
        center_y = sum(y .* weights) / sum(weights);
        center = [center_x, center_y]; % [x, y]
        fprintf('    質心法檢測到圓心: (%.2f, %.2f)\n', center(1), center(2));
    end
end

function translated_img = translateImage(img, dx, dy)
    % 使用仿射變換平移影像
    
    % 平移矩陣
    tform = affine2d([1 0 0; 0 1 0; dx dy 1]);
    
    % 套用變換
    translated_img = imwarp(img, tform, 'OutputView', imref2d(size(img)), ...
        'FillValues', 255, 'Interp', 'cubic');
end
