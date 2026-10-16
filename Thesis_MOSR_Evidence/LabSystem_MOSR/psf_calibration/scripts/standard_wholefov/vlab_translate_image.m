% Copied for LabSystem_MOSR from
% D:/GMM_2_Final/PSF_Fitting/PSF_Fitting_ValidationLab/scripts/vlab_translate_image.m.
function shifted = vlab_translate_image(img, dy, dx)
[h, w] = size(img);
[x_grid, y_grid] = meshgrid(1:w, 1:h);

shifted = interp2(x_grid, y_grid, double(img), x_grid - dx, y_grid - dy, 'linear', 0);

if isa(img, 'single')
    shifted = single(shifted);
end
end
