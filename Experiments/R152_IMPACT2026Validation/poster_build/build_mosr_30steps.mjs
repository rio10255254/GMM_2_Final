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
const data=JSON.parse(await fs.readFile(path.join(ROOT,'results/separate_conditions/poster_data_30steps.json'),'utf8'));
if(!data.no_cross_condition_average||data.main_step_um!==1)throw new Error('Wrong presentation scope');
const methods=['Raw','Wiener','MOSR'],s20=data.twenty,s50=data.fifty;
const code=process.env.IMPACT_PAPER_CODE??'';
text('Text Box 14','Measurement-Oriented Microscopy Reconstruction\nfor Cross-Magnification Micro-Displacement Inspection',120,280,3220,269,80,{font:'Arial',bold:true,align:'center'});
text('authors','Yen Hsuan Chiang, Liang-Chia Chen*',160,580,3130,72,46,{font:'Arial',bold:true,align:'center'});
text('affiliation','Department of Mechanical Engineering, National Taiwan University',160,655,3130,55,34,{font:'Arial',bold:true,align:'center'});
text('contact','No. 1, Sec. 4, Roosevelt Rd., Taipei 10617, Taiwan.  *Correspondence: lchen@ntu.edu.tw',170,721,3110,46,25,{font:'Arial',align:'center'});
text('Text Box 49',code?`Paper Code:\n${code}`:'Paper Code:',3008,197,350,151,28,{font:'Arial',bold:true,align:'center'});
for(const [name,label,x,y,w,pt] of [['Text Box 42','Introduction',120,917,1500,80],['Text Box 10','Methods',120,3100,1500,80],['Text Box 43','Results',1810,919,1510,80],['Text Box 11','Conclusions',1810,3580,1510,76],['Text Box 27','Bibliography',1830,4050,1460,56]])text(name,label,x,y,w,145,pt,{font:'Arial',bold:label!=='Bibliography',align:'center'});
text('intro_body','Optical inspection estimates motion from image features. A sharper reconstructed edge is useful when its measured position remains stable. Optical blur, pixel sampling and reconstruction-induced boundary shifts can all change the reported displacement, especially when an inspection workflow switches objectives.\n\nMOSR combines U-Net context [1], calibrated optical guidance and anti-aliased processing [2] to address these effects. Bounded correction retains the original image grid and limits geometry changes while improving boundary visibility. One fixed set of learned weights serves both objectives.\n\nAt a common nominal step of 1 µm, this study compares Raw, fixed Wiener and MOSR at 20× and 50×. Each condition contributes 30 measured single steps. The central outcome is the variation of these steps, linking reconstruction quality directly to displacement measurement.',125,1090,1480,640,29);
text('raw_label','Raw',202,1750,530,65,38,{font:'Arial',bold:true,align:'center'});
text('mosr_label','MOSR',992,1750,530,65,38,{font:'Arial',bold:true,align:'center'});
for(const [key,label,top] of [['20x','20×',1840],['50x','50×',2450]]){
 text(`mag-${key}`,label,125,top-55,165,55,29,{font:'Arial',bold:true});
 for(const [m,x] of [['Raw',202],['MOSR',992]]){
  const asset=data.images[`${key}_${m}`];
  await img(`${label}, 1 micrometer, ${m}, measured acquisition field`,asset.path,x,top,530,530);
  const length=530*(2/asset.scale_um_per_px)/asset.width_px;
  bar(`scale-${key}-${m}`,x+494-length,top+493,length);
  text(`scale-label-${key}-${m}`,'2 µm',x+474-length,top+439,length+40,45,24,{font:'Arial',align:'center',color:'#FFFFFF'});
 }
}
text('fig1_caption','Fig. 1. Raw and MOSR images from the measured 20× and 50×, 1 µm datasets. Paired images use identical fields and grayscale ranges. Scale bars: 2 µm.',125,2995,1480,95,25);
text('methods_body','Data and reconstruction. At 20×, 31 frames form 30 consecutive steps; 50× uses the original 30 locked adjacent pairs. Both conditions employ a 1 µm nominal step. MOSR uses fixed weights and native-grid outputs, with 25 measured PSF kernels at 20× and one calibrated kernel at 50×. Fixed Wiener uses a regularization value of 0.0565.\n\nBoundary and center. A coarse active contour [3] initializes each pillar boundary. Intensity profiles normal to the contour use 0.1-pixel spacing. Quadratic refinement locates each gradient maximum between samples. Geometric least-squares circle fitting [4] uses 64 refined points at 20× and 96 at 50× to estimate the center.\n\nDisplacement and statistics. Coordinate-wise medians of nine pillar-center changes define the array shift. Its component along the acquisition motion direction gives the measured step. Object-space conversion uses the scale in Table I. Each condition yields one sample SD from its 30 steps. Raw, Wiener and MOSR share the same images, features and center-calculation settings.',125,3260,1480,735,27);
text('table1_caption','TABLE I. SEPARATE ACQUISITION CONDITIONS',130,4035,1470,64,27,{align:'center'});
table([['Objective','Step (µm)','Measured steps','µm/pixel'],['20×','1.0','30','0.1725'],['50×','1.0','30','0.0690']],130,4110,1470,185,[300,310,510,350],25);
text('statistics_definition','Step SD uses all 30 displacements with denominator 29. Reduction (%) = 100 × (1 − SD(MOSR) / SD(Raw)). Each trace plots measured step minus the nominal 1 µm; each objective is summarized separately.',130,4330,1470,125,25);

