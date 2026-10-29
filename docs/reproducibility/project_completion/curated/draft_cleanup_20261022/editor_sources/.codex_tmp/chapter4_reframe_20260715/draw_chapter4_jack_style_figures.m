function draw_chapter4_jack_style_figures
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))))))));
% Clean Chapter 4 method figures with a thesis-style visual language.
% All visible text is English; every figure is exported as PNG, PDF, and FIG.

outDir = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures/05_CHAPTER4_METHOD_PLAIN');
if ~exist(outDir, 'dir'); mkdir(outDir); end

inputPath = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\' ...
    'center9_pillar_fit_20x_50x\20x\05_original_pillar_3x3.png'];
outputPath = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\' ...
    'center9_pillar_fit_20x_50x\20x\06_v42_e120_reconstruction_pillar_3x3.png'];
rawThumb = readGraySafe(inputPath);
restoredThumb = readGraySafe(outputPath);

set(groot,'defaultFigureColor','w');
set(groot,'defaultAxesFontName','Arial');
set(groot,'defaultTextFontName','Arial');
set(groot,'defaultTextInterpreter','none');
set(groot,'defaultAxesFontSize',8.2);

% Restrained thesis palette: charcoal, neutral gray, and one muted blue.
ink = [0.10 0.10 0.10];
gray = [0.42 0.42 0.42];
light = [0.975 0.975 0.975];
blue = [0.18 0.34 0.50];
lightBlue = [0.94 0.96 0.98];
green = blue;
lightGreen = light;
gold = blue;
lightGold = light;
purple = blue;
lightPurple = light;
red = gray;

%% Figure 4-1: overall workflow
f = makeFigure(7.2,3.15);
main = canvas(f);
text(0.50,0.93,'Measurement-Oriented Reconstruction Workflow', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);
xs = [0.035 0.225 0.415 0.605 0.795];
titles = {'Optical\ncalibration','Training\ndata','Model\nlearning','Single-image\ninference','Metrology\nvalidation'};
details = {'Center-nine pillars\nSEM geometry\nand PSF fitting', ...
    'Geometry, real textures,\nand known-shift pairs', ...
    'Image, boundary, motion,\nand safeguard objectives', ...
    'One H x W image in\nOne H x W image out', ...
    'Edge, CD, displacement,\nand condition\nrobustness'};
fills = {light,light,light,light,light};
for i = 1:5
    simpleBox(xs(i),0.40,0.15,0.33,fills{i},ink,0.65);
    text(xs(i)+0.075,0.775,sprintf('Stage %d',i),'HorizontalAlignment','center', ...
        'FontSize',6.3,'FontWeight','bold','Color',blue);
    text(xs(i)+0.075,0.65,multiline(titles{i}),'HorizontalAlignment','center', ...
        'FontSize',7.8,'FontWeight','bold','Color',ink);
    text(xs(i)+0.075,0.50,multiline(details{i}),'HorizontalAlignment','center', ...
        'VerticalAlignment','middle','FontSize',5.7,'Color',[0.22 0.22 0.22]);
    if i < 5
        drawArrow(f,xs(i)+0.154,xs(i+1)-0.010,0.565,ink,1.0);
    end
end
plot([0.06 0.94],[0.27 0.27],'-','Color',[0.75 0.75 0.75],'LineWidth',0.8);
text(0.50,0.18,'Common evaluation protocol', ...
    'HorizontalAlignment','center','FontSize',7.5,'FontWeight','bold','Color',ink);
text(0.50,0.10,'Identical region, orientation, pixel scale, and measurement rules for all methods.', ...
    'HorizontalAlignment','center','FontSize',7.1,'Color',[0.28 0.28 0.28]);
saveFigure(f,outDir,'fig_4_1_overall_method_workflow');

%% Figure 4-2: center-nine selection, orientation, and SEM truth
f = makeFigure(7.2,3.65);
main = canvas(f);
text(0.50,0.95,'Center-Nine Pillar Selection and SEM Ground Truth', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);

% (a) Junction schematic
simpleBox(0.025,0.16,0.29,0.70,[1 1 1],ink,0.9);
text(0.17,0.82,'(a) Structure identification','HorizontalAlignment','center', ...
    'FontSize',8.7,'FontWeight','bold','Color',ink);
plot([0.07 0.07],[0.21 0.72],'-','Color',ink,'LineWidth',1.0);
plot([0.07 0.28],[0.21 0.21],'-','Color',ink,'LineWidth',1.0);
plot(0.07,0.21,'p','MarkerSize',8,'MarkerFaceColor',red,'MarkerEdgeColor',red);
text(0.085,0.185,'Sample center','FontSize',7.1,'Color',red,'HorizontalAlignment','left');
for r = 1:3
    for c = 1:3
        cx = 0.125 + (c-1)*0.065;
        cy = 0.31 + (r-1)*0.14;
        drawDisk(cx,cy,0.018,[0.28 0.28 0.28],ink,0.6);
    end
