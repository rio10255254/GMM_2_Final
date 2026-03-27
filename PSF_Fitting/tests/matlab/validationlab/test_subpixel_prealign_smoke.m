function test_subpixel_prealign_smoke()
test_dir = fileparts(mfilename('fullpath'));
project_root = fileparts(fileparts(fileparts(test_dir)));
lab_root = fullfile(project_root, 'PSF_Fitting_ValidationLab');
scripts_dir = fullfile(lab_root, 'scripts');

addpath(scripts_dir);

base = fspecial('gaussian', [65 65], 6);
shifted = vlab_translate_image(base, -0.5, 0.5);

prealign = struct();
prealign.search_radius = 1;
prealign.search_step = 0.5;
prealign.crop_rows = 9:57;
prealign.crop_cols = 9:57;
prealign.gt_grad_norm = normlz(imgradient(base));

align_info = vlab_prealign_image(shifted, prealign);

assert(abs(align_info.shift_y - 0.5) <= 0.26, 'Expected subpixel dy close to +0.5.');
assert(abs(align_info.shift_x + 0.5) <= 0.26, 'Expected subpixel dx close to -0.5.');
end
