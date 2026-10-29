# R125 identity

- Run identity: `r125_data_fit_pilot_20260908`.
- Profile: self-contained source-independent data and bounded exploratory learning.
- Branch: `codex/r125-data-aligned-pilot`.
- Current run truth: `runs/matrix_state.json`; individual training `runs/{A|B|C}_s{seed}/state.json` and `summary.json`.
- Admitted data: `data/package_v2/manifest.json`, SHA256 `f371ed372f7ed73e015e10dae5295bb25cbd86573a581b6a283ce66277ed35f4`.
- Original rejected data: `data/package/manifest.json`, admission remains false and original evidence unchanged.
- Planned actual study:64scenes x2views,64updates per arm/start,3arms x2starts=384updates. No best-checkpoint search.
- Controls: A omits explicit observation steps; B includes them; C adds geometry/reference-consistency supervision. Common data/order/initial tensors and unchanged image/observation/reference losses.
- True model inputs: source image tensor and known simulation observation profile. No target, SEM, stage position truth, sample ID or teacher output enters the network feature input.
- Real evaluation: six optical images plus six fixed first-frame pairs/ROIs, same12 initial/final evaluations, all-model common SEM profile population. No independent stage truth or qualified material/optical mapping.
- Known simulator calibration is not known real microscope calibration; all real qualification flags remain false.
- Initial data failure, precision diagnosis, runtime helper failure, original dense runtime, numerical Raw replay drift and all corrections are retained separately.
- Completion requires same-run checkpoints,384ledger updates, exactscene/order/source verification, all12real evaluations, final aggregation and independent execution audit. Training completion is not scientific promotion.
