# Answer-equivalence check: validation on the 150 author-labelled traces

Prompt `answer-equiv-v1`, file sha256 `51082bc881a19231299de0e9fab4e574895760637276abce7845294b9eec8153`, system sha256 `2831314b99da86c2fc8d7879a401b1ebea8c5617ff2c01102bba28e044d8ba63`, model `anthropic/claude-haiku-5.5`, temperature 0.
Scored 150/150; spend $0.020857 against a $0.50 cap. Calls: `rebuttal/pilots/20261112_answer_equiv/calls_validate.jsonl`.

## Result

- Agreement with the authors' answer-correctness call: **0.940** (95% CI 0.900-0.973).
- Cohen's kappa: **0.848** (95% CI 0.725-0.939).
- EQUIVALENT recall on the 38 author-CORRECT answers: **0.947**.
- NOT_EQUIVALENT recall on the 112 author-DEFECT answers: **0.938**.

| check verdict | author CORRECT | author DEFECT |
| --- | ---: | ---: |
| EQUIVALENT | 36 | 7 |
| NOT_EQUIVALENT | 2 | 105 |

## Go/no-go

Required: agreement >= 0.90, kappa >= 0.75, EQUIVALENT recall >= 0.85. **PASS**.

## Disagreements

### E1 Anchor Q13 run 1
Authors: CORRECT; check: NOT_EQUIVALENT
Question: **Task: Top-K Selection**

Find the 10 largest values across all agents' data.

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm:**
1. Find the top 10 values in your local data
2. Coordinate with other agents to find the global top-10
3. Each agent only needs to send at most 10
Gold: [1000, 1000, 999, 997, 995, 994, 994, 993, 993, 984]
Answer: [1000, 999, 997, 995, 994, 993, 984, 982, 981, 980]
Reason: The system's list differs from the gold: it has only one 1000 (gold has two), and its later values (982, 981, 980 vs gold's 994, 993, 984 duplicates) do not match the required top-10 multiset.

### E1 Anchor Q15 run 2
Authors: CORRECT; check: NOT_EQUIVALENT
Question: When did the maker of Acura Legend, the manufacturer of Lexus RX and Nissan open US assembly plants?
Gold: 1981
Answer: Acura Legend's maker (Honda) opened US assembly plants in the early 1980s, Lexus's maker (Toyota) opened US assembly plants around the same time, and Nissan opened US assembly plants shortly after, affected by the 1981 voluntary export restraints.
Reason: The gold answer is a single year, 1981, while the system answer gives only vague timing ('early 1980s', 'around the same time', 'shortly after') for the three makers and never states the specific year of their plant openings.

### E1 Anchor Q19 run 1
Authors: DEFECT; check: EQUIVALENT
Question: Where is the province of Aqqala County located?
Gold: in the north-east of the country south of the Caspian Sea
Answer: In the north-east of Iran, south of the Caspian Sea.
Reason: The system answer states the same location as the gold (north-east, south of the Caspian Sea), with 'Iran' added as the country, which does not contradict the gold.

### E1 Anchor Q27 run 2
Authors: DEFECT; check: EQUIVALENT
Question: Where is the headquarters of the 1st Combat Communication Squadron located?
Gold: Ramstein-Miesenbach
Answer: The headquarters of the 1st Combat Communications Squadron is located at Ramstein Air Base, Germany.
Reason: The system names Ramstein Air Base, Germany, which is the same location as the gold answer Ramstein-Miesenbach (Ramstein Air Base lies in the Ramstein-Miesenbach district), so it identifies the same place.

### E1 Anchor Q04 run 1
Authors: DEFECT; check: EQUIVALENT
Question: How many Stations of the Cross happened in the city originating Christianity in Rome, Egypt, Judea and the country for Vasilopita?
Gold: fourteen
Answer: 14 Stations of the Cross happened in Judea, the city originating Christianity; none occurred in Rome, Egypt, or the country for Vasilopita.
Reason: The system answer gives 14, matching the gold answer 'fourteen', and its added clarification about Judea and the other locations does not change the numeric answer.

### E1 Anchor Q08 run 1
Authors: DEFECT; check: EQUIVALENT
Question: What was Germany's goal in the Battle of the ocean adjacent to the city Herbert Saffir died in?
Gold: to stem the flow of merchant shipping that enabled Britain to keep fighting
Answer: Germany's goal in the Battle of the Atlantic, the ocean adjacent to Miami where Herbert Saffir died, was to enforce a naval blockade using U-boats and surface warships to cut off Britain’s supply lines and force a strategic surrender.
Reason: Both answers identify Germany's goal as disrupting/cutting off the merchant shipping and supply lines that let Britain keep fighting, which matches the gold answer's core claim; the system's added detail about forcing surrender is consistent with that aim rather than contradicting it.

### E1 Anchor Q06 run 2
Authors: DEFECT; check: EQUIVALENT
Question: Where in the country where Bodindecha was born was The Beach filmed?
Gold: island Koh Phi Phi
Answer: Koh Phi Phi in Thailand.
Reason: The system answer names Koh Phi Phi, matching the gold answer's island Koh Phi Phi, with the added country name Thailand being consistent with the question's context.

### E1 Anchor Q18 run 1
Authors: DEFECT; check: EQUIVALENT
Question: What country had the Border Troops of the republic known for the literature of the country of citizenship of Ilona Richter?
Gold: GDR
Answer: East Germany
Reason: GDR (German Democratic Republic) is the same country as East Germany, so the system's answer names the same entity as the gold answer.

### E1 Anchor Q18 run 2
Authors: DEFECT; check: EQUIVALENT
Question: What country had the Border Troops of the republic known for the literature of the country of citizenship of Ilona Richter?
Gold: GDR
Answer: East Germany
Reason: GDR is the German Democratic Republic, which is commonly known as East Germany, so the system answer names the same country.

