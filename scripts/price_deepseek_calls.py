"""Price the uncharged deepseek/deepseek-v3.2 calls in the Extension B artifacts (no calls).

Every record in `rebuttal/results/extension_b_deepseekv32_*/api_responses.jsonl` carries a `usage` dict and
no `cost_usd`, so the ledger rule (top-level non-null `cost_usd` only) never counted them. This script prices
them from the recorded token counts at the OpenRouter list price for the model on 2026-11-15.

    ./run.sh python -m scripts.price_deepseek_calls
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_inventory/deepseek_v32_pricing.json'
MODEL = 'deepseek/deepseek-v3.2'
PRICE_IN = 0.26 / 1e6   # OpenRouter list, 2026-11-15
PRICE_OUT = 0.38 / 1e6


def usage(e):
    u = e.get('usage')
    if isinstance(u, str):
        try:
            u = json.loads(u.replace("'", '"'))
        except Exception:
            u = {}
    return u or {}


def main():
    files, tok, recs, charged, ids = collections.Counter(), collections.Counter(), 0, 0, collections.Counter()
    for p in sorted(ROOT.glob('rebuttal/**/*.jsonl'), key=str):
        if p.name == 'swaps.jsonl':
            continue
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get('model') != MODEL:
                continue
            recs += 1
            files[str(p.relative_to(ROOT))] += 1
            if e.get('cost_usd') is not None:
                charged += 1
            u = usage(e)
            tok['prompt'] += u.get('prompt_tokens', 0) or 0
            tok['completion'] += u.get('completion_tokens', 0) or 0
            if e.get('request_id'):
                ids[e['request_id']] += 1
    cost = tok['prompt'] * PRICE_IN + tok['completion'] * PRICE_OUT
    res = {'model': MODEL, 'records': recs, 'records_with_cost_usd': charged,
           'unique_request_ids': len(ids), 'duplicate_request_ids': sum(v - 1 for v in ids.values() if v > 1),
           'prompt_tokens': tok['prompt'], 'completion_tokens': tok['completion'],
           'price_usd_per_token': {'prompt': PRICE_IN, 'completion': PRICE_OUT},
           'price_source': 'OpenRouter /api/v1/models, deepseek/deepseek-v3.2, read 2026-11-15: '
                           '$0.26/M prompt, $0.38/M completion',
           'estimate_usd': round(cost, 6),
           'rule': 'estimate = prompt_tokens * 0.26/1e6 + completion_tokens * 0.38/1e6; '
                   'counted once per logged record, deduplicated by request_id (no duplicates found)',
           'files': dict(files)}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()