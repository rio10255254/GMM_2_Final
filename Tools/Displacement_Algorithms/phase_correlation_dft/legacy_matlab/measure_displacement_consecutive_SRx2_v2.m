%% (A) 參數設定
clearvars;
clc; close all;  

magnificationName = '1';    % 資料夾名稱(對應倍率)
subfolder1 = '10';
subfolder2 = '3.2';
subfolder3 = '1';
subfolder4 = '0.32';
subfolder5 = '1';

pixelSize = 3.2;             % (um/pixel)
theoryVal = 0.32;              % 每次小移動理論(um)

baseDir     = "D:\NonSystemFiles\GMM\ShiftCaculation";                   % 主路徑
folderShift = fullfile(baseDir, 'Shift',    subfolder4);                 % 原始資料夾
folderSR    = fullfile(baseDir, 'Shift_SR_2\0318_1000_x2',    subfolder4);  % 超解析資料夾1
folderSR2   = fullfile(baseDir, 'Shift_SR_2\0310_1600_x2',    subfolder4);  % 超解析資料夾2

% ===(原圖) ROI：定位標靶 (示例)===
%   下列範例為切取 [row: 376~1476]、[col: 3333~4433] 這塊。
roiRowStart = 430; 
roiRowEnd   = 2730; 
roiColStart = 2500; 
roiColEnd   = 4800;

% roiRowStart = 1000; 
% roiRowEnd   = 3600; 
% roiColStart = 1700; 
% roiColEnd   = 4300;

% dftregistration 中的上採樣倍率
usfac  = 1000;   
% 共有 1..Nshots 張
Nshots = 11;    

%% (B) 量測: 原始資料夾 (Shift)
[distSteps_orig] = measureSmallSteps(folderShift, magnificationName, ...
    pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);

%% (C) 量測: 超解析資料夾 (Shift_SR)

% ----------------------------------------------------------
% (1) 超解析影像放大倍率 (假設一樣是 2)
% ----------------------------------------------------------
srScale    = 2;                    
% ----------------------------------------------------------
% (2) 對應的 pixel size 變為原本的一半
% ----------------------------------------------------------
pixelSizeSR = pixelSize / srScale; 
% ----------------------------------------------------------
% (3) ROI也要乘上 srScale，以鎖定「與原圖同樣的實際區域」
% ----------------------------------------------------------
roiRowStartSR = (roiRowStart - 1)*srScale + 1;
roiRowEndSR   = (roiRowEnd   - 1)*srScale + 1;
roiColStartSR = (roiColStart - 1)*srScale + 1;
roiColEndSR   = (roiColEnd   - 1)*srScale + 1;

% roiRowStartSR = 430; 
% roiRowEndSR   = 2230; 
% roiColStartSR = 2500; 
% roiColEndSR   = 4300;
% 
% roiRowStartSR = 1000; 
% roiRowEndSR   = 3600; 
% roiColStartSR = 1700; 
% roiColEndSR   = 4300;

roiRowStartSR = round(roiRowStartSR);
roiRowEndSR   = round(roiRowEndSR);
roiColStartSR = round(roiColStartSR);
roiColEndSR   = round(roiColEndSR);

[distSteps_sr] = measureSmallSteps(folderSR, magnificationName, ...
    pixelSizeSR, roiRowStartSR, roiRowEndSR, roiColStartSR, roiColEndSR, ...
    Nshots, usfac);

%% (D) 量測: 第二個超解析資料夾 (Shift_SR_2) -- (同樣倍率、ROI設定)
% 若 Shift_SR_2 的倍率不同，請自行調整
sr2Scale = 2;
pixelSizeSR2 = pixelSize / sr2Scale;

roiRowStartSR2 = (roiRowStart - 1)*sr2Scale + 1;
roiRowEndSR2   = (roiRowEnd   - 1)*sr2Scale + 1;
roiColStartSR2 = (roiColStart - 1)*sr2Scale + 1;
roiColEndSR2   = (roiColEnd   - 1)*sr2Scale + 1;

