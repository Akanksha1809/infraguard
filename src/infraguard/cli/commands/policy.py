import typer

from infraguard.core.rule_registry import RULES
from infraguard.modules.change_analysis.policy import PolicyConfig


def register(app: typer.Typer) -> None:
    @app.command("policy")
    def policy_show(
        module: str | None = typer.Option(
            None,
            "--module",
            help="Filter the rule catalog: change_analysis | failure_simulation | disaster_recovery.",
        ),
    ) -> None:
        """Show the active CI policy and the full rule catalog across all modules."""
        default_policy = PolicyConfig()
        typer.echo("Change-analysis CI policy (default; override per-run with --policy):")
        typer.echo(f"  fail_on_severity_at_or_above: {default_policy.fail_on_severity_at_or_above.value}")
        typer.echo(f"  warn_on_severity_at_or_above: {default_policy.warn_on_severity_at_or_above.value}")
        typer.echo(f"  strict_on_parse_warnings: {default_policy.strict_on_parse_warnings}")
        typer.echo("")
        typer.echo(
            "Failure-simulation and disaster-recovery have no severity-threshold CI policy "
            "(see docs/POLICY_REFERENCE.md) — their rule catalog below is fixed, not configurable."
        )
        typer.echo("")
        typer.echo("Rule catalog (severity shown is the default; some vary by context):")
        for rule in RULES:
            if module and rule.module != module:
                continue
            typer.echo(f"  [{rule.module}] {rule.rule_id} ({rule.default_severity}): {rule.description}")
