import asyncio
import argparse

from src.engine.trader.config import (
    load_backtest_config,
    load_pipeline_config,
    load_risk_config,
    load_run_profile_config,
    load_strategy_config,
    load_universe_config,
    PipelineConfig,
)
from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)
from src.engine.trader.cli.promote_pairs import (
    add_promote_pairs_parser,
    promote_pairs_from_args,
)
from src.engine.trader.cli.risk_kill_switch import (
    add_risk_kill_switch_parser,
    print_risk_kill_switch_result,
    risk_kill_switch_from_args,
)
from src.pipeline.master_flow import research_flow, execute_flow

async def main():
    parser = argparse.ArgumentParser(description="Trader Institutional Framework")
    subparsers = parser.add_subparsers(dest="command", help="Operational Mode")

    # --- RESEARCH COMMAND ---
    research_parser = subparsers.add_parser("research", help="Run Historical Data Mining and Vector Stress Testing")
    research_parser.add_argument("--pipeline", type=str, required=True, help="Path to pipeline YAML config")
    research_parser.add_argument("--venue", type=str, required=True, help="Path to exchange venue YAML config")
    research_parser.add_argument("--market-profile", type=str, required=True, help="Path to CCXT market profile YAML config")
    research_parser.add_argument("--universe", type=str, required=True, help="Path to universe YAML config")
    research_parser.add_argument("--backtest", type=str, required=True, help="Path to backtest YAML config")
    research_parser.add_argument("--strategy", type=str, required=True, help="Path to strategy YAML config")
    research_parser.add_argument("--skip-fetch", action="store_true", help="Dirty Run: Skip API Fetch")

    # --- RUN PROFILE COMMAND ---
    run_parser = subparsers.add_parser("run", help="Run research from a typed run profile")
    run_parser.add_argument("--config", type=str, required=True, help="Path to run profile YAML config")

    # --- EXECUTE COMMAND ---
    execute_parser = subparsers.add_parser("execute", help="Launch the Live Trading Execution Engine")
    execute_parser.add_argument("--pipeline", type=str, required=True, help="Path to pipeline YAML config")
    execute_parser.add_argument("--venue", type=str, required=True, help="Path to exchange venue YAML config")
    execute_parser.add_argument("--market-profile", type=str, required=True, help="Path to CCXT market profile YAML config")
    execute_parser.add_argument("--strategy", type=str, required=True, help="Path to strategy YAML config")
    execute_parser.add_argument("--risk", type=str, required=True, help="Path to risk YAML config")
    execute_parser.add_argument("--telegram", type=str, default=None, help="Path to telegram YAML config")
    execute_parser.add_argument("--max-ticks", type=_positive_int, default=None, help="Override execution max_ticks for bounded local drills")
    execute_parser.add_argument("--heartbeat-seconds", type=_positive_int, default=None, help="Override execution heartbeat_seconds for bounded local drills")

    # --- PROMOTION COMMAND ---
    add_promote_pairs_parser(subparsers)

    # --- RISK KILL SWITCH COMMAND ---
    add_risk_kill_switch_parser(subparsers)

    args = parser.parse_args()

    if args.command == "research":
        pipeline_cfg = load_pipeline_config(args.pipeline)
        venue_cfg = load_exchange_venue_config(args.venue)
        exchange_config = load_ccxt_exchange_config(args.market_profile)
        universe_cfg = load_universe_config(args.universe)
        backtest_cfg = load_backtest_config(args.backtest)
        strategy_cfg = load_strategy_config(args.strategy)
        
        await research_flow(
            pipeline_cfg=pipeline_cfg, 
            venue_cfg=venue_cfg,
            exchange_config=exchange_config,
            universe_cfg=universe_cfg, 
            backtest_cfg=backtest_cfg,
            strategy_cfg=strategy_cfg,
            skip_fetch=args.skip_fetch
        )

    elif args.command == "run":
        run_profile = load_run_profile_config(args.config)
        pipeline_cfg = load_pipeline_config(run_profile.pipeline)
        venue_cfg = load_exchange_venue_config(run_profile.venue)
        exchange_config = load_ccxt_exchange_config(run_profile.market_profile)
        universe_cfg = load_universe_config(run_profile.universe)
        backtest_cfg = load_backtest_config(run_profile.backtest)
        strategy_cfg = load_strategy_config(run_profile.strategy)

        await research_flow(
            pipeline_cfg=pipeline_cfg,
            venue_cfg=venue_cfg,
            exchange_config=exchange_config,
            universe_cfg=universe_cfg,
            backtest_cfg=backtest_cfg,
            strategy_cfg=strategy_cfg,
            skip_fetch=run_profile.skip_fetch,
        )

    elif args.command == "execute":
        pipeline_cfg = load_pipeline_config(args.pipeline)
        venue_cfg = load_exchange_venue_config(args.venue)
        exchange_config = load_ccxt_exchange_config(args.market_profile)
        strategy_cfg = load_strategy_config(args.strategy)
        risk_cfg = load_risk_config(args.risk)
        pipeline_cfg = apply_execution_overrides(
            pipeline_cfg,
            max_ticks=args.max_ticks,
            heartbeat_seconds=args.heartbeat_seconds,
        )
        
        await execute_flow(
            pipeline_cfg=pipeline_cfg,
            venue_cfg=venue_cfg,
            exchange_config=exchange_config,
            strategy_cfg=strategy_cfg,
            risk_cfg=risk_cfg,
            telegram_path=args.telegram
        )

    elif args.command == "promote-pairs":
        result = promote_pairs_from_args(args)
        print(f"Promoted artifact: {result.promoted_path}")
        print(f"Promotion audit: {result.audit_path}")

    elif args.command == "risk-kill-switch":
        result = risk_kill_switch_from_args(args)
        print_risk_kill_switch_result(result, as_json=args.json)
        
    else:
        parser.print_help()

def apply_execution_overrides(
    pipeline_cfg: PipelineConfig,
    *,
    max_ticks: int | None = None,
    heartbeat_seconds: int | None = None,
) -> PipelineConfig:
    """Return a pipeline config with CLI-only execution overrides applied."""
    if max_ticks is None and heartbeat_seconds is None:
        return pipeline_cfg

    execution_data = pipeline_cfg.execution.model_dump()
    if max_ticks is not None:
        execution_data["max_ticks"] = max_ticks
    if heartbeat_seconds is not None:
        execution_data["heartbeat_seconds"] = heartbeat_seconds

    pipeline_data = pipeline_cfg.model_dump()
    pipeline_data["execution"] = execution_data
    return PipelineConfig.model_validate(pipeline_data)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed

if __name__ == "__main__":
    asyncio.run(main())