% roiRowStartSR2 = 430; 
% roiRowEndSR2   = 2230; 
% roiColStartSR2 = 2500; 
% roiColEndSR2   = 4300;
% 
% roiRowStartSR2 = 1000; 
% roiRowEndSR2   = 3600; 
% roiColStartSR2 = 1700; 
% roiColEndSR2   = 4300;

roiRowStartSR2 = round(roiRowStartSR2);
roiRowEndSR2   = round(roiRowEndSR2);
roiColStartSR2 = round(roiColStartSR2);
roiColEndSR2   = round(roiColEndSR2);

[distSteps_sr2] = measureSmallSteps(folderSR2, magnificationName, ...
    pixelSizeSR2, roiRowStartSR2, roiRowEndSR2, roiColStartSR2, roiColEndSR2, ...
    Nshots, usfac);

%% (E) 分析/顯示每次小移動
shots   = 2:Nshots;  % 表示 (1->2), (2->3), ...
errOrig = distSteps_orig - theoryVal;
errSR   = distSteps_sr   - theoryVal;
errSR2  = distSteps_sr2  - theoryVal;

fprintf('\n==== 每次相鄰影像的小移動 (相對前一張) vs. 理論=%.3f um ====\n\n', theoryVal);
drawnow;
pause(0.05);

fprintf('--- [原始資料 Shift] ---\n');
drawnow;
pause(0.05);
for i = 1:numel(distSteps_orig)
    shotPair = [shots(i)-1, shots(i)];
    fprintf('Shot(%2d->%2d): 實測=%.4f um, 誤差=%.4f um\n', ...
        shotPair(1), shotPair(2), distSteps_orig(i), errOrig(i));
    drawnow;
    pause(0.05);
end

fprintf('\n--- [超解析 Shift_SR] ---\n');
drawnow;
pause(0.05);
for i = 1:numel(distSteps_sr)
    shotPair = [shots(i)-1, shots(i)];
    fprintf('Shot(%2d->%2d): 實測=%.4f um, 誤差=%.4f um\n', ...
        shotPair(1), shotPair(2), distSteps_sr(i), errSR(i));
    drawnow;
    pause(0.05);
end

fprintf('\n--- [超解析 Shift_SR_2] ---\n');
drawnow;
pause(0.05);
for i = 1:numel(distSteps_sr2)
    shotPair = [shots(i)-1, shots(i)];
    fprintf('Shot(%2d->%2d): 實測=%.4f um, 誤差=%.4f um\n', ...
        shotPair(1), shotPair(2), distSteps_sr2(i), errSR2(i));
    drawnow;
    pause(0.05);
end

