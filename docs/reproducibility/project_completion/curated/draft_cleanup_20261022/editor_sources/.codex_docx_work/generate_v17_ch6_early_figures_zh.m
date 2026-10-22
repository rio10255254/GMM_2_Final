function generate_v17_ch6_early_figures_zh()
%GENERATE_V17_CH6_EARLY_FIGURES_ZH Redraw Chapter 6 figures with Chinese labels.

close all;
outDir = 'D:\GMM_2_Final\PSF_Fitting\.codex_docx_work\v17_chinese_figures\early';
if ~exist(outDir, 'dir'), mkdir(outDir); end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Microsoft JhengHei');
set(groot, 'defaultTextFontName', 'Microsoft JhengHei');
set(groot, 'defaultAxesFontSize', 10.5);
set(groot, 'defaultAxesLineWidth', 0.85);
set(groot, 'defaultLineLineWidth', 1.5);

root = ['D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\' ...
    '03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit'];
figureRoot = fullfile(root, 'figures', 'center9_pillar_fit_20x_50x');
sourceRoot = fullfile(root, 'source_data', 'center9_pillar_fit_20x_50x');
tableRoot = fullfile(root, 'tables', 'center9_pillar_fit_20x_50x');
deconvRoot = fullfile(sourceRoot, 'psf_deconvolution_cd');
auditRoot = fullfile(sourceRoot, 'sharpness_validation');
payload = load(fullfile(auditRoot, 'matlab_cd_sharpness_plot_data.mat'));

% Figures 6-1, 6-2, 6-18 and 6-19: absolute FFT amplitude on a shared scale.
for label = ["20x", "50x"]
    captured = readGrayDouble(fullfile(figureRoot, label, '05_original_pillar_3x3.bmp'));
    wienerData = load(fullfile(deconvRoot, label + "_wiener_deconvolution.mat"));
    drawSpectrum(captured, strrep(label, "x", " 倍") + "拍攝影像之空間頻譜", ...
        'FFT 絕對振幅；統一使用 -80 至 0 dBFS 色階', ...
        fullfile(outDir, "fig6-" + spectrumNumber(label, false) + "_zh.png"));
    drawSpectrum(double(wienerData.restored), strrep(label, "x", " 倍") + " Wiener 反卷積之空間頻譜", ...
        '未截幅反卷積結果；NSR = 0.05；統一使用 -80 至 0 dBFS 色階', ...
        fullfile(outDir, "fig6-" + spectrumNumber(label, true) + "_zh.png"));
end

% Figures 6-4 and 6-5: fitted PSFs.
fitRoot = 'D:\GMM_2_Final\PSF_Fitting\output\deconvolution_baseline_psf_20260715';
drawPSF(fullfile(fitRoot, '50x', 'fit_result', 'PSF_fitted_2D_FOVstack.mat'), ...
    '50 倍擬合點擴散函數', fullfile(outDir, 'fig6-04_zh.png'));
drawPSF(fullfile(fitRoot, '20x', 'fit_result', 'PSF_fitted_2D_FOVstack.mat'), ...
    '20 倍擬合點擴散函數', fullfile(outDir, 'fig6-05_zh.png'));

% Figures 6-6 and 6-11 to 6-17.
drawCdMethod(payload, fullfile(outDir, 'fig6-06_zh.png'));
drawEdgeProfile(payload, '20x', fullfile(outDir, 'fig6-11_zh.png'));
drawEdgeProfile(payload, '50x', fullfile(outDir, 'fig6-12_zh.png'));

rawWidth = [mean(payload.m20x_raw_edge_width_px)*payload.m20x_pixel_um; ...
    mean(payload.m50x_raw_edge_width_px)*payload.m50x_pixel_um];
wienerWidth = [mean(payload.m20x_deconvolved_edge_width_px)*payload.m20x_pixel_um; ...
    mean(payload.m50x_deconvolved_edge_width_px)*payload.m50x_pixel_um];
drawGroupedBars([rawWidth, wienerWidth], {'20 倍','50 倍'}, ...
    '平均 10–90% 邊緣寬度 (µm)', 'Pillar 邊緣過渡寬度', ...
    '數值越低表示灰階過渡越集中', '%.3f', fullfile(outDir, 'fig6-13_zh.png'));

summary = readtable(fullfile(tableRoot, 'cd_before_after_summary.csv'), ...
    'VariableNamingRule', 'preserve');
