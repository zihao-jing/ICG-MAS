"""
Paradigm II: Structured Mesh / Stencil Motifs
Cases II-11 to II-20

Characteristics:
- Data has spatial locality (agents are arranged sequentially)
- Each agent's computation depends on BOUNDARY data from immediate neighbors
- Optimal topology: Chain or mesh with neighbor-to-neighbor communication
- Theoretical message complexity: O(N) but ONLY between adjacent agents
- Key insight: Agents should discover they only need to talk to neighbors, not everyone
"""

import random
from typing import List, Dict, Any, Callable

# Set random seed for reproducibility
random.seed(42)


def generate_paradigm_ii_cases(num_agents: int, case_structure_func: Callable) -> List[Dict]:
    """Generate all Paradigm II benchmark cases"""
    cases = []

    # II-11: Prefix Sum
    cases.append(_generate_ii11_prefix_sum(num_agents, case_structure_func))

    # II-12: Moving Average
    cases.append(_generate_ii12_moving_average(num_agents, case_structure_func))

    # II-13: Longest Palindrome
    cases.append(_generate_ii13_longest_palindrome(num_agents, case_structure_func))

    # II-14: 1D Life Game
    cases.append(_generate_ii14_life_game(num_agents, case_structure_func))

    # II-15: Pattern Search
    cases.append(_generate_ii15_pattern_search(num_agents, case_structure_func))

    # II-16: Trapping Rain
    cases.append(_generate_ii16_trapping_rain(num_agents, case_structure_func))

    # II-17: Diff Array
    cases.append(_generate_ii17_diff_array(num_agents, case_structure_func))

    # II-18: List Ranking
    cases.append(_generate_ii18_list_ranking(num_agents, case_structure_func))

    # II-19: Merge Neighbors
    cases.append(_generate_ii19_merge_neighbors(num_agents, case_structure_func))

    # II-20: Pipeline Hash
    cases.append(_generate_ii20_pipeline_hash(num_agents, case_structure_func))

    return cases


def _generate_ii11_prefix_sum(num_agents: int, case_func: Callable) -> Dict:
    """II-11: Prefix Sum (Scan) - Sequential dependency

    NOTE: This is a SEGMENTED output task - each agent outputs their own portion!
    """

    total_size = num_agents * 15
    data = [random.randint(1, 50) for _ in range(total_size)]

    # Shard data sequentially
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute expected prefix sums
    expected_output = []
    cumsum = 0
    for val in data:
        cumsum += val
        expected_output.append(cumsum)

    # Shard expected output - each agent has their own segment
    expected_shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(expected_output)
        expected_shards.append(expected_output[start:end])

    description = """**Task: Prefix Sum (Cumulative Sum)**

Compute the prefix sum (cumulative sum) of the entire array.

**Agent Ordering:**
Agent 0 → Agent 1 → ... → Agent {max_id} (sequential segments)

**Your Data (Position {agent_id}):**
{input_shard}

**Algorithm:**
- prefix_sum[i] = sum of all elements from index 0 to i
- You need the TOTAL SUM from all previous agents to adjust your local prefix sums

**Output:**
Each agent submits THEIR portion of the prefix sum array.

**Communication Protocol:**
Topology: Chain (0 → 1 → 2 → ... → {max_id}). Communicate with neighbors only.
Each agent submits their own segment using submit_result(your_prefix_sum_segment)."""

    return case_func(
        case_id="II-11",
        case_name="Prefix Sum",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/running-sum-of-1d-array/",
        description=description,
        input_data=shards,
        expected_output=expected_shards,
        verification_logic="concat(agent_outputs) == cumsum(global_input)",
        optimal_topology="Chain (Agent 0 → 1 → 2 → ... → N-1)",
        optimal_message_count=f"{num_agents - 1} messages (one per chain link)",
        output_type="distributed",
        is_segmented=True,   # ✅ NEW
    )