%% (E') 統計 (單步)
% 計算誤差
errOrig = distSteps_orig - theoryVal;
errSR   = distSteps_sr   - theoryVal;
errSR2  = distSteps_sr2  - theoryVal;

% 計算統計數據
meanOrig = mean(distSteps_orig);
stdOrig  = std(distSteps_orig);
meanErrO = mean(errOrig);
stdErrO  = std(errOrig);

meanSR   = mean(distSteps_sr);
stdSR    = std(distSteps_sr);
meanErrS = mean(errSR);
stdErrS  = std(errSR);

meanSR2   = mean(distSteps_sr2);
stdSR2    = std(distSteps_sr2);
meanErrS2 = mean(errSR2);
stdErrS2  = std(errSR2);

% === 誤差佔比計算（波動性分析）===
% 根據標準差與平均值計算波動性
errPctO  = (stdOrig / meanOrig) * 100;   % Original 的波動性百分比
errPctS  = (stdSR / meanSR)     * 100;   % SR 的波動性百分比
errPctS2 = (stdSR2 / meanSR2)   * 100;   % SR_2 的波動性百分比

% 結果輸出
fprintf('\n==== 統計結果（波動性分析） ====\n');

% 顯示 Original 結果
fprintf('[Original - 小移動] mean=%.4f ± %.4f um, 誤差=%.4f ± %.4f um, 波動性=%.2f%%\n', ...
    meanOrig, stdOrig, meanErrO, stdErrO, errPctO);
drawnow; pause(0.05);

% 顯示 SR 結果
fprintf('[SR       - 小移動] mean=%.4f ± %.4f um, 誤差=%.4f ± %.4f um, 波動性=%.2f%%\n', ...
    meanSR, stdSR, meanErrS, stdErrS, errPctS);
drawnow; pause(0.05);

% 顯示 SR_2 結果
fprintf('[SR_2     - 小移動] mean=%.4f ± %.4f um, 誤差=%.4f ± %.4f um, 波動性=%.2f%%\n', ...
    meanSR2, stdSR2, meanErrS2, stdErrS2, errPctS2);
drawnow; pause(0.05);



%% (F) 累計位移 (透過「相鄰相加」)
cumulativeDist_orig = [0, cumsum(distSteps_orig)];
cumulativeDist_sr   = [0, cumsum(distSteps_sr)];
cumulativeDist_sr2  = [0, cumsum(distSteps_sr2)];

cummShots   = 1:Nshots;
theoryCumm  = (cummShots - 1)*theoryVal;
cummErrOrig = cumulativeDist_orig - theoryCumm;
cummErrSR   = cumulativeDist_sr   - theoryCumm;
cummErrSR2  = cumulativeDist_sr2  - theoryCumm;

fprintf('\n=== 累計位移(相對第1張) ===\n');
drawnow;
pause(0.05);
for i = 2:Nshots
    fprintf('Shot=%2d => Orig=%.4f(誤差=%.4f) | SR=%.4f(誤差=%.4f) | SR2=%.4f(誤差=%.4f), Theory=%.4f\n',...
        i, ...
        cumulativeDist_orig(i), cummErrOrig(i), ...
        cumulativeDist_sr(i),   cummErrSR(i), ...
        cumulativeDist_sr2(i),  cummErrSR2(i), ...
        theoryCumm(i));
    drawnow;
    pause(0.05);
end

%% **線性回歸分析**
% 計算線性擬合
p_orig = polyfit(cummShots, cumulativeDist_orig, 1);
p_sr   = polyfit(cummShots, cumulativeDist_sr, 1);
p_sr2  = polyfit(cummShots, cumulativeDist_sr2, 1);

% 計算 R-squared (相關係數)
fit_orig = polyval(p_orig, cummShots);
fit_sr   = polyval(p_sr, cummShots);
fit_sr2  = polyval(p_sr2, cummShots);

R2_orig = 1 - sum((cumulativeDist_orig - fit_orig).^2) / sum((cumulativeDist_orig - mean(cumulativeDist_orig)).^2);
R2_sr   = 1 - sum((cumulativeDist_sr - fit_sr).^2) / sum((cumulativeDist_sr - mean(cumulativeDist_sr)).^2);
R2_sr2  = 1 - sum((cumulativeDist_sr2 - fit_sr2).^2) / sum((cumulativeDist_sr2 - mean(cumulativeDist_sr2)).^2);

%% (G) 繪製 累計位移 + 線性擬合
figure('Name', 'Cumulative Displacement with Linear Regression', 'Color', 'w');

plot(cummShots, cumulativeDist_orig, '-o', 'LineWidth', 1.5); hold on;
plot(cummShots, cumulativeDist_sr,   '-s', 'LineWidth', 1.5);
plot(cummShots, cumulativeDist_sr2,  '-^', 'LineWidth', 1.5);
plot(cummShots, theoryCumm, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.2);

% 繪製線性回歸擬合線
plot(cummShots, fit_orig, '--', 'Color', [0 0.447 0.741], 'LineWidth', 1.5);
plot(cummShots, fit_sr,   '--', 'Color', [0.85 0.325 0.098], 'LineWidth', 1.5);
plot(cummShots, fit_sr2,  '--', 'Color', [0.929 0.694 0.125], 'LineWidth', 1.5);

hold off;
legend('Orig Cum.', 'SR Cum.', 'SR_2 Cum.', 'Theory', 'Orig Fit', 'SR Fit', 'SR_2 Fit', 'Location', 'best');
xlabel('Shot #');
ylabel('Cumulative Displacement (um)');
title(sprintf('Cumulative Displacement & Linear Fit (Expected Step = %.2f um)', theoryVal));

% 標註擬合方程與 R^2 值
text(2, max(cumulativeDist_orig)*0.9, sprintf('Orig: y=%.3fx + %.3f, R^2=%.8f', p_orig(1), p_orig(2), R2_orig), 'Color', [0 0.447 0.741], 'FontSize', 10);
text(2, max(cumulativeDist_orig)*0.8, sprintf('SR: y=%.3fx + %.3f, R^2=%.8f', p_sr(1), p_sr(2), R2_sr), 'Color', [0.85 0.325 0.098], 'FontSize', 10);
text(2, max(cumulativeDist_orig)*0.7, sprintf('SR_2: y=%.3fx + %.3f, R^2=%.8f', p_sr2(1), p_sr2(2), R2_sr2), 'Color', [0.929 0.694 0.125], 'FontSize', 10);

disp('=== 完成: 累計位移分析與線性回歸 ===');


%% (G) 額外計算：直接量測「Shot i 相對 Shot 1」的位移
%    (而非先前相鄰疊加)，以評估放大後是否對直接對準比較準
[directDist_orig] = measureFromShot1(folderShift, magnificationName, ...
    pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);

[directDist_sr] = measureFromShot1(folderSR, magnificationName, ...
    pixelSizeSR, roiRowStartSR, roiRowEndSR, roiColStartSR, roiColEndSR, Nshots, usfac);

[directDist_sr2] = measureFromShot1(folderSR2, magnificationName, ...
    pixelSizeSR2, roiRowStartSR2, roiRowEndSR2, roiColStartSR2, roiColEndSR2, Nshots, usfac);

% 每張 i (從第2張開始) 的理論位移為 (i-1)*theoryVal
shotsDirect = 2:Nshots;
theoryDirect = (shotsDirect - 1)*theoryVal;

directErr_orig = directDist_orig(2:end) - theoryDirect;
directErr_sr   = directDist_sr(2:end)   - theoryDirect;
directErr_sr2  = directDist_sr2(2:end)  - theoryDirect;

fprintf('\n=== 直接量測「Shot i 相對 Shot 1」 ===\n');
drawnow;
pause(0.05);
for i = 2:Nshots
    idx = i-1;  % 用來索引 directErr_xxx
    fprintf('Shot=%2d => Orig=%.4f(Err=%.4f) | SR=%.4f(Err=%.4f) | SR2=%.4f(Err=%.4f), Theory=%.4f\n',...
        i, ...
        directDist_orig(i), directErr_orig(idx), ...
        directDist_sr(i),   directErr_sr(idx), ...
        directDist_sr2(i),  directErr_sr2(idx), ...
        (i-1)*theoryVal);
    drawnow;
    pause(0.05);
end


fprintf('\n=== Step Stability Measure: each step minus the average step ===\n');
drawnow;
pause(0.05);

fprintf('meanOrig = %.4f, || meanSR =  %.4f, || meanSR2 = %.4f\n',...
    meanOrig, meanSR, meanSR2);
drawnow;
pause(0.05);

% 每一步相對平均位移的偏差 (stability measure)
stabilityOrig = distSteps_orig - meanOrig;
stabilitySR   = distSteps_sr   - meanSR;
stabilitySR2  = distSteps_sr2  - meanSR2;

for i = 1:numel(distSteps_orig)
    fprintf('Step #%2d: Orig=%.4f (meanDiff=%.4f), SR=%.4f (meanDiff=%.4f), SR2=%.4f (meanDiff=%.4f)\n',...
        i, distSteps_orig(i), stabilityOrig(i), ...
           distSteps_sr(i),   stabilitySR(i),   ...
           distSteps_sr2(i),  stabilitySR2(i));
end


%% (H) 繪圖 (升級為3x2六宮格，包含每次小移動、誤差、累計、以及直接量測之比較)
figure('Name', 'Analysis Results (include SR_2 + Direct vs. Shot1)', 'Color', 'w');

% 1) 每次小移動
subplot(2,2,1);
plot(shots, distSteps_orig, '-o','LineWidth',1.5); hold on;
plot(shots, distSteps_sr,   '-s','LineWidth',1.5);
plot(shots, distSteps_sr2,  '-^','LineWidth',1.5);
yline(theoryVal,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2,'Label','Theory');
hold off;
legend('Original','SR','SR_2','Location','best');
xlabel('Shot Transition (i->i+1)');
ylabel('Displacement of each step (um)');
title(sprintf('Each small step, expected=%.2f um', theoryVal));

