function build_v20_traceability_figures()
    PROJECT_ROOT = fileparts(fileparts(fileparts(mfilename('fullpath'))));
% Build the traceability figures added to thesis v20.
% Every annotation is tied to the actual source frame and the locked
% coordinates used by the corresponding measurement package.

close all; clc;
root = fullfile(PROJECT_ROOT, 'Experiments/R66_V20_TraceabilityFigures_20260725');
out = fullfile(root, 'figures');
if ~exist(out, 'dir'), mkdir(out); end

rawStatic = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/20260618_100MG/Image__2026-06-18__17-10-31.bmp');
raw50 = fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp');
raw50b = fullfile(PROJECT_ROOT, '20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0001.bmp');
raw20 = fullfile(PROJECT_ROOT, '20260704_20x_5x_analysis/raw_inputs/20x_0p5um/bmp/frame_0000.bmp');
staticCenterTable = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/cd/tables/center9_cd_per_pillar.csv');

pillar50Initial = [24 1100.5 642.5; 23 1173.5 642.5; 22 1244.5 642.5; ...
                   30 1100.5 714.5; 29 1173.5 714.5; 28 1244.5 714.5; ...
                   36 1100.5 786.5; 35 1173.5 786.5; 34 1244.5 786.5];
pillar20Initial = [36 1962.8 863.0; 35 1991.8 863.0; 34 2020.8 863.0; ...
                   30 1962.8 892.0; 29 1991.8 892.0; 28 2020.8 892.0; ...
                   24 1962.8 921.0; 23 1991.8 921.0; 22 2020.8 921.0];
% The grid coordinates above identify each physical pillar.  For figures
% that show a sampling origin, estimate the local apparent centre once
% from the Raw frame and then hold it fixed across reconstruction methods.
pillar50 = refineDarkCenters(raw50, pillar50Initial, 31);
pillar20 = refineDarkCenters(raw20, pillar20Initial, 13);
static50 = readStaticCenters(staticCenterTable);

via50 = [1 798.6068 877.6695; 2 870.6223 876.6583; 3 942.9940 876.3266; ...
         4 800.1645 949.1002; 5 871.2066 949.9027; 6 943.6618 949.1032; ...
         7 800.1586 1023.0714; 8 871.9894 1021.9980; 9 944.3032 1021.2992];
% 20x is vertically flipped relative to the physical SEM row order.
via20 = [7 1665.0561 682.0335; 8 1694.1736 681.8984; 9 1723.2161 682.0527; ...
         4 1665.1516 711.1191; 5 1694.2046 711.0804; 6 1723.2534 710.9749; ...
         1 1665.1826 740.1390; 2 1694.2137 740.0101; 3 1723.3151 740.0453];

makeIdentity(rawStatic, static50, [716 936 634 854], 0.069, 'P', ...
    fullfile(out, '01_static_50x_pillar_identity.png'));
makeProfileLocation(raw50, pillar50, 29, 19.5, 0.069, ...
    fullfile(out, '02_50x_p29_radial_profile_location.png'));
makeProfileLocation(raw20, pillar20, 29, 7.6, 0.1725, ...
    fullfile(out, '03_20x_p29_radial_profile_location.png'));
makeCDSampling(rawStatic, static50, 29, static50(static50(:,1)==29,4), 0.069, ...
    fullfile(out, '04_50x_p29_cd_sampling_location.png'));
makeCDSampling(raw20, pillar20, 29, 7.6, 0.1725, ...
    fullfile(out, '05_20x_p29_cd_sampling_location.png'));
makeDisplacementSchematic(raw50, raw50b, pillar50, 19.5, 0.069, ...
    fullfile(out, '06_displacement_measurement_location.png'));
makeIdentity(raw50, via50, [770 974 850 1053], 0.069, 'V', ...
    fullfile(out, '07_50x_via_identity.png'));
makeIdentity(raw20, via20, [1656 1733 673 749], 0.1725, 'V', ...
    fullfile(out, '08_20x_via_identity.png'));
makeLineRegions(raw50, 0.069, fullfile(out, '09_line_measurement_regions.png'));

