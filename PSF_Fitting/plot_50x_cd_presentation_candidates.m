function plot_50x_cd_presentation_candidates()
% Candidate English figures for a fair presentation of the 50x CD ablation.

root = "Thesis_MOSR_Evidence/Final_Data_Figures/10_V23_50X_CD_PRESENTATION_CANDIDATES_20260727";
figureDir = fullfile(root, "figures");
if ~isfolder(figureDir)
    mkdir(figureDir);
end

colors.Blue = [0.05 0.38 0.67];
colors.Orange = [0.82 0.42 0.12];
colors.Gray = [0.42 0.42 0.42];
colors.Grid = [0.86 0.86 0.86];
colors.Text = [0.18 0.18 0.18];

locked = readtable(fullfile(root, "presentation_locked_cd.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
plot_locked_with_raw(locked, colors, ...
    fullfile(figureDir, "01_50x_cd_locked_protocol_with_raw"));

corrected = readtable(fullfile(root, "presentation_bias_corrected_cd.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
plot_corrected_metrics(corrected, colors, ...
    fullfile(figureDir, "02_50x_cd_bias_corrected_metrics"));

sensitivity = readtable(fullfile(root, "presentation_smoothing_sensitivity.csv"), ...
    "VariableNamingRule", "preserve", "TextType", "string");
plot_sensitivity(sensitivity, colors, ...
    fullfile(figureDir, "03_50x_cd_bias_correction_sensitivity"));
end


function plot_locked_with_raw(data, colors, outputBase)
f = new_figure(7.2, 4.8);
ax = axes(f);
hold(ax, "on");
values = data.median_abs_error_nm;
b = barh(ax, values, 0.62, "FaceColor", "flat", "LineWidth", 1.0);
b.CData = [colors.Gray; colors.Blue; colors.Orange];
b.EdgeColor = [0.25 0.25 0.25];
yticks(ax, 1:3);
yticklabels(ax, ["Raw", "Anti-aliased upsampling", "Standard upsampling"]);
xlabel(ax, "Median absolute CD error (nm)");
xlim(ax, [0 112]);
for i = 1:3
    text(ax, values(i) + 2.0, i, sprintf("%.2f", values(i)), ...
        "HorizontalAlignment", "left", "VerticalAlignment", "middle", ...
        "FontName", "Times New Roman", ...
        "FontSize", 12.0, "Color", colors.Text);
end
ax.YDir = "reverse";
style_axes(ax, colors);
ax.YGrid = "off";
ax.XGrid = "on";
export_figure(f, outputBase);
close(f);
end


function plot_corrected_metrics(data, colors, outputBase)
f = new_figure(7.2, 4.8);
ax = axes(f);
hold(ax, "on");
values = [data.shift_safe_nm, data.standard_nm];
b = bar(ax, values, "grouped", "BarWidth", 0.76);
b(1).FaceColor = colors.Blue;
b(1).EdgeColor = colors.Blue * 0.72;
b(2).FaceColor = colors.Orange;
b(2).EdgeColor = colors.Orange * 0.72;
for j = 1:2
    for i = 1:height(data)
        text(ax, b(j).XEndPoints(i), values(i, j) + 1.5, ...
            sprintf("%.2f", values(i, j)), "HorizontalAlignment", "center", ...
            "FontName", "Times New Roman", "FontSize", 11.5, ...
            "Color", colors.Text);
    end
end
xticks(ax, 1:height(data));
xticklabels(ax, ["Median AE", "RMSE", "Maximum AE"]);
ylabel(ax, "Bias-corrected CD error (nm)");
ylim(ax, [0 70]);
legend(ax, b, ["Anti-aliased upsampling", "Standard upsampling"], ...
    "Location", "northoutside", "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 12.5);
style_axes(ax, colors);
export_figure(f, outputBase);
close(f);
end


function plot_sensitivity(data, colors, outputBase)
f = new_figure(7.2, 4.8);
ax = axes(f);
hold(ax, "on");
h1 = plot(ax, data.sigma_px, data.shift_safe_rmse_nm, "-o", ...
    "Color", colors.Blue, "MarkerFaceColor", colors.Blue, ...
    "MarkerSize", 7.0, "LineWidth", 2.2);
h2 = plot(ax, data.sigma_px, data.standard_rmse_nm, "-s", ...
    "Color", colors.Orange, "MarkerFaceColor", "white", ...
    "MarkerSize", 7.0, "LineWidth", 2.2);
for i = 1:height(data)
    text(ax, data.sigma_px(i), data.shift_safe_rmse_nm(i) - 0.08, ...
        sprintf("%.2f", data.shift_safe_rmse_nm(i)), ...
        "HorizontalAlignment", "center", "VerticalAlignment", "top", ...
        "FontName", "Times New Roman", "FontSize", 11.0, "Color", colors.Blue);
    text(ax, data.sigma_px(i), data.standard_rmse_nm(i) + 0.08, ...
        sprintf("%.2f", data.standard_rmse_nm(i)), ...
        "HorizontalAlignment", "center", "VerticalAlignment", "bottom", ...
        "FontName", "Times New Roman", "FontSize", 11.0, "Color", colors.Orange);
end
xlabel(ax, "Gradient-profile smoothing, sigma (pixel)");
ylabel(ax, "Bias-corrected CD RMSE (nm)");
xlim(ax, [0.65 1.60]);
xticks(ax, data.sigma_px);
ylim(ax, [26.35 27.30]);
legend(ax, [h1 h2], ["Anti-aliased upsampling", "Standard upsampling"], ...
    "Location", "northoutside", "Orientation", "horizontal", ...
    "Box", "off", "FontSize", 12.5);
style_axes(ax, colors);
export_figure(f, outputBase);
close(f);
end


function f = new_figure(widthIn, heightIn)
f = figure("Color", "white", "Units", "inches", ...
    "Position", [0.7 0.7 widthIn heightIn], "Renderer", "painters");
end


function style_axes(ax, colors)
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
end


function export_figure(f, outputBase)
drawnow;
exportgraphics(f, outputBase + ".png", "Resolution", 300, ...
    "BackgroundColor", "white");
savefig(f, outputBase + ".fig");
end
