function [psf_mosaic, fig_handle] = visualize_fitted_psf_grid(mat_path, varargin)
%VISUALIZE_FITTED_PSF_GRID Render fitted PSFs across the full FOV as one heatmap.
%
% Example:
%   visualize_fitted_psf_grid;
%   visualize_fitted_psf_grid([], 'CropSize', 17, 'TileSize', 5, ...
%       'NormalizeEachPSF', true, 'OutputPath', 'Crop_circle_FreqFiltered/Fits/fitted_psf_grid.png');

if nargin < 1 || isempty(mat_path)
    mat_path = fullfile('Crop_circle_FreqFiltered', 'Fits', 'PSF_fitted_2D_FOVstack.mat');
end

parser = inputParser;
parser.addParameter('CropSize', 21, @(x) validateattributes(x, {'numeric'}, {'scalar', 'integer', '>=', 3}));
parser.addParameter('TileSize', 5, @(x) validateattributes(x, {'numeric'}, {'scalar', 'integer', '>=', 2}));
parser.addParameter('GapSize', 1, @(x) validateattributes(x, {'numeric'}, {'scalar', 'integer', '>=', 0}));
parser.addParameter('NormalizeEachPSF', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('UseLogScale', false, @(x) islogical(x) || isnumeric(x));
parser.addParameter('OutputPath', "", @(x) ischar(x) || isstring(x));
parser.addParameter('FigureTitle', "Fitted PSFs", @(x) ischar(x) || isstring(x));
parser.parse(varargin{:});
opts = parser.Results;

data = load(mat_path);
psf_grid = extract_psf_grid(data);

if ndims(psf_grid) ~= 4
    error('Expected psf_grid to be H x W x rows x cols, but received %s.', mat2str(size(psf_grid)));
end

[psf_h, psf_w, grid_rows, grid_cols] = size(psf_grid);
crop_size = min([opts.CropSize, psf_h, psf_w]);
if mod(crop_size, 2) == 0
    crop_size = crop_size - 1;
end

row_center = floor((psf_h + 1) / 2);
col_center = floor((psf_w + 1) / 2);
half_crop = floor(crop_size / 2);
row_idx = (row_center - half_crop):(row_center + half_crop);
col_idx = (col_center - half_crop):(col_center + half_crop);

tile_size = opts.TileSize;
gap_size = opts.GapSize;
canvas_h = grid_rows * tile_size + (grid_rows - 1) * gap_size;
canvas_w = grid_cols * tile_size + (grid_cols - 1) * gap_size;
psf_mosaic = zeros(canvas_h, canvas_w);

for row = 1:grid_rows
    for col = 1:grid_cols
        tile = double(psf_grid(row_idx, col_idx, row, col));
        tile = max(tile, 0);

        if opts.NormalizeEachPSF
            tile_peak = max(tile(:));
            if tile_peak > 0
                tile = tile ./ tile_peak;
            end
        end

        if opts.UseLogScale
            tile = log1p(tile);
        end

        tile = imresize(tile, [tile_size, tile_size], 'bicubic');

        row_start = (row - 1) * (tile_size + gap_size) + 1;
        col_start = (col - 1) * (tile_size + gap_size) + 1;
        psf_mosaic(row_start:row_start + tile_size - 1, col_start:col_start + tile_size - 1) = tile;
    end
end

fig_handle = figure('Color', 'w');
ax = axes(fig_handle);
imagesc(ax, psf_mosaic);
axis(ax, 'image');
colormap(ax, parula(256));
colorbar(ax);
title(ax, opts.FigureTitle);
xlabel(ax, sprintf('FOV columns (%d)', grid_cols));
ylabel(ax, sprintf('FOV rows (%d)', grid_rows));
disableDefaultInteractivity(ax);
if isprop(ax, 'Toolbar')
    ax.Toolbar.Visible = 'off';
end

if strlength(string(opts.OutputPath)) > 0
    output_path = char(opts.OutputPath);
    output_dir = fileparts(output_path);
    if ~isempty(output_dir) && ~exist(output_dir, 'dir')
        mkdir(output_dir);
    end
    exportgraphics(fig_handle, output_path, 'Resolution', 300);
end
end

function psf_grid = extract_psf_grid(data)
if isfield(data, 'psf_grid')
    psf_grid = data.psf_grid;
    return;
end

if isfield(data, 'fov_psf_data') && isfield(data.fov_psf_data, 'psf_grid')
    psf_grid = data.fov_psf_data.psf_grid;
    return;
end

error('Could not find ''psf_grid'' inside %s.', inputname(1));
end
