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
const TEMPLATE=path.join(ROOT,'sources/impact2026_poster_template.pptx');
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
const data=JSON.parse(await fs.readFile(path.join(ROOT,'results/separate_conditions/poster_data.json'),'utf8'));
if(!data.no_cross_condition_average||data.main_step_um!==1)throw new Error('Wrong presentation scope');
const methods=['Raw','Wiener','MOSR'],s20=data.twenty,s50=data.fifty;
const code=process.env.IMPACT_PAPER_CODE??'';
text('Text Box 14','Measurement-Oriented Microscopy Reconstruction\nfor Cross-Magnification Micro-Displacement Inspection',120,280,3220,269,80,{font:'Arial',bold:true,align:'center'});
text('authors','Yen Hsuan Chiang, Liang-Chia Chen*',160,580,3130,72,46,{font:'Arial',bold:true,align:'center'});
text('affiliation','Department of Mechanical Engineering, National Taiwan University',160,655,3130,55,34,{font:'Arial',bold:true,align:'center'});
text('contact','No. 1, Sec. 4, Roosevelt Rd., Taipei 10617, Taiwan.  *Correspondence: lchen@ntu.edu.tw',170,721,3110,46,25,{font:'Arial',align:'center'});
text('Text Box 49',code?`Paper Code:\n${code}`:'Paper Code:',3008,197,350,151,28,{font:'Arial',bold:true,align:'center'});
for(const [name,label,x,y,w,pt] of [['Text Box 42','Introduction',120,917,1500,80],['Text Box 10','Methods',120,3161,1500,80],['Text Box 43','Results',1810,919,1510,80],['Text Box 11','Conclusions',1810,3580,1510,76],['Text Box 27','Bibliography',1830,4050,1460,56]])text(name,label,x,y,w,145,pt,{font:'Arial',bold:label!=='Bibliography',align:'center'});
text('intro_body','Microscopy reconstruction supports optical inspection when clearer boundaries also produce more stable position measurements. Objective changes alter object-space sampling, optical blur and the pixel phase of motion. The variation of measured single steps provides a direct test of reconstruction for displacement inspection.\n\nMOSR reconstructs each monochrome image on its native pixel grid. One fixed set of learned weights serves 20× and 50× objectives. This study examines each objective at a common nominal step of 1 µm, with Raw, fixed Wiener and MOSR sharing the same image pairs and circle-center calculation.',125,1090,1480,455,30);
text('raw_label','Raw',165,1558,650,65,38,{font:'Arial',bold:true,align:'center'});
text('mosr_label','MOSR',940,1558,650,65,38,{font:'Arial',bold:true,align:'center'});
for(const [key,label,top] of [['20x','20×',1660],['50x','50×',2390]]){
 text(`mag-${key}`,label,125,top-60,165,60,29,{font:'Arial',bold:true});
 for(const [m,x] of [['Raw',165],['MOSR',940]]){
  const asset=data.images[`${key}_${m}`];
  await img(`${label}, 1 micrometer, ${m}, actual acquisition field`,asset.path,x,top,650,650);
  const length=650*(2/asset.scale_um_per_px)/asset.width_px;
  bar(`scale-${key}-${m}`,x+605-length,top+604,length);
  text(`scale-label-${key}-${m}`,'2 µm',x+585-length,top+545,length+40,45,24,{font:'Arial',align:'center',color:'#FFFFFF'});
 }
}
text('fig1_caption','Fig. 1. Raw and MOSR images from the 20× and 50×, 1 µm datasets. Each comparison uses the same field and grayscale range. Scale bars: 2 µm.',125,3060,1480,90,25);
text('methods_body','Reconstruction. MOSR combines U-Net context [1], anti-aliasing [2] and bounded PSF guidance. The optical inputs comprise 25 measured kernels at 20× and one calibrated kernel at 50×. Fixed Wiener uses a regularization value of 0.0565.\n\nLocalization. Coarse contours [3] initialize maximum-gradient boundary points. Geometric least-squares circle fitting [4] uses 64 points at 20× and 96 at 50×. Gradient peaks provide subpixel boundary positions.\n\nDisplacement. The median of nine pillar-center changes defines each step along the acquisition motion direction. The 20× dataset contains 30 complete scans of 30 steps. The 50× dataset contains 30 locked adjacent-frame pairs.',125,3315,1480,540,28);
text('table1_caption','TABLE I. SEPARATE ACQUISITION CONDITIONS',130,3875,1470,64,28,{align:'center'});
table([['Objective','Step (µm)','Measured steps','µm/pixel'],['20×','1.0','30 scans × 30','0.1725'],['50×','1.0','30 pairs','0.0690']],130,3960,1470,240,[300,310,510,350],27);
text('statistics_definition','Each scan or locked set yields the sample SD of 30 steps (denominator 29). At 20×, all 30 scan SDs are shown; the within-scan summary is the square root of their mean squared SD. The 50× result is reported separately. Both use image-measured displacement.',130,4250,1470,200,26);