% % 2) 每次小移動誤差
% subplot(3,2,2);
% plot(shots, errOrig, '-o','LineWidth',1.5); hold on;
% plot(shots, errSR,   '-s','LineWidth',1.5);
% plot(shots, errSR2,  '-^','LineWidth',1.5);
% yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
% hold off;
% legend('OrigErr','SRErr','SR_2Err','Location','best');
% xlabel('Shot Transition (i->i+1)');
% ylabel('Error (um) = measured - theory');
% title('Error per small step');

% ---------------------------------------------------------------------
% 2) 每一步與「平均步距」的差異 (Stability measure)
subplot(2,2,2);
plot(shots, stabilityOrig, '-o','LineWidth',1.5); hold on;
plot(shots, stabilitySR,   '-s','LineWidth',1.5);
plot(shots, stabilitySR2,  '-^','LineWidth',1.5);
yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
hold off;
legend('OrigStability','SRStability','SR_2Stability','Location','best');
xlabel('Shot Transition (i->i+1)');
ylabel('Deviation from mean step (um)');
title('Stability: each step - average step');
% ---------------------------------------------------------------------


% 3) 累計位移 vs. 理論 (相鄰疊加)
subplot(2,2,3);
plot(cummShots, cumulativeDist_orig, '-o','LineWidth',1.5); hold on;
plot(cummShots, cumulativeDist_sr,   '-s','LineWidth',1.5);
plot(cummShots, cumulativeDist_sr2,  '-^','LineWidth',1.5);
plot(cummShots, theoryCumm,         '--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
hold off;
legend('OrigCum','SRCum','SR_2Cum','Theory','Location','best');
xlabel('Shot #');
ylabel('Cumulative distance (um) from shot1');
title(sprintf('Cumulative displacement, each step=%.2f um', theoryVal));

% 4) 累計位移誤差
subplot(2,2,4);
plot(cummShots, cummErrOrig, '-o','LineWidth',1.5); hold on;
plot(cummShots, cummErrSR,   '-s','LineWidth',1.5);
plot(cummShots, cummErrSR2,  '-^','LineWidth',1.5);
yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
hold off;
legend('OrigCummErr','SRCummErr','SR_2CummErr','Location','best');
xlabel('Shot #');
ylabel('Cumulative error (um)');
title('Cumulative error from shot1');

