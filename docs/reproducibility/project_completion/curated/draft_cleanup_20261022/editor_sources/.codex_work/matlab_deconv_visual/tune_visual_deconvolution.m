function tune_visual_deconvolution()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))))))));
%TUNE_VISUAL_DECONVOLUTION Compare visually sharper deconvolution variants.

close all;
outputRoot = fullfile(PROJECT_ROOT, 'PSF_Fitting/.codex_work/deconvolution_visual_tuning_final_20260716');
fitRoot = fullfile(PROJECT_ROOT, 'PSF_Fitting/output/deconvolution_baseline_psf_20260715');
reviewRoot = [[fullfile(PROJECT_ROOT, 'Thesis_MOSR_Evidence/Final_Data_Figures') filesep] ...
    '03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\' ...
    'center9_pillar_fit_20x_50x\wiener_visual_sharpness_retest'];
reviewNsr = 0.050;
ensure_dir(outputRoot);
ensure_dir(reviewRoot);

cases = struct( ...
    'label', {'50x','20x'}, ...
    'pitchPx', {72.4637681159420,28.9855072463768}, ...
    'currentNsr', {0.0796563412944888,0.101895418923707});
nsrValues = [0.008,0.012,0.016,0.020,0.025,0.032,0.040,0.050,0.063,0.080,0.100,0.125];
lucyIterations = [3,4,5,6,7,8];
lucyDamping = [0,0.0025,0.0050];

