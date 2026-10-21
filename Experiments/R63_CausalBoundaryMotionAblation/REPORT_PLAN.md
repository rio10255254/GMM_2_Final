# R63 Technical Report Plan

## Reporting job

- Audience: technical thesis reader.
- Question: which MOSR innovations improve boundary localization and displacement stability under a matched optical prior and training recipe?
- Decision supported: whether a module-level causal statement is strong enough to add to the thesis, and exactly how narrow that statement must be.
- Comparison basis: matched full control, 2 x 2 geometry-motion factorial, seven loss-component removals, three matched output-module removals, matched upsampling pair, and final-checkpoint output-path bypasses.
- Success criterion: cross-seed direction consistency, at least 10% practical effect, paired 95% interval above zero, and no material guardrail failure.
- Time frame: R63 execution opened 2026-07-16; report is a fixed result snapshot.
- Delivery: portable HTML technical report because no MCP report renderer is callable in this desktop task. Thesis-ready figures remain separate MATLAB PNG/PDF files.
- Status: complete; the final report is answer-first, contains the adverse 50x ringing result, and keeps unsupported module-level claims out of the recommended thesis wording.

## Answer-first spine

1. State which mechanisms are supported, suggestive, or unsupported.
2. Show the primary cross-seed causal contrasts before detailed methods.
3. Define removal penalty, populations, physical units, fixed-30 rule, and SEM reference geometry.
4. Explain the matched 2 x 2 design, seven loss-component contrasts, three output-module retraining contrasts, architecture pair, and inference-only audit.
5. Show sensitivity, ringing, invalid-boundary, convergence, and data-independence checks near the findings they qualify.
6. Separate the package-manifest-unseen 50x capture and synthetic shifts from same-domain 20x/displacement results.
7. Recommend only the chapter claims warranted by the evidence; list unresolved questions.

## Required technical-report structure mapping

| Required role | Visible report section |
|---|---|
| Title | `R63 MOSR Causal Ablation Report` |
| Technical summary | `What the experiment establishes` |
| Key findings with visual evidence | One section each for geometry, motion, upsampling, and output protection |
| Scope, data, and definitions | `What was measured and on which populations` |
| Methodology | `Matched causal design` |
| Model / experimental validation detail | `Reproducibility and invariants` |
| Limitations and robustness | `Where the evidence is strong and where it is not` |
| Recommended next steps | `What may be written into the thesis` |
| Further questions | `Open checks before final submission` |

No required section is omitted. Reproducibility is separated from methodology because artifact identity, optical invariance, and convergence are decision-critical.

## Evidence inventory

- Pre-registered protocol and config snapshots.
- Thirty-two matched training runs, globally extended to sixty epochs because the frozen convergence gate triggered.
- Checkpoint structure and optical tensor audit.
- Independent 50x SEM-linked image and 360 known-shift cases.
- Same-domain 20x CD frame and four Raw-ranked 30-step sequences.
- Static CD, edge width, ringing, synthetic equivariance, and displacement tables.
- A full-control-versus-identical-Raw context audit so causal removal penalties are not reported without absolute performance context.
- Factorial, component, architecture, output-protection, bootstrap, and convergence tables.
- English MATLAB figures and visual-QA record.

## Omission record

- New external NTU GMF reconstruction is omitted unless the deleted original input sequences are restored. Existing old-model reconstructions are not reused as if they were Raw inputs. The package-manifest-unseen 50x known-shift set is the predeclared substitute; earlier checkpoint ancestry remains unproven and visible in the report.
