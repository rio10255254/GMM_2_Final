function out = make_center9_psf_analysis_figures(write_figures, write_data)
% Generate thesis-ready PSF analysis figures using MATLAB only.
if nargin < 1, write_figures = true; end
if nargin < 2, write_data = true; end

opts = default_options();
labels = {'20x', '50x'};
items = cell(numel(labels), 1);
for k = 1:numel(labels)
    items{k} = analyze_case(load_case(opts, labels{k}));
end
data = [items{:}];
metrics = struct2table([data.metric]');
figure_paths = strings(0, 1);

if write_figures
    figure_paths = render_all(data, opts);
end
if write_data
    save_analysis_data(data, metrics, figure_paths, opts);
end
out = struct('metrics', metrics, 'figure_paths', figure_paths, 'data', data);
end

function opts = default_options()
root = fullfile('D:', 'GMM_2_Final');
package_root = fullfile(root, 'Thesis_MOSR_Evidence', 'Final_Data_Figures', ...
    '03_PSF_EXPERIMENT_RESULTS', '01_global_bads_fit');
opts.fit_root = fullfile(root, 'PSF_Fitting', 'output', ...
    'deconvolution_baseline_psf_20260715');
opts.figure_root = fullfile(package_root, 'figures', ...
    'center9_pillar_fit_20x_50x');
opts.source_root = fullfile(package_root, 'source_data', ...
    'center9_pillar_fit_20x_50x', 'psf_analysis');
opts.view_um = 3;
opts.freq_max = 1.2;
opts.dpi = 220;
opts.visible = 'off';
opts.typography = struct('title_pt', 14, 'subtitle_pt', 10, ...
    'axis_tick_pt', 9.5, 'axis_label_pt', 10.5, 'legend_pt', 9.5, ...
    'colorbar_tick_pt', 9, 'annotation_pt', 9);
end

function d = load_case(opts, label)
case_root = fullfile(opts.fit_root, label);
meta = jsondecode(fileread(fullfile(case_root, 'selected_frame.json')));
loaded = load(fullfile(case_root, 'fit_result', ...
    'PSF_fitted_2D_FOVstack.mat'), 'psf_grid');
input_root = fullfile(case_root, 'fit_input');
d.label = label;
d.object_pixel_um = double(meta.object_pixel_um);
d.psf = double(squeeze(loaded.psf_grid));
d.measured = read_gray(fullfile(input_root, 'fit_input.bmp'));
d.gt = read_gray(fullfile(input_root, 'GT', 'gt_sem_cd.bmp'));
d.mask = imread(fullfile(input_root, 'loss_mask.bmp')) > 0;
d.input_paths = struct('fit_result', fullfile(case_root, 'fit_result', ...
    'PSF_fitted_2D_FOVstack.mat'), 'metadata', fullfile(case_root, ...
    'selected_frame.json'), 'fit_input', fullfile(input_root, 'fit_input.bmp'), ...
    'ground_truth', fullfile(input_root, 'GT', 'gt_sem_cd.bmp'), ...
    'loss_mask', fullfile(input_root, 'loss_mask.bmp'));
end

function image = read_gray(path)
image = im2double(imread(path));
if size(image, 3) > 1, image = rgb2gray(image); end
end

function d = analyze_case(d)
P = d.psf;
Pn = P / max(P(:));
[~, peak_index] = max(P(:));
[peak_y, peak_x] = ind2sub(size(P), peak_index);
dx = d.object_pixel_um;
x_profile_um = ((1:size(P, 2)) - peak_x) * dx;
y_profile_um = ((1:size(P, 1)) - peak_y) * dx;
profile_x = Pn(peak_y, :);
profile_y = Pn(:, peak_x)';
[fwhm_x, left_x, right_x] = profile_fwhm(profile_x, x_profile_um);
[fwhm_y, left_y, right_y] = profile_fwhm(profile_y, y_profile_um);

W = P / sum(P(:));
[X, Y] = meshgrid(1:size(P, 2), 1:size(P, 1));
centroid_x = sum(X(:) .* W(:));
centroid_y = sum(Y(:) .* W(:));
x_image_um = ((1:size(P, 2)) - centroid_x) * dx;
y_image_um = ((1:size(P, 1)) - centroid_y) * dx;
xx = (X - centroid_x) * dx;
yy = (Y - centroid_y) * dx;
covariance = [sum(W(:).*xx(:).^2), sum(W(:).*xx(:).*yy(:)); ...
    sum(W(:).*xx(:).*yy(:)), sum(W(:).*yy(:).^2)];
eigenvalues = sort(eig(covariance), 'descend');
axis_ratio = sqrt(eigenvalues(1) / eigenvalues(2));

[radius_um, encircled] = encircled_energy(W, xx, yy);
r50 = threshold_radius(radius_um, encircled, 0.5);
r80 = threshold_radius(radius_um, encircled, 0.8);
[frequency, mtf_x, mtf_y] = mtf_profiles(W, dx);
mtf50_x = threshold_frequency(frequency, mtf_x, 0.5);
mtf50_y = threshold_frequency(frequency, mtf_y, 0.5);
mtf10_x = threshold_frequency(frequency, mtf_x, 0.1);
mtf10_y = threshold_frequency(frequency, mtf_y, 0.1);

predicted = conv2(d.gt, P, 'same');
residual = d.measured - predicted;
measured_values = d.measured(d.mask);
predicted_values = predicted(d.mask);
fit_correlation = scalar_correlation(measured_values, predicted_values);
fit_nrmse = sqrt(mean((measured_values-predicted_values).^2)) / ...
    max(max(measured_values)-min(measured_values), eps);
sorted_abs = sort(abs(residual(d.mask)));
residual_limit = max(sorted_abs(max(1, ceil(0.99*numel(sorted_abs)))), eps);

d.shape = struct('normalized', Pn, 'peak_xy', [peak_x, peak_y], ...
    'centroid_xy', [centroid_x, centroid_y], 'x_image_um', x_image_um, ...
    'y_image_um', y_image_um, 'x_profile_um', x_profile_um, ...
    'y_profile_um', y_profile_um, 'profile_x', profile_x, ...
    'profile_y', profile_y, 'cross_x_um', [left_x, right_x], ...
    'cross_y_um', [left_y, right_y]);
d.energy = struct('radius_um', radius_um, 'fraction', encircled);
d.mtf = struct('frequency_cyc_per_um', frequency, 'x', mtf_x, 'y', mtf_y);
d.fit = struct('predicted', predicted, 'residual', residual, ...
    'display_limit', residual_limit);
d.metric = struct('magnification', string(d.label), ...
    'object_pixel_um', dx, 'fwhm_x_um', fwhm_x, 'fwhm_y_um', fwhm_y, ...
    'fwhm_mean_um', mean([fwhm_x, fwhm_y]), ...
    'second_moment_axis_ratio', axis_ratio, 'r50_um', r50, 'r80_um', r80, ...
    'mtf50_x_cyc_per_um', mtf50_x, 'mtf50_y_cyc_per_um', mtf50_y, ...
    'mtf50_mean_cyc_per_um', mean([mtf50_x, mtf50_y]), ...
    'mtf10_x_cyc_per_um', mtf10_x, 'mtf10_y_cyc_per_um', mtf10_y, ...
    'mtf10_mean_cyc_per_um', mean([mtf10_x, mtf10_y]), ...
    'fit_correlation', fit_correlation, 'fit_nrmse', fit_nrmse, ...
    'psf_peak', max(P(:)), 'psf_sum', sum(P(:)));
end

function [width, left, right] = profile_fwhm(profile, coordinate)
profile = double(profile(:))' / max(profile);
coordinate = double(coordinate(:))';
[~, peak] = max(profile);
left_below = find(profile(1:peak) < 0.5, 1, 'last');
right_below = peak-1 + find(profile(peak:end) < 0.5, 1, 'first');
if isempty(left_below) || isempty(right_below)
    width = NaN; left = NaN; right = NaN; return
end
left = interpolate_level(coordinate(left_below:left_below+1), ...
    profile(left_below:left_below+1), 0.5);
right = interpolate_level(coordinate(right_below-1:right_below), ...
    profile(right_below-1:right_below), 0.5);
width = right - left;
end

function value = interpolate_level(x, y, level)
value = x(1) + (level-y(1)) * (x(2)-x(1)) / (y(2)-y(1));
end

function [radius, fraction] = encircled_energy(W, xx, yy)
r = hypot(xx, yy);
[sorted_radius, order] = sort(r(:));
sorted_weight = W(order);
[radius, ~, group] = unique(sorted_radius);
ring_weight = accumarray(group, sorted_weight);
fraction = cumsum(ring_weight);
fraction = fraction / fraction(end);
end

function radius = threshold_radius(r, fraction, level)
radius = interp1(fraction, r, level, 'linear');
end

function [frequency, mtf_x, mtf_y] = mtf_profiles(W, dx)
otf = abs(fftshift(fft2(ifftshift(W))));
center_y = floor(size(W, 1)/2) + 1;
center_x = floor(size(W, 2)/2) + 1;
otf = otf / otf(center_y, center_x);
fx = (-floor(size(W,2)/2):ceil(size(W,2)/2)-1) / (size(W,2)*dx);
frequency = fx(center_x:end);
mtf_x = otf(center_y, center_x:end);
mtf_y = otf(center_y:end, center_x)';
end

function frequency = threshold_frequency(x, y, level)
index = find(y <= level, 1, 'first');
if isempty(index) || index == 1, frequency = NaN; return, end
frequency = interpolate_level(x(index-1:index), y(index-1:index), level);
end

function value = scalar_correlation(a, b)
a = a(:)-mean(a(:)); b = b(:)-mean(b(:));
value = sum(a.*b) / sqrt(sum(a.^2)*sum(b.^2));
end

function paths = render_all(data, opts)
paths = strings(0, 1);
for k = 1:numel(data)
    output_dir = fullfile(opts.figure_root, data(k).label);
    if ~isfolder(output_dir), mkdir(output_dir); end
    paths(end+1) = plot_heatmap(data(k), opts, fullfile(output_dir, ...
        '15_normalized_fitted_psf_halfmax_contour.png')); %#ok<AGROW>
    paths(end+1) = plot_profiles(data(k), opts, fullfile(output_dir, ...
        '16_fitted_psf_center_profiles_fwhm.png')); %#ok<AGROW>
    paths(end+1) = plot_energy(data(k), opts, fullfile(output_dir, ...
        '17_fitted_psf_encircled_energy.png')); %#ok<AGROW>
    paths(end+1) = plot_mtf(data(k), opts, fullfile(output_dir, ...
        '18_fitted_psf_mtf.png')); %#ok<AGROW>
    paths(end+1) = plot_residual(data(k), opts, fullfile(output_dir, ...
        '19_forward_fit_residual.png')); %#ok<AGROW>
end
comparison_dir = fullfile(opts.figure_root, 'comparison');
if ~isfolder(comparison_dir), mkdir(comparison_dir); end
paths(end+1) = plot_profile_comparison(data, opts, fullfile(comparison_dir, ...
    '01_center_profile_comparison.png'));
paths(end+1) = plot_energy_comparison(data, opts, fullfile(comparison_dir, ...
    '02_encircled_energy_comparison.png'));
paths(end+1) = plot_mtf_comparison(data, opts, fullfile(comparison_dir, ...
    '03_mtf_comparison.png'));
end

function path = plot_heatmap(d, opts, path)
[fig, ax] = new_figure(opts);
imagesc(ax, d.shape.x_image_um, d.shape.y_image_um, d.shape.normalized);
set(ax, 'YDir', 'normal'); axis(ax, 'image'); hold(ax, 'on');
contour(ax, d.shape.x_image_um, d.shape.y_image_um, d.shape.normalized, ...
    [0.5, 0.5], 'k-', 'LineWidth', 3.2);
contour(ax, d.shape.x_image_um, d.shape.y_image_um, d.shape.normalized, ...
    [0.5, 0.5], 'w-', 'LineWidth', 1.6);
peak_um = (d.shape.peak_xy-d.shape.centroid_xy)*d.object_pixel_um;
plot(ax, peak_um(1), peak_um(2), 'wo', 'MarkerSize', 8, 'LineWidth', 1.5);
xlim(ax, [-opts.view_um, opts.view_um]); ylim(ax, [-opts.view_um, opts.view_um]);
clim(ax, [0, 1]); colormap(ax, parula(256));
cb = colorbar(ax); cb.Label.String = 'Normalized intensity';
xlabel(ax, 'Object-space x (µm)'); ylabel(ax, 'Object-space y (µm)');
title(ax, sprintf('%s fitted PSF', display_label(d.label)));
subtitle(ax, sprintf('Peak normalized; 50%% contour; sampling %.4f µm/pixel', ...
    d.object_pixel_um));
finish_figure(fig, ax, path, opts); close(fig);
end

function path = plot_profiles(d, opts, path)
[fig, ax] = new_figure(opts); hold(ax, 'on');
c = palette();
plot(ax, d.shape.x_profile_um, d.shape.profile_x, '-', ...
    'Color', c.blue, 'LineWidth', 2.4, 'DisplayName', 'Horizontal profile');
plot(ax, d.shape.y_profile_um, d.shape.profile_y, '--', ...
    'Color', c.orange, 'LineWidth', 2.4, 'DisplayName', 'Vertical profile');
yline(ax, 0.5, ':', 'Half maximum', 'Color', [0.25,0.25,0.25], ...
    'LineWidth', 1.4, 'LabelHorizontalAlignment', 'left', ...
    'HandleVisibility', 'off');
scatter(ax, d.shape.cross_x_um, [0.5,0.5], 55, c.blue, 'o', 'filled', ...
    'HandleVisibility', 'off');
scatter(ax, d.shape.cross_y_um, [0.5,0.5], 70, c.orange, 'd', 'filled', ...
    'HandleVisibility', 'off');
xlim(ax, [-opts.view_um, opts.view_um]); ylim(ax, [0, 1.05]);
xlabel(ax, 'Distance from PSF peak (µm)'); ylabel(ax, 'Normalized intensity');
title(ax, sprintf('%s central PSF profiles and FWHM', display_label(d.label)));
subtitle(ax, sprintf('FWHM_x = %.3f µm; FWHM_y = %.3f µm', ...
    d.metric.fwhm_x_um, d.metric.fwhm_y_um));
legend(ax, 'Location', 'northeast', 'Box', 'off'); grid(ax, 'on');
finish_figure(fig, ax, path, opts); close(fig);
end

function path = plot_energy(d, opts, path)
[fig, ax] = new_figure(opts); hold(ax, 'on'); c = palette();
plot(ax, d.energy.radius_um, d.energy.fraction, '-', ...
    'Color', c.blue, 'LineWidth', 2.6);
yline(ax, 0.5, ':', '50%', 'Color', [0.35,0.35,0.35], 'HandleVisibility', 'off');
yline(ax, 0.8, ':', '80%', 'Color', [0.35,0.35,0.35], 'HandleVisibility', 'off');
xline(ax, d.metric.r50_um, '--', 'Color', c.blue, 'LineWidth', 1.5);
xline(ax, d.metric.r80_um, '-.', 'Color', c.orange, 'LineWidth', 1.5);
scatter(ax, [d.metric.r50_um,d.metric.r80_um], [0.5,0.8], 65, ...
    [c.blue;c.orange], 'filled');
xlim(ax, [0, opts.view_um]); ylim(ax, [0, 1.02]); grid(ax, 'on');
xlabel(ax, 'Radius from PSF centroid (µm)'); ylabel(ax, 'Encircled energy fraction');
title(ax, sprintf('%s fitted-PSF encircled energy', display_label(d.label)));
subtitle(ax, sprintf('r50 = %.3f µm; r80 = %.3f µm', ...
    d.metric.r50_um, d.metric.r80_um));
finish_figure(fig, ax, path, opts); close(fig);
end

function path = plot_mtf(d, opts, path)
[fig, ax] = new_figure(opts); hold(ax, 'on'); c = palette();
plot(ax, d.mtf.frequency_cyc_per_um, d.mtf.x, '-', ...
    'Color', c.blue, 'LineWidth', 2.4, 'DisplayName', 'Horizontal MTF');
plot(ax, d.mtf.frequency_cyc_per_um, d.mtf.y, '--', ...
    'Color', c.orange, 'LineWidth', 2.4, 'DisplayName', 'Vertical MTF');
yline(ax, 0.5, ':', 'MTF50', 'Color', [0.3,0.3,0.3], 'HandleVisibility', 'off');
yline(ax, 0.1, ':', 'MTF10', 'Color', [0.3,0.3,0.3], 'HandleVisibility', 'off');
xlim(ax, [0, opts.freq_max]); ylim(ax, [0, 1.02]); grid(ax, 'on');
xlabel(ax, 'Spatial frequency (cycles/µm)'); ylabel(ax, 'Normalized MTF');
title(ax, sprintf('%s fitted-PSF modulation transfer function', ...
    display_label(d.label)));
subtitle(ax, sprintf('Mean MTF50 = %.3f cycles/µm; mean MTF10 = %.3f cycles/µm', ...
    d.metric.mtf50_mean_cyc_per_um, d.metric.mtf10_mean_cyc_per_um));
legend(ax, 'Location', 'northeast', 'Box', 'off');
finish_figure(fig, ax, path, opts); close(fig);
end

function path = plot_residual(d, opts, path)
[fig, ax] = new_figure(opts);
x = ((1:size(d.fit.residual,2))-(size(d.fit.residual,2)+1)/2)*d.object_pixel_um;
y = ((1:size(d.fit.residual,1))-(size(d.fit.residual,1)+1)/2)*d.object_pixel_um;
h = imagesc(ax, x, y, d.fit.residual); set(ax, 'YDir', 'normal');
set(h, 'AlphaData', 0.15+0.85*double(d.mask)); hold(ax, 'on');
contour(ax, x, y, double(d.mask), [0.5,0.5], 'Color', [0.15,0.15,0.15], ...
    'LineWidth', 0.9); axis(ax, 'image');
clim(ax, [-d.fit.display_limit, d.fit.display_limit]);
colormap(ax, diverging_map(256)); cb = colorbar(ax);
cb.Label.String = 'Captured - forward reconstruction';
xlabel(ax, 'Object-space x (µm)'); ylabel(ax, 'Object-space y (µm)');
title(ax, sprintf('%s forward-fit residual', display_label(d.label)));
subtitle(ax, sprintf('Fit-mask correlation = %.3f; normalized RMSE = %.3f', ...
    d.metric.fit_correlation, d.metric.fit_nrmse));
finish_figure(fig, ax, path, opts); close(fig);
end

function path = plot_profile_comparison(d, opts, path)
[fig, ax] = new_figure(opts); hold(ax, 'on'); c = palette();
x = linspace(-opts.view_um, opts.view_um, 1201);
p20 = mean_cross_profile(d(1), x); p50 = mean_cross_profile(d(2), x);
plot(ax, x, p20, '-', 'Color', c.blue, 'LineWidth', 2.5, ...
    'DisplayName', '20x mean cross-profile');
plot(ax, x, p50, '--', 'Color', c.orange, 'LineWidth', 2.5, ...
    'DisplayName', '50x mean cross-profile');
yline(ax, 0.5, ':', 'Half maximum', 'Color', [0.3,0.3,0.3], ...
    'HandleVisibility', 'off');
xlim(ax, [-opts.view_um, opts.view_um]); ylim(ax, [0, 1.05]); grid(ax, 'on');
xlabel(ax, 'Distance from PSF peak (µm)'); ylabel(ax, 'Normalized intensity');
title(ax, 'Central fitted-PSF profile comparison');
subtitle(ax, sprintf('Mean FWHM: 20x %.3f µm; 50x %.3f µm', ...
    d(1).metric.fwhm_mean_um, d(2).metric.fwhm_mean_um));
legend(ax, 'Location', 'northeast', 'Box', 'off');
finish_figure(fig, ax, path, opts); close(fig);
end

function profile = mean_cross_profile(d, x)
px = interp1(d.shape.x_profile_um, d.shape.profile_x, x, 'linear', NaN);
py = interp1(d.shape.y_profile_um, d.shape.profile_y, x, 'linear', NaN);
profile = mean([px;py], 1, 'omitnan');
end

function path = plot_energy_comparison(d, opts, path)
[fig, ax] = new_figure(opts); hold(ax, 'on'); c = palette();
plot(ax, d(1).energy.radius_um, d(1).energy.fraction, '-', ...
    'Color', c.blue, 'LineWidth', 2.5, 'DisplayName', '20x');
plot(ax, d(2).energy.radius_um, d(2).energy.fraction, '--', ...
    'Color', c.orange, 'LineWidth', 2.5, 'DisplayName', '50x');
yline(ax, 0.8, ':', '80%', 'Color', [0.3,0.3,0.3], 'HandleVisibility', 'off');
xlim(ax, [0, opts.view_um]); ylim(ax, [0, 1.02]); grid(ax, 'on');
xlabel(ax, 'Radius from PSF centroid (µm)'); ylabel(ax, 'Encircled energy fraction');
title(ax, 'Fitted-PSF encircled-energy comparison');
subtitle(ax, sprintf('r80: 20x %.3f µm; 50x %.3f µm', ...
    d(1).metric.r80_um, d(2).metric.r80_um));
legend(ax, 'Location', 'southeast', 'Box', 'off');
finish_figure(fig, ax, path, opts); close(fig);
end

function path = plot_mtf_comparison(d, opts, path)
[fig, ax] = new_figure(opts); hold(ax, 'on'); c = palette();
f = linspace(0, opts.freq_max, 1201);
m20 = mean_mtf(d(1), f); m50 = mean_mtf(d(2), f);
plot(ax, f, m20, '-', 'Color', c.blue, 'LineWidth', 2.5, ...
    'DisplayName', '20x mean x-y MTF');
plot(ax, f, m50, '--', 'Color', c.orange, 'LineWidth', 2.5, ...
    'DisplayName', '50x mean x-y MTF');
yline(ax, 0.5, ':', 'MTF50', 'Color', [0.3,0.3,0.3], 'HandleVisibility', 'off');
yline(ax, 0.1, ':', 'MTF10', 'Color', [0.3,0.3,0.3], 'HandleVisibility', 'off');
xlim(ax, [0, opts.freq_max]); ylim(ax, [0, 1.02]); grid(ax, 'on');
xlabel(ax, 'Spatial frequency (cycles/µm)'); ylabel(ax, 'Normalized MTF');
title(ax, 'Fitted-PSF MTF comparison');
subtitle(ax, sprintf('Mean MTF50: 20x %.3f; 50x %.3f cycles/µm', ...
    d(1).metric.mtf50_mean_cyc_per_um, d(2).metric.mtf50_mean_cyc_per_um));
legend(ax, 'Location', 'northeast', 'Box', 'off');
finish_figure(fig, ax, path, opts); close(fig);
end

function value = mean_mtf(d, frequency)
x = interp1(d.mtf.frequency_cyc_per_um, d.mtf.x, frequency, 'linear', NaN);
y = interp1(d.mtf.frequency_cyc_per_um, d.mtf.y, frequency, 'linear', NaN);
value = mean([x;y], 1, 'omitnan');
end

function [fig, ax] = new_figure(opts)
fig = figure('Visible', opts.visible, 'Color', 'w', 'Units', 'inches', ...
    'Position', [1,1,7.4,5.7]);
ax = axes(fig); hold(ax, 'on'); box(ax, 'on');
end

function finish_figure(fig, ax, path, opts)
style = opts.typography;
graphics = findall(fig);
for k = 1:numel(graphics)
    if isprop(graphics(k), 'FontName')
        set(graphics(k), 'FontName', 'Arial');
    end
    if isprop(graphics(k), 'FontSize')
        set(graphics(k), 'FontSize', style.annotation_pt);
    end
end
set(ax, 'FontName', 'Arial', 'FontSize', style.axis_tick_pt, 'LineWidth', 1.1, ...
    'TickDir', 'out', 'Layer', 'top');
set(get(ax, 'Title'), 'FontName', 'Arial', 'FontSize', style.title_pt, ...
    'FontWeight', 'normal');
if isprop(ax, 'Subtitle') && isgraphics(ax.Subtitle)
    set(ax.Subtitle, 'FontName', 'Arial', 'FontSize', style.subtitle_pt, ...
        'FontWeight', 'normal');
end
set(ax.XLabel, 'FontName', 'Arial', 'FontSize', style.axis_label_pt);
set(ax.YLabel, 'FontName', 'Arial', 'FontSize', style.axis_label_pt);
legends = findall(fig, 'Type', 'Legend');
set(legends, 'FontName', 'Arial', 'FontSize', style.legend_pt);
colorbars = findall(fig, 'Type', 'ColorBar');
for k = 1:numel(colorbars)
    set(colorbars(k), 'FontName', 'Arial', 'FontSize', style.colorbar_tick_pt);
    if isgraphics(colorbars(k).Label)
        set(colorbars(k).Label, 'FontName', 'Arial', ...
            'FontSize', style.axis_label_pt);
    end
end
exportgraphics(fig, path, 'Resolution', opts.dpi, 'BackgroundColor', 'white');
end

function label = display_label(raw)
label = strrep(char(raw), 'x', '×');
end

function c = palette()
c.blue = [0.00,0.35,0.67]; c.orange = [0.85,0.33,0.10];
end

function map = diverging_map(n)
blue = [0.10,0.35,0.65]; white = [1,1,1]; orange = [0.85,0.28,0.08];
t = linspace(0,1,ceil(n/2))';
lower = blue.*(1-t)+white.*t;
t = linspace(0,1,floor(n/2)+1)';
upper = white.*(1-t)+orange.*t;
map = [lower;upper(2:end,:)];
end

function save_analysis_data(data, metrics, figure_paths, opts)
if ~isfolder(opts.source_root), mkdir(opts.source_root); end
metrics_path = fullfile(opts.source_root, 'psf_analysis_metrics.csv');
data_path = fullfile(opts.source_root, 'psf_analysis_data.mat');
manifest_path = fullfile(opts.source_root, 'psf_analysis_manifest.json');
writetable(metrics, metrics_path);
analysis = compact_analysis(data); %#ok<NASGU>
save(data_path, 'analysis', 'metrics', 'figure_paths', '-v7');
manifest = build_manifest(data, figure_paths, opts, metrics_path, data_path);
file_id = fopen(manifest_path, 'w');
cleanup = onCleanup(@() fclose(file_id)); %#ok<NASGU>
fwrite(file_id, jsonencode(manifest, PrettyPrint=true), 'char');
end

function analysis = compact_analysis(data)
for k = numel(data):-1:1
    analysis(k).magnification = data(k).label;
    analysis(k).object_pixel_um = data(k).object_pixel_um;
    analysis(k).shape = data(k).shape;
    analysis(k).energy = data(k).energy;
    analysis(k).mtf = data(k).mtf;
    analysis(k).metric = data(k).metric;
    analysis(k).input_paths = data(k).input_paths;
end
end

function manifest = build_manifest(data, paths, opts, metrics_path, data_path)
manifest.generator = 'MATLAB';
manifest.generator_function = mfilename;
manifest.coordinate_space = 'object space';
manifest.heatmap_physical_limits_um = [-opts.view_um, opts.view_um];
manifest.heatmap_color_limits = [0, 1];
manifest.typography = opts.typography;
manifest.psf_shape_normalization = 'divide by fitted PSF peak';
manifest.fwhm_method = ['linear interpolation of the two 50 percent crossings ', ...
    'around the central peak on horizontal and vertical profiles'];
manifest.encircled_energy_normalization = ...
    'divide by total fitted PSF energy over the full 101 x 101 array';
manifest.mtf_normalization = 'OTF magnitude divided by its zero-frequency value';
manifest.residual_definition = 'fit input minus ground-truth forward convolution';
manifest.figure_count = numel(paths);
manifest.figure_paths = cellstr(paths);
manifest.metrics_path = metrics_path;
manifest.numeric_data_path = data_path;
for k = 1:numel(data)
    manifest.inputs.(['case_',data(k).label]) = data(k).input_paths;
end
end
