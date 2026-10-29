function build_english_wiener_figures()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
%BUILD_ENGLISH_WIENER_FIGURES Export English thesis figures.

close all;
packageRoot = fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS');
outputRoot = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_tmp/oral_defense_english_20260727/assets_english/wiener');
figureDir = fullfile(outputRoot, 'figures');
tableDir = fullfile(outputRoot, 'tables');
qaDir = fullfile(outputRoot, 'qa');
wienerRoot = fullfile(packageRoot, 'source_validation', 'wiener_baseline_20260715');
sourceTables = fullfile(wienerRoot, 'tables');
ensureDir(figureDir); ensureDir(tableDir); ensureDir(qaDir);

obsoleteArtifacts = { ...
    fullfile(figureDir,'08_legacy_raw_v42_50pct_cd_error_summary.png'), ...
    fullfile(figureDir,'09_legacy_raw_v42_50pct_cd_improvement_per_pillar.png'), ...
    fullfile(tableDir,'legacy_raw_v42_50pct_cd_summary.csv'), ...
    fullfile(tableDir,'displacement_detailed_summary.csv'), ...
    fullfile(tableDir,'displacement_pooled_summary.csv')};
for artifactIndex = 1:numel(obsoleteArtifacts)
    if isfile(obsoleteArtifacts{artifactIndex}), delete(obsoleteArtifacts{artifactIndex}); end
end

set(groot, 'defaultFigureColor', 'w');
set(groot, 'defaultAxesFontName', 'Times New Roman');
set(groot, 'defaultTextFontName', 'Times New Roman');
set(groot, 'defaultAxesFontSize', 10);
set(groot, 'defaultAxesLineWidth', 0.8);
set(groot, 'defaultLineLineWidth', 1.35);

rawColor = [0.64, 0.33, 0.18];
wienerColor = [0.78, 0.52, 0.08];
v42Color = [0.10, 0.42, 0.67];
inkColor = [0.12, 0.12, 0.12];
gridColor = [0.86, 0.86, 0.86];

cd = readCsv(fullfile(sourceTables, 'three_way_cd_per_pillar.csv'));
cdSensitivity = readCsv(fullfile(sourceTables, 'three_way_cd_threshold_sensitivity.csv'));
cdSensitivityMeasurements = readCsv(fullfile(sourceTables, 'three_way_cd_sensitivity_per_measurement.csv'));
cdRobustSummary = readCsv(fullfile(sourceTables, 'three_way_cd_robust_summary.csv'));
perStep = readCsv(fullfile(sourceTables, 'three_way_displacement_per_step.csv'));
detail = readCsv(fullfile(sourceTables, 'three_way_displacement_summary.csv'));
spatial = readCsv(fullfile(sourceTables, 'three_way_spatial_summary.csv'));
spatialCorrelation = readCsv(fullfile(sourceTables, 'three_way_spatial_correlations.csv'));

assert(height(perStep) == 120, 'The three-way displacement table must contain 120 locked steps.');
assert(all(isfinite(perStep.raw_boundary_dx_um)) && all(isfinite(perStep.wiener_boundary_dx_um)) && ...
    all(isfinite(perStep.v42_boundary_dx_um)), 'A primary displacement value is missing.');
assert(all(perStep.raw_boundary_valid_pillars == 9) && ...
    all(perStep.wiener_boundary_valid_pillars == 9) && ...
    all(perStep.v42_boundary_valid_pillars == 9), ...
    'Every primary measurement must use all nine pillars.');
assert(all(string(cd.raw_status) == "ok") && all(string(cd.wiener_status) == "ok") && ...
    all(string(cd.v42_e120_status) == "ok"), 'A CD crossing is invalid.');

copyfile(fullfile(sourceTables, 'three_way_cd_per_pillar.csv'), fullfile(tableDir, 'cd_50pct_nominal_per_pillar.csv'));
copyfile(fullfile(sourceTables, 'three_way_cd_summary.csv'), fullfile(tableDir, 'cd_50pct_nominal_summary.csv'));
copyfile(fullfile(sourceTables, 'three_way_cd_threshold_sensitivity.csv'), fullfile(tableDir, 'cd_threshold_sensitivity_summary.csv'));
copyfile(fullfile(sourceTables, 'three_way_cd_robust_per_pillar.csv'), fullfile(tableDir, 'cd_threshold_robust_per_pillar.csv'));
copyfile(fullfile(sourceTables, 'three_way_cd_robust_summary.csv'), fullfile(tableDir, 'cd_threshold_robust_summary.csv'));
cdBounds = buildCdBounds(cdSensitivityMeasurements);
writetable(cdBounds, fullfile(tableDir, 'cd_per_pillar_bounds.csv'));
copyfile(fullfile(sourceTables, 'three_way_displacement_per_step.csv'), fullfile(tableDir, 'displacement_three_way_per_step.csv'));
copyfile(fullfile(sourceTables, 'three_way_displacement_summary.csv'), fullfile(tableDir, 'displacement_three_way_summary.csv'));
copyfile(fullfile(sourceTables, 'three_way_displacement_pooled.csv'), fullfile(tableDir, 'displacement_three_way_pooled.csv'));
copyfile(fullfile(sourceTables, 'three_way_spatial_summary.csv'), fullfile(tableDir, 'wiener_spatial_variation_summary.csv'));
copyfile(fullfile(sourceTables, 'three_way_spatial_correlations.csv'), fullfile(tableDir, 'wiener_spatial_variation_correlations.csv'));

