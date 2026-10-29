# R61 v16 training-data representative real images

這包圖的用途：從訓練資料角度，展示 R61 v16 相比舊模型多了哪些真實資料，以及這些資料補強了什麼。

## Dataset check

- Dataset: `Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16`
- Target: `boundary_generalization_without_same_sample_posthoc_correction`
- Total pairs: `20296`
- Role counts: `{'legacy_shape': 800, 'motion_synthetic': 4800, 'motion_texture_synthetic': 4800, 'sem_truth_anchor': 1400, 'sequence_guard': 1200, 'step_guard_motion_texture_synthetic': 3200, 'universal_synthetic': 4096}`
- Anti-answer-leakage design: `True`

## Source overview

- `source_100mg_basler_real_image_overview.png`: 100MG Basler 原始影像的中心區域，可當作真實資料來源的總覽圖。

## Selected images

### new_sem_truth_pillar_real_crop

- Training role: `sem_truth_anchor`
- Shape/type: `pillar`
- Clean image: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sem_truth_pillar_real_crop_clean.png`
- Boundary overlay: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sem_truth_pillar_real_crop_boundary_overlay.png`
- Why this matters: 100MG 圓柱真實 crop，邊界答案來自 SEM 錨點，是這次邊界尺寸準度提升最直接的資料。
- Compared with old model: 舊模型較缺少同一套光學條件下的真實尺寸錨點，容易只把邊緣變銳但尺寸偏掉。

### new_sem_truth_via_real_crop

- Training role: `sem_truth_anchor`
- Shape/type: `via`
- Clean image: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sem_truth_via_real_crop_clean.png`
- Boundary overlay: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sem_truth_via_real_crop_boundary_overlay.png`
- Why this matters: 100MG 圓孔真實 crop，補上與圓柱相反的亮暗/內外邊界情況。
- Compared with old model: 舊模型若偏向單一形狀或單一極性，碰到圓孔時容易把邊界方向修錯。

### new_sequence_guard_pillar_real_crop

- Training role: `sequence_guard`
- Shape/type: `pillar`
- Clean image: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sequence_guard_pillar_real_crop_clean.png`
- Boundary overlay: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sequence_guard_pillar_real_crop_boundary_overlay.png`
- Why this matters: 圓柱 sequence guard 真實 crop，用較保守的邊界答案約束模型，避免連續影像重建後位置抖動。
- Compared with old model: 舊模型常把單張圖修得銳利，但連續影像之間不一定穩定。

### new_sequence_guard_via_real_crop

- Training role: `sequence_guard`
- Shape/type: `via`
- Clean image: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sequence_guard_via_real_crop_clean.png`
- Boundary overlay: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/new_sequence_guard_via_real_crop_boundary_overlay.png`
- Why this matters: 圓孔 sequence guard 真實 crop，用來讓孔洞邊界在連續影像中也不要亂漂。
- Compared with old model: 舊模型對孔洞與圓柱的穩定性不一定一致，容易造成位移讀值不對稱。

### old_style_legacy_ring

- Training role: `legacy_shape`
- Shape/type: `ring`
- Clean image: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/old_style_legacy_ring_clean.png`
- Boundary overlay: `Thesis_MOSR_Evidence/Experiments/20260626_training_data_representatives/images/old_style_legacy_ring_boundary_overlay.png`
- Why this matters: 舊模型比較熟悉的環形/理想形狀資料，可用來對照這次不是只靠舊環形資料。
- Compared with old model: 舊資料對真實 100MG 顯微紋理、圓柱/圓孔極性、SEM 尺寸錨點都比較弱。

## Plain-language slide message

- 以前模型比較像是在學會把常見形狀變清楚，尤其環形/理想形狀比較強。
- R61 v16 多了 100MG 的真實顯微 crop，並且有 SEM 邊界錨點，所以它不只是把邊緣銳化，而是被拉向較接近真實尺寸的位置。
- R61 v16 同時放入圓柱與圓孔，避免模型只熟一種亮暗極性。
- sequence guard 的資料是為了讓模型不要每張圖各自亂修邊界，對連續位移量測的穩定性比較重要。
- 位移合成資料也很重要，但它不是現場真實影像；簡報若要講真實資料來源，建議主圖用本資料夾的 real crop，位移資料另外用結果曲線說明。