text('results_intro','At a common 1 µm step, MOSR lowers displacement variation at both objectives. Results are calculated within each acquisition condition.',1830,1090,1470,140,31);
text('20x_heading','20×, 1 µm: 30 repeated scans',1840,1250,1460,85,38,{font:'Arial',bold:true});
text('20x_gain',`${s20.relative_reduction_pct.toFixed(1)}%`,1845,1360,775,165,92,{font:'Arial',bold:true});
text('20x_values',`${s20.pooled_within_scan_sd_nm.Raw.toFixed(3)} nm  Raw\n${s20.pooled_within_scan_sd_nm.MOSR.toFixed(3)} nm  MOSR`,2650,1380,640,115,34,{bold:true,align:'center'});
text('20x_gain_label','Reduction in pooled within-scan Step SD',1845,1515,1450,70,31,{font:'Arial',bold:true});
const font=(size,bold=false)=>({typeface:'Times New Roman',fontSize:size,fill:'#111111',bold});
const baseChart={hasLegend:true,legend:{position:'top',overlay:false,textStyle:font(29)},chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},plotAreaFill:'#FFFFFF',plotAreaLine:{fill:'none',width:0}};
const axis=(title,size=28)=>({visible:true,title:{text:title,textStyle:font(size)},textStyle:font(size),line:{fill:'#111111',width:1.2},majorGridlines:null});
const line=slide.charts.add('line',{
 ...baseChart,position:P(1820,1610,1510,600),categories:Array.from({length:30},(_,i)=>String(i+1)),
 series:methods.map((m,i)=>({name:m,values:s20.scan_sd_nm[m].map(v=>Number(v.toFixed(6))),valuesFormatCode:'0.000',fill:['#888888','#555555','#111111'][i],line:{fill:['#999999','#555555','#111111'][i],width:i===2?3.5:2.4,style:i===1?'dashed':'solid'},marker:{symbol:['triangle','square','circle'][i],size:i===2?6:5}})),
 lineOptions:{grouping:'standard',smooth:false},xAxis:axis('Scan number',25),
 yAxis:{...axis('Step SD (nm)',28),min:0,max:16,majorUnit:4,numberFormatCode:'0',majorGridlines:{fill:'#D6D6D6',width:.8}},dataLabels:{showValue:false},
});utils.applyPresentationChartFont(line,{fontFamily:'Times New Roman'});
text('fig2_caption','Fig. 2. Each point is the SD of 30 measured steps in one 20× scan. The 30 scans retain their individual results for all three methods.',1830,2230,1470,110,25);
text('20x_interpretation',`MOSR reduces Step SD in all 30 scans, with per-scan reductions of ${s20.per_scan_reduction_min_pct.toFixed(1)}–${s20.per_scan_reduction_max_pct.toFixed(1)}% relative to Raw. The within-scan summary is ${s20.pooled_within_scan_sd_nm.Wiener.toFixed(3)} nm for fixed Wiener and ${s20.pooled_within_scan_sd_nm.MOSR.toFixed(3)} nm for MOSR.`,1830,2370,1470,150,29);

