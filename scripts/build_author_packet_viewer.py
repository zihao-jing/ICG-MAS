"""Offline author worksheet viewer; embeds only the tested blind exports."""
import json
from pathlib import Path
O=Path('rebuttal/annotation/author_packet_20261108')
def main():
 TASKS=['E1_anchor','E1_dev','E2_spotcheck_wave1']  # the files authors work on; other jsonl files are judge inputs
 data={name:[json.loads(x) for x in (O/(name+'.jsonl')).read_text().splitlines()] for name in TASKS}
 html='''<!doctype html><meta charset="utf-8"><title>Author packet</title><style>body{font:16px system-ui;max-width:1050px;margin:2rem auto}pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}textarea{display:block;width:96%;min-height:55px;margin-bottom:1rem}button,select{padding:.5rem;margin:.3rem}label{font-weight:600}h2{border-top:1px solid #ccc;padding-top:1rem}</style>
<h1>Author packet</h1><p>Offline; no network requests. Use your assigned rows, then download your completed file. Read GUIDE.md first. Uncertain is a valid response. This viewer does not determine eligibility.</p>
<label>Author <select id="who"><option>A</option><option>B</option><option>C</option><option>D</option></select></label><label>Task <select id="task"><option>E1_anchor</option><option>E1_dev</option><option>E2_spotcheck_wave1</option></select></label><button id="prev">Previous</button><button id="next">Next</button><button id="save">Download my rows</button><p id="count"></p><div id="body"></div><script>
const data=DATA; let index=0, current=[];const who=document.getElementById('who'),task=document.getElementById('task'),body=document.getElementById('body');
function element(tag,text){let e=document.createElement(tag);e.textContent=text;return e}
function show(){current=data[task.value].filter(r=>r.assigned_annotator===who.value);index=Math.max(0,Math.min(index,current.length-1));body.replaceChildren();document.getElementById('count').textContent=`Item ${index+1}/${current.length}`;let r=current[index];if(!r)return;body.append(element('p','Item '+r.item_id));body.append(element('h2','Raw trace'));body.append(element('pre',JSON.stringify(r.trace,null,2)));if(r.spotcheck_fault_type)body.append(element('p','Fault type under check: '+r.spotcheck_fault_type+(r.target_agent_id!==null&&r.target_agent_id!==undefined?'; target agent: '+r.target_agent_id:'')));body.append(element('h2','Your independent assessment'));for(let key of Object.keys(r.answers)){body.append(element('label',key));let t=element('textarea','');t.value=r.answers[key];t.oninput=()=>{r.answers[key]=t.value;r.annotator_id=who.value};body.append(t)}}
who.onchange=task.onchange=()=>{index=0;show()};document.getElementById('prev').onclick=()=>{index--;show()};document.getElementById('next').onclick=()=>{index++;show()};document.getElementById('save').onclick=()=>{let blob=new Blob([current.map(r=>JSON.stringify(r)).join('\\n')+'\\n'],{type:'application/x-ndjson'});let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=task.value+'_'+who.value+'.jsonl';a.click();URL.revokeObjectURL(a.href)};show();</script>'''.replace('DATA',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
 (O/'review.html').write_text(html)
if __name__=='__main__':main()
