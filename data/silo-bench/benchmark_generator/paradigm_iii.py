"""
Paradigm III: Unstructured / Global / Shuffle Motifs
Cases III-21 to III-30

Characteristics:
- Complex data dependencies requiring global communication
- Random/unstructured data distribution
- Requires data shuffling, all-to-all communication, or complex routing
- Optimal topology: Fully connected, all-to-all, or sample-based partitioning
- Theoretical message complexity: O(N log N) to O(N²)
"""

import random
from typing import List, Dict, Any, Callable

# Set random seed for reproducibility
random.seed(42)


def generate_paradigm_iii_cases(num_agents: int, case_structure_func: Callable) -> List[Dict]:
    """Generate all Paradigm III benchmark cases"""
    cases = []

    # III-21: Distributed Sort
    cases.append(_generate_iii21_distributed_sort(num_agents, case_structure_func))

    # III-22: Median of Medians
    cases.append(_generate_iii22_median(num_agents, case_structure_func))

    # III-23: Graph Components
    cases.append(_generate_iii23_graph_components(num_agents, case_structure_func))

    # III-24: BFS Distance
    cases.append(_generate_iii24_bfs_distance(num_agents, case_structure_func))

    # III-25: K-Means Iteration
    cases.append(_generate_iii25_kmeans(num_agents, case_structure_func))

    # III-26: Global Distinct
    cases.append(_generate_iii26_global_distinct(num_agents, case_structure_func))

    # III-27: Collaborative Filtering
    cases.append(_generate_iii27_collaborative_filtering(num_agents, case_structure_func))

    # III-28: PageRank Step
    cases.append(_generate_iii28_pagerank(num_agents, case_structure_func))

    # III-29: Load Balance
    cases.append(_generate_iii29_load_balance(num_agents, case_structure_func))

    # III-30: Matrix Multiply
    cases.append(_generate_iii30_matrix_multiply(num_agents, case_structure_func))

    return cases


def _generate_iii21_distributed_sort(num_agents: int, case_func: Callable) -> Dict:
    """III-21: Distributed Sort - Global data redistribution

    NOTE: This is a SEGMENTED output task - each agent outputs their own sorted range!
    """

    total_size = num_agents * 20
    data = [random.randint(1, 1000) for _ in range(total_size)]

    # RANDOMLY shuffle and distribute (not sequential!)
    random.shuffle(data)
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Expected: globally sorted, with each agent holding a range
    sorted_data = sorted(data)
    expected_shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(sorted_data)
        expected_shards.append(sorted_data[start:end])

    description = """**Task: Distributed Sorting**

Sort the global dataset so that Agent 0 holds smallest values, Agent {max_id} holds largest.

**Data Distribution:**
RANDOM - your data may belong to other agents' final ranges.

**Your Data (RANDOM):**
Agent {agent_id} holds: {input_shard}

**Algorithm:**
1. Determine value ranges for each agent
2. SHUFFLE data between agents
3. Each agent sorts their final range

**Output:**
Each agent submits their sorted portion (concatenated result should be fully sorted).

**Communication Protocol:**
Topology: All-to-All / Hash-based shuffle. Global data exchange required.
Each agent submits their own segment using submit_result(your_sorted_range)."""

    return case_func(
        case_id="III-21",
        case_name="Distributed Sort",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/sort-an-array/",
        description=description,
        input_data=shards,
        expected_output=expected_shards,
        verification_logic="concat(agent_outputs) == sorted(global_input)",
        optimal_topology="All-to-all or sample-based partitioning",
        optimal_message_count=f"O(N) to O(N²) depending on strategy",
        output_type="distributed",
        is_segmented=True,   # ✅ NEW
    )



