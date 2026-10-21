%BUILD_THESIS_ARCHITECTURE_FIGURES Create clean English architecture diagrams.

scriptDir = fileparts(mfilename('fullpath'));
experimentDir = fileparts(scriptDir);
outDir = fullfile(experimentDir, 'results', 'thesis_v8_language_cleanup', 'architecture_figures');
if ~exist(outDir, 'dir'); mkdir(outDir); end

fontName = 'Times New Roman';
lineColor = [0.16 0.20 0.23];
blue = [0.76 0.86 0.93];
green = [0.82 0.90 0.78];
orange = [0.94 0.82 0.68];
gray = [0.90 0.91 0.92];
yellow = [0.96 0.90 0.63];

%% Figure 5-19, main network path.
fig = figure('Color', 'w', 'Units', 'inches', 'Position', [0.5 0.5 12 4.5], ...
    'Visible', 'off');
annotation(fig, 'textbox', [0.03 0.86 0.20 0.08], 'String', 'Single microscopy image', ...
    'EdgeColor', 'none', 'FontName', fontName, 'FontSize', 10, ...
    'HorizontalAlignment', 'center');
box(fig, [0.06 0.61 0.13 0.16], 'Input image', gray, lineColor, fontName, 10);
box(fig, [0.80 0.81 0.15 0.12], 'Fixed multi-position PSF prior', yellow, lineColor, fontName, 8);
box(fig, [0.25 0.61 0.13 0.16], 'Encoder\nBlock 1', blue, lineColor, fontName, 10);
box(fig, [0.25 0.35 0.13 0.16], 'Encoder\nBlock 2', blue, lineColor, fontName, 10);
box(fig, [0.25 0.09 0.13 0.16], 'Encoder\nBlock 3', blue, lineColor, fontName, 10);
box(fig, [0.44 0.09 0.13 0.16], 'Bottleneck', green, lineColor, fontName, 10);
box(fig, [0.62 0.09 0.14 0.16], 'Anti-aliased\nUpsampling 1', orange, lineColor, fontName, 9);
box(fig, [0.62 0.35 0.14 0.16], 'Anti-aliased\nUpsampling 2', orange, lineColor, fontName, 9);
box(fig, [0.62 0.61 0.14 0.16], 'Anti-aliased\nUpsampling 3', orange, lineColor, fontName, 9);
box(fig, [0.80 0.61 0.15 0.16], 'Decoder and\nPSF residual correction', green, lineColor, fontName, 9);
box(fig, [0.80 0.33 0.15 0.18], 'Boundary residual\nbranch', blue, lineColor, fontName, 9);
box(fig, [0.80 0.07 0.15 0.18], 'Input-referenced\nresidual output', gray, lineColor, fontName, 9);

arrow(fig, [0.19 0.25], [0.69 0.69], lineColor);
arrow(fig, [0.315 0.315], [0.61 0.51], lineColor);
arrow(fig, [0.315 0.315], [0.35 0.25], lineColor);
arrow(fig, [0.38 0.44], [0.17 0.17], lineColor);
arrow(fig, [0.57 0.62], [0.17 0.17], lineColor);
arrow(fig, [0.69 0.69], [0.25 0.35], lineColor);
arrow(fig, [0.69 0.69], [0.51 0.61], lineColor);
arrow(fig, [0.76 0.80], [0.69 0.69], lineColor);
arrow(fig, [0.875 0.875], [0.61 0.51], lineColor);
arrow(fig, [0.875 0.875], [0.33 0.25], lineColor);
arrow(fig, [0.875 0.875], [0.81 0.77], lineColor);
annotation(fig, 'textbox', [0.36 0.80 0.35 0.06], 'String', 'encoder-decoder skip connections are retained at matching scales', ...
    'EdgeColor', 'none', 'FontName', fontName, 'FontSize', 8, ...
    'HorizontalAlignment', 'center', 'Color', [0.25 0.25 0.25]);
annotation(fig, 'textbox', [0.80 0.94 0.15 0.05], 'String', 'same-size output', ...
    'EdgeColor', 'none', 'FontName', fontName, 'FontSize', 10, ...
    'HorizontalAlignment', 'center');

exportgraphics(fig, fullfile(outDir, 'figure_5_19_main.png'), 'Resolution', 300);
close(fig);

%% Figure 5-19, legend.
fig = figure('Color', 'w', 'Units', 'inches', 'Position', [0.5 0.5 12 4.1], ...
    'Visible', 'off');
legend_box(fig, 0.10, 0.69, blue, 'Convolution, normalization, and SiLU', lineColor, fontName);
legend_box(fig, 0.10, 0.53, green, 'Residual feature block', lineColor, fontName);
legend_box(fig, 0.10, 0.37, orange, 'Bilinear interpolation and low-pass filtering', lineColor, fontName);
legend_box(fig, 0.10, 0.21, yellow, 'Fixed optical prior', lineColor, fontName);
legend_box(fig, 0.55, 0.69, gray, 'Input-referenced residual output', lineColor, fontName);
annotation(fig, 'textbox', [0.55 0.42 0.36 0.18], ...
    'String', {'All feature enlargement uses bilinear interpolation, reflection padding,', ...
    'depthwise low-pass filtering, and convolution. The final image remains on', ...
    'the original sampling grid.'}, 'EdgeColor', 'none', 'FontName', fontName, ...
    'FontSize', 10, 'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle');
