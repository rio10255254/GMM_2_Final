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
const TEMPLATE=path.join(ROOT,'sources/poster_TW0243_before_redesign.pptx');
process.env.RUNTIME_NODE_MODULES='C:/Users/Rio/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const utils=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const source=await PresentationFile.importPptx(await FileBlob.load(TEMPLATE));const proto=source.toProto();
const keep=new Set(['AutoShape 50','AutoShape 4','AutoShape 13','Text Box 10','Text Box 11','Text Box 14','Text Box 27','Text Box 42','Text Box 43','Text Box 49','圖片 22']);
proto.slides[0].elements=proto.slides[0].elements.filter(e=>keep.has(e.name)||(e.bbox?.xEmu>28000000&&e.bbox?.yEmu<3000000));const sourceScale=32400000/proto.slides[0].widthEmu;const k=32400000/32918400;
function scale(e){if(e.bbox)for(const key of ['xEmu','yEmu','widthEmu','heightEmu'])if(e.bbox[key]!==undefined)e.bbox[key]=Math.round(e.bbox[key]*sourceScale);for(const c of e.children??[])scale(c)}
proto.slides[0].elements.forEach(scale);proto.slides[0].widthEmu=32400000;proto.slides[0].heightEmu=43200000;
const deck=Presentation.load(proto),slide=deck.slides.getItem(0);const names={};
for(const v of (await deck.inspect({kind:'textbox,shape,image',maxChars:18000})).ndjson.trim().split('\n').map(JSON.parse))names[v.name]=v.id;
const P=(x,y,w,h)=>({left:x*k,top:y*k,width:w*k,height:h*k});
function text(name,value,x,y,w,h,pt=31,opt={}){const s=names[name]?deck.resolve(names[name]):slide.shapes.add({geometry:'textbox',name,position:P(x,y,w,h),fill:'none',line:{fill:'none',width:0}});s.position=P(x,y,w,h);s.text=value;s.text.style={typeface:opt.font??'Times New Roman',fontSize:pt*4/3,bold:opt.bold??false,italic:opt.italic??false,color:opt.color??'#111111',alignment:opt.align??'left',verticalAlignment:'top',autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0},lineSpacing:1.02};return s}
function table(values,x,y,w,h,widths,pt=27){const t=slide.tables.add({rows:values.length,columns:values[0].length,left:x*k,top:y*k,width:w*k,height:h*k,columnWidths:widths.map(v=>v*k),values});t.borders.assign({fill:'none',width:0});for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.fill='#FFFFFF';cell.text.style={typeface:'Times New Roman',fontSize:pt*4/3,bold:r===0||values[r][0]==='Mean'||c===3&&values[0][3].includes('MOSR'),color:'#111111',alignment:c===0?'left':'center',verticalAlignment:'middle',wrap:'square',autoFit:'none'}}return t}
async function img(name,p,x,y,w,h){return slide.images.add({blob:new Uint8Array(await fs.readFile(p)),contentType:'image/png',alt:name,position:P(x,y,w,h),fit:'contain'})}
function bar(name,x,y,w){slide.shapes.add({geometry:'line',name,position:P(x,y,w,0),fill:'none',line:{fill:'#FFFFFF',width:6*k}})}
const data=JSON.parse(await fs.readFile(path.join(ROOT,'results/separate_conditions/poster_data_30steps.json'),'utf8'));
const boundary=JSON.parse(await fs.readFile(path.join(BUILD,'design_assets/measured_boundary.json'),'utf8'));
const methods=['Raw','Wiener','MOSR'];
const mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
const s20=data.twenty,s50=data.fifty;
if(!data.no_cross_condition_average||data.main_step_um!==1)throw new Error('Wrong experiment scope');

