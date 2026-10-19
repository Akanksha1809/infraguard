# Module B — Infrastructure Failure-Domain Simulator

## What it does

Takes a declarative infrastructure topology (YAML or JSON) and simulates the failure of one
or more components or entire failure domains, computing exactly what else becomes
unreachable, whether any single point of failure exists, and how much capacity survives —
all as a deterministic consequence of the topology you declared, never as a claim about a
real system's actual availability.

## The model, defined precisely

This section exists because the brief explicitly requires it: **no vague availability
claims.** Every term below means exactly this and nothing more.

- **Component**: one node in the topology (`id`, `name`, `kind`, optional
  `failure_domain`, `capacity`, `redundancy_group`).
- **Dependency**: a directed edge `from_id -> to_id` with `required: true|false`.
  - `required: true` (the default): if the target becomes fully unavailable, the dependent
    is also considered unavailable. This is the only mechanism that propagates failure.
  - `required: false`: never propagates failure. A report notes a degraded optional
    dependency but the dependent is still considered up.
- **Redundancy group**: components sharing the same `redundancy_group` are treated as fully
  interchangeable peers. **Which specific peer actually serves a given request is not
  modeled** — this is a deliberate simplification, stated here rather than left implicit.
- **Logical node**: a redundancy_group if the component declares one, otherwise the
  component itself (a singleton group of one).
- **Down**: a component is down if it was explicitly failed by the scenario, OR if it has
  at least one required dependency whose target's entire logical node (ALL members) is
  down. This is computed as a monotonic fixed point — once down, always down for that
  scenario — so propagation always terminates.
- **Single point of failure (SPOF)**: a component whose failure, *alone*, causes at least
  one other component to go down. Concretely: simulate failing only that component; if the
  resulting blast radius is non-empty, it's a SPOF. A component with a surviving redundant
  peer is never flagged this way, because its logical node isn't fully down when just one
  member fails.
- **Dependency without redundancy**: a static (no simulation needed) check — a required
  dependency whose target's logical node has exactly one member.
- **Surviving capacity**: `sum(capacity of up members) / sum(capacity of all members)` for
  a logical node, computed **only if every member declares a `capacity` value**. If any
  member's capacity is undeclared, the ratio is reported as unknown — never assumed to be 0
  or 1. Capacity units are arbitrary and only meaningful relative to other members of the
  *same* group; comparing capacity across groups means nothing.
- **Blast radius**: the full set of components that end up down (explicit + cascaded) for a
  given scenario.

**What this explicitly does not model**, stated rather than hidden: network partitions,
correlated/simultaneous unrelated failures, provider-specific behavior, retry/backoff
behavior, or any numeric availability percentage. This is a structural analysis of a
declared graph, not a measurement of a real system.

## Topology format

```yaml
name: my-topology
description: optional
components:
  - id: app-1
    name: App instance 1
    kind: app                  # free-form label
    failure_domain: zone-a      # optional
    capacity: 100                # optional, arbitrary units
    redundancy_group: app         # optional
dependencies:
  - from_id: app-1
    to_id: db
    required: true               # default
```

## CLI and API

```bash
infraguard validate-topology --file topology.yaml [--format json|markdown|both] [--out DIR]
infraguard simulate-failure --topology topology.yaml \
    [--failure COMPONENT_ID ...] [--failure-domain DOMAIN ...] \
    [--format json|markdown|both] [--out DIR]
```

`--failure` and `--failure-domain` are each repeatable, so multiple simultaneous failures
(e.g. two components in different domains) are supported in one scenario.

```
POST /api/v1/failure-simulation/validate-topology   {"topology": {...}}
POST /api/v1/failure-simulation/simulate-failure     {"topology": {...}, "scenario": {...}}
```

Unlike Module A, there is no pass/fail CI policy here — a what-if simulation has no
inherent "should this block CI" meaning. Both commands exit 0 on success and 2 on invalid
input (missing file, malformed topology, bad YAML/JSON).

## Validation

`validate-topology` reports, as fatal errors (nothing sound to analyze):
duplicate component ids, a dependency referencing an unknown component id, a
self-referential dependency, or a document root that isn't an object.

It reports, as non-fatal warnings (analysis still proceeds): a dependency cycle, a
redundancy_group with only one member (provides no actual redundancy), or no component
declaring any `failure_domain` (domain-level scenarios would have nothing to target).

It also prints the dependency graph in machine-readable form (`report.inputs.graph`:
`{"nodes": [...], "edges": [...]}`).

## The three example topologies

All three live under [examples/topologies/](../examples/topologies/) and were actually run
through `simulate-failure` to produce the numbers below — not asserted from description.

| Topology | Scenario | Result |
|---|---|---|
| [fragile-single-instance.yaml](../examples/topologies/fragile-single-instance.yaml) | fail `app` | Cascades fully: `lb` and `client` also go down. Every one of `lb`/`app`/`db` is independently a SPOF. |
| [redundant-app-shared-db-bottleneck.yaml](../examples/topologies/redundant-app-shared-db-bottleneck.yaml) | fail `db` | Cascades fully (`app-1`, `app-2`, `lb`, `client`) **despite the app tier having two redundant instances** — because the shared database has no redundancy. `app-1`/`app-2` individually are *not* SPOFs (their peer covers for them); `db` and `lb` are. |
| [multi-zone-redundant.yaml](../examples/topologies/multi-zone-redundant.yaml) | fail failure-domain `zone-a` (takes down `app-1`, `db-primary`, `lb-a` at once) | **Zero cascade.** `client` stays up via `lb-b` → `app-2` → `db-replica`. No SPOFs, no redundancy gaps. Capacity drops to 50% everywhere but nothing goes down. |

This is the concrete demonstration the brief asks for: the same client-to-database shape,
three different redundancy designs, three structurally different outcomes — including the
non-obvious one (topology 2) where tier-level redundancy alone does not save you from a
shared dependency with none.

## Findings produced

| Rule ID | Scope | Confidence | Notes |
|---|---|---|---|
| `single_point_of_failure` | whole topology | heuristic | Only as sound as the declared dependencies/redundancy groups. |
| `dependency_without_redundancy` | whole topology | confirmed | Read directly from the topology structure. |
| `component_failed_explicit` | this scenario | confirmed | The scenario said so directly. |
| `component_down_cascaded` | this scenario | heuristic | Includes the specific dependency/redundancy-group reason in `evidence`, i.e. the propagation path. |
| `capacity_degraded` | this scenario | confirmed | Only emitted where capacity data is complete for that group. |
| `topology_warning.*` | whole topology | confirmed | Cycles, single-member groups, missing failure domains. |

## Known limitations (stated, not hidden)

- Redundancy is "all members interchangeable"; there is no partial/weighted routing model.
- A dependency cycle doesn't break propagation (the algorithm is a monotonic fixed point
  regardless), but is still unusual enough to warrant a warning.
- Capacity comparisons are only meaningful within one redundancy group, never across groups.
- No notion of time, request-level behavior, or retry semantics — this is a point-in-time
  structural snapshot of "what's up" given a failure.
