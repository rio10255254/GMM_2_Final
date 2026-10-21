clc; clear; close all;

%% ========== 檔案設定 ==========
GT_file_path = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle_1201\Crop_circle_901_v2\GT\GT_901_with_Block.bmp";
out_folder   = "D:\NonSystemFiles\GMM2\MitsutoyoSample_GMMSys_20x\TestImage\Representative_Clusters_Output\Crop_circle_1201\Crop_circle_901_v2\GT\";   % 若不想存檔可註解下面 imwrite

if ~exist(out_folder,'dir'); mkdir(out_folder); end
[~, gt_name, gt_ext] = fileparts(GT_file_path);
fprintf('開始處理 GT 影像：%s%s\n', gt_name, gt_ext);

%% ========== 基本設定 ==========
crop_size   = 901;                  % 固定輸出大小
target_cx   = (crop_size+1)/2;      % = 451
target_cy   = (crop_size+1)/2;      % = 451
target_center = [target_cx, target_cy];
half_span   = (crop_size-1)/2;      % = 450

%% ========== 找圓參數（imfindcircles）==========
scale_detect = 1;     % 先縮放再找圓 (=1 表示不縮放)
sens         = 0.92;  % 霍夫靈敏度
minR         = 300;   % 半徑搜尋下界（以原圖為基準）
maxR         = 450;   % 半徑搜尋上界

%% ========== 中心區域「黑塊」修補參數 ==========
adapt_sens_center   = 1;     % imbinarize(adaptive) 靈敏度（越小越嚴）
inner_ratio_mask    = 0.65;  % 只在 r*ratio 內偵測黑塊
blend_inner_ratio   = 0.95;  % feather 到 r*ratio 內
feather_dilate_px_c = 31;    % 遮罩外擴像素
feather_norm_px_c   = 31;    % 權重距離正規化
gaussian_sigma_c    = 31;    % 過渡模糊強度

%% ========== 四角亮點（白塊）修補參數 ==========
inner_ratio_corner   = 1.02;   % 從外圓往外多少才開始偵測角落（>1 避開圓邊）
corner_margin        = 150;    % 四角偵測框寬高（像素）
tophat_radius        = 25;     % white top-hat 的結構元素半徑
alpha_otsu_corner    = 0.001;  % Otsu 門檻縮放（<1 放寬、>1 加嚴）
min_area_corner      = 9;      % 移除太小的白點
dilate_r_corner      = 3;      % 遮罩外擴半徑
feather_r_corner     = 4;      % 羽化帶寬
feather_sigma_corner = 3;      % 羽化模糊

%% ========== 主流程（只處理 GT）==========
try
    % 讀取影像並轉灰階
    imgU = imread(GT_file_path);
    imgG = im2gray(imgU);
    I    = im2double(imgG);

    %% ========== 圓心檢測（優先用多法融合）==========
    circle_center = findCircleCenter(imgG);

    if isempty(circle_center)
        fprintf('  警告: 多法未找到圓心，改用 imfindcircles 備援\n');
        img_s = imresize(imgG, scale_detect);
        rmin  = round(minR * scale_detect);
        rmax  = round(maxR * scale_detect);
        [C, R, M] = imfindcircles(img_s, [rmin rmax], ...
            'ObjectPolarity','bright','Sensitivity', sens);
        if isempty(C)
            error('未找到圓');
        end
        [~, ib]   = max(M);
        c_small   = C(ib,:);      r_small = R(ib);
        cx0       = c_small(1) / scale_detect;
        cy0       = c_small(2) / scale_detect;
        r         = r_small / scale_detect;
        circle_center = [cx0, cy0];
    else
        fprintf('  偵測到圓心: (%.2f, %.2f)\n', circle_center(1), circle_center(2));
        cx0 = circle_center(1);
        cy0 = circle_center(2);
        % 半徑估計使用 imfindcircles 提升穩定性
        img_s = imresize(imgG, scale_detect);
        rmin  = round(minR * scale_detect);
        rmax  = round(maxR * scale_detect);
        [~, R, M] = imfindcircles(img_s, [rmin rmax], ...
            'ObjectPolarity','bright','Sensitivity', sens);
        if ~isempty(R)
            [~, ib] = max(M);
            r = R(ib) / scale_detect;
        else
            r = (minR + maxR) / 2;
        end
    end

    %% ========== 應用平移對心 ==========
    dx = target_center(1) - circle_center(1);
    dy = target_center(2) - circle_center(2);
    fprintf('  平移量: dx=%.2f, dy=%.2f\n', dx, dy);

    aligned_img = translateImage(imgU, dx, dy);

    if size(aligned_img,3) == 3
        I_aligned = im2double(rgb2gray(aligned_img));
    else
        I_aligned = im2double(aligned_img);
    end

    %% ========== 裁切成 901×901 ==========
    [H0, W0] = size(I_aligned);
    x1 = round(target_cx - half_span);  y1 = round(target_cy - half_span);
    x2 = x1 + crop_size - 1;            y2 = y1 + crop_size - 1;

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
    I_crop = Ipad(y1:y2, x1:x2);        % 901×901
    cx = target_cx;  cy = target_cy;    % 鎖定中心

    %% ========== 中心黑塊修補（可開關）==========
    [xx, yy]    = meshgrid(1:crop_size, 1:crop_size);
    circle_mask = (xx - cx).^2 + (yy - cy).^2 <= (inner_ratio_mask * r)^2;

    bw_center = ~imbinarize(I_crop, 'adaptive', 'Sensitivity', adapt_sens_center);
    dark_mask = bw_center & circle_mask;
    I_fill = I_crop;

    % 如需開啟中心區域 feather 過渡，取消註解以下區塊
    % I_fill = regionfill(I_crop, dark_mask);
    % if any(dark_mask(:))
    %     circle_limit = (xx - cx).^2 + (yy - cy).^2 <= (blend_inner_ratio * r)^2;
    %     blend_mask   = imdilate(dark_mask, strel('disk', feather_dilate_px_c)) & circle_limit;
    %     if any(blend_mask(:))
    %         D      = bwdist(~blend_mask);
    %         w      = min(D / feather_norm_px_c, 1) .* blend_mask;
    %         I_blur = imgaussfilt(I_fill, gaussian_sigma_c);
    %         I_fill = I_fill .* (1 - w) + I_blur .* w;
    %     end
    % end

    %% ========== 四角亮點修補 ==========
    outer_mask = (xx - cx).^2 + (yy - cy).^2 >= (inner_ratio_corner * r)^2;

    corner_mask = false(crop_size, crop_size);
    cm = corner_margin;
    corner_mask(1:cm, 1:cm) = true;                          % 左上
    corner_mask(1:cm, end-cm+1:end) = true;                  % 右上
    corner_mask(end-cm+1:end, 1:cm) = true;                  % 左下
    corner_mask(end-cm+1:end, end-cm+1:end) = true;          % 右下
    search_mask = outer_mask & corner_mask;

    I_wh     = imtophat(I_fill, strel('disk', tophat_radius));
    t        = graythresh(I_wh(search_mask));                % ROI 上 Otsu
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

    I_out = I_corner;

    %% ========== 存檔 ==========
    new_filename = gt_name + "_proc" + gt_ext; 
    out_path = fullfile(out_folder, new_filename);  % 例如 GT_901_proc.bmp
    imwrite(im2uint8(I_out), out_path);
    fprintf('處理完成，已保存到：%s\n', out_path);

    %% ========== 顯示結果之梯度圖（imagesc）==========
    [Gmag_out, ~] = imgradient(I_out);
    figure('Name','Gradient of Processed Result','Color','w');
    imagesc(Gmag_out); axis image; colorbar;
    title('Gradient Magnitude (Processed Result)');


