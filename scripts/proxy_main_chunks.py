"""Run the 608-trace proxy pipeline in chunks of at most $1, total cap $5.5.

Stops when a chunk overruns its $1 budget or the total cap is reached. Every call is
logged by `proxy_support_run`; the pipeline resumes from `pipeline.jsonl`.
"""
import argparse
import json

import scripts.proxy_support_run as R

DEFAULT_DIR = 'rebuttal/pilots/20261115_proxy_support_main'
TOTAL_CAP = 5.5
CHUNK = 1.0


def main():
    global TOTAL_CAP, CHUNK
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--total-cap', type=float, default=TOTAL_CAP)
    ap.add_argument('--chunk', type=float, default=CHUNK)
    a = ap.parse_args()
    TOTAL_CAP, CHUNK = a.total_cap, a.chunk
    R.configure(a.dir)
    DIR = a.dir
    # a run may freeze a different facts prompt (the granularity fix); the manifest holds it
    try:
        m = json.load(open(f'{DIR}/build_manifest.json'))
        if m.get('facts_prompt'):
            R.FACTS_PROMPT = R.ROOT / m['facts_prompt']
            print(json.dumps({'facts_prompt': m['facts_prompt'],
                              'sha': R.file_sha(R.FACTS_PROMPT)[:12]}), flush=True)
    except FileNotFoundError:
        pass
    i = 0
    while True:
        start = R.spent()
        if start >= TOTAL_CAP:
            print(json.dumps({'stop': 'total cap', 'spent': round(start, 6)}))
            break
        cap = min(start + CHUNK, TOTAL_CAP)
        i += 1
        print(json.dumps({'chunk': i, 'start': round(start, 6), 'cap': round(cap, 6)}),
              flush=True)
        R.pipeline(8, cap)
        end = R.spent()
        # the instruction's bar is $1.00 of actual spend per chunk; CHUNK is the call-level
        # budget that leaves room for the calls in flight when the cap check fires
        over = end - start > 1.000
        print(json.dumps({'chunk': i, 'end': round(end, 6),
                          'chunk_spend': round(end - start, 6),
                          'overrun': over}), flush=True)
        if over:
            print(json.dumps({'stop': 'chunk overrun'}))
            break
        done = sum(1 for _ in open(f'{DIR}/pipeline.jsonl'))
        want = 608
        try:
            m = json.load(open(f'{DIR}/build_manifest.json'))
            want = m.get('traces', want)
        except Exception:
            pass
        if done >= want:
            print(json.dumps({'stop': 'complete', 'traces': done, 'spent': round(end, 6)}))
            break
        if end <= start:
            print(json.dumps({'stop': 'no progress'}))
            break


if __name__ == '__main__':
    main()