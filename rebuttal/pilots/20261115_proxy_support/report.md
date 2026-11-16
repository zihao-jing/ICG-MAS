# Proxy support for the audit's stage diagnosis: pilot

2026-11-15. Rule `Proxy-support-pilot-v1.md` (frozen and hashed), amendment 1 (output-shape tolerance,
parser only), facts prompt `proxy_facts_prompt_v1.json`, equivalence prompt
`proxy_support_equiv_prompt_v1.json`, labeller prompt v3 (system `3f7f19bb…`). Qwen3-235B generates the
facts from the question and the agents' shards; Gemini 3.6 Flash checks them against the gold supports;
Haiku 5.5 runs the audit label. Spend **$0.060048** (facts $0.008088, gold check $0.049776, labels
$0.002184), cap $1.0.

## Sample

10 MuSiQue cases, stratified by the gold-based audit stage: extraction 4, transmission 4, sharding 1,
aggregation 1. 10 instances, models gemma31b 4 / gpt4omini 5 / qwen235b 1; 6 injected and 4 cohort traces.
40 proxy facts generated. Generation: 7/10 traces valid on the first pass; the other 3 returned complete
facts in a flat-map shape (2) or cited document titles inside a supplied shard (1) and were regenerated
after amendment 1, which changed only the parser and the shard-id normalisation, not the prompt.

## Proxy facts against the gold supports

**Match (equivalent) 33/40 = .825 [.672, .927]**, 95% Clopper-Pearson.

| verdict | facts |
| --- | ---: |
| equivalent | 33 |
| partial | 3 |
| unsupported | 4 |
| contradicted | 0 |

Two failure types, both read from the verdict reasons:

- **Off-chain facts (4 unsupported, 3 of them).** Facts taken from documents outside the gold chain:
  the Vatican/Pope claim, two facts about Radio Television of Kosovo, and the Forest Acres–Columbia
  border claim. The model cannot tell which document is gold, so it states true-looking facts from
  distractors.
- **Over-specification (3 partial + 1 unsupported).** The fact adds a relation or qualifier the gold
  passage does not state: "the FDA is the owner of iPLEDGE", "Millbrook is Serena Ryder's birthplace",
  "Claudia Wells co-starred" (the support names the role, not the co-star relation).

No fact was contradicted by the gold supports.

## Stage diagnosis on proxy facts

**Agreement with the gold-based audit 7/10 = .700 [.348, .933]**; with the case's known stage also
7/10 = .700 [.348, .933]. The gold audit itself agrees with the known stage on 8/10 of these cases.
95% Clopper-Pearson.

| proxy stage \ gold-audit stage | extraction | transmission | sharding | aggregation |
| --- | ---: | ---: | ---: | ---: |
| extraction | 3 | 1 | 0 | 0 |
| transmission | 1 | 3 | 0 | 1 |
| sharding | 0 | 0 | 1 | 0 |
| aggregation | 0 | 0 | 0 | 0 |

| case | facts | equiv | proxy | gold audit | known |
| --- | ---: | ---: | --- | --- | --- |
| inj/gemma31b/4hop1__429751… | 5 | 4/5 | extraction | extraction | transmission |
| coh/gemma31b/2hop__723404… | 5 | 4/5 | extraction | extraction | extraction |
| coh/gpt4omini/3hop1__389761… | 3 | 3/3 | extraction | extraction | extraction |
| coh/gpt4omini/2hop__25396… | 2 | 2/2 | transmission | extraction | extraction |
| inj/qwen235b/3hop1__144439… | 9 | 9/9 | transmission | transmission | transmission |
| inj/gpt4omini/2hop__17455… | 3 | 3/3 | extraction | transmission | transmission |
| inj/gemma31b/2hop__51074… | 1 | 0/1 | transmission | transmission | transmission |
| inj/gpt4omini/3hop1__773623… | 4 | 3/4 | transmission | transmission | transmission |
| coh/gpt4omini/3hop1__127837… | 4 | 2/4 | sharding | sharding | sharding |
| inj/gemma31b/3hop1__254856… | 4 | 3/4 | transmission | aggregation | transmission |

**The three mismatches are fact-set differences, not label changes.**

- `coh/gpt4omini/2hop__25396…`: the proxy fact merges two parentage claims ("second son of Arthur Peel
  … youngest son of Sir Robert Peel"); the extraction pool carries only one of them, so the labeller
  calls the conjunction distorted on the board and the audit names transmission. The gold audit's fact
  targets the gold-chain relation and names extraction. Granularity.
- `inj/gpt4omini/2hop__17455…`: a proxy fact from a distractor document (Second Punic War) is absent
  from the extraction pool, so the audit names extraction. The gold audit's fact is the corrupted unit,
  carried but partial at the board, so it names transmission. Distractor fact.
- `inj/gemma31b/3hop1__254856…`: two proxy facts over-specify (debut album, birthplace) and are only
  partial at the board, so the audit names transmission partial; the gold audit's facts are all present
  and it names aggregation. Over-specification.

All three mismatches trace to the proxy fact set. Equivalence does not predict stage agreement: the
two traces whose facts are all equivalent still disagree (the granularity and distractor cases above),
while the trace with the worst gold match (0/1) agrees. Stage agreement therefore depends on which
facts the proxy chose, not on how many of them the gold supports state.

## Projection

Measured $0.0060/trace. Full run over the 89 diagnosed cases ≈ $0.53; over the 608 main-table traces
≈ $3.65, inside the $3–8 band. No full run started.

## Ledger

$89.948501 before this pilot + $0.060048 = **$90.008548**. Calls in `calls.jsonl`, logs
`facts_retry.log` and `audit.log`; results in `results.json`.