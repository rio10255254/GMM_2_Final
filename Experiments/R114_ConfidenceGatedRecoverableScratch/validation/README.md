# R114 fixed validation scaffold

This folder is the model-independent validation entry point.  It intentionally
does not train or choose a model.  A model adapter supplies
`load_model(checkpoint, device)` and the model returns either an image tensor or
a mapping/object containing `output` plus spatial internal maps.

The shared validation always records:

- finite output and internal-map checks;
- clear, identity, and flat-image change;
- metrics split by geometry family and role;
- full-frame versus three tile layouts, including a shifted origin, overlap,
  and a second core/halo pair;
- pairwise tile-layout parity and seam-band error;
- lossless internal-map arrays plus PNG previews.

Example:

```powershell
C:\Users\Rio\anaconda3\python.exe validation\run_validation.py `
  --adapter validation\fixtures\fake_adapter.py `
  --manifest results\validation_smoke\manifest.json `
  --output results\validation_smoke\validation `
  --device cpu
```

`tool_inventory.json` freezes the existing ACM, LSC, real-sequence, tile, and
internal-map tools that later R114 qualification should call without silently
retuning their measurement logic.

## Split-profile locked ACM entry point

`run_split_profile_locked_acm.py` evaluates one frozen split-profile checkpoint
against the unchanged R73 and R74 MATLAB ACM contracts.  With no `--smoke`
flag, it reconstructs every sealed ACM sample, saves both Raw and reconstructed
BMP inputs, runs the locked primary and sensitivity protocols, and writes
method, family, and zero-failure summaries under the requested output folder.

Complete evaluation after checkpoint selection:

```powershell
C:\Users\Rio\anaconda3\python.exe validation\run_split_profile_locked_acm.py `
  --checkpoint runs\RUN_ID\weights\epoch_NNN.pth `
  --output results\split_profile_locked_acm\epoch_NNN `
  --method-name R114SplitENNN `
  --suite R73 R74 `
  --device cuda:0
```

The `--smoke` flag is explicitly non-formal.  It uses one primary image from
the first family but retains the original ACM implementation, parameters,
three sensitivity images, three sensitivity presets, alignments, and metric
definitions.  `--prepare-only` checks reconstruction and contract preparation
without launching MATLAB.
