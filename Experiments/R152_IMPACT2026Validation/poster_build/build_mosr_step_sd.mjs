import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {FileBlob,Presentation,PresentationFile} from '@oai/artifact-tool';
const ROOT=path.resolve(new URL('..',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'));
const BUILD=path.join(ROOT,'poster_build'),OUT=path.join(ROOT,'poster_final');
const SKILL='C:/Users/Rio/.codex/plugins/cache/openai-primary-runtime/presentations/26.915.20218/skills/presentations';
const PYTHON='C:/Users/Rio/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const TEMPLATE='C:/Users/Rio/OneDrive/學業/碩班/論文/投稿/IMPACT2026/4. Poster_Sample_2026 (2).pptx';
process.env.RUNTIME_NODE_MODULES='C:/Users/Rio/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const utils=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const source=await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));const proto=source.toProto();
const keep=new Set(['AutoShape 50','AutoShape 4','AutoShape 13','Text Box 10','Text Box 11','Text Box 14','Text Box 27','Text Box 42','Text Box 43','Text Box 49','圖片 22']);
proto.slides[0].elements=proto.slides[0].elements.filter(e=>keep.has(e.name));const k=32400000/proto.slides[0].widthEmu;
function scale(e){if(e.bbox)for(const key of ['xEmu','yEmu','widthEmu','heightEmu'])if(e.bbox[key]!==undefined)e.bbox[key]=Math.round(e.bbox[key]*k);for(const c of e.children??[])scale(c)}
proto.slides[0].elements.forEach(scale);proto.slides[0].widthEmu=32400000;proto.slides[0].heightEmu=43200000;
const deck=Presentation.load(proto),slide=deck.slides.getItem(0);const names={};
for(const v of (await deck.inspect({kind:'textbox,shape,image',maxChars:18000})).ndjson.trim().split('\n').map(JSON.parse))names[v.name]=v.id;
const P=(x,y,w,h)=>({left:x*k,top:y*k,width:w*k,height:h*k});
function text(name,value,x,y,w,h,pt=31,opt={}){const s=names[name]?deck.resolve(names[name]):slide.shapes.add({geometry:'textbox',name,position:P(x,y,w,h),fill:'none',line:{fill:'none',width:0}});s.position=P(x,y,w,h);s.text=value;s.text.style={typeface:opt.font??'Times New Roman',fontSize:pt*4/3,bold:opt.bold??false,italic:opt.italic??false,color:opt.color??'#111111',alignment:opt.align??'left',verticalAlignment:'top',autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0},lineSpacing:1.02};return s}
function table(values,x,y,w,h,widths,pt=27){const t=slide.tables.add({rows:values.length,columns:values[0].length,left:x*k,top:y*k,width:w*k,height:h*k,columnWidths:widths.map(v=>v*k),values});t.borders.assign({fill:'none',width:0});for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.fill='#FFFFFF';cell.text.style={typeface:'Times New Roman',fontSize:pt*4/3,bold:r===0||values[r][0]==='Mean'||c===3&&values[0][3].includes('MOSR'),color:'#111111',alignment:c===0?'left':'center',verticalAlignment:'middle',wrap:'square',autoFit:'none'}}return t}
async function img(name,p,x,y,w,h){return slide.images.add({blob:new Uint8Array(await fs.readFile(p)),contentType:'image/png',alt:name,position:P(x,y,w,h),fit:'contain'})}
function bar(name,x,y,w){slide.shapes.add({geometry:'line',name,position:P(x,y,w,0),fill:'none',line:{fill:'#FFFFFF',width:6*k}})}
const arr=(await fs.readFile(path.join(ROOT,'results/localization_improvement/improved_summary.csv'),'utf8')).trim().split(/\r?\n/).map(s=>s.split(','));const head=arr.shift();const rows=arr.map(v=>Object.fromEntries(head.map((f,i)=>[f,i<2?v[i]:Number(v[i])])));
const seqs=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um'];const labels=['50× / 0.5','50× / 1.0','20× / 0.5','20× / 1.0'];const methods=['Raw','Wiener','R152'];const publicName=m=>m==='R152'?'MOSR':m;
const values=Object.fromEntries(methods.map(m=>[m,seqs.map(seq=>rows.find(r=>r.scope===seq&&r.method===m).step_sd_nm)]));
const means=Object.fromEntries(methods.map(m=>[m,values[m].reduce((a,b)=>a+b,0)/4]));const gains=values.Raw.map((v,i)=>100*(v-values.R152[i])/v);const totalGain=100*(means.Raw-means.R152)/means.Raw;const code=process.env.IMPACT_PAPER_CODE??'';
text('Text Box 14','Measurement-Oriented Microscopy Reconstruction\nfor Cross-Magnification Micro-Displacement Inspection',120,280,3220,269,80,{font:'Arial',bold:true,align:'center'});
text('authors','Yen Hsuan Chiang, Liang-Chia Chen*',160,580,3130,72,46,{font:'Arial',bold:true,align:'center'});
text('affiliation','Department of Mechanical Engineering, National Taiwan University',160,655,3130,55,34,{font:'Arial',bold:true,align:'center'});
text('contact','No. 1, Sec. 4, Roosevelt Rd., Taipei 10617, Taiwan.  *Correspondence: lchen@ntu.edu.tw',170,721,3110,46,25,{font:'Arial',align:'center'});
text('Text Box 49',code?`Paper Code:\n${code}`:'Paper Code:',3008,197,350,151,28,{font:'Arial',bold:true,align:'center'});
for(const [name,label,x,y,w,pt] of [['Text Box 42','Introduction',120,917,1500,80],['Text Box 10','Methods',120,3161,1500,80],['Text Box 43','Results',1810,919,1510,80],['Text Box 11','Conclusions',1810,3475,1510,76],['Text Box 27','Bibliography',1830,4040,1460,56]])text(name,label,x,y,w,145,pt,{font:'Arial',bold:label!=='Bibliography',align:'center'});