drawGroupedBars([summary.raw_mae_nm, summary.deconvolved_mae_nm], {'20 倍','50 倍'}, ...
    '平均 CD 絕對誤差 (nm)', '固定 50% 邊界下的 CD 誤差', ...
    '以已知 SEM 直徑作為一致性參考', '%.1f', fullfile(outDir, 'fig6-14_zh.png'));

sensitivity = readtable(fullfile(tableRoot, 'cd_threshold_sensitivity.csv'), ...
    'VariableNamingRule', 'preserve');
drawThreshold(sensitivity, '20x', fullfile(outDir, 'fig6-15_zh.png'));
drawThreshold(sensitivity, '50x', fullfile(outDir, 'fig6-16_zh.png'));
drawGroupedBars(100.*[summary.raw_max_ringing_ratio, summary.deconvolved_max_ringing_ratio], ...
    {'20 倍','50 倍'}, '最大振鈴比例 (%)', '九顆 pillar 周圍的最強局部振鈴', ...
    '反向徑向變化相對於向外邊緣上升量的比例', '%.1f%%', ...
    fullfile(outDir, 'fig6-17_zh.png'));

% Figure 6-20: training losses.
trainingPath = ['D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Model_Packages\' ...
    'V42_SoftLabelSNR_FullStandalone_20260709\results\training_results\' ...
    'training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713\' ...
    'V42_SoftLabelSNR_full_training_20260709_202710_val_log_v5.csv'];
training = readmatrix(trainingPath, 'NumHeaderLines', 1);
drawTraining(training(:,1), training(:,5:7), fullfile(outDir, 'fig6-20_zh.png'));

% Figures 6-21 and 6-22: full-FOV locators.
rerunRoot = ['D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\' ...
    '04_V42_NEURAL_NETWORK_RESULTS\source_validation\rerun_20260715\inputs'];
raw50 = imread(fullfile(rerunRoot, '50x_0p5um_latest', 'frame_0000.bmp'));
centers50 = [1100.5,642.5;1173.5,642.5;1244.5,642.5;1100.5,714.5; ...
    1173.5,714.5;1244.5,714.5;1100.5,786.5;1173.5,786.5;1244.5,786.5];
crop50 = cropAroundCenters(centers50, 72.5*0.65, size(raw50));
drawLocator(raw50, centers50, crop50, 72.5, 'upper_right', 'lower_left', ...
    0.069, 20, '50 倍 Raw 完整視野結構定位', fullfile(outDir, 'fig6-21_zh.png'));

raw20 = imread(fullfile(rerunRoot, '20x_0p5um_latest', 'frame_0000.bmp'));
centers20 = [1962.8,863.0;1991.8,863.0;2020.8,863.0;1962.8,892.0; ...
    1991.8,892.0;2020.8,892.0;1962.8,921.0;1991.8,921.0;2020.8,921.0];
crop20 = cropAroundCenters(centers20, 29.0*0.65, size(raw20));
drawLocator(raw20, centers20, crop20, 29.0, 'lower_right', 'upper_left', ...
    0.1725, 50, '20 倍 Raw 完整視野結構定位', fullfile(outDir, 'fig6-22_zh.png'));

fprintf('Chinese Chapter 6 early figures written to %s\n', outDir);
end

function n = spectrumNumber(label, isWiener)
if ~isWiener
    if label == "50x", n = "01"; else, n = "02"; end
else
    if label == "50x", n = "19"; else, n = "18"; end
end
end

