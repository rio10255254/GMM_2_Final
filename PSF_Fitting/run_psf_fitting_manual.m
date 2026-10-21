function summary = run_psf_fitting_manual(varargin)
%RUN_PSF_FITTING_MANUAL Clean manual entrypoint for formal Whole-FOV PSF fitting.
opts = parse_manual_options(varargin{:});

project_root = fileparts(mfilename('fullpath'));
validationlab_scripts = fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts');
opts.output_root = resolve_project_path(project_root, opts.output_root);
opts.reuse_candidate_output_root = resolve_project_path(project_root, opts.reuse_candidate_output_root);
addpath(project_root);
addpath(validationlab_scripts);
addpath(fullfile(project_root, 'SimulatePSF'));
addpath(genpath(fullfile(project_root, 'bads-1.1.3')));

validate_manual_inputs(project_root, opts);

fprintf('Manual PSF fitting entrypoint\n');
fprintf('Project root: %s\n', project_root);
fprintf('Subset indices: %s\n', mat2str(opts.subset_indices));
fprintf('Grid: %d x %d\n', opts.grid_rows, opts.grid_cols);
fprintf('Output root: %s\n', opts.output_root);
fprintf('Warm start: %d, pre-alignment: %d, lock tilt: %d\n', ...
    opts.warm_start, opts.pre_alignment, opts.lock_tilt);

impl_args = { ...
    'subset_indices', opts.subset_indices, ...
    'grid_rows', opts.grid_rows, ...
    'grid_cols', opts.grid_cols, ...
    'warm_start', opts.warm_start, ...
    'pre_alignment', opts.pre_alignment, ...
    'lock_tilt', opts.lock_tilt, ...
    'output_root', opts.output_root, ...
    'use_gpu', opts.use_gpu, ...
    'prealign_search_radius', opts.prealign_search_radius, ...
    'prealign_search_step', opts.prealign_search_step, ...
    'prealign_crop_size', opts.prealign_crop_size};

if strlength(string(opts.reuse_candidate_output_root)) > 0
    impl_args = [impl_args, {'reuse_candidate_output_root', opts.reuse_candidate_output_root}]; %#ok<AGROW>
end

summary = HDR_fitting_2D_WholeFOV_impl(impl_args{:});

fprintf('PSF fitting completed.\n');
fprintf('Batch results: %s\n', summary.batch_results_path);
fprintf('Fitted PSF stack: %s\n', summary.stack_path);
fprintf('Config: %s\n', summary.config_path);
end

function opts = parse_manual_options(varargin)
parser = inputParser;
parser.addParameter('subset_indices', 1:100, @(x) isnumeric(x) && ~isempty(x));
parser.addParameter('grid_rows', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('grid_cols', 10, @(x) isnumeric(x) && isscalar(x) && x >= 1);
parser.addParameter('warm_start', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('pre_alignment', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('lock_tilt', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('output_root', fullfile('Crop_circle_FreqFiltered', 'Fits'), @(x) ischar(x) || isstring(x));
parser.addParameter('use_gpu', [], @(x) isempty(x) || islogical(x) || isnumeric(x));
parser.addParameter('prealign_search_radius', 2, @(x) isnumeric(x) && isscalar(x) && x >= 0);
parser.addParameter('prealign_search_step', 0.25, @(x) isnumeric(x) && isscalar(x) && x > 0);
parser.addParameter('prealign_crop_size', 257, @(x) isnumeric(x) && isscalar(x) && x >= 33);
parser.addParameter('reuse_candidate_output_root', '', @(x) ischar(x) || isstring(x));
parser.parse(varargin{:});

opts = parser.Results;
opts.subset_indices = unique(double(opts.subset_indices(:))', 'stable');
opts.grid_rows = double(opts.grid_rows);
opts.grid_cols = double(opts.grid_cols);
opts.warm_start = logical(opts.warm_start);
opts.pre_alignment = logical(opts.pre_alignment);
opts.lock_tilt = logical(opts.lock_tilt);
opts.output_root = char(opts.output_root);
opts.reuse_candidate_output_root = char(opts.reuse_candidate_output_root);
end

function validate_manual_inputs(project_root, opts)
required_files = {
    fullfile(project_root, 'HDR_fitting_2D_WholeFOV_impl.m')
    fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts', 'HDR_fitting_2D_WholeFOV_reasonable_v1.m')
    fullfile(project_root, 'PSF_Fitting_ValidationLab', 'scripts', 'HDR_fitting_2D_WholeFOV_candidate_prealign.m')
    fullfile(project_root, 'SimulatePSF', 'psf_multi.mat')
    fullfile(project_root, 'bads-1.1.3', 'bads.m')
    fullfile(project_root, 'Crop_circle_FreqFiltered', 'GT', 'GT_901_with_Block_proc.bmp')
};

for idx = 1:numel(required_files)
    if ~isfile(required_files{idx})
        error('Required file not found: %s', required_files{idx});
    end
end

input_folder = fullfile(project_root, 'Crop_circle_FreqFiltered');
file_list = dir(fullfile(input_folder, 'VisionTop_*.bmp'));
file_list = file_list(~[file_list.isdir]);
if isempty(file_list)
    error('No Whole-FOV input images found in: %s', input_folder);
end

if any(opts.subset_indices < 1) || any(opts.subset_indices > numel(file_list))
    error('subset_indices must be within 1..%d for the Whole-FOV input folder.', numel(file_list));
end

if numel(opts.subset_indices) > opts.grid_rows * opts.grid_cols
    error('grid_rows x grid_cols is too small for %d selected images.', numel(opts.subset_indices));
end

if strlength(string(opts.reuse_candidate_output_root)) > 0
    if ~isfile(fullfile(opts.reuse_candidate_output_root, 'batch_results.csv')) || ...
            ~isfile(fullfile(opts.reuse_candidate_output_root, 'PSF_fitted_2D_FOVstack.mat'))
        error('reuse_candidate_output_root is missing candidate fitting outputs: %s', opts.reuse_candidate_output_root);
    end
end

if ~exist(opts.output_root, 'dir')
    mkdir(opts.output_root);
end
end

function resolved_path = resolve_project_path(project_root, input_path)
input_path = char(input_path);
if isempty(input_path) || is_absolute_path(input_path)
    resolved_path = input_path;
else
    resolved_path = fullfile(project_root, input_path);
end
end

function tf = is_absolute_path(input_path)
tf = startsWith(input_path, filesep) || ...
    startsWith(input_path, '\\') || ...
    ~isempty(regexp(input_path, '^[A-Za-z]:[\\/]', 'once'));
end
