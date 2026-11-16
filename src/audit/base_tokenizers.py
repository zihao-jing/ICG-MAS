"""Exact base-model tokenization of added evidence text (no chat template/BOS)."""
from functools import lru_cache
from pathlib import Path
import hashlib,json
ROOT=Path('rebuttal/pilots/20261108_preflight/tokenizers')
@lru_cache(None)
def tokenizer(model):
 if model=='openai/gpt-4o-mini':
  import tiktoken
  return tiktoken.encoding_for_model('gpt-4o-mini')
 from tokenizers import Tokenizer
 names={'qwen/qwen3-235b-a22b-2507':'Qwen3-235B-A22B-Instruct-2507','google/gemma-4-31b-it':'gemma-4-31B-it'}
 if model not in names:raise ValueError('Base tokenizer required, not Gemini')
 return Tokenizer.from_file(str(ROOT/names[model]/'tokenizer.json'))
def count_added_tokens(model,text):
 t=tokenizer(model)
 if model=='openai/gpt-4o-mini':return len(t.encode(text,disallowed_special=()))
 return len(t.encode(text,add_special_tokens=False).ids)
def added_token_count(model,units):
 return sum(count_added_tokens(model,u['text']) for u in units)
def volume_match(model,repair_units,control_units):
 a=added_token_count(model,repair_units);b=added_token_count(model,control_units)
 return {'repair_tokens':a,'control_tokens':b,'matched':len(repair_units)==len(control_units) and (a==b==0 or a>0 and abs(a-b)/a<=.10),
         'method':'exact base tokenizer; each added unit encoded separately; no BOS/chat tokens'}
