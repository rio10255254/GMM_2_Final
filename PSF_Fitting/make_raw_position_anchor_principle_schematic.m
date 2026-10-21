function make_raw_position_anchor_principle_schematic()
% English schematic for explaining the Raw-position anchoring principle.

outRoot = "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures" + ...
    "\13_V26_RAW_POSITION_ANCHOR_PRINCIPLE_20260727";
figureDir = fullfile(outRoot, "figures");
if ~isfolder(figureDir)
    mkdir(figureDir);
end

blue = [0.05 0.38 0.67];
orange = [0.82 0.42 0.12];
gold = [0.82 0.62 0.12];
dark = [0.18 0.18 0.18];
lightBlue = [0.93 0.96 0.985];

% Illustrative pillar images. The fusion operation follows the implemented
% detail-mode adapter: Raw + 0.35 * high-frequency prediction detail.
n = 180;
[xx, yy] = meshgrid(1:n, 1:n);
cx = (n + 1) / 2;
cy = (n + 1) / 2;
radius = 47;
rawMask = hypot(xx - cx, yy - cy) <= radius;
predMask = hypot(xx - (cx + 3.0), yy - (cy - 1.5)) <= radius;

rawImage = 0.76 - 0.43 * imgaussfilt(double(rawMask), 5.2);
predCore = imgaussfilt(double(predMask), 1.25);
ring = imgaussfilt(double(predMask), 1.0) - imgaussfilt(double(predMask), 4.0);
predImage = 0.76 - 0.47 * predCore - 0.17 * ring;

predLow = imgaussfilt(predImage, 2.0);
detail = predImage - predLow;
anchoredImage = rawImage + 0.35 * detail;
anchoredImage = anchoredImage + mean(rawImage, "all") - mean(anchoredImage, "all");
anchoredImage = min(max(anchoredImage, 0), 1);

f = figure("Color", "white", "Units", "inches", ...
    "Position", [0.5 0.5 12.6 5.4], "Renderer", "painters");

axPred = axes(f, "Position", [0.055 0.585 0.17 0.30]);
show_image(axPred, predImage, [0.25 0.82]);
outline_axes(axPred, orange);

axRaw = axes(f, "Position", [0.055 0.175 0.17 0.30]);
show_image(axRaw, rawImage, [0.25 0.82]);
outline_axes(axRaw, blue);

axDetail = axes(f, "Position", [0.365 0.585 0.17 0.30]);
detailLimit = max(abs(detail), [], "all");
show_image(axDetail, detail, [-detailLimit detailLimit]);
outline_axes(axDetail, gold);

axOutput = axes(f, "Position", [0.765 0.355 0.18 0.32]);
show_image(axOutput, anchoredImage, [0.25 0.82]);
outline_axes(axOutput, blue);

add_label(f, [0.035 0.895 0.21 0.055], "Network prediction, I_{pred}", orange, 16.5, "bold");
add_label(f, [0.035 0.485 0.21 0.055], "Raw image, I_{raw}", blue, 16.5, "bold");
add_label(f, [0.335 0.895 0.23 0.055], "High-frequency detail, D", gold, 16.5, "bold");
add_label(f, [0.735 0.685 0.24 0.055], "Anchored output, I_{out}", blue, 16.5, "bold");

add_label(f, [0.035 0.535 0.21 0.045], "Restored edge information", dark, 12.5, "normal");
add_label(f, [0.035 0.125 0.21 0.045], "Measured position and intensity", dark, 12.5, "normal");
add_label(f, [0.335 0.535 0.23 0.045], "Low-frequency content removed", dark, 12.5, "normal");
add_label(f, [0.735 0.305 0.24 0.045], "Detail enhanced, position retained", dark, 12.5, "normal");

annotation(f, "arrow", [0.225 0.355], [0.735 0.735], ...
    "Color", dark, "LineWidth", 1.8, "HeadLength", 10, "HeadWidth", 10);
annotation(f, "arrow", [0.535 0.622], [0.735 0.525], ...
    "Color", gold, "LineWidth", 2.0, "HeadLength", 10, "HeadWidth", 10);
annotation(f, "arrow", [0.225 0.622], [0.325 0.485], ...
    "Color", blue, "LineWidth", 2.0, "HeadLength", 10, "HeadWidth", 10);
annotation(f, "arrow", [0.680 0.755], [0.505 0.505], ...
    "Color", dark, "LineWidth", 2.0, "HeadLength", 10, "HeadWidth", 10);

annotation(f, "ellipse", [0.622 0.457 0.058 0.096], ...
    "FaceColor", "white", "EdgeColor", dark, "LineWidth", 1.8);
add_label(f, [0.622 0.461 0.058 0.088], "+", dark, 23, "bold");
add_label(f, [0.555 0.595 0.075 0.05], "\times 0.35", gold, 14.0, "bold");

annotation(f, "textbox", [0.275 0.045 0.67 0.16], ...
    "String", {"D = I_{pred} - G_{\sigma=2 px}(I_{pred})", ...
    "I_{out} = clip[I_{raw} + 0.35D]  with mean intensity aligned to I_{raw}"}, ...
    "Interpreter", "tex", "HorizontalAlignment", "center", ...
    "VerticalAlignment", "middle", "FontName", "Times New Roman", ...
    "FontSize", 15.0, "Color", dark, "EdgeColor", blue, ...
    "BackgroundColor", lightBlue, "LineWidth", 1.2, "Margin", 8);

annotation(f, "textbox", [0.055 0.035 0.19 0.075], ...
    "String", "Raw supplies the spatial base", ...
    "HorizontalAlignment", "center", "VerticalAlignment", "middle", ...
    "FontName", "Times New Roman", "FontSize", 13.0, ...
    "FontWeight", "bold", "Color", blue, "EdgeColor", "none");

outputBase = fullfile(figureDir, "01_raw_position_anchor_principle_schematic");
drawnow;
exportgraphics(f, outputBase + ".png", "Resolution", 300, ...
    "BackgroundColor", "white");
exportgraphics(f, outputBase + ".pdf", "ContentType", "vector", ...
    "BackgroundColor", "white");
savefig(f, outputBase + ".fig");
close(f);
end


function show_image(ax, imageData, limits)
imagesc(ax, imageData, limits);
axis(ax, "image");
axis(ax, "off");
colormap(ax, gray(256));
end


function outline_axes(ax, color)
rectangle(ax, "Position", [0.5 0.5 size(ax.Children.CData, 2) size(ax.Children.CData, 1)], ...
    "EdgeColor", color, "LineWidth", 2.2);
end


function add_label(fig, position, label, color, fontSize, weight)
annotation(fig, "textbox", position, "String", label, ...
    "Interpreter", "tex", "HorizontalAlignment", "center", ...
    "VerticalAlignment", "middle", "FontName", "Times New Roman", ...
    "FontSize", fontSize, "FontWeight", weight, "Color", color, ...
    "EdgeColor", "none", "Margin", 0);
end
