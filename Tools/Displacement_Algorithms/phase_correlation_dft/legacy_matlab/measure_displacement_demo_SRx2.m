
%% (A) 參數設定
clearvars;
clc; close all;   % 註解掉以便測試時不強制清空

magnificationName = '0.32';    % 資料夾名稱(對應倍率)
pixelSize = 3.2;            % (um/pixel)
theoryVal = 0.32;              % 每次小移動理論(um)

baseDir     = "C:\NonSystemFiles\GMM";   % 主路徑
folderShift = fullfile(baseDir, 'Shift',    magnificationName);   % 原始資料夾
folderSR    = fullfile(baseDir, 'Shift_SR\0122_1641', magnificationName); % 超解析資料夾

% ===(原圖) ROI：定位標靶 (示例)===
%   下列範例為切取 [row: 376~1476]、[col: 3333~4433] 這塊。
roiRowStart = 376; 
roiRowEnd   = 1476; 
roiColStart = 3333; 
roiColEnd   = 4433;

%  % 顯示 ROI 選擇範圍以供檢查
% checkROI(folderShift, magnificationName, roiRowStart, roiRowEnd, roiColStart, roiColEnd);

% dftregistration 中的上採樣倍率
usfac  = 2000;   
% 共有 1..Nshots 張
Nshots = 11;    

%% (B) 量測: 原始資料夾 (Shift)
[distSteps_orig] = measureSmallSteps(folderShift, magnificationName, ...
    pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);

%% (C) 量測: 超解析資料夾 (Shift_SR)

% ----------------------------------------------------------
% (1) 超解析影像放大倍率
% ----------------------------------------------------------
srScale    = 2;                    % 超解析影像寬、高都放大 2 倍

% ----------------------------------------------------------
% (2) 對應的 pixel size 變為原本的一半
% ----------------------------------------------------------
pixelSizeSR = pixelSize / srScale; 

% ----------------------------------------------------------
% (3) ROI也要乘上 srScale，以鎖定「與原圖同樣的實際區域」
%    假設想量測 SR 圖中的同一個物理區域：
%    可以將 (rowStart, rowEnd, colStart, colEnd) 都乘上 srScale
%    下面範例以簡單的線性縮放方式示範
% ----------------------------------------------------------
% roiRowStartSR = 835;
% roiRowEndSR   = 1935;
% roiColStartSR = 7690;
% roiColEndSR   = 8790;

roiRowStartSR = (roiRowStart - 1)*srScale + 1;
roiRowEndSR   = (roiRowEnd   - 1)*srScale + 1;
roiColStartSR = (roiColStart - 1)*srScale + 1;
roiColEndSR   = (roiColEnd   - 1)*srScale + 1;


% (可視情況加上 round() 取整)
roiRowStartSR = round(roiRowStartSR);
roiRowEndSR   = round(roiRowEndSR);
roiColStartSR = round(roiColStartSR);
roiColEndSR   = round(roiColEndSR);

%  % 顯示 ROI 選擇範圍以供檢查
% checkROISR(folderSR, magnificationName, roiRowStartSR, roiRowEndSR, roiColStartSR, roiColEndSR);

% ----------------------------------------------------------
% (4) 呼叫同一個 measureSmallSteps，但傳入「新的ROI範圍」與「新的pixelSize」
% ----------------------------------------------------------
[distSteps_sr] = measureSmallSteps(folderSR, magnificationName, ...
    pixelSizeSR, roiRowStartSR, roiRowEndSR, roiColStartSR, roiColEndSR, ...
    Nshots, usfac);

%% (D) 分析/顯示每次小移動
shots   = 2:Nshots;  % 代表第(1->2), (2->3), ...
errOrig = distSteps_orig - theoryVal;
errSR   = distSteps_sr   - theoryVal;

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

%% (E) 統計 (單步)
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

%% (F) 累計位移
cumulativeDist_orig = [0, cumsum(distSteps_orig)];
cumulativeDist_sr   = [0, cumsum(distSteps_sr)];
cummShots = 1:Nshots;
theoryCumm = (cummShots - 1)*theoryVal;

cummErrOrig = cumulativeDist_orig - theoryCumm;
cummErrSR   = cumulativeDist_sr   - theoryCumm;

fprintf('\n=== 累計位移(相對第1張) ===\n');
for i = 2:Nshots
    fprintf('Shot=%2d => Orig=%.4f um(誤差=%.4f) || SR=%.4f um(誤差=%.4f), Theory=%.4f\n',...
        i, ...
        cumulativeDist_orig(i), cummErrOrig(i), ...
        cumulativeDist_sr(i),   cummErrSR(i), ...
        theoryCumm(i));
end

meanCummErrO = mean(cummErrOrig(2:end));
stdCummErrO  = std(cummErrOrig(2:end));
meanCummErrS = mean(cummErrSR(2:end));
stdCummErrS  = std(cummErrSR(2:end));

fprintf('\n[Original - 累計位移] 平均誤差=%.4f +/- %.4f um\n',...
    meanCummErrO, stdCummErrO);