allRows = table();
selectionRows = table();
reviewRows = table();
for caseIndex = 1:numel(cases)
    item = cases(caseIndex);
    caseRoot = fullfile(outputRoot,item.label);
    ensure_dir(caseRoot);

    metadata = jsondecode(fileread(fullfile(fitRoot,item.label,'selected_frame.json')));
    loaded = load(fullfile(fitRoot,item.label,'fit_result','PSF_fitted_2D_FOVstack.mat'),'psf_grid');
    psf = squeeze(double(loaded.psf_grid));
    psf = psf ./ sum(psf(:));
    rawFull = read_gray_double(metadata.selected_image);
    centers = double(metadata.pillar_centers_xy);
    processRect = centers_crop_rect(centers,item.pitchPx,size(rawFull),1.30);
    displayRectGlobal = centers_crop_rect(centers,item.pitchPx,size(rawFull),0.65);
    [rawCrop,centersLocal] = crop_with_centers(rawFull,centers,processRect);
    displayRect = [displayRectGlobal(1)-processRect(1)+1, ...
        displayRectGlobal(2)-processRect(2)+1, ...
        displayRectGlobal(3)-processRect(1)+1, ...
        displayRectGlobal(4)-processRect(2)+1];

    rawMetrics = measure_grid(rawCrop,centersLocal,item.pitchPx);
    rawGradient = edge_gradient(rawCrop,centersLocal,item.pitchPx);
    rawNoise = background_noise(rawCrop,centersLocal,item.pitchPx);
    candidateImages = {};
    localRows = table();

    [currentImage,currentClip] = restore_bg_wiener(rawCrop,psf,item.currentNsr,item.pitchPx,false,false);
    [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
        "current_wiener",item.currentNsr,0,currentImage,currentClip,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);

    for nsrIndex = 1:numel(nsrValues)
        nsr = nsrValues(nsrIndex);
        [image,clipFraction] = restore_bg_wiener(rawCrop,psf,nsr,item.pitchPx,false,false);
        [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
            "bg_wiener",nsr,0,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);

        [image,clipFraction] = restore_bg_wiener(rawCrop,psf,nsr,item.pitchPx,true,false);
        [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
            "bg_wiener_nn",nsr,0,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);

        [image,clipFraction] = restore_bg_wiener(rawCrop,psf,nsr,item.pitchPx,true,true);
        [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
            "bg_wiener_taper_nn",nsr,0,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);

        [image,clipFraction] = restore_direct_wiener(rawCrop,psf,nsr,false);
        [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
            "direct_wiener",nsr,0,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);

        [image,clipFraction] = restore_direct_wiener(rawCrop,psf,nsr,true);
        [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
            "direct_wiener_taper",nsr,0,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);
    end

    for dampingIndex = 1:numel(lucyDamping)
        for iterationIndex = 1:numel(lucyIterations)
            iterations = lucyIterations(iterationIndex);
            damping = lucyDamping(dampingIndex);
            [image,clipFraction] = restore_bg_lucy(rawCrop,psf,iterations,damping,item.pitchPx,false);
            [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
                "bg_lucy",damping,iterations,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);

            [image,clipFraction] = restore_bg_lucy(rawCrop,psf,iterations,damping,item.pitchPx,true);
            [localRows,candidateImages] = add_candidate(localRows,candidateImages,item.label, ...
                "bg_lucy_taper",damping,iterations,image,clipFraction,rawMetrics,rawGradient,rawNoise,centersLocal,item.pitchPx);
        end
    end

    % A visible second ring is not real sharpness. Keep the guard strict so
    % the chosen result remains a solid pillar instead of an annulus.
    localRows.safe = ~localRows.any_inverted & localRows.valid_pillars==9 & ...
        isfinite(localRows.median_edge_width_px) & localRows.ringing_ratio<=0.10 & ...
        localRows.background_noise_gain<=1.25 & localRows.clip_fraction<=0.02;
    localRows.score = 2.0.*log(max(localRows.edge_width_gain,eps)) + ...
        0.8.*log(max(localRows.edge_gradient_gain,eps)) - ...
        5.0.*localRows.ringing_ratio - ...
        0.35.*max(localRows.background_noise_gain-1.0,0) - ...
        6.0.*localRows.clip_fraction;

    safeIndices = find(localRows.safe);
    if isempty(safeIndices)
        [~,selectedIndex] = max(localRows.score);
        selectionStatus = "fallback_best_score";
    else
        [~,relativeIndex] = max(localRows.score(safeIndices));
        selectedIndex = safeIndices(relativeIndex);
        selectionStatus = "best_visual_score_with_artifact_guard";
    end
    localRows.selected = false(height(localRows),1);
    localRows.selected(selectedIndex) = true;
    localRows.selection_status = repmat(selectionStatus,height(localRows),1);

    selectedImage = candidateImages{selectedIndex};
    rawDisplay = crop_rect(rawCrop,displayRect);
    currentIndex = find(localRows.method=="current_wiener",1,'first');
    currentDisplay = crop_rect(candidateImages{currentIndex},displayRect);
    selectedDisplay = crop_rect(selectedImage,displayRect);
    imwrite(im2uint8(min(max(rawDisplay,0),1)),fullfile(caseRoot,'01_raw_same_display.bmp'));
    imwrite(im2uint8(min(max(currentDisplay,0),1)),fullfile(caseRoot,'02_current_wiener_same_display.bmp'));
    imwrite(im2uint8(min(max(selectedDisplay,0),1)),fullfile(caseRoot,'03_selected_sharp_deconvolution_same_display.bmp'));
    imwrite(im2uint8(min(max(selectedImage,0),1)),fullfile(caseRoot,'04_selected_processed_crop.bmp'));

    make_contact_sheet(rawCrop,candidateImages,localRows,selectedIndex,displayRect,item, ...
        fullfile(caseRoot,sprintf('%s_candidate_contact_sheet.png',item.label)));
    make_selected_comparison(rawDisplay,currentDisplay,selectedDisplay,localRows(currentIndex,:), ...
        localRows(selectedIndex,:),item,fullfile(caseRoot,sprintf('%s_raw_current_selected.png',item.label)));

    reviewIndex = find(localRows.method=="bg_wiener_taper_nn" & ...
        abs(localRows.parameter-reviewNsr)<1e-12,1,'first');
    reviewImage = candidateImages{reviewIndex};
    reviewDisplay = crop_rect(reviewImage,displayRect);
    reviewCaseRoot = fullfile(reviewRoot,item.label);
    ensure_dir(reviewCaseRoot);
    imwrite(im2uint8(min(max(rawDisplay,0),1)), ...
        fullfile(reviewCaseRoot,'01_raw_fixed_display.png'));
    imwrite(im2uint8(min(max(reviewDisplay,0),1)), ...
        fullfile(reviewCaseRoot,'02_wiener_deconvolution_fixed_display.png'));
    make_wiener_review(rawDisplay,reviewDisplay,localRows(reviewIndex,:),item, ...
        fullfile(reviewCaseRoot,'03_raw_vs_wiener_fixed_display.png'));
    writetable(localRows(reviewIndex,:),fullfile(reviewCaseRoot,'wiener_metrics.csv'));
    reviewRows = [reviewRows; localRows(reviewIndex,:)]; %#ok<AGROW>

    writetable(sortrows(localRows,'score','descend'),fullfile(caseRoot,'candidate_metrics.csv'));
    selectionRows = [selectionRows; localRows(selectedIndex,:)]; %#ok<AGROW>
    allRows = [allRows; localRows]; %#ok<AGROW>