text('results_intro','At a common 1 µm step, MOSR lowers displacement variation at both objectives. Results are calculated within each acquisition condition.',1830,1090,1470,140,31);
text('20x_heading','20×, 1 µm: 30 single steps',1840,1250,1460,85,38,{font:'Arial',bold:true});
text('20x_gain',`${s20.relative_reduction_pct.toFixed(1)}%`,1845,1360,775,165,92,{font:'Arial',bold:true});
text('20x_values',`${s20.step_sd_nm.Raw.toFixed(3)} nm  Raw\n${s20.step_sd_nm.MOSR.toFixed(3)} nm  MOSR`,2650,1380,640,115,34,{bold:true,align:'center'});
text('20x_gain_label','Reduction in Step SD',1845,1515,1450,70,31,{font:'Arial',bold:true});
const font=(size,bold=false)=>({typeface:'Times New Roman',fontSize:size,fill:'#111111',bold});
const baseChart={hasLegend:true,legend:{position:'top',overlay:false,textStyle:font(29)},chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},plotAreaFill:'#FFFFFF',plotAreaLine:{fill:'none',width:0}};
const axis=(title,size=28)=>({visible:true,title:{text:title,textStyle:font(size)},textStyle:font(size),line:{fill:'#111111',width:1.2},majorGridlines:null});
const line=slide.charts.add('line',{
 ...baseChart,position:P(1820,1610,1510,600),categories:Array.from({length:30},(_,i)=>String(i+1)),
 series:methods.map((m,i)=>({name:m,values:s20.steps_nm[m].map(v=>Number((v-1000).toFixed(6))),valuesFormatCode:'0.000',fill:['#888888','#555555','#111111'][i],line:{fill:['#999999','#555555','#111111'][i],width:i===2?3.5:2.4,style:i===1?'dashed':'solid'},marker:{symbol:['triangle','square','circle'][i],size:i===2?6:5}})),
 lineOptions:{grouping:'standard',smooth:false},xAxis:axis('Step number',25),
 yAxis:{...axis('Measured step − 1 µm (nm)',28),min:data.common_curve_axis_nm[0],max:data.common_curve_axis_nm[1],majorUnit:10,numberFormatCode:'0',majorGridlines:{fill:'#D6D6D6',width:.8}},dataLabels:{showValue:false},
});utils.applyPresentationChartFont(line,{fontFamily:'Times New Roman'});
text('fig2_caption','Fig. 2. Thirty single-step displacements at 20×. The traces show measured step minus 1 µm, using the same axes and units as the 50× experiment.',1830,2230,1470,110,25);
text('20x_interpretation',`At 20×, Step SD decreases from ${s20.step_sd_nm.Raw.toFixed(3)} nm for Raw to ${s20.step_sd_nm.Wiener.toFixed(3)} nm for fixed Wiener and ${s20.step_sd_nm.MOSR.toFixed(3)} nm for MOSR. MOSR reduces the variation by ${s20.relative_reduction_pct.toFixed(1)}% relative to Raw.`,1830,2370,1470,150,29);

