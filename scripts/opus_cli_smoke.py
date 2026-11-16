"""Opus CLI smoke test: three judge calls through `claude -p` instead of the OpenRouter API.

The user's step: empty temp cwd, tools disabled, the frozen prompt as the full system prompt
(`--system-prompt-file` plus `--exclude-dynamic-system-prompt-sections`), JSON output, Opus 5.5
explicit. Checks that the result parses to the same JSON shape the API path produced, with no CLI
chatter, and logs tokens, cost and transport for each call.

    ./run.sh python -m scripts.opus_cli_smoke --run
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from src.audit.judge_render import trace_text

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'rebuttal/pilots/20261114_part_b_k1/manifest.json'
PROMPT = ROOT / 'rebuttal/judge/E2-judge-v2.json'
OUT = ROOT / 'rebuttal/pilots/20261115_opus_cli_smoke'
CALLS = OUT / 'calls.jsonl'
MODEL = 'claude-opus-5-5'
PRICE = (4.0 / 1e6, 20.0 / 1e6)
TOOLS_OFF = ('Bash Edit Write Read Glob Grep WebFetch WebSearch Task NotebookEdit TodoWrite '
             'Agent Skill Workflow Monitor')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    man = json.loads(MANIFEST.read_text())
    items = [x for x in man['items'] if x['dataset'] == 'musique'][:3]
    prof = json.loads(PROMPT.read_text())
    tmp = Path(tempfile.mkdtemp(prefix='opus_cli_smoke_'))
    with CALLS.open('a') as log:
        for it in items:
            sysmsg = prof['system']
            user = prof['user_template'].format(trace=trace_text(it['trace']))
            sp = tmp / 'system.txt'
            sp.write_text(sysmsg)
            cmd = ['claude', '-p', user, '--output-format', 'json', '--model', MODEL,
                   '--system-prompt-file', str(sp), '--exclude-dynamic-system-prompt-sections',
                   '--disallowedTools', TOOLS_OFF]
            log.write(json.dumps({'event': 'intent', 'key': it['trace_id'], 'model': MODEL,
                                  'prompt': str(PROMPT.relative_to(ROOT)),
                                  'system_sha256': sha(sysmsg), 'user_sha256': sha(user),
                                  'transport': 'claude-cli', 'cwd': str(tmp),
                                  'cmd': cmd[:4] + ['<user>'] + cmd[5:]}) + '\n')
            log.flush()
            p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=600)
            rec = {'event': 'result', 'key': it['trace_id'], 'model': MODEL,
                   'prompt': str(PROMPT.relative_to(ROOT)),
                   'transport': 'claude-cli', 'returncode': p.returncode,
                   'stderr': p.stderr[-2000:]}
            try:
                obj = json.loads(p.stdout)
                rec['cli_keys'] = sorted(obj)
                rec['result_text'] = obj.get('result')
                rec['usage'] = obj.get('usage')
                rec['total_cost_usd'] = obj.get('total_cost_usd')
                u = obj.get('usage') or {}
                rec['cost_usd'] = round((u.get('input_tokens', 0) * PRICE[0]
                                         + u.get('output_tokens', 0) * PRICE[1]), 8)
                try:
                    lab = json.loads(obj.get('result') or '')
                    rec['parsed_ok'] = isinstance(lab, dict) and 'defects' in lab and 'class' in lab
                    rec['parsed_keys'] = sorted(lab) if isinstance(lab, dict) else None
                    rec['class'] = lab.get('class') if isinstance(lab, dict) else None
                except json.JSONDecodeError:
                    rec['parsed_ok'] = False
                    rec['chatter'] = (obj.get('result') or '')[:300]
            except json.JSONDecodeError:
                rec['parsed_ok'] = False
                rec['stdout_head'] = p.stdout[:300]
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            print(json.dumps({k: rec.get(k) for k in ('key', 'returncode', 'parsed_ok', 'class',
                                                      'usage', 'total_cost_usd')}, ensure_ascii=False),
                  flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    if ap.parse_args().run:
        main()