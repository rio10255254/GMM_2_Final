# Wiener Deconvolution Spectrum Design

## Goal

Add one standalone spatial-frequency spectrum for the fitted-PSF Wiener deconvolution result at 20x and 50x. The new figures must be directly comparable with the existing captured and V42 spectra without per-image visual enhancement.

## Source and calculation

- Read the unquantized `restored` array from each current Wiener result MAT file.
- Require the stored NSR to equal the accepted fixed value, 0.08.
- Compute absolute FFT amplitude as `abs(fftshift(fft2(restored))) / pixel_count`.
- Convert to dBFS with `20*log10(amplitude)`, using a numerical floor only to avoid log of zero.
- Do not clip the input, subtract its mean, apply a window, smooth the spectrum, or normalize each spectrum to its own peak.

## Display and outputs

- Use the same fixed -80 to 0 dBFS color scale already used for the captured and V42 spectra.
- Save one white-background RGB PNG per magnification as `09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png` beside the related 09 deconvolved image.
- State in the subtitle that the source is the unclipped Wiener result and that the display scale is shared.
- Add the exact deconvolved amplitude and dBFS arrays to each magnification's numeric spectrum archive.
- Record the MAT source, `restored` array name, and NSR in the spectrum manifest; update the shared-scale scope from four to six spectra.

## Verification

- Recompute the expected spectrum from the MAT `restored` array and require exact numerical agreement with the saved array.
- Verify both new figures are readable, RGB, large enough for labels, and use the fixed shared scale.
- Open both figures and visually check the title, subtitle, axes, colorbar, white background, and absence of clipping or layout collisions.
