"""
Paradigm I: MapReduce / Aggregation Motifs
Cases I-01 to I-10

Characteristics:
- Embarrassingly parallel computations
- Independent local processing
- Simple aggregation at the end
- Optimal topology: Star or Tree structure
- Theoretical message complexity: O(N)
"""

import random
from typing import List, Dict, Any, Callable

# Set random seed for reproducibility
random.seed(42)


def generate_paradigm_i_cases(num_agents: int, case_structure_func: Callable) -> List[Dict]:
    """Generate all Paradigm I benchmark cases"""
    cases = []

    # I-01: Global Max
    cases.append(_generate_i01_global_max(num_agents, case_structure_func))

    # I-02: Word Frequency
    cases.append(_generate_i02_word_frequency(num_agents, case_structure_func))

    # I-03: Distributed Vote
    cases.append(_generate_i03_distributed_vote(num_agents, case_structure_func))

    # I-04: Any Match
    cases.append(_generate_i04_any_match(num_agents, case_structure_func))

    # I-05: Range Count
    cases.append(_generate_i05_range_count(num_agents, case_structure_func))

    # I-06: Checksum
    cases.append(_generate_i06_checksum(num_agents, case_structure_func))

    # I-07: Average Value
    cases.append(_generate_i07_average_value(num_agents, case_structure_func))

    # I-08: Set Union Size
    cases.append(_generate_i08_set_union_size(num_agents, case_structure_func))

    # I-09: Top-K Select
    cases.append(_generate_i09_top_k_select(num_agents, case_structure_func))

    # I-10: Standard Deviation
    cases.append(_generate_i10_std_deviation(num_agents, case_structure_func))

    return cases


def _generate_i01_global_max(num_agents: int, case_func: Callable) -> Dict:
    """I-01: Global Max - Find the maximum value across all data"""

    # Generate test data
    total_size = num_agents * 20  # 20 numbers per agent
    data = [random.randint(-1000, 1000) for _ in range(total_size)]

    # Shard data to agents
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = max(data)

    description = """**Task: Global Maximum**

Find the GLOBAL MAXIMUM value across all agents' data.

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm:**
1. Compute the maximum in your local shard
2. Coordinate with other agents to determine the global maximum

**Output:**
A single integer representing the global maximum value.

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result(global_max)."""

    return case_func(
        case_id="I-01",
        case_name="Global Max",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/third-maximum-number/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_values) == max(global_data)",
        optimal_topology="Star (all agents → leader) or Tree, then broadcast result",
        optimal_message_count=f"{num_agents - 1} messages to collect + {num_agents - 1} to broadcast = {2 * (num_agents - 1)} total",
        output_type="distributed"
    )


def _generate_i02_word_frequency(num_agents: int, case_func: Callable) -> Dict:
    """I-02: Word Frequency - Count occurrences of a target word"""

    # Generate word list
    words = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
    target_word = "apple"

    total_size = num_agents * 30
    data = [random.choice(words) for _ in range(total_size)]

    # Ensure some target words exist
    for i in range(0, len(data), 10):
        data[i] = target_word

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = data.count(target_word)

    description = f"""**Task: Word Frequency Count**

Count the TOTAL occurrences of the word "{target_word}" across all agents' data.

**Your Data:**
You (Agent {{agent_id}}) hold: {{input_shard}}

**Algorithm:**
1. Count how many times "{target_word}" appears in your local data
2. Coordinate with other agents to compute the global count

**Output:**
A single integer representing the total count of "{target_word}".

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result(total_count)."""

    return case_func(
        case_id="I-02",
        case_name="Word Frequency",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/count-common-words-with-one-occurrence/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_counts) == global_count",
        optimal_topology="Star (all agents → leader) then broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} messages (collect + broadcast)",
        output_type="distributed"
    )


def _generate_i03_distributed_vote(num_agents: int, case_func: Callable) -> Dict:
    """I-03: Distributed Vote - Find the candidate with most votes"""

    candidates = ["Candidate_A", "Candidate_B", "Candidate_C", "Candidate_D"]

    total_votes = num_agents * 25
    votes = [random.choice(candidates) for _ in range(total_votes)]

    # Ensure there's a clear winner (every 2nd vote to guarantee majority)
    winner = random.choice(candidates)
    for i in range(0, len(votes), 2):
        votes[i] = winner

    # Shard data
    chunk_size = len(votes) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(votes)
        shards.append(votes[start:end])

    # Find winner
    vote_counts = {c: votes.count(c) for c in candidates}
    expected_output = max(vote_counts, key=vote_counts.get)

    description = """**Task: Distributed Voting**

Determine which candidate received the MOST votes across all agents' data.

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm:**
1. Count the votes for each candidate in your local shard
2. Collaborate with other agents to determine the global winner

**Output:**
A string with the candidate name who received the most votes (e.g., "Candidate_A").

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result("Candidate_X")."""

    return case_func(
        case_id="I-03",
        case_name="Distributed Vote",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/majority-element/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_candidates) == majority_winner",
        optimal_topology="Star or Tree with histogram aggregation, then broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} messages",
        output_type="distributed"
    )