exportgraphics(fig, fullfile(outDir, 'figure_5_19_legend.png'), 'Resolution', 300);
close(fig);

%% Figure 5-20, spatially varying PSF fusion.
fig = figure('Color', 'w', 'Units', 'inches', 'Position', [0.5 0.5 12 5.65], ...
    'Visible', 'off');
box(fig, [0.04 0.42 0.13 0.16], 'Input feature', gray, lineColor, fontName, 11);
box(fig, [0.23 0.66 0.17 0.17], 'Candidate PSF bank\n(PSF 1 ... PSF K)', yellow, lineColor, fontName, 10);
box(fig, [0.23 0.37 0.17 0.17], 'Frequency-domain\nPSF responses', orange, lineColor, fontName, 10);
box(fig, [0.23 0.09 0.17 0.17], 'Global pooling and\nweight estimation', blue, lineColor, fontName, 10);
box(fig, [0.49 0.37 0.17 0.17], 'Weighted PSF\nresidual', green, lineColor, fontName, 10);
box(fig, [0.49 0.09 0.17 0.17], 'Softmax weights\n(sum = 1)', blue, lineColor, fontName, 10);
box(fig, [0.74 0.37 0.16 0.17], 'Residual addition\n(scale beta)', gray, lineColor, fontName, 10);
box(fig, [0.74 0.66 0.16 0.17], 'Fixed PSF prior\n(scale alpha)', yellow, lineColor, fontName, 10);
box(fig, [0.74 0.09 0.16 0.17], 'Output feature', gray, lineColor, fontName, 11);

arrow(fig, [0.17 0.23], [0.50 0.455], lineColor);
arrow(fig, [0.17 0.23], [0.48 0.18], lineColor);
arrow(fig, [0.315 0.315], [0.66 0.54], lineColor);
arrow(fig, [0.40 0.49], [0.455 0.455], lineColor);
arrow(fig, [0.40 0.49], [0.175 0.175], lineColor);
arrow(fig, [0.575 0.575], [0.26 0.37], lineColor);
arrow(fig, [0.66 0.74], [0.455 0.455], lineColor);
arrow(fig, [0.82 0.82], [0.66 0.54], lineColor);
arrow(fig, [0.82 0.82], [0.37 0.26], lineColor);
line(fig, [0.105 0.105], [0.42 0.04], lineColor);
line(fig, [0.105 0.82], [0.04 0.04], lineColor);
arrow(fig, [0.82 0.82], [0.04 0.09], lineColor);

annotation(fig, 'textbox', [0.25 0.90 0.50 0.06], ...
    'String', 'Weight estimation: global pooling, convolution, SiLU, temperature scaling, and softmax', ...
    'EdgeColor', 'none', 'FontName', fontName, 'FontSize', 9, ...
    'HorizontalAlignment', 'center');
annotation(fig, 'textbox', [0.32 0.01 0.22 0.05], ...
    'String', 'input residual path', ...
    'EdgeColor', 'none', 'BackgroundColor', 'w', 'FontName', fontName, 'FontSize', 9, ...
    'HorizontalAlignment', 'center');

exportgraphics(fig, fullfile(outDir, 'figure_5_20_psf_fusion.png'), 'Resolution', 300);
close(fig);

fprintf('Architecture figures written to %s\n', outDir);


function box(fig, position, label, faceColor, edgeColor, fontName, fontSize)
label = strrep(label, '\n', newline);
annotation(fig, 'textbox', position, 'String', label, 'FitBoxToText', 'off', ...
    'BackgroundColor', faceColor, 'EdgeColor', edgeColor, 'LineWidth', 1.0, ...
    'FontName', fontName, 'FontSize', fontSize, 'FontWeight', 'normal', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', ...
    'Interpreter', 'none');
end


function arrow(fig, x, y, color)
annotation(fig, 'arrow', x, y, 'Color', color, 'LineWidth', 1.1, ...
    'HeadLength', 7, 'HeadWidth', 7);
end


function line(fig, x, y, color)
annotation(fig, 'line', x, y, 'Color', color, 'LineWidth', 0.9, ...
    'LineStyle', '--');
end


function legend_box(fig, x, y, faceColor, label, edgeColor, fontName)
annotation(fig, 'rectangle', [x y 0.035 0.055], 'FaceColor', faceColor, ...
    'EdgeColor', edgeColor, 'LineWidth', 0.9);
annotation(fig, 'textbox', [x + 0.05 y - 0.003 0.34 0.07], 'String', label, ...
    'EdgeColor', 'none', 'FontName', fontName, 'FontSize', 10, ...
    'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle');
end
