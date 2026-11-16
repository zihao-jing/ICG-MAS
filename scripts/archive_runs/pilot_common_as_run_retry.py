"""Pilot-only provenance, fail-closed call ledger, rendering and statistics."""
from __future__ import annotations
import hashlib,json,os,random,time,fcntl
from collections import Counter,defaultdict
from pathlib import Path

MODELS=('qwen/qwen3-235b-a22b-2507','openai/gpt-4o-mini','google/gemma-4-31b-it')
STRONG='google/gemini-3.6-flash'

def digest(value):
    data=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    return hashlib.sha256(data).hexdigest()

def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]

def freeze(path,value):
    """Idempotent immutable artifact; changed inputs require a new preregistration."""
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
    if p.exists():
        if p.read_text()!=text:raise ValueError(f'Frozen artifact differs: {p}')
    else:
        with p.open('x') as f:f.write(text)

def ranked(values,seed=42):
    return sorted(values,key=lambda x:(digest([seed,x]),str(x)))

def kappa(a,b):
    if not a or len(a)!=len(b):raise ValueError('Nonempty equal-length paired labels required')
    ca,cb=Counter(a),Counter(b);n=len(a)
    po=sum(x==y for x,y in zip(a,b))/n
    pe=sum(ca[x]*cb[x] for x in set(a)|set(b))/n**2
    return None if pe==1 else (po-pe)/(1-pe)

def cluster_bootstrap(rows,statistic,draws=2000,seed=42):
    """Resample instance IDs jointly across models; preserve all rows per draw."""
    groups=defaultdict(list)
    for row in rows:groups[row['instance_id']].append(row)
    if not groups:raise ValueError('No clusters')
    keys=sorted(groups);rng=random.Random(seed);values=[]
    for _ in range(draws):
        value=statistic([r for k in rng.choices(keys,k=len(keys)) for r in groups[k]])
        if value is not None:values.append(value)
    values.sort()
    return {'estimate':statistic(rows),'lo':values[int(.025*(len(values)-1))] if values else None,
            'hi':values[int(.975*(len(values)-1))] if values else None,'valid_draws':len(values),'draws':draws,'clusters':len(keys)}

def render_trace(trace,include_answer=True):
    """Stage coordinates are fixed; raw outputs only, never audit or baseline-attributor output."""
    agents=sorted({u['agent_id'] for u in trace['source_contexts']})
    steps=[]
    for checkpoint,stage in [('extraction','extraction'),('transmission','transmission')]:
        for agent in agents:
            texts=[u['text'] for u in trace['checkpoints'][checkpoint] if u['agent_id']==agent]
            steps.append({'step':len(steps)+1,'agent':f'agent-{agent}','stage':stage,'text':'\n'.join(texts) or '(empty)'})
    steps.append({'step':len(steps)+1,'agent':'aggregator','stage':'aggregation','text':'Board:\n'+'\n'.join(u['text'] for u in trace['checkpoints']['board'])})
    if include_answer:steps.append({'step':len(steps)+1,'agent':'aggregator','stage':'aggregation','text':trace['answer_text']})
    return steps

def blind_view(trace):
    # Explicit recursive projection: unknown nested fields cannot leak through.
    units=lambda rows:[{k:r[k] for k in ('unit_id','support_id','context_id','agent_id','text') if k in r} for r in rows]
    return {'instance_id':trace['instance_id'],'question':trace['question'],'gold_answer':trace['gold_answer'],
            'source_contexts':units(trace['source_contexts']),'source_supports':units(trace['source_supports']),
            'checkpoints':{k:units(trace['checkpoints'][k]) for k in ('extraction','transmission','board')},
            'answer_text':trace.get('answer_text','')}