text('intro_body','Optical inspection benefits from reconstruction when clearer boundaries produce more stable position measurements. Changing magnification changes object-space sampling and the pixel phase of the same motion. Single-step displacement dispersion therefore provides a direct test of measurement utility.\n\nMOSR reconstructs each monochrome image on its original pixel grid. One fixed set of learned weights serves 20× and 50× objectives. Raw, fixed Wiener and MOSR use the same image pairs and pillar identities.',125,1090,1480,430,30);
text('raw_label','Raw',165,1558,650,65,38,{font:'Arial',bold:true,align:'center'});text('mosr_label','MOSR',940,1558,650,65,38,{font:'Arial',bold:true,align:'center'});
for(const item of [{prefix:'2_0000',mag:'20×',scale:.1725,top:1660,width:92},{prefix:'0_0000',mag:'50×',scale:.069,top:2390,width:226}]){
 text(`mag-${item.mag}`,item.mag,125,item.top-60,165,60,29,{font:'Arial',bold:true});
 for(const [internal,x] of [['Raw',165],['R152',940]]){await img(`${item.mag} ${publicName(internal)} actual field`,path.join(ROOT,`inspection/images/${item.prefix}_${internal}.png`),x,item.top,650,650);const length=650*(2/item.scale)/item.width;bar(`scale-${item.mag}-${internal}`,x+605-length,item.top+604,length);text(`scale-label-${item.mag}-${internal}`,'2 µm',x+585-length,item.top+545,length+40,45,24,{font:'Arial',align:'center',color:'#FFFFFF'})}
}
text('fig1_caption','Fig. 1. Native-grid Raw and MOSR pillar fields at 20× and 50×. The common display range preserves direct visual comparison. Scale bars: 2 µm.',125,3060,1480,90,25);
text('methods_body','Reconstruction. MOSR combines U-Net context [1], anti-aliasing [2] and bounded PSF-guided correction. Optical inputs comprise 25 measured kernels at 20× and one calibrated kernel at 50×.\n\nLocalization. Coarse contours [3] initialize geometric least-squares circle (LSC) centers [4]. Each pillar uses 720 uniform radial directions, 0.05-pixel profile sampling and three center updates.\n\nDisplacement. Each pair yields nine horizontal pillar-center shifts. Their median, converted to object space and taken in absolute value, defines one single-step displacement. All three image methods use the same procedure.',125,3315,1480,540,29);
text('table1_caption','TABLE I. FIXED ACQUISITION CONDITIONS',130,3875,1470,64,28,{align:'center'});
table([['Objective','Step (µm)','Pairs','µm/pixel'],['50×','0.5','30','0.0690'],['50×','1.0','30','0.0690'],['20×','0.5','30','0.1725'],['20×','1.0','30','0.1725']],130,3960,1470,369,[390,370,300,410],27);
text('statistics_definition','Within each condition, Step SD is the sample standard deviation of its 30 single-step displacements (denominator 29). The reported mean is the arithmetic mean of the four condition-level SDs.',130,4360,1470,104,25);

