function make_mad_derivation_english()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
%MAKE_MAD_DERIVATION_ENGLISH Render the appendix derivation in English.

outputDir = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_tmp/oral_defense_english_20260727/assets_english/custom');
outputPath = fullfile(outputDir, 'mad_derivation_english.png');
if ~isfolder(outputDir), mkdir(outputDir); end

fig = figure('Color', 'w', 'Units', 'pixels', 'Position', [100, 100, 2400, 1450], ...
    'MenuBar', 'none', 'ToolBar', 'none', 'Resize', 'off');
ax = axes(fig, 'Units', 'normalized', 'Position', [0, 0, 1, 1]);
xlim(ax, [0, 1]); ylim(ax, [0, 1]); axis(ax, 'off'); hold(ax, 'on');

fontName = 'Times New Roman';
bodySize = 18;
formulaSize = 19;
leftX = 0.018;
centerX = 0.50;

addBody(ax, leftX, 0.970, 'The factor 1.4826 converts the median absolute deviation (MAD) to a scale comparable to the standard deviation under a normal distribution.', fontName, bodySize);
addBody(ax, leftX, 0.918, 'MAD is defined as:', fontName, bodySize);
addFormula(ax, centerX, 0.872, '$\mathrm{MAD}=\mathrm{median}_{j}\left|d_j-\mathrm{median}(d_j)\right|$', formulaSize);

addBody(ax, leftX, 0.816, 'Assume the data follow a normal distribution:', fontName, bodySize);
addFormula(ax, centerX, 0.770, '$X\sim\mathcal{N}(\mu,\sigma^2)$', formulaSize);

addBody(ax, leftX, 0.714, 'For a standard normal variable Z ~ N(0, 1), the median of |Z| satisfies:', fontName, bodySize);
addFormula(ax, centerX, 0.668, '$P\left(|Z|\leq a\right)=0.5$', formulaSize);

addBody(ax, leftX, 0.612, 'By symmetry of the normal distribution:', fontName, bodySize);
addFormula(ax, centerX, 0.566, '$P\left(|Z|\leq a\right)=2\Phi(a)-1$', formulaSize);

addBody(ax, leftX, 0.510, 'Therefore:', fontName, bodySize);
addFormula(ax, centerX, 0.468, '$2\Phi(a)-1=0.5$', formulaSize);
addFormula(ax, centerX, 0.426, '$\Phi(a)=0.75$', formulaSize);
addFormula(ax, centerX, 0.384, '$a=\Phi^{-1}(0.75)\approx0.67448975$', formulaSize);

addBody(ax, leftX, 0.328, 'Under a normal distribution:', fontName, bodySize);
addFormula(ax, centerX, 0.282, '$\mathrm{MAD}\approx0.67449\sigma$', formulaSize);

addBody(ax, leftX, 0.226, 'To convert MAD to a scale comparable with the standard deviation, divide by 0.67449:', fontName, bodySize);
addFormula(ax, centerX, 0.178, '$\sigma_{\mathrm{robust}}\approx\frac{\mathrm{MAD}}{0.67449}$', formulaSize);
addFormula(ax, centerX, 0.128, '$\frac{1}{0.67449}\approx1.4826$', formulaSize);

addBody(ax, leftX, 0.074, 'Thus, the nine-pillar displacement dispersion used here is:', fontName, bodySize);
addFormula(ax, centerX, 0.028, '$D_9=1.4826\,\mathrm{median}_{j}\left|d_j-\mathrm{median}(d_j)\right|$', formulaSize);

exportgraphics(fig, outputPath, 'Resolution', 150, 'BackgroundColor', 'white');
close(fig);
fprintf('%s\n', outputPath);
end

function addBody(ax, x, y, content, fontName, fontSize)
text(ax, x, y, content, 'Units', 'normalized', 'FontName', fontName, ...
    'FontSize', fontSize, 'FontWeight', 'normal', 'Interpreter', 'none', ...
    'HorizontalAlignment', 'left', 'VerticalAlignment', 'middle', 'Color', [0, 0, 0]);
end

function addFormula(ax, x, y, content, fontSize)
text(ax, x, y, content, 'Units', 'normalized', 'FontSize', fontSize, ...
    'FontWeight', 'normal', 'Interpreter', 'latex', ...
    'HorizontalAlignment', 'center', 'VerticalAlignment', 'middle', 'Color', [0, 0, 0]);
end
