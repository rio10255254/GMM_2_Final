# 早期輪次：原命令、候選與結果如何串回

2026-10-22。早期資料按日期及程序名稱保存，不代表某日期只有一輪。本次再讀31份完整autotune JSON的profile、候選與23份原日誌，將R2至R10串回；R10實際包含在R9的四步排程內。[逐次原報告](EARLY_REPORTS.md)／[完整原綁定](EARLY_ROUND_BINDINGS.json)／[逐號對照](ROUND_NUMBER_MAP.md)。

這些原件已在既有正式附件，本次只提出小檔方便直接閱讀。內部分數、零值及NaN保留原值，不能當外部GMF或物理精度；新整理沒有重跑訓練或重算原測量。

## R1

0307 Round1與修復round1b，將選模改成直接重視8px步長、極端值與平均偏移，新增stage15／16稀疏曲邊。保留Windows長路徑、選模視窗與日誌不同步的失敗。後來stdguard_v2作內部種子，不能直接當作當時外部正式採用版。

[原進度與四候選](../../../Traing_Progress/organized_20260307/selected/reports/AUTO_TUNE_ROUND1_20260307.md)／[後來整理](../../../Traing_Progress/organized_20260307/ROUND1_CLEANUP_REPORT_20260309.md)。進度的執行中是當日截面。更早0306自動調參另屬前置基礎。

## R2

03-09 10:51的原meta記錄AutoTuneTrain、sweep6、final14、deterministic；stdout保留seed1261200、8px目標、0307 stdguard起點、四候選及最後JSON。不能因報告沒有profile欄而漏記，輪次由原日誌檔名及產物明確綁定。

[原命令](early_sources/R2/auto_tune_console_20260309_105107_round2.meta.txt)／[原stdout](early_sources/R2/auto_tune_console_20260309_105107_round2.out.log)／[完整原候選及選擇](early_sources/reports/auto_tune_report_20260309_105119.json)。原內部step_std零值不能當成外部定位完美。

## R3

原JSON雖沒有R3檔名，profile明記round3_gmf_guard與round3_sharp_balance。03-09 11:59／12:48各為sweep6、final12，14:44／15:19各為sweep6、final10，四份均保留status及best／final。前者提高GMF保護，後者兼顧銳利度；原候選多由同一0307 stdguard起步，不因編號較後就認作繼承R2末檔。

[11:59 guard](early_sources/reports/auto_tune_report_20260309_115909.json)／[12:48 sharp](early_sources/reports/auto_tune_report_20260309_124822.json)／[14:44 guard](early_sources/reports/auto_tune_report_20260309_144411.json)／[15:19 sharp](early_sources/reports/auto_tune_report_20260309_151919.json)。PSF校正另有自己的Round3，不能拿來補這個編號。

## R4

round4_refine_seed降低更新強度並延後光學啟動，原命令sweep6／final10、seed1261200，保留實際資料stage、best及final。它是同一既有種子的保守精修，沒有外部通過宣稱。

[原命令](early_sources/R4/auto_tune_console_20260309_134614_round4_refine.meta.txt)／[完整原報告](early_sources/reports/auto_tune_report_20260309_134617.json)。

## R5

round5_extval_preserve與round5_extval_data_probe的原報告分開：前者降低更新及邊緣變動，希望保留既有外部行為，後者另探資料。profile名稱含extval，不代表本次已取得新的外部GMF驗收。

[原命令](early_sources/R5/auto_tune_console_20260309_173246_round5_extval_preserve.meta.txt)／[保守版完整原報告](early_sources/reports/auto_tune_report_20260309_173251.json)；資料探測另列[31份逐次對照](EARLY_REPORTS.md)。

## R6

Round6包含subpixel_guard與microstep_probe的多次不同尺度。正常完成仍常出現final破壞sweep，當時沒有全域新贏家取代0307種子。分開保存各尺度、重啟與較長／較短final，不把最後run當採用。

[原長跑分析與完整分數](../../../Traing_Progress/organized_20260309/selected/reports/ROUND6_LONGRUN_ANALYSIS_20260310.md)／[所有原profile表](EARLY_REPORTS.md)。

## R7

先重建uint16 microstep與序列資料，再做round7_sequence_microstep_probe，原目標0.08px、sweep4；日誌明記選seq_defect_balance。保留空啟動、資料重建與原四候選設定。內部零步長波動同時伴隨0.08步長誤差，不可解讀為實際量測零誤差。

