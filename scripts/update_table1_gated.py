"""
update_table1_gated.py — Read gated/debate results for 4 new models and print
the values needed to fill Table 1 in sections/4-experiments.tex.

Protocols added: free_form_debate, confidence_gated, disagreement_gated
Models: geminiflashlite, gpt4omini, deepseekr1_32b, gemma31b

SB combined accuracy = mean(n5_acc, n10_acc) * 100, rounded to 1 decimal.
MQ accuracy = musique acc * 100 (F1), rounded to 1 decimal.
"""
import json, os, sys

BASE = os.path.join(os.path.dirname(__file__), "..", "results")

MODELS = [
    ("geminiflashlite", "Gemini-FL"),
    ("gpt4omini",       "GPT-4o-mini"),
    ("deepseekr1_32b",  "DeepSeek-32B"),
    ("gemma31b",        "Gemma-4-31B"),
]

PROTOCOLS = ["free_form_debate", "confidence_gated", "disagreement_gated"]
PROTO_LABELS = {
    "free_form_debate":    "Free-form Debate",
    "confidence_gated":    "Confidence-Gated",
    "disagreement_gated":  "Disagreement-Gated",
}

def load_acc(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        d = json.load(f)
    return d.get("table", {})

results = {}
for short, label in MODELS:
    n5_table  = load_acc(os.path.join(BASE, f"run_{short}_n5_gated",     "results.json"))
    n10_table = load_acc(os.path.join(BASE, f"run_{short}_n10_gated",    "results.json"))
    mq_table  = load_acc(os.path.join(BASE, f"run_musique_{short}_gated","results.json"))

    row = {}
    for p in PROTOCOLS:
        sb, mq = None, None

        if n5_table and n10_table and p in n5_table and p in n10_table:
            a5  = n5_table[p]["acc"]
            a10 = n10_table[p]["acc"]
            sb  = round((a5 + a10) / 2 * 100, 1)
        elif n5_table and p in (n5_table or {}):
            sb = round(n5_table[p]["acc"] * 100, 1)
        elif n10_table and p in (n10_table or {}):
            sb = round(n10_table[p]["acc"] * 100, 1)

        if mq_table and p in mq_table:
            mq = round(mq_table[p]["acc"] * 100, 1)

        row[p] = (sb, mq)
    results[label] = row

# Print a compact summary
print("=== Table 1 fill-in values for gated/debate protocols ===\n")
for label in [r[1] for r in MODELS]:
    row = results[label]
    print(f"  {label}")
    for p in PROTOCOLS:
        sb, mq = row[p]
        sb_s = f"{sb:.1f}" if sb is not None else "MISSING"
        mq_s = f"{mq:.1f}" if mq is not None else "MISSING"
        print(f"    {PROTO_LABELS[p]:22s}  SB={sb_s:6s}  MQ={mq_s:6s}")
    print()

# Print LaTeX-ready block
print("=== LaTeX row snippets for Table 1 ===\n")
# Column order: Gemini-FL, GPT-4o-mini, DeepSeek-32B, Gemma-4-31B (SB MQ each)
model_labels = [r[1] for r in MODELS]
for p in PROTOCOLS:
    cells = []
    for label in model_labels:
        sb, mq = results[label][p]
        sb_s = f"{sb:.1f}" if sb is not None else "---"
        mq_s = f"{mq:.1f}" if mq is not None else "---"
        cells.append(f"{sb_s} & {mq_s}")
    print(f"    \\quad {PROTO_LABELS[p]:<22s}& {' & '.join(cells)} \\\\")
