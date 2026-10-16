function run_acm_qa()
% Save a visually inspectable subset of the exact ACM masks.

script_dir = fileparts(mfilename('fullpath'));
experiment_root = fileparts(script_dir);
raw_dir = fullfile(experiment_root, 'inputs', 'sem_paired_50x_exposure_stack');
recon_dir = fullfile(experiment_root, 'results', 'inference_runs', ...
    'reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020', ...
    'r61v16_psfoff_sem_paired_50x');
sem_dir = 'H:\From_2TB_D_disk\13_thesis\SEM_data';
mask_dir = fullfile(experiment_root, 'results', 'masks');
if ~exist(mask_dir, 'dir'), mkdir(mask_dir); end

selected_exposures = [13 18 24];
iterations = 200;
smooth_factor = 1.0;
cell_half = 52;
cell_side = 104;
% Start just outside the bright SEM rim. A larger seed can include the
% partial neighbouring pillar visible at a few cell edges.
seed_radius = 40;
support_radius = 45;

global_index = [
     6  5  4  3  2  1;
    12 11 10  9  8  7;
    18 17 16 15 14 13;
    24 23 22 21 20 19;
    30 29 28 27 26 25;
    36 35 34 33 32 31];
p_to_block = [3 1; 3 2; 3 3; 2 3; 2 2; 2 1; 1 1; 1 2; 1 3];

reference_raw = imread(fullfile(raw_dir, '13.bmp'));
[opt_centers, ~, ~] = imfindcircles(reference_raw, [28 45], ...
    'ObjectPolarity', 'dark', 'Sensitivity', 0.92, 'EdgeThreshold', 0.05);
opt_centers = sort_grid_centers(opt_centers, 6, 6);

truth_cells = zeros(cell_side, cell_side, 36, 'uint8');
truth_masks = false(cell_side, cell_side, 36);
for p_index = 1:9
    sem_image = imread(fullfile(sem_dir, sprintf('P-%02d.tiff', p_index)));
    sem_image = sem_image(:, :, 1);
    sem_aligned = imresize(sem_image(7:754, 142:914), 1/3.23, 'bicubic');
    [centers, ~, ~] = imfindcircles(sem_aligned, [28 45], ...
        'ObjectPolarity', 'bright', 'Sensitivity', 0.90, 'EdgeThreshold', 0.05);
    centers = sort_grid_centers(centers, 2, 2);
    block_row = p_to_block(p_index, 1);
    block_col = p_to_block(p_index, 2);
    ids = reshape(global_index(2*block_row-1:2*block_row, ...
        2*block_col-1:2*block_col).', 1, []);
    for local_index = 1:4
        pillar_id = ids(local_index);
        cell_image = extract_padded_cell(sem_aligned, centers(local_index, :), cell_half);
        truth_cells(:, :, pillar_id) = im2uint8(mat2gray(cell_image));
        truth_mask = segment_acm( ...
            cell_image, seed_radius, iterations, smooth_factor, support_radius);
        truth_masks(:, :, pillar_id) = remove_sem_edge_artifacts(truth_mask);
    end
end

raw_cells = zeros(cell_side, cell_side, 36, numel(selected_exposures), 'uint8');
recon_cells = zeros(cell_side, cell_side, 36, numel(selected_exposures), 'uint8');
raw_masks = false(cell_side, cell_side, 36, numel(selected_exposures));
recon_masks = false(cell_side, cell_side, 36, numel(selected_exposures));

for exposure_index = 1:numel(selected_exposures)
    exposure = selected_exposures(exposure_index);
    raw_image = imread(fullfile(raw_dir, sprintf('%d.bmp', exposure)));
    recon_image = imread(fullfile(recon_dir, sprintf('%d.bmp', exposure)));
    for row = 1:6
        for col = 1:6
            position = (row - 1) * 6 + col;
            pillar_id = global_index(row, col);
            raw_cell = extract_padded_cell(raw_image, opt_centers(position, :), cell_half);
            recon_cell = extract_padded_cell(recon_image, opt_centers(position, :), cell_half);
            raw_cells(:, :, pillar_id, exposure_index) = im2uint8(mat2gray(raw_cell));
            recon_cells(:, :, pillar_id, exposure_index) = im2uint8(mat2gray(recon_cell));
            raw_masks(:, :, pillar_id, exposure_index) = segment_acm( ...
                raw_cell, seed_radius, iterations, smooth_factor, support_radius);
            recon_masks(:, :, pillar_id, exposure_index) = segment_acm( ...
                recon_cell, seed_radius, iterations, smooth_factor, support_radius);
        end
    end
end

save(fullfile(mask_dir, 'acm_qa_masks.mat'), ...
    'truth_cells', 'truth_masks', 'raw_cells', 'raw_masks', ...
    'recon_cells', 'recon_masks', 'global_index', 'selected_exposures', ...
    'opt_centers', 'iterations', 'smooth_factor', 'cell_half', 'seed_radius', ...
    'support_radius', ...
    '-v7');
fprintf('R69 ACM QA masks saved for exposures 13, 18, and 24.\n');
end


function centers = sort_grid_centers(centers, rows, cols)
if size(centers, 1) ~= rows * cols
    error('Expected %d centers, found %d.', rows * cols, size(centers, 1));
end
[~, order] = sort(centers(:, 2));
centers = centers(order, :);
result = zeros(size(centers));
for row = 1:rows
    block = centers((row-1)*cols+1:row*cols, :);
    [~, x_order] = sort(block(:, 1));
    result((row-1)*cols+1:row*cols, :) = block(x_order, :);
end
centers = result;
end


function cell_image = extract_padded_cell(image, center, half_size)
if ~isfloat(image), image = im2double(image); end
padded = padarray(image, [half_size half_size], 'symmetric', 'both');
cx = round(center(1)) + half_size;
cy = round(center(2)) + half_size;
cell_image = padded(cy-half_size:cy+half_size-1, ...
    cx-half_size:cx+half_size-1);
end


function mask = segment_acm(cell_image, seed_radius, iterations, smooth_factor, support_radius)
image = mat2gray(cell_image);
limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1), image = imadjust(image, limits, [0 1]); end
[height, width] = size(image);
[x, y] = meshgrid(1:width, 1:height);
initial = (x-(width+1)/2).^2 + (y-(height+1)/2).^2 <= seed_radius^2;
mask = activecontour(image, initial, iterations, 'Chan-Vese', ...
    'SmoothFactor', smooth_factor, 'ContractionBias', 0);