end

writetable(sortrows(allRows,{'magnification','score'},{'ascend','descend'}), ...
    fullfile(outputRoot,'all_candidate_metrics.csv'));
writetable(selectionRows,fullfile(outputRoot,'selected_visual_deconvolution.csv'));
writetable(reviewRows,fullfile(reviewRoot,'wiener_visual_sharpness_summary.csv'));
write_summary(outputRoot,selectionRows);
fprintf('Visual deconvolution tuning completed: %s\n',outputRoot);
end

function [rows,images] = add_candidate(rows,images,magnification,method,parameter,iterations,imageData,clipFraction,rawMetrics,rawGradient,rawNoise,centers,pitchPx)
metrics = measure_grid(imageData,centers,pitchPx);
gradient = edge_gradient(imageData,centers,pitchPx);
noise = background_noise(imageData,centers,pitchPx);
row = table(string(magnification),string(method),parameter,iterations, ...
    rawMetrics.medianEdgeWidthPx,metrics.medianEdgeWidthPx, ...
    rawMetrics.medianEdgeWidthPx./metrics.medianEdgeWidthPx, ...
    rawGradient,gradient,gradient./max(rawGradient,eps), ...
    rawNoise,noise,noise./max(rawNoise,eps),metrics.maxRingingRatio, ...
    metrics.anyInverted,metrics.validPillars,clipFraction, ...
    'VariableNames',{'magnification','method','parameter','iterations', ...
    'raw_edge_width_px','median_edge_width_px','edge_width_gain', ...
    'raw_edge_gradient','edge_gradient','edge_gradient_gain', ...
    'raw_background_noise','background_noise','background_noise_gain', ...
    'ringing_ratio','any_inverted','valid_pillars','clip_fraction'});
rows = [rows;row]; %#ok<AGROW>
images{end+1,1} = min(max(imageData,0),1); %#ok<AGROW>
end

function [restored,clipFraction] = restore_bg_wiener(imageData,psf,nsr,pitchPx,nonnegative,taper)
[background,contrast,contrastScale] = dark_contrast(imageData,pitchPx);
[padded,padY,padX] = symmetric_pad(contrast,psf);
if taper, padded = edgetaper(padded,psf); end
restoredPadded = deconvwnr(padded,psf,nsr);
restoredContrast = unpad(restoredPadded,padY,padX,size(imageData));
if nonnegative
    restoredContrast = min(max(restoredContrast,0),1.25);
end
unclipped = background-contrastScale.*restoredContrast;
clipFraction = mean(unclipped(:)<0 | unclipped(:)>1);
restored = min(max(unclipped,0),1);
end

function [restored,clipFraction] = restore_direct_wiener(imageData,psf,nsr,taper)
[padded,padY,padX] = symmetric_pad(imageData,psf);
if taper, padded = edgetaper(padded,psf); end
restoredPadded = deconvwnr(padded,psf,nsr);
unclipped = unpad(restoredPadded,padY,padX,size(imageData));
clipFraction = mean(unclipped(:)<0 | unclipped(:)>1);
restored = min(max(unclipped,0),1);
end