def _generate_i04_any_match(num_agents: int, case_func: Callable) -> Dict:
    """I-04: Any Match - Check if any string contains 'ERROR'"""

    strings = ["INFO: System started", "DEBUG: Loading config", "WARNING: Low memory",
               "SUCCESS: Task completed", "TRACE: Function called"]

    total_size = num_agents * 15
    data = [random.choice(strings) for _ in range(total_size)]

    # Randomly insert ERROR
    has_error = random.choice([True, False])
    if has_error:
        error_pos = random.randint(0, len(data) - 1)
        data[error_pos] = "ERROR: Critical failure detected"

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = any("ERROR" in s for s in data)

    description = """**Task: Error Detection**

Determine if ANY string in the global dataset contains the substring "ERROR".

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm:**
1. Check if any string in your local data contains "ERROR"
2. Coordinate with other agents to determine if ERROR exists anywhere
3. Early termination: Once ANY agent finds "ERROR", the answer is True

**Output:**
A boolean (True/False) indicating if "ERROR" was found anywhere.

**Communication Protocol:**
Topology: Star/Tree with early termination → broadcast.
All agents must submit the same final answer using submit_result(True/False)."""

    return case_func(
        case_id="I-04",
        case_name="Any Match",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/find-the-index-of-the-first-occurrence-in-a-string/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_bools) == (pattern in global_input)",
        optimal_topology="Star with early termination or broadcast",
        optimal_message_count=f"1 to {2 * (num_agents - 1)} messages (early termination + broadcast if found)",
        output_type="distributed"
    )


def _generate_i05_range_count(num_agents: int, case_func: Callable) -> Dict:
    """I-05: Range Count - Count numbers in a range [L, R]"""

    L, R = 100, 500
    total_size = num_agents * 30
    data = [random.randint(0, 1000) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = sum(1 for x in data if L <= x <= R)

    description = f"""**Task: Range Count**

Count how many numbers in the global dataset fall within the range [{L}, {R}] (inclusive).

**Your Data:**
You (Agent {{agent_id}}) hold: {{input_shard}}

**Algorithm:**
1. Count how many numbers in your local data satisfy: {L} ≤ x ≤ {R}
2. Coordinate with other agents to compute the global count

**Output:**
A single integer representing the total count of numbers in range [{L}, {R}].

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result(total_count)."""

    return case_func(
        case_id="I-05",
        case_name="Range Count",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/count-of-range-sum/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_counts) == global_range_count",
        optimal_topology="Star (all agents → leader) then broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} messages",
        output_type="distributed"
    )


def _generate_i06_checksum(num_agents: int, case_func: Callable) -> Dict:
    """I-06: Checksum - Compute XOR checksum"""

    total_size = num_agents * 20
    data = [random.randint(0, 255) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute XOR checksum
    expected_output = 0
    for val in data:
        expected_output ^= val

    description = """**Task: XOR Checksum**

Compute the XOR checksum of all data bytes across all agents.

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm:**
1. Compute local XOR: local_xor = byte1 ^ byte2 ^ ... ^ byteN
2. Coordinate with other agents to compute global XOR
3. Property: XOR is associative and commutative, so global_xor = xor1 ^ xor2 ^ ... ^ xorN

**Output:**
A single integer (0-255) representing the global XOR checksum.

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result(global_checksum)."""

    return case_func(
        case_id="I-06",
        case_name="Checksum",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/single-number/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_hashes) == global_hash",
        optimal_topology="Star (all agents → leader) then broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} messages",
        output_type="distributed"
    )