class CallLedger:
    """Append intent before dispatch; uncertain calls block resume to avoid double billing.

    One SDK attempt per ledger record; no hidden retries. A process-wide lock prevents
    duplicate workers. --max-calls bounds total dispatches across all resumptions.
    """
    def __init__(self,output,config,prereg,max_calls,transport=None,seal_content=False,seal_path=None):
        self.output=Path(output).resolve()
        roots=[Path('rebuttal/pilots').resolve(),Path('rebuttal/results/batch1').resolve()]
        if not any(r in self.output.parents for r in roots):raise ValueError('Output must be under rebuttal/pilots/ or rebuttal/results/batch1/')
        if not Path(prereg).is_file():raise ValueError('Missing preregistration')
        if max_calls is None or max_calls<0:raise ValueError('--max-calls is mandatory')
        self.output.mkdir(parents=True,exist_ok=True)
        self.lock=(self.output/'worker.lock').open('a')
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.cfg=digest(config);self.pre=digest(Path(prereg).read_bytes());self.cap=max_calls;self.transport=transport
        # Sealed mode: responses go to a separate sealed file; calls.jsonl keeps metadata only (hash, length, tokens, cost), so status checks never need the responses.
        self.seal_content=seal_content;self.seal_path=Path(seal_path) if seal_path else self.output/'sealed_responses.jsonl'
        freeze(self.output/'run_identity.json',{'config_sha256':self.cfg,'prereg_sha256':self.pre})
        self.path=self.output/'calls.jsonl'
        self.rows=read_jsonl(self.path) if self.path.exists() else []
        self.started={r['call_id'] for r in self.rows if r['event']=='intent'}
        self.done={r['call_id']:r for r in self.rows if r['event']=='result'}
        if self.seal_content and self.seal_path.exists():
            sealed={x['call_id']:x['content'] for x in read_jsonl(self.seal_path)}
            for cid,row in self.done.items():row['content']=sealed.get(cid,row.get('content',''))
        if self.started-self.done.keys():raise RuntimeError('Unresolved intent: inspect billing before manual reconciliation; no automatic retry')
        prices=json.loads(Path(config['pricing']).read_text())['models']
        self.prices={r['id']:r['pricing'] for r in prices}
    def append(self,row):
        with self.path.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    def _record(self,result):
        if not self.seal_content:self.append(result);return
        content=result.get('content') or ''
        if content:
            self.seal_path.parent.mkdir(parents=True,exist_ok=True)
            with self.seal_path.open('a') as f:f.write(json.dumps({'call_id':result['call_id'],'content':content},ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        self.append(dict(result,content='',content_sha256=hashlib.sha256(content.encode()).hexdigest(),content_chars=len(content)))
    def call(self,key,model,messages,max_tokens=2048,temperature=0,response_format=None):
        if model not in (*MODELS,STRONG):raise ValueError('Off-paper model')
        ph=digest(messages);cid=digest([self.cfg,key,model,ph,max_tokens,temperature] + ([response_format] if response_format else []))
        if cid in self.done:
            r=self.done[cid]
            if not r['success']:raise RuntimeError('Previous call failed; explicit review required, not retried')
            return r['content']
        if len(self.started)>=self.cap:raise RuntimeError('Call cap reached')
        info={'call_id':cid,'key':key,'model_id':model,'prompt_sha256':ph,'config_sha256':self.cfg,
              'prereg_sha256':self.pre,'temperature':temperature,'max_tokens':max_tokens,'seed':42,
              'response_format':response_format}
        self.append(dict(info,event='intent',time=time.time(),tokens=None,cost_usd=None));self.started.add(cid)
        t=time.monotonic()
        try:
            if self.transport is None:
                from utility.apis.openrouter_api import _get_client
                client=_get_client().with_options(max_retries=0)
                extra={'response_format':response_format} if response_format else {}
                raw=client.chat.completions.create(model=model,messages=messages,temperature=temperature,
                    max_tokens=max_tokens,seed=42,**extra).model_dump()
            else:raw=self.transport(model=model,messages=messages,max_tokens=max_tokens,temperature=temperature,seed=42)
            usage=raw.get('usage') or {};content=raw['choices'][0]['message'].get('content') or ''
            rate=self.prices[model]
            est=usage.get('prompt_tokens',0)*float(rate['prompt'])+usage.get('completion_tokens',0)*float(rate['completion'])
            billed=usage.get('cost')
            result=dict(info,event='result',time=time.time(),seconds=time.monotonic()-t,success=True,content=content,
                tokens=usage,cost_usd=billed if billed is not None else est,cost_kind='provider' if billed is not None else 'estimated_from_usage',
                finish_reason=raw['choices'][0].get('finish_reason'),resolved_model=raw.get('model'),provider=raw.get('provider'))
        except Exception as exc:
            result=dict(info,event='result',time=time.time(),seconds=time.monotonic()-t,success=False,content='',
                tokens=None,cost_usd=None,cost_kind='unknown',error=type(exc).__name__+': '+str(exc))
            self.append(result);self.done[cid]=result
            raise
        self._record(result);self.done[cid]=result
        return content
    def close(self):
        fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()
