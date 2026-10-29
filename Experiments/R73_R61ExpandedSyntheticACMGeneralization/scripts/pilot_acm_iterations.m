function pilot_acm_iterations(experiment_root)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))));
if nargin < 1
    experiment_root = fileparts(fileparts(mfilename('fullpath')));
end
cfg = jsondecode(fileread(fullfile(experiment_root, 'config', 'experiment.json')));
data_root = fullfile(PROJECT_ROOT, char(cfg.dataset.root));
iterations_list = [50 100 200 300];
selected_files = {'0000.bmp', '0007.bmp', '0014.bmp'};
rows = struct([]);
for family_index = 1:numel(cfg.dataset.families)
    family = cfg.dataset.families(family_index);
    stage = char(family.stage);
    for file_index = 1:numel(selected_files)
        filename = selected_files{file_index};
        exact = imread(fullfile(data_root, 'mask', stage, filename)) > 0;
        image = im2double(imread(fullfile(data_root, 'lbl', stage, filename)));
        for iter_index = 1:numel(iterations_list)
            predicted = segment(image, iterations_list(iter_index));
            row.family = string(family.name);
            row.filename = string(filename);
            row.iterations = iterations_list(iter_index);
            row.iou = nnz(exact & predicted) / nnz(exact | predicted);
            row.area_ratio = nnz(predicted) / nnz(exact);
            if isempty(rows), rows = row; else, rows(end+1, 1) = row; end %#ok<AGROW>
        end
    end
end
table_dir = fullfile(experiment_root, 'results', 'tables');
if ~exist(table_dir, 'dir'), mkdir(table_dir); end
writetable(struct2table(rows), fullfile(table_dir, 'acm_iteration_pilot.csv'));
summary = groupsummary(struct2table(rows), 'iterations', {'min','median'}, 'iou');
disp(summary);
end

function mask = segment(image, iterations)
image = mat2gray(image);
limits = stretchlim(image, [0.01 0.99]);
if limits(2) > limits(1), image = imadjust(image, limits, [0 1]); end
initial = automatic_inner_seed(image);
mask = activecontour(image, initial, iterations, 'Chan-Vese', 'SmoothFactor', 1, 'ContractionBias', 0);
components = bwconncomp(mask, 8);
[~, best] = max(cellfun(@numel, components.PixelIdxList));
selected = false(size(mask)); selected(components.PixelIdxList{best}) = true;
mask = imfill(selected, 'holes');
end

function seed = automatic_inner_seed(image)
level = graythresh(image);
candidates = {image >= level, image <= level};
best_area = -inf; seed = false(size(image));
for candidate_index = 1:2
    candidate = imclearborder(candidates{candidate_index}, 8);
    components = bwconncomp(candidate, 8);
    if components.NumObjects == 0, continue; end
    [area, best] = max(cellfun(@numel, components.PixelIdxList));
    area_fraction = area / numel(image);
    if area_fraction >= 0.05 && area_fraction <= 0.65 && area > best_area
        selected = false(size(image)); selected(components.PixelIdxList{best}) = true;
        seed = selected; best_area = area;
    end
end
if best_area < 0, error('Could not derive a valid automatic inner seed.'); end
seed = imerode(imfill(seed, 'holes'), strel('disk', 3));
if ~any(seed, 'all'), error('Automatic inner seed became empty.'); end
end