function [restored,clipFraction] = restore_bg_lucy(imageData,psf,iterations,damping,pitchPx,taper)
[background,contrast,contrastScale] = dark_contrast(imageData,pitchPx);
[padded,padY,padX] = symmetric_pad(contrast,psf);
if taper, padded = edgetaper(padded,psf); end
restoredPadded = deconvlucy(padded,psf,iterations,damping);
restoredContrast = unpad(restoredPadded,padY,padX,size(imageData));
restoredContrast = min(max(restoredContrast,0),1.25);
unclipped = background-contrastScale.*restoredContrast;
clipFraction = mean(unclipped(:)<0 | unclipped(:)>1);
restored = min(max(unclipped,0),1);
end

function [background,contrast,contrastScale] = dark_contrast(imageData,pitchPx)
backgroundRadius = max(2,ceil(0.36*pitchPx));
background = imclose(imageData,strel('disk',backgroundRadius));
contrast = max(background-imageData,0);
contrastScale = prctile(contrast(:),99.5);
contrast = contrast./max(contrastScale,eps);
end

function [padded,padY,padX] = symmetric_pad(imageData,psf)
padY = floor(size(psf,1)/2);
padX = floor(size(psf,2)/2);
padded = padarray(imageData,[padY padX],'symmetric','both');
end

function result = unpad(imageData,padY,padX,targetSize)
result = imageData(padY+1:padY+targetSize(1),padX+1:padX+targetSize(2));
end

function metrics = measure_grid(imageData,centers,pitchPx)
radialStep = 0.05;
radii = 0:radialStep:(0.38*pitchPx);
angles = linspace(0,2*pi,361); angles(end)=[];
widths = nan(size(centers,1),1);
ringing = nan(size(centers,1),1);
inverted = false(size(centers,1),1);
for centerIndex=1:size(centers,1)
    x=centers(centerIndex,1)+cos(angles(:)).*radii;
    y=centers(centerIndex,2)+sin(angles(:)).*radii;
    samples=interp2(imageData,x,y,'cubic');
    samples=smoothdata(samples,2,'gaussian',13);
    coreLevel=median(samples(:,radii<=0.07*pitchPx),'all');
    backgroundLevel=median(samples(:,radii>=0.30*pitchPx & radii<=0.36*pitchPx),'all');
    inverted(centerIndex)=coreLevel>=backgroundLevel;
    r10=crossing_radii(samples,radii,coreLevel+0.10*(backgroundLevel-coreLevel));
    r90=crossing_radii(samples,radii,coreLevel+0.90*(backgroundLevel-coreLevel));
    valid=isfinite(r10)&isfinite(r90)&r90>=r10;
    if nnz(valid)>=324, widths(centerIndex)=median(r90(valid)-r10(valid)); end
    medianProfile=median(samples,1);
    normalized=(medianProfile-coreLevel)./max(backgroundLevel-coreLevel,eps);
    changes=diff(normalized(radii<=0.30*pitchPx));
    outwardRise=sum(changes(changes>0));
    inwardDip=-sum(changes(changes<0));
    ringing(centerIndex)=inwardDip./max(outwardRise,eps);
end
metrics=struct('medianEdgeWidthPx',median(widths,'omitnan'), ...
    'maxRingingRatio',max(ringing,[],'omitnan'),'anyInverted',any(inverted), ...
    'validPillars',nnz(isfinite(widths)));
end

function value = edge_gradient(imageData,centers,pitchPx)
[yy,xx]=ndgrid(1:size(imageData,1),1:size(imageData,2));
mask=false(size(imageData));
for centerIndex=1:size(centers,1)
    distance=hypot(xx-centers(centerIndex,1),yy-centers(centerIndex,2));
    mask=mask | (distance>=0.13*pitchPx & distance<=0.29*pitchPx);
end
gradient=imgradient(imageData,'sobel');
values=gradient(mask & isfinite(gradient));
value=sqrt(mean(values.^2));
end