configPath = fullfile(packageRoot,'..','01_CURRENT_THESIS_RESULTS_V42_CENTER9','config','sequence_center9_50x20x.json');
configPayload = jsondecode(fileread(configPath));
calibrationRows = readCsv(fullfile(sourceTables,'wiener_selected_nsr.csv'));
fitRoot = fullfile(PROJECT_ROOT, 'PSF_Fitting/output/deconvolution_baseline_psf_20260715');
case50 = loadCalibrationCase('50x',calibrationRows,configPayload,wienerRoot,fitRoot);
case20 = loadCalibrationCase('20x',calibrationRows,configPayload,wienerRoot,fitRoot);
raw50Path=case50.rawPath; v4250Path=case50.v42Path; wiener50Path=case50.wienerPath;
raw20Path=case20.rawPath; v4220Path=case20.v42Path; wiener20Path=case20.wienerPath;
paths={raw50Path,v4250Path,wiener50Path,raw20Path,v4220Path,wiener20Path};
assert(all(cellfun(@isfile,paths)),'A calibration-frame image is missing.');
raw50=readGray(raw50Path);wiener50=readGray(wiener50Path);v4250=readGray(v4250Path);
raw20=readGray(raw20Path);wiener20=readGray(wiener20Path);v4220=readGray(v4220Path);
assert(isequal(size(raw50), size(wiener50), size(v4250)) && ...
    isequal(size(raw20), size(wiener20), size(v4220)), 'Three-way image dimensions differ.');

ids50=case50.ids;centers50=case50.centers;
ids20=case20.ids;centers20=case20.centers;
crop50 = cropAroundCenters(centers50, 72.5*0.65, size(raw50));
crop20 = cropAroundCenters(centers20, 29.0*0.65, size(raw20));
drawImageCrop(raw50,crop50,0.069,5,'50\times Raw PSF-Calibration Frame', ...
    fullfile(figureDir,'01_50x_raw_center9.png'));
drawImageCrop(wiener50,crop50,0.069,5,'50\times Wiener Deconvolution', ...
    fullfile(figureDir,'02a_50x_wiener_center9.png'));
    drawImageCrop(v4250,crop50,0.069,5,'50\times MOSR Reconstruction (Paired Frame)', ...
    fullfile(figureDir,'02_50x_v42_center9.png'));
drawImageCrop(raw20,crop20,0.1725,5,'20\times Raw PSF-Calibration Frame', ...
    fullfile(figureDir,'04_20x_raw_center9.png'));
drawImageCrop(wiener20,crop20,0.1725,5,'20\times Wiener Deconvolution', ...
    fullfile(figureDir,'05a_20x_wiener_center9.png'));
    drawImageCrop(v4220,crop20,0.1725,5,'20\times MOSR Reconstruction (Paired Frame)', ...
    fullfile(figureDir,'05_20x_v42_center9.png'));
visualSelection=table(["50x";"20x"],[string(case50.sequence);string(case20.sequence)], ...
    [case50.frameIndex;case20.frameIndex],[mean(centers50(:,1));mean(centers20(:,1))], ...
    [mean(centers50(:,2));mean(centers20(:,2))], ...
    'VariableNames',{'magnification','sequence','frame_index','center_x_px','center_y_px'});
writetable(visualSelection,fullfile(tableDir,'psf_calibration_visual_frame_selection.csv'));

contrast = [measurePillarContrast(raw50,centers50,ids50,19.5,'50x','Raw'); ...
    measurePillarContrast(wiener50,centers50,ids50,19.5,'50x','Wiener deconvolution'); ...
    measurePillarContrast(v4250,centers50,ids50,19.5,'50x','V42 epoch 120'); ...
    measurePillarContrast(raw20,centers20,ids20,7.6,'20x','Raw'); ...
    measurePillarContrast(wiener20,centers20,ids20,7.6,'20x','Wiener deconvolution'); ...
    measurePillarContrast(v4220,centers20,ids20,7.6,'20x','V42 epoch 120')];
writetable(contrast,fullfile(tableDir,'contrast_polarity_per_pillar.csv'));
contrastSummary = summarizePillarContrast(contrast);
writetable(contrastSummary,fullfile(tableDir,'contrast_polarity_summary.csv'));
assert(all(contrastSummary.median_signed_difference_8bit < 0), ...
    'Pillar polarity is not dark-on-bright for every case.');
drawSignedContrast(contrastSummary,rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'00c_signed_pillar_contrast.png'));

[edge50,profile50] = analyzeRadialPillarEdges(raw50,wiener50,v4250,centers50,ids50,72.5,0.069,'50x');
[edge20,profile20] = analyzeRadialPillarEdges(raw20,wiener20,v4220,centers20,ids20,29.0,0.1725,'20x');
edgeTable = [edge50;edge20];
writetable(edgeTable,fullfile(tableDir,'edge_transition_widths_10_90.csv'));
edgeSummary = groupsummary(edgeTable,{'magnification','case'},{'mean','std','median'},'transition_width_nm');
writetable(edgeSummary,fullfile(tableDir,'edge_transition_width_summary.csv'));
drawProfile(profile50,edge50,'50\times Pillar Radial Edge Profile',rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'03_50x_pillar_edge_profile.png'));
drawProfile(profile20,edge20,'20\times Pillar Radial Edge Profile',rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'06_20x_pillar_edge_profile.png'));

drawCdBounds(cdBounds,rawColor,wienerColor,v42Color,inkColor,gridColor, ...
    fullfile(figureDir,'07_center9_cd_per_pillar.png'));
drawCdRobustSummary(cdRobustSummary,rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'08_center9_cd_error_summary.png'));
drawCdThresholdSensitivity(cdSensitivity,'horizontal_strip',rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'09a_cd_threshold_sensitivity_horizontal.png'));
drawCdThresholdSensitivity(cdSensitivity,'radial_mean',rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'09b_cd_threshold_sensitivity_radial.png'));

sequenceOrder = ["50x_x_0p5um","50x_x_1um","20x_0p5um","20x_1um"];
traceFiles = {'10_50x_0p5um_step_trace.png','11_50x_1um_step_trace.png', ...
    '12_20x_0p5um_step_trace.png','13_20x_1um_step_trace.png'};
for i = 1:numel(sequenceOrder)
    drawSequenceTrace(perStep,detail(i,:),sequenceOrder(i),rawColor,wienerColor,v42Color,inkColor,gridColor, ...
        fullfile(figureDir,traceFiles{i}));
