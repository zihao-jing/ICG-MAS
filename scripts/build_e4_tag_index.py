"""Write an explicit (a)-(f) tag index for every diagnosed trace.

Reads cases.json (regenerated scores stay untouched) and verdicts.json, and
writes rebuttal/diagnosis/tags.md. No model call.

    ./run.sh python -m scripts.build_e4_tag_index
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/diagnosis/tags.md'
CASES = ROOT / 'rebuttal/diagnosis/cases.json'
VERDICTS = ROOT / 'rebuttal/diagnosis/verdicts.json'

CLASSES = {'a': 'fact not missing', 'b': 'present but unused',
           'c': 'scorer rejected a right answer', 'd': 'model already knew it',
           'e': 'delivery not as intended', 'f': 'other', 'ok': 'correct'}


def short(s, n=150):
    s = ' '.join((s or '').split())
    return s if len(s) <= n else s[:n - 3] + '...'


def main():
    cases = json.loads(CASES.read_text())
    ver = json.loads(VERDICTS.read_text())
    sections = [
        ('Missing-fact repair', 'extraction', cases['extraction'], 'extraction'),
        ('Direct insertion', 'insertion', cases['extraction'], 'insertion'),
        ('Selection cohort', 'selection', cases['selection'], 'selection'),
        ('Distortion repair', 'distortion', cases['distortion'], 'distortion'),
    ]
    lines = ['# Case tag index\n',
             'Every case is tagged (a)-(f), or `correct`. The tag is the `class` '
             'field in `verdicts.json`; this file only indexes it for review.\n']
    counts = {}
    for title, prefix, rows, _ in sections:
        lines.append(f'## {title}\n')
        lines.append('| case | model / trace | tag | cause |')
        lines.append('| --- | --- | --- | --- |')
        counts[title] = {}
        for r in rows:
            key = prefix + ':' + r['trace_id']
            v = ver.get(key)
            if not v:
                lines.append(f"| {r['instance_id']} | {r['model']} | _missing_ | |")
                continue
            code = v['class']
            counts[title][code] = counts[title].get(code, 0) + 1
            model = r['model'].split('/')[-1] if '/' in r.get('model', '') else r.get('model', '')
            lines.append(f"| {r['instance_id']} | {model} | ({code}) {CLASSES[code]} | "
                         f"{short(v['cause'])} |")
        lines.append('')
    lines.append('## Counts\n')
    lines.append('| experiment | a | b | c | d | e | f | correct | total |')
    lines.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for title in counts:
        c = counts[title]
        lines.append(f"| {title} | " + ' | '.join(str(c.get(k, 0)) for k in 'abcdef')
                     + f" | {c.get('ok', 0)} | {sum(c.values())} |")
    OUT.write_text('\n'.join(lines) + '\n')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()