def _generate_ii12_moving_average(num_agents: int, case_func: Callable) -> Dict:
    """II-12: Moving Average - Requires boundary exchange

    NOTE: This is a GLOBAL output task - all agents submit the same result!
    """

    total_size = num_agents * 15
    data = [random.randint(1, 100) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute moving average (window=3, centered)
    expected_output = []
    for i in range(1, len(data) - 1):
        avg = (data[i-1] + data[i] + data[i+1]) / 3.0
        expected_output.append(round(avg, 2))

    description = """**Task: Moving Average (Window=3)**

Compute a moving average with window size 3 for all valid positions.

**Agent Ordering:**
Agents in a LINE: 0 ↔ 1 ↔ 2 ↔ ... ↔ {max_id} (consecutive data)

**Your Data (Position {agent_id}):**
{input_shard}

**Algorithm:**
For each element (except first and last globally): avg = (prev + curr + next) / 3
- You need BOUNDARY elements from neighbors to compute averages at segment edges

**Output:**
The complete moving average array (excluding first and last positions).

**Communication Protocol:**
Topology: Chain (0 ↔ 1 ↔ ... ↔ {max_id}). Exchange boundaries with neighbors.
All agents must submit the same final answer using submit_result(global_moving_averages)."""

    return case_func(
        case_id="II-12",
        case_name="Moving Average",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/moving-average-from-data-stream/",
        description=description,
        input_data=shards,
        expected_output=expected_output,  # Single list - all agents submit same
        verification_logic="all(agent_outputs) == moving_average(global_input, window=3)",
        optimal_topology="Chain with bidirectional boundary exchange, then share result",
        optimal_message_count=f"{2 * (num_agents - 1)} for boundaries + O(N) for sharing = O(N)",
        output_type="distributed"
    )


def _generate_ii13_longest_palindrome(num_agents: int, case_func: Callable) -> Dict:
    """II-13: Longest Palindrome - Cross-boundary palindrome detection

    NOTE: This is a GLOBAL output task - all agents submit the same length!
    """

    # Create a string with potential cross-boundary palindromes
    chars = "abcdefghijklmnopqrstuvwxyz"
    total_size = num_agents * 15
    data = [random.choice(chars) for _ in range(total_size)]

    # Insert a known palindrome
    palindrome = "racecar"
    insert_pos = random.randint(0, len(data) - len(palindrome))
    for j, char in enumerate(palindrome):
        data[insert_pos + j] = char

    string = ''.join(data)

    # Shard string
    chunk_size = len(string) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(string)
        shards.append(string[start:end])

    # Find longest palindrome
    def longest_palindrome_length(s):
        if not s:
            return 0
        max_len = 1
        for i in range(len(s)):
            for j in range(i + 1, len(s) + 1):
                substr = s[i:j]
                if substr == substr[::-1] and len(substr) > max_len:
                    max_len = len(substr)
        return max_len

    expected_output = longest_palindrome_length(string)

    description = """**Task: Longest Palindrome (Cross-Boundary)**

Find the length of the longest palindromic substring, including palindromes spanning agent boundaries.

**Agent Ordering:**
Agents hold CONSECUTIVE parts of one string: 0 → 1 → ... → {max_id}

**Your Data (Position {agent_id}):**
String segment: {input_shard}

**Algorithm:**
1. Find longest palindrome within your local segment
2. Exchange BOUNDARY CHARACTERS with neighbors to detect cross-boundary palindromes
3. Coordinate to find the global maximum length

**Output:**
A single integer representing the length of the longest palindrome.

**Communication Protocol:**
Topology: Chain (0 ↔ 1 ↔ ... ↔ {max_id}). Exchange prefix/suffix with neighbors.
All agents must submit the same final answer using submit_result(max_palindrome_length)."""

    return case_func(
        case_id="II-13",
        case_name="Longest Palindrome",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/longest-palindromic-substring/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == longest_palindrome(global_string)",
        optimal_topology="Chain with prefix/suffix exchange, then broadcast result",
        optimal_message_count=f"{2 * (num_agents - 1)} for boundaries + O(N) for sharing",
        output_type="distributed"
    )


def _generate_ii14_life_game(num_agents: int, case_func: Callable) -> Dict:
    """II-14: 1D Life Game - Cellular automaton with boundary dependencies

    NOTE: This is a SEGMENTED output task - each agent outputs their own final segment!
    """

    total_size = num_agents * 10
    # Initial state (0/1)
    state = [random.randint(0, 1) for _ in range(total_size)]
    steps = 5

    # Shard state sequentially
    chunk_size = len(state) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(state)
        shards.append(state[start:end])

    # Simulate global 1D life for expected output
    def step_once(arr):
        new_arr = arr[:]
        for i in range(len(arr)):
            left = arr[i - 1] if i - 1 >= 0 else 0
            right = arr[i + 1] if i + 1 < len(arr) else 0
            # Simple rule: cell becomes 1 iff exactly one of (left, self, right) is 1
            s = left + arr[i] + right
            new_arr[i] = 1 if s == 1 else 0
        return new_arr

    cur = state
    for _ in range(steps):
        cur = step_once(cur)

    expected_output = cur

    # Shard expected output
    expected_shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(expected_output)
        expected_shards.append(expected_output[start:end])

    description = f"""**Task: 1D Life Game (Cellular Automaton)**

Simulate a 1D cellular automaton for {steps} steps.

**Agent Ordering:**
Agents arranged sequentially: 0 ↔ 1 ↔ 2 ↔ ... ↔ {{max_id}}

**Your Data (Position {{agent_id}}):**
Initial segment: {{input_shard}}

**Algorithm:**
- Each cell's next state depends on (left, self, right)
- Rule: cell becomes 1 iff exactly one of (left, self, right) is 1
- Exchange boundary cells with neighbors at EACH step

**Output:**
Each agent submits their own final segment after {steps} steps.

**Communication Protocol:**
Topology: Chain (0 ↔ 1 ↔ ... ↔ {{max_id}}). Repeated boundary exchange.
Each agent submits their own segment using submit_result(your_final_segment)."""

    return case_func(
        case_id="II-14",
        case_name="1D Life Game",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/game-of-life/",
        description=description,
        input_data=shards,
        expected_output=expected_shards,
        verification_logic="concat(agent_outputs) == life_game(global_input, steps)",
        optimal_topology="Chain with repeated boundary exchange",
        optimal_message_count=f"O({steps} * (N-1))",
        output_type="distributed",
        is_segmented=True,   # ✅ NEW
    )






def _generate_ii15_pattern_search(num_agents: int, case_func: Callable) -> Dict:
    """II-15: Pattern Search - State machine across boundaries

    NOTE: This is a GLOBAL output task - all agents submit the same count!
    """

    chars = ['A', 'B', 'C', 'D', 'X', 'Y', 'Z']
    total_size = num_agents * 20
    data = [random.choice(chars) for _ in range(total_size)]

    # Insert pattern "A...B...C" a few times
    pattern_positions = []
    for _ in range(2):
        pos = random.randint(0, len(data) - 15)
        data[pos] = 'A'
        data[pos + random.randint(1, 5)] = 'B'
        data[pos + random.randint(6, 10)] = 'C'

    string = ''.join(data)

    # Count occurrences of subsequence A...B...C
    def count_subsequence(s, pattern):
        count = 0
        state = 0  # 0: looking for A, 1: found A looking for B, 2: found B looking for C
        for char in s:
            if state == 0 and char == 'A':
                state = 1
            elif state == 1 and char == 'B':
                state = 2
            elif state == 2 and char == 'C':
                count += 1
                state = 0  # Reset to find next pattern
        return count

    expected_output = count_subsequence(string, "ABC")

    # Shard string
    chunk_size = len(string) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(string)
        shards.append(string[start:end])

    description = """**Task: Subsequence Pattern Search**

Count how many times the subsequence pattern "A...B...C" appears in the global string.
(A followed eventually by B followed eventually by C)

**Agent Ordering:**
Agents hold CONSECUTIVE parts: 0 → 1 → 2 → ... → {max_id}

**Your Data (Position {agent_id}):**
String segment: {input_shard}

**Algorithm:**
Track state machine: 0 (looking for A) → 1 (found A) → 2 (found B) → complete on C
- State must be PASSED FORWARD through the chain (pipeline pattern)

**Output:**
A single integer representing the count of "A...B...C" patterns.

**Communication Protocol:**
Topology: Chain (0 → 1 → 2 → ... → {max_id}). Pass state forward.
All agents must submit the same final answer using submit_result(total_pattern_count)."""

    return case_func(
        case_id="II-15",
        case_name="Pattern Search",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/is-subsequence/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == global_subseq_count",
        optimal_topology="Chain with state passing (0 → 1 → 2 → ...), then broadcast result",
        optimal_message_count=f"{num_agents - 1} for pipeline + O(N) for sharing",
        output_type="distributed"
    )


def _generate_ii16_trapping_rain(num_agents: int, case_func: Callable) -> Dict:
    """II-16: Trapping Rain Water - Requires bidirectional pass

    NOTE: This is a GLOBAL output task - all agents submit the same total!
    """

    total_size = num_agents * 10
    data = [random.randint(0, 10) for _ in range(total_size)]

    # Ensure some valleys for water trapping
    for i in range(1, len(data) - 1, 5):
        data[i] = random.randint(0, 3)  # Create valleys

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute trapped water
    def trap_water(heights):
        if not heights:
            return 0
        n = len(heights)
        left_max = [0] * n
        right_max = [0] * n

        left_max[0] = heights[0]
        for i in range(1, n):
            left_max[i] = max(left_max[i-1], heights[i])

        right_max[n-1] = heights[n-1]
        for i in range(n-2, -1, -1):
            right_max[i] = max(right_max[i+1], heights[i])

        water = 0
        for i in range(n):
            water += min(left_max[i], right_max[i]) - heights[i]

        return water

    expected_output = trap_water(data)

    description = """**Task: Trapping Rain Water**

Given an elevation map, compute how much water can be trapped after raining.

**Agent Ordering:**
Agents hold CONSECUTIVE segments: 0 ↔ 1 ↔ ... ↔ {max_id}

**Your Data (Position {agent_id}):**
Elevation heights: {input_shard}

**Algorithm:**
- water_at_i = min(max_height_to_left, max_height_to_right) - height[i]
- Requires TWO PASSES: left-to-right (get left_max), right-to-left (get right_max)

**Output:**
A single integer representing the total trapped water units.

**Communication Protocol:**
Topology: Chain (0 ↔ 1 ↔ ... ↔ {max_id}). Bidirectional pass.
All agents must submit the same final answer using submit_result(total_water)."""

    return case_func(
        case_id="II-16",
        case_name="Trapping Rain",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/trapping-rain-water/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == trap_water(global_input)",
        optimal_topology="Chain with bidirectional pass, then aggregate and broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} for passes + O(N) for sharing",
        output_type="distributed"
    )


def _generate_ii17_diff_array(num_agents: int, case_func: Callable) -> Dict:
    """II-17: Difference Array - Simple neighbor dependency

    NOTE: This is a GLOBAL output task - all agents submit the same array!
    """

    total_size = num_agents * 15
    data = [random.randint(1, 100) for _ in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute differences
    expected_output = [data[i] - data[i-1] for i in range(1, len(data))]

    description = """**Task: Difference Array**

Compute the difference array: diff[i] = arr[i] - arr[i-1] for all i >= 1.

**Agent Ordering:**
Agents hold CONSECUTIVE elements: 0 → 1 → ... → {max_id}

**Your Data (Position {agent_id}):**
{input_shard}

**Algorithm:**
- Compute differences within your segment
- First element of your segment needs the LAST element from previous agent

**Output:**
The complete difference array.

**Communication Protocol:**
Topology: Chain (0 → 1 → ... → {max_id}). Get boundary from left neighbor.
All agents must submit the same final answer using submit_result(global_diff_array)."""

    return case_func(
        case_id="II-17",
        case_name="Diff Array",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/car-pooling/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == diff(global_input)",
        optimal_topology="Chain (each agent → next agent), then collect and broadcast",
        optimal_message_count=f"{num_agents - 1} for boundaries + O(N) for sharing",
        output_type="distributed"
    )


def _generate_ii18_list_ranking(num_agents: int, case_func: Callable) -> Dict:
    """II-18: List Ranking - Linked list rank computation

    NOTE: This is a GLOBAL output task - all agents submit the same dictionary!

    FIX: 保存真正的头节点在第二次 shuffle 之前
    """

    total_size = num_agents * 8
    # Create a linked list structure
    nodes = list(range(total_size))
    random.shuffle(nodes)  # First shuffle: create logical chain order

    # Create next pointers (logical chain)
    next_pointers = {}
    for i in range(len(nodes) - 1):
        next_pointers[nodes[i]] = nodes[i + 1]
    next_pointers[nodes[-1]] = -1  # End of list

    # CRITICAL FIX: Save the true head before second shuffle
    true_head = nodes[0]  # This is the real head of the logical chain

    # Randomly distribute nodes to agents (second shuffle)
    random.shuffle(nodes)  # Second shuffle: for distribution to agents
    chunk_size = len(nodes) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(nodes)
        agent_nodes = []
        for node_id in nodes[start:end]:
            agent_nodes.append({"id": node_id, "next": next_pointers[node_id]})
        shards.append(agent_nodes)

    # Compute expected ranks (distance from head, i.e., list rank)
    head = true_head
    distances = {}
    current = head
    ordered_nodes = []
    while current != -1:
        distances[current] = len(ordered_nodes)  # rank from head
        ordered_nodes.append(current)
        current = next_pointers[current]

    expected_output = distances

    description = """**Task: List Ranking (Compute Rank from Head)**

Reconstruct a distributed linked list and compute each node's rank from the head.

**Data Distribution:**
- Total nodes: {total_size}, SCATTERED across agents
- Each node has "id" and "next" pointer (-1 for end)
- Forms ONE logical chain

**Your Data:**
Agent {{agent_id}} holds: {{input_shard}}

**Algorithm:**
1. Reconstruct the logical chain starting from head node
2. Compute each node's rank (head=0, next=1, ...)

**Output:**
Dictionary mapping node_id to its rank: {{node_id: rank, ...}}

**Communication Protocol:**
Topology: Share pointers to reconstruct chain, then broadcast ranks.
All agents must submit the same final answer using submit_result({{node_id: rank, ...}})."""

    return case_func(
        case_id="II-18",
        case_name="List Ranking",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/linked-list-cycle/",
        description=description.format(total_size=total_size),
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == compute_distances(nodes)",
        optimal_topology="Chain or pointer-jumping tree",
        optimal_message_count="O(N) to share pointers + O(log N) pointer jumping",
        output_type="distributed",
    )






def _generate_ii19_merge_neighbors(num_agents: int, case_func: Callable) -> Dict:
    """II-19: Merge/Dedup Neighbors - Boundary deduplication

    NOTE: This is a GLOBAL output task - all agents submit the same array!
    """

    # Create sorted segments with potential duplicates at boundaries
    total_size = num_agents * 15
    data = sorted([random.randint(1, 50) for _ in range(total_size)])

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Remove consecutive duplicates
    expected_output = []
    for i, val in enumerate(data):
        if i == 0 or data[i] != data[i-1]:
            expected_output.append(val)

    description = """**Task: Deduplicate Consecutive Elements**

Given sorted consecutive segments, remove consecutive duplicate elements globally.

**Agent Ordering:**
Agents hold SORTED CONSECUTIVE segments: 0 → 1 → ... → {max_id}

**Your Data (Position {agent_id}):**
Sorted segment: {input_shard}

**Algorithm:**
1. Remove consecutive duplicates within your segment
2. Check boundaries with neighbors to remove cross-boundary duplicates

**Output:**
A sorted array with no consecutive duplicates.

**Communication Protocol:**
Topology: Chain (0 ↔ 1 ↔ ... ↔ {max_id}). Compare boundaries with neighbors.
All agents must submit the same final answer using submit_result(global_deduped_array)."""

    return case_func(
        case_id="II-19",
        case_name="Merge Neighbors",
        paradigm="Paradigm II",
        leetcode_url="https://leetcode.com/problems/remove-duplicates-from-sorted-array/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == unique_consecutive(global_input)",
        optimal_topology="Chain with boundary comparison, then collect and broadcast",
        optimal_message_count=f"{2 * (num_agents - 1)} for boundaries + O(N) for sharing",
        output_type="distributed"
    )


def _generate_ii20_pipeline_hash(num_agents: int, case_func: Callable) -> Dict:
    """II-20: Pipeline Hash - Blockchain-style dependency

    NOTE: This is a SEGMENTED output task - each agent outputs their own hashes!
    """

    total_size = num_agents * 5
    data = [f"Block_{i}_Data" for i in range(total_size)]

    # Shard data
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute sequential hashes
    def simple_hash(prev_hash, block_data):
        """Simple hash: sum of ASCII values XOR prev_hash"""
        data_hash = sum(ord(c) for c in block_data) % 10000
        return (data_hash ^ prev_hash) % 10000

    expected_output = []
    current_hash = 0  # Genesis hash
    for block_data in data:
        current_hash = simple_hash(current_hash, block_data)
        expected_output.append(current_hash)

    # Shard expected output
    expected_shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(expected_output)
        expected_shards.append(expected_output[start:end])

    description = """**Task: Pipeline Hash (Blockchain Simulation)**

Compute a hash chain where each block's hash depends on the previous block's hash.

**Agent Ordering:**
Agents hold CONSECUTIVE blocks: 0 → 1 → 2 → ... → {max_id}

**Your Data (Position {agent_id}):**
Blocks: {input_shard}

**Algorithm:**
hash[i] = (sum(ASCII_values(block[i])) XOR hash[i-1]) % 10000
hash[0] = 0 (genesis)
- Agent i needs the FINAL HASH from Agent i-1 to start computing

**Output:**
Each agent submits their portion of hash values.

**Communication Protocol:**
Topology: Chain (0 → 1 → 2 → ... → {max_id}). Strict sequential dependency.
Each agent submits their own segment using submit_result(your_computed_hashes)."""

    return case_func(
        case_id="II-20",
        case_name="Pipeline Hash",
        paradigm="Paradigm II",
        leetcode_url="https://en.wikipedia.org/wiki/Blockchain",
        description=description,
        input_data=shards,
        expected_output=expected_shards,  # List of lists - each agent has different output
        verification_logic="concat(agent_outputs) == valid_blockchain",
        optimal_topology="Chain with strict sequential processing",
        optimal_message_count=f"{num_agents - 1} messages (hash pipeline)",
        output_type="distributed",
        is_segmented=True,
    )