end
tickLabels = {'50\times\newline0.5 \mum','50\times\newline1.0 \mum', ...
    '20\times\newline0.5 \mum','20\times\newline1.0 \mum'};
drawGroupedMetric(detail,'raw_step_sd_nm','wiener_step_sd_nm','v42_step_sd_nm', ...
    'Step-to-Step Displacement SD','Standard Deviation (nm)',tickLabels, ...
    rawColor,wienerColor,v42Color,gridColor,fullfile(figureDir,'14_step_stability_summary.png'));
drawGroupedMetric(detail,'raw_within_mean_nm','wiener_within_mean_nm','v42_within_mean_nm', ...
    'Within-Grid Displacement Dispersion','Mean Robust Dispersion (nm)',tickLabels, ...
    rawColor,wienerColor,v42Color,gridColor,fullfile(figureDir,'15_nine_pillar_consistency_summary.png'));
drawGroupedMetric(detail,'raw_command_mae_nm','wiener_command_mae_nm','v42_command_mae_nm', ...
    'Agreement with PI-Stage Feedback','Mean Absolute Deviation (nm)',tickLabels, ...
    rawColor,wienerColor,v42Color,gridColor,fullfile(figureDir,'16_nominal_command_consistency.png'));
drawImprovementRate(detail,tickLabels,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'17_stepwise_local_improvement_rate.png'));
drawSpatialRobustness(spatial,'50x',rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'18a_50x_wiener_psf_distance_robustness.png'));
drawSpatialRobustness(spatial,'20x',rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'18b_20x_wiener_psf_distance_robustness.png'));

rawAudit = readCsv(fullfile(packageRoot,'..','01_CURRENT_THESIS_RESULTS_V42_CENTER9','diagnostics', ...
    'unified_displacement_step_audit','tables','all_adjacent_pairs_audit.csv'));
wienerAudit = readCsv(fullfile(wienerRoot,'displacement_audit','tables','all_adjacent_pairs_audit.csv'));
selectionRobustness = drawUsableVsTop30(rawAudit,wienerAudit,perStep,rawColor,wienerColor,v42Color,gridColor, ...
    fullfile(figureDir,'20_20x_0p5um_usable_vs_top30.png'));
writetable(selectionRobustness,fullfile(tableDir,'selection_robustness_20x_0p5um.csv'));

fid = fopen(fullfile(qaDir,'three_way_matlab_generation_check.txt'),'w','n','UTF-8');
fprintf(fid,'Generated: %s\n',string(datetime('now','TimeZone','Asia/Taipei')));
fprintf(fid,'MATLAB: %s\n',version);
fprintf(fid,'Locked three-way displacement steps: %d\n',height(perStep));
fprintf(fid,'Steps with nine pillars in every case: %d\n',sum(perStep.raw_boundary_valid_pillars==9 & perStep.wiener_boundary_valid_pillars==9 & perStep.v42_boundary_valid_pillars==9));
fprintf(fid,'CD crossings valid in every case: %d/%d\n',sum(string(cd.raw_status)=="ok" & string(cd.wiener_status)=="ok" & string(cd.v42_e120_status)=="ok"),height(cd));
fprintf(fid,'CD sensitivity summary rows: %d; robust summary rows: %d\n',height(cdSensitivity),height(cdRobustSummary));
fprintf(fid,'Spatial summary rows: %d; correlation rows: %d\n',height(spatial),height(spatialCorrelation));
fprintf(fid,'Figure count: %d\n',numel(dir(fullfile(figureDir,'*.png'))));
fprintf(fid,'Table count: %d\n',numel(dir(fullfile(tableDir,'*.csv'))));
fclose(fid);
fprintf('Raw/Wiener/MOSR Chapter 6 figures generated successfully.\n');
end

function result = measurePillarContrast(image,centers,ids,radiusPx,magnification,caseName)
rows = cell(size(centers,1),8); outer = ceil(1.70*radiusPx);
for i=1:size(centers,1)
    xc=round(centers(i,1)); yc=round(centers(i,2));
    x0=max(1,xc-outer); x1=min(size(image,2),xc+outer);
    y0=max(1,yc-outer); y1=min(size(image,1),yc+outer);
    [xx,yy]=meshgrid(x0:x1,y0:y1); distance=hypot(xx-centers(i,1),yy-centers(i,2));
    patch=double(image(y0:y1,x0:x1));
    featureLevel=median(patch(distance<=0.55*radiusPx),'omitnan');
    backgroundLevel=median(patch(distance>=1.25*radiusPx & distance<=1.70*radiusPx),'omitnan');
    difference=featureLevel-backgroundLevel;
    michelson=100*difference/(featureLevel+backgroundLevel);
    if difference<0, polarity="dark-on-bright"; else, polarity="bright-on-dark"; end
    rows(i,:)={string(magnification),ids(i),string(caseName),featureLevel,backgroundLevel,difference,michelson,polarity};
end
result=cell2table(rows,'VariableNames',{'magnification','pillar_id','case','pillar_core_median_8bit', ...
    'local_background_median_8bit','signed_difference_8bit','signed_michelson_pct','polarity'});
end

function summary = summarizePillarContrast(tableData)
magnifications=["50x";"50x";"50x";"20x";"20x";"20x"];
cases=["Raw";"Wiener deconvolution";"V42 epoch 120";"Raw";"Wiener deconvolution";"V42 epoch 120"];
rows=cell(6,10);
for i=1:6
    g=tableData(string(tableData.magnification)==magnifications(i) & string(tableData.case)==cases(i),:);
    delta=g.signed_difference_8bit; michelson=g.signed_michelson_pct;
    if median(delta)<0, polarity="dark-on-bright"; else, polarity="bright-on-dark"; end
    rows(i,:)={magnifications(i),cases(i),height(g),median(g.pillar_core_median_8bit), ...
        median(g.local_background_median_8bit),median(delta),mean(delta),std(delta),median(michelson),polarity};
