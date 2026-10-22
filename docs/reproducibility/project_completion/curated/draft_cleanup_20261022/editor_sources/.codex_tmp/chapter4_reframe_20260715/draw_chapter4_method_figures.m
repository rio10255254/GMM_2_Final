function draw_chapter4_method_figures
% Chapter 4 method figures for the measurement-oriented workflow.

outDir = 'D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\05_CHAPTER4_METHOD_REFRAME';
if ~exist(outDir, 'dir'); mkdir(outDir); end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Arial');
set(groot, 'defaultTextFontName', 'Arial');
set(groot, 'defaultTextInterpreter', 'none');

blue = [0.18 0.42 0.66];
teal = [0.15 0.55 0.52];
orange = [0.90 0.52 0.20];
purple = [0.47 0.36 0.67];
lightBlue = [0.91 0.95 0.98];
lightTeal = [0.90 0.97 0.96];
lightOrange = [0.99 0.94 0.87];
lightPurple = [0.95 0.93 0.98];
gray = [0.35 0.38 0.42];

%% Figure 4-1: overall method and evidence flow
f = figure('Units','inches','Position',[1 1 7.2 3.4]);
axes('Position',[0 0 1 1],'XLim',[0 1],'YLim',[0 1],'Visible','off'); hold on;
text(0.5,0.94,'Measurement-Oriented Reconstruction Workflow', ...
    'HorizontalAlignment','center','FontSize',12,'FontWeight','bold','Color',[0.12 0.16 0.20]);

xs = [0.035 0.235 0.435 0.635 0.835];
w = 0.13; h = 0.35; y = 0.42;
fills = {lightBlue, lightTeal, lightPurple, lightOrange, [0.94 0.95 0.96]};
edges = {blue, teal, purple, orange, gray};
titles = {'Optical\ncalibration','Training data\ndesign','Model\ntraining','Single-frame\ninference','Metrology\nevaluation'};
subs = {'Local PSF fitting\nWiener control','SEM anchors\nMotion pairs','Geometry-preserving\nreconstruction','One image in\nOne image out','Edge, CD, and\ndisplacement'};
for i = 1:5
    roundedBox(xs(i),y,w,h,fills{i},edges{i});
    text(xs(i)+w/2,y+0.235,multiLine(titles{i}),'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontSize',9.3,'FontWeight','bold','Color',edges{i});
    text(xs(i)+w/2,y+0.105,multiLine(subs{i}),'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontSize',7.8,'Color',[0.18 0.20 0.23]);
    if i < 5
        annotation(f,'arrow',[xs(i)+w+0.012 xs(i+1)-0.012],[y+h/2 y+h/2], ...
            'Color',[0.42 0.45 0.48],'LineWidth',1.2,'HeadLength',7,'HeadWidth',7);
    end
end

text(0.5,0.26,'Design goal: improve measurement reliability while preserving geometric position', ...
    'HorizontalAlignment','center','FontSize',9.2,'FontWeight','bold','Color',[0.18 0.23 0.28]);
text(0.5,0.15,['PSF fitting characterizes the optical system; the proposed model is judged by downstream ', ...
    'measurement rather than visual sharpness alone.'], ...
    'HorizontalAlignment','center','FontSize',8.1,'Color',[0.30 0.33 0.36]);
saveFigure(f,outDir,'fig_4_1_overall_method_workflow');

%% Figure 4-2: proposed reconstruction data path
f = figure('Units','inches','Position',[1 1 7.2 4.3]);
axes('Position',[0 0 1 1],'XLim',[0 1],'YLim',[0 1],'Visible','off'); hold on;
text(0.5,0.95,'Measurement-Oriented Reconstruction Network', ...
    'HorizontalAlignment','center','FontSize',12,'FontWeight','bold','Color',[0.12 0.16 0.20]);

% Main horizontal path
items = {
    0.025, 0.57, 0.115, 0.22, [0.95 0.96 0.97], gray, 'Raw image', 'H x W';
    0.165, 0.57, 0.145, 0.22, lightBlue, blue, 'Fixed multi-PSF\naggregation', '25 normalized PSFs\n5 x 5 grid, mean';
    0.335, 0.57, 0.145, 0.22, lightTeal, teal, 'Conservative\nphysical prior', 'Wiener-style residual\nalpha = 0.10, reg = 10';
    0.505, 0.57, 0.135, 0.22, lightPurple, purple, 'Encoder-\ndecoder', 'Position-preserving\nupsampling';
    0.665, 0.57, 0.145, 0.22, lightOrange, orange, 'Boundary\ncorrection', 'Orientation-aware\nmax residual = 0.025';
    0.835, 0.57, 0.14, 0.22, [0.92 0.96 0.94], [0.20 0.48 0.30], 'Restored image', 'H x W'};
for i = 1:size(items,1)
    x=items{i,1}; yy=items{i,2}; ww=items{i,3}; hh=items{i,4};
    roundedBox(x,yy,ww,hh,items{i,5},items{i,6});
    text(x+ww/2,yy+0.145,multiLine(items{i,7}),'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontSize',8.8,'FontWeight','bold','Color',items{i,6});
    text(x+ww/2,yy+0.052,multiLine(items{i,8}),'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontSize',7.2,'Color',[0.20 0.22 0.25]);
    if i < size(items,1)
        x2=items{i+1,1};
        annotation(f,'arrow',[x+ww+0.006 x2-0.006],[yy+hh/2 yy+hh/2], ...
            'Color',[0.40 0.43 0.46],'LineWidth',1.1,'HeadLength',6,'HeadWidth',6);
    end
end

% Output safeguards beneath the main path
roundedBox(0.275,0.20,0.22,0.19,[0.95 0.96 0.98],[0.32 0.42 0.58]);
text(0.385,0.32,'Raw low-frequency anchor','HorizontalAlignment','center', ...
    'FontSize',8.1,'FontWeight','bold','Color',[0.24 0.35 0.52]);