function node(name,label,x,y,w,h,pt=25,bold=false){
 const s=slide.shapes.add({geometry:'rect',name,position:P(x,y,w,h),fill:bold?'#F1F1F1':'#FFFFFF',line:{fill:'#222222',width:1.9*k}});
 s.text=label;s.text.style={typeface:'Times New Roman',fontSize:pt*4/3,bold,color:'#111111',alignment:'center',verticalAlignment:'middle',autoFit:'none',wrap:'square',insets:{left:8,right:8,top:8,bottom:8},lineSpacing:1.0};return s;
}
function anchor(name,x,y){return slide.shapes.add({geometry:'rect',name,position:P(x-.5,y-.5,1,1),fill:'none',line:{fill:'none',width:0}})}
function connect(a,b,from='right',to='left',kind='straight',arrow=true,dashed=false){
 return slide.shapes.connect(a,b,{kind,fromSide:from,toSide:to,line:{fill:'#333333',width:2.2*k,style:dashed?'dashed':'solid'},tail:arrow?{type:'arrow',width:'med',length:'med'}:{type:'none'}});
}
function dot(name,x,y,r,color){return slide.shapes.add({geometry:'ellipse',name,position:P(x-r,y-r,2*r,2*r),fill:color,line:{fill:'none',width:0}})}

text('Text Box 14','Measurement-Oriented Microscopy Reconstruction\nfor Cross-Magnification Micro-Displacement Inspection',120,280,3220,269,80,{font:'Arial',bold:true,align:'center'});
text('authors','Yen Hsuan Chiang, Liang-Chia Chen*',160,580,3130,72,46,{font:'Arial',bold:true,align:'center'});
text('affiliation','Department of Mechanical Engineering, National Taiwan University',160,655,3130,55,34,{font:'Arial',bold:true,align:'center'});
text('contact','No. 1, Sec. 4, Roosevelt Rd., Taipei 10617, Taiwan.  *Correspondence: lchen@ntu.edu.tw',170,721,3110,46,25,{font:'Arial',align:'center'});
text('Text Box 49','Paper Code: TW0243',2968,197,405,110,28,{font:'Arial',bold:true,align:'center'});
for(const [name,label,x,y,w,pt] of [['Text Box 42','Introduction',120,917,1500,80],['Text Box 10','Methods',120,2655,1500,80],['Text Box 43','Results',1810,919,1510,80],['Text Box 11','Conclusions',1810,3640,1510,72],['Text Box 27','Bibliography',1830,4080,1460,53]])text(name,label,x,y,w,145,pt,{font:'Arial',bold:label!=='Bibliography',align:'center'});

text('intro_body','Micro-displacement inspection requires image features that can be located consistently when the objective changes. Optical blur and pixel sampling affect the boundary signals used to estimate position.\n\nMOSR combines calibrated optical guidance, anti-aliased multiscale features [1,2] and bounded correction on the original pixel grid. One fixed set of reconstruction weights serves 20× and 50×. We test its measurement benefit using the same circle-center procedure for Raw, fixed Wiener and MOSR.',125,1090,1480,390,29);
text('raw_label','Raw',250,1500,440,60,35,{font:'Arial',bold:true,align:'center'});
text('mosr_label','MOSR',1000,1500,440,60,35,{font:'Arial',bold:true,align:'center'});
for(const [key,label,top] of [['20x','20×',1605],['50x','50×',2115]]){
 text(`mag-${key}`,label,125,top-50,150,50,27,{font:'Arial',bold:true});
 for(const [m,x] of [['Raw',250],['MOSR',1000]]){
  const a=data.images[`${key}_${m}`],side=440;
  await img(`${label}, 1 micrometer, ${m}, actual measured field`,a.path,x,top,side,side);
  const len=side*2/a.scale_um_per_px/a.width_px;
  bar(`scale-${key}-${m}`,x+410-len,top+410,len);
  text(`scale-label-${key}-${m}`,'2 µm',x+390-len,top+362,len+40,42,23,{font:'Arial',align:'center',color:'#FFFFFF'});
 }
}
text('figure1_caption','Fig. 1. Corresponding Raw and MOSR fields at both objectives. Paired images share the crop and grayscale range. Scale bars: 2 µm.',125,2570,1480,83,24);

