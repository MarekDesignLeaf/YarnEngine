const $ = id => document.getElementById(id);
let patterns = [], yarns = [], operations = [], editorState=null, selectedOp='K', currentProjectId=null, lastCalculation=null;

function mode(){ return document.querySelector('input[name="mode"]:checked').value; }
function setMode(){
  const m = mode();
  $('swatchFields').classList.toggle('hidden', m !== 'swatch');
  $('geometryFields').classList.toggle('hidden', m !== 'geometry');
}
document.querySelectorAll('input[name="mode"]').forEach(x => x.addEventListener('change', setMode));

async function boot(){
  try{
    const [health,p,y,o] = await Promise.all([
      fetch('/api/health').then(r=>r.json()),
      fetch('/api/patterns').then(r=>r.json()),
      fetch('/api/yarns').then(r=>r.json()),
      fetch('/api/operations').then(r=>r.json())
    ]);
    patterns=p; yarns=y; operations=o;
    $('apiStatus').textContent=`Engine ${health.version} · online`;
    $('pattern').innerHTML=patterns.map(x=>`<option value="${x.pattern_id}|${x.version}">${x.name} · ${x.family_id}</option>`).join('');
    $('yarn').innerHTML='<option value="">No yarn selected</option>'+yarns.map(x=>`<option value="${x.yarn_id}">${x.brand} · ${x.product}${x.source_type==='synthetic_test'?' · TEST':''}</option>`).join('');
    $('pattern').addEventListener('change', loadPatternChart);
    await loadPatternChart();
  }catch(e){ $('apiStatus').textContent='Engine unavailable'; showError(e.message); }
}

function number(id){ return Number($(id).value); }
function showError(msg){ $('errorBox').textContent=msg; $('errorBox').classList.remove('hidden'); }
function clearError(){ $('errorBox').classList.add('hidden'); $('errorBox').textContent=''; }
function fmt(v,d=1){ return v==null?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:d}); }

