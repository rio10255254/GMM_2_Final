# Wiener Deconvolution Spectrum Design

## Goal

Add one standalone spatial-frequency spectrum for the fitted-PSF Wiener deconvolution result at 20x and 50x. The new figures must be directly comparable with the existing captured and V42 spectra without per-image visual enhancement.

## Source and calculation

- Read the unquantized `restored` array from each current Wiener result MAT file.
- Require the stored NSR to equal the accepted fixed value, 0.08.
- Compute absolute FFT amplitude as `abs(fftshift(fft2(restored))) / pixel_count`.
- Convert to dBFS with `20*log10(max(amplitude, np.finfo(float).tiny))`. For this floating-point Wiener source, 0 dBFS means the FFT amplitude of a constant image whose value is 1.0.
- Do not clip the input, subtract its mean, apply a window, smooth the spectrum, or normalize each spectrum to its own peak.

## Display and outputs

- Use the same fixed -80 to 0 dBFS color scale already used for the captured and V42 spectra.
- Reuse the existing spectrum renderer without changing the colormap, cycles-per-pixel axes, frequency extent, orientation, nearest-neighbour interpolation, or equal aspect ratio.
- Save one white-background RGB PNG per magnification as `09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png` beside the related 09 deconvolved image.
- State in the subtitle that the source is the unclipped Wiener result and that the display scale is shared.
- Add the exact arrays to each magnification's numeric spectrum archive as `deconvolved_amplitude` and `deconvolved_dbfs`.
- Keep the existing `image/255` normalization metadata for captured and V42 sources, and add separate Wiener normalization metadata for the floating-point `restored` array.
- Record the MAT source, `restored` array name, NSR, and the 1.0 full-scale reference in the spectrum manifest; update the shared-scale scope from four to six spectra.
- Values below -80 dBFS may intentionally share the darkest display color, while the saved numeric arrays retain their complete values.

## Verification

- Recompute both amplitude and dBFS from the MAT `restored` array and compare them with `deconvolved_amplitude` and `deconvolved_dbfs` using zero relative tolerance and absolute tolerance `1e-12`.
- Require the saved deconvolution arrays, source array, frequency grids, and related captured/V42 arrays to have matching shapes and finite values.
- Verify both new figures are readable, RGB, large enough for labels, and use the fixed shared scale.
- Open both figures and visually check the title, subtitle, axes, colorbar, white background, and absence of cropped labels or layout collisions. Display saturation below -80 dBFS is expected and must not be confused with source or numeric-array clipping.
