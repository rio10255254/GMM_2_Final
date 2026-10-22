import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const assetRoot = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_english_20260727";
const root = process.env.ORAL_TMP_ROOT ?? assetRoot;
const starterPptxPath = path.join(root, "template-starter.pptx");
const outputPptxPath = process.env.ORAL_OUTPUT_PPTX ?? "C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_英文圖表版_v17效能修正.pptx";
const qaDir = path.join(root, "artifact-final-targets");
await fs.mkdir(qaDir, { recursive: true });

const assets = {
  early: path.join(assetRoot, "assets_english", "early"),
  wiener: path.join(assetRoot, "assets_english", "wiener", "figures"),
  v19: path.join(assetRoot, "assets_english", "v19", "01_displacement_improvement"),
  custom: path.join(assetRoot, "assets_english", "custom"),
};

const replacementPlan = [
  { slide: 26, x: 554.94, y: 341.36, file: path.join(assets.early, "fig6-04_zh.png"), alt: "50x fitted point-spread function" },
  { slide: 26, x: 880.20, y: 343.59, file: path.join(assets.early, "fig6-05_zh.png"), alt: "20x fitted point-spread function" },

  { slide: 28, x: 88.00, y: 177.50, file: path.join(assets.early, "fig6-02_zh.png"), alt: "20x Raw image spatial spectrum" },
  { slide: 28, x: 66.86, y: 444.91, file: path.join(assets.early, "fig6-18_zh.png"), alt: "20x Wiener-deconvolved image spatial spectrum" },
  { slide: 28, x: 623.37, y: 177.50, file: path.join(assets.early, "fig6-01_zh.png"), alt: "50x Raw image spatial spectrum" },
  { slide: 28, x: 647.95, y: 455.75, file: path.join(assets.early, "fig6-19_zh.png"), alt: "50x Wiener-deconvolved image spatial spectrum" },

  { slide: 29, x: 855.33, y: 6.97, file: path.join(assets.early, "fig6-06_zh.png"), alt: "Pillar CD boundary-detection diagram" },
  { slide: 29, x: 829.42, y: 372.38, file: path.join(assets.early, "fig6-06_zh.png"), alt: "Pillar radial profile and 10-90 percent edge-width diagram" },

  { slide: 30, x: 75.54, y: 177.50, file: path.join(assets.early, "fig6-11_zh.png"), alt: "20x Raw and Wiener radial edge profiles" },
  { slide: 30, x: 75.54, y: 441.60, file: path.join(assets.early, "fig6-12_zh.png"), alt: "50x Raw and Wiener radial edge profiles" },

  { slide: 32, x: 64.30, y: 233.07, file: path.join(assets.early, "fig6-21_zh.png"), alt: "50x full-field test-target locator" },
  { slide: 32, x: 664.55, y: 233.07, file: path.join(assets.early, "fig6-22_zh.png"), alt: "20x full-field test-target locator" },

  { slide: 34, x: 562.10, y: 177.50, file: path.join(assets.wiener, "03_50x_pillar_edge_profile.png"), alt: "50x Raw, Wiener, and MOSR radial edge profiles" },
  { slide: 36, x: 562.10, y: 177.50, file: path.join(assets.wiener, "06_20x_pillar_edge_profile.png"), alt: "20x Raw, Wiener, and MOSR radial edge profiles" },
  { slide: 37, x: 534.12, y: 204.91, file: path.join(assets.custom, "720_equal_angle_sampling_P29_english.png"), alt: "720-direction angular-averaged radial CD sampling" },
  { slide: 39, x: 640.00, y: 28.80, file: path.join(assets.wiener, "07_center9_cd_per_pillar.png"), alt: "Per-pillar CD bounds across thresholds" },
  { slide: 40, x: 160.67, y: 415.16, file: path.join(assets.wiener, "09a_cd_threshold_sensitivity_horizontal.png"), alt: "Seven-row horizontal-profile CD threshold sensitivity" },
  { slide: 40, x: 702.00, y: 415.06, file: path.join(assets.wiener, "09b_cd_threshold_sensitivity_radial.png"), alt: "Angular-averaged radial-profile CD threshold sensitivity" },
  { slide: 41, x: 424.67, y: 415.16, file: path.join(assets.custom, "20x_cd_median_absolute_error_english.png"), alt: "20x median absolute CD error by reconstruction method" },

  { slide: 45, x: 656.77, y: 197.97, file: path.join(assets.v19, "01_50x_x_0p5um_step_trace.png"), alt: "50x 0.5 micrometer stepwise displacement trace" },
  { slide: 45, x: 48.00, y: 197.97, file: path.join(assets.v19, "02_50x_x_1um_step_trace.png"), alt: "50x 1.0 micrometer stepwise displacement trace" },
  { slide: 47, x: 656.77, y: 197.97, file: path.join(assets.v19, "03_20x_0p5um_step_trace.png"), alt: "20x 0.5 micrometer stepwise displacement trace" },
  { slide: 47, x: 48.00, y: 197.97, file: path.join(assets.v19, "04_20x_1um_step_trace.png"), alt: "20x 1.0 micrometer stepwise displacement trace" },
  { slide: 49, x: 766.67, y: 73.73, file: path.join(assets.v19, "06_sequence_step_sd.png"), alt: "Step-to-step displacement standard deviation across four conditions" },
  { slide: 51, x: 52.02, y: 177.50, file: path.join(assets.custom, "raw_anchor_visual_comparison_english.png"), alt: "Raw, full-model, and no-anchor reconstruction comparison" },
];