rawA = rawStatic;
fullA = fullfile(PROJECT_ROOT, 'Experiments/R63_CausalBoundaryMotionAblation/results/evaluation/reconstructions/full_control/seed1261200/static_50x_sem/Image__2026-06-18__17-10-31.bmp');
noA = fullfile(PROJECT_ROOT, 'Experiments/R63_CausalBoundaryMotionAblation/results/evaluation/reconstructions/no_raw_position_anchor/seed1261200/static_50x_sem/Image__2026-06-18__17-10-31.bmp');
makeComparison({rawA, fullA, noA}, {'Raw','完整模型','移除位置基準'}, ...
    [768 889 687 808], 0.069, fullfile(out, '10_ablation_p29_matched_comparison.png'));

naf50 = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/results/nafnet/real_inference/sequences/50x_x_0p5um/frame_0000.bmp');
eds50 = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/results/edsr/real_inference/sequences/50x_x_0p5um/frame_0000.bmp');
mos50 = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures/02_V42_E120_SOURCE_MATERIAL/reconstructions/50x_0p5um/frame_0000.bmp');
makeComparison({raw50, naf50, eds50, mos50}, {'Raw','NAFNet','EDSR-x1','MOSR'}, ...
    [1065 1281 607 823], 0.069, fullfile(out, '11_multimodel_50x_pillar_matched_comparison.png'));
makeComparison({raw50, naf50, eds50, mos50}, {'Raw','NAFNet','EDSR-x1','MOSR'}, ...
    [763 981 841 1060], 0.069, fullfile(out, '12_multimodel_50x_via_matched_comparison.png'));
makeIdentity(raw50, pillar50, [1072 1273 614 815], 0.069, 'P', ...
    fullfile(out, '13_50x_sequence_pillar_identity.png'));
makeIdentity(raw20, pillar20, [1953 2030 853 930], 0.1725, 'P', ...
    fullfile(out, '14_20x_sequence_pillar_identity.png'));

writeManifest(root, out);
fprintf('V20 traceability figures complete: %s\n', out);
end

function makeIdentity(path, points, lim, umpx, prefix, outPath)
I = readGray(path);
f = baseFigure(15.5, 12.0);
ax = axes(f); showImage(ax, I, lim, []);
hold(ax,'on');
for k = 1:size(points,1)
    x = points(k,2); y = points(k,3);
    text(ax,x,y-0.20*(lim(4)-lim(3))/3,sprintf('%s%d',prefix,points(k,1)), ...
        'HorizontalAlignment','center','VerticalAlignment','bottom', ...
        'FontName','Times New Roman','FontSize',9,'FontWeight','bold', ...
        'Color','w','BackgroundColor',[0.12 0.12 0.12],'Margin',1.5);
end
drawScale(ax, lim, umpx, 5);
finish(f,outPath);
end

function makeProfileLocation(path, points, id, radius, umpx, outPath)
I = readGray(path);
p = points(points(:,1)==id,:);
pad = max(2.4*radius, 22);
lim = [p(2)-pad p(2)+pad p(3)-pad p(3)+pad];
f = baseFigure(13.0, 11.0); ax=axes(f); showImage(ax,I,lim,[]); hold(ax,'on');
th = linspace(0,2*pi,360);
plot(ax,p(2)+radius*cos(th),p(3)+radius*sin(th),'--','Color',[0.00 0.45 0.74],'LineWidth',1.2);
angles = deg2rad(0:30:330);
for a = angles
    plot(ax,[p(2) p(2)+1.52*radius*cos(a)],[p(3) p(3)-1.52*radius*sin(a)], ...
        '-','Color',[0.45 0.65 0.78],'LineWidth',0.6);
end
ang = deg2rad(30);
plot(ax,[p(2) p(2)+1.52*radius*cos(ang)],[p(3) p(3)-1.52*radius*sin(ang)], ...
    '-','Color',[0.85 0.33 0.10],'LineWidth',2);
plot(ax,p(2),p(3),'o','Color',[0.00 0.45 0.74],'MarkerFaceColor','w', ...
    'LineWidth',1.3,'MarkerSize',5);
