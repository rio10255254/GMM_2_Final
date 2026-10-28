import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {FileBlob,Presentation,PresentationFile} from '@oai/artifact-tool';

const ROOT=path.resolve(new URL('..',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
const BUILD=path.join(ROOT,'poster_build');
const SKILL='C:/Users/Rio/.codex/plugins/cache/openai-primary-runtime/presentations/26.915.20218/skills/presentations';
const PYTHON='C:/Users/Rio/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const TEMPLATE='C:/Users/Rio/OneDrive/學業/碩班/論文/投稿/IMPACT2026/4. Poster_Sample_2026 (2).pptx';
const OUT=path.join(ROOT,'poster_final');
process.env.RUNTIME_NODE_MODULES='C:/Users/Rio/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
await fs.mkdir(OUT,{recursive:true});
const utils=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const source=await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));
const proto=source.toProto();
const keep=new Set(['AutoShape 50','AutoShape 4','AutoShape 13','Text Box 10','Text Box 11','Text Box 14','Text Box 27','Text Box 42','Text Box 43','Text Box 49','圖片 22']);
proto.slides[0].elements=proto.slides[0].elements.filter(e=>keep.has(e.name));
// The supplied file uses 36x48 inches but visibly specifies 90x120 cm. Preserve its 3:4 geometry at the stated print size.
const factor=32400000/proto.slides[0].widthEmu;
function scaleBox(e){if(e.bbox)for(const k of ['xEmu','yEmu','widthEmu','heightEmu'])if(e.bbox[k]!==undefined)e.bbox[k]=Math.round(e.bbox[k]*factor);for(const ch of e.children??[])scaleBox(ch)}
for(const e of proto.slides[0].elements)scaleBox(e);
proto.slides[0].widthEmu=32400000;proto.slides[0].heightEmu=43200000;
const deck=Presentation.load(proto);const slide=deck.slides.getItem(0);
const textNames={};
const inspected=(await deck.inspect({kind:'textbox,shape,image',maxChars:18000})).ndjson.trim().split('\n').map(x=>JSON.parse(x));
for(const e of inspected)textNames[e.name]=e.id;
const P=(x,y,w,h)=>({left:x*factor,top:y*factor,width:w*factor,height:h*factor});
const C={ink:'#111111',navy:'#003064',blue:'#36618A',raw:'#A8ADB3',wiener:'#7896B5',r152:'#003064',light:'#E8EFF8',line:'#B8C7D5'};
function text(name,value,x,y,w,h,pt=32,{font='Times New Roman',bold=false,color=C.ink,align='left',italic=false}={}){
 let s=textNames[name]?deck.resolve(textNames[name]):slide.shapes.add({geometry:'textbox',name,position:P(x,y,w,h),fill:'none',line:{fill:'none',width:0}});
 s.position=P(x,y,w,h);s.text=value;s.text.style={typeface:font,fontSize:pt*4/3,bold,italic,color,alignment:align,verticalAlignment:'top',autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0},lineSpacing:1.03};return s;
}
function line(name,x,y,w,color='#FFFFFF',thickness=5){return slide.shapes.add({geometry:'line',name,position:P(x,y,w,0),fill:'none',line:{fill:color,width:thickness*factor}})}
async function image(name,file,x,y,w,h){return slide.images.add({blob:new Uint8Array(await fs.readFile(file)),contentType:'image/png',alt:name,position:P(x,y,w,h),fit:'contain'});}
function table(name,values,x,y,w,h,widths,pt=28){
 const t=slide.tables.add({rows:values.length,columns:values[0].length,left:x*factor,top:y*factor,width:w*factor,height:h*factor,columnWidths:widths.map(v=>v*factor),values});
 t.borders.assign({fill:C.line,width:1.2,style:'solid'});
 for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
  const cell=t.getCell(r,c);cell.fill=r===0?C.light:'#FFFFFF';cell.text.style={typeface:'Times New Roman',fontSize:pt*4/3,bold:r===0||values[r][0]==='R152',color:values[r][0]==='R152'?C.navy:C.ink,alignment:c===0?'left':'center',verticalAlignment:'middle',autoFit:'none',wrap:'square'};
 }
 return t;
}
const csv=(await fs.readFile(path.join(ROOT,'results/localization_improvement/improved_summary.csv'),'utf8')).trim().split(/\r?\n/).map(l=>l.split(','));const header=csv.shift();const data=csv.map(v=>Object.fromEntries(header.map((k,i)=>[k,i<2?v[i]:Number(v[i])])));
const aggregate=Object.fromEntries(data.filter(r=>r.scope==='all120').map(r=>[r.method,r]));
const m20=data.find(r=>r.scope==='20x'&&r.method==='R152');const m50=data.find(r=>r.scope==='50x'&&r.method==='R152');
const reduction=(key,base='Raw')=>100*(aggregate[base][key]-aggregate.R152[key])/aggregate[base][key];
const code=process.env.IMPACT_PAPER_CODE??'';