$('calcForm').addEventListener('submit', async e=>{
  e.preventDefault(); clearError();
  const button=e.submitter; button.disabled=true; button.textContent='Calculating…';
  const [pattern_id,pattern_version]=$('pattern').value.split('|');
  const m=mode();
  const payload={
    pattern_id, pattern_version,
    yarn_id:$('yarn').value||null,
    width_cm:number('width'),height_cm:number('height'),
    gauge_stitches_per_10cm:number('gaugeSt'),gauge_rows_per_10cm:number('gaugeRows'),
    allowance_percent:number('allowance'),partial_repeat_mode:$('partial').value,
    edges:{left_stitches:number('edgeLeft'),right_stitches:number('edgeRight'),left_operation:'K',right_operation:'K'},
    calculation_mode:m,
    swatch:m==='swatch'?{stitches:number('swatchSt'),rows:number('swatchRows'),yarn_length_m:number('swatchLength')}:null,
    yarn_diameter_mm:m==='geometry'?number('diameter'):null
  };
  try{
    const res=await fetch('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await res.json();
    if(!res.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
    render(data);
  }catch(err){ showError(err.message); }
  finally{ button.disabled=false; button.textContent='Calculate yarn'; }
});

function render(d){
  lastCalculation=d;
  $('emptyState').classList.add('hidden'); $('results').classList.remove('hidden');
  const c=d.consumption;
  $('resultTier').textContent=`TIER ${c.tier} · ${c.model_status}`;
  $('resultTitle').textContent=d.pattern.name;
  $('confidenceBadge').textContent=d.confidence.label;
  $('recommended').textContent=fmt(c.recommended_length_m,1)+' m';
  $('core').textContent=fmt(c.core_length_m,1)+' m';
  $('mass').textContent=c.mass_g==null?'—':fmt(c.mass_g,1)+' g';
  $('packages').textContent=c.packages==null?'—':String(c.packages);
  $('gridValue').textContent=`${d.project.stitches} st × ${d.project.rows} rows`;
  $('achieved').textContent=`Achieved ${fmt(d.project.achieved_width_cm,1)} × ${fmt(d.project.achieved_height_cm,1)} cm`;
  $('patternValue').textContent=d.pattern.name;
  $('familyValue').textContent=d.pattern.family;
  $('yarnValue').textContent=d.yarn?`${d.yarn.brand} · ${d.yarn.product}`:'No yarn selected';
  $('yarnEvidence').textContent=d.yarn?`${d.yarn.evidence_level} · ${d.yarn.source_type}`:'Mass and package count unavailable';
  const ws=d.warnings||[];
  $('warnings').innerHTML=ws.length?ws.map(x=>`<div class="warning">${escapeHtml(x)}</div>`).join(''):'<div class="warning ok">No additional warnings.</div>';
  $('audit').textContent=JSON.stringify({confidence:d.confidence,audit:d.audit,compatibility:d.compatibility,horizontal_layout:d.project.horizontal_layout,vertical_layout:d.project.vertical_layout},null,2);
  $('operations').textContent=JSON.stringify(d.project.operation_counts,null,2);
}

function escapeHtml(s){ return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
boot(); setMode();


async function loadPatternChart(){
  if(!$('pattern').value) return;
  const [id,version]=$('pattern').value.split('|');
  $('patternChart').innerHTML='<div class="chart-meta">Loading chart…</div>';
  try{
    const res=await fetch(`/api/patterns/${encodeURIComponent(id)}/${encodeURIComponent(version)}/chart`);
    const d=await res.json();
    if(!res.ok) throw new Error(d.detail||'Unable to load chart');
    renderPatternChart(d);
  }catch(e){
    $('patternChart').innerHTML=`<div class="chart-error">${escapeHtml(e.message)}</div>`;
    $('patternLegend').innerHTML='';
  }
}

function renderPatternChart(d){
  $('chartMeta').textContent=`${d.repeat_width} stitches × ${d.repeat_height} rows · ${d.symbol_system}`;
  const cols=d.repeat_width;
  const html=d.rows.map(r=>{
    const label=`<div class="chart-row-label">${r.row}<span class="chart-direction">${r.side} ${r.direction==='right_to_left'?'←':r.direction==='left_to_right'?'→':'·'}</span></div>`;
    const cells=r.cells.map(c=>`<div class="chart-cell" data-family="${escapeHtml(c.family)}" data-op="${escapeHtml(c.op)}" data-span="${c.span}" style="grid-column:span ${c.span}" title="${escapeHtml(c.op+' · '+c.name)}">${escapeHtml(c.symbol)}</div>`).join('');
    return label+cells;
  }).join('');
  $('patternChart').innerHTML=`<div class="chart-grid" style="grid-template-columns:46px repeat(${cols},var(--chart-cell,36px))">${html}</div><div class="chart-note">Rows are shown top-down for chart viewing. RS and WS knitting direction is marked explicitly. Cell width follows produced-stitch geometry.</div>`;
  $('patternLegend').innerHTML=d.legend.map(x=>`<div class="legend-item" title="${escapeHtml(x.family)}"><span class="legend-symbol">${escapeHtml(x.symbol)}</span><span>${escapeHtml(x.op)} · ${escapeHtml(x.name)}</span></div>`).join('');
  if(d.warnings?.length){
    $('patternLegend').innerHTML += d.warnings.map(w=>`<div class="legend-item">⚠ ${escapeHtml(w)}</div>`).join('');
  }
}

$('expandChart').addEventListener('click',()=>{
  const card=$('patternChart').closest('.pattern-preview-card');
  const active=card.classList.toggle('expanded');
  $('expandChart').textContent=active?'Close':'Expand';
});


function opInfo(id){ return operations.find(x=>x.operation_id===id)||{operation_id:id,name:id,produces_stitches:1}; }
function symbolFor(id){
  const map={'K':'│','P':'●','YO':'○','K2TOG':'╲','SSK':'╱','BOBBLE':'✦','C2_2R':'C→','C2_2L':'C←'};
  return map[id]||id;
}
function buildPalette(){
  $('operationPalette').innerHTML=operations.map(o=>`<button type="button" class="op-button ${o.operation_id===selectedOp?'active':''}" data-op="${escapeHtml(o.operation_id)}" title="${escapeHtml(o.name)}">${escapeHtml(symbolFor(o.operation_id))} ${escapeHtml(o.operation_id)}</button>`).join('');
  $('operationPalette').querySelectorAll('.op-button').forEach(b=>b.addEventListener('click',()=>{
    selectedOp=b.dataset.op; buildPalette();
  }));
}
async function openEditor(){
  const [id,version]=$('pattern').value.split('|');
  const d=await fetch(`/api/patterns/${encodeURIComponent(id)}/${encodeURIComponent(version)}/chart`).then(r=>r.json());
  const cells=[];
  d.rows.forEach(r=>r.cells.forEach(c=>cells.push({row:r.row,col:c.start_column,operation_id:c.op,span:c.span})));
  editorState={pattern_id:id,version:bumpVersion(version),name:d.name+' edited',width:d.repeat_width,height:d.repeat_height,cells};
  $('editorId').value=editorState.pattern_id+'_CUSTOM';
  $('editorVersion').value=editorState.version;
  $('editorName').value=editorState.name;
  $('editorWidth').value=editorState.width; $('editorHeight').value=editorState.height;
  $('editorPanel').classList.remove('hidden'); buildPalette(); renderEditorGrid();
  $('editorPanel').scrollIntoView({behavior:'smooth',block:'start'});
}
function bumpVersion(v){
  const p=v.split('.').map(Number); if(p.length===3&&p.every(Number.isFinite)){p[2]++;return p.join('.');} return '1.0.1';
}
function syncEditorIdentity(){
  if(!editorState)return;
  editorState.pattern_id=$('editorId').value.trim();
  editorState.version=$('editorVersion').value.trim();
  editorState.name=$('editorName').value.trim();
  const w=Number($('editorWidth').value),h=Number($('editorHeight').value);
  if(w!==editorState.width||h!==editorState.height){
    editorState.width=w; editorState.height=h;
    editorState.cells=editorState.cells.filter(c=>c.row<=h&&c.col+c.span-1<=w);
  }
}
function renderEditorGrid(){
  syncEditorIdentity();
  if(!editorState)return;
  const occ=new Map();
  editorState.cells.forEach(c=>{for(let x=c.col;x<c.col+c.span;x++)occ.set(`${c.row}:${x}`,c)});
  let html='';
  for(let r=editorState.height;r>=1;r--){
    html+=`<div class="editor-row-label">${r}</div>`;
    for(let c=1;c<=editorState.width;c++){
      const cell=occ.get(`${r}:${c}`);
      const isStart=cell&&cell.col===c;
      html+=`<div class="editor-cell ${cell&&!isStart?'covered':''}" data-row="${r}" data-col="${c}" title="${cell?escapeHtml(cell.operation_id):'Empty'}">${isStart?escapeHtml(symbolFor(cell.operation_id)):cell?'·':'+'}</div>`;
    }
  }
  $('editorGrid').innerHTML=`<div class="editor-grid" style="grid-template-columns:42px repeat(${editorState.width},36px)">${html}</div>`;
  $('editorGrid').querySelectorAll('.editor-cell').forEach(el=>el.addEventListener('click',()=>paintEditor(Number(el.dataset.row),Number(el.dataset.col))));
}
function paintEditor(row,col){
  syncEditorIdentity();
  const op=opInfo(selectedOp);
  const span=Math.max(1,Number(op.produces_stitches)||1);
  if(col+span-1>editorState.width){$('editorValidation').textContent='Selected operation does not fit before repeat boundary.';$('editorValidation').className='editor-validation bad';return;}
  editorState.cells=editorState.cells.filter(c=>c.row!==row || (c.col+c.span-1<col || col+span-1<c.col));
  editorState.cells.push({row,col,operation_id:selectedOp,span});
  editorState.cells.sort((a,b)=>a.row-b.row||a.col-b.col);
  renderEditorGrid();
}
async function validateEditor(){
  syncEditorIdentity();
  const res=await fetch('/api/editor/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(editorState)});
  const d=await res.json();
  const box=$('editorValidation');
  if(d.valid){box.textContent='Valid pattern geometry and canonical operation accounting.';box.className='editor-validation good';}
  else{
    const issues=[...(d.grid_issues||[]),...(d.canonical_issues||[])];
    box.textContent=issues.map(x=>`${x.code}: ${x.message}`).join(' | ');
    box.className='editor-validation bad';
  }
  return d.valid;
}
async function saveEditor(){
  if(!(await validateEditor()))return;
  syncEditorIdentity();
  const payload={pattern:editorState,family_id:'CUSTOM',difficulty:'unknown',tags:['custom','editor'],techniques:[]};
  const res=await fetch('/api/editor/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await res.json();
  if(!res.ok){$('editorValidation').textContent=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail);$('editorValidation').className='editor-validation bad';return;}
  $('editorValidation').textContent=`Saved ${d.metadata.pattern_id} ${d.metadata.version}. Reloading pattern library…`;
  $('editorValidation').className='editor-validation good';
  const fresh=await fetch('/api/patterns').then(r=>r.json()); patterns=fresh;
  $('pattern').innerHTML=patterns.map(x=>`<option value="${x.pattern_id}|${x.version}">${x.name} · ${x.family_id}</option>`).join('');
  $('pattern').value=`${d.metadata.pattern_id}|${d.metadata.version}`;
  await loadPatternChart();
}
$('editPattern').addEventListener('click',openEditor);
$('closeEditor').addEventListener('click',()=> $('editorPanel').classList.add('hidden'));
$('validateEditor').addEventListener('click',validateEditor);
$('saveEditor').addEventListener('click',saveEditor);
['editorId','editorVersion','editorName','editorWidth','editorHeight'].forEach(id=>$(id).addEventListener('change',()=>{syncEditorIdentity();renderEditorGrid();}));


function currentCalculationPayload(){
  const [pattern_id,pattern_version]=$('pattern').value.split('|');
  const m=mode();
  return {
    pattern_id, pattern_version,
    yarn_id:$('yarn').value||null,
    width_cm:number('width'),height_cm:number('height'),
    gauge_stitches_per_10cm:number('gaugeSt'),gauge_rows_per_10cm:number('gaugeRows'),
    allowance_percent:number('allowance'),partial_repeat_mode:$('partial').value,
    edges:{left_stitches:number('edgeLeft'),right_stitches:number('edgeRight'),left_operation:'K',right_operation:'K'},
    calculation_mode:m,
    swatch:m==='swatch'?{stitches:number('swatchSt'),rows:number('swatchRows'),yarn_length_m:number('swatchLength')}:null,
    yarn_diameter_mm:m==='geometry'?number('diameter'):null
  };
}
function setProjectLabel(name){ $('currentProjectLabel').textContent=name||'Unsaved project'; }
function resetProject(){
  currentProjectId=null; lastCalculation=null; setProjectLabel('Unsaved project');
  $('results').classList.add('hidden'); $('emptyState').classList.remove('hidden');
}
async function saveCurrentProject(){
  const existing=currentProjectId?await fetch(`/api/projects/${currentProjectId}`).then(r=>r.ok?r.json():null):null;
  const name=existing?.name || prompt('Project name', $('pattern').selectedOptions[0]?.textContent || 'Knitting project');
  if(!name)return;
  const payload={name,description:existing?.description||null,calculation:currentCalculationPayload(),result:lastCalculation,status:lastCalculation?'calculated':'draft'};
  let res;
  if(currentProjectId){
    res=await fetch(`/api/projects/${currentProjectId}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  }else{
    res=await fetch('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  }
  const d=await res.json();
  if(!res.ok){showError(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));return;}
  currentProjectId=d.project_id; setProjectLabel(d.name); await refreshProjects();
}
async function refreshProjects(){
  const list=await fetch('/api/projects').then(r=>r.json());
  $('projectsList').innerHTML=list.length?list.map(p=>`
    <div class="project-item">
      <div><h3>${escapeHtml(p.name)} <span class="project-status">${escapeHtml(p.status)}</span></h3>
      <p>${escapeHtml(p.pattern_id)} ${escapeHtml(p.pattern_version)} · ${p.yarn_id?escapeHtml(p.yarn_id):'no yarn'} · updated ${escapeHtml(p.updated_at)}</p></div>
      <div class="project-item-actions">
        <button type="button" class="ghost-button" data-open="${p.project_id}">Open</button>
        <button type="button" class="ghost-button" data-delete="${p.project_id}">Delete</button>
      </div>
    </div>`).join(''):'<div class="chart-meta">No saved projects yet.</div>';
  $('projectsList').querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>openProject(Number(b.dataset.open))));
  $('projectsList').querySelectorAll('[data-delete]').forEach(b=>b.addEventListener('click',()=>deleteProject(Number(b.dataset.delete))));
}
async function openProject(id){
  const p=await fetch(`/api/projects/${id}`).then(r=>r.json());
  currentProjectId=p.project_id; setProjectLabel(p.name);
  const c=p.request;
  $('pattern').value=`${c.pattern_id}|${c.pattern_version}`; await loadPatternChart();
  $('yarn').value=c.yarn_id||'';
  $('width').value=c.width_cm; $('height').value=c.height_cm;
  $('gaugeSt').value=c.gauge_stitches_per_10cm; $('gaugeRows').value=c.gauge_rows_per_10cm;
  $('allowance').value=c.allowance_percent; $('partial').value=c.partial_repeat_mode;
  $('edgeLeft').value=c.edges?.left_stitches||0; $('edgeRight').value=c.edges?.right_stitches||0;
  const radio=document.querySelector(`input[name="mode"][value="${c.calculation_mode}"]`); if(radio)radio.checked=true; setMode();
  if(c.swatch){$('swatchSt').value=c.swatch.stitches;$('swatchRows').value=c.swatch.rows;$('swatchLength').value=c.swatch.yarn_length_m;}
  if(c.yarn_diameter_mm)$('diameter').value=c.yarn_diameter_mm;
  if(p.result){render(p.result);}else{lastCalculation=null;$('results').classList.add('hidden');$('emptyState').classList.remove('hidden');}
  $('projectsPanel').classList.add('hidden');
}
async function deleteProject(id){
  if(!confirm('Delete this saved project?'))return;
  await fetch(`/api/projects/${id}`,{method:'DELETE'});
  if(currentProjectId===id)resetProject();
  await refreshProjects();
}
$('saveProject').addEventListener('click',saveCurrentProject);
$('newProject').addEventListener('click',resetProject);
$('openProjects').addEventListener('click',async()=>{$('projectsPanel').classList.remove('hidden');await refreshProjects();});
$('closeProjects').addEventListener('click',()=> $('projectsPanel').classList.add('hidden'));


function parseFibre(s){
  const m=String(s).trim().match(/^(.+?)\s+(\d+(?:\.\d+)?)$/);
  if(!m)throw new Error('Fibre format must be like "Wool 100"');
  return {[m[1].trim()]:Number(m[2])};
}
async function reloadYarns(){
  yarns=await fetch('/api/yarns').then(r=>r.json());
  $('yarn').innerHTML='<option value="">No yarn selected</option>'+yarns.map(x=>`<option value="${x.yarn_id}">${x.brand} · ${x.product}${x.source_type==='synthetic_test'?' · TEST':''}</option>`).join('');
}
async function createYarn(){
  const status=$('yarnManagerStatus');
  try{
    const payload={yarn_id:$('ymId').value.trim(),brand:$('ymBrand').value.trim(),product:$('ymProduct').value.trim(),
      variant:$('ymVariant').value.trim()||null,cyc_weight:$('ymWeight').value===''?null:Number($('ymWeight').value),
      package_mass_g:Number($('ymMass').value),package_length_m:Number($('ymLength').value),
      fibre_composition:parseFibre($('ymFibre').value),nominal_diameter_mm:$('ymDiameter').value===''?null:Number($('ymDiameter').value)};
    const r=await fetch('/api/yarns',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const d=await r.json(); if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));
    await reloadYarns();status.textContent=`Created ${d.yarn.yarn_id}.`;status.className='editor-validation good';
  }catch(e){status.textContent=e.message;status.className='editor-validation bad';}
}
function fillSwatchSelectors(){
  $('swPattern').innerHTML=patterns.map(x=>`<option value="${x.pattern_id}|${x.version}">${x.name}</option>`).join('');
  $('swYarn').innerHTML=yarns.map(x=>`<option value="${x.yarn_id}">${x.brand} · ${x.product}</option>`).join('');
}
async function refreshSwatches(){
  const rows=await fetch('/api/swatches').then(r=>r.json());
  $('swatchList').innerHTML=rows.length?rows.map(s=>`<div class="project-item"><div><h3>${escapeHtml(s.name)}</h3><p>${escapeHtml(s.pattern_id)} · ${escapeHtml(s.yarn_id)} · ${s.stitches} st × ${s.rows} rows · ${s.width_cm} × ${s.height_cm} cm · ${s.yarn_length_m??'—'} m</p></div><div class="project-item-actions"><button type="button" class="ghost-button" data-use-swatch="${s.swatch_id}">Use</button><button type="button" class="ghost-button" data-del-swatch="${s.swatch_id}">Delete</button></div></div>`).join(''):'<div class="chart-meta">No measured swatches yet.</div>';
  $('swatchList').querySelectorAll('[data-use-swatch]').forEach(b=>b.addEventListener('click',()=>useSwatch(Number(b.dataset.useSwatch))));
  $('swatchList').querySelectorAll('[data-del-swatch]').forEach(b=>b.addEventListener('click',async()=>{await fetch(`/api/swatches/${b.dataset.delSwatch}`,{method:'DELETE'});refreshSwatches();}));
}
async function createSwatch(){
  const [pattern_id,pattern_version]=$('swPattern').value.split('|');
  const payload={name:$('swName').value.trim(),pattern_id,pattern_version,yarn_id:$('swYarn').value,
    stitches:Number($('swStitches').value),rows:Number($('swRows').value),
    needle_mm:$('swNeedle').value?Number($('swNeedle').value):null,width_cm:Number($('swWidth').value),height_cm:Number($('swHeight').value),
    yarn_length_m:Number($('swLength').value)||null,yarn_mass_g:null};
  const r=await fetch('/api/swatches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await r.json();const box=$('swatchStatus');
  if(!r.ok){box.textContent=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail);box.className='editor-validation bad';return;}
  box.textContent=`Saved measured swatch #${d.swatch_id}.`;box.className='editor-validation good';await refreshSwatches();
}
async function useSwatch(id){
  const s=await fetch(`/api/swatches/${id}`).then(r=>r.json());
  $('pattern').value=`${s.pattern_id}|${s.pattern_version}`;$('yarn').value=s.yarn_id;
  $('swatchSt').value=s.stitches;$('swatchRows').value=s.rows;$('swatchLength').value=s.yarn_length_m;
  document.querySelector('input[name="mode"][value="swatch"]').checked=true;setMode();await loadPatternChart();
  $('swatchesPanel').classList.add('hidden');
}
$('openYarnManager').addEventListener('click',()=> $('yarnManagerPanel').classList.remove('hidden'));
$('closeYarnManager').addEventListener('click',()=> $('yarnManagerPanel').classList.add('hidden'));
$('createYarn').addEventListener('click',createYarn);
$('openSwatches').addEventListener('click',async()=>{fillSwatchSelectors();$('swatchesPanel').classList.remove('hidden');await refreshSwatches();});
$('closeSwatches').addEventListener('click',()=> $('swatchesPanel').classList.add('hidden'));
$('createSwatch').addEventListener('click',createSwatch);


async function refreshLab(){
 const d=await fetch('/api/calibration-lab/status').then(r=>r.json());
 const c=d.coverage||{};
 $('labStatus').innerHTML=[
  ['Eligible',c.records||0],['Patterns',Object.keys(c.patterns||{}).length],['Yarns',Object.keys(c.yarns||{}).length],['Excluded',(d.excluded||[]).length]
 ].map(x=>`<div class="cal-card"><span>${x[0]}</span><strong>${x[1]}</strong></div>`).join('');
 const box=$('labReport');
 if(d.ready){box.textContent='Readiness gate passed. Model fitting is enabled, but remains research-stage until validation evidence is adequate.';box.className='editor-validation good';}
 else{box.textContent='Not ready: '+(d.reasons||[]).join(' · ')+(d.excluded?.length?' · Excluded: '+d.excluded.map(x=>`#${x.swatch_id} ${x.reason}`).join('; '):'');box.className='editor-validation bad';}
 $('fitLab').disabled=!d.ready;$('registerModel').disabled=!d.ready; await refreshQuality(); await refreshModels();
}
async function fitLab(){
 const r=await fetch('/api/calibration-lab/fit',{method:'POST'});const d=await r.json();const box=$('labReport');
 if(!r.ok){box.textContent=JSON.stringify(d.detail);box.className='editor-validation bad';return;}
 const cv=d.leave_one_out;
 box.textContent=`Research model fitted on ${d.model.n_samples} samples. Training RMSE ${d.model.rmse_m.toFixed(4)} m, MAE ${d.model.mae_m.toFixed(4)} m. `+
   (cv?`LOO RMSE ${cv.rmse_m.toFixed(4)} m, MAE ${cv.mae_m.toFixed(4)} m.`:`Validation unavailable: ${d.validation_error||'insufficient data'}`)+
   ' This model is not automatically promoted to production.';
 box.className='editor-validation good';
}
$('openLab').addEventListener('click',async()=>{$('labPanel').classList.remove('hidden');await refreshLab();});
$('closeLab').addEventListener('click',()=> $('labPanel').classList.add('hidden'));
$('refreshLab').addEventListener('click',refreshLab);$('fitLab').addEventListener('click',fitLab);


async function refreshQuality(){
 const d=await fetch('/api/calibration-lab/quality').then(r=>r.json());
 const box=$('replicateReport');
 if(!d.groups.length){box.textContent='No replicate groups defined yet.';return;}
 box.textContent=d.groups.map(g=>`${g.replicate_group_id}: n=${g.n}, CV=${g.cv_percent===null?'—':g.cv_percent.toFixed(2)+'%'}`).join(' · ')+
  (d.flags.length?' · Flags: '+d.flags.map(f=>`${f.group}/${f.code}`).join(', '):' · No replicate flags.');
}
async function refreshModels(){
 const ms=await fetch('/api/models').then(r=>r.json());
 $('modelRegistry').innerHTML=ms.length?ms.map(m=>`<div class="project-item"><div><h3>${escapeHtml(m.name)} <span class="project-status">${escapeHtml(m.stage)}</span></h3><p>${escapeHtml(m.model_id)} · n=${m.model.n_samples} · RMSE ${Number(m.model.rmse_m).toFixed(4)} m</p></div><div class="project-item-actions">${m.stage==='research'?`<button type="button" class="ghost-button" data-promote="${m.model_id}" data-target="candidate">Candidate</button>`:''}${m.stage==='candidate'?`<button type="button" class="ghost-button" data-promote="${m.model_id}" data-target="production">Production</button>`:''}${m.stage!=='retired'?`<button type="button" class="ghost-button" data-promote="${m.model_id}" data-target="retired">Retire</button>`:''}</div></div>`).join(''):'<div class="chart-meta">No registered models.</div>';
 $('modelRegistry').querySelectorAll('[data-promote]').forEach(b=>b.addEventListener('click',()=>promoteModel(b.dataset.promote,b.dataset.target)));
}
async function registerModel(){
 const name=prompt('Model name','Real calibration candidate');if(!name)return;
 const r=await fetch('/api/calibration-lab/fit-and-register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
 const d=await r.json();if(!r.ok){$('labReport').textContent=JSON.stringify(d.detail);$('labReport').className='editor-validation bad';return;}
 $('labReport').textContent=`Registered ${d.model_id} as research. Promotion requires an explicit separate action.`;$('labReport').className='editor-validation good';await refreshModels();
}
async function promoteModel(id,target){
 if(!confirm(`Promote model ${id} to ${target}?`))return;
 const note=prompt('Promotion note / evidence reference','Manual review');
 const r=await fetch(`/api/models/${id}/promote`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target,note})});
 const d=await r.json();if(!r.ok){$('labReport').textContent=JSON.stringify(d.detail);return;}await refreshModels();
}
$('registerModel').addEventListener('click',registerModel);

async function loadProductionModel(){
 const d=await fetch('/api/models/production/current').then(r=>r.json());
 $('productionModelLabel').textContent=d.active?`${d.model.name} · ${d.model.model_id} · n=${d.model.n_samples} · RMSE ${Number(d.model.rmse_m).toFixed(4)} m`:'No approved production model';
}

let inspectedImport=null;
async function inspectImport(){
 const box=$('importReport');$('acceptImport').disabled=true;inspectedImport=null;
 try{
  const payload=JSON.parse($('importJson').value);
  const r=await fetch('/api/import-studio/inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await r.json();if(!r.ok)throw new Error(JSON.stringify(d.detail));
  inspectedImport=d;
  box.className='editor-validation '+(d.valid?'good':'bad');
  box.innerHTML=`<strong>${d.valid?'Structurally valid':'Invalid'}</strong> · checksum ${d.checksum||'—'} · review ${d.review_required?'required':'clear'}`+
   (d.duplicate?` · duplicate: ${escapeHtml(d.duplicate.type)}`:'')+
   (d.issues||[]).map(x=>`<div class="import-issue import-${x.severity}">${escapeHtml(x.code)}: ${escapeHtml(x.message)}</div>`).join('');
  $('acceptImport').disabled=!(d.valid&&!d.duplicate&&d.bundle?.metadata?.source_reference&&d.bundle?.metadata?.license_id);
  $('importPreview').innerHTML=d.bundle?`<pre>${escapeHtml(JSON.stringify(d.bundle,null,2))}</pre>`:'';
 }catch(e){box.textContent=e.message;box.className='editor-validation bad';}
}
async function acceptImport(){
 if(!inspectedImport?.bundle)return;
 const r=await fetch('/api/import-studio/accept',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(inspectedImport.bundle)});
 const d=await r.json();const box=$('importReport');
 if(!r.ok){box.textContent=JSON.stringify(d.detail);box.className='editor-validation bad';return;}
 box.textContent=`Accepted ${d.pattern_id} ${d.version}. Checksum ${d.checksum}.`;box.className='editor-validation good';
 await boot();
}
$('openImportStudio').addEventListener('click',()=> $('importStudioPanel').classList.remove('hidden'));
$('closeImportStudio').addEventListener('click',()=> $('importStudioPanel').classList.add('hidden'));
$('inspectImport').addEventListener('click',inspectImport);$('acceptImport').addEventListener('click',acceptImport);

$('openAcquisition').addEventListener('click',()=> $('acquisitionPanel').classList.remove('hidden'));
$('closeAcquisition').addEventListener('click',()=> $('acquisitionPanel').classList.add('hidden'));
$('translateAcquisition').addEventListener('click', async ()=>{
 const lines=$('acqRows').value.split(/\r?\n/).filter(x=>x.trim());
 const payload={
  pattern_id:$('acqId').value,name:$('acqName').value,version:'1.0.0',
  repeat:{width_stitches:Number($('acqWidth').value),height_rows:lines.length},
  rows:lines.map((instruction,i)=>({row:i+1,side:i%2===0?'RS':'WS',instruction})),
  metadata:{family_id:'UNCLASSIFIED',difficulty:'unknown',techniques:['knitting'],source_type:'user_import'}
 };
 const r=await fetch('/api/acquisition/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();const box=$('acqReport');
 if(!r.ok){box.textContent=JSON.stringify(d.detail);box.className='editor-validation bad';return;}
 box.textContent=`Stage: ${d.stage} · valid: ${d.valid} · review required: ${d.review_required}`;
 box.className='editor-validation '+(d.valid?'good':'bad');
 $('acqPreview').textContent=JSON.stringify(d,null,2);
});

$('openShaping').addEventListener('click',()=> $('shapingPanel').classList.remove('hidden'));
$('closeShaping').addEventListener('click',()=> $('shapingPanel').classList.add('hidden'));
$('translateShaping').addEventListener('click',async()=>{
 const lines=$('shapeRows').value.split(/\r?\n/).filter(x=>x.trim());
 const payload={pattern_id:$('shapeId').value,name:$('shapeName').value,version:'1.0.0',
  initial_stitches:Number($('shapeInitial').value),construction:'flat',
  rows:lines.map((instruction,i)=>({row:i+1,side:i%2===0?'RS':'WS',instruction}))};
 const r=await fetch('/api/shaping/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();const box=$('shapeReport');
 if(!r.ok){box.textContent=JSON.stringify(d.detail);box.className='editor-validation bad';return;}
 box.textContent=`Stage: ${d.stage} · valid: ${d.valid}`+(d.final_stitches!==undefined?` · ${d.initial_stitches} → ${d.final_stitches} stitches`:'');
 box.className='editor-validation '+(d.valid?'good':'bad');
 $('shapePreview').textContent=JSON.stringify(d,null,2);
});

$('openSpatial').addEventListener('click',()=> $('spatialPanel').classList.remove('hidden'));
$('closeSpatial').addEventListener('click',()=> $('spatialPanel').classList.add('hidden'));
$('analyseSpatial').addEventListener('click',async()=>{
 const lines=$('spatialRows').value.split(/\r?\n/).filter(x=>x.trim());
 const payload={pattern_id:$('spatialId').value,name:$('spatialId').value,version:'1.0.0',
  initial_stitches:Number($('spatialInitial').value),construction:'flat',
  gauge_preview:{stitch_width_mm:Number($('spatialStitchWidth').value),row_height_mm:Number($('spatialRowHeight').value)},
  rows:lines.map((instruction,i)=>({row:i+1,side:i%2===0?'RS':'WS',instruction}))};
 const r=await fetch('/api/spatial-shaping/analyse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();const box=$('spatialReport');
 if(!r.ok){box.textContent=JSON.stringify(d.detail);box.className='editor-validation bad';return;}
 const events=d.topology?.rows?.reduce((n,x)=>n+(x.shaping_events?.length||0),0)||0;
 box.textContent=`Stage: ${d.stage} · valid: ${d.valid} · shaping events: ${events}`;
 box.className='editor-validation '+(d.valid?'good':'bad');
 $('spatialPreview').textContent=JSON.stringify(d,null,2);
});

$('openGroups').addEventListener('click',()=> $('groupsPanel').classList.remove('hidden'));
$('closeGroups').addEventListener('click',()=> $('groupsPanel').classList.add('hidden'));
$('analyseGroups').addEventListener('click',async()=>{
 let events;
 try{events=JSON.parse($('groupsEvents').value);}catch(e){
  $('groupsReport').textContent='Invalid JSON';$('groupsReport').className='editor-validation bad';return;
 }
 const payload={initial_stitches:Number($('groupsInitial').value),events};
 const r=await fetch('/api/stitch-groups/analyse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();const box=$('groupsReport');
 if(!r.ok){box.textContent=JSON.stringify(d.detail);box.className='editor-validation bad';return;}
 box.textContent=`valid: ${d.valid} · live stitches: ${d.live_stitches ?? 'n/a'} · groups: ${d.groups ? Object.keys(d.groups).length : 0}`;
 box.className='editor-validation '+(d.valid?'good':'bad');
 $('groupsPreview').textContent=JSON.stringify(d,null,2);
});


// M9.5 Crochet calibration workflow
function ccValue(id){ return $(id).value.trim(); }
function ccNumberOrNull(id){ const v=$(id).value.trim(); return v===''?null:Number(v); }

async function refreshCrochetCalibration(){
  const [status,records]=await Promise.all([
    fetch('/api/crochet/calibration/status').then(r=>r.json()),
    fetch('/api/crochet/calibration/records').then(r=>r.json())
  ]);
  const box=$('crochetCalibrationStatus');
  box.className='editor-validation '+(status.ready?'good':'bad');
  box.textContent=status.ready?'Calibration evidence gate READY':
    'Not ready: '+(status.reasons||[]).join(' | ');
  $('crochetCalibrationRecords').innerHTML=(records||[]).map(r=>
    `<div class="project-card"><strong>${escapeHtml(r.record_id)}</strong> · ${escapeHtml(r.construction)} · ${escapeHtml(r.yarn_id)} · ${fmt(r.yarn_length_m,3)} m<br><span>${escapeHtml(JSON.stringify(r.operation_counts))}</span></div>`
  ).join('')||'<div class="chart-meta">No physical crochet measurements stored.</div>';
}

function printableCrochetForm(){
  const formId=ccValue('ccFormId')||'CROCHET_CALIBRATION_FORM';
  const operator=ccValue('ccCrocheter');
  const yarn=ccValue('ccYarn');
  const hook=ccValue('ccHook');
  const construction=ccValue('ccConstruction');
  const group=ccValue('ccGroup');
  const ops=['SC','SC_INC','SC2TOG','SC_BLO','SC_FLO','SLST','CH','HDC','DC','TR','PUFF3','POPCORN5'];
  const rows=ops.map(op=>`<tr><td>${op}</td><td></td><td></td></tr>`).join('');
  const w=window.open('','_blank');
  w.document.write(`<!doctype html><html><head><title>${escapeHtml(formId)}</title><style>
    @page{size:A4;margin:12mm}body{font-family:Arial,sans-serif;color:#111;font-size:11pt}
    h1{font-size:18pt;margin:0 0 4mm}h2{font-size:12pt;margin:5mm 0 2mm}
    .meta{display:grid;grid-template-columns:1fr 1fr;gap:2mm 8mm}
    .line{border-bottom:1px solid #222;min-height:7mm;padding:1mm}
    table{width:100%;border-collapse:collapse;margin-top:2mm}th,td{border:1px solid #333;padding:2mm;text-align:left;height:7mm}
    .note{font-size:9pt;margin-top:4mm}.checks{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2mm}
  </style></head><body>
  <h1>Crochet Calibration Measurement Form</h1>
  <div><strong>Form ID:</strong> ${escapeHtml(formId)}</div>
  <h2>Predefined setup</h2><div class="meta">
  <div>Operator / crocheter<div class="line">${escapeHtml(operator)}</div></div>
  <div>Replicate group<div class="line">${escapeHtml(group)}</div></div>
  <div>Yarn ID<div class="line">${escapeHtml(yarn)}</div></div>
  <div>Hook size (mm)<div class="line">${escapeHtml(hook)}</div></div>
  <div>Construction<div class="line">${escapeHtml(construction)}</div></div>
  <div>Date<div class="line"></div></div></div>
  <h2>Physical measurements</h2><div class="meta">
  <div>Record ID<div class="line"></div></div><div>Condition<div class="line">as crocheted / relaxed / other:</div></div>
  <div>Gauge stitches counted<div class="line"></div></div><div>Gauge rounds / rows counted<div class="line"></div></div>
  <div>Measured width (mm)<div class="line"></div></div><div>Measured height (mm)<div class="line"></div></div>
  <div>Yarn length used (m)<div class="line"></div></div><div>Yarn mass used (g)<div class="line"></div></div>
  <div>Yarn diameter (mm)<div class="line"></div></div><div>Evidence / photo reference<div class="line"></div></div></div>
  <h2>Canonical operation counts</h2>
  <table><thead><tr><th>Operation</th><th>Count</th><th>Notes</th></tr></thead><tbody>${rows}</tbody></table>
  <h2>Measurement controls</h2><div class="checks">
  <div>□ Same yarn lot</div><div>□ Same hook</div><div>□ Same operator</div>
  <div>□ Sample conditioned consistently</div><div>□ Length measured</div><div>□ Photo/reference captured</div></div>
  <div class="note">This sheet records physical evidence. Do not estimate missing measurements. Enter the completed values into YarnEngine Crochet Calibration before fitting a model.</div>
  <script>window.onload=()=>window.print();<\/script></body></html>`);
  w.document.close();
}

async function saveCrochetMeasurement(){
  let operation_counts;
  try{operation_counts=JSON.parse($('ccOps').value);}catch(e){$('crochetCalibrationStatus').textContent='Operation counts must be valid JSON.';return;}
  const payload={
    record_id:ccValue('ccRecordId'),replicate_group_id:ccValue('ccGroup'),crocheter_id:ccValue('ccCrocheter'),
    yarn_id:ccValue('ccYarn'),hook_mm:Number($('ccHook').value),gauge_stitches:Number($('ccGaugeSt').value),
    gauge_rows:Number($('ccGaugeRows').value),gauge_width_mm:Number($('ccWidth').value),
    gauge_height_mm:Number($('ccHeight').value),operation_counts,
    yarn_length_m:Number($('ccUsedM').value),yarn_mass_g:ccNumberOrNull('ccMassG'),
    yarn_diameter_mm:ccNumberOrNull('ccDiameter'),construction:ccValue('ccConstruction'),
    tension_condition:'as_crocheted',evidence_reference:ccValue('ccEvidence')||null
  };
  const r=await fetch('/api/crochet/calibration/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const d=await r.json();
  if(!r.ok){$('crochetCalibrationStatus').textContent=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail);return;}
  await refreshCrochetCalibration();
}

async function fitCrochetCalibration(){
  const r=await fetch('/api/crochet/calibration/fit-register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Crochet calibration candidate'})});
  const d=await r.json();
  const box=$('crochetCalibrationStatus');
  if(!r.ok){box.className='editor-validation bad';box.textContent=typeof d.detail==='string'?d.detail:JSON.stringify(d.detail);return;}
  box.className='editor-validation good';box.textContent=`Registered research model ${d.model.model_id}. Promotion still requires model governance gates.`;
}

$('openCrochetCalibration')?.addEventListener('click',()=>{$('crochetCalibrationPanel').classList.remove('hidden');refreshCrochetCalibration();$('crochetCalibrationPanel').scrollIntoView({behavior:'smooth'});});
$('closeCrochetCalibration')?.addEventListener('click',()=>$('crochetCalibrationPanel').classList.add('hidden'));
$('printCrochetForm')?.addEventListener('click',printableCrochetForm);
$('refreshCrochetCalibration')?.addEventListener('click',refreshCrochetCalibration);
$('saveCrochetMeasurement')?.addEventListener('click',saveCrochetMeasurement);
$('fitCrochetCalibration')?.addEventListener('click',fitCrochetCalibration);

let currentCrochetExperimentPlan=null;
async function generateCrochetPlan(){
 const payload={yarn_id:ccValue('ccYarn')||null,crocheter_id:ccValue('ccCrocheter')||null,
  hook_mm:ccValue('ccHook')||null,construction:ccValue('ccConstruction')||'spiral'};
 const r=await fetch('/api/crochet/calibration/experiment-plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const d=await r.json();if(!r.ok){$('crochetCalibrationStatus').textContent=JSON.stringify(d.detail);return;}
 currentCrochetExperimentPlan=d;
 $('crochetExperimentPlan').innerHTML=d.complete?'<div class="editor-validation good">Configured calibration evidence is complete.</div>':
 `<div class="section-title">Missing experiment plan · ${d.count} physical measurements</div>`+
 d.experiments.map(x=>`<div class="project-card"><strong>${escapeHtml(x.experiment_id)}</strong> · ${escapeHtml(x.operation)} · replicate ${x.replicate}<br>
 Group ${escapeHtml(x.replicate_group_id)} · ${escapeHtml(x.construction)}<br><span>${escapeHtml(x.instruction.note)}</span></div>`).join('');
}
function printCrochetPlan(){
 if(!currentCrochetExperimentPlan){generateCrochetPlan().then(printCrochetPlan);return;}
 const d=currentCrochetExperimentPlan,w=window.open('','_blank');
 const cards=d.experiments.map(x=>`<section><h2>${escapeHtml(x.experiment_id)} · ${escapeHtml(x.operation)}</h2>
 <p>Replicate group: ${escapeHtml(x.replicate_group_id)} | Replicate: ${x.replicate} | Construction: ${escapeHtml(x.construction)}</p>
 <p>Yarn: ${escapeHtml(x.yarn_id||'________________')} | Operator: ${escapeHtml(x.crocheter_id||'________________')} | Hook mm: ${escapeHtml(x.hook_mm??'______')}</p>
 <table><tr><td>Exact operation count</td><td></td><td>Gauge stitches</td><td></td></tr>
 <tr><td>Gauge rows / rounds</td><td></td><td>Width mm</td><td></td></tr>
 <tr><td>Height mm</td><td></td><td>Yarn length m</td><td></td></tr>
 <tr><td>Yarn mass g</td><td></td><td>Yarn diameter mm</td><td></td></tr>
 <tr><td>Evidence reference</td><td colspan="3"></td></tr></table>
 <p class="note">${escapeHtml(x.instruction.note)}</p></section>`).join('');
 w.document.write(`<!doctype html><html><head><title>Crochet calibration experiment plan</title><style>
 @page{size:A4;margin:12mm}body{font-family:Arial,sans-serif;color:#111;font-size:10pt}h1{font-size:18pt}
 section{break-inside:avoid;border:1px solid #222;padding:4mm;margin:0 0 5mm}h2{font-size:12pt;margin:0 0 2mm}
 table{width:100%;border-collapse:collapse}td{border:1px solid #444;padding:2mm;height:6mm}.note{font-size:8.5pt}
 </style></head><body><h1>Crochet Calibration Experiment Plan</h1>
 <p>Required physical measurements: ${d.count}. This plan contains no synthetic measurement values.</p>${cards}
 <script>window.onload=()=>window.print();<\/script></body></html>`);w.document.close();
}
$('generateCrochetPlan')?.addEventListener('click',generateCrochetPlan);
$('printCrochetPlan')?.addEventListener('click',printCrochetPlan);

async function checkCrochetQuality(){
 const r=await fetch('/api/crochet/calibration/quality');const d=await r.json();
 const box=$('crochetQualityStatus');if(!r.ok){box.className='editor-validation bad';box.textContent=JSON.stringify(d.detail);return;}
 const rep=d.replicates,con=d.consistency;
 const rows=(rep.groups||[]).map(g=>`${g.replicate_group_id}: n=${g.n}, CV=${g.cv==null?'—':(g.cv*100).toFixed(1)+'%'}, ${g.status}`).join(' | ');
 box.className='editor-validation '+(rep.overall==='fail'||!con.valid?'bad':rep.overall==='pass'&&con.valid?'good':'');
 box.textContent=`Replicates: ${rep.overall}. ${rows||'No groups.'} Mass/tex consistency: ${con.valid?'pass':'fail ('+con.issues.length+' issues)'}.`;
}
$('checkCrochetQuality')?.addEventListener('click',checkCrochetQuality);

async function printCrochetAudit(){
 const r=await fetch('/api/crochet/calibration/audit');const d=await r.json();
 if(!r.ok){$('crochetCalibrationStatus').textContent=JSON.stringify(d.detail);return;}
 const w=window.open('','_blank'),groups=(d.replicate_quality.groups||[]).map(g=>
 `<tr><td>${escapeHtml(g.replicate_group_id)}</td><td>${g.n}</td><td>${g.cv==null?'—':(g.cv*100).toFixed(2)+'%'}</td><td>${g.status}</td></tr>`).join('');
 w.document.write(`<!doctype html><html><head><title>Calibration Audit</title><style>
 @page{size:A4;margin:12mm}body{font-family:Arial,sans-serif;font-size:10pt;color:#111}h1{font-size:18pt}
 table{width:100%;border-collapse:collapse}th,td{border:1px solid #333;padding:2mm}.hash{font-family:monospace;word-break:break-all;font-size:8pt}
 </style></head><body><h1>Crochet Calibration Audit</h1>
 <p>Created: ${escapeHtml(d.created_at)}</p><p>Records: ${d.dataset.record_count}</p>
 <p>Dataset SHA256:</p><div class="hash">${escapeHtml(d.dataset.dataset_sha256)}</div>
 <h2>Evidence gate</h2><p>${d.readiness.ready?'READY':'NOT READY'}</p>
 <p>${escapeHtml((d.readiness.reasons||[]).join(' | ')||'No missing evidence reported.')}</p>
 <h2>Replicate quality</h2><p>Overall: ${escapeHtml(d.replicate_quality.overall)}</p>
 <table><tr><th>Group</th><th>N</th><th>CV</th><th>Status</th></tr>${groups}</table>
 <h2>Measurement consistency</h2><p>${d.measurement_consistency.valid?'PASS':'FAIL'}</p>
 <p>Issues: ${d.measurement_consistency.issues.length}</p>
 <h2>Audit integrity</h2><div class="hash">${escapeHtml(d.audit_sha256)}</div>
 <script>window.onload=()=>window.print();<\/script></body></html>`);w.document.close();
}
$('printCrochetAudit')?.addEventListener('click',printCrochetAudit);
