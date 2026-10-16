# R96 Manifest

| Area | Purpose | State |
|---|---|---|
| `config` | Locked independent design, execution policy and measured GPU batch plan | ready |
| `model` | Local, five-stage, tile-exact reconstruction model | verified |
| `training` | Exact procedural replay, localized supervision and protected updates | verified |
| `inference` | One canonical full/tiled reconstruction path | verified |
| `scripts` | Launch, monitor, preflight, capacity and data audits | verified |
| `tests` | Focused behavior and monitor checks | passed |
| `reports` | Fresh R96 preflight evidence | complete |
| `data` | Small policy/pointer plus live preview images; large arrays stay hash-locked at source | ready |
| `runs`, `weights`, `results`, `logs` | Reserved only for the sole R96 formal run | empty before launch |

Formal training is authorized only because the aggregate locked-design audit is
fully passing.  The formal launcher refuses a second independent run and the
trainer forbids checkpoint, resume, teacher, pseudo-label and pretrained inputs.