def _generate_iii22_median(num_agents: int, case_func: Callable) -> Dict:
    """III-22: Median of Medians - Iterative convergence

    NOTE: This is a GLOBAL output task - all agents submit the same median value!
    """

    total_size = num_agents * 25
    data = [random.randint(1, 1000) for _ in range(total_size)]

    # Randomly shard
    random.shuffle(data)
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    # Compute expected median
    sorted_data = sorted(data)
    median_idx = len(sorted_data) // 2
    expected_output = sorted_data[median_idx]

    description = f"""**Task: Global Median (Iterative)**

Find the median value without collecting all data (use iterative consensus).

**Data Distribution:**
RANDOM across agents. Total elements: {total_size}, median at position {median_idx}.

**Your Data (RANDOM):**
Agent {{agent_id}} holds: {{input_shard}}

**Algorithm (Iterative):**
1. Each agent computes local median/quantiles
2. Estimate global pivot from local medians
3. Each agent counts: values < pivot, = pivot, > pivot
4. Determine which range contains median, repeat until convergence

**Output:**
A single integer representing the global median.

**Communication Protocol:**
Topology: All-to-All. Multiple rounds of coordination required.
All agents must submit the same final answer using submit_result(median_value)."""

    return case_func(
        case_id="III-22",
        case_name="Median of Medians",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/find-median-from-data-stream/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == median(global_data)",
        optimal_topology="Iterative broadcast and aggregation",
        optimal_message_count=f"O(N log N) - multiple rounds of coordination",
        output_type="distributed"
    )


def _generate_iii23_graph_components(num_agents: int, case_func: Callable) -> Dict:
    """III-23: Graph Connected Components - Distributed union-find

    NOTE: This is a GLOBAL output task - all agents submit the same component count!
    """

    # Create a random graph
    num_nodes = num_agents * 10
    nodes = list(range(num_nodes))

    # Generate random edges to create some connected components
    edges = []
    for _ in range(num_nodes * 2):
        u = random.randint(0, num_nodes - 1)
        v = random.randint(0, num_nodes - 1)
        if u != v:
            edges.append((u, v))

    # Randomly distribute edges to agents
    random.shuffle(edges)
    chunk_size = len(edges) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(edges)
        shards.append(edges[start:end])

    # Compute expected components using Union-Find
    parent = list(range(num_nodes))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for u, v in edges:
        union(u, v)

    # Count components
    component_roots = len(set(find(i) for i in range(num_nodes)))
    expected_output = component_roots

    description = f"""**Task: Graph Connected Components**

Find the number of connected components in an undirected graph with randomly distributed edges.

**Data Distribution:**
Total nodes: {num_nodes}. Edges RANDOMLY distributed across agents.

**Your Data (RANDOM edges):**
Agent {{agent_id}} holds: {{input_shard}} (each edge is tuple (u, v))

**Algorithm:**
Use Union-Find. Coordinate to merge components connected through edges held by different agents.

**Output:**
A single integer representing the number of connected components.

**Communication Protocol:**
Topology: All-to-All or Hash-based. Share component membership information.
All agents must submit the same final answer using submit_result(component_count)."""

    return case_func(
        case_id="III-23",
        case_name="Graph Components",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/number-of-connected-components-in-an-undirected-graph/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == networkx.connected_components(graph)",
        optimal_topology="Hash-based partitioning or all-to-all coordination",
        optimal_message_count=f"O(N) to O(N²) depending on coordination strategy",
        output_type="distributed"
    )


def _generate_iii24_bfs_distance(num_agents: int, case_func: Callable) -> Dict:
    """III-24: BFS Distance - Multi-hop message propagation

    NOTE: This is a GLOBAL output task - all agents submit the same distance dictionary!
    """

    num_nodes = num_agents * 8
    # Create a random graph (adjacency list)
    graph = {i: [] for i in range(num_nodes)}
    edges = []
    for _ in range(num_nodes * 2):
        u = random.randint(0, num_nodes - 1)
        v = random.randint(0, num_nodes - 1)
        if u != v and v not in graph[u]:
            graph[u].append(v)
            graph[v].append(u)
            edges.append((u, v))

    # Randomly distribute edges
    random.shuffle(edges)
    chunk_size = len(edges) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(edges)
        shards.append(edges[start:end])

    # Compute BFS distances from source node 0
    from collections import deque
    source = 0
    distances = {i: -1 for i in range(num_nodes)}
    distances[source] = 0
    queue = deque([source])

    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if distances[neighbor] == -1:
                distances[neighbor] = distances[node] + 1
                queue.append(neighbor)

    expected_output = distances

    description = f"""**Task: BFS Distance (Single-Source Shortest Path)**

Compute shortest distance from source node 0 to all nodes in an unweighted graph.

**Data Distribution:**
Total nodes: {num_nodes}. Edges RANDOMLY distributed. Source: node 0.

**Your Data (RANDOM edges):**
Agent {{agent_id}} holds: {{input_shard}}

**Algorithm:**
BFS wave propagation. Messages must propagate along edges held by different agents.

**Output:**
Dictionary mapping node_id to distance_from_source (-1 if unreachable).

**Communication Protocol:**
Topology: Multi-hop message passing along graph structure.
All agents must submit the same final answer using submit_result(complete_distance_dict)."""

    return case_func(
        case_id="III-24",
        case_name="BFS Distance",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/01-matrix/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == bfs(graph, source=0)",
        optimal_topology="Dynamic message routing along graph edges",
        optimal_message_count=f"O(N × E) - proportional to graph edges",
        output_type="distributed"
    )