text('model_heading','Optically guided reconstruction on the native grid',125,2810,1480,56,29,{bold:true,align:'center'});
const input=node('model_input','Input\nimage',130,2910,230,140,26);
const context=node('model_context','Anti-aliased\nU-Net context',460,2910,330,140,25);
const native=node('model_native','Native-grid\nrefinement stages',900,2910,310,140,24);
const output=node('model_output','Input-referenced\nbounded output',1320,2910,270,140,23,true);
const guidance=node('model_optical','Calibrated optical guidance',570,3145,480,105,25);
const sum=slide.shapes.add({geometry:'ellipse',name:'model_bounded_addition',position:P(1240,2950,60,60),fill:'#FFFFFF',line:{fill:'#222222',width:1.9*k}});
sum.text='+';sum.text.style={typeface:'Times New Roman',fontSize:27*4/3,color:'#111111',alignment:'center',verticalAlignment:'middle',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};
connect(input,context);connect(context,native);connect(native,sum);connect(sum,output);
connect(guidance,context,'top','bottom','elbow');
const opticalTurn=anchor('optical_route',1270,3198);
connect(guidance,opticalTurn,'right','left','straight',false);
connect(opticalTurn,sum,'top','bottom','straight');
const refA=anchor('reference_route_a',245,3325),refB=anchor('reference_route_b',1455,3325);
connect(input,refA,'bottom','top','straight',false,true);connect(refA,refB,'right','left','straight',false,true);connect(refB,output,'top','bottom','straight',true,true);
text('reference_label','Original-image reference',605,3270,570,45,23,{align:'center'});
text('figure2_caption','Fig. 2. Functional design of MOSR. Calibrated guidance addresses optical variation; anti-aliased features target sampling sensitivity. Refinement and bounded output retain the native image grid.',125,3360,1480,150,25);

text('readout_heading','Common readout for Raw, fixed Wiener and MOSR',125,3555,1480,60,29,{bold:true,align:'center'});
const bx=140,by=3675,bw=240;
await img('Actual measured boundary and circle center from the displayed 20x MOSR frame',boundary.image_path,bx,by,bw,bw);
const mapX=x=>bx+(x+.5)*bw/boundary.width_px,mapY=y=>by+(y+.5)*bw/boundary.height_px;
const cx=mapX(boundary.center_xy_px[0]),cy=mapY(boundary.center_xy_px[1]),rr=boundary.radius_px*bw/boundary.width_px;
slide.shapes.add({geometry:'ellipse',name:'measured_lsc_circle',position:P(cx-rr,cy-rr,2*rr,2*rr),fill:'none',line:{fill:'#111111',width:1.1*k}});
boundary.boundary_xy_px.forEach((p,i)=>dot(`measured_boundary_point_${i+1}`,mapX(p[0]),mapY(p[1]),1.9,'#FFFFFF'));
slide.shapes.add({geometry:'line',name:'measured_center_x',position:P(cx-10,cy,20,0),line:{fill:'#FFFFFF',width:2.6*k}});
slide.shapes.add({geometry:'line',name:'measured_center_y',position:P(cx,cy-10,0,20),line:{fill:'#FFFFFF',width:2.6*k}});
text('center_label','c',cx+14,cy-30,35,40,23,{italic:true,color:'#FFFFFF'});
const evidenceNode=anchor('boundary_plot_exit',380,3795);
const centers=node('readout_centers','LSC centers\nin paired frames',440,3725,305,145,25);
const shift=node('readout_shift','Median shift\nof nine pillars',850,3725,315,145,25);
const sd=node('readout_sd','30 single steps\nSample SD',1270,3725,320,145,25,true);
connect(evidenceNode,centers);connect(centers,shift);connect(shift,sd);
text('boundary_key','Boundary points and LSC center',130,3930,510,60,22,{align:'center'});
text('figure3_caption','Fig. 3. Coarse contours [3] initialize boundary extraction. Circle fits [4] provide the centers used for displacement. The inset shows measured points and a fitted center.',125,3995,1480,95,24);
text('table1_caption','TABLE I. EVALUATION AT A 1 µm NOMINAL STEP',130,4110,1470,58,26,{align:'center'});
table([['Objective','Acquisition','Steps','µm/pixel'],['20×','31-frame evaluation scan','30','0.1725'],['50×','30 locked adjacent pairs','30','0.0690']],130,4180,1470,190,[265,620,200,385],24);
text('measurement_definition','Centers come from maximum-gradient boundary points and geometric LSC fits. Nine-pillar median shifts use the acquisition direction. Each condition reports the sample SD of 30 steps (denominator 29).',130,4400,1470,115,23);