def _generate_i07_average_value(num_agents: int, case_func: Callable) -> Dict:
    """I-07: Average Value - Compute global average"""

    total_size = num_agents * 25
    data = [random.uniform(0, 100) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = sum(data) / len(data)

    description = """**Task: Global Average**

Compute the average (mean) value of all numbers across all agents' data.

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm:**
1. Compute local_sum and local_count
2. Coordinate with other agents to compute global_sum and global_count
3. global_average = global_sum / global_count

**Output:**
A floating-point number representing the global average (precision: 2 decimal places).

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result(global_average)."""

    return case_func(
        case_id="I-07",
        case_name="Average Value",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/average-salary-excluding-the-minimum-and-maximum-salary/",
        description=description,
        input_data=shards,
        expected_output=round(expected_output, 2),
        verification_logic="all(abs(submitted_avg - global_avg) < 0.01)",
        optimal_topology="Star (all agents → leader with (sum, count)) then broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} messages",
        output_type="distributed"
    )


def _generate_i08_set_union_size(num_agents: int, case_func: Callable) -> Dict:
    """I-08: Set Union Size - Count distinct elements globally"""

    # Generate data with some duplicates
    total_size = num_agents * 30
    unique_elements = list(range(total_size // 2))  # Half as many unique elements as total
    data = [random.choice(unique_elements) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = len(set(data))

    description = """**Task: Global Distinct Count**

Count the total number of DISTINCT (unique) elements across all agents' data.

**Your Data:**
You (Agent {agent_id}) hold (may contain duplicates): {input_shard}

**Algorithm:**
1. Identify unique elements in your local data: local_set = set(your_data)
2. Coordinate with other agents to find the global set of distinct elements
3. Note: Elements may appear in multiple agents' data - need global deduplication

**Output:**
A single integer representing the total count of distinct elements.

**Communication Protocol:**
Topology: Star/Tree aggregation or hash-based partitioning → broadcast.
All agents must submit the same final answer using submit_result(global_distinct_count)."""

    return case_func(
        case_id="I-08",
        case_name="Set Union Size",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/contains-duplicate/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(submitted_sizes) == len(set(global_input))",
        optimal_topology="Star or hash-based partitioning, then broadcast",
        optimal_message_count=f"{num_agents - 1} to O(N²) depending on strategy, plus broadcast",
        output_type="distributed"
    )


def _generate_i09_top_k_select(num_agents: int, case_func: Callable) -> Dict:
    """I-09: Top-K Select - Find K largest elements"""

    K = 10
    total_size = num_agents * 30
    data = [random.randint(1, 1000) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = sorted(data, reverse=True)[:K]

    description = f"""**Task: Top-K Selection**

Find the {K} largest values across all agents' data.

**Your Data:**
You (Agent {{agent_id}}) hold: {{input_shard}}

**Algorithm:**
1. Find the top {K} values in your local data
2. Coordinate with other agents to find the global top-{K}
3. Each agent only needs to send at most {K} values to a coordinator

**Output:**
A list of {K} integers, sorted in descending order.

**Communication Protocol:**
Topology: Star/Tree aggregation → broadcast.
All agents must submit the same final answer using submit_result([val1, val2, ..., val{K}])."""

    return case_func(
        case_id="I-09",
        case_name="Top-K Select",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/kth-largest-element-in-an-array/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(set(submitted_list) == set(global_top_k))",
        optimal_topology="Star (all agents → leader with local top-K) then broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} messages",
        output_type="distributed"
    )


def _generate_i10_std_deviation(num_agents: int, case_func: Callable) -> Dict:
    """I-10: Standard Deviation - Two-phase computation"""

    total_size = num_agents * 30
    data = [random.uniform(0, 100) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute expected standard deviation
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    expected_output = variance ** 0.5

    description = """**Task: Standard Deviation (Two-Phase)**

Compute the population standard deviation of all numbers across all agents' data.

**Your Data:**
You (Agent {agent_id}) hold: {input_shard}

**Algorithm (Two Phases):**
**Phase 1: Compute Global Mean**
- Calculate local_sum and local_count
- Coordinate to compute global_mean = total_sum / total_count

**Phase 2: Compute Variance**
- Calculate local variance contribution: sum((x - global_mean)² for x in local_data)
- Coordinate to sum all variance contributions
- Compute std_dev = sqrt(total_variance / total_count)

**Output:**
A floating-point number (precision: 2 decimal places).

**Communication Protocol:**
Topology: Star/Tree with two-phase protocol → broadcast after each phase.
All agents must submit the same final answer using submit_result(std_dev)."""

    return case_func(
        case_id="I-10",
        case_name="Standard Deviation",
        paradigm="Paradigm I",
        leetcode_url="https://leetcode.com/problems/average-salary-excluding-the-minimum-and-maximum-salary/",
        description=description,
        input_data=shards,
        expected_output=round(expected_output, 2),
        verification_logic="all(abs(submitted_std - global_std) < 0.01)",
        optimal_topology="Star with two-phase protocol and broadcast",
        optimal_message_count=f"2 × {2 * (num_agents - 1)} = {4 * (num_agents - 1)} messages (two rounds, each with collect + broadcast)",
        output_type="distributed"
    )