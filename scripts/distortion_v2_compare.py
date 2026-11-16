"""Like-for-like v1 vs v2 four-model rates on the pairs labelled under both prompts (no calls)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.distortion_rescore_run import cp, parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT / 'rebuttal/pilots/20261115_distortion_rescore'
NEW = ROOT / 'rebuttal/pilots/20261115_distortion_v2_recheck'


def labels(path, tag='labh'):
    out = {}
    if not path.exists():
        return out
    for l in path.read_text().splitlines():
        if not l.strip():
            continue
        e = json.loads(l)
        if e.get('event') != 'result' or not e.get('success') or not e['key'].startswith(tag + '/'):
            continue
        p = parse(e.get('content'))
        if p is not None:
            out[e['key'].split('/')[1].rsplit('/attempt-', 1)[0]] = p['fidelity']
    return out


def rates(pairs, lab, model):
    m = {'covered': 0, 'faithful': 0, 'partial': 0, 'distorted': 0, 'absent': 0}
    for p in pairs:
        f = lab.get(p['pair_id'])
        if f is None:
            continue
        m[f] += 1
        if f != 'absent':
            m['covered'] += 1
    m['strict'] = m['distorted'] / m['covered'] if m['covered'] else None
    m['strict_ci'] = list(cp(m['distorted'], m['covered'])) if m['covered'] else None
    m['broad'] = (m['distorted'] + m['partial']) / m['covered'] if m['covered'] else None
    m['broad_ci'] = list(cp(m['distorted'] + m['partial'], m['covered'])) if m['covered'] else None
    return m


def main():
    pairs = json.loads((NEW / 'population_pairs.json').read_text())
    v1 = labels(OLD / 'calls.jsonl')
    v2 = labels(NEW / 'calls.jsonl')
    common = [p for p in pairs if p['pair_id'] in v1 and p['pair_id'] in v2]
    out = {'pairs': len(pairs), 'labelled_v1': len(v1), 'labelled_v2': len(v2),
           'common': len(common), 'unlabelled_v2': sorted(
               p['pair_id'] for p in pairs if p['pair_id'] not in v2),
           'by_model': {}}
    for model in ('geminifl', 'gpt4omini', 'deepseekr1_32b', 'gemma31b'):
        sub = [p for p in common if p['model'] == model]
        out['by_model'][model] = {'n': len(sub), 'v1': rates(sub, v1, model),
                                  'v2': rates(sub, v2, model)}
    (NEW / 'comparison.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('pairs', 'labelled_v1', 'labelled_v2', 'common')}, indent=1))
    for model, x in out['by_model'].items():
        a, b = x['v1'], x['v2']
        print('%-16s n=%3d v1 strict %5.1f%% [%4.1f, %4.1f]  v2 strict %5.1f%% [%4.1f, %4.1f]  '
              'v1 broad %5.1f%%  v2 broad %5.1f%%'
              % (model, x['n'], 100 * a['strict'], 100 * a['strict_ci'][0], 100 * a['strict_ci'][1],
                 100 * b['strict'], 100 * b['strict_ci'][0], 100 * b['strict_ci'][1],
                 100 * a['broad'], 100 * b['broad']))


if __name__ == '__main__':
    main()