async function readArrayBuffer(filePath) {
  const bytes = await fs.readFile(filePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function parseNdjson(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

function nearestImage(records, slideNumber, x, y) {
  const candidates = records.filter((record) => record.kind === "image" && record.slide === slideNumber);
  if (!candidates.length) throw new Error(`No images found on slide ${slideNumber}`);
  return candidates
    .map((record) => ({
      record,
      distance: Math.hypot((record.bbox?.[0] ?? 0) - x, (record.bbox?.[1] ?? 0) - y),
    }))
    .sort((a, b) => a.distance - b.distance)[0];
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPptxPath));
const before = await presentation.inspect({
  kind: "slide,textbox,shape,image,table,notes",
  maxChars: 180000,
});
const records = parseNdjson(before.ndjson);
const usedIds = new Set();

for (const item of replacementPlan) {
  const match = nearestImage(records, item.slide, item.x, item.y);
  if (match.distance > 3) {
    throw new Error(`Image match on slide ${item.slide} is too far from target (${match.distance.toFixed(2)} px).`);
  }
  if (usedIds.has(match.record.id)) throw new Error(`Image ${match.record.id} was selected more than once.`);
  usedIds.add(match.record.id);

  const image = presentation.resolve(match.record.id);
  const oldFrame = image.frame;
  const oldCrop = image.crop;
  const oldFit = image.fit;
  const oldPrompt = image.prompt;
  const oldGeometry = image.geometry;
  const oldBorderRadius = image.borderRadius;
  const oldRotation = image.rotation;
  const oldFlipHorizontal = image.flipHorizontal;
  const oldFlipVertical = image.flipVertical;
  const oldLockAspectRatio = image.lockAspectRatio;

  image.replace({
    blob: await readArrayBuffer(item.file),
    contentType: "image/png",
    alt: item.alt,
    ...(oldFit ? { fit: oldFit } : {}),
    ...(oldPrompt ? { prompt: oldPrompt } : {}),
  });
  image.frame = oldFrame;
  image.crop = oldCrop;
  image.geometry = oldGeometry;
  image.borderRadius = oldBorderRadius;
  image.rotation = oldRotation;
  image.flipHorizontal = oldFlipHorizontal;
  image.flipVertical = oldFlipVertical;
  image.lockAspectRatio = oldLockAspectRatio;
}

const performanceTableRecord = records.find(
  (record) => record.kind === "table" && record.slide === 59 && record.name === "表格 1",
);
if (!performanceTableRecord) throw new Error("Could not resolve the slide 59 performance table.");
const performanceTable = presentation.resolve(performanceTableRecord.id);
const performanceValues = [
  ["Model", "Parameters (M)", "Median Latency (ms)", "P95 Latency (ms)", "Throughput (MP/s)"],
  ["NAFNet", "4.182", "152.7", "155.3", "20.60"],
  ["EDSR-x1", "4.071", "915.6", "920.4", "3.44"],
  ["MOSR", "4.024", "400.2", "406.8", "7.86"],
];
for (let row = 0; row < performanceValues.length; row += 1) {
  for (let column = 0; column < performanceValues[row].length; column += 1) {
    performanceTable.cells.set(row, column, performanceValues[row][column]);
  }
}

for (let row = 1; row <= 3; row += 1) {
  for (let column = 1; column <= 4; column += 1) {
    const text = performanceTable.getCell(row, column).text;
    text.color = "#000000";
    text.bold = false;
  }
}
for (const [row, column] of [[1, 2], [1, 3], [1, 4], [3, 1]]) {
  const text = performanceTable.getCell(row, column).text;
  text.color = "#4EA72E";
  text.bold = true;
}
for (const [row, column] of [[2, 1], [3, 2], [3, 3], [3, 4]]) {
  const text = performanceTable.getCell(row, column).text;
  text.color = "#0F9ED5";
  text.bold = true;
}

const performanceSubtitleRecord = records.find(
  (record) => record.kind === "textbox" && record.slide === 59 && record.name === "文字方塊 5",
);
if (!performanceSubtitleRecord) throw new Error("Could not resolve the slide 59 protocol label.");
const performanceSubtitle = presentation.resolve(performanceSubtitleRecord.id);
performanceSubtitle.text.replace(
  "20× Pillar, 1.0 µm",
  "2048×1536 · RTX A6000 · Direct AMP",
);
performanceSubtitle.frame = { ...performanceSubtitle.frame, width: 500 };

const performanceSummaryRecord = records.find(
  (record) => record.kind === "textbox" && record.slide === 59 && record.name === "文字方塊 3",
);
if (!performanceSummaryRecord) throw new Error("Could not resolve the slide 59 performance summary.");
presentation.resolve(performanceSummaryRecord.id).text.replace(
  "Compared with EDSR-x1, MOSR achieved 1.58× faster inference on a 256×256 input and 9.27× higher full-frame processing speed, while using slightly fewer model parameters.",
  "Under the same direct full-frame protocol, NAFNet was fastest (152.7 ms). MOSR required 400.2 ms (7.86 MP/s; 2.50 fps), 56.3% faster than EDSR-x1 while retaining the strongest measurement performance.",
);

const obsoleteAuthorNoteRecords = records.filter(
  (record) => record.kind === "textbox" && record.textPreview === "需補進論文",
);
if (obsoleteAuthorNoteRecords.length !== 7) {
  throw new Error(`Expected 7 obsolete authoring reminders, found ${obsoleteAuthorNoteRecords.length}.`);
}
for (const record of obsoleteAuthorNoteRecords) presentation.resolve(record.id).delete();

const conclusionPerformanceRecord = records.find(
  (record) => record.kind === "textbox" && record.slide === 60 && record.name === "文字方塊 12",
);
if (!conclusionPerformanceRecord) throw new Error("Could not resolve the slide 60 performance conclusion.");
presentation.resolve(conclusionPerformanceRecord.id).text.replace("0.408 s", "0.400 s");

const performanceNotesRecord = records.find(
  (record) => record.kind === "notes" && record.slide === 59,
);
if (performanceNotesRecord) {
  const notes = presentation.resolve(performanceNotesRecord.id);
  notes.setText([
    notes.text.trim(),
    "[Sources]",
    "- Thesis v17, Table 6-17: direct 2048×1536 full-frame comparison on RTX A6000; 2 warm-up and 6 timed runs.",
    "- evaluation/runtime_fair_modes/fair_runtime_modes.csv and benchmark_runtime_fair_modes.py.",
    "[/Sources]",
  ].filter(Boolean).join("\n"));
}

const conclusionNotesRecord = records.find(
  (record) => record.kind === "notes" && record.slide === 60,
);
if (conclusionNotesRecord) {
  const notes = presentation.resolve(conclusionNotesRecord.id);
  notes.setText([
    notes.text.trim(),
    "[Sources]",
    "- Thesis v17, Table 6-17: MOSR direct full-frame median latency = 400.2 ms.",
    "[/Sources]",
  ].filter(Boolean).join("\n"));
}

const slide63Record = records.find((record) => record.kind === "textbox" && record.slide === 63 && record.name === "文字方塊 2");
if (!slide63Record) throw new Error("Could not resolve the slide 63 derivation text box.");
const derivation = presentation.resolve(slide63Record.id);
const derivationFrame = derivation.frame;
derivation.delete();
const slide63SlideRecord = records.find((record) => record.kind === "slide" && record.slide === 63);
const slide63 = presentation.resolve(slide63SlideRecord.id);
slide63.images.add({
  blob: await readArrayBuffer(path.join(assets.custom, "mad_derivation_english.png")),
  contentType: "image/png",
  alt: "English derivation of the normal-distribution MAD scaling factor 1.4826",
  fit: "contain",
  position: derivationFrame,
});

const targetSlides = [...new Set(replacementPlan.map((item) => item.slide).concat([59, 60, 63]))];
for (const slideNumber of targetSlides) {
  const slideRecord = records.find((record) => record.kind === "slide" && record.slide === slideNumber);
  const slide = presentation.resolve(slideRecord.id);
  const png = await slide.export({ format: "png", scale: 1.5 });
  await writeBlob(path.join(qaDir, `final-slide-${String(slideNumber).padStart(2, "0")}.png`), png);
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(qaDir, `final-slide-${String(slideNumber).padStart(2, "0")}.layout.json`), await layout.text());
}

const after = await presentation.inspect({
  kind: "slide,textbox,shape,image,table,notes",
  maxChars: 180000,
});
await fs.writeFile(path.join(root, "final-inspect.ndjson"), after.ndjson);

const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(outputPptxPath);
await fs.writeFile(path.join(root, "authoring-log.json"), JSON.stringify({
  starterPptxPath,
  outputPptxPath,
  replacedImages: replacementPlan.length,
  translatedSlide: 63,
  targetSlides,
}, null, 2));
console.log(outputPptxPath);