// Header and all section anchors preserve the supplied two-column composition.
text('Text Box 14','Measurement-Oriented Microscopy Reconstruction\nfor Cross-Magnification Micro-Displacement Inspection',120,280,3220,269,80,{font:'Arial',bold:true,align:'center'});
text('authors','Yen Hsuan Chiang, Liang-Chia Chen*',160,580,3130,72,46,{font:'Arial',bold:true,align:'center'});
text('affiliation','Department of Mechanical Engineering, National Taiwan University',160,655,3130,55,34,{font:'Arial',bold:true,align:'center'});
text('contact','No. 1, Sec. 4, Roosevelt Rd., Taipei 10617, Taiwan.  *Correspondence: lchen@ntu.edu.tw',170,721,3110,46,25,{font:'Arial',align:'center'});
text('Text Box 49',code?`Paper Code:\n${code}`:'Paper Code:',3008,197,350,151,28,{font:'Arial',bold:true,align:'center'});
for(const [name,label,x,y,w] of [['Text Box 42','Introduction',120,917,1500],['Text Box 10','Methods',120,3161,1500],['Text Box 43','Results',1810,919,1510],['Text Box 11','Conclusions',1810,2970,1510],['Text Box 27','Bibliography',1830,3880,1460]]){
 text(name,label,x,y,w,label==='Bibliography'?114:148,label==='Bibliography'?65:86,{font:'Arial',bold:label!=='Bibliography',align:'center'});
}

text('intro_body','Reliable optical inspection requires clear boundaries and stable feature positions. R152 reconstructs microscopy images on the original pixel grid and connects them to one geometric measurement pipeline.\n\nOne fixed set of learned weights processes 20× and 50× images with objective-specific optical information. Bounded correction sharpens pillar boundaries on the native grid.',125,1090,1480,350,32);
text('fig1_label','Figure #1',500,1457,720,100,54,{font:'Arial',bold:true,italic:true,align:'center'});
text('raw_label','Raw',165,1558,650,65,40,{font:'Arial',bold:true,align:'center'});
text('r152_label','R152',940,1558,650,65,40,{font:'Arial',bold:true,color:C.navy,align:'center'});
const ims=[{prefix:'2_0000',mag:'20×',scale:.1725,top:1660,width:92,height:91},{prefix:'0_0000',mag:'50×',scale:.069,top:2390,width:226,height:226}];
for(const item of ims){
 text(`mag-${item.mag}`,item.mag,125,item.top-60,165,60,30,{font:'Arial',bold:true});
 for(const [method,x] of [['Raw',165],['R152',940]]){
  const file=path.join(ROOT,`inspection/images/${item.prefix}_${method}.png`);await image(`${item.mag} ${method} first locked frame`,file,x,item.top,650,650);
  const bw=650*(2/item.scale)/item.width;line(`scale-${item.mag}-${method}`,x+650-45-bw,item.top+604,bw,'#FFFFFF',7);
  text(`scale-label-${item.mag}-${method}`,'2 µm',x+650-65-bw,item.top+545,bw+40,45,24,{font:'Arial',color:'#FFFFFF',align:'center'});
 }
}
text('fig1_caption','Representative pillar fields at 20× and 50×. R152 yields clearer boundaries on the native pixel grid. Scale bars: 2 µm.',125,3060,1480,90,26);