% % 5) 直接量測「Shot i 相對 Shot 1」之實際距離
% subplot(3,2,5);
% plot( shotsDirect, directDist_orig(2:end), '-o','LineWidth',1.5 ); hold on;
% plot( shotsDirect, directDist_sr(2:end),   '-s','LineWidth',1.5 );
% plot( shotsDirect, directDist_sr2(2:end),  '-^','LineWidth',1.5 );
% plot( shotsDirect, theoryDirect,           '--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
% hold off;
% legend('OrigDirect','SRDirect','SR_2Direct','Theory','Location','best');
% xlabel('Shot #');
% ylabel('Distance from shot1 (um)');
% title('Direct measurement: shot i vs. shot1');
% 
% % 6) 直接量測「Shot i 相對 Shot 1」之誤差
% subplot(3,2,6);
% plot( shotsDirect, directErr_orig, '-o','LineWidth',1.5 ); hold on;
% plot( shotsDirect, directErr_sr,   '-s','LineWidth',1.5 );
% plot( shotsDirect, directErr_sr2,  '-^','LineWidth',1.5 );
% yline(0,'--','Color',[0.5 0.5 0.5],'LineWidth',1.2);
% hold off;
% legend('OrigDirectErr','SRDirectErr','SR_2DirectErr','Location','best');
% xlabel('Shot #');
% ylabel('Error (um)');
% title('Direct error: measured - theory (shot i vs shot1)');
% 
% disp('=== 完成: 各種量測與繪圖 ===');