function drawSpectrum(source, titleText, subtitleText, outputPath)
amplitude = abs(fftshift(fft2(double(source)))) / numel(source);
dbfs = 20*log10(max(amplitude, realmin('double')));
[h,w] = size(dbfs);
fx = (-floor(w/2):ceil(w/2)-1)/w;
fy = (-floor(h/2):ceil(h/2)-1)/h;
fig = figure('Color','white','Position',[100 100 900 700]);
ax = axes(fig);
imagesc(ax, fx, fy, dbfs); axis(ax,'xy'); axis(ax,'image');
clim(ax,[-80 0]); colormap(ax,parula(256));
cb = colorbar(ax); cb.Label.String = 'FFT 振幅 (dBFS)';
xlabel(ax,'空間頻率 x (cycles/pixel)'); ylabel(ax,'空間頻率 y (cycles/pixel)');
title(ax,titleText,'FontWeight','normal','FontSize',14);
subtitle(ax,subtitleText,'FontSize',10);
exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawPSF(matPath, titleText, outputPath)
d = load(matPath,'psf_grid'); psf = double(d.psf_grid); psf = psf/sum(psf(:));
fig = figure('Color','white','Position',[100 100 800 680]); ax = axes(fig);
imagesc(ax,psf); axis(ax,'image'); axis(ax,'off'); colormap(ax,parula(256));
cb = colorbar(ax); cb.Label.String = 'PSF 強度';
title(ax,titleText,'FontWeight','normal','FontSize',14);
exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawCdMethod(s, outputPath)
gold=[0.90 0.56 0.05]; teal=[0.05 0.57 0.58]; dark=[0.16 0.17 0.18];
grayColor=[0.42 0.44 0.47]; lightBlue=[0.76 0.86 0.95]; blue=[0.12 0.40 0.70];
fig=figure('Color','white','Position',[80 80 1150 560]);
t=tiledlayout(fig,1,2,'TileSpacing','compact','Padding','compact');
pillarIndex=5; center=s.m50x_centers_xy(pillarIndex,:); pitch=s.m50x_pitch_px;
r50=s.m50x_raw_r50_px(pillarIndex,:); angles=s.m50x_raw_angles_rad;
ax1=nexttile(t,1); imagesc(ax1,s.m50x_raw_image); axis(ax1,'image'); colormap(ax1,gray(256));
halfRange=0.43*pitch; xlim(ax1,center(1)+[-halfRange halfRange]); ylim(ax1,center(2)+[-halfRange halfRange]);
set(ax1,'YDir','reverse','XTick',[],'YTick',[]); hold(ax1,'on'); theta=linspace(0,2*pi,361);
plot(ax1,center(1)+r50.*cos(angles),center(2)+r50.*sin(angles),'Color',gold,'LineWidth',1.7,'DisplayName','50% 對比邊界');
plot(ax1,center(1)+0.07*pitch*cos(theta),center(2)+0.07*pitch*sin(theta),'--','Color',teal,'DisplayName','核心灰階區');
plot(ax1,center(1)+0.30*pitch*cos(theta),center(2)+0.30*pitch*sin(theta),':','Color',teal,'HandleVisibility','off');
plot(ax1,center(1)+0.36*pitch*cos(theta),center(2)+0.36*pitch*sin(theta),':','Color',teal,'DisplayName','背景環帶');
pairAngle=25; opposite=205; p1=center+r50(pairAngle+1)*[cosd(pairAngle),sind(pairAngle)];
p2=center+r50(opposite+1)*[cosd(opposite),sind(opposite)];
plot(ax1,[p1(1) p2(1)],[p1(2) p2(2)],'-','Color',[0.95 0.95 0.95],'LineWidth',1.5,'DisplayName','相對方向直徑');
plot(ax1,[p1(1) p2(1)],[p1(2) p2(2)],'o','Color',[0.95 0.95 0.95],'MarkerFaceColor',dark,'MarkerSize',4,'HandleVisibility','off');
title(ax1,'(a) 影像中的邊界判定','FontWeight','normal');
legend(ax1,'Location','southoutside','NumColumns',2,'FontSize',9,'Box','off');

