function configs = vlab_get_experiment_configs(root_dir, varargin)
parser = inputParser;
parser.addRequired('root_dir', @(x) ischar(x) || isstring(x));
parser.addParameter('profile_name', 'subset4', @(x) ischar(x) || isstring(x));
parser.addParameter('subset_indices', [1 56 60 100], @(x) isnumeric(x) && ~isempty(x));
parser.addParameter('output_root', fullfile(char(root_dir), 'outputs'), @(x) ischar(x) || isstring(x));
parser.addParameter('include_optional_experiment', true, @(x) islogical(x) || isnumeric(x));
parser.addParameter('warm_start', true, @(x) islogical(x) || isnumeric(x));
parser.parse(root_dir, varargin{:});

root_dir = char(parser.Results.root_dir);
output_root = char(parser.Results.output_root);
profile_name = string(parser.Results.profile_name);
subset_indices = unique(parser.Results.subset_indices(:)', 'stable');
warm_start = logical(parser.Results.warm_start);
include_optional = logical(parser.Results.include_optional_experiment);

switch profile_name
    case "subset4"
        experiment_prefix = "subset";
    case "rep16"
        subset_indices = [1 4 6 10 31 34 36 40 51 54 56 60 91 94 96 100];
        experiment_prefix = "rep16";
    otherwise
        error('Unsupported profile_name: %s', profile_name);
end

configs = struct( ...
    'name', {}, ...
    'subset_indices', {}, ...
    'warm_start', {}, ...
    'pre_alignment', {}, ...
    'prealign_step', {}, ...
    'lock_tilt', {}, ...
    'output_dir', {}, ...
    'lab_root', {}, ...
    'profile_name', {});

switch experiment_prefix
    case "subset"
        configs(end + 1) = make_config('baseline_subset', subset_indices, warm_start, false, 1.0, true, output_root, profile_name); %#ok<AGROW>
        configs(end + 1) = make_config('alignment_subset', subset_indices, warm_start, true, 1.0, true, output_root, profile_name); %#ok<AGROW>
        configs(end + 1) = make_config('tilt_subset', subset_indices, warm_start, false, 1.0, false, output_root, profile_name); %#ok<AGROW>
        if include_optional
            configs(end + 1) = make_config('alignment_tilt_subset', subset_indices, warm_start, true, 1.0, false, output_root, profile_name); %#ok<AGROW>
        end
    case "rep16"
        configs(end + 1) = make_config('baseline_rep16', subset_indices, warm_start, false, 1.0, true, output_root, profile_name); %#ok<AGROW>
        configs(end + 1) = make_config('alignment_rep16', subset_indices, warm_start, true, 1.0, true, output_root, profile_name); %#ok<AGROW>
        configs(end + 1) = make_config('alignment_subpixel_rep16', subset_indices, warm_start, true, 0.5, true, output_root, profile_name); %#ok<AGROW>
        configs(end + 1) = make_config('alignment_quarter_rep16', subset_indices, warm_start, true, 0.25, true, output_root, profile_name); %#ok<AGROW>
        configs(end + 1) = make_config('alignment_tilt_rep16', subset_indices, warm_start, true, 1.0, false, output_root, profile_name); %#ok<AGROW>
end

    function config = make_config(name, subset, warm_start_flag, prealign_flag, prealign_step, lock_tilt_flag, output_root_dir, profile)
        config = struct( ...
            'name', name, ...
            'subset_indices', subset, ...
            'warm_start', logical(warm_start_flag), ...
            'pre_alignment', logical(prealign_flag), ...
            'prealign_step', prealign_step, ...
            'lock_tilt', logical(lock_tilt_flag), ...
            'output_dir', fullfile(output_root_dir, 'experiments', name), ...
            'lab_root', root_dir, ...
            'profile_name', char(profile));
    end
end
