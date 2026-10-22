import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const presentation = await PresentationFile.importPptx(await FileBlob.load("C:/Users/Rio/OneDrive/學業/碩班/論文/可用/江彥諠_口試簡報_附講稿.pptx"));
for (const search of ["exportPptx preserve imported original package", "importPptx round trip preserve formatting", "pptx export options"]) {
  const result = presentation.help("*", { search, include: ["index", "notes", "examples"], maxChars: 12000 });
  console.log(`SEARCH: ${search}\n${result.ndjson ?? result}\n`);
}