function value = background_noise(imageData,centers,pitchPx)
[yy,xx]=ndgrid(1:size(imageData,1),1:size(imageData,2));
mask=true(size(imageData));
for centerIndex=1:size(centers,1)
    mask=mask & hypot(xx-centers(centerIndex,1),yy-centers(centerIndex,2))>=0.42*pitchPx;
end
highpass=imageData-imgaussfilt(imageData,1.0);
values=highpass(mask & isfinite(highpass));
value=1.4826*median(abs(values-median(values)));
end

function crossings = crossing_radii(samples,radii,threshold)
crossings=nan(size(samples,1),1);
for rowIndex=1:size(samples,1)
    profile=samples(rowIndex,:);
    index=find(profile>=threshold,1,'first');
    if isempty(index)||index==1, continue; end
    y0=profile(index-1); y1=profile(index);
    if y1==y0
        crossings(rowIndex)=radii(index);
    else
        fraction=(threshold-y0)./(y1-y0);
        crossings(rowIndex)=radii(index-1)+fraction.*(radii(index)-radii(index-1));
    end
end
end

function make_contact_sheet(rawImage,candidateImages,rows,selectedIndex,displayRect,item,outputPath)
methods=["current_wiener","bg_wiener","bg_wiener_nn","bg_wiener_taper_nn", ...
    "direct_wiener","direct_wiener_taper","bg_lucy","bg_lucy_taper"];
indices=zeros(numel(methods),1);
for methodIndex=1:numel(methods)
    candidates=find(rows.method==methods(methodIndex));
    safe=candidates(rows.safe(candidates));
    if ~isempty(safe), candidates=safe; end
    [~,best]=max(rows.score(candidates));
    indices(methodIndex)=candidates(best);
end
figureHandle=figure('Visible','off','Color','w','Position',[100 100 1500 1450]);
layout=tiledlayout(3,3,'TileSpacing','compact','Padding','compact');
nexttile;imagesc(crop_rect(rawImage,displayRect),[0 1]);axis image off;colormap gray;
title(sprintf('%s Raw | width %.2f px',item.label,rows.raw_edge_width_px(1)),'FontWeight','normal');
for tileIndex=1:numel(indices)
    rowIndex=indices(tileIndex);
    nexttile;imagesc(crop_rect(candidateImages{rowIndex},displayRect),[0 1]);axis image off;
    selectedMark=""; if rowIndex==selectedIndex, selectedMark=" | SELECTED"; end
    if rows.iterations(rowIndex)>0
        parameterText=sprintf('iter %d, damp %.4f',rows.iterations(rowIndex),rows.parameter(rowIndex));
    else
        parameterText=sprintf('NSR %.4f',rows.parameter(rowIndex));
    end
    title(sprintf('%s | %s%s\nwidth %.2f px (%.2fx), grad %.2fx, ring %.2f', ...
        strrep(rows.method(rowIndex),'_',' '),parameterText,selectedMark, ...
        rows.median_edge_width_px(rowIndex),rows.edge_width_gain(rowIndex), ...
        rows.edge_gradient_gain(rowIndex),rows.ringing_ratio(rowIndex)), ...
        'Interpreter','none','FontWeight','normal','FontSize',9);
end
title(layout,sprintf('%s deconvolution candidates; fixed 0-1 display range',item.label), ...
    'FontWeight','normal','FontSize',13);
set(findall(figureHandle,'-property','FontName'),'FontName','Times New Roman');
exportgraphics(figureHandle,outputPath,'Resolution',220,'BackgroundColor','white');
close(figureHandle);
end

function make_selected_comparison(raw,current,selected,currentRow,selectedRow,item,outputPath)
figureHandle=figure('Visible','off','Color','w','Position',[100 100 1500 520]);
layout=tiledlayout(1,3,'TileSpacing','compact','Padding','compact');
nexttile;imagesc(raw,[0 1]);axis image off;colormap gray;
title(sprintf('Raw\nwidth %.2f px',selectedRow.raw_edge_width_px),'FontWeight','normal');
nexttile;imagesc(current,[0 1]);axis image off;
title(sprintf('Current Wiener\nwidth %.2f px | ring %.2f',currentRow.median_edge_width_px,currentRow.ringing_ratio),'FontWeight','normal');
nexttile;imagesc(selected,[0 1]);axis image off;
if selectedRow.iterations>0
    parameterText=sprintf('iter %d, damp %.4f',selectedRow.iterations,selectedRow.parameter);
