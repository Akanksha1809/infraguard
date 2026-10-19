import pytest

from infraguard.modules.change_analysis.categories import categorize
from infraguard.modules.change_analysis.models import ResourceCategory


@pytest.mark.parametrize(
    ("resource_type", "expected"),
    [
        ("aws_db_instance", ResourceCategory.DATABASE),
        ("google_sql_database_instance", ResourceCategory.DATABASE),
        ("aws_s3_bucket", ResourceCategory.STORAGE),
        ("azurerm_storage_account", ResourceCategory.STORAGE),
        ("aws_iam_role", ResourceCategory.IAM),
        ("aws_security_group", ResourceCategory.NETWORKING),
        ("aws_instance", ResourceCategory.COMPUTE),
        ("widgetco_thingamajig", ResourceCategory.OTHER),
    ],
)
def test_categorize(resource_type: str, expected: ResourceCategory) -> None:
    assert categorize(resource_type) is expected


def test_db_instance_is_not_misclassified_as_compute() -> None:
    # "db_instance" contains "instance" but must match DATABASE first.
    assert categorize("aws_db_instance") is ResourceCategory.DATABASE