def _generate_iii25_kmeans(num_agents: int, case_func: Callable) -> Dict:
    """III-25: K-Means Iteration - Clustering coordination

    NOTE: This is a GLOBAL output task - all agents submit the same new centroids!
    """

    K = 3
    total_points = num_agents * 20

    # Generate random 2D points
    points = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(total_points)]

    # Initialize centroids
    initial_centroids = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(K)]

    # Randomly distribute points
    random.shuffle(points)
    chunk_size = len(points) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(points)
        shards.append(points[start:end])

    # Perform one K-means iteration
    def distance(p1, p2):
        return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) ** 0.5

    # Assign points to clusters
    clusters = [[] for _ in range(K)]
    for point in points:
        closest_k = min(range(K), key=lambda k: distance(point, initial_centroids[k]))
        clusters[closest_k].append(point)

    # Compute new centroids
    new_centroids = []
    for k in range(K):
        if clusters[k]:
            cx = sum(p[0] for p in clusters[k]) / len(clusters[k])
            cy = sum(p[1] for p in clusters[k]) / len(clusters[k])
            new_centroids.append((round(cx, 2), round(cy, 2)))
        else:
            x, y = initial_centroids[k]
            new_centroids.append((round(x, 2), round(y, 2)))

    expected_output = new_centroids

    description = f"""**Task: K-Means Clustering (One Iteration)**

Perform ONE iteration of K-Means to update {K} cluster centroids.

**Data Distribution:**
2D points RANDOMLY distributed. Initial centroids: {initial_centroids}

**Your Data (RANDOM points):**
Agent {{agent_id}} holds: {{input_shard}}

**Algorithm:**
1. Assign each point to nearest centroid
2. Compute new centroids as mean of assigned points
3. Aggregate statistics across agents (sum_x, sum_y, count per cluster)

**Output:**
List of {K} centroids: [(x0, y0), (x1, y1), (x2, y2)]

**Communication Protocol:**
Topology: All-to-All or cluster-based shuffle. Aggregate by cluster ID.
All agents must submit the same final answer using submit_result([(x0, y0), ...])."""

    return case_func(
        case_id="III-25",
        case_name="K-Means Iteration",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/best-meeting-point/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == kmeans_iter(points, K)",
        optimal_topology="Shuffle by cluster ID or all-to-all",
        optimal_message_count=f"O(K × N) - statistics per cluster",
        output_type="distributed"
    )