end
summary=cell2table(rows,'VariableNames',{'magnification','case','pillar_count','median_pillar_core_8bit', ...
    'median_local_background_8bit','median_signed_difference_8bit','mean_signed_difference_8bit', ...
    'std_signed_difference_8bit','median_signed_michelson_pct','polarity'});
end

function drawSignedContrast(summary,rawColor,wienerColor,v42Color,gridColor,outputPath)
values=reshape(summary.median_signed_michelson_pct,3,2)';
fig=figure('Units','inches','Position',[1,1,6.35,3.65]); ax=axes(fig);
b=bar(ax,values,'grouped','EdgeColor','none');
b(1).FaceColor=rawColor; b(2).FaceColor=wienerColor; b(3).FaceColor=v42Color;
yline(ax,0,'-','Color',[0.18,0.18,0.18],'LineWidth',1.0,'HandleVisibility','off');
set(ax,'XTick',1:2,'XTickLabel',{'50\times','20\times'},'TickLabelInterpreter','tex');
ylabel(ax,'Signed Michelson Contrast (%)');
title(ax,'Pillar Contrast in Paired Displacement Frames','FontSize',12,'FontWeight','normal');
subtitle(ax,'Median over nine pillars; negative values indicate dark pillars on a bright background','FontSize',9.5);
    legend(ax,{'Raw','Wiener','MOSR'},'Location','northoutside','Orientation','horizontal','Box','off','NumColumns',3);
padding=max(1.5,0.04*range(values(:)));
for j=1:3
    text(ax,b(j).XEndPoints,b(j).YEndPoints-padding,compose('%+.1f%%',b(j).YEndPoints), ...
        'HorizontalAlignment','center','VerticalAlignment','top','FontSize',7.5);
end
ylim(ax,[min(values(:))-5*padding,3]); styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function [edgeTable,profile] = analyzeRadialPillarEdges(raw,wiener,v42,centers,ids,pitchPx,umPerPx,magnification)
rows=cell(0,5);profile=struct();
for i=1:size(centers,1)
    [radiusRaw,scoreRaw,widthRaw]=normalizedRadialProfile(raw,centers(i,:),pitchPx,umPerPx);
    [radiusW,scoreW,widthW]=normalizedRadialProfile(wiener,centers(i,:),pitchPx,umPerPx);
    [radiusV,scoreV,widthV]=normalizedRadialProfile(v42,centers(i,:),pitchPx,umPerPx);
    rows(end+1,:)={string(magnification),ids(i),'Raw',widthRaw*umPerPx*1000,360}; %#ok<AGROW>
    rows(end+1,:)={string(magnification),ids(i),'Wiener deconvolution',widthW*umPerPx*1000,360}; %#ok<AGROW>
    rows(end+1,:)={string(magnification),ids(i),'V42 epoch 120',widthV*umPerPx*1000,360}; %#ok<AGROW>
    if i==5
        profile.x_um=radiusRaw;profile.raw=scoreRaw;
        profile.wiener=interp1(radiusW,scoreW,radiusRaw,'linear','extrap');
        profile.v42=interp1(radiusV,scoreV,radiusRaw,'linear','extrap');
    end
end
edgeTable=cell2table(rows,'VariableNames',{'magnification','pillar_id','case','transition_width_nm','angular_profiles'});
end

function [radiusUm,medianScore,widthPx] = normalizedRadialProfile(image,center,pitchPx,umPerPx)
radialStep=0.05;radii=0:radialStep:(0.38*pitchPx);angles=linspace(0,2*pi,361);angles(end)=[];
x=center(1)+cos(angles(:)).*radii;y=center(2)+sin(angles(:)).*radii;
samples=interp2(double(image),x,y,'cubic');samples=smoothdata(samples,2,'gaussian',13);
coreLevel=median(samples(:,radii<=0.07*pitchPx),'all');
backgroundLevel=median(samples(:,radii>=0.30*pitchPx & radii<=0.36*pitchPx),'all');
r10=crossingRadii(samples,radii,coreLevel+0.10*(backgroundLevel-coreLevel));
r90=crossingRadii(samples,radii,coreLevel+0.90*(backgroundLevel-coreLevel));
valid=isfinite(r10)&isfinite(r90)&r90>=r10;
if nnz(valid)>=324,widthPx=median(r90(valid)-r10(valid));else,widthPx=NaN;end
medianProfile=median(samples,1);medianScore=(medianProfile-coreLevel)./max(backgroundLevel-coreLevel,eps);
radiusUm=radii*umPerPx;
end

function crossings=crossingRadii(samples,radii,threshold)
crossings=nan(size(samples,1),1);
for row=1:size(samples,1)
    profile=samples(row,:);index=find(profile>=threshold,1,'first');
    if isempty(index)||index==1,continue;end
    y0=profile(index-1);y1=profile(index);
    if y1==y0,crossings(row)=radii(index);else
        fraction=(threshold-y0)/(y1-y0);
        crossings(row)=radii(index-1)+fraction*(radii(index)-radii(index-1));
    end
end
end

function drawProfile(profile,edgeTable,titleText,rawColor,wienerColor,v42Color,gridColor,outputPath)
rawMedian=median(edgeTable.transition_width_nm(string(edgeTable.case)=="Raw"),'omitnan');
wMedian=median(edgeTable.transition_width_nm(string(edgeTable.case)=="Wiener deconvolution"),'omitnan');
vMedian=median(edgeTable.transition_width_nm(string(edgeTable.case)=="V42 epoch 120"),'omitnan');
fig=figure('Units','inches','Position',[1,1,6.35,3.65]); ax=axes(fig); hold(ax,'on');
plot(ax,profile.x_um,profile.raw,'-s','Color',rawColor,'MarkerFaceColor','w','MarkerSize',3,'DisplayName','Raw');
plot(ax,profile.x_um,profile.wiener,'-^','Color',wienerColor,'MarkerFaceColor',wienerColor,'MarkerSize',3,'DisplayName','Wiener');
    plot(ax,profile.x_um,profile.v42,'-o','Color',v42Color,'MarkerFaceColor',v42Color,'MarkerSize',3,'DisplayName','MOSR');
