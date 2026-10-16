function [output, Greg] = dftregistration_hf(buf1ft,buf2ft,usfac,cutoff_D0)
% Efficient subpixel image registration by crosscorrelation, MODIFIED FOR
% HIGH-FREQUENCY (HF) REGISTRATION.
%
% This version adds a high-pass filter to focus the registration on
% high-frequency details, useful for evaluating super-resolution results.
%
% Original author: Manuel Guizar - Dec 13, 2007
% HF modifications by AI assistant - Aug 12, 2025
%
% NEW INPUTS:
% cutoff_D0 (optional) Cutoff frequency for the Gaussian high-pass filter.
%           A smaller value (e.g., 20) means a stronger filter, only
%           allowing very high frequencies. A larger value (e.g., 50) is
%           weaker. If not provided or NaN, it performs standard registration.
%
% Copyright (c) 2016, Manuel Guizar Sicairos, James R. Fienup, University of Rochester
% All rights reserved. (Original license applies)

%%% MODIFICATION START: Handle new optional input %%%
if ~exist('usfac','var') || isempty(usfac)
    usfac = 1;
end
if ~exist('cutoff_D0','var')
    cutoff_D0 = 30; % Default to standard registration
end
%%% MODIFICATION END %%%

[nr,nc]=size(buf2ft);
Nr = ifftshift(-fix(nr/2):ceil(nr/2)-1);
Nc = ifftshift(-fix(nc/2):ceil(nc/2)-1);

%%% MODIFICATION START: Create and apply High-Pass filter %%%
% 1. Calculate the original cross-power spectrum
cross_power_spectrum = buf1ft .* conj(buf2ft);

% 2. If a cutoff frequency is provided, filter the spectrum
if ~isnan(cutoff_D0) && cutoff_D0 > 0
    % Create the filter (DC in center)
    H_hp = create_gaussian_highpass_filter([nr, nc], cutoff_D0);
    % Apply the filter. Since input FT has DC at (1,1), we must ifftshift
    % the filter to align it before multiplication.
    cross_power_spectrum = cross_power_spectrum .* ifftshift(H_hp);
end
%%% MODIFICATION END %%%

if usfac == 0
    % Simple computation of error and phase difference without registration
    CCmax = sum(cross_power_spectrum(:)); % Use modified spectrum
    row_shift = 0;
    col_shift = 0;
elseif usfac == 1
    % Single pixel registration
    %%% MODIFICATION: Use the filtered spectrum %%%
    CC = ifft2(cross_power_spectrum);
    CCabs = abs(CC);
    [row_shift, col_shift] = find(CCabs == max(CCabs(:)));
    CCmax = CC(row_shift,col_shift)*nr*nc;
    % Now change shifts so that they represent relative shifts and not indices
    row_shift = Nr(row_shift);
    col_shift = Nc(col_shift);
elseif usfac > 1
    % Start with usfac == 2
    %%% MODIFICATION: Use the filtered spectrum %%%
    CC = ifft2(FTpad(cross_power_spectrum,[2*nr,2*nc]));
    CCabs = abs(CC);
    [row_shift, col_shift] = find(CCabs == max(CCabs(:)),1,'first');
    CCmax = CC(row_shift,col_shift)*nr*nc;
    % Now change shifts so that they represent relative shifts and not indices
    Nr2 = ifftshift(-fix(nr):ceil(nr)-1);
    Nc2 = ifftshift(-fix(nc):ceil(nc)-1);
    row_shift = Nr2(row_shift)/2;
    col_shift = Nc2(col_shift)/2;
    % If upsampling > 2, then refine estimate with matrix multiply DFT
    if usfac > 2
        %%% DFT computation %%%
        % Initial shift estimate in upsampled grid
        row_shift = round(row_shift*usfac)/usfac; 
        col_shift = round(col_shift*usfac)/usfac;     
        dftshift = fix(ceil(usfac*1.5)/2); %% Center of output array at dftshift+1
        % Matrix multiply DFT around the current shift estimate
        %%% MODIFICATION: Use the filtered spectrum %%%
        CC = conj(dftups(conj(cross_power_spectrum),ceil(usfac*1.5),ceil(usfac*1.5),usfac,...
            dftshift-row_shift*usfac,dftshift-col_shift*usfac));
        % Locate maximum and map back to original pixel grid 
        CCabs = abs(CC);
        [rloc, cloc] = find(CCabs == max(CCabs(:)),1,'first');
        CCmax = CC(rloc,cloc);
        rloc = rloc - dftshift - 1;
        cloc = cloc - dftshift - 1;
        row_shift = row_shift + rloc/usfac;
        col_shift = col_shift + cloc/usfac;    
    end
    % If its only one row or column the shift along that dimension has no
    % effect. Set to zero.
    if nr == 1
        row_shift = 0;
    end
    if nc == 1
        col_shift = 0;
    end
    