else
    parameterText=sprintf('NSR %.4f',selectedRow.parameter);
end

title(sprintf('Selected %s, %s\nwidth %.2f px | gradient %.2fx | ring %.2f', ...
    strrep(selectedRow.method,'_',' '),parameterText,selectedRow.median_edge_width_px, ...
    selectedRow.edge_gradient_gain,selectedRow.ringing_ratio), ...
    'Interpreter','none','FontWeight','normal');
title(layout,sprintf('%s visual deconvolution comparison; identical 0-1 display',item.label), ...
    'FontWeight','normal','FontSize',13);
set(findall(figureHandle,'-property','FontName'),'FontName','Times New Roman');
exportgraphics(figureHandle,outputPath,'Resolution',240,'BackgroundColor','white');
close(figureHandle);
end

function make_wiener_review(raw,restored,row,item,outputPath)
figureHandle=figure('Visible','off','Color','w','Position',[100 100 1080 520]);
layout=tiledlayout(1,2,'TileSpacing','compact','Padding','compact');
nexttile;imagesc(raw,[0 1]);axis image off;colormap gray;
title(sprintf('Raw\n10-90%% edge width: %.2f px',row.raw_edge_width_px), ...
    'FontWeight','normal');
nexttile;imagesc(restored,[0 1]);axis image off;
title(sprintf('Wiener deconvolution (NSR = %.3f)\nedge width: %.2f px | gradient: %.2fx', ...
    row.parameter,row.median_edge_width_px,row.edge_gradient_gain), ...
    'FontWeight','normal');
title(layout,sprintf('%s pillar image; identical display range',item.label), ...
    'FontWeight','normal','FontSize',13);
set(findall(figureHandle,'-property','FontName'),'FontName','Times New Roman');
exportgraphics(figureHandle,outputPath,'Resolution',240,'BackgroundColor','white');
close(figureHandle);
end

function write_summary(outputRoot,rows)
payload=struct();
payload.objective='visibly sharper than Raw under identical 0-1 display, without using CD or displacement outcomes';
payload.artifact_guard='preserved dark-pillar polarity, nine valid edges, ringing <= 0.10, background-noise gain <= 1.25, clip fraction <= 0.02';
for rowIndex=1:height(rows)
    key=['m' char(rows.magnification(rowIndex))];
    payload.(key)=table2struct(rows(rowIndex,:));
end
payload.generated_at=char(datetime('now','TimeZone','Asia/Taipei','Format','yyyy-MM-dd HH:mm:ss XXX'));
fid=fopen(fullfile(outputRoot,'selection_summary.json'),'w');
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(payload,PrettyPrint=true));
end

function rect = centers_crop_rect(centers,pitchPx,imageSize,marginPitch)
margin=marginPitch*pitchPx;
x1=max(1,floor(min(centers(:,1))-margin));
x2=min(imageSize(2),ceil(max(centers(:,1))+margin));
y1=max(1,floor(min(centers(:,2))-margin));
y2=min(imageSize(1),ceil(max(centers(:,2))+margin));
rect=[x1 y1 x2 y2];
end

function [crop,centersLocal] = crop_with_centers(imageData,centers,rect)
crop=imageData(rect(2):rect(4),rect(1):rect(3));
centersLocal=centers-[rect(1)-1,rect(2)-1];
end

function crop = crop_rect(imageData,rect)
crop=imageData(rect(2):rect(4),rect(1):rect(3));
end

function imageData = read_gray_double(path)
imageData=im2double(imread(path));
if size(imageData,3)>1, imageData=rgb2gray(imageData); end
end

function ensure_dir(path)
if ~exist(path,'dir'),mkdir(path);end
end
