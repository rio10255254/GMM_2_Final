function build_wiener_linewidth_crops()
    PROJECT_ROOT = fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))))));
%BUILD_WIENER_LINEWIDTH_CROPS Apply the fixed 50x Wiener baseline to the line ROI.

outputRoot = fileparts(fileparts(mfilename('fullpath')));
cropRoot = fullfile(outputRoot, 'wiener_crops');
if ~exist(cropRoot, 'dir'); mkdir(cropRoot); end

psfPath = [fullfile(PROJECT_ROOT, 'PSF_Fitting/output/deconvolution_baseline_psf_20260715'), ...
    '\50x\fit_result\PSF_fitted_2D_FOVstack.mat'];
loaded = load(psfPath, 'psf_grid');
psf = squeeze(double(loaded.psf_grid));
psf = psf ./ sum(psf(:));

nsr = 0.050;
pitchPx = 72.5;
% Python analysis coordinates: x=100, y=90, width=700, height=560.
innerRect = [101, 91, 800, 650]; % MATLAB inclusive coordinates.
marginPx = 100;

sequences = struct( ...
    'name', {'50x_x_0p5um', '50x_x_1um'}, ...
    'rawDir', { ...
        fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp'), ...
        fullfile(PROJECT_ROOT, 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp')}, ...
    'lastFrame', {50, 49});

for sequenceIndex = 1:numel(sequences)
    sequence = sequences(sequenceIndex);
    destination = fullfile(cropRoot, sequence.name);
    if ~exist(destination, 'dir'); mkdir(destination); end

    for frameIndex = 0:sequence.lastFrame
        inputPath = fullfile(sequence.rawDir, sprintf('frame_%04d.bmp', frameIndex));
        imageData = im2double(imread(inputPath));
        if ndims(imageData) == 3
            imageData = rgb2gray(imageData);
        end

        expandedRect = [ ...
            max(1, innerRect(1) - marginPx), ...
            max(1, innerRect(2) - marginPx), ...
            min(size(imageData, 2), innerRect(3) + marginPx), ...
            min(size(imageData, 1), innerRect(4) + marginPx)];
        expanded = imageData(expandedRect(2):expandedRect(4), ...
            expandedRect(1):expandedRect(3));
        restoredExpanded = restore_dark_line_roi(expanded, psf, nsr, pitchPx);

        localX1 = innerRect(1) - expandedRect(1) + 1;
        localY1 = innerRect(2) - expandedRect(2) + 1;
        localX2 = localX1 + innerRect(3) - innerRect(1);
        localY2 = localY1 + innerRect(4) - innerRect(2);
        restoredCrop = restoredExpanded(localY1:localY2, localX1:localX2);

        outputPath = fullfile(destination, sprintf('frame_%04d.bmp', frameIndex));
        imwrite(im2uint8(min(max(restoredCrop, 0), 1)), outputPath);
    end
end

manifest = struct();
manifest.method = ['Fixed-PSF Wiener deconvolution using the same NSR 0.05 baseline; ', ...
    'symmetric padding, edge tapering, and background-normalized dark-line contrast.'];
manifest.psf = psfPath;
manifest.nsr = nsr;
manifest.pitch_px = pitchPx;
manifest.analysis_roi_python = struct('x', 100, 'y', 90, 'width', 700, 'height', 560);
manifest.processing_margin_px = marginPx;
manifest.frame_count = 101;
fid = fopen(fullfile(outputRoot, 'wiener_linewidth_manifest.json'), 'w');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(manifest, PrettyPrint=true), 'char');

fprintf('Exported 101 Wiener line-ROI crops to %s\n', cropRoot);
end

function restored = restore_dark_line_roi(imageData, psf, nsr, pitchPx)
backgroundRadius = max(2, ceil(0.36 * pitchPx));
background = imclose(imageData, strel('disk', backgroundRadius));
contrast = max(background - imageData, 0);
contrastScale = prctile(contrast(:), 99.5);
contrast = contrast ./ max(contrastScale, eps);

padY = floor(size(psf, 1) / 2);
padX = floor(size(psf, 2) / 2);
padded = padarray(contrast, [padY padX], 'symmetric', 'both');
padded = edgetaper(padded, psf);
restoredPadded = deconvwnr(padded, psf, nsr);
restoredContrast = restoredPadded(padY + 1:padY + size(imageData, 1), ...
    padX + 1:padX + size(imageData, 2));
restoredContrast = min(max(restoredContrast, 0), 1.25);
restored = background - contrastScale .* restoredContrast;
end