text(0.385,0.245,multiLine('Preserve position; add only\n0.35 x predicted detail'),'HorizontalAlignment','center', ...
    'FontSize',7.5,'Color',[0.22 0.24 0.27]);

roundedBox(0.52,0.20,0.21,0.19,[0.96 0.94 0.98],[0.48 0.34 0.64]);
text(0.625,0.32,'Image-quality control','HorizontalAlignment','center', ...
    'FontSize',8.2,'FontWeight','bold','Color',[0.42 0.28 0.58]);
text(0.625,0.245,multiLine('Scale the final correction\nwithin 0.78-1.08'),'HorizontalAlignment','center', ...
    'FontSize',7.5,'Color',[0.22 0.24 0.27]);

annotation(f,'arrow',[0.385 0.72],[0.39 0.565],'Color',[0.32 0.42 0.58], ...
    'LineWidth',1.0,'LineStyle','--','HeadLength',6,'HeadWidth',6);
annotation(f,'arrow',[0.625 0.885],[0.39 0.565],'Color',[0.48 0.34 0.64], ...
    'LineWidth',1.0,'LineStyle','--','HeadLength',6,'HeadWidth',6);

text(0.5,0.09,'Adaptive four-PSF weighting is retained as a switchable extension of the fixed fusion path.', ...
    'HorizontalAlignment','center','FontSize',7.8,'Color',[0.42 0.42 0.42]);
saveFigure(f,outDir,'fig_4_2_measurement_oriented_reconstruction_path');

%% Figure 4-3: supervision-to-evidence logic
f = figure('Units','inches','Position',[1 1 7.2 4.6]);
axes('Position',[0 0 1 1],'XLim',[0 1],'YLim',[0 1],'Visible','off'); hold on;
text(0.5,0.955,'Training Supervision and Evaluation Design', ...
    'HorizontalAlignment','center','FontSize',12,'FontWeight','bold','Color',[0.12 0.16 0.20]);

colX = [0.035 0.365 0.695]; colW = 0.27;
headers = {'Training evidence','Functional objectives','Evaluation measures'};
headerColors = {blue,purple,orange};
for c=1:3
    roundedBox(colX(c),0.84,colW,0.08,headerColors{c},headerColors{c});
    text(colX(c)+colW/2,0.88,headers{c},'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontSize',9.2,'FontWeight','bold','Color','w');
end

left = {'Known synthetic geometry','SEM geometry references','Real-image reconstruction\nreferences', ...
        'Known-shift and motion pairs','Multi-magnification\nstability data'};
mid = {'Image content and low-frequency\npreservation','Boundary geometry preservation', ...
       'Motion and translation\nconsistency','Limits on excessive correction'};
right = {'10-90% edge width\nand ringing','CD error and\nthreshold robustness', ...
         'Command consistency\nand step spread','Spatial and condition\nrobustness'};

drawList(colX(1),0.24,colW,0.56,left,lightBlue,blue);
drawList(colX(2),0.29,colW,0.51,mid,lightPurple,purple);
drawList(colX(3),0.29,colW,0.51,right,lightOrange,orange);

annotation(f,'arrow',[colX(1)+colW+0.015 colX(2)-0.015],[0.56 0.56], ...
    'Color',[0.40 0.43 0.46],'LineWidth',1.3,'HeadLength',7,'HeadWidth',7);
annotation(f,'arrow',[colX(2)+colW+0.015 colX(3)-0.015],[0.56 0.56], ...
    'Color',[0.40 0.43 0.46],'LineWidth',1.3,'HeadLength',7,'HeadWidth',7);

text(0.5,0.145,'Evaluation compares original images, PSF-based Wiener deconvolution, and the proposed model.', ...
    'HorizontalAlignment','center','FontSize',8.4,'FontWeight','bold','Color',[0.20 0.24 0.28]);
text(0.5,0.075,['Training and evaluation groups are separated by image sequence ', ...
    'to prevent neighboring frames from leaking across the split.'], ...
    'HorizontalAlignment','center','FontSize',7.8,'Color',[0.38 0.40 0.42]);
saveFigure(f,outDir,'fig_4_3_supervision_and_evidence_logic');

close all;
fprintf('Saved Chapter 4 figures to %s\n', outDir);
end

function roundedBox(x,y,w,h,fillColor,edgeColor)
rectangle('Position',[x y w h],'Curvature',0.10,'FaceColor',fillColor, ...
    'EdgeColor',edgeColor,'LineWidth',1.15);
end

function drawList(x,y,w,h,items,fillColor,edgeColor)
roundedBox(x,y,w,h,fillColor,edgeColor);
n = numel(items);
top = y+h-0.065;
step = (h-0.09)/n;
for i=1:n
    yy = top-(i-0.5)*step;
    plot(x+0.027,yy,'o','MarkerSize',4.2,'MarkerFaceColor',edgeColor,'MarkerEdgeColor',edgeColor);
    text(x+0.047,yy,multiLine(items{i}),'HorizontalAlignment','left','VerticalAlignment','middle', ...
        'FontSize',7.7,'Color',[0.19 0.21 0.24]);
end
end

function saveFigure(f,outDir,baseName)
set(f,'PaperPositionMode','auto');
exportgraphics(f,fullfile(outDir,[baseName '.png']),'Resolution',300,'BackgroundColor','white');
exportgraphics(f,fullfile(outDir,[baseName '.pdf']),'ContentType','vector','BackgroundColor','white');
savefig(f,fullfile(outDir,[baseName '.fig']));
end

function out = multiLine(in)
out = strrep(in, '\n', sprintf('\n'));
end
