"""Execute pinned official prompt builders; unlicensed source stays in the gitignored rebuttal/external/ folder."""
import ast,contextlib,hashlib,importlib.util,io,json,re,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
import yaml
from src.audit.pilot_common import render_trace,digest
CACHE=Path(__file__).resolve().parents[2]/'rebuttal'/'external'

def verify_external():
    """Problems found when checking rebuttal/external/ against MANIFEST.json (empty list = fine)."""
    manifest=CACHE/'MANIFEST.json'
    if not manifest.exists():return [f'{manifest} is missing']
    problems=[]
    for name,entry in json.loads(manifest.read_text())['files'].items():
        f=CACHE/name
        if not f.exists():problems.append(f'missing {name}')
        elif hashlib.sha256(f.read_bytes()).hexdigest()!=entry['sha256']:problems.append(f'hash mismatch {name}')
    return problems

def require_external():
    """Fail loudly (never skip) when the pinned external files are absent or altered."""
    problems=verify_external()
    if problems:
        raise RuntimeError('Pinned external files in rebuttal/external/ are not usable ('+'; '.join(problems[:5])+'). Run: python -m scripts.fetch_external')

def external_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod

def ww(ledger,key,model,history,question,gold=None,method='all_at_once',temperature=0,is_handcrafted=False):
    require_external()
    mod=external_module(CACHE/'utils.py','official_ww_utils')
    counter=[0];raw=[]
    class Bridge:
        def create(self,**kwargs):
            idx=counter[0];counter[0]+=1
            text=ledger.call(key+f'/step-{idx}',model,kwargs['messages'],max_tokens=kwargs.get('max_tokens',4096),temperature=temperature)
            raw.append(text)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=Bridge()))
    # Invoke the actual release control flow. Do not rewrite its prompt or stopping condition.
    with tempfile.TemporaryDirectory(prefix='ww-eval-') as directory:
        Path(directory,'1.json').write_text(json.dumps({'history':history,'question':question,'ground_truth':gold or ''}))
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(io.StringIO()):
            getattr(mod,method)(client,directory,is_handcrafted,model,4096)
    return {'raw':raw,'stdout':output.getvalue(),'calls':counter[0],'native_step_origin':0}

def r1_prompt(trace=None,release=None,gold=False):
    require_external()
    if str(CACHE) not in sys.path:sys.path.insert(0,str(CACHE))
    from whowhen_eval.prompts import all_at_once,load_taxonomy,user_msg
    from whowhen_eval.render.base import RenderResult,TranscriptBlock
    if release is not None:
        from whowhen_eval.render import get_renderer
        release=dict(release)
        for k in ('task','trajectory','ground_truth','extras'):
            if isinstance(release.get(k),str):release[k]=json.loads(release[k])
        rr=get_renderer(release['framework'])(release);problem=release['task']['query']
        steps=[{'step':coord,'agent':'agent','stage':'external'} for coord,_ in rr.step_index]
    else:
        steps=render_trace(trace)
        rr=RenderResult(blocks=[TranscriptBlock(str(s['step']),f"Step {s['step']} | Agent: {s['agent']}\n{s['text']}") for s in steps],
            step_format_hint='step N (1-indexed)',step_index=[(str(s['step']),(s['step'],)) for s in steps],trajectory_length=len(steps))
        problem=trace['question']
        if gold:problem+='\nGround-truth answer: '+trace['gold_answer']
    taxonomy=load_taxonomy(CACHE)
    return [user_msg(all_at_once(rr,problem=problem,taxonomy=taxonomy))],steps