%% -------------------------------------------------------------
% (1) 相鄰影像量測: measureSmallSteps

% function [distStep_um] = measureSmallSteps(folderPath, magName, pixelSize, ...
%     rStart, rEnd, cStart, cEnd, Nshots, usfac)
%     % 讀取所有影像(ROI)進入 cell array
%     allROIs = cell(1,Nshots);
%     for iShot = 1:Nshots
%         % 構造檔名
%         fname = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot));
%         if ~exist(fname,'file')
%             warning('File not found: %s', fname);
%             allROIs{iShot} = [];
%         else
%             tmpImg = imread(fname);
% 
%             % 依 ROI 擷取
%             tmpROI = im2double(tmpImg(rStart:rEnd, cStart:cEnd));
%             allROIs{iShot} = tmpROI;
%         end
%     end
% 
%     distStep_um = zeros(1, Nshots-1);
% 
%     % 相鄰影像 => (iShot vs iShot+1)
%     for iShot = 1 : (Nshots-1)
%         roi1 = allROIs{iShot};
%         roi2 = allROIs{iShot+1};
%         if isempty(roi1) || isempty(roi2)
%             distStep_um(iShot) = NaN;
%             continue;
%         end
% 
%         [output, ~] = dftregistration(fft2(roi1), fft2(roi2), usfac);
%         rowShift_pix = output(3);
%         colShift_pix = output(4);
%         dist_pix = sqrt(rowShift_pix^2 + colShift_pix^2);
%         dist_um  = dist_pix * pixelSize;
% 
%         distStep_um(iShot) = dist_um;
% %         fprintf('Shot(%2d->%2d): rowShift=%.4f pix, colShift=%.4f pix => %.4f pix => %.4f um\n',...
% %             iShot, iShot+1, rowShift_pix, colShift_pix, dist_pix, dist_um);
%     end
% end

function [distStep_um] = measureSmallSteps(folderPath, magName, pixelSize, ...
    rStart, rEnd, cStart, cEnd, Nshots, usfac)

    allROIs = cell(1, Nshots);
    for iShot = 1:Nshots
        fname = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot));
        if ~exist(fname, 'file')
            warning('File not found: %s', fname);
            allROIs{iShot} = [];
        else
            tmpImg = imread(fname);
            tmpROI = im2double(tmpImg(rStart:rEnd, cStart:cEnd));
            allROIs{iShot} = tmpROI;
        end
    end

    distStep_um = zeros(1, Nshots-1);

    for iShot = 1 : (Nshots-1)
        roi1 = allROIs{iShot};
        roi2 = allROIs{iShot+1};
        if isempty(roi1) || isempty(roi2)
            distStep_um(iShot) = NaN;
            continue;
        end
        
        [output, ~] = dftregistration_hf(fft2(roi1), fft2(roi2), usfac);
        rowShift_pix = output(3);
        colShift_pix = output(4);
        dist_pix = sqrt(rowShift_pix^2 + colShift_pix^2);
        dist_um  = dist_pix * pixelSize;
        distStep_um(iShot) = dist_um;

        % **即時顯示結果**
        fprintf('Shot(%2d->%2d): RowShift=%.4f pix, ColShift=%.4f pix, Distance=%.4f um\n',...
                iShot, iShot+1, rowShift_pix, colShift_pix, dist_um);
        drawnow;  
        pause(0.01);
    end
    fprintf('\n');