text('50x_heading','50×, 1 µm: 30 single steps',1840,2550,1460,85,38,{font:'Arial',bold:true});
text('50x_gain',`${s50.relative_reduction_pct.toFixed(1)}%`,1845,2650,775,160,92,{font:'Arial',bold:true});
text('50x_values',`${s50.step_sd_nm.Raw.toFixed(3)} nm  Raw\n${s50.step_sd_nm.MOSR.toFixed(3)} nm  MOSR`,2650,2670,640,115,34,{bold:true,align:'center'});
text('50x_gain_label','Reduction in Step SD',1845,2800,1450,65,31,{font:'Arial',bold:true});
const curve50=slide.charts.add('line',{
 ...baseChart,position:P(1820,2880,1510,510),categories:Array.from({length:30},(_,i)=>String(i+1)),
 series:methods.map((m,i)=>({name:m,values:s50.steps_nm[m].map(v=>Number((v-1000).toFixed(6))),valuesFormatCode:'0.000',fill:['#888888','#555555','#111111'][i],line:{fill:['#999999','#555555','#111111'][i],width:i===2?3.5:2.4,style:i===1?'dashed':'solid'},marker:{symbol:['triangle','square','circle'][i],size:i===2?6:5}})),
 lineOptions:{grouping:'standard',smooth:false},xAxis:axis('Pair number',25),
 yAxis:{...axis('Measured step − 1 µm (nm)',28),min:data.common_curve_axis_nm[0],max:data.common_curve_axis_nm[1],majorUnit:10,numberFormatCode:'0',majorGridlines:{fill:'#D6D6D6',width:.8}},dataLabels:{showValue:false},
});utils.applyPresentationChartFont(curve50,{fontFamily:'Times New Roman'});
text('fig3_caption',`Fig. 3. Thirty locked single-step displacements at 50×. Step SD is ${s50.step_sd_nm.Raw.toFixed(3)} nm for Raw, ${s50.step_sd_nm.Wiener.toFixed(3)} nm for fixed Wiener and ${s50.step_sd_nm.MOSR.toFixed(3)} nm for MOSR.`,1830,3410,1470,115,25);
text('conclusions_body',`MOSR reduces the SD of 30 measured single steps by ${s20.relative_reduction_pct.toFixed(1)}% at 20× and ${s50.relative_reduction_pct.toFixed(1)}% at 50×, at a common nominal step of 1 µm. Each result retains its own acquisition condition.\n\nOne reconstruction model supports both objectives with calibrated optical inputs. Clearer boundaries and lower step variation support cross-magnification optical inspection.`,1830,3750,1470,263,29);
text('bibliography_body','[1] O. Ronneberger et al., U-Net, MICCAI, 2015, pp. 234–241.\n[2] R. Zhang, Making convolutional networks shift-invariant again, ICML, 2019, pp. 7324–7334.\n[3] T. F. Chan and L. A. Vese, Active contours without edges, IEEE Trans. Image Process., 10(2), 266–277, 2001.\n[4] N. Chernov and C. Lesort, Least squares fitting of circles, J. Math. Imaging Vis., 23, 239–252, 2005.',1830,4170,1460,282,25);
slide.speakerNotes.textFrame.setText([
 'Public model: MOSR. Source model identity: unchanged delivered R152 checkpoint.',
 'Data: '+path.join(ROOT,'results/separate_conditions/poster_data_30steps.json'),
 '20x: September 3 thesis run 003412_XY_0, acquisition run 7, the first evaluation run after the existing first-six-RAW-scan direction calibration split. Use all 31 frames and all 30 adjacent steps. This presentation selection follows the user request after full 30-scan auditing and is not a preregistered original-study choice.',
 '50x: July 2 original 1 micrometer cohort, all 30 original Raw-locked adjacent pairs, ordered by acquisition index. They are selected pairs rather than a new 31-frame scan.',
 'Each headline is 100*(1-SD(MOSR)/SD(Raw)), using sample SD of exactly 30 image-measured steps in that condition. There is no pooled scan statistic and no cross-objective average on this poster.',
 'Curve values are observed image-measured displacements minus nominal 1000 nm, with identical axes in both plots. No per-method recentering, detrending, scaling, clipping or outlier removal is applied.',
 'The complete 30-scan 20x study and 0.5 micrometer 50x result remain in the supplementary records. The submitted two-page manuscript is unchanged.',
 'Both methods use the same normal-gradient geometric LSC family with the same settings within each condition. The submitted manuscript supplies references [1]-[4].',
].join('\n'));
const revision=process.env.POSTER_REVISION??'v1';const draft=path.join(BUILD,`mosr_30steps_${revision}.pptx`);
await (await PresentationFile.exportPptx(deck)).save(draft);
const patch=spawnSync(PYTHON,[path.join(BUILD,'journal_style.py'),draft],{encoding:'utf8'});if(patch.status!==0)throw new Error(patch.stderr);
const finalPath=path.join(OUT,`IMPACT2026_MOSR_1um_30Steps_${revision}.pptx`);
await utils.finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath,pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','32400000,43200000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','1'],explicitTotalSlideCount:1,requiredNativeTableOwnerSlides:[1],requiredNativeChartOwnerSlides:[1],materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'portable',fontPolicy:{basis:'reference',families:['Arial','Times New Roman'],referencePath:TEMPLATE,referenceSha256:crypto.createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex')},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`mosr_30steps_validation_${revision}.json`)});
console.log(finalPath);
