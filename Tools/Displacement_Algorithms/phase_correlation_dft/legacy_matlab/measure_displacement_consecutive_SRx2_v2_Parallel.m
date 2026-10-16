%% (A) 參數設定
clearvars;
clc; close all;   % 測試階段可先註解掉

magnificationName = '0.32';    % 資料夾名稱(對應倍率)
subfolder1 = '10';
subfolder2 = '3.2';
subfolder3 = '1';
subfolder4 = '0.32';
subfolder5 = '0.1';

pixelSize = 3.2;             % (um/pixel)
theoryVal = 0.32;            % 每次小移動理論(um)

baseDir     = "D:\NonSystemFiles\GMM\ShiftCaculation";  % 主路徑
folderShift = fullfile(baseDir, 'Shift',    subfolder4);    % 原始資料夾
folderSR    = fullfile(baseDir, 'Shift_SR_2\0303_1700_x2', subfolder4); % 超解析資料夾1
folderSR2   = fullfile(baseDir, 'Shift_SR_2\0304_2200_x2', subfolder4); % 超解析資料夾2 (新增)

% ===(原圖) ROI：定位標靶 (示例)===
% 以範例 ROI: [row: 430~2730]、[col: 2500~4800]
roiRowStart = 430; 
roiRowEnd   = 2730; 
roiColStart = 2500; 
roiColEnd   = 4800;

% dftregistration 中的上採樣倍率
usfac  = 1000;   
% 共有 1..Nshots 張
Nshots = 11;    

%% (B) 量測: 原始資料夾 (Shift)
[distSteps_orig] = measureSmallSteps(folderShift, magnificationName, ...
    pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);

%% (C) 量測: 超解析資料夾 (Shift_SR)
srScale    = 2;                    
pixelSizeSR = pixelSize / srScale; 
roiRowStartSR = round((roiRowStart - 1)*srScale + 1);
roiRowEndSR   = round((roiRowEnd   - 1)*srScale + 1);
roiColStartSR = round((roiColStart - 1)*srScale + 1);
roiColEndSR   = round((roiColEnd   - 1)*srScale + 1);

[distSteps_sr] = measureSmallSteps(folderSR, magnificationName, ...
    pixelSizeSR, roiRowStartSR, roiRowEndSR, roiColStartSR, roiColEndSR, Nshots, usfac);

%% (D) 量測: 第二個超解析資料夾 (Shift_SR_2)
sr2Scale = 2;
pixelSizeSR2 = pixelSize / sr2Scale;
roiRowStartSR2 = round((roiRowStart - 1)*sr2Scale + 1);
roiRowEndSR2   = round((roiRowEnd   - 1)*sr2Scale + 1);
roiColStartSR2 = round((roiColStart - 1)*sr2Scale + 1);
roiColEndSR2   = round((roiColEnd   - 1)*sr2Scale + 1);

[distSteps_sr2] = measureSmallSteps(folderSR2, magnificationName, ...
    pixelSizeSR2, roiRowStartSR2, roiRowEndSR2, roiColStartSR2, roiColEndSR2, Nshots, usfac);

%% (E) 分析/顯示每次小移動 (逐步輸出)
shots   = 2:Nshots;  % 表示 (1->2), (2->3), ...
errOrig = distSteps_orig - theoryVal;
errSR   = distSteps_sr   - theoryVal;
errSR2  = distSteps_sr2  - theoryVal;

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

fprintf('\n--- [超解析 Shift_SR_2] ---\n');
for i = 1:numel(distSteps_sr2)
    shotPair = [shots(i)-1, shots(i)];
    fprintf('Shot(%2d->%2d): 實測=%.4f um, 誤差=%.4f um\n', ...
        shotPair(1), shotPair(2), distSteps_sr2(i), errSR2(i));
end

