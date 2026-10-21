function measure_displacement_consecutive()
    %% (A) 參數設定
    clc; close all;

    magnificationName = '1';    % 資料夾名稱(對應倍率)
    pixelSize = 3.2;            % (um/pixel)
    theoryVal = 1;             % 每次小移動理論(um)

    baseDir     = 'C:\NonSystemFiles\GMM\ShiftCaculation';   % 主路徑
    folderShift = fullfile(baseDir, 'Shift',    magnificationName);  % 原始資料夾
    folderSR    = fullfile(baseDir, 'Shift_SR\0223_1107\', magnificationName);  % 超解析資料夾

    % ROI：定位標靶 (示例)
    roiRowStart = 376; 
    roiRowEnd   = 1476; 
    roiColStart = 3333; 
    roiColEnd   = 4433;

    usfac  = 2000;   % dftregistration upsampling
    Nshots = 11;     % 共有 1..Nshots 張

    %% (B) 量測: 原始資料夾 (Shift)
    [distSteps_orig] = measureSmallSteps(folderShift, magnificationName, ...
        pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);

    %% (C) 量測: 超解析資料夾 (Shift_SR)
    [distSteps_sr]   = measureSmallSteps(folderSR, magnificationName, ...
        pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);

    %% distSteps_xxx => size= Nshots-1, 表示 (1->2), (2->3), ..., (Nshots-1->Nshots)

    %% (D) 每一次小移動的誤差 (單步)
    shots   = 2:Nshots;  % 代表第(1->2), (2->3), ...
    errOrig = distSteps_orig - theoryVal;
    errSR   = distSteps_sr   - theoryVal;

    % 逐次列印
    fprintf('\n==== 每次相鄰影像的小移動 (相對前一張) vs. 理論=%.3f um ====\n\n', theoryVal);

    fprintf('--- [原始資料 Shift] ---\n');
    for i = 1:numel(distSteps_orig)
        shotPair = [shots(i)-1, shots(i)];
        fprintf('Shot(%2d->%2d): 實測=%.4f um, 誤差=%.4f um\n', ...
            shotPair(1), shotPair(2), distSteps_orig(i), errOrig(i));
    end

    fprintf('\n--- [超解析 Shift_SR] ---\n');
    for i = 1:numel(distSteps_sr)
        shotPair = [shots(i)-1, shots(i)];
        fprintf('Shot(%2d->%2d): 實測=%.4f um, 誤差=%.4f um\n', ...
            shotPair(1), shotPair(2), distSteps_sr(i), errSR(i));
    end

    %% (E) 統計 (針對每一次小移動)
    meanOrig = mean(distSteps_orig);
    stdOrig  = std(distSteps_orig);
    meanErrO = mean(errOrig);
    stdErrO  = std(errOrig);

    meanSR   = mean(distSteps_sr);
    stdSR    = std(distSteps_sr);
    meanErrS = mean(errSR);
    stdErrS  = std(errSR);

    fprintf('\n[Original - 小移動] mean=%.4f +/- %.4f um, 誤差=%.4f +/- %.4f um\n',...
        meanOrig, stdOrig, meanErrO, stdErrO);
    fprintf('[SR       - 小移動] mean=%.4f +/- %.4f um, 誤差=%.4f +/- %.4f um\n',...
        meanSR,   stdSR,   meanErrS, stdErrS);

    %% (F) 計算 & 比對「累計位移」
    %  cumsum(...) 可把每一步加起來, 得到相對第一張的位移
    %  假設 distSteps(1) = 1->2, distSteps(2) = 2->3, ...
    %  則 cumulativeDist(2) = distSteps(1) (第一步),
    %     cumulativeDist(3) = distSteps(1)+distSteps(2),
    %     ...
    %  為方便索引, 多補1個 0 在最前面 => cumulativeDist(1)=0, cumulativeDist(2)=step1, ...
    cumulativeDist_orig = [0, cumsum(distSteps_orig)];
    cumulativeDist_sr   = [0, cumsum(distSteps_sr)];

    % cummShots = 1..Nshots
    cummShots = 1:Nshots;  % cummDist(i) 對應 shot i

    % 理論累積: shot i => (i-1)*theoryVal
    theoryCumm = (cummShots - 1)*theoryVal;

    % 計算累計誤差
    cummErrOrig = cumulativeDist_orig - theoryCumm;
    cummErrSR   = cumulativeDist_sr   - theoryCumm;

    % 印出最後一張(相對第1張)總量
    fprintf('\n=== 累計位移(相對第1張) ===\n');
    for i = 2:Nshots
        fprintf('Shot=%2d => Orig=%.4f um(誤差=%.4f), SR=%.4f um(誤差=%.4f), Theory=%.4f\n',...
            i, ...
            cumulativeDist_orig(i), cummErrOrig(i), ...
            cumulativeDist_sr(i),   cummErrSR(i), ...
            theoryCumm(i));
    end

    %% 額外可計算「累計位移」的平均誤差(若需要)
    meanCummErrO = mean(cummErrOrig(2:end));  % 忽略第1張=0
    stdCummErrO  = std(cummErrOrig(2:end));
    meanCummErrS = mean(cummErrSR(2:end));
    stdCummErrS  = std(cummErrSR(2:end));

    fprintf('\n[Original - 累計位移] 平均誤差=%.4f +/- %.4f um\n',...
        meanCummErrO, stdCummErrO);
    fprintf('[SR       - 累計位移] 平均誤差=%.4f +/- %.4f um\n',...
        meanCummErrS, stdCummErrS);

    %% (G) 圖表: 每次小移動 + 累計
    % 1) 每次小移動
    figure('Name','Consecutive steps: displacement','Color','w');
    plot(shots, distSteps_orig, '-o','LineWidth',1.5); hold on;
    plot(shots, distSteps_sr,   '-s','LineWidth',1.5);
    yline(theoryVal,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2,'Label','Theory');
    hold off;
    legend('Original','SR','Location','best');
    xlabel('Shot Transition (i->i+1)');
    ylabel('Displacement of each step (um)');
    title(sprintf('Each small step, expected=%.2f um', theoryVal));

    % 2) 每次小移動 誤差
    figure('Name','Consecutive steps: error','Color','w');
    plot(shots, errOrig, '-o','LineWidth',1.5); hold on;
    plot(shots, errSR,   '-s','LineWidth',1.5);
    yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
    hold off;
    legend('OriginalErr','SRErr','Location','best');
    xlabel('Shot Transition (i->i+1)');
    ylabel('Error (um) = measured - theory');
    title('Error per small step');

    % 3) 累計位移 vs. 理論
    figure('Name','Cumulative displacement','Color','w');
    plot(cummShots, cumulativeDist_orig, '-o','LineWidth',1.5); hold on;
    plot(cummShots, cumulativeDist_sr,   '-s','LineWidth',1.5);
    plot(cummShots, theoryCumm, '--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
    hold off;
    legend('OriginalCumulative','SRCumulative','TheoryCumulative','Location','best');
    xlabel('Shot #');
    ylabel('Cumulative distance from shot1 (um)');
    title(sprintf('Cumulative displacement up to shot i, step=%.2f um', theoryVal));

    % 4) 累計位移 誤差
    figure('Name','Cumulative error','Color','w');
    plot(cummShots, cummErrOrig, '-o','LineWidth',1.5); hold on;
    plot(cummShots, cummErrSR,   '-s','LineWidth',1.5);
    yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
    hold off;
    legend('Original Cumm. Err','SR Cumm. Err','Location','best');
    xlabel('Shot #');
    ylabel('Cumulative error (um) = measured - theory');
    title('Cumulative error from shot1');

    disp('=== 完成: 每一步 & 累計位移 vs. 理論 ===');