text('results_intro','Each condition contributes one Step SD from 30 measured single steps. MOSR yields the lowest Step SD in all four conditions, directly linking reconstruction to reduced step-to-step dispersion.',1830,1090,1470,181,32);
text('primary_gain',`${totalGain.toFixed(1)}%`,1845,1320,775,210,118,{font:'Arial',bold:true});
text('primary_values',`${means.Raw.toFixed(2)} nm  Raw\n${means.R152.toFixed(2)} nm  MOSR`,2690,1355,595,147,38,{font:'Times New Roman',bold:true,align:'center'});
text('primary_gain_label','Reduction in the mean Step SD',1845,1535,1450,86,36,{font:'Arial',bold:true});

const chart=slide.charts.add('bar',{
 position:P(1820,1680,1510,737),categories:labels,
 series:methods.map((m,i)=>({name:publicName(m),values:values[m].map(v=>Number(v.toFixed(6))),valuesFormatCode:'0.00',fill:i===0?{type:'solid',color:'#D8D8D8',pattern:{type:'percent5',color:'#111111'}}:i===1?{type:'solid',color:'#AFAFAF',pattern:{type:'upwardDiagonal',color:'#111111'}}:'#181818',line:{fill:'#111111',width:1}})),
 barOptions:{direction:'column',grouping:'clustered',gapWidth:75,overlap:0},hasLegend:true,legend:{position:'top',overlay:false,textStyle:{typeface:'Times New Roman',fontSize:31,fill:'#111111'}},
 xAxis:{visible:true,title:{text:'Objective / nominal step (µm)',textStyle:{typeface:'Times New Roman',fontSize:29,fill:'#111111'}},textStyle:{typeface:'Times New Roman',fontSize:29,fill:'#111111'},line:{fill:'#111111',width:1.2},majorGridlines:null},
 yAxis:{visible:true,min:0,max:16,majorUnit:4,title:{text:'Step SD (nm)',textStyle:{typeface:'Times New Roman',fontSize:31,fill:'#111111'}},numberFormatCode:'0',textStyle:{typeface:'Times New Roman',fontSize:29,fill:'#111111'},line:{fill:'#111111',width:1.2},majorGridlines:{fill:'#D6D6D6',width:.8}},
 dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:'Times New Roman',fontSize:27,fill:'#111111',bold:true}},chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},plotAreaFill:'#FFFFFF',plotAreaLine:{fill:'none',width:0},
});utils.applyPresentationChartFont(chart,{fontFamily:'Times New Roman'});
text('fig2_caption','Fig. 2. Condition-level standard deviation of 30 single-step displacements. All methods use the same locked pairs and circle-center reader.',1830,2450,1470,99,26);
text('result_interpretation',`The reduction relative to Raw spans ${Math.min(...gains).toFixed(1)}–${Math.max(...gains).toFixed(1)}% across the four conditions. The largest reduction occurs at 20× with 0.5 µm steps, where Step SD decreases from ${values.Raw[2].toFixed(2)} to ${values.R152[2].toFixed(2)} nm. MOSR also improves both 50× conditions.`,1830,2590,1470,191,30);
text('table2_caption','TABLE II. STEP SD AND RELATIVE REDUCTION',1830,2810,1470,65,28,{align:'center'});
table([
 ['Condition','Raw\n(nm)','Wiener\n(nm)','MOSR\n(nm)','Reduction\nvs Raw (%)'],
 ...seqs.map((seq,i)=>[labels[i],values.Raw[i].toFixed(2),values.Wiener[i].toFixed(2),values.R152[i].toFixed(2),gains[i].toFixed(1)]),
 ['Mean',means.Raw.toFixed(2),means.Wiener.toFixed(2),means.R152.toFixed(2),totalGain.toFixed(1)],
],1830,2900,1470,488,[430,225,250,225,340],26);
text('table2_note','Mean row: arithmetic mean of the four SDs. Reduction = (Raw − MOSR) / Raw.',1830,3400,1470,61,24);