%% (E') 統計 (單步)
% 計算統計數據與波動性
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

errPctO  = (stdOrig / meanOrig) * 100;
errPctS  = (stdSR   / meanSR)   * 100;
errPctS2 = (stdSR2  / meanSR2)  * 100;

fprintf('\n==== 統計結果（波動性分析） ====\n');
fprintf('[Original - 小移動] mean=%.4f ± %.4f um, 誤差=%.4f ± %.4f um, 波動性=%.2f%%\n', ...
    meanOrig, stdOrig, meanErrO, stdErrO, errPctO);
fprintf('[SR       - 小移動] mean=%.4f ± %.4f um, 誤差=%.4f ± %.4f um, 波動性=%.2f%%\n', ...
    meanSR, stdSR, meanErrS, stdErrS, errPctS);
fprintf('[SR_2     - 小移動] mean=%.4f ± %.4f um, 誤差=%.4f ± %.4f um, 波動性=%.2f%%\n', ...
    meanSR2, stdSR2, meanErrS2, stdErrS2, errPctS2);

%% (F) 累計位移 (透過相鄰相加)
cumulativeDist_orig = [0, cumsum(distSteps_orig)];
cumulativeDist_sr   = [0, cumsum(distSteps_sr)];
cumulativeDist_sr2  = [0, cumsum(distSteps_sr2)];

cummShots   = 1:Nshots;
theoryCumm  = (cummShots - 1) * theoryVal;
cummErrOrig = cumulativeDist_orig - theoryCumm;
cummErrSR   = cumulativeDist_sr   - theoryCumm;
cummErrSR2  = cumulativeDist_sr2  - theoryCumm;

fprintf('\n=== 累計位移 (相對第1張) ===\n');
for i = 2:Nshots
    fprintf('Shot=%2d => Orig=%.4f (誤差=%.4f) | SR=%.4f (誤差=%.4f) | SR_2=%.4f (誤差=%.4f), Theory=%.4f\n',...
        i, cumulativeDist_orig(i), cummErrOrig(i), ...
           cumulativeDist_sr(i),   cummErrSR(i), ...
           cumulativeDist_sr2(i),  cummErrSR2(i), theoryCumm(i));
end

%% (G) 線性回歸分析與繪圖 (累計位移 + 線性擬合)
p_orig = polyfit(cummShots, cumulativeDist_orig, 1);
p_sr   = polyfit(cummShots, cumulativeDist_sr, 1);
p_sr2  = polyfit(cummShots, cumulativeDist_sr2, 1);

fit_orig = polyval(p_orig, cummShots);
fit_sr   = polyval(p_sr, cummShots);
fit_sr2  = polyval(p_sr2, cummShots);

R2_orig = 1 - sum((cumulativeDist_orig - fit_orig).^2) / sum((cumulativeDist_orig - mean(cumulativeDist_orig)).^2);
R2_sr   = 1 - sum((cumulativeDist_sr - fit_sr).^2) / sum((cumulativeDist_sr - mean(cumulativeDist_sr)).^2);
R2_sr2  = 1 - sum((cumulativeDist_sr2 - fit_sr2).^2) / sum((cumulativeDist_sr2 - mean(cumulativeDist_sr2)).^2);

figure('Name', 'Cumulative Displacement with Linear Regression', 'Color', 'w');
plot(cummShots, cumulativeDist_orig, '-o', 'LineWidth', 1.5); hold on;
plot(cummShots, cumulativeDist_sr,   '-s', 'LineWidth', 1.5);
plot(cummShots, cumulativeDist_sr2,  '-^', 'LineWidth', 1.5);
plot(cummShots, theoryCumm, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.2);
plot(cummShots, fit_orig, '--', 'Color', [0 0.447 0.741], 'LineWidth', 1.5);
plot(cummShots, fit_sr,   '--', 'Color', [0.85 0.325 0.098], 'LineWidth', 1.5);
plot(cummShots, fit_sr2,  '--', 'Color', [0.929 0.694 0.125], 'LineWidth', 1.5);
hold off;
legend('Orig Cum.', 'SR Cum.', 'SR_2 Cum.', 'Theory', 'Orig Fit', 'SR Fit', 'SR_2 Fit', 'Location', 'best');
xlabel('Shot #'); ylabel('Cumulative Displacement (um)');
title(sprintf('Cumulative Displacement & Linear Fit (Expected Step = %.2f um)', theoryVal));
text(2, max(cumulativeDist_orig)*0.9, sprintf('Orig: y=%.3fx + %.3f, R^2=%.8f', p_orig(1), p_orig(2), R2_orig), 'Color', [0 0.447 0.741], 'FontSize', 10);
text(2, max(cumulativeDist_orig)*0.8, sprintf('SR: y=%.3fx + %.3f, R^2=%.8f', p_sr(1), p_sr(2), R2_sr), 'Color', [0.85 0.325 0.098], 'FontSize', 10);
text(2, max(cumulativeDist_orig)*0.7, sprintf('SR_2: y=%.3fx + %.3f, R^2=%.8f', p_sr2(1), p_sr2(2), R2_sr2), 'Color', [0.929 0.694 0.125], 'FontSize', 10);

%% (G') 額外計算：直接量測「Shot i 相對 Shot 1」
[directDist_orig] = measureFromShot1(folderShift, magnificationName, pixelSize, roiRowStart, roiRowEnd, roiColStart, roiColEnd, Nshots, usfac);
[directDist_sr]   = measureFromShot1(folderSR,    magnificationName, pixelSizeSR, roiRowStartSR, roiRowEndSR, roiColStartSR, roiColEndSR, Nshots, usfac);
[directDist_sr2]  = measureFromShot1(folderSR2,   magnificationName, pixelSizeSR2, roiRowStartSR2, roiRowEndSR2, roiColStartSR2, roiColEndSR2, Nshots, usfac);

shotsDirect = 2:Nshots;
theoryDirect = (shotsDirect - 1) * theoryVal;
directErr_orig = directDist_orig(2:end) - theoryDirect;
directErr_sr   = directDist_sr(2:end)   - theoryDirect;
directErr_sr2  = directDist_sr2(2:end)  - theoryDirect;

fprintf('\n=== 直接量測「Shot i 相對 Shot 1」 ===\n');
for i = 2:Nshots
    idx = i-1;
    fprintf('Shot=%2d => Orig=%.4f (Err=%.4f) | SR=%.4f (Err=%.4f) | SR_2=%.4f (Err=%.4f), Theory=%.4f\n',...
        i, directDist_orig(i), directErr_orig(idx), directDist_sr(i), directErr_sr(idx), directDist_sr2(i), directErr_sr2(idx), (i-1)*theoryVal);
end

%% (H) 繪圖 (3x2 子圖，包含每次小移動、穩定性、累計位移與累計誤差)
figure('Name', 'Analysis Results (include SR_2 + Direct vs. Shot1)', 'Color', 'w');

% 1) 每次小移動
subplot(2,2,1);
plot(shots, distSteps_orig, '-o', 'LineWidth', 1.5); hold on;
plot(shots, distSteps_sr,   '-s', 'LineWidth', 1.5);
plot(shots, distSteps_sr2,  '-^', 'LineWidth', 1.5);
yline(theoryVal, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.2, 'Label', 'Theory');
hold off;
legend('Original', 'SR', 'SR_2', 'Location', 'best');
xlabel('Shot Transition (i->i+1)'); ylabel('Displacement (um)');
title(sprintf('Each small step, expected = %.2f um', theoryVal));

% 2) 穩定性 (每一步與平均步距的差異)
subplot(2,2,2);
stabilityOrig = distSteps_orig - meanOrig;
stabilitySR   = distSteps_sr - meanSR;
stabilitySR2  = distSteps_sr2 - meanSR2;
plot(shots, stabilityOrig, '-o', 'LineWidth', 1.5); hold on;
plot(shots, stabilitySR,   '-s', 'LineWidth', 1.5);
plot(shots, stabilitySR2,  '-^', 'LineWidth', 1.5);
yline(0, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.2);
hold off;
legend('Orig Stability','SR Stability','SR_2 Stability','Location','best');
xlabel('Shot Transition (i->i+1)'); ylabel('Deviation (um)');
title('Stability: each step - average step');