catch ME
    fprintf('處理失敗：%s\n', ME.message);
end

fprintf('所有作業完成（僅 GT 一張）。\n');

%% ========== 圓心檢測函數 ==========
function center = findCircleCenter(img)
    center = [];
    try
        center = findCircleByHough(img);
        if ~isempty(center); return; end
    catch
        fprintf('    霍夫檢測失敗，嘗試其他方法\n');
    end
    try
        center = findCircleByEdge(img);
        if ~isempty(center); return; end
    catch
        fprintf('    邊檢失敗，嘗試質心法\n');
    end
    try
        center = findCircleByCentroid(img);
    catch
        fprintf('    質心法也失敗\n');
    end
end

function center = findCircleByHough(img)
    center = [];
    edges = edge(img, 'canny', [0.1 0.2]);
    [centers, radii] = imfindcircles(edges, [50 400], ...
        'ObjectPolarity','bright','Sensitivity',0.85,'EdgeThreshold',0.1);
    if ~isempty(centers)
        [~, maxIdx] = max(radii);
        center = centers(maxIdx, :);
        fprintf('    霍夫檢測到圓心: (%.2f, %.2f), R=%.2f\n', center(1), center(2), radii(maxIdx));
    end
end

function center = findCircleByEdge(img)
    center = [];
    threshold = graythresh(img);
    bw = imbinarize(img, threshold);
    bw_filled = imfill(bw, 'holes');
    cc = bwconncomp(bw_filled);
    if cc.NumObjects == 0; return; end
    areas = cellfun(@numel, cc.PixelIdxList);
    [~, maxIdx] = max(areas);
    mask = false(size(bw));
    mask(cc.PixelIdxList{maxIdx}) = true;
    props = regionprops(mask, 'Centroid','Eccentricity');
    if ~isempty(props) && props.Eccentricity < 0.3
        center = props.Centroid; % [x, y]
        fprintf('    邊緣法圓心: (%.2f, %.2f)\n', center(1), center(2));
    end
end

function center = findCircleByCentroid(img)
    center = [];
    img_inv = imcomplement(img);
    img_smooth = imgaussfilt(double(img_inv), 2);
    threshold = mean(img_smooth(:)) + std(img_smooth(:));
    mask = img_smooth > threshold;
    se = strel('disk', 5);
    mask = imopen(mask, se);
    mask = imfill(mask, 'holes');
    cc = bwconncomp(mask);
    if cc.NumObjects == 0; return; end
    areas = cellfun(@numel, cc.PixelIdxList);
    [~, maxIdx] = max(areas);
    largest = false(size(mask));
    largest(cc.PixelIdxList{maxIdx}) = true;
    [y, x] = find(largest);
    if ~isempty(x)
        weights = double(img_smooth(largest));
        cx = sum(x .* weights) / sum(weights);
        cy = sum(y .* weights) / sum(weights);
        center = [cx, cy];
        fprintf('    質心法圓心: (%.2f, %.2f)\n', center(1), center(2));
    end
end

function translated_img = translateImage(img, dx, dy)
    % Use affine transform to translate image
    tform = affine2d([1 0 0; 0 1 0; dx dy 1]);
    refIn = imref2d(size(img, [1 2]));
    translated_img = imwarp(img, tform, 'OutputView', refIn, ...
        'FillValues', 255, 'InterpolationMethod', 'cubic');
end