text(ax,0.04,0.06,'P29','Units','normalized','Color','w','FontWeight','bold', ...
    'FontName','Times New Roman','FontSize',10,'BackgroundColor',[0.12 0.12 0.12], ...
    'Margin',1.5,'VerticalAlignment','top');
drawScale(ax,lim,umpx,2);
finish(f,outPath);
end

function makeCDSampling(path, points, id, radius, umpx, outPath)
I = readGray(path); p=points(points(:,1)==id,:);
margin=max(28,1.35*radius);
halfWindow=radius+margin;
pad=halfWindow+5;
lim=[p(2)-pad p(2)+pad p(3)-pad p(3)+pad];
f=baseFigure(13.0,11.0); ax=axes(f); showImage(ax,I,lim,[]); hold(ax,'on');
% The estimator first averages center_row-3:center_row+3 into one profile.
y0=round(p(3));
x1=p(2)-halfWindow; x2=p(2)+halfWindow;
patch(ax,[x1 x2 x2 x1],[y0-3.5 y0-3.5 y0+3.5 y0+3.5], ...
    [0.85 0.33 0.10],'FaceAlpha',0.24,'EdgeColor',[0.85 0.33 0.10],'LineWidth',1.1);
plot(ax,[x1 x2],[y0 y0],'--','Color',[0.85 0.33 0.10],'LineWidth',1.1);
plot(ax,p(2),p(3),'o','Color',[0.00 0.45 0.74],'MarkerFaceColor','w', ...
    'LineWidth',1.3,'MarkerSize',5);
drawScale(ax,lim,umpx,2); finish(f,outPath);
end

function makeDisplacementSchematic(path1,path2,points,radius,umpx,outPath)
I1=readGray(path1); I2=readGray(path2);
p=points(points(:,1)==29,:); pad=2.4*radius;
lim1=[p(2)-pad p(2)+pad p(3)-pad p(3)+pad];
% The adjacent-frame search begins from the previous Raw track plus the
% nominal expected step. Platform feedback is not used to steer the search.
dx=-0.5/umpx; p2=[p(2)+dx p(3)]; lim2=[p2(1)-pad p2(1)+pad p2(2)-pad p2(2)+pad];
cl=[0 255];
f=baseFigure(17.0,8.5);
ax1=subplot(1,2,1,'Parent',f); showImage(ax1,I1,lim1,cl); hold(ax1,'on');
% Exact chord fractions used by the locked maximum-gradient tracker.
ys=p(3)+[-0.55 -0.275 0 0.275 0.55]*radius;
for y=ys, plot(ax1,[p(2)-1.5*radius p(2)+1.5*radius],[y y],'-','Color',[0.85 0.33 0.10],'LineWidth',1.0); end
plot(ax1,[p(2) p(2)],[p(3)-0.18*radius p(3)+0.18*radius], ...
    '-','Color',[0.00 0.45 0.74],'LineWidth',1.7);
text(ax1,0.04,0.95,'(a)','Units','normalized','Color','w','FontSize',10,'FontWeight','bold','VerticalAlignment','top');
ax2=subplot(1,2,2,'Parent',f); showImage(ax2,I2,lim2,cl); hold(ax2,'on');
[leftEdge,rightEdge,measuredCenter,edgeHalfWidth] = centralChordMeasurement(I2,p2,radius,8.0);
bandHalfHeight=0.14*radius;
patch(ax2,[p2(1)-radius-edgeHalfWidth p2(1)-radius+edgeHalfWidth ...
           p2(1)-radius+edgeHalfWidth p2(1)-radius-edgeHalfWidth], ...
          [p2(2)-bandHalfHeight p2(2)-bandHalfHeight ...
           p2(2)+bandHalfHeight p2(2)+bandHalfHeight], ...
          [0.00 0.45 0.74],'FaceAlpha',0.12,'EdgeColor',[0.45 0.65 0.78], ...
          'LineStyle','--','LineWidth',1.0);