yline(ax,0.1,':','Color',[0.45,0.45,0.45],'HandleVisibility','off'); yline(ax,0.9,':','Color',[0.45,0.45,0.45],'HandleVisibility','off');
xlabel(ax,'Radius from Pillar Center (\mum)','Interpreter','tex'); ylabel(ax,'Normalized Radial Signal');
title(ax,titleText,'FontSize',12,'FontWeight','normal','Interpreter','tex');
subtitle(ax,'Median over 360 directions; identical radial smoothing and 10–90% rule','FontSize',9.5);
legend(ax,'Location','southwest','Box','off','NumColumns',3);
finiteValues=[profile.raw(isfinite(profile.raw)),profile.wiener(isfinite(profile.wiener)),profile.v42(isfinite(profile.v42))];
span=max(max(finiteValues)-min(finiteValues),0.25); ylim(ax,[min(-0.1,min(finiteValues)-0.08*span),max(1.1,max(finiteValues)+0.08*span)]);
text(ax,0.985,0.97,sprintf('Median 10–90%% width\nRaw %.1f nm | Wiener %.1f nm | MOSR %.1f nm',rawMedian,wMedian,vMedian), ...
    'Units','normalized','HorizontalAlignment','right','VerticalAlignment','top','FontSize',7.7, ...
    'BackgroundColor','w','EdgeColor',[0.75,0.75,0.75],'Margin',4);
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function bounds=buildCdBounds(observations)
caseKeys=["raw","wiener","v42_e120"];
ids=unique(observations.sem_index,'stable');
values=nan(numel(ids),13);
for pillarIndex=1:numel(ids)
    pillarRows=observations(observations.sem_index==ids(pillarIndex),:);
    values(pillarIndex,1)=pillarRows.center9_position(1);
    values(pillarIndex,2)=ids(pillarIndex);
    values(pillarIndex,3)=pillarRows.sem_diameter_um(1);
    observationCount=NaN;
    for caseIndex=1:numel(caseKeys)
        selected=pillarRows(string(pillarRows.case)==caseKeys(caseIndex) & string(pillarRows.status)=="ok",:);
        diameters=selected.diameter_um(isfinite(selected.diameter_um));
        assert(numel(diameters)==14,'Each method and pillar must contain two profiles by seven thresholds.');
        if isnan(observationCount),observationCount=numel(diameters);end
        column=4+(caseIndex-1)*3;
        values(pillarIndex,column)=min(diameters);
        values(pillarIndex,column+1)=max(diameters);
        values(pillarIndex,column+2)=1000*(max(diameters)-min(diameters));
    end
    values(pillarIndex,13)=observationCount;
end
bounds=array2table(values,'VariableNames',{ ...
    'center9_position','sem_index','sem_diameter_um', ...
    'raw_lower_um','raw_upper_um','raw_span_nm', ...
    'wiener_lower_um','wiener_upper_um','wiener_span_nm', ...
    'mosr_lower_um','mosr_upper_um','mosr_span_nm','observations_per_method'});
end

function drawCdBounds(bounds,rawColor,wienerColor,v42Color,inkColor,gridColor,outputPath)
x=(1:height(bounds))'; labels=compose('P%d',bounds.sem_index);
fig=figure('Units','inches','Position',[1,1,6.35,3.65]); ax=axes(fig); hold(ax,'on');
hSem=plot(ax,x,bounds.sem_diameter_um,'o','LineStyle','none','Color',inkColor, ...
    'MarkerFaceColor','w','MarkerSize',4.5,'LineWidth',1.2,'DisplayName','SEM CD');
offsets=[-0.19,0,0.19]; colors={rawColor,wienerColor,v42Color};
lowerFields={'raw_lower_um','wiener_lower_um','mosr_lower_um'};
upperFields={'raw_upper_um','wiener_upper_um','mosr_upper_um'};
names={'Raw bounds','Wiener bounds','MOSR bounds'};
handles=gobjects(1,3); capWidth=0.065;
for methodIndex=1:3
    lower=bounds.(lowerFields{methodIndex}); upper=bounds.(upperFields{methodIndex});
    xp=x+offsets(methodIndex);
    for pillarIndex=1:numel(x)
        plot(ax,[xp(pillarIndex),xp(pillarIndex)],[lower(pillarIndex),upper(pillarIndex)],'-', ...
            'Color',colors{methodIndex},'LineWidth',2.0,'HandleVisibility','off');
        plot(ax,[xp(pillarIndex)-capWidth,xp(pillarIndex)+capWidth],[lower(pillarIndex),lower(pillarIndex)],'-', ...
            'Color',colors{methodIndex},'LineWidth',1.4,'HandleVisibility','off');
        plot(ax,[xp(pillarIndex)-capWidth,xp(pillarIndex)+capWidth],[upper(pillarIndex),upper(pillarIndex)],'-', ...
            'Color',colors{methodIndex},'LineWidth',1.4,'HandleVisibility','off');
    end
    handles(methodIndex)=plot(ax,nan,nan,'-','Color',colors{methodIndex},'LineWidth',2.2,'DisplayName',names{methodIndex});