end
rectangle('Position',[0.095 0.275 0.178 0.355],'EdgeColor',blue,'LineWidth',1.4,'LineStyle','--');
text(0.19,0.68,'Nearest pillar 3 x 3','HorizontalAlignment','center', ...
    'FontSize',7.5,'FontWeight','bold','Color',blue);
for r = 1:3
    for c = 1:2
        cx = 0.012 + (c-1)*0.035;
        cy = 0.34 + (r-1)*0.14;
        drawRing(cx,cy,0.014,[0.65 0.65 0.65]);
    end
end
text(0.035,0.75,'Via region','HorizontalAlignment','center','FontSize',7.1,'Color',gray);
text(0.19,0.75,'Pillar region','HorizontalAlignment','center','FontSize',7.1,'Color',ink);

% (b) Orientation rule
simpleBox(0.345,0.16,0.28,0.70,[1 1 1],ink,0.9);
text(0.485,0.82,'(b) Orientation correction','HorizontalAlignment','center', ...
    'FontSize',8.7,'FontWeight','bold','Color',ink);
drawMiniGrid(0.39,0.54,0.13,0.18,false,ink);
text(0.455,0.50,'50x: keep acquisition orientation','HorizontalAlignment','center', ...
    'FontSize',7.2,'Color',ink);
drawMiniGrid(0.39,0.25,0.13,0.18,true,ink);
text(0.455,0.21,'20x: apply vertical flip first','HorizontalAlignment','center', ...
    'FontSize',7.2,'Color',ink);
drawArrow(f,0.535,0.595,0.63,blue,1.0);
text(0.565,0.66,'Canonical SEM direction','Rotation',90,'HorizontalAlignment','center', ...
    'FontSize',7.0,'Color',blue);
text(0.485,0.115,'Polarity is not used to decide pillar versus via.', ...
    'HorizontalAlignment','center','FontSize',7.1,'Color',red);

% (c) SEM-derived diameter map
simpleBox(0.655,0.16,0.32,0.70,[1 1 1],ink,0.9);
text(0.815,0.82,'(c) Per-pillar SEM diameter','HorizontalAlignment','center', ...
    'FontSize',8.7,'FontWeight','bold','Color',ink);
diam = [2620.214374 2620.016372 2642.315580; ...
        2620.428558 2608.719538 2658.613794; ...
        2621.779998 2598.751654 2676.796570];
for r = 1:3
    for c = 1:3
        cx = 0.71 + (c-1)*0.105;
        cy = 0.33 + (3-r)*0.15;
        rr = 0.021 + (diam(r,c)-min(diam(:)))/(max(diam(:))-min(diam(:)))*0.007;
        drawDisk(cx,cy,rr,[0.35 0.35 0.35],ink,0.6);
        text(cx,cy-0.045,sprintf('%.1f',diam(r,c)),'HorizontalAlignment','center', ...
            'FontSize',6.5,'Color',ink);
    end
end
plot(0.675,0.25,'p','MarkerSize',7,'MarkerFaceColor',red,'MarkerEdgeColor',red);
text(0.69,0.235,'Sample center','FontSize',6.8,'Color',red,'HorizontalAlignment','left');
text(0.815,0.18,'SEM radius x 2 = ground-truth CD (nm)', ...
    'HorizontalAlignment','center','FontSize',7.3,'FontWeight','bold','Color',ink);
saveFigure(f,outDir,'fig_4_2_center_nine_and_sem_ground_truth');

%% Figure 4-3: PSF fitting process
f = makeFigure(7.2,4.15);
main = canvas(f);
text(0.50,0.955,'Parametric PSF Fitting Procedure', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);

[gt,psf,pred] = syntheticPsfExample;
imageAxes([0.030 0.59 0.145 0.24],gt,'SEM geometry');
axes(main);
text(0.190,0.70,'x','FontSize',16,'FontWeight','bold','HorizontalAlignment','center','Color',ink);
imageAxes([0.210 0.59 0.120 0.24],psf,'Candidate PSF');
axes(main);
text(0.348,0.70,'=','FontSize',16,'FontWeight','bold','HorizontalAlignment','center','Color',ink);
imageAxes([0.365 0.59 0.145 0.24],pred,'Predicted image');
axes(main);
drawArrow(f,0.525,0.565,0.705,ink,1.0);
imageAxes([0.575 0.59 0.145 0.24],rawThumb,'Captured image');
axes(main);

simpleBox(0.765,0.56,0.205,0.29,lightBlue,ink,0.8);
text(0.868,0.78,'Masked loss','HorizontalAlignment','center','FontSize',8.2, ...
    'FontWeight','bold','Color',ink);
text(0.868,0.70,'Intensity MSE','HorizontalAlignment','center','FontSize',7.3,'Color',ink);
text(0.868,0.64,'Normalized-gradient MSE','HorizontalAlignment','center', ...
    'FontSize',6.8,'Color',ink);
text(0.868,0.585,'Weight = 8 x 10^4','HorizontalAlignment','center', ...
    'FontSize',6.9,'Color',blue);
drawArrow(f,0.725,0.765,0.705,ink,1.0);

simpleBox(0.31,0.26,0.38,0.19,lightGold,ink,0.8);
text(0.50,0.395,'BADS parameter update','HorizontalAlignment','center','FontSize',8.5, ...
    'FontWeight','bold','Color',ink);