ax2=nexttile(t,2); radii=s.m50x_raw_radii_px*s.m50x_pixel_um;
profile=s.m50x_raw_median_profile(pillarIndex,:);
r10=median(s.m50x_raw_r10_px(pillarIndex,:),'omitnan')*s.m50x_pixel_um;
r50m=median(s.m50x_raw_r50_px(pillarIndex,:),'omitnan')*s.m50x_pixel_um;
r90=median(s.m50x_raw_r90_px(pillarIndex,:),'omitnan')*s.m50x_pixel_um;
hold(ax2,'on'); patch(ax2,[r10 r90 r90 r10],[-0.15 -0.15 1.22 1.22],lightBlue,'FaceAlpha',0.45,'EdgeColor','none','DisplayName','10–90% 邊緣寬度');
plot(ax2,radii,profile,'Color',dark,'LineWidth',1.7,'DisplayName','360 個徑向剖面中位數');
yline(ax2,0.10,':','10%','Color',grayColor,'LabelHorizontalAlignment','left','HandleVisibility','off');
yline(ax2,0.50,'--','50%','Color',gold,'LabelHorizontalAlignment','left','HandleVisibility','off');
yline(ax2,0.90,':','90%','Color',grayColor,'LabelHorizontalAlignment','left','HandleVisibility','off');
xline(ax2,r10,':','Color',blue,'HandleVisibility','off'); xline(ax2,r50m,'--','Color',gold,'HandleVisibility','off'); xline(ax2,r90,':','Color',blue,'HandleVisibility','off');
xlabel(ax2,'距 pillar 中心的徑向距離 (µm)'); ylabel(ax2,'正規化強度');
xlim(ax2,[0 0.38*pitch*s.m50x_pixel_um]); ylim(ax2,[-0.12 1.18]); grid(ax2,'on'); ax2.GridAlpha=0.14;
title(ax2,'(b) 10%、50% 與 90% 對比交點','FontWeight','normal');
text(ax2,0.03,0.97,{'CD = r_{50}(\theta)+r_{50}(\theta+\pi)','邊緣寬度 = r_{90}-r_{10}'},'Units','normalized','VerticalAlignment','top','FontSize',9,'BackgroundColor','white','Margin',3,'Interpreter','tex');
legend(ax2,'Location','southeast','Box','off','FontSize',9);
exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawEdgeProfile(s, label, outputPath)
if strcmp(label,'20x')
    x=s.m20x_raw_distance_um; raw=s.m20x_raw_aligned_median; win=s.m20x_deconvolved_aligned_median; limits=[-0.80 0.55]; mag='20 倍';
else
    x=s.m50x_raw_distance_um; raw=s.m50x_raw_aligned_median; win=s.m50x_deconvolved_aligned_median; limits=[-0.60 0.55]; mag='50 倍';
end
fig=figure('Color','white','Position',[100 100 900 560]); ax=axes(fig); hold(ax,'on');
plot(ax,x,raw,'-','Color',[0.42 0.44 0.47],'LineWidth',1.8,'DisplayName','Raw');
plot(ax,x,win,'-','Color',[0.12 0.40 0.70],'LineWidth',2.0,'DisplayName','Wiener');
yline(ax,0.10,':','Color',[0.65 0.65 0.65],'HandleVisibility','off'); yline(ax,0.90,':','Color',[0.65 0.65 0.65],'HandleVisibility','off'); xline(ax,0,'--','Color',[0.72 0.72 0.72],'HandleVisibility','off');
xlabel(ax,'相對 50% 邊界的位置 (µm)'); ylabel(ax,'正規化強度');
title(ax,[mag ' pillar 徑向邊緣剖面'],'FontWeight','normal','FontSize',14);
subtitle(ax,'九顆 pillar、每顆 360 個方向的中位數','FontSize',10.5);
xlim(ax,limits); ylim(ax,[-0.18 1.25]); grid(ax,'on'); ax.XGrid='off'; ax.GridAlpha=0.18;
legend(ax,'Location','southeast','Box','off'); exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawGroupedBars(values, ticks, yText, titleText, subtitleText, numberFormat, outputPath)
colors=[0.42 0.44 0.47;0.12 0.40 0.70];
fig=figure('Color','white','Position',[100 100 900 560]); ax=axes(fig);
b=bar(ax,values,'grouped','BarWidth',0.76); b(1).FaceColor=colors(1,:); b(2).FaceColor=colors(2,:);
b(1).DisplayName='Raw'; b(2).DisplayName='Wiener'; xticks(ax,1:size(values,1)); xticklabels(ax,ticks);
ylabel(ax,yText); title(ax,titleText,'FontWeight','normal','FontSize',14); subtitle(ax,subtitleText,'FontSize',10.5);
grid(ax,'on'); ax.XGrid='off'; ax.GridAlpha=0.18; legend(ax,'Location','northoutside','Orientation','horizontal','Box','off');
ylim(ax,[0 1.23*max(values,[],'all')]);
for j=1:size(values,2), for i=1:size(values,1)
    text(ax,b(j).XEndPoints(i),b(j).YEndPoints(i),sprintf(numberFormat,values(i,j)),'HorizontalAlignment','center','VerticalAlignment','bottom','FontSize',10);
