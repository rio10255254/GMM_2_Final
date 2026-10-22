clc; clear; close all;

% 1) Find the center of the bright circle (parallel)
% 2) (Optional) Mask inner squares later if needed
% 3) (Optional) Crop ROI around the circle later if needed

%% Collect files (sorted by name = timestamp order)
folder = 'TestImage\\Representative_Clusters_Output\\';
files = dir(fullfile(folder, 'VisionTop_*.bmp'));
[~, idx] = sort({files.name});
files = files(idx);
numFiles = numel(files);

if numFiles == 0
    error('No files found.');
end

%% Prepare results (use fixed-size arrays for parfor)
centers_all = nan(numFiles, 2);    % [x, y] per image
radii_all   = nan(numFiles, 1);    % radius per image
found       = false(numFiles, 1);  % flag if circle found

% Parameters
scale = 0.25;       % downscale factor to speed up Hough
sens  = 0.92;       % imfindcircles sensitivity

%% Start or reuse a pool
p = gcp('nocreate');
if isempty(p)
    % You can change the number of workers if needed, e.g., parpool('local', 6)
    parpool('local');
end

%% Simple progress bar using a DataQueue
dq = parallel.pool.DataQueue;
progCnt = 0;
afterEach(dq, @nUpdate);
fprintf('Processing %d images in parallel...\n', numFiles);

% Nested function for progress
function nUpdate(~)
    progCnt = progCnt + 1;
    if mod(progCnt, 10) == 0 || progCnt == numFiles
        fprintf('  Progress: %d / %d\n', progCnt, numFiles);
    end
end

%% Parallel loop: compute centers & radii only (no display here)
parfor k = 1:numFiles
    try
        filename = fullfile(folder, files(k).name);
        img = imread(filename);
        img = im2gray(img);

        % Downscale to speed up Hough
        img_small = imresize(img, scale);

        % Radius range at the downscaled resolution
        minR = max(5, round(50 * scale));
        maxR = round(min(size(img_small)) / 12);

        % Hough circle detection on bright circles
        [centers, radii, metric] = imfindcircles(img_small, [minR, maxR], ...
            'ObjectPolarity', 'bright', 'Sensitivity', sens);

        if ~isempty(centers)
            % Pick the circle with the highest metric
            [~, idxBest] = max(metric);
            center_small = centers(idxBest, :);
            radius_small = radii(idxBest);

            % Rescale back to original coordinates
            centers_all(k, :) = center_small / scale;
            radii_all(k)      = radius_small / scale;
            found(k)          = true;
        else
            found(k) = false;
        end

        % <-- 這裡直接印進度
        fprintf('處理第 %d/%d 張: %s\n', k, numFiles, files(k).name);

    catch
        found(k) = false;
        fprintf('第 %d/%d 張失敗: %s\n', k, numFiles, files(k).name);
    end
end
%% Sequential display (each frame shows for 0.2 s)
figure('Name', 'Circle detection preview');
for k = 1:numFiles
    filename = fullfile(folder, files(k).name);
    img = imread(filename);
    img = im2gray(img);

    imshow(img); hold on;
    if found(k)
        % viscircles(centers_all(k, :), radii_all(k), 'EdgeColor', 'b');
        plot(centers_all(k, 1), centers_all(k, 2), 'r.', 'MarkerSize', 12, 'LineWidth', 1.5);
        title(sprintf('Center = (%.1f, %.1f), Radius = %.1f px | %d/%d: %s', ...
            centers_all(k, 1), centers_all(k, 2), radii_all(k), ...
            k, numFiles, files(k).name));
    else
        title(sprintf('No circle found | %d/%d: %s', k, numFiles, files(k).name));
    end
    hold off;

    pause(0.02); % show each image for 0.2 s
end

%% (Optional) Save results
save('circle_results.mat', 'files', 'centers_all', 'radii_all', 'found');
fprintf('Done. Results saved to circle_results_parallel.mat\n');
