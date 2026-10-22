function generate_v18_fig36_clean()
%GENERATE_V17_FIG36_ZH Redraw Figure 6-36 with Chinese labels.

tablePath = ['D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\' ...
    '04_V42_NEURAL_NETWORK_RESULTS\source_validation\wiener_baseline_20260715\' ...
    'supplementary_20x_cd\tables\20x_frame49_cd_summary.csv'];
outDir = 'D:\GMM_2_Final\PSF_Fitting\.codex_docx_work\v18\figures\wiener\figures';
if ~exist(outDir, 'dir'), mkdir(outDir); end

rows = readtable(tablePath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
caseOrder = ["raw", "wiener", "mosr"];
caseLabels = ["Raw", "Wiener", "MOSR"];
colors = [0.65 0.29 0.12; 0.80 0.48 0.00; 0.05 0.37 0.64];
values = zeros(1, numel(caseOrder));
for caseIndex = 1:numel(caseOrder)
    selected = rows(rows.case == caseOrder(caseIndex), :);
    assert(height(selected) == 1, 'Expected one summary row per method.');
    values(caseIndex) = selected.pooled_median_abs_error_nm;
end

fig = figure('Color', 'white', 'Position', [150 150 900 560]);
ax = axes(fig);
b = bar(ax, 1:numel(values), values, 0.60, 'FaceColor', 'flat', 'EdgeColor', 'none');
b.CData = colors;
grid(ax, 'on'); box(ax, 'off');
ax.YGrid = 'on'; ax.XGrid = 'off';
ax.GridColor = [0.84 0.84 0.84]; ax.GridAlpha = 0.65;
ax.FontName = 'Microsoft JhengHei'; ax.FontSize = 11; ax.LineWidth = 0.9;
xticks(ax, 1:numel(values)); xticklabels(ax, caseLabels);
ylabel(ax, '跨閾值 CD 絕對誤差中位數 (nm)');
ylim(ax, [0, max(values) * 1.30]);
title(ax, '20 倍非 PSF 校正影格之 CD 誤差', ...
    'FontWeight', 'normal', 'FontSize', 14);
subtitle(ax, '每種方法共 126 筆量測：九顆 pillar、七個閾值與兩種剖面', ...
    'FontSize', 10.5);
for caseIndex = 1:numel(values)
    text(ax, caseIndex, values(caseIndex) + max(values) * 0.045, ...
        sprintf('%.1f nm', values(caseIndex)), 'HorizontalAlignment', 'center', ...
        'FontName', 'Microsoft JhengHei', 'FontSize', 10.5);
end

cleanFigure(fig); exportgraphics(fig, fullfile(outDir, '19_20x_noncalibration_cd_error_summary.png'), ...
    'Resolution', 300, 'BackgroundColor', 'white');
savefig(fig, fullfile(outDir, '19_20x_noncalibration_cd_error_summary.fig'));
close(fig);
fprintf('Figure 6-36 written to %s\n', outDir);
end


function cleanFigure(fig)
% Keep only axes labels, legends, ticks and visual marks.  Explanatory text
% is deliberately moved to the Word caption.
axesList = findall(fig, 'Type', 'axes');
for k = 1:numel(axesList)
    ax = axesList(k);
    if ~isa(ax, 'matlab.graphics.axis.Axes')
        continue;
    end
    axtoolbar(ax, {});
    ax.Title.String = '';
    ax.Title.Visible = 'off';
    if isprop(ax, 'Subtitle')
        ax.Subtitle.String = '';
        ax.Subtitle.Visible = 'off';
    end
    keep = [ax.XLabel, ax.YLabel, ax.ZLabel];
    notes = findall(ax, 'Type', 'text');
    for n = 1:numel(notes)
        if ~any(notes(n) == keep)
            delete(notes(n));
        end
    end
    refs = findall(ax, 'Type', 'ConstantLine');
    for n = 1:numel(refs)
        if isprop(refs(n), 'Label')
            refs(n).Label = '';
        end
    end
end
end