patch(ax2,[p2(1)+radius-edgeHalfWidth p2(1)+radius+edgeHalfWidth ...
           p2(1)+radius+edgeHalfWidth p2(1)+radius-edgeHalfWidth], ...
          [p2(2)-bandHalfHeight p2(2)-bandHalfHeight ...
           p2(2)+bandHalfHeight p2(2)+bandHalfHeight], ...
          [0.00 0.45 0.74],'FaceAlpha',0.12,'EdgeColor',[0.45 0.65 0.78], ...
          'LineStyle','--','LineWidth',1.0);
plot(ax2,[p2(1)-1.55*radius p2(1)+1.55*radius],[p2(2) p2(2)], ...
    '-','Color',[0.85 0.33 0.10],'LineWidth',1.1);
plot(ax2,[leftEdge rightEdge],[p2(2) p2(2)],'o','Color',[0.85 0.33 0.10], ...
    'MarkerFaceColor',[0.85 0.33 0.10],'MarkerSize',5);
plot(ax2,[measuredCenter measuredCenter], ...
    [p2(2)-0.18*radius p2(2)+0.18*radius], ...
    '-','Color',[0.00 0.45 0.74],'LineWidth',1.7);
text(ax2,0.04,0.95,'(b)','Units','normalized','Color','w','FontSize',10,'FontWeight','bold','VerticalAlignment','top');
finish(f,outPath);
end

function makeLineRegions(path,umpx,outPath)
I=readGray(path); lim=[70 1780 60 1440];
f=baseFigure(16.0,12.0); ax=axes(f); showImage(ax,I,lim,[]); hold(ax,'on');
rectangle(ax,'Position',[100 90 700 560],'EdgeColor',[0.00 0.45 0.74],'LineWidth',2);
rectangle(ax,'Position',[1050 850 700 560],'EdgeColor',[0.85 0.33 0.10],'LineWidth',2);
% Median profiles run perpendicular to the line direction.
plot(ax,[150 750],[370 370],'-','Color',[0.00 0.45 0.74],'LineWidth',2);
plot(ax,[1400 1400],[900 1360],'-','Color',[0.85 0.33 0.10],'LineWidth',2);
drawScale(ax,lim,umpx,20); finish(f,outPath);
end

function makeComparison(paths,labels,lim,umpx,outPath)
imgs=cellfun(@readGray,paths,'UniformOutput',false);
% Preserve the native 8-bit intensity scale. No per-image or pooled
% percentile stretching is used in method-comparison figures.
cl=[0 255];
f=baseFigure(17.5,5.5);
for k=1:numel(imgs)
    ax=subplot(1,numel(imgs),k,'Parent',f); showImage(ax,imgs{k},lim,cl);
    hold(ax,'on');
    text(ax,0.5,1.035,labels{k},'Units','normalized','HorizontalAlignment','center', ...
        'FontName','Microsoft JhengHei','FontSize',9,'Color','k');
    if k==1, drawScale(ax,lim,umpx,5); end
end
finish(f,outPath);
end

function I=readGray(path)
assert(isfile(path),'Missing source: %s',path);
I=imread(path);
if ndims(I)==3, I=rgb2gray(I); end
I=double(I);
end

function f=baseFigure(w,h)
f=figure('Color','w','Units','centimeters','Position',[2 2 w h],'Visible','off');
end

function showImage(ax,I,lim,cl)
if isempty(cl), cl=[0 255]; end
imagesc(ax,[1 size(I,2)],[1 size(I,1)],I,cl);
axis(ax,'image'); axis(ax,'ij'); xlim(ax,lim(1:2)); ylim(ax,lim(3:4));
colormap(ax,gray(256)); set(ax,'XTick',[],'YTick',[],'Box','on','LineWidth',0.8);
end

function C=cropByLimits(I,lim)
x1=max(1,round(lim(1))); x2=min(size(I,2),round(lim(2)));
y1=max(1,round(lim(3))); y2=min(size(I,1),round(lim(4)));
C=I(y1:y2,x1:x2);
end