fprintf('[SR       - 累計位移] 平均誤差=%.4f +/- %.4f um\n',...
    meanCummErrS, stdCummErrS);

%% (G) 繪圖

% (G) 繪圖 - 以四宮格方式顯示結果
figure('Name', 'Analysis Results', 'Color', 'w');

% 1) 每次小移動
subplot(2,2,1);
% figure('Name','Consecutive steps: displacement','Color','w');
plot(shots, distSteps_orig, '-o','LineWidth',1.5); hold on;
plot(shots, distSteps_sr,   '-s','LineWidth',1.5);
yline(theoryVal,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2,'Label','Theory');
hold off;
legend('Original','SR','Location','best');
xlabel('Shot Transition (i->i+1)');
ylabel('Displacement of each step (um)');
title(sprintf('Each small step, expected=%.2f um', theoryVal));

% 2) 每次小移動誤差
subplot(2,2,2);
% figure('Name','Consecutive steps: error','Color','w');
plot(shots, errOrig, '-o','LineWidth',1.5); hold on;
plot(shots, errSR,   '-s','LineWidth',1.5);
yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
hold off;
legend('OriginalErr','SRErr','Location','best');
xlabel('Shot Transition (i->i+1)');
ylabel('Error (um) = measured - theory');
title('Error per small step');

% 3) 累計位移 vs. 理論
subplot(2,2,3);
% figure('Name','Cumulative displacement','Color','w');
plot(cummShots, cumulativeDist_orig, '-o','LineWidth',1.5); hold on;
plot(cummShots, cumulativeDist_sr,   '-s','LineWidth',1.5);
plot(cummShots, theoryCumm, '--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
hold off;
legend('OriginalCumulative','SRCumulative','TheoryCumulative','Location','best');
xlabel('Shot #');
ylabel('Cumulative distance from shot1 (um)');
title(sprintf('Cumulative displacement up to shot i, step=%.2f um', theoryVal));

% 4) 累計位移誤差
subplot(2,2,4);
% figure('Name','Cumulative error','Color','w');
plot(cummShots, cummErrOrig, '-o','LineWidth',1.5); hold on;
plot(cummShots, cummErrSR,   '-s','LineWidth',1.5);
yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
hold off;
legend('Original Cumm. Err','SR Cumm. Err','Location','best');
xlabel('Shot #');
ylabel('Cumulative error (um) = measured - theory');
title('Cumulative error from shot1');

disp('=== 完成: 每一步 & 累計位移 vs. 理論 ===');


%% -------------------------------------------------------------
function [distStep_um] = measureSmallSteps(folderPath, magName, pixelSize, ...
    rStart, rEnd, cStart, cEnd, Nshots, usfac)
    % 讀取所有影像(ROI)進入 cell array
    allROIs = cell(1,Nshots);
    for iShot = 1:Nshots
        % 構造檔名
        fname = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot));
        if ~exist(fname,'file')
            warning('File not found: %s', fname);
            allROIs{iShot} = [];
        else
            tmpImg = imread(fname);
            % 依 ROI 擷取
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

%% 顯示影像與ROI函數
function checkROI(folderPath, magName, rStart, rEnd, cStart, cEnd)
    fname = fullfile(folderPath, sprintf('%s (1).bmp', magName));
    if ~exist(fname, 'file')
        error('File not found: %s', fname);
    end

    img = imread(fname);
    [imgHeight, imgWidth, ~] = size(img);
    figure('Name', 'ROI Selection Check', 'Color', 'w');
    imshow(img, []);
    hold on;
    rectangle('Position', [cStart, rStart, cEnd - cStart, rEnd - rStart], ...
              'EdgeColor', 'r', 'LineWidth', 2);
    hold off;
    title('Check ROI Selection');
    fprintf('ROI範圍: row [%d:%d], col [%d:%d]\n', rStart, rEnd, cStart, cEnd);
    fprintf('影像尺寸: 寬=%d, 高=%d\n', imgWidth, imgHeight);
    fprintf('ROI範圍: row [%d:%d], col [%d:%d]\n', rStart, rEnd, cStart, cEnd);
    
end

function checkROISR(folderPath, magName, rStart, rEnd, cStart, cEnd)
    fname = fullfile(folderPath, sprintf('%s (1).bmp', magName));
    if ~exist(fname, 'file')
        error('File not found: %s', fname);
    end

    img = imread(fname);
    [imgHeight, imgWidth, ~] = size(img);
    figure('Name', 'ROI Selection Check', 'Color', 'w');
    imshow(img, []);
    hold on;
    rectangle('Position', [cStart, rStart, cEnd - cStart, rEnd - rStart], ...
              'EdgeColor', 'r', 'LineWidth', 2);
    hold off;
    title('Check ROI Selection');
    fprintf('SR_ROI範圍: row [%d:%d], col [%d:%d]\n', rStart, rEnd, cStart, cEnd);
    fprintf('影像尺寸: 寬=%d, 高=%d\n', imgWidth, imgHeight);
    fprintf('SR_ROI範圍: row [%d:%d], col [%d:%d]\n', rStart, rEnd, cStart, cEnd);
    
end