end, end
exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawThreshold(tbl, label, outputPath)
rows=tbl(strcmp(string(tbl.magnification),label),:); x=100.*rows.contrast_fraction;
fig=figure('Color','white','Position',[100 100 900 560]); ax=axes(fig); hold(ax,'on');
plot(ax,x,rows.raw_mae_nm,'-o','Color',[0.42 0.44 0.47],'MarkerFaceColor','white','LineWidth',1.8,'DisplayName','Raw');
plot(ax,x,rows.deconvolved_mae_nm,'-o','Color',[0.12 0.40 0.70],'MarkerFaceColor',[0.12 0.40 0.70],'LineWidth',2.0,'DisplayName','Wiener');
xlabel(ax,'相對邊緣閾值 (%)'); ylabel(ax,'平均 CD 絕對誤差 (nm)');
title(ax,[strrep(label,'x',' 倍') ' CD 閾值敏感度'],'FontWeight','normal','FontSize',14);
subtitle(ax,'每個閾值皆使用相同影像、中心位置與 SEM 直徑','FontSize',10.5);
xticks(ax,[40 50 60]); xlim(ax,[38 62]); grid(ax,'on'); ax.XGrid='off'; ax.GridAlpha=0.18;
legend(ax,'Location','north','Orientation','horizontal','Box','off'); exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawTraining(epoch, losses, outputPath)
normalized=100.*losses./losses(1,:);
reductions=100.*(1-losses(end,:)./losses(1,:));
fig=figure('Color','white','Position',[100 100 920 550]); ax=axes(fig); hold(ax,'on');
plot(ax,epoch,normalized(:,1),'-','Color',[0.64 0.33 0.18],'DisplayName',sprintf('重建損失（下降 %.1f%%）',reductions(1)));
plot(ax,epoch,normalized(:,2),'-','Color',[0.10 0.42 0.67],'DisplayName',sprintf('梯度幅值損失（下降 %.1f%%）',reductions(2)));
plot(ax,epoch,normalized(:,3),'-','Color',[0.78 0.57 0.10],'DisplayName',sprintf('邊緣方向損失（下降 %.1f%%）',reductions(3)));
yline(ax,100,'--','Color',[0.35 0.35 0.35],'HandleVisibility','off');
xlabel(ax,'訓練週期'); ylabel(ax,'相對第 1 週期的損失 (%)');
title(ax,'MOSR 訓練損失組成','FontWeight','normal','FontSize',14);
subtitle(ax,'未平滑的逐週期數值；第 1 週期 = 100%','FontSize',10.5);
xlim(ax,[1 120]); finite=normalized(isfinite(normalized)); ylim(ax,[max(0,min(finite)-5),max(finite)+5]);
grid(ax,'on'); ax.XGrid='off'; ax.GridAlpha=0.18; legend(ax,'Location','best','Box','off');
exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function drawLocator(image, centers, cropRect, pitch, pillarQuadrant, innerCorner, umPerPx, scaleBarUm, titleText, outputPath)
if ndims(image)==3, image=rgb2gray(image); end
if contains(string(innerCorner),'left'), centerX=min(centers(:,1))-0.75*pitch; else, centerX=max(centers(:,1))+0.75*pitch; end
if contains(string(innerCorner),'upper'), centerY=min(centers(:,2))-0.75*pitch; else, centerY=max(centers(:,2))+0.75*pitch; end
sampleCenter=[min(max(centerX,1),size(image,2)),min(max(centerY,1),size(image,1))];
fig=figure('Color','white','Position',[80 80 1000 760]); ax=axes(fig); imagesc(ax,image,[0 255]); colormap(ax,gray(256)); axis(ax,'image'); axis(ax,'off');
title(ax,titleText,'FontWeight','normal','FontSize',14); hold(ax,'on');
pillarColor=[0.86 0.22 0.16]; viaColor=[0.00 0.56 0.72]; selectionColor=[1.00 0.78 0.05];
pillarRect=quadrantRectangle(pillarQuadrant,sampleCenter,size(image,2),size(image,1)); viaRect=quadrantRectangle(oppositeQuadrant(pillarQuadrant),sampleCenter,size(image,2),size(image,1));
rectangle(ax,'Position',pillarRect,'EdgeColor',pillarColor,'LineWidth',1.6,'LineStyle','--'); rectangle(ax,'Position',viaRect,'EdgeColor',viaColor,'LineWidth',1.6,'LineStyle','--');
rectangle(ax,'Position',[cropRect(1),cropRect(2),cropRect(3)-cropRect(1),cropRect(4)-cropRect(2)],'EdgeColor',[0 0 0],'LineWidth',4.5);
rectangle(ax,'Position',[cropRect(1),cropRect(2),cropRect(3)-cropRect(1),cropRect(4)-cropRect(2)],'EdgeColor',selectionColor,'LineWidth',2.6);
plot(ax,centers(:,1),centers(:,2),'o','MarkerSize',4.2,'MarkerEdgeColor',[0 0 0],'MarkerFaceColor',selectionColor);
plot(ax,sampleCenter(1),sampleCenter(2),'p','MarkerSize',10,'MarkerEdgeColor',[0 0 0],'MarkerFaceColor',[1 1 1]);
if pillarRect(3) < 0.12*size(image,2)
    text(ax,pillarRect(1)+0.50*pillarRect(3),pillarRect(2)+0.55*pillarRect(4),'pillar 區域','Color',pillarColor,'BackgroundColor','w','Margin',2,'FontWeight','bold','FontSize',10,'HorizontalAlignment','center','Rotation',90);
