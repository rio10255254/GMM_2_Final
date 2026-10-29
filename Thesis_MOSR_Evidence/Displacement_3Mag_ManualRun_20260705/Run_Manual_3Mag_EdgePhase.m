function Run_Manual_3Mag_EdgePhase(varargin)
    PROJECT_ROOT = fileparts(fileparts(fileparts(mfilename('fullpath'))));
% Open this file in MATLAB and press Run.
% Results are written into this same thesis evidence folder by default.

thisDir = fileparts(mfilename('fullpath'));
toolDir = fullfile(PROJECT_ROOT, 'Tools/Displacement_Algorithms');

addpath(toolDir);
addpath(fullfile(toolDir, 'phase_correlation_dft', 'legacy_matlab'));

args = varargin;
if ~hasOutputRoot(args)
    args = [{'outputRoot', thisDir}, args];
end

Run_Thesis_3Mag_EdgePhase_SelectROI(args{:});
end

function tf = hasOutputRoot(args)
tf = false;
for idx = 1:2:numel(args)
    if ischar(args{idx}) || isstring(args{idx})
        if strcmpi(char(args{idx}), 'outputRoot')
            
            tf = true;
            return;
        end
    end
end
end