text('results_intro','At a common nominal step of 1 µm, MOSR gives the lowest observed Step SD in both evaluations. Each comparison uses the same images and measurement settings for all three methods.',1830,1090,1470,155,30);
const font=(size,bold=false)=>({typeface:'Times New Roman',fontSize:size,fill:'#111111',bold});
const baseChart={hasLegend:true,legend:{position:'top',overlay:false,textStyle:font(29)},chartFill:'#FFFFFF',chartLine:{fill:'none',width:0},plotAreaFill:'#FFFFFF',plotAreaLine:{fill:'none',width:0}};
function curve(d,y,xlabel){
 const c=slide.charts.add('line',{...baseChart,position:P(1820,y,1510,500),categories:Array.from({length:30},(_,i)=>String(i+1)),series:methods.map((m,i)=>({name:m,values:d.steps_nm[m].map(v=>Number((v-1000).toFixed(6))),valuesFormatCode:'0.000',fill:['#999999','#555555','#111111'][i],line:{fill:['#999999','#555555','#111111'][i],width:i===2?3.5:2.4,style:i===1?'dashed':'solid'},marker:{symbol:['triangle','square','circle'][i],size:i===2?6:5}})),lineOptions:{grouping:'standard',smooth:false},xAxis:{visible:true,title:{text:xlabel,textStyle:font(25)},textStyle:font(25),line:{fill:'#111111',width:1.2},majorGridlines:null},yAxis:{visible:true,title:{text:'Measured step − 1 µm (nm)',textStyle:font(28)},min:-30,max:30,majorUnit:10,numberFormatCode:'0',textStyle:font(26),line:{fill:'#111111',width:1.2},majorGridlines:{fill:'#D6D6D6',width:.8}},dataLabels:{showValue:false}});
 utils.applyPresentationChartFont(c,{fontFamily:'Times New Roman'});return c;
}
function resultGroup(key,label,d,y){
 text(`${key}_heading`,label,1840,y,1460,74,37,{font:'Arial',bold:true});
 text(`${key}_gain`,`${d.relative_reduction_pct.toFixed(1)}%`,1845,y+90,760,145,85,{font:'Arial',bold:true});
 text(`${key}_value`,`MOSR Step SD\n${d.step_sd_nm.MOSR.toFixed(3)} nm`,2690,y+103,570,123,36,{bold:true,align:'center'});
 text(`${key}_gain_label`,'Lower Step SD relative to Raw',1845,y+235,1450,56,29,{font:'Arial',bold:true});
 table([['Step SD (nm)','Raw','Wiener','MOSR'],['',...methods.map(m=>d.step_sd_nm[m].toFixed(3))]],1830,y+305,1470,130,[530,300,340,300],26);
}
resultGroup('20x','20×, 1 µm: 30 single steps',s20,1260);
curve(s20,1735,'Step number');
text('figure4_caption','Fig. 4. All 30 single-step displacements at 20×. Curves use measured step minus 1 µm, with the same axis limits as the 50× evaluation.',1830,2250,1470,95,24);
const meanDiff=Math.abs(mean(s20.steps_nm.Raw)-mean(s20.steps_nm.MOSR)),sdDiff=s20.step_sd_nm.Raw-s20.step_sd_nm.MOSR;
text('20x_interpretation',`At 20×, the mean step changes by only ${meanDiff.toFixed(2)} nm while Step SD decreases by ${sdDiff.toFixed(2)} nm. This pattern is consistent with more stable boundary-based localization.`,1830,2370,1470,150,28);
resultGroup('50x','50×, 1 µm: 30 single steps',s50,2540);
curve(s50,3015,'Pair number');
text('figure5_caption','Fig. 5. All 30 locked single-step displacements at 50×. MOSR reaches 4.542 nm Step SD with the same learned weights and the corresponding optical calibration.',1830,3530,1470,95,24);
text('conclusions_body','With shared reconstruction weights and objective-specific optical guidance, MOSR reduces single-step variation by 57.2% at 20× and 23.5% at 50×. The observed reductions under a common center readout support MOSR for cross-magnification micro-displacement inspection.',1830,3810,1470,235,29);
text('bibliography_body','[1] O. Ronneberger et al., U-Net, MICCAI, 2015, pp. 234–241.\n[2] R. Zhang, Making convolutional networks shift-invariant again, ICML, 2019, pp. 7324–7334.\n[3] T. F. Chan and L. A. Vese, Active contours without edges, IEEE Trans. Image Process., 10(2), 266–277, 2001.\n[4] N. Chernov and C. Lesort, Least squares fitting of circles, J. Math. Imaging Vis., 23, 239–252, 2005.',1830,4200,1460,260,24);

