script_dir = fileparts(mfilename('fullpath'));
load(fullfile(script_dir, 'spectrum.mat'));
psf_multi = zeros(101,101);           % [CHANGED] 2D，而非 [101 101 61]

for j = 580:580
    param.size = [101 101 1];         % [CHANGED] 直接在函式內生成單一 z 切片
    param.NA = 0.23;
    param.lambda = j*1e-9;
    param.M = 20;
    param.resLateral = 0.125  *1e-6;
    param.resAxial = 74*1e-9;
    param.tg = 0;
    param.tg0 = 0;
    param.ng0 = 1;
    param.ng = 1;
    param.ni0 = 1;
    param.ni = 1;
    param.pZ = 0;
    param.ti0 = 1e-3;

    psf = MicroscPSF(param);          % 回傳尺寸 [101 101 1]，已做 max-normalize
    % psf = psf.^2;                    % 若要使用強度平方，視需求解開

    % 按照 spectrum 權重做跨波長加總（僅 2D）
    psf_multi = psf_multi + double(psf(:,:,1)) * spectrum(2, j-400);   % [CHANGED]
end

% 以總能量歸一化（與你原本「以中心切片總和」的精神一致）
psf_multi = psf_multi ./ sum(psf_multi, 'all');   % [CHANGED]

% 簡單視覺化（取代 volumeViewer）
figure; imagesc(psf_multi); axis image off; colormap parula; colorbar;  % [CHANGED]

% 儲存 2D PSF（固定存到此 .m 檔所在資料夾）
save(fullfile(script_dir, 'psf_multi.mat'), 'psf_multi');        % [CHANGED]
