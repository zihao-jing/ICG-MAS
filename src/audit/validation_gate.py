"""Hard gate: no label may be written before its exact validation passed.

A validation record is keyed by (label, prompt_sha256).  A record with
`passed: true` for that exact pair is required; a missing record, a hash
mismatch, or `passed: false` raises `UnvalidatedLabel`.  Validation runs
themselves write their reference/candidate labels through the same prompt and
are exempt only because they call the judge directly, never through a
results-writing path.
"""
import json
from pathlib import Path

REGISTRY = Path('rebuttal/validations/registry.json')


class UnvalidatedLabel(RuntimeError):
    pass


def require(label, prompt_sha256, registry=REGISTRY):
    data = json.loads(Path(registry).read_text())
    for rec in data.get('validations', []):
        if rec.get('label') == label and rec.get('prompt_sha256') == prompt_sha256:
            if rec.get('passed') is True:
                return rec
            raise UnvalidatedLabel(
                f'{label} at prompt {prompt_sha256[:12]} did not pass: '
                f'kappa {rec.get("kappa")} CI {rec.get("kappa_ci")}')
    raise UnvalidatedLabel(
        f'no validation record for {label} at prompt {prompt_sha256[:12]}')