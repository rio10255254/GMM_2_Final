# Diagnostic results

The primary current physical experiment is `area_render_v2/`. The root `physical_fit.csv`, `physical_fit.png`, and the physical portion of `operator_summary.json` are preserved **rasterization-confounded v1 results**. Do not use them as the final physical motion evidence. The repair changes latent occupancy integration only; see `config/area_render_v2.json` one level above this directory.

`operator_matrix.csv` and the operator/identifiability portions of `operator_summary.json` remain current. They include failed sampled operations.

`v42_provenance_summary.json` and `v42_provenance_extension.json` are complementary source audits. Tables retain individual memberships and differences. Eligibility is not a complete historical per-batch access log. `protected_inputs.json` and `protected_extension.json` preserve hashes read in this round, while independent verification also checks the old R119 expectations without replacing them.

`independent_verification.json` checks the first diagnostic outputs; `final_verification.json` additionally checks corrected physical results and final deliverables. A successful consistency check does not mean the failed operators or models are accepted.

All generated tables are reproducible diagnostic data, not sealed holdout evidence. No checkpoint was created. Retain the complete small folder locally; no archive/deletion is needed.
