function audit_current_loss()
%AUDIT_CURRENT_LOSS Measure contributions of the existing fitter objective.
here = fileparts(mfilename('fullpath'));
run_root = fileparts(here);
addpath(fullfile(fileparts(fileparts(run_root)), 'SimulatePSF'));
gt = im2double(imread(fullfile(run_root, 'fit_input', 'GT', 'gt_sem_cd.bmp')));
mask = imread(fullfile(run_root, 'fit_input', 'loss_mask.bmp')) > 0;
fit = load(fullfile(run_root, 'fit_wide2', 'PSF_fitted_2D_FOVstack.mat'), 'psf_grid');
frames = [1 13 25];
rows = repmat(struct('frame', 0, 'intensity_loss', 0, 'gradient_loss', 0, ...
    'weighted_gradient_loss', 0, 'gradient_to_intensity_ratio', 0, ...
    'gradient_max_inside_mask', false, 'clipped_pixel_fraction_in_mask', 0), numel(frames), 1);
for idx = 1:numel(frames)
    frame = frames(idx);
    img = im2double(imread(fullfile(run_root, 'fit_input', sprintf('fit_input_%02d.bmp', frame))));
    psf = fit.psf_grid(:, :, 1, frame);
    predicted = conv2(gt, psf, 'same');
    image_gradient = imgradient(img);
    predicted_gradient = imgradient(predicted);
    normalized_image_gradient = normlz(image_gradient);
    normalized_predicted_gradient = normlz(predicted_gradient);
    intensity_loss = mean((img(mask) - predicted(mask)).^2);
    gradient_loss = mean((normalized_image_gradient(mask) - normalized_predicted_gradient(mask)).^2);
    [~, maximum_index] = max(image_gradient(:));
    rows(idx).frame = frame;
    rows(idx).intensity_loss = intensity_loss;
    rows(idx).gradient_loss = gradient_loss;
    rows(idx).weighted_gradient_loss = 8e4 * gradient_loss;
    rows(idx).gradient_to_intensity_ratio = 8e4 * gradient_loss / intensity_loss;
    rows(idx).gradient_max_inside_mask = mask(maximum_index);
    rows(idx).clipped_pixel_fraction_in_mask = mean(img(mask) >= 1);
end
table_data = struct2table(rows);
writetable(table_data, fullfile(here, 'current_loss_components.csv'));
disp(table_data);
end