slide.speakerNotes.textFrame.setText('IMPACT2026 TW0243. Public model name: MOSR. This poster presents an updated evaluation at a nominal 1 micrometer step. The 20x condition uses one complete 31-frame evaluation scan; the 50x condition uses its fixed prior list of 30 adjacent-frame pairs. Conditions are reported separately. All methods use the same image pairs, identities, scale and center-estimation procedure within each condition. Fig. 2 summarizes functional roles; performance values refer to the complete reconstruction and readout. Fig. 3 uses measured boundary points and a fitted center from the displayed 20x MOSR field. The curves contain all 30 observed displacements per condition and method, minus nominal 1000 nm for display; no per-method centering, detrending or smoothing is applied. Sources for method context: Ronneberger et al., MICCAI 2015; Zhang, ICML 2019; Chan and Vese, IEEE TIP 2001; Chernov and Lesort, JMIV 2005.');
const revision=process.env.POSTER_REVISION??'v1';
const draft=path.join(BUILD,`mosr_design_${revision}.pptx`),finalPath=path.join(OUT,`IMPACT2026_MOSR_Design_TW0243_${revision}.pptx`);
await (await PresentationFile.exportPptx(deck)).save(draft);
const patch=spawnSync(PYTHON,[path.join(BUILD,'journal_style.py'),draft],{encoding:'utf8'});if(patch.status!==0)throw new Error(patch.stderr);
await utils.finalizePresentation({workspaceDir:ROOT,candidatePath:draft,finalPath,pythonExecutable:PYTHON,integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','32400000,43200000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','1'],explicitTotalSlideCount:1,requiredNativeTableOwnerSlides:[1],requiredNativeChartOwnerSlides:[1],materializeLiteralChartWorkbooks:true,nativeChartTargetApplication:'portable',fontPolicy:{basis:'reference',families:['Arial','Times New Roman'],referencePath:TEMPLATE,referenceSha256:crypto.createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex')},verifyArtifactToolImport:true,receiptPath:path.join(BUILD,`mosr_design_validation_${revision}.json`)});
await fs.writeFile(path.join(BUILD,`mosr_design_receipt_${revision}.json`),JSON.stringify({source:TEMPLATE,sourceSha256:crypto.createHash('sha256').update(await fs.readFile(TEMPLATE)).digest('hex'),paperCode:'TW0243',dataPath:'results/separate_conditions/poster_data_30steps.json',diagramLevel:'functional design and common readout',fullArchitectureOrTrainingRecipeDisclosed:false,extraThirtyScanResultsDisclosed:false,nativeBoundaryPointCount:64,meanStepChange20xNm:meanDiff,stepSdDecrease20xNm:sdDiff,sourceScope:'one 20x evaluation scan and one 50x locked-pair condition, 30 displacements each; same sources as previous poster'},null,2));
console.log(finalPath);
