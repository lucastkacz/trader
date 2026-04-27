import asyncio
import argparse
import yaml

from src.pipeline.master_flow import research_flow, execute_flow

def load_yaml(path: str) -> dict:
    if not path: return {}
    with open(path, "r") as f:
        # returns the first top-level key's dict. e.g. 'pipeline', 'strategy', etc.
        data = yaml.safe_load(f)
        if not data: return {}
        return list(data.values())[0]

async def main():
    parser = argparse.ArgumentParser(description="Trader Institutional Framework")
    subparsers = parser.add_subparsers(dest="command", help="Operational Mode")

    # --- RESEARCH COMMAND ---
    research_parser = subparsers.add_parser("research", help="Run Historical Data Mining and Vector Stress Testing")
    research_parser.add_argument("--pipeline", type=str, required=True, help="Path to pipeline YAML config")
    research_parser.add_argument("--universe", type=str, required=True, help="Path to universe YAML config")
    research_parser.add_argument("--backtest", type=str, required=True, help="Path to backtest YAML config")
    research_parser.add_argument("--strategy", type=str, required=True, help="Path to strategy YAML config")
    research_parser.add_argument("--skip-fetch", action="store_true", help="Dirty Run: Skip API Fetch")

    # --- EXECUTE COMMAND ---
    execute_parser = subparsers.add_parser("execute", help="Launch the Live Trading Execution Engine")
    execute_parser.add_argument("--pipeline", type=str, required=True, help="Path to pipeline YAML config")
    execute_parser.add_argument("--strategy", type=str, required=True, help="Path to strategy YAML config")
    execute_parser.add_argument("--telegram", type=str, default=None, help="Path to telegram YAML config")

    args = parser.parse_args()

    if args.command == "research":
        pipeline_cfg = load_yaml(args.pipeline)
        universe_cfg = load_yaml(args.universe)
        backtest_cfg = load_yaml(args.backtest)
        strategy_cfg = load_yaml(args.strategy)
        
        await research_flow(
            pipeline_cfg=pipeline_cfg, 
            universe_cfg=universe_cfg, 
            backtest_cfg=backtest_cfg,
            strategy_cfg=strategy_cfg,
            skip_fetch=args.skip_fetch
        )

    elif args.command == "execute":
        pipeline_cfg = load_yaml(args.pipeline)
        strategy_cfg = load_yaml(args.strategy)
        
        await execute_flow(
            pipeline_cfg=pipeline_cfg,
            strategy_cfg=strategy_cfg,
            telegram_path=args.telegram
        )
        
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