function drawScale(ax,lim,umpx,lengthUm)
len=lengthUm/umpx; x2=lim(2)-0.07*(lim(2)-lim(1)); x1=x2-len;
y=lim(4)-0.08*(lim(4)-lim(3));
plot(ax,[x1 x2],[y y],'w-','LineWidth',3);
plot(ax,[x1 x2],[y y],'-','Color',[0.05 0.05 0.05],'LineWidth',5);
plot(ax,[x1 x2],[y y],'w-','LineWidth',3);
text(ax,(x1+x2)/2,y-0.035*(lim(4)-lim(3)),sprintf('%g µm',lengthUm), ...
    'Color','w','HorizontalAlignment','center','VerticalAlignment','bottom', ...
    'FontName','Times New Roman','FontSize',8,'FontWeight','bold', ...
    'BackgroundColor',[0.10 0.10 0.10],'Margin',1);
end

function centers=readStaticCenters(path)
assert(isfile(path),'Missing center table: %s',path);
T=readtable(path,'Delimiter',',','ReadVariableNames',true,'VariableNamingRule','preserve');
centers=[str2double(string(T{:,2})),str2double(string(T{:,15})), ...
    str2double(string(T{:,16})),str2double(string(T{:,21}))];
end

function centers=refineDarkCenters(path, initialCenters, searchRadius)
% Estimate each dark pillar's apparent centre from the Raw frame only.
% This is a local intensity-weighted centroid inside the predeclared grid
% neighbourhood; it is never re-estimated from Wiener or model outputs.
I=readGray(path);
[xx,yy]=meshgrid(1:size(I,2),1:size(I,1));
centers=initialCenters;
for k=1:size(initialCenters,1)
    x0=initialCenters(k,2); y0=initialCenters(k,3);
    mask=hypot(xx-x0,yy-y0)<=searchRadius;
    local=I(mask);
    background=prctile(local,90);
    weights=max(background-I,0).*mask;
    denom=sum(weights,'all');
    assert(denom>0,'Unable to refine centre for feature %g',initialCenters(k,1));
    centers(k,2)=sum(weights.*xx,'all')/denom;
    centers(k,3)=sum(weights.*yy,'all')/denom;
end
end

function [leftEdge,rightEdge,centerX,halfWidth]=centralChordMeasurement(I,predicted,radius,searchRadius)
profile = double(interp2(I,1:size(I,2),predicted(2)*ones(1,size(I,2)),'linear'));
g = gradient(profile);
leftScore = -g;
rightScore = g;
halfWidth = searchRadius + max(1.0,radius*0.28);
leftEdge = edgeFromWindow(leftScore,predicted(1)-radius,halfWidth);
rightEdge = edgeFromWindow(rightScore,predicted(1)+radius,halfWidth);
centerX = 0.5*(leftEdge+rightEdge);
end

function x=edgeFromWindow(score,expected,halfWidth)
lo=max(2,ceil(expected-halfWidth));
hi=min(numel(score)-1,floor(expected+halfWidth));
[~,local]=max(score(lo:hi));
idx=lo+local-1;
y1=score(idx-1); y2=score(idx); y3=score(idx+1);
den=y1-2*y2+y3;
delta=0;
if abs(den)>eps, delta=0.5*(y1-y3)/den; end
delta=max(-0.5,min(0.5,delta));
x=idx+delta;
end

function finish(f,outPath)
set(findall(f,'-property','FontName'),'FontName','Times New Roman');
exportgraphics(f,outPath,'Resolution',600,'BackgroundColor','white');
savefig(f,strrep(outPath,'.png','.fig'));
exportgraphics(f,strrep(outPath,'.png','.pdf'),'ContentType','vector','BackgroundColor','white');
close(f);
end

function writeManifest(root,out)
files=dir(fullfile(out,'*.png'));
fid=fopen(fullfile(root,'figure_manifest.csv'),'w','n','UTF-8');
fprintf(fid,'figure_file,bytes,source_rule\n');
for k=1:numel(files)
    fprintf(fid,'"%s",%d,"%s"\n',files(k).name,files(k).bytes, ...
        'Actual source frame; locked coordinates; native 8-bit display range');
end
fclose(fid);
end
