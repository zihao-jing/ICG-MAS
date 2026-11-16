"""Build rebuttal/annotation/labelling_20261108/: one self-contained folder for authors. Blind export only.

Never contains audit, matcher, judge, lexical or baseline output; no model names or run names; items are named Q/run numbers.
Re-running is refused if any file already contains entered answers.
"""
import csv,hashlib,json
from pathlib import Path
from collections import defaultdict
SRC=Path('rebuttal/annotation/author_packet_20261108');OLD=Path('rebuttal/annotation');F=Path('rebuttal/annotation/labelling_20261108');P=Path('rebuttal/pilots')
E1_FIELDS=['critical_facts_json','sufficient_support_sets_json','carriers_json','binary_call','rationale','uncertain_reason','minutes_spent']
YN=['yes','no','uncertain']
TASKS={ # task key -> (file, title, guideline, fields with options)
 'T0_calibration_E1':('E1 calibration (5 runs, everyone, day 0)','1_E1_labelling.md',{'binary_call':['correct','lost','reached_but_unused','exclude_partial','exclude_uncertain']}),
 'T1_E1_dev':('E1 dev labels (20 runs, two authors each)','1_E1_labelling.md',{'binary_call':['correct','lost','reached_but_unused','exclude_partial','exclude_uncertain']}),
 'T2_E1_anchor':('E1 anchor (30 questions x 3 runs, two authors each)','1_E1_labelling.md',{'binary_call':['correct','lost','reached_but_unused','exclude_partial','exclude_uncertain']}),
 'T3_E2_spotcheck_wave1':('E2 spot-check, wave 1 (12 items, one author each)','2_E2_spotcheck.md',{'defect_free':YN,'fact_in_every_sufficient_set':YN,'no_carrier_outside_target_agent':YN,'feasible_for_this_fault_type':YN})}