text('methods_body','R152 combines U-Net context [1], anti-aliasing [2] and bounded PSF correction. It uses 25 kernels at 20× and one calibrated 50× kernel.\n\nCoarse contours [3] initialize geometric LSC [4]. Each pillar uses 720 radial directions and three center refinements. The absolute median horizontal shift of nine pillars defines each step.',125,3350,1480,316,30);
text('experiment_table_label','Table #1. Locked acquisition conditions',130,3690,1470,64,30,{bold:true});
table('conditions',[
 ['Objective','Step (µm)','Pairs','µm/pixel'],
 ['50×','0.5','30','0.0690'],['50×','1.0','30','0.0690'],['20×','0.5','30','0.1725'],['20×','1.0','30','0.1725'],
],130,3770,1470,424,[400,360,300,410],29);
text('metric_definitions','Step SD: mean of four condition-level standard deviations.\nNominal MAE: mean absolute difference from the set step.\nWithin-grid SD: median of 120 nine-pillar standard deviations.',130,4250,1460,185,25);

text('result_hero',`${reduction('median_within_grid_sd_nm').toFixed(1)}%`,1845,1085,850,253,146,{font:'Arial',bold:true,color:C.navy});
text('result_scope','120 paired steps\n20× and 50×',2750,1140,525,171,40,{font:'Arial',bold:true,align:'center'});
text('result_hero_label','Lower median within-grid SD versus Raw',1845,1360,1450,90,38,{font:'Arial',bold:true});
text('results_table_label','Table #2. Aggregate displacement results (nm)',1830,1483,1460,65,30,{bold:true});
table('aggregate',[
 ['Method','Step SD','Nominal MAE','Median\nwithin-grid SD'],
 ...['Raw','Wiener','R152'].map(m=>[m,aggregate[m].step_sd_nm.toFixed(2),aggregate[m].nominal_mae_nm.toFixed(2),aggregate[m].median_within_grid_sd_nm.toFixed(2)]),
],1830,1568,1470,402,[310,340,380,440],28);
text('fig2_label','Figure #2',2180,2010,770,111,60,{font:'Arial',bold:true,italic:true,align:'center'});
const chart=slide.charts.add('bar',{
 position:P(1818,2140,1510,650),categories:['Step SD','Nominal MAE','Within-grid SD'],
 series:['Raw','Wiener','R152'].map(m=>({name:m,values:[aggregate[m].step_sd_nm,aggregate[m].nominal_mae_nm,aggregate[m].median_within_grid_sd_nm].map(v=>Number(v.toFixed(6))),valuesFormatCode:'0.00',fill:m==='Raw'?C.raw:m==='Wiener'?C.wiener:C.r152,line:{fill:'none',width:0}})),
 barOptions:{direction:'column',grouping:'clustered',gapWidth:90,overlap:0},
 hasLegend:true,legend:{position:'top',overlay:false,textStyle:{typeface:'Arial',fontSize:31,fill:C.ink}},
 xAxis:{visible:true,textStyle:{typeface:'Arial',fontSize:32,fill:C.ink},line:{fill:C.ink,width:1.5},majorGridlines:null},
 yAxis:{visible:true,min:0,max:12,majorUnit:2,title:{text:'nm',textStyle:{typeface:'Arial',fontSize:32,fill:C.ink}},numberFormatCode:'0',textStyle:{typeface:'Arial',fontSize:29,fill:C.ink},line:{fill:C.ink,width:1.5},majorGridlines:{fill:'#D8E0E7',width:1}},
 dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:'Arial',fontSize:29,fill:C.ink,bold:true}},
 chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},plotAreaFill:'#FFFFFF',plotAreaLine:{fill:'none',width:0},
});
utils.applyPresentationChartFont(chart,{fontFamily:'Arial'});
text('fig2_caption','R152 achieves the lowest measured values for all three criteria across the four imaging conditions.',1830,2840,1480,105,28);

