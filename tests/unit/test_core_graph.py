from infraguard.core.graph import build_graph, dependencies_of, dependents_of


def test_dependents_of_transitive() -> None:
    graph = build_graph(["a", "b", "c"], [("b", "a"), ("c", "b")])  # c -> b -> a
    assert dependents_of(graph, "a") == {"b", "c"}


def test_dependencies_of_transitive() -> None:
    graph = build_graph(["a", "b", "c"], [("b", "a"), ("c", "b")])
    assert dependencies_of(graph, "c") == {"a", "b"}


def test_unknown_node_returns_empty_set() -> None:
    graph = build_graph(["a"], [])
    assert dependents_of(graph, "missing") == set()
    assert dependencies_of(graph, "missing") == set()


def test_isolated_node_included() -> None:
    graph = build_graph(["a", "b"], [])
    assert "a" in graph
    assert "b" in graph
    assert dependents_of(graph, "a") == set()
