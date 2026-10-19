# InfraGuard Report — failure_simulation

- **Run ID:** `cf3b395941244352b7e9dc2a13082a34`
- **Created:** 2026-10-19T17:35:36.119679+00:00
- **Schema version:** 1

## Findings (10)

### [HIGH] 'lb' is a single point of failure (`single_point_of_failure`, confidence: heuristic)

Simulating only 'lb' failing causes 1 other component(s) to go down, per this topology's declared dependencies and redundancy groups. This is only as sound as those declarations — it is not a measurement of the real system.

- **Affected resources:** client, lb
- **Evidence:** `{'failed': 'lb', 'cascaded': ['client']}`
- **Remediation:** Give 'lb' a redundant peer (same redundancy_group), or mark dependents' dependency on it as optional if that's accurate.

### [HIGH] 'db' is a single point of failure (`single_point_of_failure`, confidence: heuristic)

Simulating only 'db' failing causes 4 other component(s) to go down, per this topology's declared dependencies and redundancy groups. This is only as sound as those declarations — it is not a measurement of the real system.

- **Affected resources:** app-1, app-2, client, db, lb
- **Evidence:** `{'failed': 'db', 'cascaded': ['app-1', 'app-2', 'client', 'lb']}`
- **Remediation:** Give 'db' a redundant peer (same redundancy_group), or mark dependents' dependency on it as optional if that's accurate.

### [HIGH] 'db' fails in this scenario (`component_failed_explicit`, confidence: confirmed)

'db' was explicitly failed by this scenario.

- **Affected resources:** db

### [HIGH] 'app-1' goes down as a consequence (`component_down_cascaded`, confidence: heuristic)

'app-1' was not directly failed, but goes down due to a required dependency on 'db', whose redundancy group (db) is entirely down.

- **Affected resources:** app-1, db
- **Evidence:** `{'dependency_target': 'db', 'reason': "required dependency on 'db', whose redundancy group (db) is entirely down"}`
- **Remediation:** Add redundancy for 'db', or confirm 'app-1' genuinely cannot tolerate that dependency being unavailable.

### [HIGH] 'app-2' goes down as a consequence (`component_down_cascaded`, confidence: heuristic)

'app-2' was not directly failed, but goes down due to a required dependency on 'db', whose redundancy group (db) is entirely down.

- **Affected resources:** app-2, db
- **Evidence:** `{'dependency_target': 'db', 'reason': "required dependency on 'db', whose redundancy group (db) is entirely down"}`
- **Remediation:** Add redundancy for 'db', or confirm 'app-2' genuinely cannot tolerate that dependency being unavailable.

### [HIGH] 'client' goes down as a consequence (`component_down_cascaded`, confidence: heuristic)

'client' was not directly failed, but goes down due to a required dependency on 'lb', whose redundancy group (lb) is entirely down.

- **Affected resources:** client, lb
- **Evidence:** `{'dependency_target': 'lb', 'reason': "required dependency on 'lb', whose redundancy group (lb) is entirely down"}`
- **Remediation:** Add redundancy for 'lb', or confirm 'client' genuinely cannot tolerate that dependency being unavailable.

### [HIGH] 'lb' goes down as a consequence (`component_down_cascaded`, confidence: heuristic)

'lb' was not directly failed, but goes down due to a required dependency on 'app-1', whose redundancy group (app-1, app-2) is entirely down.

- **Affected resources:** app-1, lb
- **Evidence:** `{'dependency_target': 'app-1', 'reason': "required dependency on 'app-1', whose redundancy group (app-1, app-2) is entirely down"}`
- **Remediation:** Add redundancy for 'app-1', or confirm 'lb' genuinely cannot tolerate that dependency being unavailable.

### [MEDIUM] 'lb' is a required dependency with no redundancy (`dependency_without_redundancy`, confidence: confirmed)

'client' has a required dependency on 'lb', which declares no redundancy_group peers. This is read directly from the topology, not inferred.

- **Affected resources:** lb, client
- **Evidence:** `{'target': 'lb', 'members': ['lb']}`
- **Remediation:** Give 'lb' a redundant peer, or confirm this dependency is genuinely required rather than optional.

### [MEDIUM] 'db' is a required dependency with no redundancy (`dependency_without_redundancy`, confidence: confirmed)

'app-1' has a required dependency on 'db', which declares no redundancy_group peers. This is read directly from the topology, not inferred.

- **Affected resources:** db, app-1
- **Evidence:** `{'target': 'db', 'members': ['db']}`
- **Remediation:** Give 'db' a redundant peer, or confirm this dependency is genuinely required rather than optional.

### [LOW] Topology warning: no_failure_domains_declared (`topology_warning.no_failure_domains_declared`, confidence: confirmed)

No component declares a failure_domain, so domain-level failure scenarios (--failure-domain) have nothing to target.



## Assumptions

- A component is 'down' only if explicitly failed, or if ALL members of a required dependency's redundancy group are down — there is no partial-capability model.
- Redundant peers (same redundancy_group) are treated as fully interchangeable: which specific peer actually serves a request is not modeled.
- An optional (required: false) dependency never propagates failure.

## Limitations

- This is a structural model of declared dependencies, not a measurement of a real system: no network partitions, no correlated failures, no provider SLAs.
- No availability percentage (e.g. '99.99%') is claimed anywhere — only what the declared topology and failure scenario imply structurally.
- Surviving-capacity ratios are only computed for a redundancy group where every member declares a 'capacity' value; otherwise it is reported as unknown, not assumed.

## Recommended next steps

- 4 component(s) go down as a consequence of this scenario, not directly — trace each via its finding's evidence.
- Review HIGH-severity findings and any SPOF before relying on this topology.
