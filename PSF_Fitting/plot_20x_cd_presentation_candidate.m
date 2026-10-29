function plot_20x_cd_presentation_candidate()
% Plot the 20x counterpart of the bias-corrected 50x CD summary.

root = "Thesis_MOSR_Evidence/Final_Data_Figures" + ...
    "\12_V25_20X_CD_PRESENTATION_CANDIDATE_20260727";
figureDir = fullfile(root, "figures");
if ~isfolder(figureDir)
    mkdir(figureDir);
end

colors.Blue = [0.05 0.38 0.67];
colors.Orange = [0.82 0.42 0.12];
colors.Grid = [0.86 0.86 0.86];
colors.Text = [0.18 0.18 0.18];

data = readtable(fullfile(root, "presentation_bias_corrected_cd.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");

f = figure("Color", "white", "Units", "inches", ...
    "Position", [0.7 0.7 7.2 4.8], "Renderer", "painters");
ax = axes(f);
hold(ax, "on");
values = [data.shift_safe_nm, data.standard_nm];
b = bar(ax, values, "grouped", "BarWidth", 0.76);
b(1).FaceColor = colors.Blue;
b(1).EdgeColor = colors.Blue * 0.72;
b(2).FaceColor = colors.Orange;
b(2).EdgeColor = colors.Orange * 0.72;

upperLimit = ceil(max(values, [], "all") / 10) * 10 + 10;
labelOffset = upperLimit * 0.022;
for j = 1:2
    for i = 1:height(data)
        text(ax, b(j).XEndPoints(i), values(i, j) + labelOffset, ...
            sprintf("%.2f", values(i, j)), "HorizontalAlignment", "center", ...
            "FontName", "Times New Roman", "FontSize", 11.5, ...
            "Color", colors.Text);
    end
end

xticks(ax, 1:height(data));
xticklabels(ax, ["Median AE", "RMSE", "Maximum AE"]);
ylabel(ax, "Bias-corrected CD error (nm)");
ylim(ax, [0 upperLimit]);
legend(ax, b, ["Anti-aliased upsampling", "Standard upsampling"], ...
    "Location", "northoutside", "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 12.5);

ax.FontName = "Times New Roman";
ax.FontSize = 12.0;
ax.LineWidth = 1.15;
ax.TickDir = "out";
ax.Box = "off";
ax.XColor = colors.Text;
ax.YColor = colors.Text;
ax.YGrid = "on";
ax.XGrid = "off";
ax.GridColor = colors.Grid;
ax.GridAlpha = 1.0;
ax.Layer = "top";

outputBase = fullfile(figureDir, "01_20x_cd_bias_corrected_metrics");
drawnow;
exportgraphics(f, outputBase + ".png", "Resolution", 300, ...
    "BackgroundColor", "white");
exportgraphics(f, outputBase + ".pdf", "ContentType", "vector", ...
    "BackgroundColor", "white");
savefig(f, outputBase + ".fig");
close(f);
end
