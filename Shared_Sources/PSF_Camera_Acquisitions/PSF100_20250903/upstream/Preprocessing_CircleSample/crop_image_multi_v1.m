clc; clear; close all;

% 載入結果，並取出需要的欄位（讓 parfor 好切片）
circle_data   = load('circle_results.mat');
files         = circle_data.files;           % struct array
centers_all   = circle_data.centers_all;     % Nx2
num_files     = numel(files);

% 路徑
file_folder = 'TestImage\\Representative_Clusters_Output\\';
save_folder = 'TestImage\\Crop_circle\\';
if ~exist(save_folder, 'dir'); mkdir(save_folder); end

% 裁剪設定
crop_size = 1201;
half_size = crop_size-1 / 2;

parfor k = 1:num_files
    try
        % 檔名與讀圖（保持和原來寫法一致）
        file_name = files(k).name;
        file_path = [file_folder, file_name];
        img = imread(file_path);

        % 取圓心（和原本一致）
        cx = round(centers_all(k, 1));
        cy = round(centers_all(k, 2));

        % 沒找到圓就跳過
        if isnan(cx) || isnan(cy)
            fprintf('Skip %s (no circle found)\n', file_name);
            continue;
        end

        % 邊界（固定輸出 crop_size × crop_size）
        H = size(img, 1); W = size(img, 2);
        x1 = round(cx - (crop_size-1)/2);
        x2 = x1 + crop_size - 1;
        y1 = round(cy - (crop_size-1)/2);
        y2 = y1 + crop_size - 1;

        % 邊界檢查（避免超出影像大小）
        if x1 < 1
            x1 = 1;
            x2 = crop_size;
        end
        if y1 < 1
            y1 = 1;
            y2 = crop_size;
        end
        if x2 > W
            x2 = W;
            x1 = W - crop_size + 1;
        end
        if y2 > H
            y2 = H;
            y1 = H - crop_size + 1;
        end

        % 裁剪（灰階/彩色都適用）
        if ndims(img) == 2
            crop_img = img(y1:y2, x1:x2);
        else
            crop_img = img(y1:y2, x1:x2, :);
        end

        % 存檔（同名 .bmp 到目標資料夾）
        save_path = [save_folder, file_name];
        imwrite(crop_img, save_path);

        fprintf('Saved: %s\n', save_path);

    catch ME
        fprintf('Failed: %s | %s\n', files(k).name, ME.message);
    end
end

disp('All images processed and saved!');
