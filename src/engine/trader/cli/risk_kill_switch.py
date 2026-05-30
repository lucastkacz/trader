"""Operator CLI for durable runtime risk kill-switch control."""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from src.engine.trader.config import load_pipeline_config
from src.engine.trader.runtime.risk import (
    RiskKillSwitchState,
    activate_risk_kill_switch,
    clear_risk_kill_switch,
    get_risk_kill_switch_state,
)
from src.engine.trader.state.manager import TradeStateManager


@dataclass(frozen=True)
class RiskKillSwitchCommandResult:
    action: str
    db_path: Path
    state: RiskKillSwitchState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or update the durable runtime risk kill switch"
    )
    add_risk_kill_switch_arguments(parser)
    return parser


def add_risk_kill_switch_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "risk-kill-switch",
        help="Inspect, activate, or clear the runtime risk kill switch",
    )
    add_risk_kill_switch_arguments(parser)
    return parser


def add_risk_kill_switch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pipeline",
        type=str,
        default=None,
        help="Path to typed pipeline YAML used to derive the runtime DB path",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Explicit runtime SQLite DB path; overrides --pipeline when both are set",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    subparsers = parser.add_subparsers(dest="risk_kill_switch_action", required=True)

    subparsers.add_parser("inspect", help="Inspect the current kill-switch state")

    activate_parser = subparsers.add_parser(
        "activate",
        help="Block future entries by activating the risk kill switch",
    )
    activate_parser.add_argument(
        "--reason",
        required=True,
        help="Operator-visible reason for activating the kill switch",
    )

    subparsers.add_parser("clear", help="Clear the risk kill switch")


def risk_kill_switch_from_args(
    args: argparse.Namespace,
) -> RiskKillSwitchCommandResult:
    db_path = _resolve_db_path(args)
    state_manager = TradeStateManager(db_path=str(db_path))
    try:
        action = args.risk_kill_switch_action
        if action == "inspect":
            switch_state = get_risk_kill_switch_state(state_manager)
        elif action == "activate":
            switch_state = activate_risk_kill_switch(
                state_manager,
                reason=args.reason,
            )
        elif action == "clear":
            switch_state = clear_risk_kill_switch(state_manager)
        else:
            raise ValueError(f"Unsupported risk kill-switch action: {action}")
    finally:
        state_manager.close()

    return RiskKillSwitchCommandResult(
        action=action,
        db_path=db_path,
        state=switch_state,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = risk_kill_switch_from_args(args)
    except Exception as exc:
        print(f"Risk kill-switch command failed: {exc}", file=sys.stderr)
        return 1

    print_risk_kill_switch_result(result, as_json=args.json)
    return 0


def _resolve_db_path(args: argparse.Namespace) -> Path:
    if args.db_path is not None:
        return Path(args.db_path)
    if args.pipeline is not None:
        pipeline_cfg = load_pipeline_config(args.pipeline)
        return Path(pipeline_cfg.execution.db_path)
    raise ValueError("Either --pipeline or --db-path is required")


def print_risk_kill_switch_result(
    result: RiskKillSwitchCommandResult,
    *,
    as_json: bool,
) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "action": result.action,
                    "db_path": str(result.db_path),
                    "state": asdict(result.state),
                },
                indent=2,
            )
        )
        return

    print("RISK KILL SWITCH")
    print(f"Action: {result.action}")
    print(f"DB: {result.db_path}")
    print(f"Active: {result.state.active}")
    if result.state.reason is not None:
        print(f"Reason: {result.state.reason}")
    if result.state.activated_at is not None:
        print(f"Activated at: {result.state.activated_at}")


if __name__ == "__main__":
    raise SystemExit(main())