support = (x-(width+1)/2).^2 + (y-(height+1)/2).^2 <= support_radius^2;
mask = mask & support;
mask = select_center_component(mask);
mask = imfill(mask, 'holes');
mask = bwareaopen(mask, 64);
fraction = nnz(mask) / numel(mask);
if fraction < 0.15 || fraction > 0.60
    error('Implausible ACM area fraction %.4f.', fraction);
end
end


function cleaned = remove_sem_edge_artifacts(mask)
% A few SEM crops contain a sliver from the neighbouring acquisition at a
% cell edge. Remove only sides that reach the outer 12-pixel trigger zone;
% every valid target contour stays at least 14 pixels away from the edge.
trigger_width = 12;
trim_width = 15;
cleaned = mask;
if any(cleaned(1:trigger_width, :), 'all'), cleaned(1:trim_width, :) = false; end
if any(cleaned(end-trigger_width+1:end, :), 'all'), cleaned(end-trim_width+1:end, :) = false; end
if any(cleaned(:, 1:trigger_width), 'all'), cleaned(:, 1:trim_width) = false; end
if any(cleaned(:, end-trigger_width+1:end), 'all'), cleaned(:, end-trim_width+1:end) = false; end
cleaned = select_center_component(cleaned);
cleaned = imfill(cleaned, 'holes');
end


function selected = select_center_component(mask)
components = bwconncomp(mask, 8);
[height, width] = size(mask);
center = [(width + 1) / 2, (height + 1) / 2];
best_index = 0;
best_score = inf;
for index = 1:components.NumObjects
    [rows, cols] = ind2sub(size(mask), components.PixelIdxList{index});
    score = norm([mean(cols), mean(rows)] - center) - 0.001 * numel(rows);
    if score < best_score, best_score = score; best_index = index; end
end
selected = false(size(mask));
selected(components.PixelIdxList{best_index}) = true;
end