text(0.50,0.335,multiline('Z2 and Z3 fixed at zero\nOptimize Z4-Z15 and amplitude'), ...
    'HorizontalAlignment','center','FontSize',6.9,'Color',ink);
text(0.50,0.275,'Repeat until the loss no longer improves', ...
    'HorizontalAlignment','center','FontSize',7.1,'Color',[0.28 0.28 0.28]);
annotation(f,'arrow',[0.868 0.69],[0.56 0.355],'Color',ink,'LineWidth',1.0, ...
    'HeadLength',7,'HeadWidth',7);
annotation(f,'arrow',[0.31 0.275],[0.355 0.59],'Color',ink,'LineWidth',1.0, ...
    'HeadLength',7,'HeadWidth',7);
text(0.50,0.17,'Subpixel pre-alignment prevents displacement from being misread as aberration.', ...
    'HorizontalAlignment','center','FontSize',7.1,'Color',red);
text(0.50,0.105,'Every candidate PSF is normalized to unit energy before comparison.', ...
    'HorizontalAlignment','center','FontSize',7.1,'Color',red);
saveFigure(f,outDir,'fig_4_3_psf_fitting_process');

%% Figure 4-4: network architecture
f = makeFigure(7.2,4.15);
main = canvas(f);
text(0.50,0.955,'Measurement-Oriented Reconstruction Network', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);
imageAxes([0.025 0.58 0.105 0.22],rawThumb,'Input');
axes(main);
simpleBox(0.155,0.595,0.12,0.17,lightBlue,ink,0.8);
text(0.215,0.70,'Fixed 25-PSF','HorizontalAlignment','center','FontSize',7.6,'FontWeight','bold','Color',ink);
text(0.215,0.64,'physical prior','HorizontalAlignment','center','FontSize',7.4,'Color',ink);
drawArrow(f,0.13,0.155,0.68,ink,1.0);
drawArrow(f,0.275,0.31,0.68,ink,1.0);

% Encoder-decoder blocks
encX = [0.315 0.405 0.495]; encY = [0.66 0.53 0.40];
decX = [0.585 0.675 0.765]; decY = [0.40 0.53 0.66];
for i=1:3
    simpleBox(encX(i),encY(i),0.055,0.15,lightGreen,ink,0.8);
    text(encX(i)+0.0275,encY(i)+0.075,sprintf('E%d',i),'HorizontalAlignment','center', ...
        'FontSize',7.4,'FontWeight','bold','Color',ink);
    if i<3
        annotation(f,'arrow',[encX(i)+0.055 encX(i+1)],[encY(i)+0.075 encY(i+1)+0.075], ...
            'Color',ink,'LineWidth',0.9,'HeadLength',6,'HeadWidth',6);
    end
end
simpleBox(0.505,0.24,0.12,0.14,lightGold,ink,0.8);
text(0.565,0.31,'Bottleneck','HorizontalAlignment','center','FontSize',7.6, ...
    'FontWeight','bold','Color',ink);
annotation(f,'arrow',[0.522 0.545],[0.40 0.38],'Color',ink,'LineWidth',0.9,'HeadLength',6,'HeadWidth',6);
for i=1:3
    simpleBox(decX(i),decY(i),0.055,0.15,lightPurple,ink,0.8);
    text(decX(i)+0.0275,decY(i)+0.075,sprintf('D%d',4-i),'HorizontalAlignment','center', ...
        'FontSize',7.4,'FontWeight','bold','Color',ink);
    if i==1
        annotation(f,'arrow',[0.625 decX(i)],[0.31 decY(i)+0.075], ...
            'Color',ink,'LineWidth',0.9,'HeadLength',6,'HeadWidth',6);
    else
        annotation(f,'arrow',[decX(i-1)+0.055 decX(i)],[decY(i-1)+0.075 decY(i)+0.075], ...
            'Color',ink,'LineWidth',0.9,'HeadLength',6,'HeadWidth',6);
    end
end
for i=1:3
    y1=encY(i)+0.15; y2=decY(4-i)+0.15;
    plot([encX(i)+0.0275 decX(4-i)+0.0275],[y1 y2],'-','Color',blue,'LineWidth',1.0);
end
text(0.54,0.865,'Skip connections preserve fine spatial position', ...
    'HorizontalAlignment','center','FontSize',7.2,'Color',blue);

