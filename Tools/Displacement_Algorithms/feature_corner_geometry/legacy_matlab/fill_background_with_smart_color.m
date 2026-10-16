%% 改進的背景填充函數 - 結合鄰近像素顏色與原始背景灰色
function filled_img = fill_background_with_smart_color(img, mask, original_img)
    % img: 待填充的圖像
    % mask: 需要填充的區域的掩碼 (true表示需要填充)
    % original_img: 原始圖像，用於提取背景顏色
    
    filled_img = img;
    
    % 從原始圖像獲取背景灰色參考
    if size(original_img, 3) == 3
        % 彩色圖像 - 轉換為灰度後取邊緣區域顏色
        orig_gray = rgb2gray(original_img);
        % 獲取邊緣區域像素（假設邊緣20像素為背景）
        edge_pixels = [
            orig_gray(1:20,:); 
            orig_gray(end-19:end,:);
            orig_gray(:,1:20);
            orig_gray(:,end-19:end)
        ];
        
        % 計算背景灰色值 (排除黑色和純白)
        edge_mask = (edge_pixels > 10) & (edge_pixels < 245);
        if sum(edge_mask(:)) > 0
            ref_bg_color = mean(edge_pixels(edge_mask));
        else
            ref_bg_color = 200; % 默認淺灰色
        end
        
        % 彩色圖像的背景顏色參考
        ref_bg_color_rgb = [ref_bg_color, ref_bg_color, ref_bg_color];
    else
        % 灰度圖像
        edge_pixels = [
            original_img(1:20,:); 
            original_img(end-19:end,:);
            original_img(:,1:20);
            original_img(:,end-19:end)
        ];
        edge_mask = (edge_pixels > 10) & (edge_pixels < 245);
        if sum(edge_mask(:)) > 0
            ref_bg_color = mean(edge_pixels(edge_mask));
        else
            ref_bg_color = 200; % 默認淺灰色
        end
    end
    
    % 距離變換 - 計算每個背景像素到最近非背景像素的距離
    dist_transform = bwdist(~mask);
    max_dist = max(dist_transform(:));
    if max_dist > 0
        normalized_dist = dist_transform / max_dist;
    else
        normalized_dist = zeros(size(mask));
    end
    
    % 對於彩色圖像，分別處理每個通道
    if size(img, 3) == 3
        for c = 1:3
            channel = filled_img(:,:,c);
            channel = fill_channel_with_smart_color(channel, mask, ref_bg_color_rgb(c), normalized_dist);
            filled_img(:,:,c) = channel;
        end
    else
        % 灰度圖像
        filled_img = fill_channel_with_smart_color(filled_img, mask, ref_bg_color, normalized_dist);
    end
end

function filled_channel = fill_channel_with_smart_color(channel, mask, bg_color, normalized_dist)
    % 創建臨時圖像用於填充
    filled_channel = channel;
    
    % 擴展掩碼區域用於獲取周圍的像素
    se = strel('disk', 2);
    
    % 迭代填充直到所有背景區域都被填充
    remaining_mask = mask;
    max_iterations = 50; % 防止無限循環
    
    for i = 1:max_iterations
        if ~any(remaining_mask(:))
            break;
        end
        
        % 獲取當前邊界
        boundary_mask = imdilate(remaining_mask, se) & ~remaining_mask;
        
        for y = 3:(size(channel, 1)-2)
            for x = 3:(size(channel, 2)-2)
                if remaining_mask(y, x)
                    % 獲取5x5鄰域內有效像素的平均值
                    neighbors = channel(y-2:y+2, x-2:x+2);
                    neighbors_mask = ~remaining_mask(y-2:y+2, x-2:x+2);
                    valid_neighbors = neighbors(neighbors_mask);
                    
                    if ~isempty(valid_neighbors)
                        % 計算鄰近像素的平均顏色
                        neighbor_color = mean(valid_neighbors);
                        
                        % 基於距離的權重計算 - 使用sigmoid函數獲得更自然的過渡
                        dist_weight = 1 / (1 + exp(-10 * (normalized_dist(y, x) - 0.5)));
                        
                        % 混合鄰近顏色和背景顏色
                        filled_channel(y, x) = (1-dist_weight) * neighbor_color + dist_weight * bg_color;
                        remaining_mask(y, x) = false;
                    end
                end
            end
        end
    end
    
    % 如果仍有未填充的區域，使用背景顏色填充
    if any(remaining_mask(:))
        filled_channel(remaining_mask) = bg_color;
    end
end