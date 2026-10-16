function output_psf = resample_centered_psf(input_psf, scale)
%RESAMPLE_CENTERED_PSF Resample a PSF while keeping its original canvas size.
arguments
    input_psf (:,:) double {mustBeNonnegative, mustBeFinite}
    scale (1,1) double {mustBePositive, mustBeFinite}
end

target_size = size(input_psf);
resized = imresize(input_psf, scale, 'bicubic');
resized = max(resized, 0);
output_psf = zeros(target_size, 'double');

[source_rows, target_rows] = centered_overlap(size(resized, 1), target_size(1));
[source_cols, target_cols] = centered_overlap(size(resized, 2), target_size(2));
output_psf(target_rows, target_cols) = resized(source_rows, source_cols);

mass = sum(output_psf, 'all');
if mass <= 0
    error('center9:EmptyResampledPsf', 'PSF resampling produced zero total energy.');
end
output_psf = output_psf / mass;
end

function [source_indices, target_indices] = centered_overlap(source_length, target_length)
copy_length = min(source_length, target_length);
source_start = floor((source_length - copy_length) / 2) + 1;
target_start = floor((target_length - copy_length) / 2) + 1;
source_indices = source_start:(source_start + copy_length - 1);
target_indices = target_start:(target_start + copy_length - 1);
end