simpleBox(0.84,0.595,0.075,0.17,lightGold,ink,0.8);
text(0.877,0.70,'Output','HorizontalAlignment','center','FontSize',7.4,'FontWeight','bold','Color',ink);
text(0.877,0.64,'controls','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
drawArrow(f,0.82,0.84,0.68,ink,1.0);
imageAxes([0.925 0.58 0.07 0.22],restoredThumb,'Output');
axes(main);
drawArrow(f,0.915,0.925,0.68,ink,0.9);
text(0.50,0.11,'Same-size inference: the network restores boundary information on the original sampling grid.', ...
    'HorizontalAlignment','center','FontSize',8.0,'FontWeight','bold','Color',ink);
text(0.50,0.055,'The architecture does not stack multiple frames during deployment.', ...
    'HorizontalAlignment','center','FontSize',7.4,'Color',[0.28 0.28 0.28]);
saveFigure(f,outDir,'fig_4_4_measurement_oriented_network');

%% Figure 4-5: output safeguards
f = makeFigure(7.2,3.65);
main = canvas(f);
text(0.50,0.95,'Output Safeguards for Geometric Preservation', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);
panels = [0.025 0.34 0.32; 0.36 0.34 0.32; 0.695 0.34 0.28];
for i=1:3; simpleBox(panels(i,1),0.14,panels(i,3),0.70,[1 1 1],ink,0.9); end

text(0.185,0.80,'(a) Bounded boundary residual','HorizontalAlignment','center', ...
    'FontSize',8.5,'FontWeight','bold','Color',ink);
x=linspace(-3,3,160); raw=1./(1+exp(-1.7*x)); detail=0.018*sin(5*x).*exp(-0.7*x.^2);
ax=axes('Position',[0.065 0.35 0.24 0.32]); hold(ax,'on');
plot(ax,x,raw,'Color',gray,'LineWidth',1.3); plot(ax,x,raw+detail,'Color',blue,'LineWidth',1.5);
yline(ax,0.5,':','Color',[0.65 0.65 0.65]); grid(ax,'on'); box(ax,'on');
xlabel(ax,'Position'); ylabel(ax,'Normalized intensity');
legend(ax,{'Before correction','After correction'},'Location','southeast','FontSize',6.5);
title(ax,'Orientation-aware local change','FontSize',7.3,'FontWeight','normal');
axes(main);
text(0.185,0.23,'Maximum absolute residual = 0.025','HorizontalAlignment','center', ...
    'FontSize',7.4,'FontWeight','bold','Color',blue);
text(0.185,0.18,'Large-area geometry cannot be freely rewritten.','HorizontalAlignment','center', ...
    'FontSize',7.0,'Color',ink);

text(0.52,0.80,'(b) Raw low-frequency anchor','HorizontalAlignment','center', ...
    'FontSize',8.5,'FontWeight','bold','Color',ink);
simpleBox(0.395,0.53,0.10,0.12,light,ink,0.8); text(0.445,0.59,'Raw image','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
text(0.515,0.59,'+','HorizontalAlignment','center','FontSize',13,'FontWeight','bold','Color',ink);
simpleBox(0.54,0.53,0.105,0.12,lightBlue,ink,0.8); text(0.592,0.59,'0.35 x detail','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
text(0.52,0.43,'Detail = prediction - Gaussian blur','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
text(0.52,0.34,'Gaussian sigma = 2.0 pixels','HorizontalAlignment','center','FontSize',7.2,'FontWeight','bold','Color',blue);
text(0.52,0.25,multiline('Low-frequency position, background,\nand mean intensity remain tied to the input.'), ...
    'HorizontalAlignment','center','FontSize',7.0,'Color',ink);

text(0.835,0.80,'(c) Input-quality gate','HorizontalAlignment','center', ...
    'FontSize',8.5,'FontWeight','bold','Color',ink);
ax=axes('Position',[0.73 0.36 0.21 0.30]);
q=linspace(0,1,100); s=0.78+(1.08-0.78)*q; plot(ax,q,s,'Color',purple,'LineWidth',1.7);
grid(ax,'on'); box(ax,'on'); xlim(ax,[0 1]); ylim(ax,[0.74 1.12]);
xlabel(ax,'Estimated image quality, q'); ylabel(ax,'Correction scale, s');
axes(main);
text(0.835,0.27,'s = 0.78 + 0.30q','HorizontalAlignment','center','FontSize',7.4,'FontWeight','bold','Color',purple);
text(0.835,0.20,multiline('Noisy inputs receive a conservative correction;\nclearer inputs retain more usable detail.'), ...
    'HorizontalAlignment','center','FontSize',6.9,'Color',ink);
saveFigure(f,outDir,'fig_4_5_output_safeguards');

%% Figure 4-6: supervision design
f = makeFigure(7.2,4.15);
main = canvas(f);
text(0.50,0.955,'Training Supervision Design', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);
text(0.50,0.905,'11,254 paired samples organized by function rather than by file origin', ...
    'HorizontalAlignment','center','FontSize',7.8,'Color',[0.30 0.30 0.30]);

sourceX=[0.035 0.215 0.395 0.575 0.755];
sourceTitles={'Known geometry','SEM geometry','Real-image reference','Known-shift pair','Condition stability'};
sourceSubs={'Exact shape and boundary','Independent CD scale','Camera texture and noise', ...
    'Translation consistency','Magnification and shape'};
for i=1:5
    simpleBox(sourceX(i),0.56,0.15,0.25,[1 1 1],ink,0.8);
    ax=axes('Position',[sourceX(i)+0.038 0.63 0.074 0.12]);
    switch i
        case 1; imagesc(ax,syntheticGrid(48,0));
        case 2; imagesc(ax,syntheticGrid(48,1));
        case 3; imagesc(ax,rawThumb);
        case 4; imagesc(ax,circshift(rawThumb,[0 2]));
        case 5; imagesc(ax,syntheticMixedShapes(48));
    end
    axis(ax,'image'); axis(ax,'off'); colormap(ax,repmat(linspace(0,1,256)',1,3));
    axes(main);
    text(sourceX(i)+0.075,0.605,sourceTitles{i},'HorizontalAlignment','center', ...
        'FontSize',7.2,'FontWeight','bold','Color',ink);
    text(sourceX(i)+0.075,0.575,sourceSubs{i},'HorizontalAlignment','center', ...
        'FontSize',5.1,'Color',[0.28 0.28 0.28]);
end

for i=1:5
    annotation(f,'arrow',[sourceX(i)+0.075 0.50],[0.55 0.46], ...
        'Color',[0.55 0.55 0.55],'LineWidth',0.8,'HeadLength',5,'HeadWidth',5);
end
simpleBox(0.20,0.19,0.60,0.23,lightBlue,ink,0.9);
lossX=[0.26 0.41 0.56 0.71];
lossT={multiline('Image\ncontent'),multiline('Boundary\ngeometry'),multiline('Motion\nconsistency'),'Safeguards'};
lossS={multiline('Intensity and\nfrequency'),multiline('Mask, centerline,\nand distance'), ...
    multiline('Shift and step\npreservation'),multiline('Low-frequency\nand locality')};
for i=1:4
    text(lossX(i),0.34,lossT{i},'HorizontalAlignment','center','FontSize',7.7, ...
        'FontWeight','bold','Color',ink);
    text(lossX(i),0.255,multiline(lossS{i}),'HorizontalAlignment','center', ...
        'FontSize',5.9,'Color',[0.26 0.26 0.26]);
    if i<4; plot([lossX(i)+0.06 lossX(i)+0.06],[0.22 0.39],'-','Color',[0.75 0.75 0.75]); end
end
text(0.50,0.105,'SEM references define geometry; real-image references provide appearance. They are not treated as the same type of truth.', ...
    'HorizontalAlignment','center','FontSize',7.3,'Color',red);
saveFigure(f,outDir,'fig_4_6_training_supervision_design');

%% Figure 4-7: shift consistency and fine-tuning
f = makeFigure(7.2,3.95);
main = canvas(f);
text(0.50,0.955,'Translation Consistency and Staged Fine-Tuning', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);

% Translation consistency top half
imageAxes([0.03 0.60 0.09 0.20],rawThumb,'Input x');
axes(main);
simpleBox(0.17,0.68,0.11,0.10,light,ink,0.8); text(0.225,0.73,'Shift S_delta','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
simpleBox(0.34,0.68,0.11,0.10,lightBlue,ink,0.8); text(0.395,0.73,'Reconstruct f','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
simpleBox(0.17,0.49,0.11,0.10,lightBlue,ink,0.8); text(0.225,0.54,'Reconstruct f','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
simpleBox(0.34,0.49,0.11,0.10,light,ink,0.8); text(0.395,0.54,'Shift S_delta','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
drawArrow(f,0.12,0.17,0.73,ink,0.9); drawArrow(f,0.28,0.34,0.73,ink,0.9);
drawArrow(f,0.12,0.17,0.54,ink,0.9); drawArrow(f,0.28,0.34,0.54,ink,0.9);
drawArrow(f,0.45,0.50,0.73,ink,0.9); drawArrow(f,0.45,0.50,0.54,ink,0.9);
simpleBox(0.50,0.49,0.15,0.29,lightGold,ink,0.9);
text(0.575,0.70,'Compare two paths','HorizontalAlignment','center','FontSize',7.7,'FontWeight','bold','Color',ink);
text(0.575,0.61,'L1 difference','HorizontalAlignment','center','FontSize',7.2,'Color',ink);
text(0.575,0.53,'Same object, same shift','HorizontalAlignment','center','FontSize',7.0,'Color',ink);
text(0.34,0.84,'Shift before reconstruction','HorizontalAlignment','center','FontSize',7.0,'Color',blue);
text(0.34,0.445,'Reconstruct before shift','HorizontalAlignment','center','FontSize',7.0,'Color',blue);

% Fine-tuning right and bottom
simpleBox(0.70,0.49,0.27,0.36,[1 1 1],ink,0.9);
text(0.835,0.80,'Staged fine-tuning','HorizontalAlignment','center','FontSize',8.3,'FontWeight','bold','Color',ink);
blocksX=[0.735 0.79 0.845 0.90]; fills={light,light,lightBlue,lightBlue};
for i=1:4
    simpleBox(blocksX(i),0.63,0.04,0.10,fills{i},ink,0.7);
end
text(0.775,0.585,multiline('Frozen feature\nextractor'),'HorizontalAlignment','center','FontSize',6.3,'Color',gray);
text(0.895,0.585,multiline('Trainable\noutput side'),'HorizontalAlignment','center','FontSize',6.3,'Color',blue);
text(0.835,0.52,'120 epochs; learning rate 2 x 10^-7','HorizontalAlignment','center','FontSize',7.1,'Color',ink);

simpleBox(0.10,0.14,0.80,0.20,lightGreen,ink,0.9);
text(0.21,0.275,'2,400 sequence pairs','HorizontalAlignment','center','FontSize',7.5,'FontWeight','bold','Color',ink);
text(0.43,0.275,'Up to 3,600 motion pairs','HorizontalAlignment','center','FontSize',7.5,'FontWeight','bold','Color',ink);
text(0.67,0.275,'1,000 validation pairs','HorizontalAlignment','center','FontSize',7.5,'FontWeight','bold','Color',ink);
plot([0.32 0.32],[0.17 0.31],'-','Color',[0.70 0.70 0.70]); plot([0.56 0.56],[0.17 0.31],'-','Color',[0.70 0.70 0.70]);
text(0.50,0.19,'Groups are split by original sequence to prevent neighboring frames from leaking across sets.', ...
    'HorizontalAlignment','center','FontSize',7.0,'Color',ink);
saveFigure(f,outDir,'fig_4_7_translation_consistency_and_finetuning');

%% Figure 4-8: edge and CD measurement
f = makeFigure(7.2,3.80);
main = canvas(f);
text(0.50,0.955,'Edge Sharpness and Critical-Dimension Measurement', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);

% Edge profile
simpleBox(0.025,0.14,0.31,0.72,[1 1 1],ink,0.9);
text(0.18,0.82,'(a) 10-90% edge width','HorizontalAlignment','center','FontSize',8.5,'FontWeight','bold','Color',ink);
ax=axes('Position',[0.065 0.31 0.24 0.38]);
x=linspace(-2.2,2.2,180); y=1./(1+exp(-2.7*x)); plot(ax,x,y,'Color',ink,'LineWidth',1.6); hold(ax,'on');
yline(ax,0.1,':','10%','Color',gray,'LabelHorizontalAlignment','left');
yline(ax,0.5,'--','50%','Color',gold,'LabelHorizontalAlignment','left');
yline(ax,0.9,':','90%','Color',gray,'LabelHorizontalAlignment','left');
x10=log(0.1/0.9)/2.7; x90=log(0.9/0.1)/2.7;
plot(ax,[x10 x10],[0 1],':','Color',blue); plot(ax,[x90 x90],[0 1],':','Color',blue);
patch(ax,[x10 x90 x90 x10],[0 0 1 1],lightBlue,'EdgeColor','none','FaceAlpha',0.45); uistack(findobj(ax,'Type','line'),'top');
grid(ax,'on'); box(ax,'on'); xlabel(ax,'Object-space distance'); ylabel(ax,'Normalized intensity');
axes(main);
text(0.18,0.22,'Narrower is sharper; ringing is checked separately.','HorizontalAlignment','center','FontSize',7.0,'Color',ink);

% CD boundary geometry
simpleBox(0.355,0.14,0.31,0.72,[1 1 1],ink,0.9);
text(0.51,0.82,'(b) Fixed center and local threshold','HorizontalAlignment','center','FontSize',8.5,'FontWeight','bold','Color',ink);
drawDisk(0.51,0.53,0.105,[0.23 0.23 0.23],ink,0.8);
for k=1:7
    yy=0.50+(k-4)*0.012; plot([0.405 0.615],[yy yy],'-','Color',gold,'LineWidth',0.6);
end
th=linspace(0,2*pi,24); for k=1:numel(th); plot([0.51 0.51+0.145*cos(th(k))],[0.53 0.53+0.145*sin(th(k))],'-','Color',blue,'LineWidth',0.35); end
rectangle('Position',[0.365 0.385 0.29 0.29],'Curvature',[1 1],'EdgeColor',gray,'LineStyle','--','LineWidth',0.9);
text(0.51,0.31,'Horizontal: center +/- 3 rows','HorizontalAlignment','center','FontSize',7.1,'Color',gold);
text(0.51,0.265,'Radial: 360 directions','HorizontalAlignment','center','FontSize',7.1,'Color',blue);
text(0.51,0.205,'Primary threshold = 50%; sweep = 35-65%','HorizontalAlignment','center','FontSize',7.1,'FontWeight','bold','Color',ink);

% Physical conversion and comparison
simpleBox(0.685,0.14,0.29,0.72,[1 1 1],ink,0.9);
text(0.83,0.82,'(c) Physical-unit comparison','HorizontalAlignment','center','FontSize',8.5,'FontWeight','bold','Color',ink);
simpleBox(0.72,0.62,0.22,0.10,light,ink,0.7); text(0.83,0.67,'Diameter in pixels','HorizontalAlignment','center','FontSize',7.3,'Color',ink);
drawArrow(f,0.83,0.83,0.61,ink,0.9);
simpleBox(0.72,0.45,0.22,0.10,lightBlue,ink,0.7); text(0.83,0.50,'x object-space pixel size','HorizontalAlignment','center','FontSize',7.3,'Color',ink);
drawArrow(f,0.83,0.83,0.44,ink,0.9);
simpleBox(0.72,0.28,0.22,0.10,lightGold,ink,0.7); text(0.83,0.33,'Optical CD in nm','HorizontalAlignment','center','FontSize',7.3,'Color',ink);
text(0.83,0.22,multiline('Compare each pillar with\nits own SEM CD'),'HorizontalAlignment','center','FontSize',6.7,'Color',red);
text(0.83,0.17,multiline('No method-specific re-centering\nor display enhancement'),'HorizontalAlignment','center','FontSize',5.9,'Color',ink);
saveFigure(f,outDir,'fig_4_8_edge_and_cd_measurement');

%% Figure 4-9: displacement tracking and locked selection
f = makeFigure(7.2,4.05);
main = canvas(f);
text(0.50,0.955,'Nine-Pillar Displacement Tracking and Fixed-Step Selection', ...
    'HorizontalAlignment','center','FontSize',9.6,'FontWeight','bold','Color',ink);

% Per-pillar boundary tracker
simpleBox(0.025,0.16,0.30,0.70,[1 1 1],ink,0.9);
text(0.175,0.82,'(a) Per-pillar boundary tracking','HorizontalAlignment','center','FontSize',8.4,'FontWeight','bold','Color',ink);
drawDisk(0.175,0.53,0.105,[0.25 0.25 0.25],ink,0.8);
fractions=[-0.55 -0.275 0 0.275 0.55];
for k=1:numel(fractions)
    yy=0.53+fractions(k)*0.105; half=0.105*sqrt(1-fractions(k)^2);
    plot([0.175-half 0.175+half],[yy yy],'-','Color',gold,'LineWidth',1.0);
    plot([0.175-half 0.175+half],[yy yy],'o','Color',blue,'MarkerFaceColor','w','MarkerSize',3);
end
plot([0.175 0.175],[0.40 0.66],'--','Color',red,'LineWidth',1.0);
text(0.175,0.36,'Five horizontal chords','HorizontalAlignment','center','FontSize',7.2,'FontWeight','bold','Color',gold);
text(0.175,0.29,multiline('Subpixel left and right edges\nCenter = midpoint; pillar position = median'), ...
    'HorizontalAlignment','center','FontSize',6.8,'Color',ink);
text(0.175,0.20,'Dark/bright polarity sets the gradient direction.','HorizontalAlignment','center','FontSize',6.7,'Color',ink);

% Nine-pillar consensus
simpleBox(0.35,0.16,0.28,0.70,[1 1 1],ink,0.9);
text(0.49,0.82,'(b) Nine-pillar consensus','HorizontalAlignment','center','FontSize',8.4,'FontWeight','bold','Color',ink);
for r=1:3
    for c=1:3
        cx=0.40+(c-1)*0.07; cy=0.51+(r-1)*0.10;
        drawDisk(cx,cy,0.014,[0.35 0.35 0.35],ink,0.5);
        annotation(f,'arrow',[cx cx+0.033],[cy cy],'Color',blue,'LineWidth',0.8,'HeadLength',5,'HeadWidth',5);
    end
end
text(0.49,0.43,'Step displacement = median of nine pillars','HorizontalAlignment','center','FontSize',6.8,'FontWeight','bold','Color',ink);
text(0.49,0.35,'Within-grid disagreement','HorizontalAlignment','center','FontSize',7.1,'Color',ink);
text(0.49,0.29,'1.4826 x median absolute deviation','HorizontalAlignment','center','FontSize',7.1,'Color',blue);
text(0.49,0.205,multiline('Lower disagreement means stronger\nspatial consistency.'),'HorizontalAlignment','center','FontSize',6.5,'Color',ink);

% Locked 30-step protocol
simpleBox(0.655,0.16,0.32,0.70,[1 1 1],ink,0.9);
text(0.815,0.82,'(c) Raw-locked 30-step protocol','HorizontalAlignment','center','FontSize',8.4,'FontWeight','bold','Color',ink);
ys=[0.71 0.585 0.46 0.335]; labels={multiline('All adjacent\nRaw pairs'),multiline('Remove session breaks\nand incomplete grids'), ...
    multiline('Apply 25% motion and\ncross-axis tolerance'),multiline('Rank Raw motion quality;\nkeep best 30 steps')};
fills={light,lightBlue,lightGold,lightGreen};
for i=1:4
    simpleBox(0.69,ys(i)-0.043,0.25,0.086,fills{i},ink,0.7);
    text(0.815,ys(i),labels{i},'HorizontalAlignment','center','FontSize',5.9,'Color',ink);
    if i<4; drawArrow(f,0.815,0.815,ys(i)-0.047,ink,0.8,ys(i+1)+0.047); end
end
text(0.815,0.245,multiline('The identical 30 steps are then used for\nRaw, Wiener, and proposed-model images.'), ...
    'HorizontalAlignment','center','FontSize',6.3,'FontWeight','bold','Color',red);
text(0.815,0.185,multiline('Nominal PI motion is a reference,\nnot independent truth.'), ...
    'HorizontalAlignment','center','FontSize',5.9,'Color',ink);
saveFigure(f,outDir,'fig_4_9_displacement_tracking_and_selection');

close all;
fprintf('Saved 9 Jack-style Chapter 4 figures to %s\n',outDir);
end

function f = makeFigure(widthIn,heightIn)
f=figure('Units','inches','Position',[1 1 widthIn heightIn],'Color','w');
set(f,'PaperPositionMode','auto');
end

function ax = canvas(f)
ax=axes(f,'Position',[0 0 1 1],'XLim',[0 1],'YLim',[0 1],'Visible','off','Tag','MainCanvas'); hold(ax,'on');
end

function simpleBox(x,y,w,h,fillColor,edgeColor,lineWidth)
rectangle('Position',[x y w h],'FaceColor',fillColor,'EdgeColor',edgeColor,'LineWidth',lineWidth);
end

function circleNumber(x,y,value,color)
rectangle('Position',[x-0.022 y-0.022 0.044 0.044],'Curvature',[1 1], ...
    'FaceColor','w','EdgeColor',color,'LineWidth',1.1);
text(x,y,num2str(value),'HorizontalAlignment','center','VerticalAlignment','middle', ...
    'FontSize',7.8,'FontWeight','bold','Color',color);
end

function drawArrow(f,x1,x2,y,color,lineWidth,varargin)
if isempty(varargin); y2=y; else; y2=varargin{1}; end
annotation(f,'arrow',[x1 x2],[y y2],'Color',color,'LineWidth',lineWidth, ...
    'HeadLength',6,'HeadWidth',6);
end

function drawDisk(cx,cy,r,fillColor,edgeColor,lineWidth)
rectangle('Position',[cx-r cy-r 2*r 2*r],'Curvature',[1 1], ...
    'FaceColor',fillColor,'EdgeColor',edgeColor,'LineWidth',lineWidth);
end

function drawRing(cx,cy,r,color)
rectangle('Position',[cx-r cy-r 2*r 2*r],'Curvature',[1 1], ...
    'FaceColor','w','EdgeColor',color,'LineWidth',0.8);
end

function drawMiniGrid(x,y,w,h,flipVertical,color)
for r=1:3
    for c=1:3
        rr=r; if flipVertical; rr=4-r; end
        cx=x+0.025+(c-1)*(w-0.05)/2;
        cy=y+0.025+(rr-1)*(h-0.05)/2;
        drawDisk(cx,cy,0.010,[0.34 0.34 0.34],color,0.4);
    end
end
rectangle('Position',[x y w h],'EdgeColor',[0.65 0.65 0.65],'LineWidth',0.6);
end

function imageAxes(pos,img,labelText)
ax=axes('Position',pos);
imagesc(ax,img); axis(ax,'image'); axis(ax,'off'); colormap(ax,repmat(linspace(0,1,256)',1,3));
title(ax,labelText,'FontSize',7.4,'FontWeight','normal','Color',[0.08 0.08 0.08]);
end

function img = readGraySafe(path)
if exist(path,'file')
    img=imread(path);
    if ndims(img)==3; img=mean(double(img),3); else; img=double(img); end
    if max(img(:))>1; img=img/255; end
else
    img=syntheticGrid(48,0);
end
end

function [gt,psf,pred] = syntheticPsfExample
n=81; [x,y]=meshgrid(1:n,1:n); gt=ones(n);
centers=[20 20;40 20;60 20;20 40;40 40;60 40;20 60;40 60;60 60];
for i=1:size(centers,1); gt(hypot(x-centers(i,1),y-centers(i,2))<=6)=0.12; end
[xp,yp]=meshgrid(linspace(-3,3,41));
psf=exp(-((xp-0.18).^2/0.65^2+(yp+0.08).^2/0.95^2)/2);
psf=psf+0.13*exp(-((xp+1.0).^2+(yp-0.8).^2)/0.55^2);
psf=psf/sum(psf(:));
pred=conv2(gt,psf,'same');
end

function img = syntheticGrid(n,invert)
[x,y]=meshgrid(1:n,1:n); img=0.86*ones(n);
cent=round(linspace(10,n-10,3));
for r=1:3
    for c=1:3
        mask=hypot(x-cent(c),y-cent(r))<=3.7;
        if invert; img(mask)=0.95; else; img(mask)=0.18; end
    end
end
if invert; img(~(img>0.90))=0.12; end
end

function img = syntheticMixedShapes(n)
[x,y]=meshgrid(1:n,1:n); img=0.88*ones(n);
img(hypot(x-13,y-14)<=5)=0.18;
img(abs(x-34)<=5 & abs(y-14)<=5)=0.28;
img(abs(x-14)+abs(y-34)<=7)=0.22;
img(((x-34)/7).^2+((y-34)/4).^2<=1)=0.30;
end

function out = multiline(in)
out=strrep(in,'\n',sprintf('\n'));
end

function saveFigure(f,outDir,baseName)
main=findobj(f,'Type','axes','Tag','MainCanvas');
if ~isempty(main); uistack(main,'bottom'); end
exportgraphics(f,fullfile(outDir,[baseName '.png']),'Resolution',300,'BackgroundColor','white');
exportgraphics(f,fullfile(outDir,[baseName '.pdf']),'ContentType','vector','BackgroundColor','white');
savefig(f,fullfile(outDir,[baseName '.fig']));
end