text('conclusions_body',`R152 reduces median within-grid variation from ${aggregate.Raw.median_within_grid_sd_nm.toFixed(2)} nm to ${aggregate.R152.median_within_grid_sd_nm.toFixed(2)} nm, a ${reduction('median_within_grid_sd_nm').toFixed(1)}% reduction relative to Raw.\n\nStep SD and nominal MAE decrease by ${reduction('step_sd_nm').toFixed(1)}% and ${reduction('nominal_mae_nm').toFixed(1)}%, respectively. The same learned weights deliver the lowest measured values in every tested condition.\n\nStep variation reaches ${(m20.step_sd_nm/172.5).toFixed(3)} pixel at 20× and ${(m50.step_sd_nm/69).toFixed(3)} pixel at 50×. R152 combines clear pillar boundaries with stronger positional consistency across both objectives.`,1830,3160,1470,639,32);
text('bibliography_body','[1] O. Ronneberger et al., U-Net, MICCAI, 2015, pp. 234–241.\n[2] R. Zhang, Making convolutional networks shift-invariant again, ICML, 2019, pp. 7324–7334.\n[3] T. F. Chan and L. A. Vese, Active contours without edges, IEEE Trans. Image Process., 10(2), 266–277, 2001.\n[4] N. Chernov and C. Lesort, Least squares fitting of circles, J. Math. Imaging Vis., 23, 239–252, 2005.',1830,4008,1460,402,28);
slide.speakerNotes.textFrame.setText([
 'Template: '+TEMPLATE,
 'Title, authors and affiliation: submitted two-page IMPACT manuscript in sources/submitted_paper.pdf.',
 'Numerical source: '+path.join(ROOT,'results/localization_improvement/improved_summary.csv'),
 'Pair-level source: '+path.join(ROOT,'results/localization_improvement/improved_pairs.csv'),
 'Images: inspection/images/2_0000_Raw.png, 2_0000_R152.png, 0_0000_Raw.png, 0_0000_R152.png. These are the first locked 0.5 µm frames at each objective with common 0–1 display mapping.',
 'Current poster readout: radial 720-direction geometric LSC with three refinement passes. The model and raw data are fixed.',
 'R152 learned checkpoint SHA-256: 17bf7c63f070520a5ef8d4428010340686f465bf1fa03ef8225c0a2eadad4a61.',
 '50x optics: original calibrated single PSF, installed through the optional input adapter. 20x optics: native R152 25-kernel bank.',
 'Percent reductions use unrounded aggregate values. All four condition-level values support the stated lowest-value comparison among Raw, Wiener and R152.',
 'Bibliography metadata follows references [3], [4], [6], [8] of the supplied manuscript.',
].join('\n'));
const revision=process.env.POSTER_REVISION??'v1';
const draft=path.join(BUILD,`candidate_${revision}.pptx`);
await (await PresentationFile.exportPptx(deck)).save(draft);
const axisPatch=spawnSync(PYTHON,[path.join(BUILD,'fix_chart_axis.py'),draft],{encoding:'utf8'});
if(axisPatch.status!==0)throw new Error(axisPatch.stderr||'Chart axis formatting failed');
await fs.writeFile(path.join(BUILD,`poster_${revision}.json`),JSON.stringify(deck.toProto()));
const layout=await slide.export({format:'layout'});await fs.writeFile(path.join(BUILD,`layout_${revision}.json`),await layout.text());
try{const png=await deck.export({slide,format:'png',scale:.5});await fs.writeFile(path.join(BUILD,`preview_${revision}.png`),new Uint8Array(await png.arrayBuffer()));}catch(e){console.log('Artifact preview:',e.message)}
await fs.writeFile(path.join(BUILD,'design_receipt.json'),JSON.stringify({source:TEMPLATE,sourceSizeCm:[91.44,121.92],printedTemplateRequirementCm:[90,120],finalSizeEmu:[32400000,43200000],preserved:['two columns','rounded template panels','gradient header and background','IMPACT logo','five section headings','Arial / Times New Roman typography'],paperCode:code||null,dataSource:'results/localization_improvement/improved_summary.csv',rawR152ReductionsPct:{stepSD:reduction('step_sd_nm'),nominalMAE:reduction('nominal_mae_nm'),withinGrid:reduction('median_within_grid_sd_nm')}},null,2));
const finalPath=path.join(OUT,`IMPACT2026_R152_Poster_${revision}.pptx`);
await utils.finalizePresentation({
 workspaceDir:ROOT,candidatePath:draft,finalPath,pythonExecutable:PYTHON,
 integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','32400000,43200000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','1'],
 explicitTotalSlideCount:1,requiredNativeTableOwnerSlides:[1],requiredNativeChartOwnerSlides:[1],
 materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'portable',
 fontPolicy:{basis:'reference',families:['Arial','Times New Roman'],referencePath:TEMPLATE,referenceSha256:crypto.createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`validation_${revision}.json`),
});
console.log('FINAL',finalPath);
