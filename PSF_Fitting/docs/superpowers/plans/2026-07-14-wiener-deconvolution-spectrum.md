# Wiener Deconvolution Spectrum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add honest standalone absolute spectra for the current 20x and 50x fitted-PSF Wiener deconvolution results.

**Architecture:** Extend the existing calibrated-spectrum generator so captured, V42, and Wiener outputs share one renderer and one fixed dBFS scale. Read Wiener data from the unquantized `restored` MAT array, save both amplitude and dBFS arrays in the existing numeric archive, and verify those arrays by independently recomputing them from the MAT source.

**Tech Stack:** Python 3.12, NumPy, SciPy, Pillow, Matplotlib, pytest

---

### Task 1: Add the failing deconvolution-spectrum acceptance check

**Files:**
- Modify: `D:\GMM_2_Final\PSF_Fitting\tests\python\test_center9_wiener_evidence.py`

- [ ] **Step 1: Extend the existing spectrum test**

Import `loadmat`, define the Wiener source folder, and require:

```python
assert manifest["shared_display_scale"] == "all six spectra"
assert manifest["wiener_source_normalization"] == (
    "20*log10(abs(fftshift(fft2(restored)))/pixel_count); "
    "0 dBFS is a constant floating-point image with value 1.0"
)
assert manifest["wiener_array"] == "restored"
assert manifest["wiener_full_scale_reference"] == 1.0

result = loadmat(WIENER_ROOT / f"{magnification}_wiener_deconvolution.mat")
restored = np.asarray(result["restored"], dtype=float)
assert float(np.asarray(result["nsr"]).squeeze()) == 0.08
assert restored.ndim == 2 and np.isfinite(restored).all()
expected_amplitude = np.abs(np.fft.fftshift(np.fft.fft2(restored))) / restored.size
expected_dbfs = 20.0 * np.log10(
    np.maximum(expected_amplitude, np.finfo(float).tiny)
)
np.testing.assert_allclose(
    data["deconvolved_amplitude"], expected_amplitude, rtol=0, atol=1e-12
)
np.testing.assert_allclose(
    data["deconvolved_dbfs"], expected_dbfs, rtol=0, atol=1e-12
)
for key in (
    "captured_amplitude", "captured_dbfs", "v42_amplitude", "v42_dbfs",
    "deconvolved_amplitude", "deconvolved_dbfs",
):
    assert np.isfinite(data[key]).all()
    assert data[key].shape == restored.shape
assert data["fx_cycles_per_pixel"].shape == (restored.shape[1],)
assert data["fy_cycles_per_pixel"].shape == (restored.shape[0],)
assert np.isfinite(data["fx_cycles_per_pixel"]).all()
assert np.isfinite(data["fy_cycles_per_pixel"]).all()
assert manifest["records"][magnification]["wiener_source"] == str(
    WIENER_ROOT / f"{magnification}_wiener_deconvolution.mat"
)
assert manifest["records"][magnification]["wiener_array"] == "restored"
assert manifest["records"][magnification]["wiener_nsr"] == 0.08
```

Also require `09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png` to be a readable RGB image larger than 1000 pixels in each dimension.

- [ ] **Step 2: Run the targeted test and verify the new requirement fails**

Run:

```powershell
python -m pytest tests\python\test_center9_wiener_evidence.py -q
```

Expected: the spectrum test fails because the manifest, archive keys, and new PNG do not exist yet.

### Task 2: Extend the calibrated-spectrum generator

**Files:**
- Modify: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\spectra\generate_absolute_spectra.py`

- [ ] **Step 1: Add one array-based calculation path**

Add a helper that accepts the floating-point Wiener array without dividing by 255:

```python
def absolute_fft_amplitude_array(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(image, dtype=float)
    if image.ndim != 2 or not np.isfinite(image).all():
        raise ValueError("Spectrum source must be a finite two-dimensional array")
    amplitude = np.abs(np.fft.fftshift(np.fft.fft2(image))) / image.size
    dbfs = 20.0 * np.log10(np.maximum(amplitude, np.finfo(float).tiny))
    return amplitude, dbfs
```

- [ ] **Step 2: Load and validate the Wiener source**

For each magnification, load exactly these current MAT files:

- `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\psf_deconvolution_cd\20x_wiener_deconvolution.mat`
- `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\psf_deconvolution_cd\50x_wiener_deconvolution.mat`

Require exact equality `nsr == 0.08`, read `restored`, require a finite two-dimensional array, and require its shape to match captured and V42.

- [ ] **Step 3: Save numeric arrays and the standalone figure**

Add `deconvolved_amplitude` and `deconvolved_dbfs` to the existing NPZ archive. Render the latter through the existing `save_spectrum` function to:

```text
09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png
```

Use the title `<magnification> fitted-PSF Wiener deconvolution: spatial-frequency spectrum` and a subtitle that states the source is the unclipped Wiener result, NSR is 0.08, and the scale is shared.

Parameterize only the renderer subtitle. Pass the existing subtitle unchanged to the four captured/V42 figures and the new Wiener-specific subtitle to the two new figures. Keep the renderer's -80 to 0 dBFS scale, colormap, cycles-per-pixel axes, frequency extent, lower orientation, nearest-neighbour interpolation, and equal aspect ratio unchanged.

- [ ] **Step 4: Update provenance without weakening existing metadata**

Replace the global 8-bit-only quantity description with a source-neutral description covering absolute FFT amplitude for all supplied arrays. Keep the captured/V42 `image/255` normalization statement in explicit image-source metadata. Add separate Wiener normalization, 1.0 full-scale reference, exact MAT source, array name, NSR, minimum/maximum dBFS, and set shared scale scope to all six spectra.

### Task 3: Regenerate and verify the evidence

**Files:**
- Regenerate: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\center9_pillar_fit_20x_50x\20x\09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png`
- Regenerate: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\center9_pillar_fit_20x_50x\50x\09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png`
- Regenerate: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\spectra\20x_absolute_spectra.npz`
- Regenerate: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\spectra\50x_absolute_spectra.npz`
- Regenerate: `D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\spectra\spectrum_manifest.json`

- [ ] **Step 1: Run the spectrum generator**

Run:

```powershell
python "D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\spectra\generate_absolute_spectra.py"
```

Expected: exit 0, both Wiener records report NSR 0.08, and the manifest says all six spectra share one scale.

- [ ] **Step 2: Run the complete targeted acceptance test**

Run:

```powershell
python -m pytest tests\python\test_center9_wiener_evidence.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Inspect both new figures**

Open both new PNGs at original detail and verify white background, complete title/subtitle, cycles-per-pixel axes, colorbar, no cropped labels, and a visually honest -80 to 0 dBFS scale.

- [ ] **Step 4: Run the final numerical gate**

Re-run the Task 1 acceptance test, which recomputes both amplitude and dBFS arrays from each exact MAT source with `rtol=0`, `atol=1e-12` and checks provenance, finite values, matching grids and shapes, readable RGB files, and `per_image_peak_normalization == false`. Add only an output inventory check here; do not defer new requirements beyond the failing test.

- [ ] **Step 5: Commit the focused implementation**

Stage only the plan, test, generator, manifest, numeric archives, and two new figures that belong to this change. Do not stage unrelated worktree changes.