def jl(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def clean(trace,name):
    t=dict(trace);t['instance_id']=name;return t
def save(p,rows):
    p=Path(p)
    if p.exists() and any(r.get('annotator_id') or any(v not in ('',None) for v in r['answers'].values()) for r in jl(p)):raise ValueError('Refusing to overwrite entered answers: '+str(p))
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
def main():
    (F/'data').mkdir(parents=True,exist_ok=True);(F/'forms').mkdir(exist_ok=True)
    private=json.loads((P/'20261108_review8/packet_private_map.json').read_text());out={}
    # anchor: question numbers by SHA-free stable order of instance appearance
    a=jl(SRC/'E1_anchor.jsonl');order=[];by=defaultdict(list)
    for r in a:
        inst=private[r['item_id']]['instance_id']
        if inst not in order:order.append(inst)
        by[r['item_id']].append(r)
    runno={};
    for h,rs in by.items():runno[h]=None
    mods=['qwen235b','gpt4omini','gemma31b'];rows=[]
    for r in a:
        m=private[r['item_id']];q=order.index(m['instance_id'])+1;n=mods.index(m['model'])+1
        rows.append({'task':'T2_E1_anchor','item_id':r['item_id'],'display_name':f'Anchor Q{q:02d} run {n}','assigned_annotator':r['assigned_annotator'],'annotator_id':'','trace':clean(r['trace'],f'Anchor Q{q:02d} run {n}'),'answers':{k:'' for k in E1_FIELDS}})
    out['T2_E1_anchor']=rows
    d=jl(SRC/'E1_dev.jsonl');seen=[];rows=[]
    for r in d:
        if r['item_id'] not in seen:seen.append(r['item_id'])
    for r in d:rows.append({'task':'T1_E1_dev','item_id':r['item_id'],'display_name':f'Dev run {seen.index(r["item_id"])+1:02d}','assigned_annotator':r['assigned_annotator'],'annotator_id':'','trace':clean(r['trace'],f'Dev run {seen.index(r["item_id"])+1:02d}'),'answers':{k:'' for k in E1_FIELDS}})
    out['T1_E1_dev']=rows
    cal=jl(OLD/'E1/calibration_sheet.jsonl');rows=[]
    for n,r in enumerate(cal):
        for who in 'ABCD':rows.append({'task':'T0_calibration_E1','item_id':r['trace_hash'],'display_name':f'Calibration run {n+1}','assigned_annotator':who,'annotator_id':'','trace':clean(r['trace'],f'Calibration run {n+1}'),'answers':{k:'' for k in E1_FIELDS}})
    out['T0_calibration_E1']=rows
    s=jl(SRC/'E2_spotcheck_wave1.jsonl');rows=[]
    for n,r in enumerate(s):
        rows.append({'task':'T3_E2_spotcheck_wave1','item_id':r['item_id'],'display_name':f'Spot-check {n+1:02d}','spotcheck_fault_type':r['spotcheck_fault_type'],'target_agent_id':r['target_agent_id'],'assigned_annotator':r['assigned_annotator'],'annotator_id':'','trace':clean(r['trace'],f'Spot-check {n+1:02d}'),'answers':{k:'' for k in ['defect_free','target_fact_text','fact_in_every_sufficient_set','no_carrier_outside_target_agent','feasible_for_this_fault_type','uncertain_reason','source_citations','minutes_spent']}})
    out['T3_E2_spotcheck_wave1']=rows
    for k,rs in out.items():save(F/'data'/(k+'.jsonl'),rs)
    with (F/'data/assignments.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['task','item','authors'])
        for k,rs in out.items():
            g=defaultdict(list)
            for r in rs:g[r['display_name']].append(r['assigned_annotator'])
            for name,au in g.items():w.writerow([k,name,'+'.join(sorted(au))])
    guides={g.name:g.read_text() for g in (F/'guidelines').glob('*.md')}
    data={k:rs for k,rs in out.items()};cfg={k:{'title':v[0],'guideline':v[1],'options':v[2]} for k,v in TASKS.items()}
    VERSION=(F/'VERSION').read_text().strip();SHORT={'T0_calibration_E1':'E1calibration','T1_E1_dev':'E1dev','T2_E1_anchor':'E1anchor','T3_E2_spotcheck_wave1':'E2spotcheck1'}
    html=PAGE.replace('__VERSION__',json.dumps(VERSION)).replace('__SHORT__',json.dumps(SHORT)).replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')).replace('__CFG__',json.dumps(cfg)).replace('__GUIDES__',json.dumps(guides,ensure_ascii=False).replace('<','\\u003c'))
    (F/'forms/labelling_form.html').write_text(html)
    print({k:len(v) for k,v in out.items()})
PAGE='''<!doctype html><meta charset="utf-8"><title>Labelling form</title>
<style>body{font:16px system-ui;max-width:1100px;margin:1.5rem auto;padding:0 1rem}pre{white-space:pre-wrap;background:#f5f5f5;padding:.8rem;border-radius:6px}textarea{display:block;width:98%;min-height:60px;margin:.2rem 0 .8rem}select{margin:.2rem 0 .8rem;padding:.3rem}button,select#who,select#task{padding:.45rem;margin:.2rem}label{font-weight:600;display:block}h2{border-top:1px solid #ccc;padding-top:.8rem}.hint{color:#555;font-weight:400}.src{border-left:4px solid #bbb;padding-left:.7rem;margin:.4rem 0}.warn{background:#fff3cd;padding:.5rem;border-radius:6px}</style>
<h1>Labelling form (offline)</h1><p><b>Version: <span id="ver"></span></b></p>
<p class="warn">Works offline, no network. Pick your letter and the task, fill the boxes, press <b>Save my rows</b> (downloads a file) when done or to pause. Your typing is also kept in this browser automatically. Do not discuss an item with your partner until both of you have saved. "uncertain" is always a valid answer.</p>
<label>Author <select id="who"><option>A</option><option>B</option><option>C</option><option>D</option></select></label>
<label>Task <select id="task"></select></label>
<button id="prev">Previous</button><button id="next">Next</button><button id="save">Save my rows</button><span id="count"></span>
<details><summary>Guideline for this task (click to read)</summary><pre id="guide"></pre></details>
<div id="body"></div>
<script>
const VERSION=__VERSION__,SHORT=__SHORT__;
const data=__DATA__,cfg=__CFG__,guides=__GUIDES__;
const hints={critical_facts_json:'JSON list, e.g. [{"fact_id":"f1","text":"...","source_ids":["agent-0"]}]',sufficient_support_sets_json:'JSON list of lists, e.g. [["f1","f2"]]',carriers_json:'JSON list: fact_id, checkpoint pool|board, unit_ids, role sole|alternative|joint, fidelity faithful|partial|distorted|absent|uncertain',minutes_spent:'real minutes you spent on this item'};
const who=document.getElementById('who'),task=document.getElementById('task'),body=document.getElementById('body');let index=0,current=[];
for(const k of Object.keys(cfg)){const o=document.createElement('option');o.value=k;o.textContent=cfg[k].title;task.append(o)}
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function section(title,text){body.append(el('h2',title));body.append(el('pre',text))}
function byAgent(units){const g={};for(const u of units){(g[u.agent_id]=g[u.agent_id]||[]).push(u.unit_id+': '+u.text)}return Object.keys(g).sort((a,b)=>a-b).map(a=>'[agent-'+a+']\\n'+g[a].join('\\n')).join('\\n\\n')||'(none)'}
function renderTrace(t){section('Question',t.question);section('Gold answer',String(t.gold_answer));
 section('Source text held by each agent',t.source_contexts.map(c=>'[agent-'+c.agent_id+'] '+c.text).join('\\n\\n'));
 section('Gold supporting facts',t.source_supports.map(c=>'[agent-'+c.agent_id+'] '+c.text).join('\\n\\n'));
 section('Extraction = pool (what each agent pulled from its own source)',byAgent(t.checkpoints.extraction));
 if(JSON.stringify(t.checkpoints.transmission)!==JSON.stringify(t.checkpoints.board))section('Passed on (transmission; differs from the board)',byAgent(t.checkpoints.transmission));
 section('Board (what the final step saw)',t.checkpoints.board.map(u=>u.unit_id+' [agent-'+u.agent_id+']: '+u.text).join('\\n')||'(none)');
 section('System answer',t.answer_text||'(none)')}
function renderControl(c){section('Task',c.task_description);section('Source shard the text was picked from',c.source_shard);section('Added text ('+c.added_pieces+' pieces)',c.added_text.map((x,i)=>(i+1)+'. '+x).join('\\n'));section('Needed fact (belongs to a different agent)',c.needed_fact_from_other_agent)}
document.getElementById('ver').textContent=VERSION;
function key(){return 'lab_'+VERSION+'_'+who.value+'_'+task.value}
function load(){current=data[task.value].filter(r=>r.assigned_annotator===who.value);const saved=JSON.parse(localStorage.getItem(key())||'{}');for(const r of current){if(saved[r.item_id]){Object.assign(r.answers,saved[r.item_id]);r.annotator_id=who.value}}}
function store(){const s={};for(const r of current)s[r.item_id]=r.answers;localStorage.setItem(key(),JSON.stringify(s))}
function show(){body.replaceChildren();document.getElementById('guide').textContent=guides[cfg[task.value].guideline]||'';index=Math.max(0,Math.min(index,current.length-1));document.getElementById('count').textContent=current.length?'  Item '+(index+1)+' of '+current.length:'  No items for this author in this task.';const r=current[index];if(!r)return;
 body.append(el('h2',r.display_name));if(r.spotcheck_fault_type)body.append(el('p','Fault type under check: '+r.spotcheck_fault_type+(r.target_agent_id!==null&&r.target_agent_id!==undefined?'  |  target agent: '+r.target_agent_id:''),'warn'));
 if(r.trace)renderTrace(r.trace);
 body.append(el('h2','Your answers'));const opts=cfg[task.value].options;
 for(const k of Object.keys(r.answers)){const l=el('label',k);if(hints[k])l.append(el('span',' - '+hints[k],'hint'));body.append(l);let f;
  if(opts[k]){f=document.createElement('select');for(const v of ['',...opts[k]]){const o=document.createElement('option');o.value=v;o.textContent=v||'(choose)';f.append(o)}}else{f=document.createElement('textarea')}
  f.value=r.answers[k];const w=el('div','','warn');w.style.display='none';f.oninput=f.onchange=()=>{r.answers[k]=f.value;r.annotator_id=who.value;store();if(k.endsWith('_json')&&f.value.trim()){try{JSON.parse(f.value);w.style.display='none'}catch(e){w.textContent='This is not valid JSON yet: '+e.message;w.style.display='block'}}else{w.style.display='none'}};body.append(f);body.append(w)}}
function reset(){index=0;load();show()}
who.onchange=task.onchange=reset;document.getElementById('prev').onclick=()=>{index--;show()};document.getElementById('next').onclick=()=>{index++;show()};
document.getElementById('save').onclick=()=>{const blob=new Blob([JSON.stringify(current)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=SHORT[task.value]+'_'+who.value+'_'+VERSION+'.json';a.click();URL.revokeObjectURL(a.href)};
reset();
</script>'''
if __name__=='__main__':main()