text('conclusions_body',`MOSR lowers single-step dispersion in every tested condition, with reductions of ${Math.min(...gains).toFixed(1)}–${Math.max(...gains).toFixed(1)}% relative to Raw. The mean condition-level Step SD decreases by ${totalGain.toFixed(1)}%.\n\nOne set of reconstruction weights supports both objectives. Clearer pillar boundaries and lower displacement dispersion establish MOSR as a measurement-oriented reconstruction approach for cross-magnification optical inspection.`,1830,3640,1470,316,30);
text('bibliography_body','[1] O. Ronneberger et al., U-Net, MICCAI, 2015, pp. 234–241.\n[2] R. Zhang, Making convolutional networks shift-invariant again, ICML, 2019, pp. 7324–7334.\n[3] T. F. Chan and L. A. Vese, Active contours without edges, IEEE Trans. Image Process., 10(2), 266–277, 2001.\n[4] N. Chernov and C. Lesort, Least squares fitting of circles, J. Math. Imaging Vis., 23, 239–252, 2005.',1830,4160,1460,282,25);
slide.speakerNotes.textFrame.setText([
 'Public model name: MOSR. Internal provenance maps to the fixed R152 delivery checkpoint in the experiment record.',
 'User selected the original four-condition dataset with 30 single steps per condition; the separate 30-repeat-scan dataset is not part of this poster.',
 'Source summary: '+path.join(ROOT,'results/localization_improvement/improved_summary.csv'),
 'Source pair data: '+path.join(ROOT,'results/localization_improvement/improved_pairs.csv'),
 'Primary quantity: one sample SD (ddof=1) of 30 image-measured single-step displacements per condition. The four SDs are averaged arithmetically. Percentage reduction of the mean uses the ratio of those means.',
 'Images are the first locked 0.5 µm frame at each objective. Common crop and grayscale mapping; exact image paths remain in the source inspection manifest.',
 'Chart style follows the submitted manuscript: Times New Roman chart text, monochrome patterns, explicit native-pixel scales, zero-baseline axes, and manuscript-style captions and table rules.',
 'Template: '+TEMPLATE,
].join('\n'));
const revision=process.env.POSTER_REVISION??'v1';const draft=path.join(BUILD,`mosr_step_sd_${revision}.pptx`);
await (await PresentationFile.exportPptx(deck)).save(draft);
const patch=spawnSync(PYTHON,[path.join(BUILD,'journal_style.py'),draft],{encoding:'utf8'});if(patch.status!==0)throw new Error(patch.stderr);
await fs.writeFile(path.join(BUILD,`mosr_step_sd_layout_${revision}.json`),await (await slide.export({format:'layout'})).text());
const preview=await deck.export({slide,format:'png',scale:.5});await fs.writeFile(path.join(BUILD,`mosr_step_sd_${revision}.png`),new Uint8Array(await preview.arrayBuffer()));
const finalPath=path.join(OUT,`IMPACT2026_MOSR_StepSD_${revision}.pptx`);
await utils.finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath,pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','32400000,43200000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','1'],explicitTotalSlideCount:1,requiredNativeTableOwnerSlides:[1],requiredNativeChartOwnerSlides:[1],materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'portable',fontPolicy:{basis:'reference',families:['Arial','Times New Roman'],referencePath:TEMPLATE,referenceSha256:crypto.createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex')},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`mosr_step_sd_validation_${revision}.json`)});
await fs.writeFile(path.join(BUILD,'mosr_step_sd_design.json'),JSON.stringify({publicName:'MOSR',poster_scope:'original four acquisition conditions',repeated30ScansIncluded:false,primaryStatistic:'sample SD of 30 single-step displacements per condition',models:methods.map(publicName),conditionLabels:labels,sdValues:values,means,reductionsPct:gains,meanSDReductionPct:totalGain,source:path.join(ROOT,'results/localization_improvement/improved_summary.csv'),paperCode:code||null},null,2));
console.log(finalPath);
