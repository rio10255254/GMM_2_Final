# R129 manifest

Profile: self-contained source; immutable shared R128 data and selected weights are referenced, not duplicated. Measured PSF buffers alone are imported from V42; learned V42 network weights are not transferred.

Primary requirements: functioning measured-PSF mean/adaptive fusion; V42-style bilinear / reflected binomial filter / convolution upsampling; original-image high-frequency anchor and image-quality adjustment. Claims remain limited to the tests actually executed. The calibration bank is inherited from the V42 study and is not an independent SEM holdout.

The calibrated PSF origin, kernel shapes, normalization, adaptive strength and differing module placement must be stated explicitly. V42's stored adaptive output scale is zero; new active fusion cannot be claimed to reproduce that inactive saved branch.

The actual execution state is recorded in config/plan.json, config/implementation_v2.json and reports/R129_RESULTS.md. All 96 planned short-pilot updates and 864 normal-SEM readings completed. This does not establish efficacy, novelty, full training or promotion. No old confirmation payload is read.

Retained candidate: runs/D/step24.pth (13d73d34f7aafc806bd2d56b7b1ac845d0b150d28fdc2fa9a07acc29cea838ee). Experimental controls A/B/C and all initialization checkpoints remain available. Model implementation is model/hybrid_v2.py; standalone image entry is scripts/infer_image.py. Shared R128 training arrays and parent weights are immutable external dependencies listed in config/plan.json. V42 calibration source is independently listed in data/PSF_PROVENANCE.json.

Delivery map: results/verification.json covers actual inputs, weights, independently recalculated measurements and a real full-image replay. results/figure_sources.json records chart sources and the public entry replay. results/index_registration.json preserves the previous current-state indexes before adding R129; it does not replace historical receipt dependencies. Code, plans, logs, tables, images and representative checkpoints remain on D within the 4 GiB budget; no source cleanup was performed.