end
set(ax,'XTick',x,'XTickLabel',labels); xlabel(ax,'SEM Pillar ID'); ylabel(ax,'Pillar Diameter (\mum)','Interpreter','tex');
title(ax,'Per-Pillar Apparent CD Bounds across Thresholds','FontSize',12,'FontWeight','normal');
subtitle(ax,'Covers 35–65% thresholds and both profile definitions','FontSize',9.5);
legend(ax,[hSem,handles],'Location','north','Box','off','NumColumns',4);
xlim(ax,[0.55,9.45]);
allLower=[bounds.raw_lower_um;bounds.wiener_lower_um;bounds.mosr_lower_um;bounds.sem_diameter_um];
allUpper=[bounds.raw_upper_um;bounds.wiener_upper_um;bounds.mosr_upper_um;bounds.sem_diameter_um];
ylim(ax,[min(allLower)-0.035,max(allUpper)+0.105]);
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawCdRobustSummary(summary,rawColor,wienerColor,v42Color,gridColor,outputPath)
raw=summary(string(summary.case)=="raw",:); w=summary(string(summary.case)=="wiener",:); v=summary(string(summary.case)=="v42_e120",:);
values=[raw.pooled_median_abs_error_nm,w.pooled_median_abs_error_nm,v.pooled_median_abs_error_nm];
fig=figure('Units','inches','Position',[1,1,6.1,3.65]); ax=axes(fig);
b=bar(ax,values,0.62,'FaceColor','flat','EdgeColor','none'); b.CData=[rawColor;wienerColor;v42Color];
set(ax,'XTick',1:3,'XTickLabel',{'Raw','Wiener','MOSR'}); ylabel(ax,'Median Absolute CD Error (nm)');
title(ax,'Cross-Threshold CD Error for the Central Nine Pillars','FontSize',12,'FontWeight','normal');
subtitle(ax,'Two profiles, seven thresholds, and nine SEM-reference pillars','FontSize',9.5);
ylim(ax,[0,max(values)*1.25]);
text(ax,1:3,values+0.035*max(values),compose('%.1f nm',values),'HorizontalAlignment','center','FontSize',8);
text(ax,0.985,0.95,sprintf('Median-error change\nMOSR: %+.1f%% | Wiener: %+.1f%%', ...
    v.median_abs_improvement_vs_raw_pct,w.median_abs_improvement_vs_raw_pct), ...
    'Units','normalized','HorizontalAlignment','right','VerticalAlignment','top','FontSize',7.5, ...
    'BackgroundColor','w','EdgeColor',[0.78,0.78,0.78],'Margin',3.5);
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawCdThresholdSensitivity(summary,mode,rawColor,wienerColor,v42Color,gridColor,outputPath)
g=summary(string(summary.measurement_mode)==string(mode),:);
raw=sortrows(g(string(g.case)=="raw",:),'threshold_fraction');
w=sortrows(g(string(g.case)=="wiener",:),'threshold_fraction');
v=sortrows(g(string(g.case)=="v42_e120",:),'threshold_fraction');
fig=figure('Units','inches','Position',[1,1,6.35,3.65]); ax=axes(fig); hold(ax,'on');
plot(ax,100*raw.threshold_fraction,raw.mean_abs_error_nm,'-s','Color',rawColor,'MarkerFaceColor','w','MarkerSize',4,'DisplayName','Raw');
plot(ax,100*w.threshold_fraction,w.mean_abs_error_nm,'-^','Color',wienerColor,'MarkerFaceColor',wienerColor,'MarkerSize',4,'DisplayName','Wiener');
    plot(ax,100*v.threshold_fraction,v.mean_abs_error_nm,'-o','Color',v42Color,'MarkerFaceColor',v42Color,'MarkerSize',4,'DisplayName','MOSR');
xline(ax,50,':','Color',[0.35,0.35,0.35],'LineWidth',1,'HandleVisibility','off');
xlabel(ax,'Relative Edge Threshold (%)'); ylabel(ax,'Mean Absolute CD Error (nm)');
if string(mode) == "horizontal_strip", profileLabel = "Seven-Row Horizontal Profile"; else, profileLabel = "360-Degree Mean Radial Profile"; end
title(ax,profileLabel + " CD Threshold Sensitivity",'FontSize',12,'FontWeight','normal');
subtitle(ax,'Identical centers and SEM identities; lower, flatter curves are more robust','FontSize',9.5);
legend(ax,'Location','northoutside','Orientation','horizontal','Box','off','NumColumns',3);
xlim(ax,[33,67]); ylim(ax,[0,max([raw.mean_abs_error_nm;w.mean_abs_error_nm;v.mean_abs_error_nm])*1.12]);
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawSequenceTrace(perStep,summaryRow,sequence,rawColor,wienerColor,v42Color,inkColor,gridColor,outputPath)
    g=sortrows(perStep(string(perStep.sequence)==sequence,:),'end_frame_index'); x=(1:height(g))';
fig=figure('Units','inches','Position',[1,1,6.5,3.55]); ax=axes(fig); hold(ax,'on');
yline(ax,summaryRow.nominal_step_um,'--','Color',inkColor,'LineWidth',1.1,'DisplayName','PI-Stage Feedback');
plot(ax,x,abs(g.raw_boundary_dx_um),'-s','Color',rawColor,'MarkerFaceColor','w','MarkerSize',3,'DisplayName','Raw');
plot(ax,x,abs(g.wiener_boundary_dx_um),'-^','Color',wienerColor,'MarkerFaceColor',wienerColor,'MarkerSize',3,'DisplayName','Wiener');
    plot(ax,x,abs(g.v42_boundary_dx_um),'-o','Color',v42Color,'MarkerFaceColor',v42Color,'MarkerSize',3,'DisplayName','MOSR');
xlabel(ax,'Step Index'); ylabel(ax,'Measured Displacement Magnitude (\mum)','Interpreter','tex');
conditionTitle=strrep(strrep(string(summaryRow.condition),'x','×'),'um','µm');
title(ax,conditionTitle + " Displacement Sequence",'FontSize',12,'FontWeight','normal','Interpreter','none');
subtitle(ax,sprintf('Identical Raw-defined paired steps (n = %d)',summaryRow.paired_count),'FontSize',9.5);
    legend(ax,'Location','northoutside','Orientation','horizontal','Box','off','NumColumns',2);
    xlim(ax,[1,30]); xticks(ax,[1,5,10,15,20,25,30]);