% 3) 累計位移 vs. 理論
subplot(2,2,3);
plot(cummShots, cumulativeDist_orig, '-o', 'LineWidth', 1.5); hold on;
plot(cummShots, cumulativeDist_sr,   '-s', 'LineWidth', 1.5);
plot(cummShots, cumulativeDist_sr2,  '-^', 'LineWidth', 1.5);
plot(cummShots, theoryCumm, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.2);
hold off;
legend('Orig Cum.','SR Cum.','SR_2 Cum.','Theory','Location','best');
xlabel('Shot #'); ylabel('Cumulative displacement (um)');
title(sprintf('Cumulative displacement, each step = %.2f um', theoryVal));

% 4) 累計位移誤差
subplot(2,2,4);
plot(cummShots, cummErrOrig, '-o', 'LineWidth', 1.5); hold on;
plot(cummShots, cummErrSR,   '-s', 'LineWidth', 1.5);
plot(cummShots, cummErrSR2,  '-^', 'LineWidth', 1.5);
yline(0, '--', 'Color', [0.5 0.5 0.5], 'LineWidth', 1.2);
hold off;
legend('Orig Cumm. Err.','SR Cumm. Err.','SR_2 Cumm. Err.','Location','best');
xlabel('Shot #'); ylabel('Cumulative error (um)');
title('Cumulative error from shot1');