else
    text(ax,pillarRect(1)+0.55*pillarRect(3),pillarRect(2)+0.22*pillarRect(4),'pillar 區域','Color',pillarColor,'BackgroundColor','w','Margin',2,'FontWeight','bold','FontSize',11,'HorizontalAlignment','center');
end
text(ax,viaRect(1)+0.46*viaRect(3),viaRect(2)+0.48*viaRect(4),'via 區域','Color',viaColor,'BackgroundColor','w','Margin',2,'FontWeight','bold','FontSize',11,'HorizontalAlignment','center');
selectionX=mean(cropRect([1 3]));
if sampleCenter(1) > 0.75*size(image,2)
    selectionX=min(selectionX,size(image,2)-350);
    selectionY=max(18,cropRect(2)-48);
else
    selectionX=min(selectionX,size(image,2)-250);
    selectionY=max(18,cropRect(2)-20);
end
text(ax,selectionX,selectionY,'朝向樣品中心的 3×3','Color',[0.08 0.08 0.08],'BackgroundColor',selectionColor,'Margin',2,'FontWeight','bold','FontSize',10,'HorizontalAlignment','center');
if sampleCenter(1) > 0.75*size(image,2)
    text(ax,sampleCenter(1)-12,sampleCenter(2)+18,'樣品中心交界','Color',[0.08 0.08 0.08],'BackgroundColor','w','Margin',2,'FontSize',9.5,'HorizontalAlignment','right','VerticalAlignment','top');
else
    text(ax,sampleCenter(1)+12,sampleCenter(2)+15,'樣品中心交界','Color',[0.08 0.08 0.08],'BackgroundColor','w','Margin',2,'FontSize',9.5,'HorizontalAlignment','left','VerticalAlignment','top');
end
barPx=scaleBarUm/umPerPx; x2=size(image,2)-35; x1=x2-barPx; y=size(image,1)-34;
plot(ax,[x1 x2],[y y],'-','Color',[0 0 0],'LineWidth',5); plot(ax,[x1 x2],[y y],'-','Color',[1 1 1],'LineWidth',2.8);
text(ax,(x1+x2)/2,y-10,sprintf('%g µm',scaleBarUm),'Color','w','FontSize',10,'HorizontalAlignment','center','VerticalAlignment','bottom','FontWeight','bold');
exportgraphics(fig,outputPath,'Resolution',300,'BackgroundColor','white'); close(fig);
end

function rect=quadrantRectangle(q,c,w,h)
switch lower(string(q))
    case "upper_left", rect=[1 1 c(1)-1 c(2)-1];
    case "upper_right", rect=[c(1) 1 w-c(1) c(2)-1];
    case "lower_left", rect=[1 c(2) c(1)-1 h-c(2)];
    case "lower_right", rect=[c(1) c(2) w-c(1) h-c(2)];
end
end

function q=oppositeQuadrant(q0)
switch lower(string(q0))
    case "upper_left", q="lower_right";
    case "upper_right", q="lower_left";
    case "lower_left", q="upper_right";
    case "lower_right", q="upper_left";
end
end

function rect=cropAroundCenters(centers,margin,imageSize)
rect=[max(1,floor(min(centers(:,1))-margin)),max(1,floor(min(centers(:,2))-margin)), ...
    min(imageSize(2),ceil(max(centers(:,1))+margin)),min(imageSize(1),ceil(max(centers(:,2))+margin))];
end

function image=readGrayDouble(path)
image=im2double(imread(path)); if ndims(image)==3, image=rgb2gray(image); end
end