values=[abs(g.raw_boundary_dx_um);abs(g.wiener_boundary_dx_um);abs(g.v42_boundary_dx_um);summaryRow.nominal_step_um];
span=max(values)-min(values); if span==0,span=summaryRow.nominal_step_um*0.05;end
ylim(ax,[min(values)-0.15*span,max(values)+0.28*span]);
text(ax,0.985,0.035,sprintf('SD (nm): Raw %.2f | Wiener %.2f | MOSR %.2f',summaryRow.raw_step_sd_nm,summaryRow.wiener_step_sd_nm,summaryRow.v42_step_sd_nm), ...
    'Units','normalized','HorizontalAlignment','right','VerticalAlignment','bottom','FontSize',7.8,'BackgroundColor','w','EdgeColor',[0.78,0.78,0.78],'Margin',3.5);
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawGroupedMetric(summary,rawField,wField,vField,titleText,yLabel,tickLabels,rawColor,wienerColor,v42Color,gridColor,outputPath)
values=[summary.(rawField),summary.(wField),summary.(vField)];
fig=figure('Units','inches','Position',[1,1,6.4,3.75]); ax=axes(fig); b=bar(ax,values,'grouped','EdgeColor','none');
b(1).FaceColor=rawColor; b(2).FaceColor=wienerColor; b(3).FaceColor=v42Color;
set(ax,'XTick',1:height(summary),'XTickLabel',tickLabels,'TickLabelInterpreter','tex'); ylabel(ax,yLabel);
title(ax,titleText,'FontSize',12,'FontWeight','normal'); subtitle(ax,'Each sequence uses the same 30 Raw-defined paired steps','FontSize',9.5);
    legend(ax,{'Raw','Wiener','MOSR'},'Location','northwest','Box','off','NumColumns',3); ylim(ax,[0,max(values(:))*1.30]);
for j=1:3, text(ax,b(j).XEndPoints,b(j).YEndPoints+0.025*max(values(:)),compose('%.2f',b(j).YEndPoints),'HorizontalAlignment','center','FontSize',7.2); end
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawImprovementRate(summary,tickLabels,wienerColor,v42Color,gridColor,outputPath)
values=[summary.wiener_lower_within_pct,summary.v42_lower_within_pct];
fig=figure('Units','inches','Position',[1,1,6.35,3.6]); ax=axes(fig); b=bar(ax,values,'grouped','EdgeColor','none');
b(1).FaceColor=wienerColor; b(2).FaceColor=v42Color; hold(ax,'on'); yline(ax,50,'--','Color',[0.35,0.35,0.35],'LineWidth',1,'HandleVisibility','off');
set(ax,'XTick',1:height(summary),'XTickLabel',tickLabels,'TickLabelInterpreter','tex'); ylabel(ax,'Steps with Reduced Displacement Dispersion (%)');
title(ax,'Stepwise Improvement in Nine-Pillar Displacement Consistency','FontSize',12,'FontWeight','normal'); subtitle(ax,'Strict paired-step comparison; ties are not counted as improvements','FontSize',9.5);
    legend(ax,{'Wiener','MOSR'},'Location','northoutside','Orientation','horizontal','Box','off'); ylim(ax,[0,108]);
for j=1:2, text(ax,b(j).XEndPoints,b(j).YEndPoints+2,compose('%.1f%%',b(j).YEndPoints),'HorizontalAlignment','center','FontSize',7.5); end
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawSpatialRobustness(spatial,magnification,rawColor,wienerColor,v42Color,gridColor,outputPath)
g=spatial(string(spatial.magnification)==string(magnification),:);
order=categorical(string(g.distance_group),["Near","Middle","Far"],'Ordinal',true); [~,idx]=sort(order); g=g(idx,:);
x=g.distance_mean_object_um(:); values=[g.raw_command_mae_nm,g.wiener_command_mae_nm,g.v42_command_mae_nm];
fig=figure('Units','inches','Position',[1,1,6.25,3.65]); ax=axes(fig); hold(ax,'on');
plot(ax,x,values(:,1),'-s','Color',rawColor,'MarkerFaceColor','w','MarkerSize',5,'DisplayName','Raw');
plot(ax,x,values(:,2),'-^','Color',wienerColor,'MarkerFaceColor',wienerColor,'MarkerSize',5,'DisplayName','Wiener');
    plot(ax,x,values(:,3),'-o','Color',v42Color,'MarkerFaceColor',v42Color,'MarkerSize',5,'DisplayName','MOSR');
groupName = string(g.distance_group(:));
groupName(groupName == "Near") = "Near";
groupName(groupName == "Middle") = "Middle";
groupName(groupName == "Far") = "Far";
tickLabels=compose("%s (%.1f)",groupName,x);
set(ax,'XTick',x,'XTickLabel',tickLabels);
xlabel(ax,'Distance Group (Mean Object-Space Distance, \mum)','Interpreter','tex'); ylabel(ax,'Mean Absolute Deviation from Reference (nm)');
magnificationTitle=strrep(string(magnification),'x','×');
title(ax,magnificationTitle + " Sensitivity to PSF-Calibration Distance",'FontSize',12,'FontWeight','normal','Interpreter','none');
subtitle(ax,'Each distance group uses 20 steps; both step sizes share the same PSF','FontSize',9.5);
legend(ax,'Location','northoutside','Orientation','horizontal','Box','off','NumColumns',3); xlim(ax,[max(0,min(x)-0.12*range(x)),max(x)+0.12*range(x)]); ylim(ax,[0,max(values(:))*1.25]);
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function summary=drawUsableVsTop30(rawAudit,wienerAudit,perStep,rawColor,wienerColor,v42Color,gridColor,outputPath)
rawAudit.sequence=string(rawAudit.sequence); wienerAudit.sequence=string(wienerAudit.sequence);
g=rawAudit(rawAudit.sequence=="20x_0p5um",:); w=wienerAudit(wienerAudit.sequence=="20x_0p5um",:);
w=w(:,{'end_frame_index','v42_evaluable','v42_boundary_dx_um'});
w.Properties.VariableNames={'end_frame_index','wiener_evaluable','wiener_boundary_dx_um'};
g=innerjoin(g,w,'Keys','end_frame_index');
usable=asLogical(g.raw_eligible_25pct) & asLogical(g.v42_evaluable) & asLogical(g.wiener_evaluable);
selected=perStep(string(perStep.sequence)=="20x_0p5um",:);
values=[std(g.raw_boundary_dx_um(usable),0)*1000,std(g.wiener_boundary_dx_um(usable),0)*1000,std(g.v42_boundary_dx_um(usable),0)*1000; ...
    std(selected.raw_boundary_dx_um,0)*1000,std(selected.wiener_boundary_dx_um,0)*1000,std(selected.v42_boundary_dx_um,0)*1000];
