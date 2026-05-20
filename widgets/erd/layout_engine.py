"""Sugiyama-style hierarchical auto-layout for ERD diagrams."""
from collections import deque


def _build_bidirectional_adjacency(schema_data: dict) -> dict:
    """Return an undirected adjacency list from FK relationships."""
    adj: dict = {name: [] for name in schema_data.keys()}
    for full_name, table_info in schema_data.items():
        for fk in table_info.get('foreign_keys', []):
            target = fk['table']
            if target in schema_data:
                adj[full_name].append(target)
                adj[target].append(full_name)
    return adj


def _detect_components(schema_data: dict, adj: dict) -> list[list[str]]:
    """Return connected components via stack-based DFS, largest first."""
    visited: set = set()
    components: list = []
    for name in schema_data.keys():
        if name not in visited:
            comp: list = []
            stack = [name]
            while stack:
                u = stack.pop()
                if u not in visited:
                    visited.add(u)
                    comp.append(u)
                    for v in adj[u]:
                        if v not in visited:
                            stack.append(v)
            if comp:
                components.append(comp)
    components.sort(key=len, reverse=True)
    return components


def _rank_component(comp_nodes: list, schema_data: dict) -> tuple[dict, dict, dict]:
    """
    Assign ranks (columns) to each node in one component via Kahn's BFS.
    Returns (sub_adj, ranks, layers) dictionaries.
    """
    sub_adj: dict = {n: [] for n in comp_nodes}
    sub_in_degree: dict = {n: 0 for n in comp_nodes}
    sub_total_degree: dict = {n: 0 for n in comp_nodes}

    for u in comp_nodes:
        info = schema_data[u]
        for fk in info.get('foreign_keys', []):
            target = fk['table']
            if target in sub_adj and target != u:
                sub_adj[target].append(u)
                sub_in_degree[u] += 1
                sub_total_degree[u] += 1
                sub_total_degree[target] += 1

    # --- STEP: RANKING (Sugiyama Layering) ---
    ranks: dict = {n: 0 for n in comp_nodes}
    queue: deque = deque(n for n in comp_nodes if sub_in_degree[n] == 0)
    while queue:
        u = queue.popleft()
        for v in sub_adj[u]:
            sub_in_degree[v] -= 1
            ranks[v] = max(ranks[v], ranks[u] + 1)
            if sub_in_degree[v] == 0:
                queue.append(v)

    layers: dict = {}
    for n in comp_nodes:
        r = ranks[n]
        if r not in layers:
            layers[r] = []
        layers[r].append(n)

    return sub_total_degree, ranks, layers


def _reduce_crossings(layers: dict, sub_total_degree: dict) -> None:
    """
    Sort nodes within each rank by degree (Barycenter heuristic) to reduce
    edge crossings, placing high-degree nodes in the center of each column.
    Mutates *layers* in-place.
    """
    for r in sorted(layers.keys()):
        nodes = layers[r]
        nodes.sort(key=lambda n: sub_total_degree[n], reverse=True)
        central: deque = deque()
        left = True
        for node in nodes:
            if left:
                central.appendleft(node)
            else:
                central.append(node)
            left = not left
        layers[r] = list(central)


def _position_component(
    comp_nodes: list,
    layers: dict,
    item_map: dict,
    current_y_offset: float,
) -> float:
    """
    Set item positions for one component using left-to-right flow.
    Returns the updated y-offset for the next component.
    """
    padding_x = 180
    padding_y = 60
    sorted_ranks = sorted(layers.keys())

    node_sizes = {
        n: (item_map[n].rect().width(), item_map[n].rect().height())
        for n in comp_nodes
    }

    layer_heights = []
    max_comp_height = 0.0
    for r in sorted_ranks:
        h = sum(node_sizes[n][1] + padding_y for n in layers[r]) - padding_y
        layer_heights.append(h)
        max_comp_height = max(max_comp_height, h)

    current_x = 100.0
    for i, r in enumerate(sorted_ranks):
        nodes = layers[r]
        max_w = max(node_sizes[n][0] for n in nodes)
        layer_h = layer_heights[i]
        start_y = current_y_offset + (max_comp_height - layer_h) / 2
        local_y = start_y
        for name in nodes:
            item_map[name].setPos(current_x, local_y)
            local_y += node_sizes[name][1] + padding_y
        current_x += max_w + padding_x

    return current_y_offset + max_comp_height + 150


def auto_layout(schema_data: dict, item_map: dict) -> None:
    """
    Apply Sugiyama-style hierarchical layout to all items in *item_map*.

    Mutates item positions directly via QGraphicsItem.setPos().
    """
    if not item_map:
        return

    adj = _build_bidirectional_adjacency(schema_data)
    components = _detect_components(schema_data, adj)

    current_y_offset = 100.0
    for comp_nodes in components:
        sub_total_degree, _ranks, layers = _rank_component(comp_nodes, schema_data)
        _reduce_crossings(layers, sub_total_degree)
        current_y_offset = _position_component(
            comp_nodes, layers, item_map, current_y_offset
        )
