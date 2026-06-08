"""Operator CLI for promoting candidate eligible-pair artifacts."""

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.exchange.config.venue import ExchangeVenueConfig, load_exchange_venue_config
from src.engine.trader.config import PipelineConfig, load_pipeline_config
from src.engine.trader.runtime.artifacts import (
    DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS,
    PairRefreshPromotionPolicy,
    promote_candidate_pair_artifact,
    promotion_audit_path,
)


@dataclass(frozen=True)
class PromotionCommandResult:
    promoted_path: Path
    audit_path: Path


def promote_pairs_from_pipeline_config(
    pipeline_cfg: PipelineConfig,
    venue_cfg: ExchangeVenueConfig,
    max_age_seconds: int = DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS,
    audit_path: str | Path | None = None,
    operator: str | None = None,
    now: datetime | None = None,
) -> PromotionCommandResult:
    """Promote the candidate artifact described by typed pipeline config."""
    promoted_at = now or datetime.now(timezone.utc)
    resolved_audit_path = Path(audit_path) if audit_path is not None else promotion_audit_path(
        pipeline_cfg.timeframe,
        pipeline_cfg.execution.artifact_base_dir,
    )
    promoted_path = promote_candidate_pair_artifact(
        timeframe=pipeline_cfg.timeframe,
        exchange=venue_cfg.exchange_id,
        base_dir=pipeline_cfg.execution.artifact_base_dir,
        max_age_seconds=max_age_seconds,
        now=promoted_at,
        audit_path=resolved_audit_path,
        operator=operator,
        pipeline_name=pipeline_cfg.name,
        pair_refresh_policy=PairRefreshPromotionPolicy(
            mode=pipeline_cfg.execution.pair_refresh.mode,
            reload_policy=pipeline_cfg.execution.pair_refresh.reload_policy,
            stale_open_position_policy=(
                pipeline_cfg.execution.pair_refresh.stale_open_position_policy
            ),
        ),
    )
    return PromotionCommandResult(
        promoted_path=promoted_path,
        audit_path=resolved_audit_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote a validated candidate eligible-pair artifact"
    )
    add_promote_pairs_arguments(parser)
    return parser


def add_promote_pairs_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "promote-pairs",
        help="Promote a candidate eligible-pair artifact",
    )
    add_promote_pairs_arguments(parser)
    return parser


def add_promote_pairs_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pipeline", type=str, required=True, help="Path to pipeline YAML config")
    parser.add_argument("--venue", type=str, required=True, help="Path to exchange venue YAML config")
    parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=DEFAULT_PAIR_ARTIFACT_MAX_AGE_SECONDS,
        help="Maximum allowed candidate artifact age in seconds",
    )
    parser.add_argument(
        "--audit-path",
        type=str,
        default=None,
        help="Path to append the promotion audit JSONL record",
    )
    parser.add_argument(
        "--operator",
        type=str,
        default=None,
        help="Operator identifier recorded in the audit event",
    )


def promote_pairs_from_args(args: argparse.Namespace) -> PromotionCommandResult:
    pipeline_cfg = load_pipeline_config(args.pipeline)
    venue_cfg = load_exchange_venue_config(args.venue)
    return promote_pairs_from_pipeline_config(
        pipeline_cfg=pipeline_cfg,
        venue_cfg=venue_cfg,
        max_age_seconds=args.max_age_seconds,
        audit_path=args.audit_path,
        operator=args.operator,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = promote_pairs_from_args(args)
    except Exception as exc:
        print(f"Promotion failed: {exc}", file=sys.stderr)
        return 1

    print(f"Promoted artifact: {result.promoted_path}")
    print(f"Promotion audit: {result.audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
