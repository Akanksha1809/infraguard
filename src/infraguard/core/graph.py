"""Thin, shared wrapper around NetworkX for dependency/failure graphs.

Module A (change impact) and Module B (failure simulation) both need "what does this
affect" and "what does this depend on" queries over a directed graph of resource
addresses. Keeping that logic here means both modules share one implementation instead of
each growing a slightly different graph traversal.
"""

import networkx as nx


def build_graph(nodes: list[str], edges: list[tuple[str, str]]) -> nx.DiGraph:
    """Build a directed graph. An edge (a, b) means "a depends on b".

    Nodes not mentioned in any edge are still included, as isolated nodes, so every known
    resource appears in the graph even if no dependency was detected for it.
    """
    graph: nx.DiGraph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    for src, dst in edges:
        graph.add_edge(src, dst)
    return graph


def dependents_of(graph: nx.DiGraph, node: str) -> set[str]:
    """Resources that depend on `node` (directly or transitively) — i.e. what breaks/changes
    if `node` is removed or replaced. Returns an empty set for an unknown node rather than
    raising, since "no known dependents" and "node not in graph" both mean the same thing to
    a caller doing impact analysis.
    """
    if node not in graph:
        return set()
    reversed_graph = graph.reverse(copy=False)
    return nx.descendants(reversed_graph, node)


def dependencies_of(graph: nx.DiGraph, node: str) -> set[str]:
    """Resources that `node` depends on (directly or transitively)."""
    if node not in graph:
        return set()
    return nx.descendants(graph, node)