[原重建記錄](early_sources/R7/round7_rebuild_seq_20260310_153223.out.log)／[完整原報告](early_sources/reports/auto_tune_report_20260310_154418.json)。

## R8

round8_sequence_refine擴大缺陷與序列stage，原目標仍0.08px、sweep4，保留seq_refine_defect_mid及原結果。日誌出現best_epoch=0，不能只憑內部最高分宣稱新訓練改善；final_epochs設定也不證明final實際執行。

[原stdout](early_sources/R8/round8_seq_refine_20260310_162457.out.log)／[完整原報告](early_sources/reports/auto_tune_report_20260310_162500.json)。

## R9

原狀態JSON的last_report為空，單看它只知道四步完成；本次從三份longrun stdout找回實際命令和每步報告。18:29是未完整走完的嘗試，18:34完整四步使用val_batch，21:17重啟的完整四步改用seq_val。兩種評估來源、候選與分數不可混排；從負分變正分不能當模型物理精度因此提升。

[較早完整val_batch日誌](early_sources/R9/longrun_round9_20260310_183443.out.log)／[較晚完整seq_val日誌](early_sources/R9/longrun_round9_20260310_211726.out.log)／[原狀態](early_sources/R9/000_LONGRUN_ROUND9_STATUS.json)。31份原JSON保留每一步對應，不再只用排程狀態代替研究結果。

## R10

R10就是R9 longrun第二與第三步，profile為round10_crossscale_seqval，分別針對0.8及8px。較晚版本使用seq_val、0.8做sweep4、8做sweep5，均skip-final；兩個都選crossscale_curve_general，但分數與尺度不同。較早val_batch兩份也保留，不能合併成同一驗證。

[較晚0.8px原JSON](early_sources/reports/auto_tune_report_20260310_212245.json)／[較晚8px原JSON](early_sources/reports/auto_tune_report_20260310_212722.json)／[所在原排程](early_sources/R9/longrun_round9_20260310_211726.out.log)。

## R11

round11_annulus_gmf_align再用整環定位與缺陷保護，三次原profile亦保留。外部GMF原摘要如下；同時期內部選擇值不能與外部標準差混稱。

| 名義步長 | 原平均步長 px | 原步長標準差 px |
|---|---:|---:|
| 8px | 8.022656565656566 | 0.8297884431836471 |
| 0.8px | 0.8008474576271186 | 0.23451290778086278 |
| 0.08px | 0.08430769230769258 | 0.22446745794461337 |

[三尺度完整原摘要](early_sources/R11/reports/round11_annulus_lock_defect_posy_step_summary.md)與原回傳照原值保存，本次不改過濾或重跑定位。

## R12至R15

[完整選擇讀法](../legacy_multiscale/README.md)分清方法組初排、固定模型再審、早晚試跑及同分。R12方法組由三份模型構成，R13再審單份模型，R14初排第一與最後採用不同，R15同分沿原排序。九項早期R13總分的舊公式仍缺；既有207分數及五次選擇的重算保留原日期與範圍。

## R16至R32與不帶R號的支線

[原操作及來源](../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md)與[逐號表](ROUND_NUMBER_MAP.md)保留各輪。R16／17／18逐步針對位置和步長；R19／20的錨點與程序探測未解除問題；Branch E與成對／公式試探導向R21／22估計器。R23／24是診斷負結果，R25至29形成從零與步長權重的外部比較鏈，R30成為前任基準，R31超參數及R32 real-EQ未晉級。

估計器或推論策略改動不是另一次網路訓練，當時selected亦不代表目前正式。各輪原設定、原模型、完整回傳與不利尺度均保存。

## 尚未能綁回的編號

本次已從原內容而非檔名串回R2至R10；主專案獨立R36仍未辨認；另已從Lab R61原紀錄找到內部r36，見[兩種R36](R36_IDENTITIES_20261022.md)，不能以同號代替。列為未綁定的編號位置，不宣稱從未做過，也不補造一輪。

2026-10-22續查已補回22份較早原版與早期R13原公式，9項總分重算相同，見[最新找回與界線](../KNOWN_GAPS.md)。原JSON有配方、候選與輸出，不自動保證當年每次動態程式版本都已恢復；保存與閱讀完整度不能直接換成全部歷史精確重現。

[R36可到達歷史補查](R36_HISTORY_CHECK.json)另檢查當次243個版本記錄，沒有R36訊息或實驗檔案路徑；仍不據此斷言未記錄、未匯入或不可到達的歷史從未存在。
