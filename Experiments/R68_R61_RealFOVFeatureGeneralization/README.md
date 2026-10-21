# R68 R61v16 Real-FOV Feature Generalization

## Question

Does the frozen R61v16 checkpoint preserve real measured motion consistently across many content-rich regions of the 5x, 20x, and 50x HS100MG fields of view?

## Scope

The six image sequences were acquired after R61v16 training and are therefore external to that checkpoint. They contain 301 real microscope frames. This experiment treats the sequence, not each tile, as the independent reporting unit.

The original locked R61v16 PSF-off reconstructions are reused only after checkpoint, command, frame-count, and image-shape validation. The analysis selects 24 content-rich 256x256 regions per sequence from the Raw first frame, keeps those regions fixed, and compares Raw versus R61 motion for every short-gap adjacent pair.

## Decision rule

Every sequence must pass all pilot gates:

- at least 90% valid local measurements;
- at least 95% motion-direction agreement;
- median R61/Raw motion scale within 10%;
- median R61-versus-Raw difference within 10% of the commanded step;
- 95th-percentile difference within 25% of the commanded step;
- median correlation-strength ratio at least 0.65;
- median bounded alignment agreement at least 0.90.

These are R68 pilot gates. Passing establishes cross-magnification and cross-field evidence for this acquisition, not universal cross-sample proof.

## Run

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' scripts\run_r68.py --stage all
```
