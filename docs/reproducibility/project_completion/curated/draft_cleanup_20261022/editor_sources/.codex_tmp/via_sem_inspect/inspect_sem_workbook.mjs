import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "D:/GMM_2_Final/Thesis_MOSR_Evidence/20260618_100MG/SEM_data/via_pilar.xlsx";
const outputDir = "D:/GMM_2_Final/PSF_Fitting/.codex_tmp/via_sem_inspect/rendered";

await fs.mkdir(outputDir, { recursive: true });
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const summary = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 12000,
  tableMaxRows: 30,
  tableMaxCols: 20,
  tableMaxCellChars: 100,
});
console.log("WORKBOOK_SUMMARY");
console.log(summary.ndjson);

const sheets = workbook.worksheets.items;
for (const sheet of sheets) {
  const used = sheet.getUsedRange(true);
  const address = used ? used.address : "A1";
  const region = await workbook.inspect({
    kind: "region,formula,computedStyle",
    sheetId: sheet.name,
    range: address,
    maxChars: 18000,
    tableMaxRows: 100,
    tableMaxCols: 30,
    tableMaxCellChars: 120,
    options: { maxResults: 500 },
  });
  console.log(`SHEET_REGION ${sheet.name} ${address}`);
  console.log(region.ndjson);

  const preview = await workbook.render({
    sheetName: sheet.name,
    autoCrop: "all",
    scale: 1.5,
    format: "png",
  });
  const safeName = sheet.name.replace(/[\\/:*?"<>|]/g, "_");
  await fs.writeFile(
    path.join(outputDir, `${safeName}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}