%% （以下為函數部分）

%% (1) 相鄰影像量測: measureSmallSteps
function [distStep_um] = measureSmallSteps(folderPath, magName, pixelSize, rStart, rEnd, cStart, cEnd, Nshots, usfac)
    % 檢查是否有可用的 GPU（僅在非並列環境下啟用）
    useGPU = (gpuDeviceCount > 0);
    
    % 預先配置暫存變數
    tempDist = zeros(1, Nshots-1);
    tempRowShift = zeros(1, Nshots-1);
    tempColShift = zeros(1, Nshots-1);

    % 使用 parfor 並列處理，每次僅讀取所需的兩張影像
    parfor iShot = 1:(Nshots-1)
        localUseGPU = useGPU;
        if ~isempty(getCurrentTask())
            localUseGPU = false;  % 並列環境中禁用 GPU 加速
        end
        fname1 = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot));
        fname2 = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot+1));
        if ~exist(fname1, 'file') || ~exist(fname2, 'file')
            tempDist(iShot) = NaN;
            tempRowShift(iShot) = NaN;
            tempColShift(iShot) = NaN;
        else
            tmpImg1 = imread(fname1);
            roi1 = im2double(tmpImg1(rStart:rEnd, cStart:cEnd));
            tmpImg2 = imread(fname2);
            roi2 = im2double(tmpImg2(rStart:rEnd, cStart:cEnd));
            if localUseGPU
                F1 = fft2(gpuArray(roi1));
                F2 = fft2(gpuArray(roi2));
                output = dftregistration(F1, F2, usfac);
                output = gather(output);
            else
                output = dftregistration(fft2(roi1), fft2(roi2), usfac);
            end
            rowShift_pix = output(3);
            colShift_pix = output(4);
            dist_pix = sqrt(rowShift_pix^2 + colShift_pix^2);
            tempDist(iShot) = dist_pix * pixelSize;
            tempRowShift(iShot) = rowShift_pix;
            tempColShift(iShot) = colShift_pix;
        end
    end
    distStep_um = tempDist;
    
    % 依序輸出各次計算結果
    for iShot = 1:(Nshots-1)
        fprintf('Shot(%2d->%2d): RowShift=%.4f pix, ColShift=%.4f pix, Distance=%.4f um\n',...
            iShot, iShot+1, tempRowShift(iShot), tempColShift(iShot), tempDist(iShot));
        drawnow; pause(0.01);
    end
    fprintf('\n');
end

%% (2) 直接量測「Shot i 相對 Shot 1」: measureFromShot1
function [distShot1_um] = measureFromShot1(folderPath, magName, pixelSize, rStart, rEnd, cStart, cEnd, Nshots, usfac)
    useGPU = (gpuDeviceCount > 0);
    distShot1_um = zeros(1, Nshots);
    distShot1_um(1) = 0;  % 第一張相對自己為 0

    fname1 = fullfile(folderPath, sprintf('%s (%d).bmp', magName, 1));
    if ~exist(fname1, 'file')
        warning('File not found: %s', fname1);
        return;
    end
    tmpImg1 = imread(fname1);
    roi1 = im2double(tmpImg1(rStart:rEnd, cStart:cEnd));
    if useGPU && isempty(getCurrentTask())
        F1 = fft2(gpuArray(roi1));
    else
        F1 = fft2(roi1);
    end

    parfor iShot = 2:Nshots
        localUseGPU = useGPU;
        if ~isempty(getCurrentTask())
            localUseGPU = false;
        end
        fname = fullfile(folderPath, sprintf('%s (%d).bmp', magName, iShot));
        if ~exist(fname, 'file')
            distShot1_um(iShot) = NaN;
        else
            tmpImg = imread(fname);
            roiCurrent = im2double(tmpImg(rStart:rEnd, cStart:cEnd));
            if localUseGPU
                F2 = fft2(gpuArray(roiCurrent));
                output = dftregistration(F1, F2, usfac);
                output = gather(output);
            else
                output = dftregistration(fft2(roi1), fft2(roiCurrent), usfac);
            end
            rowShift_pix = output(3);
            colShift_pix = output(4);
            distShot1_um(iShot) = sqrt(rowShift_pix^2 + colShift_pix^2) * pixelSize;
        end
    end
end
