# Temporary optical input: compatibility contract

This optional inference adapter lives only in the independent workspace. The original model package and checkpoint under D:/GMM_2_Final are unchanged.

- Native default: without an external kernel, the original 25-kernel bank and learned selector run unchanged.
- Temporary single kernel: `configure_optical_input(model, cfg, model_root, kernel)` accepts one finite, nonnegative, normalized 101x101 measured PSF. Both optical paths use it with mixture weight one. Learned selector parameters remain present but dormant.
- Restore: `configure_optical_input(model, cfg, model_root, None)` or `restore_native_optics(model)` restores the original modules and clears cached optical transforms.

The generic interface contains no magnification, physical pixel scale, filename, image resampling or training logic. `install_50x` is only this experiment's provenance wrapper. Pixel-to-length conversion remains in the measurement configuration.

Use try/finally restoration for temporary evaluation in a long-lived process. Do not save the temporary optical state over the delivered checkpoint. Other PSF counts or replacement multi-kernel banks require a verified mapping to selector outputs; unsupported counts are rejected instead of duplicated or guessed.

The compatibility check covers independent convolution/inverse-filter calculations, both optical paths, stale-cache clearing, unchanged learned parameters, full-frame/tiled agreement, invalid count rejection, exact native-to-single-to-native-to-single restoration, and exact replay of a saved full 50x frame.

Initial 50x inference used the mathematically identical adapter preserved as `sources/objective_optics_first50run.py`; its hash matches the installation record. The current reversible wrapper exactly reproduces the checked saved full-frame output. Both preflight records remain available.

Preserving software compatibility does not establish universal performance on untested objectives or samples.
