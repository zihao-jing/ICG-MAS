"""Rebuild rebuttal/external/ from pinned public sources and verify every SHA-256.

    python -m scripts.fetch_external            # fetch (if needed) and verify
    python -m scripts.fetch_external --verify   # verify only, no network
    python -m scripts.fetch_external --init-manifest   # (re)write MANIFEST.json from a fresh fetch

The folder is gitignored: the [R1] release has no code licence, so it is used for
evaluation only and never redistributed (decision D1).
"""
import argparse, hashlib, json, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

EXTERNAL = Path(__file__).resolve().parents[1] / 'rebuttal' / 'external'
MANIFEST = EXTERNAL / 'MANIFEST.json'
SOURCES = {
    'whowhen_eval': {'kind': 'git', 'url': 'https://github.com/ag2ai/whowhen_pro.git',
                     'revision': '14369dcb079c7cdf86ed2924145d5a28ff5c73b2', 'subdir': 'whowhen_eval'},
    'utils.py': {'kind': 'git', 'url': 'https://github.com/mingyin1/Agents_Failure_Attribution.git',
                 'revision': 'b2bae5c5b06d681d04ea5e9b63b7a30525c04925', 'path': 'Automated_FA/Lib/utils.py', 'licence': 'MIT'},
    'taxonomy.yaml': {'kind': 'http',
                      'url': 'https://huggingface.co/datasets/Leoxx/whowhen_pro/resolve/0bd196c/taxonomy.yaml',
                      'repo': 'Leoxx/whowhen_pro', 'revision': '0bd196c'},
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(root):
    return {str(p.relative_to(EXTERNAL)): sha256(p)
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def fetch():
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fetch-external-') as tmp:
        s = SOURCES['whowhen_eval']
        subprocess.run(['git', 'clone', '-q', s['url'], f'{tmp}/repo'], check=True)
        subprocess.run(['git', '-C', f'{tmp}/repo', 'checkout', '-q', s['revision']], check=True)
        target = EXTERNAL / 'whowhen_eval'
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(f'{tmp}/repo/{s["subdir"]}', target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        u = SOURCES['utils.py']
        subprocess.run(['git', 'clone', '-q', u['url'], f'{tmp}/ww'], check=True)
        subprocess.run(['git', '-C', f'{tmp}/ww', 'checkout', '-q', u['revision']], check=True)
        shutil.copyfile(f'{tmp}/ww/{u["path"]}', EXTERNAL / 'utils.py')
        with urllib.request.urlopen(SOURCES['taxonomy.yaml']['url']) as r:
            (EXTERNAL / 'taxonomy.yaml').write_bytes(r.read())


def verify():
    """Return a list of problems; empty means every file in MANIFEST.json matches."""
    if not MANIFEST.exists():
        return [f'{MANIFEST} is missing']
    expected = json.loads(MANIFEST.read_text())['files']
    problems = []
    for name, entry in expected.items():
        p = EXTERNAL / name
        if not p.exists():
            problems.append(f'missing {name}')
        elif sha256(p) != entry['sha256']:
            problems.append(f'hash mismatch {name}')
    return problems


def init_manifest():
    files = {}
    for name, h in tree_hashes(EXTERNAL).items():
        if name == 'MANIFEST.json':
            continue
        src = SOURCES['whowhen_eval'] if name.startswith('whowhen_eval/') else SOURCES[name]
        where = src['url'] if src['kind'] == 'http' else f'{src["url"]} ({src.get("subdir", src.get("path"))})'
        files[name] = {'source': where,
                       'revision': src['revision'], 'sha256': h}
    MANIFEST.write_text(json.dumps({'note': 'Evaluation-only copies of public third-party files (D1); not redistributed; gitignored.',
                                    'files': files}, indent=1, sort_keys=True) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--init-manifest', action='store_true')
    a = ap.parse_args()
    if not a.verify:
        fetch()
    if a.init_manifest:
        init_manifest()
    problems = verify()
    if problems:
        print('FAILED:', *problems, sep='\n  ')
        sys.exit(1)
    print(f'OK: {len(json.loads(MANIFEST.read_text())["files"])} files match {MANIFEST}')


if __name__ == '__main__':
    main()