summary=table(["All usable";"Locked top 30"],[sum(usable);height(selected)],values(:,1),values(:,2),values(:,3), ...
    'VariableNames',{'population','step_count','raw_step_sd_nm','wiener_step_sd_nm','mosr_step_sd_nm'});
fig=figure('Units','inches','Position',[1,1,6.25,3.7]); ax=axes(fig); b=bar(ax,values,'grouped','EdgeColor','none');
b(1).FaceColor=rawColor; b(2).FaceColor=wienerColor; b(3).FaceColor=v42Color;
set(ax,'XTickLabel',{sprintf('All usable %d',sum(usable)),'Fixed 30 steps'}); ylabel(ax,'Step-to-Step Displacement SD (nm)');
title(ax,'Effect of the Fixed-30-Step Alternative Selection','FontSize',12,'FontWeight','normal'); subtitle(ax,'20\times, 0.5 \mum sequence','FontSize',9.5,'Interpreter','tex');
    legend(ax,{'Raw','Wiener','MOSR'},'Location','northeast','Box','off'); ylim(ax,[0,max(values(:))*1.25]);
for j=1:3, text(ax,b(j).XEndPoints,b(j).YEndPoints+0.025*max(values(:)),compose('%.2f',b(j).YEndPoints),'HorizontalAlignment','center','FontSize',7.5); end
styleAxes(ax,gridColor); exportFigure(fig,outputPath);
end

function drawImageCrop(image,rect,umPerPx,scaleBarUm,titleText,outputPath)
crop=image(rect(2):rect(4),rect(1):rect(3)); fig=figure('Units','inches','Position',[1,1,4.35,4.05]); ax=axes(fig);
imagesc(ax,crop,[0,255]); colormap(ax,gray(256)); axis(ax,'image'); axis(ax,'off'); title(ax,titleText,'FontSize',11.5,'FontWeight','normal','Interpreter','tex'); hold(ax,'on');
barPx=scaleBarUm/umPerPx; x2=size(crop,2)-10; x1=x2-barPx; y=size(crop,1)-12;
plot(ax,[x1,x2],[y,y],'-','Color',[0,0,0],'LineWidth',5); plot(ax,[x1,x2],[y,y],'-','Color',[1,1,1],'LineWidth',2.8);
text(ax,(x1+x2)/2,y-7,sprintf('%g \\mum',scaleBarUm),'Color','w','FontSize',8.5,'HorizontalAlignment','center','VerticalAlignment','bottom','FontWeight','bold','Interpreter','tex');
exportFigure(fig,outputPath);
end

function rect=cropAroundCenters(centers,margin,imageSize)
rect=[max(1,floor(min(centers(:,1))-margin)),max(1,floor(min(centers(:,2))-margin)), ...
    min(imageSize(2),ceil(max(centers(:,1))+margin)),min(imageSize(1),ceil(max(centers(:,2))+margin))];
end

function data=loadCalibrationCase(magnification,rows,configPayload,wienerRoot,fitRoot)
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath')))))))))));
row=rows(string(rows.magnification)==string(magnification),:);
assert(height(row)==1,'Expected one selected calibration row per magnification.');
sequenceName=char(string(row.calibration_sequence));
validName=matlab.lang.makeValidName(sequenceName);
assert(isfield(configPayload.sequences,validName),'Calibration sequence is absent from the locked configuration.');
sequence=configPayload.sequences.(validName);
frameIndex=double(row.calibration_frame);
metadata=jsondecode(fileread(fullfile(fitRoot,magnification,'selected_frame.json')));
centers=double(metadata.pillar_centers_xy);
centerValues=double(sequence.centers);
assert(size(centers,1)==9 && size(centerValues,1)==9,'Calibration case must contain exactly nine pillars.');
data.sequence=sequenceName;
data.frameIndex=frameIndex;
data.rawPath=fullfile(PROJECT_ROOT,sequence.raw_dir,sprintf('frame_%04d.bmp',frameIndex));
data.v42Path=fullfile(PROJECT_ROOT,sequence.v42_dir,sprintf('frame_%04d.bmp',frameIndex));
data.wienerPath=fullfile(wienerRoot,'reconstructions',validName,sprintf('frame_%04d.bmp',frameIndex));
data.centers=centers;
data.ids=centerValues(:,1);
end
function image=readGray(path), image=imread(path); if ndims(image)==3,image=rgb2gray(image);end; image=uint8(image); end
function tableData=readCsv(path), options=detectImportOptions(path,'Delimiter',',','VariableNamingRule','preserve','Encoding','UTF-8'); tableData=readtable(path,options); end
function values=asLogical(input), if islogical(input),values=input;elseif isnumeric(input),values=input~=0;else,values=ismember(lower(string(input)),["true","1","yes"]);end; end
function styleAxes(ax,gridColor), ax.FontName='Microsoft JhengHei';ax.FontSize=10;ax.Box='off';ax.TickDir='out';ax.XColor=[0.16,0.16,0.16];ax.YColor=[0.16,0.16,0.16];ax.GridColor=gridColor;ax.GridAlpha=0.8;ax.XGrid='off';ax.YGrid='on';ax.Layer='top';end
function exportFigure(fig,path), cleanFigure(fig); set(fig,'Renderer','painters');axesList=findall(fig,'Type','axes');for k=1:numel(axesList),axtoolbar(axesList(k),{});end;exportgraphics(fig,path,'Resolution',300,'BackgroundColor','white');close(fig);end
function ensureDir(path), if ~exist(path,'dir'),mkdir(path);end;end


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
