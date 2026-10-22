import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const starterPptxPath = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_table_only_20260728/template-starter.pptx";
const outputPptxPath = "C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_附講稿_v17效能表格修正.pptx";
const inspectPath = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/oral_defense_table_only_20260728/final-inspect.ndjson";

function parseNdjson(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPptxPath));
const before = await presentation.inspect({ kind: "table,notes", maxChars: 300000 });
const records = parseNdjson(before.ndjson);
const tableRecord = records.find((record) => record.kind === "table" && record.slide === 59 && record.name === "表格 1");
if (!tableRecord) throw new Error("Could not resolve the slide 59 performance table.");

const table = presentation.resolve(tableRecord.id);
const values = [
  ["Model", "Parameters (M)", "Median Latency (ms)", "P95 Latency (ms)", "Throughput (MP/s)"],
  ["NAFNet", "4.182", "152.7", "155.3", "20.60"],
  ["EDSR-x1", "4.071", "915.6", "920.4", "3.44"],
  ["MOSR", "4.024", "400.2", "406.8", "7.86"],
];
for (let row = 0; row < values.length; row += 1) {
  for (let column = 0; column < values[row].length; column += 1) {
    table.cells.set(row, column, values[row][column]);
  }
}

for (let row = 1; row <= 3; row += 1) {
  for (let column = 1; column <= 4; column += 1) {
    const text = table.getCell(row, column).text;
    text.color = "#000000";
    text.bold = false;
  }
}
for (const [row, column] of [[1, 2], [1, 3], [1, 4], [3, 1]]) {
  const text = table.getCell(row, column).text;
  text.color = "#4EA72E";
  text.bold = true;
}
for (const [row, column] of [[2, 1], [3, 2], [3, 3], [3, 4]]) {
  const text = table.getCell(row, column).text;
  text.color = "#0F9ED5";
  text.bold = true;
}

const after = await presentation.inspect({ kind: "slide,textbox,table,notes", maxChars: 300000 });
await fs.writeFile(inspectPath, after.ndjson, "utf8");
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(outputPptxPath);
console.log(outputPptxPath);