def _generate_iii26_global_distinct(num_agents: int, case_func: Callable) -> Dict:
    """III-26: Global Distinct - Hash-based deduplication

    NOTE: This is a GLOBAL output task - all agents submit the same distinct count!
    """

    total_size = num_agents * 30
    unique_elements = list(range(total_size // 2))  # Lots of duplicates
    data = [random.choice(unique_elements) for _ in range(total_size)]

    # Randomly distribute
    random.shuffle(data)
    chunk_size = len(data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(data)
        shards.append(data[start:end])

    expected_output = len(set(data))

    description = """**Task: Global Distinct Count (Hash-Based)**

Count the total DISTINCT elements using hash-based deduplication.

**Data Distribution:**
RANDOM with duplicates. Same element may appear in multiple agents.

**Your Data (RANDOM with duplicates):**
Agent {agent_id} holds: {input_shard}

**Algorithm:**
1. Hash-based partitioning: bucket_id = hash(element) % {num_agents}
2. SHUFFLE elements to owner agents
3. Each agent deduplicates their buckets
4. Aggregate counts

**Output:**
A single integer representing the global distinct count.

**Communication Protocol:**
Topology: All-to-All shuffle by hash.
All agents must submit the same final answer using submit_result(global_distinct_count)."""

    return case_func(
        case_id="III-26",
        case_name="Global Distinct",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/intersection-of-two-arrays/",
        description=description,
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == len(set(global_input))",
        optimal_topology="Hash-based shuffle (all-to-all by hash)",
        optimal_message_count=f"O(N) elements shuffled",
        output_type="distributed"
    )


def _generate_iii27_collaborative_filtering(num_agents: int, case_func: Callable) -> Dict:
    """III-27: Collaborative Filtering - All-pairs scoring

    NOTE: This is a GLOBAL output task - all agents submit the same top-K list!

    FIX 1: 使用 K=3 避免与 num_agents=5 冲突导致 is_segmented 误判
    FIX 2: 使用元组标记数据类型避免 User/Item ID 混淆
    """

    num_users = num_agents * 3
    num_items = num_agents * 3
    K = 3  # FIX: Use K=3 instead of K=5 to avoid confusion with num_agents

    # Generate random user and item vectors
    user_vectors = {i: [random.uniform(0, 1) for _ in range(5)] for i in range(num_users)}
    item_vectors = {i: [random.uniform(0, 1) for _ in range(5)] for i in range(num_items)}

    # FIX: Distribute users and items with explicit type tagging to avoid ID confusion
    all_data = [("user", k, v) for k, v in user_vectors.items()] + \
               [("item", k, v) for k, v in item_vectors.items()]
    random.shuffle(all_data)

    chunk_size = len(all_data) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(all_data)
        agent_data = {"users": {}, "items": {}}

        # FIX: Use type tag to distinguish users from items
        for data_type, data_id, vector in all_data[start:end]:
            if data_type == "user":
                agent_data["users"][data_id] = vector
            else:  # data_type == "item"
                agent_data["items"][data_id] = vector

        shards.append(agent_data)

    # Compute top-K user-item pairs by dot product
    def dot_product(v1, v2):
        return sum(a * b for a, b in zip(v1, v2))

    scores = []
    for uid, uvec in user_vectors.items():
        for iid, ivec in item_vectors.items():
            score = dot_product(uvec, ivec)
            scores.append((uid, iid, round(score, 4)))

    scores.sort(key=lambda x: x[2], reverse=True)
    expected_output = scores[:K]  # FIX: Top K pairs (K=3, not 5)

    description = """**Task: Collaborative Filtering (Top User-Item Pairs)**

Find the top {K} user-item pairs with highest compatibility scores (dot product).

**Data Distribution:**
User/Item vectors RANDOMLY distributed. Each has 5-dim feature vector.

**Your Data (RANDOM):**
Agent {{agent_id}} holds: {{input_shard}} (dict with "users" and "items" keys)

**Algorithm:**
1. Compute dot products for ALL (user, item) pairs
2. Find top {K} pairs with highest scores
3. score(user, item) = dot_product(user_vector, item_vector)

**Output:**
List of top {K} tuples: [(user_id, item_id, score), ...]

**Communication Protocol:**
Topology: All-to-All. This is O(users × items) computation.
All agents must submit the same final answer using submit_result([(uid, iid, score), ...])."""

    return case_func(
        case_id="III-27",
        case_name="Collaborative Filtering",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/two-sum/",
        description=description.format(num_users=num_users, num_items=num_items, K=K),
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == top_dot_products(users, items)",
        optimal_topology="Broadcast or hash-based partitioning",
        optimal_message_count=f"O(users × items) = O(N²)",
        output_type="distributed"
    )


def _generate_iii28_pagerank(num_agents: int, case_func: Callable) -> Dict:
    """III-28: PageRank Step - Graph value propagation

    NOTE: This is a GLOBAL output task - all agents submit the same rank dictionary!
    """

    num_nodes = num_agents * 8
    # Create random directed graph
    graph = {i: [] for i in range(num_nodes)}
    edges = []
    for _ in range(num_nodes * 2):
        u = random.randint(0, num_nodes - 1)
        v = random.randint(0, num_nodes - 1)
        if u != v and v not in graph[u]:
            graph[u].append(v)
            edges.append((u, v))

    # Initial PageRank values (uniform)
    initial_ranks = {i: 1.0 / num_nodes for i in range(num_nodes)}

    # Randomly distribute edges
    random.shuffle(edges)
    chunk_size = len(edges) // num_agents
    shards = []
    for i in range(num_agents):
        start = i * chunk_size
        end = start + chunk_size if i < num_agents - 1 else len(edges)
        shards.append(edges[start:end])

    # Compute one PageRank iteration
    damping = 0.85
    new_ranks = {i: (1 - damping) / num_nodes for i in range(num_nodes)}

    for node in range(num_nodes):
        out_degree = len(graph[node])
        if out_degree > 0:
            contribution = damping * initial_ranks[node] / out_degree
            for neighbor in graph[node]:
                new_ranks[neighbor] += contribution

    expected_output = {k: round(v, 6) for k, v in new_ranks.items()}

    description = """**Task: PageRank (One Iteration)**

Compute one iteration of PageRank on a directed graph.

**Data Distribution:**
Total nodes: {num_nodes}. Edges RANDOMLY distributed. Initial ranks: uniform.

**Your Data (RANDOM edges):**
Agent {{agent_id}} holds: {{input_shard}}

**Algorithm:**
rank'[v] = (1-d)/{num_nodes} + d × Σ(rank[u]/out_degree[u]) for all u→v
where d = 0.85 (damping factor)

**Output:**
Dictionary mapping node_id to rank_value.

**Communication Protocol:**
Topology: All-to-All with message routing along edges.
All agents must submit the same final answer using submit_result(complete_rank_dict)."""

    return case_func(
        case_id="III-28",
        case_name="PageRank Step",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/course-schedule/",
        description=description.format(num_nodes=num_nodes),
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == pagerank_iter(graph)",
        optimal_topology="Node-based partitioning with message routing",
        optimal_message_count=f"O(N × E) - proportional to edges",
        output_type="distributed"
    )


def _generate_iii29_load_balance(num_agents: int, case_func: Callable) -> Dict:
    """III-29: Load Balance - Deterministic greedy redistribution (unique ground truth)

    NOTE: This is a GLOBAL output task - all agents submit the same statistics!

    FIX: 确保所有任务都被分配给 agents
    """

    total_tasks = num_agents * 20
    # Generate tasks with varying durations (very unbalanced initially)
    tasks = []
    for i in range(total_tasks):
        if i % 10 == 0:
            duration = random.randint(50, 100)  # Heavy tasks
        else:
            duration = random.randint(1, 10)  # Light tasks
        tasks.append({"id": i, "duration": duration})

    # FIX: Deliberately unbalanced but COMPLETE distribution
    heavy_tasks = [t for t in tasks if t["id"] % 10 == 0]
    light_tasks = [t for t in tasks if t["id"] % 10 != 0]

    shards = []

    # Agent 0 gets all heavy tasks (highly overloaded)
    shards.append(heavy_tasks)

    # Remaining agents split the light tasks
    if num_agents > 1:
        light_chunk_size = len(light_tasks) // (num_agents - 1)
        for i in range(1, num_agents):
            start = (i - 1) * light_chunk_size
            if i < num_agents - 1:
                end = start + light_chunk_size
            else:
                end = len(light_tasks)  # Last agent gets remaining tasks
            shards.append(light_tasks[start:end])

    # Verify all tasks are assigned
    total_assigned = sum(len(shard) for shard in shards)
    assert total_assigned == total_tasks, f"Task assignment error: {total_assigned} != {total_tasks}"

    # Compute expected balanced distribution (DETERMINISTIC GREEDY: LPT)
    total_duration = sum(t["duration"] for t in tasks)
    target_per_agent = total_duration / num_agents

    # Sort tasks by duration (largest first)
    sorted_tasks = sorted(tasks, key=lambda t: t["duration"], reverse=True)
    agent_loads = [0] * num_agents
    agent_assignments = [[] for _ in range(num_agents)]

    # Deterministic tie-break: if multiple agents share the same min load, pick the smallest agent id
    for task in sorted_tasks:
        min_agent = min(range(num_agents), key=lambda i: agent_loads[i])
        agent_assignments[min_agent].append(task)
        agent_loads[min_agent] += task["duration"]

    expected_output = {
        "variance": round(sum((load - target_per_agent) ** 2 for load in agent_loads) / num_agents, 2),
        "max_load": max(agent_loads),
        "min_load": min(agent_loads),
    }

    description = """**Task: Load Balancing (Deterministic Greedy LPT)**

Redistribute tasks using a deterministic algorithm (LPT - Longest Processing Time first).

**Data Distribution:**
Severely UNBALANCED. Total tasks: {total_tasks}, total duration: {total_duration}.

**Your Data (UNBALANCED):**
Agent {{agent_id}} holds: {{input_shard}}

**Algorithm (MUST follow exactly):**
1. Collect ALL tasks globally
2. Sort by duration descending
3. Greedily assign to agent with minimum load (tie-break: smallest agent id)
4. Compute: variance, max_load, min_load

**Output:**
Statistics dict: {{"variance": X, "max_load": Y, "min_load": Z}}

**Communication Protocol:**
Topology: All-to-All share tasks, then compute and broadcast.
All agents must submit the same final answer using submit_result(stats_dict)."""

    return case_func(
        case_id="III-29",
        case_name="Load Balance",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/split-array-largest-sum/",
        description=description.format(
            total_tasks=total_tasks,
            total_duration=total_duration,
            target_per_agent=target_per_agent,
        ),
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == expected_stats_from_greedy_lpt",
        optimal_topology="All-to-all share tasks + one coordinator (or all compute)",
        optimal_message_count=f"O(N²) to share tasks + O(N) broadcast stats",
        output_type="distributed",
    )



def _generate_iii30_matrix_multiply(num_agents: int, case_func: Callable) -> Dict:
    """III-30: Matrix Multiply - Distributed linear algebra

    NOTE: This is a GLOBAL output task - all agents submit the same result matrix!

    FIX: 确保所有矩阵数据都被完整分配
    Strategy: 每个 agent 获得 A 的一部分行 AND B 的完整矩阵
    """

    # FIX: Use dimension that matches num_agents for easier complete distribution
    dim = num_agents  # Matrix dimension = num_agents for simplicity
    A = [[random.randint(1, 10) for _ in range(dim)] for _ in range(dim)]
    B = [[random.randint(1, 10) for _ in range(dim)] for _ in range(dim)]

    # FIX: New distribution strategy - each agent gets:
    # - Some rows of A (to compute their assigned output rows)
    # - Complete matrix B (needed to compute any row of C)
    shards = []
    rows_per_agent = dim // num_agents

    for i in range(num_agents):
        # Calculate which rows of A this agent is responsible for
        start_row = i * rows_per_agent
        if i < num_agents - 1:
            end_row = start_row + rows_per_agent
        else:
            end_row = dim  # Last agent gets remaining rows

        agent_data = {
            "type": "rows_and_full_B",
            "A_rows": A[start_row:end_row],
            "A_row_indices": list(range(start_row, end_row)),
            "B_matrix": B  # Each agent gets complete B
        }
        shards.append(agent_data)

    # Compute expected result: C = A × B
    C = [[sum(A[i][k] * B[k][j] for k in range(dim)) for j in range(dim)] for i in range(dim)]

    expected_output = C

    description = """**Task: Distributed Matrix Multiplication**

Compute C = A × B where matrix A is row-partitioned across agents.

**Data Distribution:**
Matrix {dim}×{dim}. Each agent has rows of A and complete B.

**Your Data:**
Agent {{agent_id}} holds: {{input_shard}}
- A_rows: Your assigned rows from A
- A_row_indices: Which rows you have
- B_matrix: Complete matrix B

**Algorithm:**
C[i,j] = Σ(A[i,k] × B[k,j]) for k = 0 to {dim_minus_1}
You can compute your assigned rows locally, then share.

**Output:**
The complete {dim}×{dim} result matrix C.

**Communication Protocol:**
Topology: All-to-All for sharing computed rows.
All agents must submit the same final answer using submit_result(C)."""

    return case_func(
        case_id="III-30",
        case_name="Matrix Multiply",
        paradigm="Paradigm III",
        leetcode_url="https://leetcode.com/problems/sparse-matrix-multiplication/",
        description=description.format(dim=dim, dim_minus_1=dim - 1),
        input_data=shards,
        expected_output=expected_output,
        verification_logic="all(agent_outputs) == np.matmul(A, B)",
        optimal_topology="All-to-all for row result sharing",
        optimal_message_count=f"O(N²) = O(dim²) elements communicated",
        output_type="distributed"
    )