text('50x_heading','50×, 1 µm: 30 locked pairs',1840,2550,1460,85,38,{font:'Arial',bold:true});
text('50x_gain',`${s50.relative_reduction_pct.toFixed(1)}%`,1845,2650,775,160,92,{font:'Arial',bold:true});
text('50x_values',`${s50.step_sd_nm.Raw.toFixed(3)} nm  Raw\n${s50.step_sd_nm.MOSR.toFixed(3)} nm  MOSR`,2650,2670,640,115,34,{bold:true,align:'center'});
text('50x_gain_label','Reduction in Step SD',1845,2800,1450,65,31,{font:'Arial',bold:true});
const bars=slide.charts.add('bar',{
 ...baseChart,position:P(1820,2880,1510,475),categories:['50×, 1 µm'],
 series:methods.map((m,i)=>({name:m,values:[Number(s50.step_sd_nm[m].toFixed(6))],valuesFormatCode:'0.000',fill:i===0?{type:'solid',color:'#D8D8D8',pattern:{type:'percent5',color:'#111111'}}:i===1?{type:'solid',color:'#AFAFAF',pattern:{type:'upwardDiagonal',color:'#111111'}}:'#181818',line:{fill:'#111111',width:1}})),
 barOptions:{direction:'column',grouping:'clustered',gapWidth:200,overlap:0},xAxis:{visible:false,majorGridlines:null},
 yAxis:{...axis('Step SD (nm)',28),min:0,max:8,majorUnit:2,numberFormatCode:'0',majorGridlines:{fill:'#D6D6D6',width:.8}},
 dataLabels:{showValue:true,position:'outEnd',textStyle:font(28,true)},
});utils.applyPresentationChartFont(bars,{fontFamily:'Times New Roman'});
text('fig3_caption','Fig. 3. SD of the 30 locked 1 µm displacements at 50×. The same calibrated optical input supports Wiener and MOSR; the circle-center calculation is shared by all methods.',1830,3385,1470,139,25);
text('conclusions_body',`At 20×, MOSR lowers pooled within-scan step variation by ${s20.relative_reduction_pct.toFixed(1)}% and improves all 30 repeated scans. At 50×, Step SD falls by ${s50.relative_reduction_pct.toFixed(1)}% for the fixed 1 µm condition.\n\nOne reconstruction model supports both objectives with calibrated optical inputs. Clearer boundaries and lower displacement variation support cross-magnification optical inspection.`,1830,3750,1470,263,29);
text('bibliography_body','[1] O. Ronneberger et al., U-Net, MICCAI, 2015, pp. 234–241.\n[2] R. Zhang, Making convolutional networks shift-invariant again, ICML, 2019, pp. 7324–7334.\n[3] T. F. Chan and L. A. Vese, Active contours without edges, IEEE Trans. Image Process., 10(2), 266–277, 2001.\n[4] N. Chernov and C. Lesort, Least squares fitting of circles, J. Math. Imaging Vis., 23, 239–252, 2005.',1830,4170,1460,282,25);
slide.speakerNotes.textFrame.setText([
 'Public model: MOSR. Source model identity: unchanged delivered R152 checkpoint.',
 'Data: '+path.join(ROOT,'results/separate_conditions/poster_data.json'),
 '20x: September 3 thesis cohort, 30 complete scans, 30 observed adjacent steps each. The line chart shows each scan SD. Summary is pooled within-scan SD, sqrt(mean(scan SD squared)); scans contain equal counts. This is not an average across acquisition conditions.',
 '50x: July 2 original 1 micrometer cohort, 30 Raw-locked adjacent pairs. The bar chart is one sample SD per method from those 30 steps.',
 'These are separate acquisition cohorts, not a matched causal isolation of magnification. All three methods share identical inputs and the same native normal-gradient geometric LSC reader within each condition.',
 'The 0.5 micrometer 50x condition is retained in the complete audit and supplementary results; the submitted manuscript is unchanged.',
 'All measured source numbers, reconstruction checks and citations are in the independent experiment workspace. The submitted manuscript supplies references [1]-[4].',
].join('\n'));
const revision=process.env.POSTER_REVISION??'v1';const draft=path.join(BUILD,`mosr_separate_${revision}.pptx`);
await (await PresentationFile.exportPptx(deck)).save(draft);
const patch=spawnSync(PYTHON,[path.join(BUILD,'journal_style.py'),draft],{encoding:'utf8'});if(patch.status!==0)throw new Error(patch.stderr);
const finalPath=path.join(OUT,`IMPACT2026_MOSR_1um_Separate_${revision}.pptx`);
await utils.finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath,pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','32400000,43200000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','1'],explicitTotalSlideCount:1,requiredNativeTableOwnerSlides:[1],requiredNativeChartOwnerSlides:[1],materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'portable',fontPolicy:{basis:'reference',families:['Arial','Times New Roman'],referencePath:TEMPLATE,referenceSha256:crypto.createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex')},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`mosr_separate_validation_${revision}.json`)});
console.log(finalPath);