end


%% (2) 直接量測「Shot i 相對 Shot 1」: measureFromShot1
function [distShot1_um] = measureFromShot1(folderPath, magName, pixelSize, ...
    rStart, rEnd, cStart, cEnd, Nshots, usfac)

    % 讀取所有影像(ROI)
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

    distShot1_um = zeros(1, Nshots);
    distShot1_um(1) = 0; % 第1張相對第1張，當然是 0

    roi1 = allROIs{1};
    if isempty(roi1)
        warning('First shot ROI is empty, cannot measure direct distance.');
        return;
    end

    % 依序與第1張對齊 (i=2..Nshots)
    for iShot = 2:Nshots
        roiCurrent = allROIs{iShot};
        if isempty(roiCurrent)
            distShot1_um(iShot) = NaN;
            continue;
        end

        [output, ~] = dftregistration_hf(fft2(roi1), fft2(roiCurrent), usfac);
        rowShift_pix = output(3);
        colShift_pix = output(4);
        dist_pix = sqrt(rowShift_pix^2 + colShift_pix^2);
        dist_um  = dist_pix * pixelSize;
        distShot1_um(iShot) = dist_um;
    end
end

% %% (3) 顯示影像與ROI函數(可選)
% function checkROI(folderPath, magName, rStart, rEnd, cStart, cEnd)
%     fname = fullfile(folderPath, sprintf('%s (1).bmp', magName));
%     if ~exist(fname, 'file')
%         error('File not found: %s', fname);
%     end
% 
%     img = imread(fname);
%     [imgHeight, imgWidth, ~] = size(img);
%     figure('Name', 'ROI Selection Check', 'Color', 'w');
%     imshow(img, []);
%     hold on;
%     rectangle('Position', [cStart, rStart, cEnd - cStart, rEnd - rStart], ...
%               'EdgeColor', 'r', 'LineWidth', 2);
%     hold off;
%     title('Check ROI Selection');
%     fprintf('ROI範圍: row [%d:%d], col [%d:%d]\n', rStart, rEnd, cStart, cEnd);
%     fprintf('影像尺寸: 寬=%d, 高=%d\n', imgWidth, imgHeight);
% end
% 
% function checkROISR(folderPath, magName, rStart, rEnd, cStart, cEnd)
%     fname = fullfile(folderPath, sprintf('%s (1).bmp', magName));
%     if ~exist(fname, 'file')
%         error('File not found: %s', fname);
%     end
% 
%     img = imread(fname);
%     [imgHeight, imgWidth, ~] = size(img);
%     figure('Name', 'ROI Selection Check (SR)', 'Color', 'w');
%     imshow(img, []);
%     hold on;
%     rectangle('Position', [cStart, rStart, cEnd - cStart, rEnd - rStart], ...
%               'EdgeColor', 'r', 'LineWidth', 2);
%     hold off;
%     title('Check ROI Selection (SR)');
%     fprintf('SR_ROI範圍: row [%d:%d], col [%d:%d]\n', rStart, rEnd, cStart, cEnd);
%     fprintf('影像尺寸: 寬=%d, 高=%d\n', imgWidth, imgHeight);
% end