def parse_r1(text,steps):
    require_external()
    if str(CACHE) not in sys.path:sys.path.insert(0,str(CACHE))
    from whowhen_eval.parse import parse_all_at_once,_FIELD_RE
    tax=yaml.safe_load((CACHE/'taxonomy.yaml').read_text())
    p=parse_all_at_once(text,tax.keys())
    fields={m.group('key').title():m.group('val').strip() for m in _FIELD_RE.finditer(text)}
    field=fields.get('Error Mode','').replace('**','').strip()
    # Layout leniency only: optional colon/dash/parentheses around the official name.
    m=re.fullmatch(r'([A-Z]+\.\d+)\s*(?:[:\-–]\s*|\(\s*)?(.+?)\)?\s*',field)
    pair=False
    if m and m.group(1) in tax:
        name=m.group(2).strip().rstrip(')').strip()
        pair=re.sub(r'\s+',' ',name).casefold()==tax[m.group(1)]['name'].casefold()
    coords={str(s['step']) for s in steps};agents={s['agent'] for s in steps}
    coordinate=re.sub(r'^Step\s+', '',p.step_coord or '',flags=re.I).strip()
    return {'agent':p.agent_name,'step':p.step_coord,'mode':p.error_mode,
        'parses':bool(p.agent_name and p.step_coord and p.error_mode),'valid_mode_code':p.error_mode in tax,
        'valid_mode_pair':pair,'step_in_trace':coordinate in coords,'canonical_step':coordinate,'agent_in_trace':p.agent_name in agents,
        'warnings':p.parse_warnings}

def mast_prompt(trace_text):
    require_external()
    notebook=json.loads((CACHE/'llm_judge_pipeline.ipynb').read_text())
    source=''.join(notebook['cells'][0]['source']);tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='openai_evaluator')
    namespace={'definitions':(CACHE/'definitions.txt').read_text(),'chat_completion_request_openai':lambda prompt:prompt}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(CACHE/'llm_judge_pipeline.ipynb'),'exec'),namespace)
    # Exact official notebook prompt and supplied examples, no instruction edits.
    return [{'role':'user','content':namespace['openai_evaluator'](trace_text,examples=(CACHE/'examples.txt').read_text())}]

def parse_mast(raw):
    modes={}
    for code in ['1.1','1.2','1.3','1.4','1.5','2.1','2.2','2.3','2.4','2.5','2.6','3.1','3.2','3.3']:
        m=re.search(r'(?m)^\s*'+re.escape(code)+r'\b[^\n]*?\b(yes|no)\b',raw,re.I)
        modes[code]=m.group(1).lower()=='yes' if m else None
    # Notebook order differs from definitions; preserve raw, map by named meaning.
    modes['3.2'],modes['3.3']=modes['3.3'],modes['3.2']
    return {'modes_definition_codes':modes,'parse_ok':all(v is not None for v in modes.values()),'missing_defaulted_to_no':False}

def run_baselines(ledger,key,trace,backbones,step_by_step=False,gold=False):
    steps=render_trace(trace);history=[{'name':s['agent'],'content':s['text']} for s in steps]
    text='\n'.join(f"Step {s['step']} | Agent {s['agent']}: {s['text']}" for s in steps)
    out=[]
    for model in backbones:
        for method in ['ww_all','r1','mast']+(['ww_step'] if step_by_step else []):
            k=f'{key}/{model}/{method}/gold-{gold}'
            if method.startswith('ww'):
                result=ww(ledger,k,model,history,trace['question'],trace['gold_answer'] if gold else None,
                    method='step_by_step' if method=='ww_step' else 'all_at_once')
                out.append({'method':method,'backbone':model,'gold':gold,**result})
            else:
                if method=='r1':msgs,_=r1_prompt(trace=trace,gold=gold)
                else:msgs=mast_prompt(('Question: '+trace['question']+'\n'+('Gold answer: '+trace['gold_answer']+'\n' if gold else '')+text))
                raw=ledger.call(k,model,msgs,max_tokens=4096)
                parsed=parse_r1(raw,steps) if method=='r1' else parse_mast(raw)
                out.append({'method':method,'backbone':model,'gold':gold,'raw':raw,'parsed':parsed})
    return out

def score_r1_released(raw, ground_truth, framework='relay'):
    require_external()
    """Actual pinned per-axis scorer; names never gate a recognised mode code."""
    if str(CACHE) not in sys.path:sys.path.insert(0,str(CACHE))
    from dataclasses import asdict
    from whowhen_eval.parse import parse_all_at_once
    from whowhen_eval.score import score
    tax=yaml.safe_load((CACHE/'taxonomy.yaml').read_text())
    parsed=parse_all_at_once(raw,tax.keys())
    return score(asdict(parsed),ground_truth,framework)