end  

rg00 = sum(abs(buf1ft(:)).^2);
rf00 = sum(abs(buf2ft(:)).^2);
error = 1.0 - abs(CCmax).^2/(rg00*rf00);
error = sqrt(abs(error));
diffphase = angle(CCmax);
output=[error,diffphase,row_shift,col_shift];
% Compute registered version of buf2ft
if (nargout > 1)&&(usfac > 0)
    [Nc_grid,Nr_grid] = meshgrid(Nc,Nr);
    Greg = buf2ft.*exp(1i*2*pi*(-row_shift*Nr_grid/nr-col_shift*Nc_grid/nc));
    Greg = Greg*exp(1i*diffphase);
elseif (nargout > 1)&&(usfac == 0)
    Greg = buf2ft*exp(1i*diffphase);
end

return
end % End of main function dftregistration_hf

%%% MODIFICATION START: Added helper function %%%
function H_hp = create_gaussian_highpass_filter(shape, cutoff_D0)
% Creates a Gaussian high-pass filter in the frequency domain.
% The filter is created with DC (zero frequency) at the center.
[rows, cols] = deal(shape(1), shape(2));
center_row = floor(rows/2) + 1;
center_col = floor(cols/2) + 1;

[u, v] = meshgrid(1:cols, 1:rows);
du = u - center_col;
dv = v - center_row;

D_sq = du.^2 + dv.^2;
H_lp = exp(-D_sq / (2 * cutoff_D0^2)); % Gaussian Low-pass
H_hp = 1 - H_lp;                      % Gaussian High-pass
end
%%% MODIFICATION END %%%

% --- (The unmodified dftups and FTpad functions from the original file should be here) ---
function out=dftups(in,nor,noc,usfac,roff,coff)
[nr,nc]=size(in);
if exist('roff', 'var')~=1, roff=0;  end
if exist('coff', 'var')~=1, coff=0;  end
if exist('usfac','var')~=1, usfac=1; end
if exist('noc',  'var')~=1, noc=nc;  end
if exist('nor',  'var')~=1, nor=nr;  end
kernc=exp((-1i*2*pi/(nc*usfac))*( ifftshift(0:nc-1).' - floor(nc/2) )*( (0:noc-1) - coff ));
kernr=exp((-1i*2*pi/(nr*usfac))*( (0:nor-1).' - roff )*( ifftshift(0:nr-1) - floor(nr/2)  ));
out=kernr*in*kernc;
return
end

function [ imFTout ] = FTpad(imFT,outsize)
if ~ismatrix(imFT)
    error('Maximum number of array dimensions is 2')
end
Nout = outsize;
Nin = size(imFT);
imFT = fftshift(imFT);
center = floor(size(imFT)/2)+1;
imFTout = zeros(outsize);
centerout = floor(size(imFTout)/2)+1;
cenout_cen = centerout - center;
imFTout(max(cenout_cen(1)+1,1):min(cenout_cen(1)+Nin(1),Nout(1)),max(cenout_cen(2)+1,1):min(cenout_cen(2)+Nin(2),Nout(2))) ...
    = imFT(max(-cenout_cen(1)+1,1):min(-cenout_cen(1)+Nout(1),Nin(1)),max(-cenout_cen(2)+1,1):min(-cenout_cen(2)+Nout(2),Nin(2)));
imFTout = ifftshift(imFTout)*Nout(1)*Nout(2)/(Nin(1)*Nin(2));
return
end