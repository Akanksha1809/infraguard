# InfraGuard Report — change_analysis

- **Run ID:** `a0b2b8676650438a832cfd1220eb10c6`
- **Created:** 2026-10-19T17:35:35.392061+00:00
- **Schema version:** 1

## Policy decision

- **Decision:** `WARN` (exit code 0)
- **Reason:** 3 finding(s) at or above severity 'medium', below the fail threshold.
- **Triggered by findings:** 9a87af05f89f, 26a2b04e9df9, ceef5eac44b6

## Findings (3)

### [MEDIUM] 9 attribute(s) of local_file.config are unknown until apply (`unknown_after_values`, confidence: confirmed)

'local_file.config' has 9 attribute(s) whose final value Terraform cannot determine from this plan alone (they depend on values only known after apply). InfraGuard cannot assess risk for these specific attributes from static plan data — this is a gap, not a clean bill of health.

- **Affected resources:** local_file.config
- **Evidence:** `{'unknown_paths': ['content', 'content_base64sha256', 'content_base64sha512', 'content_md5', 'content_sha1', 'content_sha256', 'content_sha512', 'filename', 'id'], 'unknown_path_count': 9, 'truncated': False}`
- **Remediation:** Re-run analysis after apply, or inspect these attributes manually.

### [MEDIUM] 9 attribute(s) of local_file.readme are unknown until apply (`unknown_after_values`, confidence: confirmed)

'local_file.readme' has 9 attribute(s) whose final value Terraform cannot determine from this plan alone (they depend on values only known after apply). InfraGuard cannot assess risk for these specific attributes from static plan data — this is a gap, not a clean bill of health.

- **Affected resources:** local_file.readme
- **Evidence:** `{'unknown_paths': ['content', 'content_base64sha256', 'content_base64sha512', 'content_md5', 'content_sha1', 'content_sha256', 'content_sha512', 'filename', 'id'], 'unknown_path_count': 9, 'truncated': False}`
- **Remediation:** Re-run analysis after apply, or inspect these attributes manually.

### [MEDIUM] 1 attribute(s) of random_pet.suffix are unknown until apply (`unknown_after_values`, confidence: confirmed)

'random_pet.suffix' has 1 attribute(s) whose final value Terraform cannot determine from this plan alone (they depend on values only known after apply). InfraGuard cannot assess risk for these specific attributes from static plan data — this is a gap, not a clean bill of health.

- **Affected resources:** random_pet.suffix
- **Evidence:** `{'unknown_paths': ['id'], 'unknown_path_count': 1, 'truncated': False}`
- **Remediation:** Re-run analysis after apply, or inspect these attributes manually.


## Assumptions

- Resource categories (database, storage, IAM, networking, compute) are determined by substring pattern matching on the resource type name, not a real provider schema.
- Dependency edges come from Terraform's own 'references' and 'depends_on' metadata in the plan's configuration block, root module only.
- A missing or absent field in the plan is never treated as evidence that a change is safe.

## Limitations

- Resources inside child modules are not resolved for dependency analysis (see any 'module_scoped_dependencies_unsupported' finding).
- Attributes unknown until apply cannot be risk-assessed from the plan alone (see any 'unknown_after_values' finding).
- This analysis is based solely on the supplied plan JSON; it does not inspect actual cloud state, IAM policy semantics, or network reachability.

## Recommended next steps

- Review each HIGH or CRITICAL finding before applying this plan.
- Re-run analysis if the plan is regenerated, since attribute values and dependencies may change.
