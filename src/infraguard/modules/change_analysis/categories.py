"""Heuristic resource-category detection, by substring match on the resource `type` string.

This is intentionally simple and intentionally not authoritative: it is a documented
pattern match across common provider naming conventions (AWS, Google Cloud, Azure), not a
real understanding of any provider's schema. A `type` that matches no pattern is tagged
OTHER — which means "we don't have a specific rule for this," never "this is safe."
See docs/CHANGE_ANALYSIS.md for the full, current pattern list and its limitations.
"""

from infraguard.modules.change_analysis.models import ResourceCategory

_PATTERNS: dict[ResourceCategory, tuple[str, ...]] = {
    ResourceCategory.DATABASE: (
        "db_instance",
        "rds_cluster",
        "rds_global_cluster",
        "database",
        "sql_database",
        "elasticache",
        "dynamodb_table",
        "cosmosdb",
        "documentdb",
        "redshift",
    ),
    ResourceCategory.STORAGE: (
        "s3_bucket",
        "storage_bucket",
        "storage_account",
        "ebs_volume",
        "disk",
        "blob",
        "efs_file_system",
        "filestore",
    ),
    ResourceCategory.IAM: (
        "iam_role",
        "iam_policy",
        "iam_user",
        "iam_group",
        "iam_access_key",
        "role_binding",
        "service_account",
        "key_vault_access_policy",
    ),
    ResourceCategory.NETWORKING: (
        "security_group",
        "network_acl",
        "vpc",
        "subnet",
        "route_table",
        "route53",
        "firewall",
        "nat_gateway",
        "load_balancer",
        "lb_listener",
        "network_interface",
    ),
    ResourceCategory.COMPUTE: (
        "instance",
        "vm_",
        "_vm",
        "compute_instance",
        "autoscaling_group",
        "container_group",
        "ecs_service",
        "eks_cluster",
        "kubernetes_cluster",
    ),
}

# Order matters: more specific categories are checked before the broad COMPUTE bucket so
# e.g. "db_instance" is matched as DATABASE rather than falling through to COMPUTE on
# "instance".
_CATEGORY_ORDER = (
    ResourceCategory.DATABASE,
    ResourceCategory.STORAGE,
    ResourceCategory.IAM,
    ResourceCategory.NETWORKING,
    ResourceCategory.COMPUTE,
)


def categorize(resource_type: str) -> ResourceCategory:
    type_lower = resource_type.lower()
    for category in _CATEGORY_ORDER:
        if any(pattern in type_lower for pattern in _PATTERNS[category]):
            return category
    return ResourceCategory.OTHER