end

%% -------------------------------------------------------------
function [distStep_um] = measureSmallSteps(folderPath, magName, pixelSize, ...
    rStart, rEnd, cStart, cEnd, Nshots, usfac)
    % 讀取所有影像(ROI)進入 cell array
    allROIs = cell(1,Nshots);
    for iShot = 1:Nshots
        fname = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot));
        if ~exist(fname,'file')
            warning('File not found: %s', fname);
            allROIs{iShot} = [];
        else
            tmpImg = imread(fname);
            tmpROI = im2double(tmpImg(rStart:rEnd, cStart:cEnd));
            allROIs{iShot} = tmpROI;
        end
    end

    distStep_um = zeros(1, Nshots-1);

    % 相鄰影像 => (iShot vs iShot+1)
    for iShot = 1 : (Nshots-1)
        roi1 = allROIs{iShot};
        roi2 = allROIs{iShot+1};
        if isempty(roi1) || isempty(roi2)
            distStep_um(iShot) = NaN;
            continue;
        end
        
        [output,~] = dftregistration(fft2(roi1), fft2(roi2), usfac);
        rowShift_pix = output(3);
        colShift_pix = output(4);
        dist_pix = sqrt(rowShift_pix^2 + colShift_pix^2);
        dist_um  = dist_pix * pixelSize;

        distStep_um(iShot) = dist_um;

        fprintf('Shot(%2d->%2d): rowShift=%.4f pix, colShift=%.4f pix => %.4f pix => %.4f um\n',...
            iShot, iShot+1, rowShift_pix, colShift_pix, dist_pix, dist_um);
    end
end
